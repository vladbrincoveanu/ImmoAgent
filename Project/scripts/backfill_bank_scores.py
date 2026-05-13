#!/usr/bin/env python3
"""Backfill Belehnungswert bank scoring fields for all existing MongoDB listings.

Idempotent: only processes listings where estimated_down_pct does not yet exist.
Run from the Project/ directory:
    python scripts/backfill_bank_scores.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Integration.mongodb_handler import MongoDBHandler
from Application.bank_scoring import compute_bank_score
from Application.helpers.utils import load_config
from Domain.listing import Listing


def main():
    config = load_config()
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    col = mongo.collection

    query = {'estimated_down_pct': {'$exists': False}}
    total = col.count_documents(query)
    print(f"Backfilling {total} listings (estimated_down_pct missing)")

    processed = updated = skipped = 0

    for doc in col.find(query):
        processed += 1
        listing = Listing(
            url=doc.get('url', ''),
            source=doc.get('source', 'unknown'),
            price_total=doc.get('price_total'),
            energy_class=doc.get('energy_class'),
            year_built=doc.get('year_built'),
            facade_renovated=doc.get('facade_renovated'),
            roof_renovated=doc.get('roof_renovated'),
            window_type=doc.get('window_type'),
        )

        bank = compute_bank_score(listing)

        if bank.estimated_down_pct is None:
            skipped += 1
            continue

        col.update_one(
            {'_id': doc['_id']},
            {'$set': {
                'belehnungswert_factor':   bank.belehnungswert_factor,
                'estimated_down_pct':      bank.estimated_down_pct,
                'estimated_down_pct_kimv': bank.estimated_down_pct_kimv,
                'estimated_equity_eur':    bank.estimated_equity_eur,
                'bank_score_confidence':   bank.bank_score_confidence,
            }}
        )
        updated += 1

        if processed % 100 == 0:
            print(f"  {processed}/{total} — {updated} updated, {skipped} skipped")

    print(f"\nDone: {processed} processed | {updated} updated | {skipped} skipped (no price_total)")
    mongo.close()


if __name__ == '__main__':
    main()
