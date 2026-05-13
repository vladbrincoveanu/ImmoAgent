#!/usr/bin/env python3
"""
One-time cleanup for garbage listings in MongoDB.

Three deletion rules (applied independently):
  1. Empty/missing title
  2. Neubauprojekt aggregate URL (/d/neubauprojekt/ in URL)
  3. Stored price_per_m2 between 0 and 2500 (suspicious, non-null)

The regular scraper (with expand_project_to_units) will repopulate
correct unit listings on the next run.

Usage:
    python Project/scripts/cleanup_empty_titles.py          # dry-run
    python Project/scripts/cleanup_empty_titles.py --confirm # real delete
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import argparse
import logging
from datetime import datetime

from Integration.mongodb_handler import MongoDBHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

RULES = [
    (
        "empty_title",
        {"$or": [{"title": ""}, {"title": None}, {"title": {"$exists": False}}]},
    ),
    (
        "neubauprojekt_aggregate_url",
        {"url": {"$regex": "/d/neubauprojekt/"}},
    ),
    (
        "low_price_per_m2",
        {"price_per_m2": {"$gt": 0, "$lt": 2500}},
    ),
]


def run(dry_run: bool) -> None:
    db = MongoDBHandler()
    if db.collection is None:
        logger.error("MongoDB not connected")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'log')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"cleanup_empty_titles_{ts}.log")

    total_deleted = 0

    with open(log_path, "w") as audit:
        audit.write(f"cleanup_empty_titles ts={ts} dry_run={dry_run}\n\n")

        for rule_name, query in RULES:
            candidates = list(db.collection.find(query, {"_id": 1, "url": 1, "title": 1, "price_per_m2": 1}))
            logger.info(f"[{rule_name}] {len(candidates)} candidates")

            for doc in candidates:
                url = doc.get("url", "?")
                title = doc.get("title")
                ppm2 = doc.get("price_per_m2")
                detail = f"title={title!r} price_per_m2={ppm2}"
                logger.info(f"  {'[DRY]' if dry_run else '[DELETE]'} {url} — {detail}")
                audit.write(f"{rule_name}\t{'dry' if dry_run else 'delete'}\t{url}\t{detail}\n")

                if not dry_run:
                    db.collection.delete_one({"_id": doc["_id"]})
                    total_deleted += 1

        audit.write(f"\ntotal_deleted={total_deleted}\n")

    mode = "DRY RUN" if dry_run else "REAL"
    logger.info(f"\n=== {mode} complete — deleted {total_deleted} listings ===")
    logger.info(f"Audit log: {log_path}")
    if dry_run:
        logger.info("Re-run with --confirm to apply deletes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Apply deletes (default is dry-run)")
    args = parser.parse_args()
    run(dry_run=not args.confirm)
