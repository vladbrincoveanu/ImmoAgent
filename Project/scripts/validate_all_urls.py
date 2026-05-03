#!/usr/bin/env python3
"""
Validate all listing URLs and delete broken ones.

Usage:
    python scripts/validate_all_urls.py --dry-run --limit 10
    python scripts/validate_all_urls.py --dry-run
    python scripts/validate_all_urls.py
"""
import argparse
import logging
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import requests

# Add Project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Integration.mongodb_handler import MongoDBHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TIMEOUT = 10
MAX_WORKERS = 10
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def check_url(url: str) -> Tuple[str, bool]:
    """Returns (url, is_broken)."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True, headers=headers)
        if response.status_code >= 400:
            return (url, True)
        return (url, False)
    except requests.RequestException:
        return (url, True)

def validate_urls(limit: int = None, dry_run: bool = True):
    mongodb = MongoDBHandler()

    # Fetch listings with URLs
    query = {"url": {"$exists": True, "$ne": None}}
    if limit:
        listings = list(mongodb.collection.find(query, {"url": 1, "title": 1}).limit(limit))
    else:
        listings = list(mongodb.collection.find(query, {"url": 1, "title": 1}))

    urls_to_check = [(l["_id"], l["url"]) for l in listings if l.get("url")]

    broken_ids = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, url): (lid, url) for lid, url in urls_to_check}

        for future in as_completed(futures):
            lid, url = futures[future]
            try:
                checked_url, is_broken = future.result()
                if is_broken:
                    broken_ids.append(lid)
                    logger.info(f"🔴 Broken URL ({lid}): {url}")
            except Exception as e:
                logger.error(f"Error checking {url}: {e}")
                broken_ids.append(lid)

    # Delete broken listings
    if broken_ids:
        if dry_run:
            logger.info(f"[DRY RUN] Would delete {len(broken_ids)} listings with broken URLs")
        else:
            result = mongodb.collection.delete_many({"_id": {"$in": broken_ids}})
            logger.info(f"Deleted {result.deleted_count} listings with broken URLs")
    else:
        logger.info("No broken URLs found")

    mongodb.close()
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate all listing URLs")
    parser.add_argument("--dry-run", action="store_true", help="Count deletions without actually deleting")
    parser.add_argument("--limit", type=int, help="Limit number of URLs to check")
    args = parser.parse_args()

    validate_urls(limit=args.limit, dry_run=args.dry_run)