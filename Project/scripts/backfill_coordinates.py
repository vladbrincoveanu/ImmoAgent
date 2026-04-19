#!/usr/bin/env python3
"""
Backfill coordinate_source and coordinates for existing listings in MongoDB.
Run once: python Project/scripts/backfill_coordinates.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Application.helpers import geocode_listing
from Integration.mongodb_handler import MongoDBHandler
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def backfill():
    db = MongoDBHandler()
    if db.collection is None:
        logger.error("MongoDB not connected")
        return

    cursor = db.collection.find({
        "coordinate_source": {"$exists": False}
    })

    total = 0
    updated = 0
    for listing in cursor:
        total += 1
        geocoded = geocode_listing(dict(listing))
        if geocoded.get('coordinate_source') != 'none':
            db.update_listing_coordinates(listing['url'], geocoded)
            updated += 1
        else:
            db.collection.update_one(
                {"_id": listing["_id"]},
                {"$set": {"coordinate_source": "none"}}
            )
            updated += 1

        if total % 50 == 0:
            logger.info(f"Processed {total} listings...")

    logger.info(f"Done. Processed {total} listings, updated {updated}.")

if __name__ == '__main__':
    backfill()