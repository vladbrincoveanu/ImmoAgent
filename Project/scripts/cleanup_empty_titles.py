#!/usr/bin/env python3
"""
One-time cleanup for listings with empty/missing titles or suspiciously low price_per_m2.

Usage:
    python Project/scripts/cleanup_empty_titles.py          # dry-run (default)
    python Project/scripts/cleanup_empty_titles.py --confirm # real delete
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import argparse
import logging
import requests
import dataclasses
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Optional, Tuple

from Integration.mongodb_handler import MongoDBHandler
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

GARBAGE_PRICE_PER_M2 = 2500
WORKERS = 5
REQUEST_TIMEOUT = 10

CANDIDATE_QUERY = {
    "$or": [
        {"title": ""},
        {"title": None},
        {"title": {"$exists": False}},
        {"price_per_m2": {"$lt": GARBAGE_PRICE_PER_M2}},
    ]
}


def _http_ok(url: str) -> bool:
    try:
        r = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200
    except Exception:
        return False


def _get_scraper(source: str):
    if source == "willhaben":
        from Application.scraping.willhaben_scraper import WillhabenScraper
        return WillhabenScraper()
    if source == "immo_kurier":
        from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
        return ImmoKurierScraper()
    if source == "derstandard":
        from Application.scraping.derstandard_scraper import DerStandardScraper
        return DerStandardScraper()
    return None


def _is_good_listing(listing) -> bool:
    """True if listing has a non-empty title and price_per_m2 >= threshold."""
    title = getattr(listing, 'title', None) or (listing.get('title') if isinstance(listing, dict) else None)
    price_per_m2 = getattr(listing, 'price_per_m2', None) or (listing.get('price_per_m2') if isinstance(listing, dict) else None)
    if not title:
        return False
    if price_per_m2 is not None and price_per_m2 < GARBAGE_PRICE_PER_M2:
        return False
    return True


def process_candidate(doc: Dict, dry_run: bool, db: MongoDBHandler) -> Tuple[str, str]:
    """
    Returns (action, reason) where action is 'keep'|'update'|'delete'|'dry_delete'|'dry_update'.
    """
    url = doc.get("url", "")
    source = doc.get("source", "unknown")

    if not _http_ok(url):
        reason = "URL returned non-200"
        if not dry_run:
            db.collection.update_one({"_id": doc["_id"]}, {"$set": {"url_is_valid": False}})
            db.collection.delete_one({"_id": doc["_id"]})
        return ("dry_delete" if dry_run else "delete"), reason

    scraper = _get_scraper(source)
    if scraper is None:
        return "keep", f"no scraper for source={source}"

    try:
        refreshed = scraper.scrape_single_listing(url)
    except Exception as e:
        return "keep", f"re-scrape error: {e}"

    if refreshed is None:
        reason = "re-scrape returned None"
        if not dry_run:
            db.collection.delete_one({"_id": doc["_id"]})
        return ("dry_delete" if dry_run else "delete"), reason

    if _is_good_listing(refreshed):
        if not dry_run:
            update_data = dataclasses.asdict(refreshed) if dataclasses.is_dataclass(refreshed) else dict(refreshed)
            update_data.pop("_id", None)
            db.collection.update_one({"_id": doc["_id"]}, {"$set": update_data})
        return ("dry_update" if dry_run else "update"), "re-scrape recovered listing"

    reason = f"re-scrape still bad (title={getattr(refreshed, 'title', None)!r}, price_per_m2={getattr(refreshed, 'price_per_m2', None)})"
    if not dry_run:
        db.collection.delete_one({"_id": doc["_id"]})
    return ("dry_delete" if dry_run else "delete"), reason


def run(dry_run: bool):
    db = MongoDBHandler()
    if db.collection is None:
        logger.error("MongoDB not connected")
        sys.exit(1)

    candidates = list(db.collection.find(CANDIDATE_QUERY))
    logger.info(f"Found {len(candidates)} candidate listings")

    if not candidates:
        logger.info("Nothing to clean up.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'log')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"cleanup_empty_titles_{ts}.log")

    stats = {"keep": 0, "update": 0, "delete": 0, "dry_delete": 0, "dry_update": 0}

    with open(log_path, "w") as audit_log:
        audit_log.write(f"cleanup_empty_titles run={ts} dry_run={dry_run}\n\n")

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {
                pool.submit(process_candidate, doc, dry_run, db): doc
                for doc in candidates
            }
            for future in as_completed(futures):
                doc = futures[future]
                url = doc.get("url", "?")
                try:
                    action, reason = future.result()
                except Exception as e:
                    action, reason = "keep", f"unexpected error: {e}"

                stats[action] = stats.get(action, 0) + 1
                logger.info(f"[{action.upper()}] {url} — {reason}")
                if "delete" in action:
                    audit_log.write(f"{action}\t{url}\t{reason}\n")
                elif action == "update":
                    audit_log.write(f"update\t{url}\t{reason}\n")

    mode = "DRY RUN" if dry_run else "REAL"
    logger.info(f"\n=== {mode} complete ===")
    for k, v in stats.items():
        if v:
            logger.info(f"  {k}: {v}")
    logger.info(f"Audit log: {log_path}")
    if dry_run:
        logger.info("Re-run with --confirm to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Apply deletes/updates (default is dry-run)")
    args = parser.parse_args()
    run(dry_run=not args.confirm)
