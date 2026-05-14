#!/usr/bin/env python3
"""Backfill Belehnungswert bank scoring fields for all existing MongoDB listings.

Idempotent: only processes listings where belehnungswert_factor does not yet exist.
Run from the Project/ directory:
    python scripts/backfill_bank_scores.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from types import SimpleNamespace
from pymongo import UpdateOne

from Integration.mongodb_handler import MongoDBHandler
from Application.bank_scoring import compute_bank_score
from Application.helpers.utils import load_config

BATCH_SIZE = 500


def main():
    config = load_config()
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    col = mongo.collection

    # Use belehnungswert_factor as idempotency key — written for ALL docs (even price-less).
    # estimated_down_pct alone would re-process price-less docs forever.
    query = {'belehnungswert_factor': {'$exists': False}}
    total = col.count_documents(query)
    print(f"Backfilling {total} listings (belehnungswert_factor missing)")

    processed = updated = skipped = 0
    ops = []

    try:
        cursor = col.find(query, no_cursor_timeout=True).batch_size(BATCH_SIZE)
        for doc in cursor:
            processed += 1

            listing = SimpleNamespace(
                price_total=doc.get('price_total'),
                energy_class=doc.get('energy_class'),
                year_built=doc.get('year_built'),
                facade_renovated=doc.get('facade_renovated'),
                roof_renovated=doc.get('roof_renovated'),
                window_type=doc.get('window_type'),
                hwb_value=doc.get('hwb_value'),
                condition=doc.get('condition'),
                title=doc.get('title'),
            )

            bank = compute_bank_score(listing)

            if bank.estimated_down_pct is None:
                skipped += 1

            ops.append(UpdateOne(
                {'_id': doc['_id']},
                {'$set': {
                    'belehnungswert_factor':   bank.belehnungswert_factor,
                    'estimated_down_pct':      bank.estimated_down_pct,
                    'estimated_down_pct_kimv': bank.estimated_down_pct_kimv,
                    'estimated_equity_eur':    bank.estimated_equity_eur,
                    'bank_score_confidence':   bank.bank_score_confidence,
                }}
            ))

            if len(ops) >= BATCH_SIZE:
                col.bulk_write(ops)
                updated += len(ops)
                ops = []
                print(f"  {processed}/{total} — {updated} written")

        if ops:
            col.bulk_write(ops)
            updated += len(ops)

    finally:
        mongo.close()

    print(f"\nDone: {processed} processed | {updated} written | {skipped} skipped (no price_total)")


if __name__ == '__main__':
    main()
