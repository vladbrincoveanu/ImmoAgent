#!/usr/bin/env python3
"""
Cleanup invalid listings from MongoDB.

Usage:
    python scripts/cleanup_invalid_listings.py --dry-run
    python scripts/cleanup_invalid_listings.py
"""
import argparse
import logging
from pathlib import Path
import sys

# Add Project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Integration.mongodb_handler import MongoDBHandler
from Application.buyer_profiles import GLOBAL_VALIDATION

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_invalid_listings(dry_run: bool = True):
    config = GLOBAL_VALIDATION
    mongodb = MongoDBHandler()

    # Build cleanup filter for simple criteria
    cleanup_filter = {
        "$or": [
            {"price_total": {"$lt": config["min_price_total"]}},
            {"area_m2": {"$lt": config["min_area_m2"]}},
        ]
    }

    # First: count and delete by simple criteria
    if dry_run:
        count = mongodb.collection.count_documents(cleanup_filter)
        logger.info(f"[DRY RUN] Would delete {count} listings matching price/area criteria")
    else:
        result = mongodb.collection.delete_many(cleanup_filter)
        logger.info(f"Deleted {result.deleted_count} listings matching price/area criteria")

    # Second: handle per-m2 check using BATCH processing
    # Use cursor with batch_size to avoid loading all into memory
    query = {}  # Get all listings
    projection = {"price_total": 1, "area_m2": 1, "url": 1, "title": 1}

    per_m2_delete_ids = []
    batch_size = 100

    logger.info("Checking per-m2 criteria in batches...")
    cursor = mongodb.collection.find(query, projection).batch_size(batch_size)

    for listing in cursor:
        price = listing.get("price_total")
        area = listing.get("area_m2")
        if price is not None and area is not None and area > 0:
            per_m2 = price / area
            if per_m2 < config["min_price_per_m2"] or per_m2 > config["max_price_per_m2"]:
                per_m2_delete_ids.append(listing["_id"])

    logger.info(f"Found {len(per_m2_delete_ids)} listings failing per-m2 check")

    if per_m2_delete_ids:
        if dry_run:
            logger.info(f"[DRY RUN] Would delete {len(per_m2_delete_ids)} listings failing per-m2 check")
        else:
            # Delete in batches too
            for i in range(0, len(per_m2_delete_ids), batch_size):
                batch = per_m2_delete_ids[i:i+batch_size]
                result = mongodb.collection.delete_many({"_id": {"$in": batch}})
                logger.info(f"Deleted batch of {result.deleted_count} listings failing per-m2 check")

    mongodb.close()
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup invalid listings from MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Count deletions without actually deleting")
    args = parser.parse_args()

    cleanup_invalid_listings(dry_run=args.dry_run)