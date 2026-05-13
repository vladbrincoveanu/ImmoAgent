#!/usr/bin/env python3
"""
Cleanup migration script: remove listings with empty titles or sub-threshold price/m².
Also re-scrapes candidates to recover from transient failures.

Usage:
    python scripts/cleanup_empty_titles.py       # dry-run (print count only)
    python scripts/cleanup_empty_titles.py --confirm  # actual delete
"""
import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Integration.mongodb_handler import MongoDBHandler
from Application.scraping.willhaben_scraper import WillhabenScraper
from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

CLEANUP_QUERY = {
    '$or': [
        { 'title': '' },
        { 'title': None },
        { 'title': { '$exists': False } },
        { 'price_per_m2': { '$lt': 2500 } },
        { 'url': { '$regex': '/neubauprojekt/' } },
    ]
}


def rescrape_listing(url: str, source_enum: str) -> Optional[Dict]:
    """Try to re-scrape a listing using source-specific scraper. Returns listing dict or None."""
    config = load_config()
    scrapers = {
        'willhaben': WillhabenScraper(config),
        'immo_kurier': ImmoKurierScraper(config),
        'derstandard': DerStandardScraper(config),
    }
    scraper = scrapers.get(source_enum, scrapers.get('willhaben'))
    if not scraper:
        return None
    try:
        listing = scraper.scrape_single_listing(url)
        if listing and listing.title and listing.price_per_m2 and listing.price_per_m2 >= 2500:
            return listing.__dict__
        return None
    except Exception as e:
        logger.debug(f"Re-scrape failed for {url}: {e}")
        return None


def process_listing(listing: Dict, dry_run: bool, scrapers: dict) -> Optional[str]:
    """Process one listing. Returns reason string if deleted, None if kept."""
    url = listing.get('url', '')
    title = listing.get('title', '')
    price_per_m2 = listing.get('price_per_m2')
    source_enum = listing.get('source_enum', 'willhaben')

    # Try re-scrape if source_enum is known
    if source_enum in scrapers and url:
        scraped = rescrape_listing(url, source_enum)
        if scraped:
            logger.info(f"✅ Re-scraped successfully, updating: {url}")
            return None  # Keep

    # Delete reasons
    if not title or title in ('', None):
        return "empty title"
    if price_per_m2 is not None and price_per_m2 < 2500:
        return f"price_per_m2 {price_per_m2:.0f} < 2500"
    if '/neubauprojekt/' in url:
        return "neubauprojekt aggregate page"
    return None


def main():
    parser = argparse.ArgumentParser(description='Cleanup listings with empty titles or bad price data')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default is dry-run)')
    parser.add_argument('--workers', type=int, default=5, help='Parallel workers (default 5)')
    args = parser.parse_args()

    config = load_config()
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))

    if mongo.collection is None:
        logger.error("MongoDB not available")
        return

    logger.info(f"Finding cleanup candidates...")
    candidates = list(mongo.collection.find(CLEANUP_QUERY))
    logger.info(f"Found {len(candidates)} candidates")

    if not candidates:
        logger.info("Nothing to clean up")
        return

    dry_run = not args.confirm
    if dry_run:
        logger.info(f"[DRY RUN] Would process {len(candidates)} listings")

    # Init scrapers for re-scrape
    scrapers = {}
    for name, cls in [('willhaben', WillhabenScraper), ('immo_kurier', ImmoKurierScraper), ('derstandard', DerStandardScraper)]:
        try:
            scrapers[name] = cls(config)
        except Exception as e:
            logger.debug(f"Could not init {name} scraper: {e}")

    to_delete: List[str] = []
    audit_entries: List[str] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one := lambda c: process_listing(c, dry_run, scrapers), c): c for c in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result:
                url, reason = result
                to_delete.append(url)
                audit_entries.append(f"{url} — {reason}")

    # Audit log
    if audit_entries:
        ts = time.strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(os.path.dirname(__file__), '..', 'log', f'cleanup_empty_titles_{ts}.log')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'w') as f:
            f.write('\n'.join(audit_entries))
        logger.info(f"Audit log: {log_path}")

    if not args.confirm:
        logger.info(f"[DRY RUN] Would delete {len(to_delete)} listings")
        return

    if to_delete:
        result = mongo.collection.delete_many({'url': {'$in': to_delete}})
        logger.info(f"Deleted {result.deleted_count}/{len(to_delete)} listings")

if __name__ == '__main__':
    main()