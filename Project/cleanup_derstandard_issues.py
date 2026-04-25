#!/usr/bin/env python3
"""
Cleanup script for derStandard listing issues:
1. Remove derstandard listings with suspiciously low prices (likely "Preis auf Anfrage" parsed as Betriebskosten)
2. Remove duplicate listings by content fingerprint (same title+area+rooms+bezirk+source)
3. Add content_fingerprint field to all existing listings for future dedup
"""

import sys
import os
import time
import logging
import pymongo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config
from Application.helpers.listing_validator import compute_content_fingerprint

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

ANFRAGE_KEYWORDS = [
    'preis auf anfrage', 'auf anfrage', 'price on request', 'on request',
    'preis nach vereinbarung', 'price by arrangement', 'nach vereinbarung',
    'preis n.v.', 'price n.v.', 'n.v.', 'n/a', 'na', 'tba', 'to be announced',
    'preis wird bekanntgegeben', 'price to be announced', 'wird bekanntgegeben'
]


def cleanup_price_on_request(mongo: MongoDBHandler) -> int:
    """Find derstandard listings with suspiciously low prices and remove them."""
    logger.info("=" * 60)
    logger.info("STEP 1: Cleanup 'Preis auf Anfrage' listings")
    logger.info("=" * 60)

    deleted = 0
    try:
        suspicious = list(mongo.collection.find({
            "source_enum": {"$in": ["derstandard", "derStandard"]},
            "price_total": {"$lt": 10000}
        }))

        logger.info(f"Found {len(suspicious)} derstandard listings with price_total < €10,000")

        for listing in suspicious:
            url = listing.get('url', 'N/A')
            price = listing.get('price_total', 'N/A')
            title = listing.get('title', 'N/A')

            if price is not None and isinstance(price, (int, float)) and price < 10000:
                if price < 1000:
                    logger.info(f"🚫 DELETING obviously wrong price ({price}) for: {title}")
                    logger.info(f"   URL: {url}")
                    mongo.collection.delete_one({"_id": listing['_id']})
                    deleted += 1
                else:
                    logger.info(f"⚠️  Price €{price} seems low for: {title}")
                    logger.info(f"   URL: {url} — keeping for manual review (not deleting)")

    except Exception as e:
        logger.error(f"Error during price cleanup: {e}")

    logger.info(f"Deleted {deleted} price-on-request / bad-price listings")
    return deleted


def add_fingerprints_to_existing(mongo: MongoDBHandler) -> int:
    """Add content_fingerprint to all existing listings that don't have one."""
    logger.info("=" * 60)
    logger.info("STEP 2: Add content_fingerprint to existing listings")
    logger.info("=" * 60)

    updated = 0
    try:
        listings = list(mongo.collection.find({"content_fingerprint": {"$exists": False}}))
        logger.info(f"Found {len(listings)} listings without content_fingerprint")

        for listing in listings:
            fingerprint = compute_content_fingerprint(listing)
            mongo.collection.update_one(
                {"_id": listing['_id']},
                {"$set": {"content_fingerprint": fingerprint}}
            )
            updated += 1

        logger.info(f"Added fingerprints to {updated} listings")

    except Exception as e:
        logger.error(f"Error adding fingerprints: {e}")

    return updated


def cleanup_duplicates(mongo: MongoDBHandler) -> int:
    """Find and remove duplicate listings by content fingerprint."""
    logger.info("=" * 60)
    logger.info("STEP 3: Remove duplicate listings by content fingerprint")
    logger.info("=" * 60)

    deleted = 0
    try:
        pipeline = [
            {"$match": {"content_fingerprint": {"$exists": True}}},
            {"$group": {
                "_id": {
                    "content_fingerprint": "$content_fingerprint",
                    "source_enum": "$source_enum"
                },
                "ids": {"$push": {"$toString": "$_id"}},
                "count": {"$sum": 1},
                "earliest": {"$min": "$processed_at"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]

        duplicate_groups = list(mongo.collection.aggregate(pipeline))
        logger.info(f"Found {len(duplicate_groups)} groups with duplicate fingerprints")

        for group in duplicate_groups:
            fingerprint = group['_id']['content_fingerprint']
            source = group['_id']['source_enum']
            ids = group['ids']
            earliest = group['earliest']

            logger.info(f"Group: fingerprint={fingerprint[:8]}..., source={source}, count={group['count']}")

            listings_in_group = list(mongo.collection.find({
                "content_fingerprint": fingerprint,
                "source_enum": source
            }).sort("processed_at", 1))

            to_delete = listings_in_group[1:]

            for listing in to_delete:
                logger.info(f"   DELETING duplicate: {listing.get('title', 'N/A')} (URL: {listing.get('url', 'N/A')})")
                mongo.collection.delete_one({"_id": listing['_id']})
                deleted += 1

    except Exception as e:
        logger.error(f"Error during duplicate cleanup: {e}")

    logger.info(f"Deleted {deleted} duplicate listings")
    return deleted


MIGRATION_FLAG = "derstandard_cleanup_v1_run"
MIGRATION_COLLECTION = "migrations"


def is_migration_done(mongo: MongoDBHandler) -> bool:
    """Check if migration has already been run."""
    try:
        migrations_col = mongo.db[MIGRATION_COLLECTION]
        result = migrations_col.find_one({"_id": MIGRATION_FLAG})
        return result is not None
    except Exception:
        return False


def mark_migration_done(mongo: MongoDBHandler):
    """Mark migration as done so it won't run again."""
    try:
        migrations_col = mongo.db[MIGRATION_COLLECTION]
        migrations_col.insert_one({"_id": MIGRATION_FLAG, "run_at": time.time()})
    except pymongo.errors.DuplicateKeyError:
        pass
    except Exception as e:
        logger.warning(f"Could not mark migration as done: {e}")


def main():
    config = load_config()
    mongo_uri = os.getenv("MONGODB_URI") or config.get("mongodb_uri", "mongodb://localhost:27017/")

    logger.info(f"Connecting to MongoDB: {mongo_uri[:50]}...")
    mongo = MongoDBHandler(uri=mongo_uri)

    if mongo.collection is None:
        logger.error("Failed to connect to MongoDB. Exiting.")
        return

    logger.info("✅ Connected to MongoDB\n")

    if is_migration_done(mongo):
        logger.info("✅ Migration already run (found flag). Skipping.")
        logger.info("To re-run, delete the _migration_flag document first.")
        return

    deleted_pricing = cleanup_price_on_request(mongo)
    updated = add_fingerprints_to_existing(mongo)
    deleted_dupes = cleanup_duplicates(mongo)

    mark_migration_done(mongo)

    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Price-on-request listings deleted: {deleted_pricing}")
    logger.info(f"  Fingerprints added to existing:  {updated}")
    logger.info(f"  Duplicate listings deleted:      {deleted_dupes}")
    logger.info("=" * 60)
    logger.info("✅ Cleanup complete! Migration flag set.")


if __name__ == "__main__":
    main()
