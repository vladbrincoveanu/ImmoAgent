"""Backfill per-profile scores on the PROD Atlas DB (the one the Vercel
dashboard reads). Reads MONGODB_URI from dashboard/.env.local; never prints it.

Usage: PYTHONPATH=. python3 ../scratchpad/backfill_atlas_scores.py [--dry-run]
(run from Project/)
"""
import argparse
import os
import re
import sys

from bson import ObjectId
from Application.profile_scoring import score_all_profiles
from Integration.mongodb_handler import MongoDBHandler, PROFILE_NAMES

ENV_PATH = os.environ.get('ENV_FILE') or os.path.join(os.path.dirname(__file__), '..', 'dashboard', '.env.local')
PROBE_ID = '6a4810ac78671f130338ead2'  # listing id served by prod /api/listings/top


def read_uri() -> str | None:
    try:
        with open(ENV_PATH) as f:
            for line in f:
                m = re.match(r'\s*MONGODB_URI\s*=\s*"?([^"\n]+)"?\s*$', line)
                if m:
                    return m.group(1)
    except OSError as e:
        print('cannot read .env.local:', e)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    uri = read_uri()
    if not uri:
        print('NO MONGODB_URI in dashboard/.env.local')
        sys.exit(2)
    host = re.sub(r'^mongodb(\+srv)?://[^@]*@', '', uri).split('/')[0]
    print('target host:', host)

    m = MongoDBHandler(uri=uri)
    coll = m.collection
    total = coll.count_documents({})
    probe = coll.find_one({'_id': ObjectId(PROBE_ID)}, {'_id': 1})
    print('db:', coll.database.name, '| docs:', total, '| prod probe doc present:', bool(probe))
    if not probe:
        print('ABORT: this is not the DB prod serves.')
        sys.exit(3)

    processed = updated = skipped = errors = 0
    for doc in coll.find({}, {'_id': 1}).batch_size(200):
        processed += 1
        full = coll.find_one({'_id': doc['_id']})
        if not full:
            skipped += 1
            continue
        existing = full.get('scores') or {}
        if existing and all(p in existing for p in PROFILE_NAMES):
            skipped += 1
            continue
        try:
            new_scores = score_all_profiles(full)
            if not args.dry_run:
                m.update_profile_scores(doc['_id'], new_scores)
            updated += 1
        except Exception as e:
            print('error on', doc['_id'], ':', e)
            errors += 1
    print(f'done dry_run={args.dry_run} processed={processed} updated={updated} skipped={skipped} errors={errors}')
    sys.exit(0 if errors == 0 else 1)


if __name__ == '__main__':
    main()
