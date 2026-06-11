#!/usr/bin/env python3
"""
Backfill bank score fields on legacy listings.

Old listings (pre-fix) have no `bank_score_confidence`, no
`estimated_down_pct`, no `belehnungswert_factor`, etc. This script
recomputes them via the same logic used at scrape time, so the
dashboard's EquityBadge can render real values instead of
'? equity' placeholders.

Usage:
  MONGODB_URI=mongodb://localhost:27017/immo python backfill_bank_score.py
  MONGODB_URI=mongodb+srv://... python backfill_bank_score.py
  python backfill_bank_score.py --dry-run     # preview only
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Application.bank_scoring import compute_bank_score
from Integration.mongodb_handler import MongoDBHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('backfill_bank_score')

REQUIRED_FIELDS = [
    'energy_class', 'year_built', 'facade_renovated', 'roof_renovated',
    'window_type', 'hwb_value', 'condition', 'title', 'price_total',
]


def as_listing(doc: Dict[str, Any]):
    kwargs = {k: doc.get(k) for k in REQUIRED_FIELDS}
    return SimpleNamespace(**kwargs)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true', help='Compute but do not write back')
    p.add_argument('--limit', type=int, default=0, help='Max listings to update (0=all)')
    p.add_argument('--only-missing', action='store_true', default=True, help='Only update listings without bank_score_confidence')
    args = p.parse_args()

    handler = MongoDBHandler()
    coll = handler.collection

    query: Dict[str, Any] = {}
    if args.only_missing:
        query = {'bank_score_confidence': {'$exists': False}}

    total = coll.count_documents(query)
    log.info(f'Found {total} listings to backfill (query={query})')

    cursor = coll.find(query, {f: 1 for f in (['_id'] + REQUIRED_FIELDS)})
    if args.limit:
        cursor = cursor.limit(args.limit)

    updated = 0
    failed = 0
    confidence_dist: Dict[str, int] = {'high': 0, 'medium': 0, 'low': 0}
    for doc in cursor:
        try:
            listing = as_listing(doc)
            score = compute_bank_score(listing)
            update = {
                'belehnungswert_factor': score.belehnungswert_factor,
                'estimated_down_pct': score.estimated_down_pct,
                'estimated_down_pct_kimv': score.estimated_down_pct_kimv,
                'estimated_equity_eur': score.estimated_equity_eur,
                'bank_score_confidence': score.bank_score_confidence,
            }
            if args.dry_run:
                log.info(f'[DRY] {doc["_id"]}: {update}')
            else:
                coll.update_one({'_id': doc['_id']}, {'$set': update})
            updated += 1
            confidence_dist[score.bank_score_confidence] += 1
        except Exception as e:
            log.warning(f'Failed {doc.get("_id")}: {e}')
            failed += 1

    log.info(f'Done. updated={updated} failed={failed} confidence={confidence_dist}')
    if args.dry_run:
        log.info('(dry-run — no changes written)')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
