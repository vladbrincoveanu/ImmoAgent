import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import os
import json
import time
from types import SimpleNamespace
from Application.helpers.utils import load_config
from Application.helpers.listing_validator import compute_content_fingerprint, compute_xsrc_fingerprint
from Application.helpers.mortgage import add_monthly_payment_calculation
from Application.buyer_profiles import GLOBAL_VALIDATION, BUYER_PROFILES
from Domain.constants import RENTAL_KEYWORDS, PRICE_ON_REQUEST_KEYWORDS
import logging
logger = logging.getLogger(__name__)

# Per-profile precalculation support
PROFILE_NAMES: list[str] = list(BUYER_PROFILES.keys())


def is_valid_listing_data(listing: Dict) -> Tuple[bool, str]:
    """
    Validate listing data against GLOBAL_VALIDATION thresholds.
    Returns (is_valid, reason). Lenient: missing price/area passes.
    """
    config = GLOBAL_VALIDATION  # noqa: F811 - imported from buyer_profiles at module level
    price = listing.get('price_total')
    area = listing.get('area_m2')

    if price is not None and area is not None and area > 0:
        per_m2 = price / area
        if per_m2 < config['min_price_per_m2']:
            return False, f"price_per_m2 {per_m2:.0f} below minimum {config['min_price_per_m2']}"
        if per_m2 > config['max_price_per_m2']:
            return False, f"price_per_m2 {per_m2:.0f} above maximum {config['max_price_per_m2']}"

    return True, ""


class MongoDBHandler:
    def __init__(self, uri: str = None, db_name: str = "immo", collection_name: str = "listings"):
        config = load_config()
        self.uri = uri or config.get("mongodb_uri") or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
        
        # Handle SSL connection for MongoDB Atlas in GitHub Actions
        if "mongodb.net" in self.uri:
            # Add TLS parameters for GitHub Actions compatibility
            separator = "&" if "?" in self.uri else "?"
            if "tlsAllowInvalidCertificates=true" not in self.uri:
                self.uri = f"{self.uri}{separator}tlsAllowInvalidCertificates=true"
            logging.info("🔧 Added TLS parameters to MongoDB URI for GitHub Actions compatibility")
        
        try:
            # Create MongoDB client with specific options for GitHub Actions
            client_options = {
                'serverSelectionTimeoutMS': 30000,
                'connectTimeoutMS': 30000,
                'socketTimeoutMS': 30000,
            }
            
            # Add TLS options if using MongoDB Atlas
            if "mongodb.net" in self.uri:
                client_options.update({
                    'tlsAllowInvalidCertificates': True,
                })
            
            self.client = MongoClient(self.uri, **client_options)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            self.metrics_collection = self.db["validation_metrics"]
            self.outreach_collection = self.db["outreach_jobs"]
            self.source_meta_collection = self.db["source_meta"]

            # Test the connection
            self.client.admin.command('ping')
            logging.info("✅ MongoDB connection successful!")
            
        except Exception as e:
            logging.error(f"❌ MongoDB connection failed: {e}")
            self.client = None
            self.db = None
            self.collection = None
        
        # Try to create index, but don't fail if authentication is required
        try:
            self.collection.create_index("url", unique=True)
            self.collection.create_index([("content_fingerprint", 1), ("source_enum", 1)])
            self.collection.create_index([("source_enum", 1), ("score", -1)])
            self.collection.create_index([("bezirk", 1), ("price_per_m2", 1)])
            self.collection.create_index([("url_is_valid", 1), ("processed_at", -1)])
            self.collection.create_index([("sent_to_telegram", 1), ("processed_at", -1)])
            self.collection.create_index("price_total")
            self.collection.create_index("processed_at")
            self.collection.create_index([("score", -1), ("processed_at", -1)], name='score_processed_idx')
            self.collection.create_index("year_built")
            self.collection.create_index([("listing_status", 1), ("processed_at", -1)])
            self.collection.create_index([("listing_status", 1), ("source_enum", 1)])
            self.collection.create_index([("listing_status", 1), ("bezirk", 1)])
            # Co-op cross-source dedup key (v1): only set on genossenschaft listings.
            self.collection.create_index(
                "content_fingerprint_xsrc",
                partialFilterExpression={"content_fingerprint_xsrc": {"$exists": True}},
                name="coop_xsrc_fp",
            )
            # Per-profile score indexes (compound with processed_at for stable tiebreak)
            for _profile in PROFILE_NAMES:
                try:
                    self.collection.create_index(
                        [(f"scores.{_profile}", -1), ("processed_at", -1)],
                        name=f"scores_{_profile}_idx",
                    )
                except Exception as e:
                    logging.warning(f"Could not create index scores.{_profile}: {e}")
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, skipping index creation: {e}")
            else:
                print(f"⚠️  Could not create MongoDB index: {e}")
        except Exception as e:
            print(f"⚠️  MongoDB initialization warning: {e}")

        # Create outreach job queue indexes
        try:
            self.outreach_collection.create_index([('status', 1), ('next_retry', 1)])
            self.outreach_collection.create_index([('recipient_email', 1)])
        except Exception as e:
            logging.warning(f"Could not create outreach indexes: {e}")

    def close(self):
        """Close the MongoDB connection"""
        if hasattr(self, 'client') and self.client:
            self.client.close()

    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()

    def insert_listing(self, listing: Dict) -> bool:
        price_val = listing.get('price_total')
        if not isinstance(price_val, (int, float)) or price_val <= 0:
            logging.info(f"🚫 Skipping save: invalid or missing price_total ({price_val}) for URL {listing.get('url')}")
            return False

        valid, reason = is_valid_listing_data(listing)
        if not valid:
            logging.info(f"🚫 Skipping save: validation failed — {reason}")
            source = listing.get('source_enum', listing.get('source', 'unknown'))
            self.increment_validation_failure(source)
            return False

        # Co-op cross-source dedup (v1): collapse same unit across Willhaben + Bauträger.
        # compute_xsrc_fingerprint() expects attribute-style access (it was written against
        # the Listing dataclass), but insert_listing() always receives a plain dict — wrap
        # it in SimpleNamespace so the same fields resolve without touching that function.
        if listing.get('is_genossenschaft'):
            xfp = compute_xsrc_fingerprint(SimpleNamespace(**listing))
            if xfp:
                listing['content_fingerprint_xsrc'] = xfp
                try:
                    existing = self.collection.find_one({"content_fingerprint_xsrc": xfp})
                    if existing:
                        # Prefer Bauträger-direct (canonical apply URL) over Willhaben.
                        if (listing.get('coop_source') == 'bautraeger_direct'
                                and existing.get('coop_source') == 'willhaben'):
                            self.collection.update_one(
                                {"_id": existing["_id"]},
                                {"$set": {
                                    "url": listing.get('url'),
                                    "coop_source": 'bautraeger_direct',
                                    "bautraeger": listing.get('bautraeger'),
                                }}
                            )
                        logging.info(f"🚫 Skipping cross-source co-op duplicate: {xfp}")
                        return True
                except pymongo.errors.DuplicateKeyError:
                    return False
                except pymongo.errors.OperationFailure as e:
                    if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                        print(f"MongoDB co-op dedup error: command insert requires authentication, full error: {e}")
                    else:
                        print(f"MongoDB co-op dedup error: {e}")
                    return False
                except Exception as e:
                    print(f"MongoDB co-op dedup error: {e}")
                    return False

        fingerprint = compute_content_fingerprint(listing)
        listing['content_fingerprint'] = fingerprint

        try:
            existing_fingerprint = self.collection.find_one(
                {"content_fingerprint": fingerprint, "source_enum": listing.get('source_enum', listing.get('source'))}
            )
            if existing_fingerprint:
                logging.info(f"🚫 Skipping duplicate by content fingerprint: {listing.get('title')} (URL: {listing.get('url')})")
                return True
            self.collection.insert_one(listing)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"MongoDB insert error: command insert requires authentication, full error: {e}")
            else:
                print(f"MongoDB insert error: {e}")
            return False
        except Exception as e:
            print(f"MongoDB insert error: {e}")
            return False

    def upsert_coop_listing(self, listing: Dict) -> str:
        """Upsert a co-op listing WITHOUT the price>0 gate (co-op units often
        have no purchase price). Mirrors the co-op branch of
        save_listings_to_mongodb (validation → xsrc dedup → url upsert →
        fingerprint dedup → insert) minus geocoding/scoring.

        Preserves send-state on update so a */5 re-poll never resets
        sent_to_telegram and re-spams. Returns one of:
        "inserted" | "updated" | "duplicate" | "invalid" | "error"."""
        if self.collection is None:
            return "error"
        valid, reason = is_valid_listing_data(listing)
        if not valid:
            logging.info(f"🚫 coop upsert skipped — {reason}")
            return "invalid"
        try:
            # Cross-source dedup (Willhaben ↔ Bauträger-direct for one unit).
            if listing.get('is_genossenschaft'):
                xfp = compute_xsrc_fingerprint(SimpleNamespace(**listing))
                if xfp:
                    listing['content_fingerprint_xsrc'] = xfp
                    existing = self.collection.find_one({"content_fingerprint_xsrc": xfp})
                    if existing and existing.get('url') != listing.get('url'):
                        if (listing.get('coop_source') == 'bautraeger_direct'
                                and existing.get('coop_source') == 'willhaben'):
                            self.collection.update_one(
                                {"_id": existing["_id"]},
                                {"$set": {
                                    "url": listing.get('url'),
                                    "coop_source": 'bautraeger_direct',
                                    "bautraeger": listing.get('bautraeger'),
                                    "builder_url": listing.get('builder_url'),
                                }})
                        logging.info(f"🚫 coop xsrc duplicate: {xfp}")
                        return "duplicate"

            listing['content_fingerprint'] = compute_content_fingerprint(listing)

            existing_by_url = self.collection.find_one({"url": listing.get('url')})
            if existing_by_url:
                listing['_id'] = existing_by_url['_id']
                # NEVER reset send-state on re-poll → no 5-minute re-spam.
                for k in ("sent_to_telegram", "sent_to_telegram_at", "url_is_valid"):
                    if k in existing_by_url:
                        listing[k] = existing_by_url[k]
                # Keep a previously-resolved builder_url if this update lacks one
                # (only run_coop resolves it; other write paths would else wipe it).
                if not listing.get('builder_url') and existing_by_url.get('builder_url'):
                    listing['builder_url'] = existing_by_url['builder_url']
                self.collection.replace_one({"_id": existing_by_url['_id']}, listing)
                return "updated"

            source_enum = listing.get('source_enum', listing.get('source', ''))
            existing_by_fp = self.collection.find_one(
                {"content_fingerprint": listing['content_fingerprint'],
                 "source_enum": source_enum})
            if existing_by_fp:
                logging.info(f"🚫 coop fingerprint duplicate: {listing.get('url')}")
                return "duplicate"

            self.collection.insert_one(listing)
            return "inserted"
        except Exception as e:
            logging.error(f"upsert_coop_listing error: {e}")
            return "error"

    def update_profile_scores(self, listing_id, scores: dict) -> None:
        """Persist per-profile scores subdoc for a listing.

        Idempotent: $set is a no-op if values are unchanged.
        Skips silently if collection not initialized (e.g., when no Mongo connection).
        """
        if not scores:
            return
        if self.collection is None:
            logging.warning("update_profile_scores: collection unavailable; skipping")
            return
        try:
            from datetime import datetime, timezone
            self.collection.update_one(
                {"_id": listing_id},
                {
                    "$set": {
                        "scores": scores,
                        "scores_updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as e:
            logging.warning(f"update_profile_scores failed for _id={listing_id}: {e}")

    def upsert_listing_with_history(self, listing: Dict) -> bool:
        """Insert or update listing with price history tracking.

        On new listing: set first_scraped_at = processed_at, price_at_scrape = price_total
        On existing listing with price change: push old price to price_history
        Returns True on success, False on validation failure.
        """
        price_val = listing.get('price_total')
        if not isinstance(price_val, (int, float)) or price_val <= 0:
            logging.info(f"🚫 Skipping: invalid price_total ({price_val})")
            return False

        valid, reason = is_valid_listing_data(listing)
        if not valid:
            logging.info(f"🚫 Skipping: validation failed — {reason}")
            return False

        fingerprint = compute_content_fingerprint(listing)
        listing['content_fingerprint'] = fingerprint

        try:
            from datetime import datetime
            now = datetime.utcnow()

            existing = self.collection.find_one({
                "content_fingerprint": fingerprint,
                "source_enum": listing.get('source_enum', listing.get('source'))
            })

            if existing:
                old_price = existing.get('price_total')
                price_history = existing.get('price_history', [])

                if old_price and old_price != price_val:
                    price_history.append({
                        'price_total': old_price,
                        'recorded_at': now
                    })

                update_set = {
                    'price_total': price_val,
                    'price_history': price_history,
                    'processed_at': listing.get('processed_at', now.timestamp()),
                }
                if existing.get('price_at_scrape') is None:
                    update_set['price_at_scrape'] = old_price or price_val

                self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": update_set}
                )
                return True

            listing['first_scraped_at'] = listing.get('processed_at') or now.timestamp()
            listing['price_at_scrape'] = price_val
            listing['price_history'] = []
            listing['listing_status'] = 'active'

            self.collection.insert_one(listing)
            return True

        except pymongo.errors.DuplicateKeyError:
            existing = self.collection.find_one({"url": listing.get('url')})
            if existing:
                old_price = existing.get('price_total')
                price_history = existing.get('price_history', [])
                if old_price and old_price != price_val:
                    price_history.append({'price_total': old_price, 'recorded_at': datetime.utcnow()})
                self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        'price_total': price_val,
                        'price_history': price_history,
                        'processed_at': listing.get('processed_at', datetime.utcnow().timestamp()),
                        'price_at_scrape': existing.get('price_at_scrape') or old_price or price_val,
                        'listing_status': 'active'
                    }}
                )
            return True
        except Exception as e:
            logging.error(f"❌ upsert_listing_with_history error: {e}")
            return False

    def mark_listing_taken(self, url: str) -> bool:
        """Mark a listing as taken (offline/404)."""
        try:
            from datetime import datetime
            result = self.collection.update_one(
                {"url": url, "listing_status": {"$ne": "taken"}},
                {"$set": {
                    "listing_status": "taken",
                    "taken_at": datetime.utcnow(),
                    "url_is_valid": False
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"❌ mark_listing_taken error for {url}: {e}")
            return False

    def update_listing_coordinates(self, url: str, geocoded_listing: Dict) -> bool:
        """Update a listing's coordinates after geocoding."""
        try:
            result = self.collection.update_one(
                {"url": url},
                {"$set": {
                    "coordinates": geocoded_listing.get('coordinates'),
                    "coordinate_source": geocoded_listing.get('coordinate_source'),
                    "landmark_hint": geocoded_listing.get('landmark_hint'),
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"Error updating coordinates: {e}")
            return False

    def listing_exists(self, url: str) -> bool:
        try:
            return self.collection.find_one({"url": url}) is not None
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"MongoDB query error: command find requires authentication, full error: {e}")
            else:
                print(f"MongoDB query error: {e}")
            return False
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return False

    def mark_sent(self, url: str):
        """Mark a listing as sent to Telegram with timestamp"""
        try:
            from datetime import datetime
            sent_timestamp = datetime.now().timestamp()
            self.collection.update_one(
                {"url": url}, 
                {"$set": {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": sent_timestamp
                }}
            )
            logging.info(f"✅ Marked listing as sent to Telegram: {url}")
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, skipping update: {e}")
            else:
                logging.error(f"MongoDB update error: {e}")
        except Exception as e:
            logging.error(f"MongoDB update error: {e}")

    def mark_listings_sent(self, listings: List[Dict]):
        """Mark multiple listings as sent to Telegram"""
        try:
            from datetime import datetime
            sent_timestamp = datetime.now().timestamp()

            urls = [listing.get('url') for listing in listings if listing.get('url')]
            if not urls:
                return

            # Update all listings at once
            result = self.collection.update_many(
                {"url": {"$in": urls}},
                {"$set": {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": sent_timestamp
                }}
            )

            logging.info(f"✅ Marked {result.modified_count} listings as sent to Telegram")
            
            expected_count = len(urls)
            if result.modified_count < expected_count:
                logging.warning(f"⚠️ Only {result.modified_count}/{expected_count} listings marked as sent (some may not exist)")

        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, skipping update: {e}")
            else:
                logging.error(f"MongoDB update error: {e}")
        except Exception as e:
            logging.error(f"MongoDB update error: {e}")

    def mark_url_invalid(self, url: str) -> None:
        """Mark a listing URL as invalid/broken so future runs skip it."""
        try:
            from datetime import datetime
            if not url or not self.client:
                return
            result = self.collection.update_one(
                {"url": url},
                {"$set": {
                    "url_is_valid": False,
                    "url_invalidated_at": datetime.now().timestamp()
                }}
            )
            if result.modified_count > 0:
                logging.debug(f"Marked URL as invalid: {url}")
        except Exception as e:
            logging.warning(f"Failed to mark URL invalid in MongoDB: {e}")

    def get_source_meta(self, source: str) -> Dict:
        """Conditional-GET metadata for a coop adapter: {etag, last_modified, page_hash}.
        Returns {} when unknown or on error (caller then does an unconditional GET)."""
        try:
            doc = self.source_meta_collection.find_one({"source": source})
            if not doc:
                return {}
            return {k: doc.get(k) for k in ("etag", "last_modified", "page_hash")
                    if doc.get(k) is not None}
        except Exception as e:
            logging.warning(f"get_source_meta({source}) failed: {e}")
            return {}

    def set_source_meta(self, source: str, etag: Optional[str] = None,
                        last_modified: Optional[str] = None,
                        page_hash: Optional[str] = None) -> None:
        """Upsert conditional-GET metadata for a coop adapter. Only non-None
        fields are written, so a 304 (no new headers) never clobbers a good ETag."""
        try:
            update = {k: v for k, v in
                      (("etag", etag), ("last_modified", last_modified),
                       ("page_hash", page_hash)) if v is not None}
            if not update:
                return
            self.source_meta_collection.update_one(
                {"source": source}, {"$set": update}, upsert=True)
        except Exception as e:
            logging.warning(f"set_source_meta({source}) failed: {e}")

    def get_recently_sent_listings(self, days: int = 7) -> List[str]:
        """Get URLs of listings sent to Telegram in the last N days"""
        try:
            from datetime import datetime, timedelta
            cutoff_timestamp = (datetime.now() - timedelta(days=days)).timestamp()
            
            cursor = self.collection.find(
                {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": {"$gte": cutoff_timestamp}
                },
                {"url": 1}
            )
            
            urls = [doc.get('url') for doc in cursor if doc.get('url')]
            logging.info(f"📋 Found {len(urls)} listings sent to Telegram in last {days} days")
            return urls
            
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, returning empty list: {e}")
                return []
            else:
                logging.error(f"MongoDB query error: {e}")
                return []
        except Exception as e:
            logging.error(f"MongoDB query error: {e}")
            return []

    def get_unsent_listings(self):
        try:
            return list(self.collection.find({"sent_to_telegram": {"$ne": True}}))
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, returning empty list: {e}")
                return []
            else:
                print(f"MongoDB query error: {e}")
                return []
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return []

    def get_listing(self, url: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({"url": url})
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, returning None: {e}")
                return None
            else:
                print(f"MongoDB query error: {e}")
                return None
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return None
    
    def get_top_listings(self, limit: int = 5, min_score: float = 0.0, days_old: int = 30,
                        excluded_districts: List[str] = None, min_rooms: float = 0.0,
                        exclude_recently_sent: bool = True, recently_sent_days: int = 7,
                        profile: str = "default") -> List[Dict]:
        """
        Get top listings from MongoDB sorted by score with additional filters.

        Args:
            limit: Maximum number of listings to return
            min_score: Minimum score threshold
            days_old: Only include listings from last N days
            excluded_districts: List of district codes to exclude (e.g., ["1100", "1160"])
            min_rooms: Minimum number of rooms required
            exclude_recently_sent: Whether to exclude listings sent to Telegram in recent days
            recently_sent_days: Number of days to look back for recently sent listings
            profile: Which precalculated score to sort by. "default" uses legacy `score` field.

        Returns:
            List of listing dictionaries sorted by score (highest first)
        """
        try:
            if not self.client:
                logging.error("MongoDB client not connected")
                return []

            query = self._build_top_listings_query(
                days_old, min_score, excluded_districts, min_rooms,
                exclude_recently_sent, recently_sent_days,
            )
            listings = self._fetch_and_score_listings(query, limit, profile, min_score)
            for listing in listings:
                add_monthly_payment_calculation(listing)
            filtered = self._apply_top_listings_exclusion_filters(listings, limit)
            self._log_top_listings_summary(
                filtered, len(listings), min_score, days_old,
                excluded_districts, min_rooms, exclude_recently_sent, recently_sent_days,
            )
            return filtered
        except pymongo.errors.PyMongoError as e:
            logging.error(f"MongoDB error fetching top listings: {e}")
            return []

    def _build_top_listings_query(self, days_old, min_score, excluded_districts,
                                   min_rooms, exclude_recently_sent, recently_sent_days) -> Dict:
        """Build the MongoDB query for top-listing candidates. Pure query construction."""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_timestamp = cutoff_date.timestamp()

        base_query = {
            "processed_at": {"$gte": cutoff_timestamp},
            "url_is_valid": {"$ne": False},
        }

        if min_score > 0:
            base_query["$or"] = [
                {"score": {"$gte": min_score}},
                {"score": {"$exists": False}},
                {"score": None},
                {"score": 0},
            ]

        if excluded_districts and len(excluded_districts) > 0:
            base_query["bezirk"] = {"$nin": excluded_districts}

        if exclude_recently_sent:
            recently_sent_urls = self.get_recently_sent_listings(recently_sent_days)
            if recently_sent_urls:
                base_query["url"] = {"$nin": recently_sent_urls}
                logging.info(f"🚫 Excluding {len(recently_sent_urls)} recently sent listings")

        if min_rooms > 0:
            return {
                "$and": [
                    base_query,
                    {"$or": [{"rooms": {"$gte": min_rooms}}, {"rooms": None}]},
                ]
            }
        return base_query

    def _fetch_and_score_listings(self, query, limit, profile, min_score) -> List[Dict]:
        """Fetch candidates, calculate missing scores, filter by min_score, re-sort by score desc."""
        if profile == "default":
            sort_criteria = [("score", -1), ("processed_at", -1)]
        else:
            sort_criteria = [(f"scores.{profile}", -1), ("processed_at", -1)]

        cursor = self.db.listings.find(query).sort(sort_criteria).limit(limit * 3)
        listings = list(cursor)

        from Application.scoring import score_apartment_simple
        scores_calculated = 0
        for listing in listings:
            score_value = listing.get('score')
            # Case 1: score missing/None — always recalculate
            if score_value is None or 'score' not in listing:
                try:
                    listing['score'] = score_apartment_simple(listing)
                    scores_calculated += 1
                    logging.debug(f"📊 Calculated missing score: {listing['score']:.1f}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not calculate score: {e}")
                    listing['score'] = 0.0
            # Case 2: score is 0 — only recalculate if very recent (likely placeholder)
            elif score_value == 0:
                processed_at = listing.get('processed_at')
                if processed_at and isinstance(processed_at, (int, float)):
                    age_hours = (time.time() - processed_at) / 3600
                    if age_hours < 24:
                        try:
                            listing['score'] = score_apartment_simple(listing)
                            scores_calculated += 1
                            logging.debug(f"📊 Recalculated recent score:0 (age: {age_hours:.1f}h): {listing['score']:.1f}")
                        except Exception as e:
                            logging.warning(f"⚠️ Could not recalculate score: {e}")

        if scores_calculated > 0:
            logging.info(f"📊 Calculated scores for {scores_calculated} listings that were missing scores")

        if min_score > 0:
            listings = [l for l in listings if (l.get('score', 0) or 0) >= min_score]

        return sorted(listings, key=lambda x: (x.get('score', 0) or 0, x.get('processed_at', 0)), reverse=True)

    def _apply_top_listings_exclusion_filters(self, listings, limit) -> List[Dict]:
        """Drop rentals, price-on-request, and expensive-low-score listings; cap at limit."""
        filtered = []
        for listing in listings:
            title = (listing.get('title') or '').lower()
            description = (listing.get('description') or '').lower()
            special_features = listing.get('special_features', []) or []

            # Skip rentals (title/description, then special_features)
            if any(kw in title or kw in description for kw in RENTAL_KEYWORDS):
                continue
            if special_features and any(
                any(kw in str(f).lower() for kw in RENTAL_KEYWORDS) for f in special_features
            ):
                continue

            # Drop "Preis auf Anfrage" / missing prices
            price_total = listing.get('price_total')
            if not isinstance(price_total, (int, float)) or price_total <= 0:
                continue

            # Filter out "Preis auf Anfrage" (title/description, then special_features)
            if any(kw in title or kw in description for kw in PRICE_ON_REQUEST_KEYWORDS):
                continue
            if special_features and any(
                any(kw in str(f).lower() for kw in PRICE_ON_REQUEST_KEYWORDS) for f in special_features
            ):
                continue

            # Apply stricter scoring for expensive properties
            score = listing.get('score', 0) or 0
            if price_total > 400000 and score < 40:
                continue

            filtered.append(listing)
            if len(filtered) >= limit:
                break

        return filtered

    def _log_top_listings_summary(self, filtered, total_count, min_score, days_old,
                                   excluded_districts, min_rooms,
                                   exclude_recently_sent, recently_sent_days) -> None:
        """Log summary of top-listing search results."""
        if days_old >= 365:
            logging.info(f"📊 Found {len(filtered)} top listings (score >= {min_score}, all time)")
        else:
            logging.info(f"📊 Found {len(filtered)} top listings (score >= {min_score}, last {days_old} days)")
        if excluded_districts:
            logging.info(f"🚫 Excluded districts: {excluded_districts}")
        if min_rooms > 0:
            logging.info(f"🛏️ Minimum rooms: {min_rooms}")
        if exclude_recently_sent:
            logging.info(f"🚫 Excluded recently sent listings (last {recently_sent_days} days)")
        logging.info(f"🚫 Filtered out {total_count - len(filtered)} rental/expensive properties")

    @staticmethod
    def save_listings_to_mongodb(listings: list) -> int:
        """
        Save multiple listings to MongoDB
        Returns the number of successfully saved listings
        """
        try:
            handler = MongoDBHandler()
            saved_count = 0
            
            for listing in listings:
                # Convert Listing object to dict if needed
                if hasattr(listing, '__dict__'):
                    listing_dict = listing.__dict__
                else:
                    listing_dict = listing
                
                if handler.upsert_listing_with_history(listing_dict):
                    saved_count += 1
            
            handler.close()
            return saved_count
            
        except Exception as e:
            print(f"Error saving listings to MongoDB: {e}")
            return 0
    
    def increment_validation_failure(self, source: str):
        """Increment validation failure counter for a source."""
        try:
            self.metrics_collection.update_one(
                {"source": source},
                {"$inc": {"validation_failures": 1, "total_processed": 1}},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to increment metrics: {e}")

    def get_validation_metrics(self, source: str = None) -> Dict:
        """Get validation metrics for a source or all sources."""
        query = {"source": source} if source else {}
        metrics = list(self.metrics_collection.find(query))
        result = {}
        for m in metrics:
            total = m.get("total_processed", 0)
            failures = m.get("validation_failures", 0)
            rate = (failures / total * 100) if total > 0 else 0
            result[m["source"]] = {"total": total, "failures": failures, "rate": rate}
        return result

    def reset_validation_metrics(self, source: str = None):
        """Reset metrics for a source or all sources."""
        query = {"source": source} if source else {}
        self.metrics_collection.delete_many(query)

    def create_outreach_jobs(self, jobs: List[Dict]) -> int:
        """Create pending outreach jobs in MongoDB for tracking and retry."""
        if not jobs:
            return 0
        from datetime import datetime, timezone
        job_docs = []
        for job in jobs:
            job_docs.append({
                'recipient_email': job['contact_email'],
                'listing_url': job['listing_url'],
                'listing_title': job.get('title', ''),
                'status': 'pending',
                'attempts': 0,
                'created_at': datetime.now(timezone.utc),
                'last_attempt': None,
                'next_retry': None,
                'error_message': None
            })
        result = self.outreach_collection.insert_many(job_docs)
        return len(result.inserted_ids)

    def get_pending_outreach_jobs(self, limit: int = 10) -> List[Dict]:
        """Get jobs ready for sending (pending or retry-eligible)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return list(self.outreach_collection.find({
            '$or': [
                {'status': 'pending'},
                {'status': 'retry', 'next_retry': {'$lte': now}}
            ]
        }).limit(limit))

    def mark_outreach_job_sent(self, job_id, sent_at: datetime = None) -> None:
        from datetime import datetime, timezone
        self.outreach_collection.update_one(
            {'_id': job_id},
            {'$set': {
                'status': 'sent',
                'sent_at': sent_at or datetime.now(timezone.utc)
            }}
        )

    def mark_outreach_job_failed(self, job_id, error: str, retry_at: datetime = None) -> None:
        from datetime import datetime, timezone
        self.outreach_collection.update_one(
            {'_id': job_id},
            {'$inc': {'attempts': 1},
             '$set': {
                 'last_attempt': datetime.now(timezone.utc),
                 'error_message': error,
                 'next_retry': retry_at,
                 'status': 'retry' if retry_at else 'failed'
             }}
        )