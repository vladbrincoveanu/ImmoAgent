#!/usr/bin/env python3
"""One-shot CLI: compute per-profile scores for existing listings.

Usage:
  python -m Project.scripts.backfill_profile_scores [--batch 500] [--dry-run] [--profile urban_professional]
"""
import argparse
import logging
import sys

from Application.profile_scoring import score_all_profiles
from Integration.mongodb_handler import MongoDBHandler, PROFILE_NAMES

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def run_backfill(dry_run: bool = False, batch: int = 500, only_profile: str | None = None) -> dict:
    """Stream listings; compute scores; write $set updates. Idempotent.

    Returns a stats dict {processed, updated, skipped, errors}.
    """
    mongo = MongoDBHandler()
    if mongo.collection is None:
        logger.error("MongoDB not available; aborting backfill")
        return {'processed': 0, 'updated': 0, 'skipped': 0, 'errors': 1}

    processed = 0
    updated = 0
    skipped = 0
    errors = 0

    cursor = mongo.collection.find({}, {'_id': 1}).batch_size(batch)
    for doc in cursor:
        processed += 1
        full = mongo.collection.find_one({'_id': doc['_id']})
        if not full:
            skipped += 1
            continue
        existing_scores = full.get('scores') or {}
        if existing_scores and all(p in existing_scores for p in PROFILE_NAMES):
            skipped += 1
            continue
        try:
            new_scores = score_all_profiles(full)
            if only_profile:
                # Single-profile mode: keep existing scores, refresh only the target
                merged = dict(existing_scores)
                merged[only_profile] = new_scores.get(only_profile)
                new_scores = merged
            if dry_run:
                logger.info(f"[dry-run] would update _id={doc['_id']} scores={new_scores}")
            else:
                mongo.update_profile_scores(doc['_id'], new_scores)
            updated += 1
        except Exception as e:
            logger.error(f"backfill error on _id={doc['_id']}: {e}")
            errors += 1
        if processed % 500 == 0:
            logger.info(f"backfill progress: processed={processed} updated={updated} skipped={skipped} errors={errors}")

    return {'processed': processed, 'updated': updated, 'skipped': skipped, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description='Backfill per-profile scores')
    parser.add_argument('--batch', type=int, default=500)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--profile', type=str, default=None, help='Only backfill one profile (faster)')
    args = parser.parse_args()
    stats = run_backfill(dry_run=args.dry_run, batch=args.batch, only_profile=args.profile)
    logger.info(f"backfill complete: {stats}")
    sys.exit(0 if stats['errors'] == 0 else 1)


if __name__ == '__main__':
    main()
