"""
Cleanup module for immo-scouter.
Contains all database cleanup and maintenance functions.
"""

import time
import logging
import requests
from typing import Dict
from Integration.mongodb_handler import MongoDBHandler, is_valid_listing_data
from Integration.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ImmoScouter/1.0; +https://github.com/vladbrincoveanu/immo-scouter)'
}


def deep_cleanup_database(mongo_handler: MongoDBHandler) -> Dict[str, int]:
    """One-time comprehensive cleanup: removes invalid data, broken URLs, very old listings, and recalculates scores."""
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0, "old_removed": 0, "scores_calculated": 0}

    logging.info("🧹 Running DEEP CLEANUP (comprehensive database cleanup)...")

    stats = {
        "invalid_data": 0,
        "broken_urls": 0,
        "old_removed": 0,
        "scores_calculated": 0
    }

    invalid_query = {
        "$or": [
            {"url": {"$exists": False}},
            {"url": None},
            {"url": ""},
        ]
    }
    invalid_result = mongo_handler.collection.delete_many(invalid_query)
    stats["invalid_data"] = invalid_result.deleted_count
    if stats["invalid_data"] > 0:
        logging.info(f"   ✅ Removed {stats['invalid_data']} listings with invalid data")

    invalid_price_per_m2 = 0
    all_listings = list(mongo_handler.collection.find(
        {"url": {"$exists": True, "$ne": None, "$ne": ""}},
        {"price_total": 1, "area_m2": 1, "_id": 1}
    ).limit(1000))
    from datetime import datetime
    for listing in all_listings:
        is_valid, _ = is_valid_listing_data(listing)
        if not is_valid:
            try:
                mongo_handler.collection.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"url_is_valid": False, "invalidated_at": datetime.utcnow()}}
                )
                invalid_price_per_m2 += 1
            except Exception as e:
                logging.debug(f"   ⚠️ Failed to update listing {listing.get('_id')}: {e}")
    if invalid_price_per_m2 > 0:
        logging.info(f"   ✅ Marked {invalid_price_per_m2} listings with invalid price_per_m2 as invalid")
        stats["invalid_data"] += invalid_price_per_m2

    derstandard_listings = list(mongo_handler.collection.find(
        {"source": "derstandard"},
        {"url": 1, "_id": 1}
    ).limit(500))

    if derstandard_listings:
        logging.info(f"   🔍 Checking {len(derstandard_listings)} derstandard URLs for broken links...")
        broken_count = 0
        for listing in derstandard_listings:
            url = listing.get("url")
            if not url:
                continue

            try:
                resp = requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=3)
                if resp.status_code >= 400:
                    mongo_handler.collection.delete_one({"_id": listing["_id"]})
                    broken_count += 1
            except Exception:
                mongo_handler.collection.delete_one({"_id": listing["_id"]})
                broken_count += 1

        stats["broken_urls"] = broken_count
        if broken_count > 0:
            logging.info(f"   ✅ Removed {broken_count} broken derstandard URLs")

    cutoff_ts = time.time() - (365 * 86400)
    old_result = mongo_handler.collection.delete_many({"processed_at": {"$lt": cutoff_ts}})
    stats["old_removed"] = old_result.deleted_count
    if stats["old_removed"] > 0:
        logging.info(f"   ✅ Removed {stats['old_removed']} listings older than 365 days")

    missing_scores_query = {
        "$or": [
            {"score": {"$exists": False}},
            {"score": None}
        ]
    }
    listings_without_scores = list(mongo_handler.collection.find(missing_scores_query))

    if listings_without_scores:
        from Application.scoring import score_apartment_simple
        from collections import Counter
        source_counts = Counter(l.get('source', 'unknown') for l in listings_without_scores)
        logging.info(f"   🔍 Recalculating scores for {len(listings_without_scores)} listings without scores")
        logging.info(f"      By source: {dict(source_counts)}")

        success_count = 0
        for listing in listings_without_scores:
            try:
                score = score_apartment_simple(listing)
                mongo_handler.collection.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"score": score}}
                )
                success_count += 1
            except Exception as e:
                logging.debug(f"      ⚠️ Failed to calculate score: {e}")

        stats["scores_calculated"] = success_count
        if success_count > 0:
            logging.info(f"   ✅ Calculated {success_count} missing scores")

    total_removed = stats["invalid_data"] + stats["broken_urls"] + stats["old_removed"]
    logging.info(f"🧹 Deep cleanup complete: removed {total_removed} listings, calculated {stats['scores_calculated']} scores")

    return {
        "checked": len(derstandard_listings) + len(listings_without_scores),
        "removed": total_removed,
        "invalid_data": stats["invalid_data"],
        "broken_urls": stats["broken_urls"],
        "old_removed": stats["old_removed"],
        "scores_calculated": stats["scores_calculated"]
    }


def comprehensive_cleanup_all_listings(mongo_handler: MongoDBHandler, max_age_days: int = 180, verify_urls: bool = True, batch_size: int = 100) -> Dict[str, int]:
    """
    Comprehensive cleanup that checks ALL listings for broken URLs and invalid data.
    This is more thorough than regular cleanup and should be run periodically.

    Args:
        mongo_handler: MongoDB handler instance
        max_age_days: Remove listings older than this (default: 180 days)
        verify_urls: Actually check if URLs are accessible (slower but thorough)
        batch_size: Process listings in batches to avoid memory issues

    Returns:
        Dictionary with cleanup statistics
    """
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0, "old_removed": 0}

    logging.info("🧹 Running COMPREHENSIVE cleanup (checking ALL listings for broken URLs)...")

    stats = {
        "checked": 0,
        "removed": 0,
        "invalid_data": 0,
        "broken_urls": 0,
        "old_removed": 0
    }

    invalid_query = {
        "$or": [
            {"url": {"$exists": False}},
            {"url": None},
            {"url": ""},
        ]
    }
    invalid_result = mongo_handler.collection.delete_many(invalid_query)
    stats["invalid_data"] = invalid_result.deleted_count
    if stats["invalid_data"] > 0:
        logging.info(f"   ✅ Removed {stats['invalid_data']} listings with invalid data")

    invalid_price_per_m2 = 0
    all_listings = list(mongo_handler.collection.find(
        {"url": {"$exists": True, "$ne": None, "$ne": ""}},
        {"price_total": 1, "area_m2": 1, "_id": 1}
    ).limit(1000))
    for listing in all_listings:
        is_valid, _ = is_valid_listing_data(listing)
        if not is_valid:
            try:
                mongo_handler.collection.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"url_is_valid": False, "invalidated_at": datetime.utcnow()}}
                )
                invalid_price_per_m2 += 1
            except Exception as e:
                logging.debug(f"   ⚠️ Failed to update listing {listing.get('_id')}: {e}")
    if invalid_price_per_m2 > 0:
        logging.info(f"   ✅ Marked {invalid_price_per_m2} listings with invalid price_per_m2 as invalid")
        stats["invalid_data"] += invalid_price_per_m2

    cutoff_ts = time.time() - (max_age_days * 86400)
    old_result = mongo_handler.collection.delete_many({"processed_at": {"$lt": cutoff_ts}})
    stats["old_removed"] = old_result.deleted_count
    if stats["old_removed"] > 0:
        logging.info(f"   ✅ Removed {stats['old_removed']} listings older than {max_age_days} days")

    if verify_urls:
        all_listings = list(mongo_handler.collection.find(
            {
                "$and": [
                    {"url": {"$exists": True}},
                    {"url": {"$ne": None}},
                    {"url": {"$ne": ""}}
                ]
            },
            {"url": 1, "_id": 1, "source": 1}
        ))

        total_listings = len(all_listings)
        if total_listings > 0:
            logging.info(f"   🔍 Checking {total_listings} listings for broken URLs...")

            broken_count = 0
            checked = 0

            for i in range(0, total_listings, batch_size):
                batch = all_listings[i:i + batch_size]
                for listing in batch:
                    url = listing.get("url")
                    if not url:
                        continue

                    checked += 1
                    url_invalid = False

                    try:
                        resp = requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=8)
                        if resp.status_code == 404 or resp.status_code == 410:
                            url_invalid = True
                            logging.debug(f"💀 Broken URL (HTTP {resp.status_code}): {url}")
                        elif resp.status_code >= 400:
                            logging.debug(f"⚠️ URL returned {resp.status_code} (not deleting): {url}")
                    except requests.exceptions.RequestException as e:
                        logging.debug(f"⚠️ URL check failed (network error, not deleting): {url} — {e}")

                    if url_invalid:
                        try:
                            mongo_handler.collection.update_one(
                                {"_id": listing["_id"]},
                                {"$set": {"url_is_valid": False, "invalidated_at": datetime.utcnow()}}
                            )
                            broken_count += 1
                        except Exception as exc:
                            logging.warning(f"⚠️ Failed to update listing {listing.get('_id')}: {exc}")

                if total_listings > batch_size:
                    progress = min(100, int((checked / total_listings) * 100))
                    logging.info(f"   🔍 Progress: {checked}/{total_listings} checked ({progress}%)...")

            stats["broken_urls"] = broken_count
            stats["checked"] = checked
            if broken_count > 0:
                logging.info(f"   ✅ Removed {broken_count} listings with broken URLs")
            else:
                logging.info(f"   ✅ All {checked} URLs are valid")

    stats["removed"] = stats["invalid_data"] + stats["broken_urls"] + stats["old_removed"]

    if stats["removed"] > 0:
        logging.info(f"🧹 Comprehensive cleanup complete: checked {stats['checked']} URLs, removed {stats['removed']} listings (invalid: {stats['invalid_data']}, broken URLs: {stats['broken_urls']}, old: {stats['old_removed']})")
    else:
        logging.info(f"🧹 Comprehensive cleanup complete: checked {stats['checked']} URLs, no listings removed")

    return stats


def clean_stale_or_broken_listings(mongo_handler: MongoDBHandler, max_age_days: int = 180, batch_limit: int = None, verify_urls: bool = True, aggressive: bool = False) -> Dict[str, int]:
    """Prune obviously broken/stale listings to avoid serving dead links.

    Args:
        mongo_handler: MongoDB handler instance
        max_age_days: Remove listings older than this (default: 180 days)
        batch_limit: Limit number of listings to check (None = check all)
        verify_urls: Actually check if URLs are accessible (slower but thorough)
        aggressive: If True, check ALL listings regardless of age, focusing on derstandard URLs
    """
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0}

    if aggressive:
        query = {"source": "derstandard"}
        logging.info("🧹 Running AGGRESSIVE cleanup on derstandard listings...")
    else:
        cutoff_ts = time.time() - (max_age_days * 86400)
        query = {"processed_at": {"$lt": cutoff_ts}}
        logging.info(f"🧹 Running cleanup on listings older than {max_age_days} days...")

    cursor = mongo_handler.collection.find(query, {"url": 1, "price_total": 1, "area_m2": 1, "source": 1})
    if batch_limit:
        cursor = cursor.limit(batch_limit)

    candidates = list(cursor)
    removed = 0
    invalid_data = 0
    broken_urls = 0

    for doc in candidates:
        doc_id = doc.get("_id")
        url = doc.get("url")
        price_total = doc.get("price_total")
        area_m2 = doc.get("area_m2")
        source = doc.get("source")

        if not doc_id:
            continue

        data_invalid = (not url) or (not isinstance(price_total, (int, float)) or price_total <= 0) or (not isinstance(area_m2, (int, float)) or area_m2 <= 0)

        url_invalid = False
        if verify_urls and url:
            try:
                resp = requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=3)
                url_invalid = resp.status_code >= 400
                if url_invalid:
                    logging.debug(f"💀 Broken URL (HTTP {resp.status_code}): {url}")
            except Exception as e:
                url_invalid = True
                logging.debug(f"💀 Unreachable URL ({type(e).__name__}): {url}")

        if data_invalid or url_invalid:
            try:
                mongo_handler.collection.delete_one({"_id": doc_id})
                removed += 1
                if data_invalid:
                    invalid_data += 1
                if url_invalid:
                    broken_urls += 1
            except Exception as exc:
                logging.warning(f"⚠️ Failed to delete listing {doc_id}: {exc}")

    if candidates:
        logging.info(f"🧹 Cleanup complete: checked {len(candidates)} listings, removed {removed} (invalid data: {invalid_data}, broken URLs: {broken_urls})")
    else:
        logging.info("🧹 No listings found matching cleanup criteria")

    return {"checked": len(candidates), "removed": removed, "invalid_data": invalid_data, "broken_urls": broken_urls}


def check_and_alert_rejection_rate(mongodb: MongoDBHandler, telegram_bot, threshold: float = 10.0):
    """Check rejection rate and send Telegram alert if above threshold."""
    metrics = mongodb.get_validation_metrics()
    for source, data in metrics.items():
        if data["rate"] > threshold:
            message = f"⚠️ High validation rejection rate for {source}: {data['rate']:.1f}% ({data['failures']}/{data['total']} failed)"
            if telegram_bot:
                telegram_bot.send_message(message)
            logging.warning(message)
    mongodb.reset_validation_metrics()


SOFT_404_PATTERNS = [
    'verkauft', 'vergeben', 'inaktiv', 'nicht mehr verfügbar',
    'reserviert', 'abgelaufen',
    'nicht gefunden', 'seite nicht', '404',
    'anzeige wurde entfernt', 'objekt nicht mehr', 'ist nicht mehr aktiv',
    'listing not found', 'page not found',
]

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ImmoScouter/1.0; +https://github.com/vladbrincoveanu/immo-scouter)'
}

def mark_taken_listings(
    mongo_handler,
    source_filter: list = None,
    timeout: int = 5
) -> Dict[str, int]:
    """Lightweight post-scrape revalidation: check active listings for a source.

    Uses HEAD request first. For derstandard, if HEAD returns 200, does body scan.
    Marks 404/410 as taken. Skips already-taken listings.
    Returns dict with checked, newly_taken, already_taken counts.
    """
    stats = {"checked": 0, "newly_taken": 0, "already_taken": 0}

    query = {"listing_status": {"$ne": "taken"}}
    if source_filter:
        query["source_enum"] = {"$in": source_filter}

    cursor = mongo_handler.collection.find(query, {"url": 1, "source_enum": 1, "_id": 1})
    listings = list(cursor)

    for doc in listings:
        url = doc.get('url')
        source = doc.get('source_enum')
        if not url:
            continue

        stats["checked"] += 1
        url_invalid = False

        try:
            resp = requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout)
            if resp.status_code in (404, 410):
                url_invalid = True
            elif resp.status_code == 200 and source == 'derstandard':
                try:
                    get_resp = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout, stream=True)
                    chunk = b''
                    for c in get_resp.iter_content(8192):
                        chunk += c
                        if len(chunk) > 51200:
                            break
                    body = chunk.decode('utf-8', errors='ignore').lower()
                    if any(p in body for p in SOFT_404_PATTERNS):
                        url_invalid = True
                except Exception:
                    pass
        except requests.exceptions.RequestException:
            url_invalid = True

        if url_invalid:
            was_updated = mongo_handler.mark_listing_taken(url)
            if was_updated:
                stats["newly_taken"] += 1
            else:
                stats["already_taken"] += 1

    logging.info(f"🔍 mark_taken_listings: checked={stats['checked']}, newly_taken={stats['newly_taken']}, already_taken={stats['already_taken']}")
    return stats


def daily_revalidation(
    mongo_handler,
    batch_size: int = 50,
    timeout: int = 8
) -> Dict[str, int]:
    """Thorough daily revalidation of ALL active listings.

    Batch processing to avoid rate limiting.
    Logs progress every 10%.
    Returns stats dict.
    """
    stats = {"checked": 0, "newly_taken": 0, "already_taken": 0, "batches": 0}

    query = {"listing_status": {"$ne": "taken"}}
    cursor = mongo_handler.collection.find(query, {"url": 1, "source_enum": 1, "_id": 1})
    listings = list(cursor)
    total = len(listings)

    if total == 0:
        logging.info("✅ daily_revalidation: no active listings to check")
        return stats

    logging.info(f"🔍 daily_revalidation: checking {total} active listings...")

    for i in range(0, total, batch_size):
        batch_stats = mark_taken_listings(mongo_handler, source_filter=None, timeout=timeout)
        stats['checked'] += batch_stats['checked']
        stats['newly_taken'] += batch_stats['newly_taken']
        stats['already_taken'] += batch_stats['already_taken']
        stats['batches'] += 1

        time.sleep(0.5)

        if total > batch_size:
            progress = min(100, int(((i + batch_size) / total) * 100))
            if progress % 10 == 0 or progress == 100:
                logging.info(f"   📊 Progress: {i + batch_size}/{total} ({progress}%)")

    logging.info(f"✅ daily_revalidation complete: checked={stats['checked']}, newly_taken={stats['newly_taken']}, batches={stats['batches']}")
    return stats
