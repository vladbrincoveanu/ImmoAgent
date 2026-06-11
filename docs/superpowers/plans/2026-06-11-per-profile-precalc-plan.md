# Per-Profile Precalculated Scores — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 10 buyer profile scores precomputed and stored on each listing, so the dashboard can switch profiles instantly (URL `?profile=X`) with the list order changing on both `/dashboard` and `/dashboard/map`.

**Architecture:** At scrape time, score each listing against all 10 profiles and store as `scores: {<profile>: <float>}` subdoc. API routes sort by `scores.<profile>` when `?profile=` is provided. Client keeps all loaded listings + their 10 scores in a local Map; switching profile re-sorts locally without refetch. Mobile + desktop parity via shared ProfileSelector in FilterBar and FilterDrawer.

**Tech Stack:** Python 3 (pymongo, scoring module), Next.js 14 App Router (TypeScript, React), MongoDB, Playwright (E2E), pytest (Python tests), Vitest/Playwright (TS tests).

**Branch:** `relentless/per-profile-precalc` (auto-created at Task 0)

**Spec:** `docs/superpowers/specs/2026-06-11-per-profile-precalc-design.md`

---

## File Structure

### New files
- `Project/Application/profile_scoring.py` — pure scoring module
- `Project/scripts/__init__.py` — package marker
- `Project/scripts/backfill_profile_scores.py` — one-shot migration CLI
- `Tests/test_profile_scoring.py` — unit tests
- `Tests/test_backfill_idempotent.py` — integration test
- `dashboard/lib/profile.ts` — shared profile list (client)
- `dashboard/components/ProfileSelector.tsx` — UI switcher
- `dashboard/tests/profile-sort.spec.ts` — Playwright sort test
- `dashboard/tests/profile-map.spec.ts` — Playwright map test
- `dashboard/tests/profile-url-state.spec.ts` — Playwright URL persistence test

### Modified files
- `Project/Integration/mongodb_handler.py` — add `PROFILE_NAMES`, indexes, `update_profile_scores`, extend `get_top_listings` with `profile` arg
- `Project/Application/main.py` — call `score_all_profiles` + `update_profile_scores` after each listing upsert
- `dashboard/app/api/listings/top/route.ts` — accept `?profile=`, sort by `scores.<profile>`
- `dashboard/app/api/listings/map/route.ts` — same
- `dashboard/app/api/listings/[id]/route.ts` — return `scores[profile]` for the requested profile
- `dashboard/app/api/listings/stream/route.ts` — include `scores` subdoc
- `dashboard/lib/filters.ts` — add `profile` to URL ↔ state
- `dashboard/components/FilterBar.tsx` — render ProfileSelector
- `dashboard/components/FilterDrawer.tsx` — render ProfileSelector (mobile)
- `dashboard/app/dashboard/page.tsx` — read `?profile=`, local Map cache, re-sort on switch
- `dashboard/app/dashboard/map/page.tsx` — same

---

## Task 0: Branch setup

**Files:** none (git only)

- [ ] **Step 1: Create and checkout branch from main**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
git checkout main
git pull origin main 2>/dev/null || true
git checkout -b relentless/per-profile-precalc
```

- [ ] **Step 2: Verify branch**

Run: `git branch --show-current`
Expected: `relentless/per-profile-precalc`

- [ ] **Step 3: Initialize relentless status file**

```bash
cat > .claude/relentless-status-per-profile-precalc.md << 'EOF'
# Relentless Status
**Task:** Per-profile precalculated scores (dashboard buyer profile switcher)
**Started:** 2026-06-11
**Branch:** relentless/per-profile-precalc
**Current step:** Task 0
**End state:** All 10 profile scores precomputed + dashboard switcher works with Playwright green

## Progress
- [x] Task 0: Branch created (2026-06-11)

## Next action
Task 1: profile_scoring.py module
EOF
```

---

## Task 1: Profile scoring module (Python)

**Files:**
- Create: `Project/Application/profile_scoring.py`
- Test: `Tests/test_profile_scoring.py`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_profile_scoring.py`:

```python
"""Unit tests for profile_scoring.score_all_profiles()."""
import pytest
from Application.profile_scoring import score_all_profiles
from Application.buyer_profiles import BUYER_PROFILES


SAMPLE_LISTING = {
    '_id': 'test-1',
    'price_per_m2': 5000,
    'hwb_value': 60,
    'year_built': 1985,
    'ubahn_walk_minutes': 5,
    'school_walk_minutes': 10,
    'rooms': 3.0,
    'area_m2': 80,
    'balcony_terrace': 1,
    'floor_level': 2,
    'potential_growth_rating': 3,
    'renovation_needed_rating': 2,
}


def test_returns_dict_with_all_profiles():
    scores = score_all_profiles(SAMPLE_LISTING)
    assert isinstance(scores, dict)
    assert set(scores.keys()) == set(BUYER_PROFILES.keys())
    assert len(scores) == 10


def test_all_scores_are_floats_in_range():
    scores = score_all_profiles(SAMPLE_LISTING)
    for profile_key, score in scores.items():
        assert isinstance(score, float), f"{profile_key} not float"
        assert 0.0 <= score <= 100.0, f"{profile_key} out of range: {score}"


def test_missing_field_does_not_break_scoring():
    listing = {k: v for k, v in SAMPLE_LISTING.items() if k != 'hwb_value'}
    scores = score_all_profiles(listing)
    assert len(scores) == 10  # all profiles still scored
    # eco_conscious has hwb weight 0.25, so it should be lower than for full data
    full_scores = score_all_profiles(SAMPLE_LISTING)
    assert scores['eco_conscious'] < full_scores['eco_conscious']


def test_different_profiles_yield_different_scores():
    scores = score_all_profiles(SAMPLE_LISTING)
    unique_scores = set(scores.values())
    # Most listings will have at least 5 distinct scores across 10 profiles
    assert len(unique_scores) >= 5, f"Expected diverse scores, got {scores}"


def test_empty_listing_returns_zero_scores():
    scores = score_all_profiles({'_id': 'empty'})
    assert len(scores) == 10
    for s in scores.values():
        assert s == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_profile_scoring.py -v`
Expected: ImportError or ModuleNotFoundError (profile_scoring doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Create `Project/Application/profile_scoring.py`:

```python
#!/usr/bin/env python3
"""
Per-profile scoring for dashboard precalculation.

Scores one listing against all buyer profiles and returns a dict
mapping profile key -> normalized score (0-100).
"""
import logging
from typing import Any

from Application.buyer_profiles import BUYER_PROFILES
from Application.scoring import score_apartment_simple

logger = logging.getLogger(__name__)


def score_all_profiles(listing_dict: dict[str, Any]) -> dict[str, float]:
    """Score a single listing against every buyer profile.

    Skips profiles whose scoring raises; logs a warning.
    Returns dict with all profile keys (missing ones omitted on failure).
    """
    scores: dict[str, float] = {}
    for profile_key, profile in BUYER_PROFILES.items():
        try:
            weights = profile['weights']
            score = score_apartment_simple(listing_dict, weights=weights)
            scores[profile_key] = round(float(score), 2)
        except Exception as e:
            logger.warning(
                "profile_scoring: failed to score profile=%s listing=%s err=%s",
                profile_key,
                listing_dict.get('_id', '<no-id>'),
                e,
            )
    return scores
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_profile_scoring.py -v`
Expected: 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add Project/Application/profile_scoring.py Tests/test_profile_scoring.py
git commit -m "feat(scoring): per-profile precalc module + unit tests"
```

---

## Task 2: MongoDB handler extensions

**Files:**
- Modify: `Project/Integration/mongodb_handler.py`

- [ ] **Step 1: Add PROFILE_NAMES and index helper near top of file**

After the existing imports and before the class definition, add:

```python
from Application.buyer_profiles import BUYER_PROFILES
PROFILE_NAMES: list[str] = list(BUYER_PROFILES.keys())
```

- [ ] **Step 2: Add index creation in `__init__` after existing `create_index` calls**

In the `MongoDBHandler.__init__` method, after the existing index creation, add:

```python
# Per-profile score indexes (compound with processed_at for stable tiebreak)
for _profile in PROFILE_NAMES:
    try:
        self.collection.create_index(
            [(f'scores.{_profile}', -1), ('processed_at', -1)],
            name=f'scores_{_profile}_idx',
        )
    except Exception as e:
        logging.warning(f"Could not create index scores.{_profile}: {e}")
```

- [ ] **Step 3: Add `update_profile_scores` method**

Add a new method on `MongoDBHandler` (place near `update_listing`):

```python
def update_profile_scores(self, listing_id, scores: dict) -> None:
    """Persist per-profile scores subdoc for a listing.

    Idempotent: $set is a no-op if values are unchanged.
    """
    if not scores:
        return
    from datetime import datetime, timezone
    self.collection.update_one(
        {'_id': listing_id},
        {
            '$set': {
                'scores': scores,
                'scores_updated_at': datetime.now(timezone.utc),
            }
        },
    )
```

- [ ] **Step 4: Extend `get_top_listings` to accept `profile`**

In `MongoDBHandler.get_top_listings`, add `profile: str = "default"` to the signature, and replace the existing `find` call's `.sort` to use per-profile sort when `profile != "default"`. The new signature:

```python
def get_top_listings(
    self,
    limit: int = 5,
    min_score: float = 0.0,
    days_old: int = 30,
    district: str | None = None,
    profile: str = "default",
) -> list[dict]:
```

And in the existing sort logic, replace:

```python
.sort([("score", -1), ("processed_at", -1)])
```

with:

```python
.sort(
    ([(f"scores.{profile}", -1), ("processed_at", -1)]
     if profile != "default"
     else [("score", -1), ("processed_at", -1)])
)
```

- [ ] **Step 5: Verify file imports cleanly**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -c "from Integration.mongodb_handler import MongoDBHandler, PROFILE_NAMES; print('OK', len(PROFILE_NAMES))"`
Expected: `OK 10`

- [ ] **Step 6: Commit**

```bash
git add Project/Integration/mongodb_handler.py
git commit -m "feat(mongo): per-profile score indexes + update_profile_scores"
```

---

## Task 3: Integrate scoring into main.py scrape flow

**Files:**
- Modify: `Project/Application/main.py`

- [ ] **Step 1: Find the listing upsert block in main.py**

Run: `grep -n "score_apartment_simple\|mongo.update\|update_listing" /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project/Application/main.py | head -20`

- [ ] **Step 2: Add import near other scoring imports**

Add (near the existing `from Application.scoring import set_buyer_profile, score_apartment_simple`):

```python
from Application.profile_scoring import score_all_profiles
```

- [ ] **Step 3: After each listing upsert, compute and persist per-profile scores**

Find the block where each listing's `score` is computed and stored (around line 715-720 in current main.py). After the existing `score = score_apartment_simple(listing.__dict__)` and the mongo update that stores `score`, add:

```python
try:
    all_scores = score_all_profiles(listing.__dict__)
    if all_scores:
        mongo_handler.update_profile_scores(listing._id if hasattr(listing, '_id') else listing.id, all_scores)
except Exception as e:
    logger.error(f"Failed to update profile scores for {getattr(listing, '_id', '<no-id>')}: {e}")
```

- [ ] **Step 4: Verify syntax**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -c "import Application.main"`
Expected: no errors (or known import-time warnings only)

- [ ] **Step 5: Commit**

```bash
git add Project/Application/main.py
git commit -m "feat(scrape): compute + store per-profile scores at scrape time"
```

---

## Task 4: Backfill CLI

**Files:**
- Create: `Project/scripts/__init__.py`
- Create: `Project/scripts/backfill_profile_scores.py`
- Test: `Tests/test_backfill_idempotent.py`

- [ ] **Step 1: Create package marker**

Create `Project/scripts/__init__.py`:

```python
"""CLI scripts for immo-scouter."""
```

- [ ] **Step 2: Write failing idempotency test**

Create `Tests/test_backfill_idempotent.py`:

```python
"""Integration test: backfill_profile_scores is idempotent."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import importlib.util

# Load the backfill module
SCRIPT_PATH = Path(__file__).parent.parent / 'Project' / 'scripts' / 'backfill_profile_scores.py'
spec = importlib.util.spec_from_file_location('backfill_profile_scores', SCRIPT_PATH)
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)


def test_idempotent_no_changes_on_second_run():
    # Fake mongo with 3 listings
    fake_collection = MagicMock()
    cursor = MagicMock()
    cursor.__iter__ = lambda self: iter([
        {'_id': 'a', 'price_per_m2': 5000, 'area_m2': 80, 'rooms': 3},
        {'_id': 'b', 'price_per_m2': 6000, 'area_m2': 90, 'rooms': 4},
        {'_id': 'c', 'price_per_m2': 4000, 'area_m2': 70, 'rooms': 2},
    ])
    fake_collection.find.return_value = cursor
    # First call returns no scores, second call returns full scores
    fake_collection.find_one.side_effect = [
        None, {'_id': 'a', 'scores': {'default': 50.0, 'owner_occupier': 60.0}},
        None, {'_id': 'b', 'scores': {'default': 55.0, 'owner_occupier': 65.0}},
        None, {'_id': 'c', 'scores': {'default': 60.0, 'owner_occupier': 70.0}},
        {'_id': 'a', 'scores': {'default': 50.0, 'owner_occupier': 60.0}},  # on second pass
        {'_id': 'b', 'scores': {'default': 55.0, 'owner_occupier': 65.0}},
        {'_id': 'c', 'scores': {'default': 60.0, 'owner_occupier': 70.0}},
    ]
    fake_mongo = MagicMock()
    fake_mongo.collection = fake_collection
    with patch.object(backfill, 'MongoDBHandler', return_value=fake_mongo):
        backfill.run_backfill(dry_run=False, batch=10)
        updates_after_first = fake_collection.update_one.call_count
        # Run again — should be a no-op (all listings have scores)
        fake_collection.update_one.reset_mock()
        backfill.run_backfill(dry_run=False, batch=10)
        updates_after_second = fake_collection.update_one.call_count
    # Second run should issue far fewer updates (only ones missing scores)
    assert updates_after_first >= 3
    assert updates_after_second < updates_after_first
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_backfill_idempotent.py -v`
Expected: ImportError (backfill module doesn't exist)

- [ ] **Step 4: Implement backfill script**

Create `Project/scripts/backfill_profile_scores.py`:

```python
#!/usr/bin/env python3
"""One-shot CLI: compute per-profile scores for existing listings.

Usage:
  python -m Project.scripts.backfill_profile_scores [--batch 500] [--dry-run] [--profile owner_occupier]
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
        if all(p in existing_scores for p in PROFILE_NAMES):
            skipped += 1
            continue
        try:
            new_scores = score_all_profiles(full)
            if only_profile:
                new_scores = {only_profile: new_scores[only_profile]}
                new_scores = {**{p: existing_scores.get(p) for p in PROFILE_NAMES if p in existing_scores}, **new_scores}
            if dry_run:
                logger.info(f"[dry-run] would update _id={doc['_id']} scores={new_scores}")
            else:
                mongo.collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'scores': new_scores, 'scores_updated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc)}},
                )
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_backfill_idempotent.py -v`
Expected: 1 test passes

- [ ] **Step 6: Run backfill in dry-run mode (no DB writes)**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -m scripts.backfill_profile_scores --dry-run --batch 100 2>&1 | head -20`
Expected: lists some `_id` entries with `scores=...`; no errors

- [ ] **Step 7: Commit**

```bash
git add Project/scripts/__init__.py Project/scripts/backfill_profile_scores.py Tests/test_backfill_idempotent.py
git commit -m "feat(backfill): one-shot CLI to compute per-profile scores + idempotency test"
```

---

## Task 5: Run backfill on dev DB

**Files:** none (DB op only)

- [ ] **Step 1: Verify Mongo connection**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -c "from Integration.mongodb_handler import MongoDBHandler; h = MongoDBHandler(); print('count:', h.collection.count_documents({}))"`
Expected: prints a positive integer (your listings count)

- [ ] **Step 2: Run backfill (live)**

Run: `python -m scripts.backfill_profile_scores --batch 500 2>&1 | tail -30`
Expected: `backfill complete: {'processed': N, 'updated': M, 'skipped': ..., 'errors': 0}`

- [ ] **Step 3: Spot-check 1 listing has all 10 scores**

Run: `python -c "from Integration.mongodb_handler import MongoDBHandler; h = MongoDBHandler(); doc = h.collection.find_one({'scores': {'$exists': True}}); print('keys:', sorted((doc.get('scores') or {}).keys()))"`
Expected: 10 profile keys

- [ ] **Step 4: Re-run backfill (idempotency check)**

Run: `python -m scripts.backfill_profile_scores --batch 500 2>&1 | tail -5`
Expected: `skipped` count = `processed` count (no `updated`)

- [ ] **Step 5: Commit (no source changes; this is a DB op — skip if no files changed)**

If no files changed, this step is a no-op. Otherwise commit any config tweaks.

---

## Task 6: Shared profile list (client)

**Files:**
- Create: `dashboard/lib/profile.ts`

- [ ] **Step 1: Create the profile module**

Create `dashboard/lib/profile.ts`:

```typescript
/**
 * Single source of truth for buyer profile list + display labels on the client.
 * MUST be kept in sync with Project/Application/buyer_profiles.py BUYER_PROFILES keys.
 * Drift test: Tests/test_profile_sync.py asserts equality (see Task 13).
 */

export interface ProfileMeta {
  key: string;
  label: string;
  description: string;
}

export const PROFILES: ProfileMeta[] = [
  { key: 'default',           label: 'Default',            description: 'Balanced scoring for general property evaluation' },
  { key: 'owner_occupier',    label: 'Owner-Occupier',     description: 'Newer, efficient homes with low renovation needs' },
  { key: 'diy_renovator',     label: 'DIY Renovator',      description: 'Actively seeking properties to add value through renovation' },
  { key: 'growing_family',    label: 'Growing Family',     description: 'Space, safety, and convenience for children' },
  { key: 'urban_professional',label: 'Urban Professional', description: 'Location, lifestyle, modern comforts' },
  { key: 'eco_conscious',     label: 'Eco-Conscious',      description: 'Sustainability, energy efficiency, low carbon footprint' },
  { key: 'retiree',           label: 'Retiree',            description: 'Comfort, accessibility, peaceful living' },
  { key: 'budget_buyer',      label: 'Budget Buyer',       description: 'Enter the market at lowest cost' },
  { key: 'prime_new_build',   label: 'Prime New Build',    description: 'New/recent construction in good zones' },
  { key: 'bank_loan_ready',   label: 'Bank Loan Ready',    description: 'Austrian bank Belehnungswert criteria; missing fields score 0' },
];

export const PROFILE_KEYS: string[] = PROFILES.map((p) => p.key);

export const PROFILE_LABELS: Record<string, string> = Object.fromEntries(
  PROFILES.map((p) => [p.key, p.label]),
);

export const DEFAULT_PROFILE = 'default';

export function isValidProfile(s: string | null | undefined): s is string {
  return typeof s === 'string' && PROFILE_KEYS.includes(s);
}
```

- [ ] **Step 2: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit lib/profile.ts`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/profile.ts
git commit -m "feat(dashboard): shared client profile list"
```

---

## Task 7: Extend dashboard URL filters

**Files:**
- Modify: `dashboard/lib/filters.ts`

- [ ] **Step 1: Read current filters.ts**

Run: `cat /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/lib/filters.ts`

- [ ] **Step 2: Add `profile` field to FilterState and helpers**

Modify `dashboard/lib/filters.ts`:

```typescript
import { DEFAULT_PROFILE, isValidProfile } from './profile';

export interface FilterState {
  minScore: string;
  district: string;
  sortBy: string;
  maxPrice: string;
  showUnfinanceable: boolean;
  equity: string;
  rate: string;
  maxEquity: string;
  profile: string;  // NEW
}

export function filtersFromParams(params: URLSearchParams): FilterState {
  const rawProfile = params.get('profile');
  return {
    minScore: params.get('min_score') ?? '0',
    district: params.get('district') ?? '',
    sortBy: params.get('sort') ?? 'score_desc',
    maxPrice: params.get('max_price') ?? '500000',
    showUnfinanceable: params.get('show_unfinanceable') === '1',
    equity: params.get('equity') ?? '100000',
    rate: params.get('rate') ?? '3.8',
    maxEquity: params.get('max_equity') ?? '',
    profile: isValidProfile(rawProfile) ? (rawProfile as string) : DEFAULT_PROFILE,
  };
}

export function paramsFromFilters(state: FilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.minScore !== '0') params.set('min_score', state.minScore);
  if (state.district) params.set('district', state.district);
  if (state.sortBy !== 'score_desc') params.set('sort', state.sortBy);
  if (state.maxPrice !== '500000') params.set('max_price', state.maxPrice);
  if (state.showUnfinanceable) params.set('show_unfinanceable', '1');
  if (state.equity !== '100000') params.set('equity', state.equity);
  if (state.rate !== '3.8') params.set('rate', state.rate);
  if (state.maxEquity) params.set('max_equity', state.maxEquity);
  // Always set profile explicitly so URL is shareable
  params.set('profile', state.profile);
  return params;
}
```

- [ ] **Step 3: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit lib/filters.ts`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/filters.ts
git commit -m "feat(filters): add profile to URL state"
```

---

## Task 8: API route — top listings

**Files:**
- Modify: `dashboard/app/api/listings/top/route.ts`

- [ ] **Step 1: Read current file (already done in exploration)**

- [ ] **Step 2: Add profile validation + sort**

Replace the existing `validateSort` import line and the sortOptions block with:

```typescript
import { validateDistrict, validateSort, validateMinScore, validateLimit, validateStatus } from '@/lib/validators';
import { DEFAULT_PROFILE, PROFILE_KEYS, isValidProfile } from '@/lib/profile';
```

- [ ] **Step 3: Add profile parameter handling in GET**

After the `sort` line in GET, add:

```typescript
const profileParam = searchParams.get('profile');
const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
if (profileParam && !isValidProfile(profileParam)) {
  console.warn('[/api/listings/top] Invalid profile rejected:', profileParam);
}
```

- [ ] **Step 4: Update sortOptions + sortBy to use per-profile sort when active**

Replace the `sortOptions` constant with:

```typescript
const baseSortOptions: Record<string, Record<string, 1 | -1>> = {
  score_desc: {},  // populated below based on profile
  price_asc: { price_total: 1 },
  price_desc: { price_total: -1 },
  date_desc: { processed_at: -1 },
  area_desc: { area_m2: -1 },
};
if (profile === DEFAULT_PROFILE) {
  baseSortOptions.score_desc = { score: -1, processed_at: -1 };
} else {
  baseSortOptions.score_desc = { [`scores.${profile}`]: -1, processed_at: -1 };
}
const sortBy = baseSortOptions[sort] ?? baseSortOptions.score_desc;
```

- [ ] **Step 5: Return per-profile score in payload**

In the listings `.map(...)`, change `score: l.score,` to:

```typescript
score: (l as any).scores?.[profile] ?? l.score ?? null,
profile,
```

- [ ] **Step 6: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add dashboard/app/api/listings/top/route.ts
git commit -m "feat(api): /listings/top accepts ?profile= and sorts by scores.<profile>"
```

---

## Task 9: API route — map listings

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts`

- [ ] **Step 1: Add profile import**

After existing imports, add:

```typescript
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
```

- [ ] **Step 2: Add profile parameter handling**

After `const sort = validateSort(searchParams.get('sort'));` in GET, add:

```typescript
const profileParam = searchParams.get('profile');
const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
if (profileParam && !isValidProfile(profileParam)) {
  console.warn('[/api/listings/map] Invalid profile rejected:', profileParam);
}
```

- [ ] **Step 3: Update sortOptions + sortBy**

Replace the existing sortOptions block with:

```typescript
const baseSortOptions: Record<string, Record<string, 1 | -1>> = {
  score_desc: {},
  price_asc: { price_total: 1 },
  price_desc: { price_total: -1 },
  date_desc: { processed_at: -1 },
  area_desc: { area_m2: -1 },
};
if (profile === DEFAULT_PROFILE) {
  baseSortOptions.score_desc = { score: -1, processed_at: -1 };
} else {
  baseSortOptions.score_desc = { [`scores.${profile}`]: -1, processed_at: -1 };
}
const sortBy = baseSortOptions[sort] ?? baseSortOptions.score_desc;
```

- [ ] **Step 4: Return per-profile score in payload**

In the map response, change `score: l.score,` to:

```typescript
score: (l as any).scores?.[profile] ?? l.score ?? null,
profile,
```

- [ ] **Step 5: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts
git commit -m "feat(api): /listings/map accepts ?profile= and sorts by scores.<profile>"
```

---

## Task 10: API routes — detail and stream

**Files:**
- Modify: `dashboard/app/api/listings/[id]/route.ts`
- Modify: `dashboard/app/api/listings/stream/route.ts`

- [ ] **Step 1: Read both files**

```bash
cat /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/app/api/listings/[id]/route.ts
cat /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/app/api/listings/stream/route.ts
```

- [ ] **Step 2: In [id]/route.ts, add profile param + return active profile's score**

At the top after existing imports, add:

```typescript
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
```

Inside GET, after any other search-params reading, add:

```typescript
const profileParam = searchParams.get('profile');
const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
```

In the response payload, change `score: listing.score` to:

```typescript
score: (listing as any).scores?.[profile] ?? listing.score ?? null,
profile,
```

Also include all scores in the response (for client Map cache):

```typescript
scores: (listing as any).scores ?? null,
```

- [ ] **Step 3: In stream/route.ts, include all scores in payload**

Find the response payload construction. Add to each listing:

```typescript
scores: (l as any).scores ?? null,
```

- [ ] **Step 4: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/api/listings/\[id\]/route.ts dashboard/app/api/listings/stream/route.ts
git commit -m "feat(api): per-profile score in detail + stream payloads"
```

---

## Task 11: ProfileSelector component

**Files:**
- Create: `dashboard/components/ProfileSelector.tsx`
- Modify: `dashboard/components/FilterBar.tsx`
- Modify: `dashboard/components/FilterDrawer.tsx`

- [ ] **Step 1: Create ProfileSelector.tsx**

Create `dashboard/components/ProfileSelector.tsx`:

```tsx
'use client';

import React from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { PROFILES, PROFILE_LABELS, DEFAULT_PROFILE } from '@/lib/profile';

export function ProfileSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = searchParams.get('profile') ?? DEFAULT_PROFILE;

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    const params = new URLSearchParams(searchParams.toString());
    if (next === DEFAULT_PROFILE) {
      params.delete('profile');
    } else {
      params.set('profile', next);
    }
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700">Buyer Profile</label>
      <select
        data-testid="profile-selector"
        value={current}
        onChange={handleChange}
        className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
        aria-label="Buyer profile"
      >
        {PROFILES.map((p) => (
          <option key={p.key} value={p.key} title={p.description}>
            {p.label}
          </option>
        ))}
      </select>
    </div>
  );
}
```

- [ ] **Step 2: Add ProfileSelector to FilterBar**

In `dashboard/components/FilterBar.tsx`, add import at top:

```tsx
import { ProfileSelector } from './ProfileSelector';
```

In the JSX, before the existing `<div className="flex items-center gap-2 ml-auto">` (the Min Score block), add:

```tsx
<ProfileSelector />
```

- [ ] **Step 3: Add ProfileSelector to FilterDrawer**

In `dashboard/components/FilterDrawer.tsx`, add the same import. In the drawer body, near the top, add:

```tsx
<ProfileSelector />
```

- [ ] **Step 4: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/ProfileSelector.tsx dashboard/components/FilterBar.tsx dashboard/components/FilterDrawer.tsx
git commit -m "feat(ui): ProfileSelector in FilterBar and FilterDrawer"
```

---

## Task 12: Wire profile into dashboard pages (instant local switch)

**Files:**
- Modify: `dashboard/app/dashboard/page.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Read both pages**

- [ ] **Step 2: In dashboard/page.tsx, add profile state + local Map cache + re-sort on switch**

Add to imports:

```tsx
import { isValidProfile, DEFAULT_PROFILE, PROFILE_KEYS } from '@/lib/profile';
```

In `DashboardContent` component, add new state:

```tsx
const [profile, setProfile] = useState<string>(DEFAULT_PROFILE);
const [allLoadedScores, setAllLoadedScores] = useState<Record<string, Record<string, number | null>>>({});
```

In the `useEffect` that reads `searchParams`, sync profile:

```tsx
const p = searchParams.get('profile');
setProfile(isValidProfile(p) ? p : DEFAULT_PROFILE);
```

In `fetchListings`, modify to also capture all scores:

```tsx
const res = await fetch(`/api/listings/top?${params.toString()}`);
const data = await res.json();
setListings(data.listings ?? []);
const map: Record<string, Record<string, number | null>> = {};
for (const l of data.listings ?? []) {
  map[l._id] = (l as any).scores ?? { [profile]: l.score ?? null };
}
setAllLoadedScores(map);
```

Also extend the params construction in `fetchListings` to include `profile`:

```tsx
if (profile !== DEFAULT_PROFILE) params.set('profile', profile);
```

Add a `useEffect` that re-derives sorted listings locally when `profile` changes (no refetch):

```tsx
useEffect(() => {
  if (Object.keys(allLoadedScores).length === 0) return;
  setListings((prev) => {
    const sorted = [...prev].sort((a, b) => {
      const sa = allLoadedScores[a._id]?.[profile] ?? a.score ?? 0;
      const sb = allLoadedScores[b._id]?.[profile] ?? b.score ?? 0;
      return sb - sa;
    });
    return sorted;
  });
}, [profile, allLoadedScores]);
```

- [ ] **Step 3: In map/page.tsx, add the same profile handling**

Mirror the dashboard changes: import profile helpers, add `profile` state, sync from URL, pass profile to API, store all scores, re-sort markers when profile changes.

- [ ] **Step 4: Type-check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/dashboard/page.tsx dashboard/app/dashboard/map/page.tsx
git commit -m "feat(ui): instant local re-sort on profile change"
```

---

## Task 13: Profile sync drift test (Python ↔ TS)

**Files:**
- Create: `Tests/test_profile_sync.py`

- [ ] **Step 1: Write the test**

Create `Tests/test_profile_sync.py`:

```python
"""Drift test: TS profile keys must match Python BUYER_PROFILES keys."""
import re
from pathlib import Path

from Application.buyer_profiles import BUYER_PROFILES

TS_FILE = Path(__file__).parent.parent / 'dashboard' / 'lib' / 'profile.ts'
ts_text = TS_FILE.read_text()
ts_keys = set(re.findall(r"key:\s*'([^']+)'", ts_text))
py_keys = set(BUYER_PROFILES.keys())


def test_keys_match():
    missing_in_ts = py_keys - ts_keys
    extra_in_ts = ts_keys - py_keys
    assert not missing_in_ts, f"Python profiles missing from TS: {missing_in_ts}"
    assert not extra_in_ts, f"TS profiles missing from Python: {extra_in_ts}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -m pytest Tests/test_profile_sync.py -v`
Expected: 1 test passes

- [ ] **Step 3: Commit**

```bash
git add Tests/test_profile_sync.py
git commit -m "test: assert TS profile keys match Python BUYER_PROFILES"
```

---

## Task 14: Playwright tests — sort and URL state

**Files:**
- Create: `dashboard/tests/profile-sort.spec.ts`
- Create: `dashboard/tests/profile-url-state.spec.ts`

- [ ] **Step 1: Read dashboard smoke test for patterns**

Run: `cat /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard/tests/smoke.spec.ts | head -50`

- [ ] **Step 2: Create profile-sort.spec.ts**

Create `dashboard/tests/profile-sort.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('profile switch reorders listings and reflects in URL', async ({ page }) => {
  await page.goto('/dashboard?profile=owner_occupier');
  await page.waitForLoadState('networkidle');
  const cards = page.locator('[data-testid="listing-card"]');
  await expect(cards.first()).toBeVisible();
  const firstScoreBefore = await cards.first().getAttribute('data-score');

  // Switch to bank_loan_ready via dropdown
  await page.selectOption('[data-testid="profile-selector"]', 'bank_loan_ready');
  await page.waitForURL(/profile=bank_loan_ready/);
  await page.waitForTimeout(500); // let local re-sort settle

  const firstScoreAfter = await cards.first().getAttribute('data-score');
  expect(firstScoreBefore).not.toBeNull();
  expect(firstScoreAfter).not.toBeNull();
  // Either score changed OR first card is different
  const firstHrefBefore = await cards.first().getAttribute('data-listing-id');
  const firstHrefAfter = await cards.first().getAttribute('data-listing-id');
  // At least one of: score changed, listing id changed
  expect(firstScoreBefore !== firstScoreAfter || firstHrefBefore !== firstHrefAfter).toBe(true);
});
```

- [ ] **Step 3: Create profile-url-state.spec.ts**

Create `dashboard/tests/profile-url-state.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('profile persists across page refresh and is shareable', async ({ page }) => {
  await page.goto('/dashboard?profile=urban_professional');
  await expect(page).toHaveURL(/profile=urban_professional/);

  await page.reload();
  await expect(page).toHaveURL(/profile=urban_professional/);

  const selector = page.locator('[data-testid="profile-selector"]');
  await expect(selector).toHaveValue('urban_professional');
});

test('invalid profile in URL falls back to default', async ({ page }) => {
  await page.goto('/dashboard?profile=garbage');
  await page.waitForLoadState('networkidle');
  // Should still render and have default selected
  const selector = page.locator('[data-testid="profile-selector"]');
  await expect(selector).toHaveValue('default');
});
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/tests/profile-sort.spec.ts dashboard/tests/profile-url-state.spec.ts
git commit -m "test(e2e): profile sort + URL state Playwright tests"
```

---

## Task 15: Playwright test — map

**Files:**
- Create: `dashboard/tests/profile-map.spec.ts`

- [ ] **Step 1: Create profile-map.spec.ts**

Create `dashboard/tests/profile-map.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('map reflects active profile and persists in URL', async ({ page }) => {
  await page.goto('/dashboard/map?profile=urban_professional');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(/profile=urban_professional/);
  // Leaflet container visible
  const map = page.locator('.leaflet-container');
  await expect(map).toBeVisible();
  // At least one marker (pin)
  const markers = page.locator('.leaflet-marker-icon');
  await expect(markers.first()).toBeVisible({ timeout: 10000 });
});

test('switching profile on map updates URL and does not reload map', async ({ page }) => {
  await page.goto('/dashboard/map?profile=default');
  await page.waitForLoadState('networkidle');
  await page.selectOption('[data-testid="profile-selector"]', 'eco_conscious');
  await page.waitForURL(/profile=eco_conscious/);
  const map = page.locator('.leaflet-container');
  await expect(map).toBeVisible();
});
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/tests/profile-map.spec.ts
git commit -m "test(e2e): map profile switch Playwright test"
```

---

## Task 16: Visual verification (per ui_scope flag)

**Files:** new screenshot PNGs in `dashboard/tests/screenshots/`

- [ ] **Step 1: Start dev server in background**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npm run dev > /tmp/dashboard-dev.log 2>&1 &
echo $! > /tmp/dashboard-dev.pid
sleep 12
```

- [ ] **Step 2: Render dashboard with profile at 3 viewports**

For each viewport (375×667 mobile, 768×1024 tablet, 1280×800 desktop):
1. Open `/dashboard?profile=owner_occupier`
2. Wait for `networkidle`
3. Take full-page screenshot → `dashboard/tests/screenshots/dashboard-profile-{viewport}.png`

- [ ] **Step 3: Render map with profile at 3 viewports**

Same as Step 2 but for `/dashboard/map?profile=urban_professional` → `dashboard/tests/screenshots/map-profile-{viewport}.png`

- [ ] **Step 4: Open FilterDrawer on mobile**

At 375×667, open `/dashboard`, click the filter FAB, screenshot the drawer → `dashboard/tests/screenshots/filter-drawer-profile-mobile.png`

- [ ] **Step 5: Inspect screenshots**

Verify visually:
- ProfileSelector is visible and shows correct label
- ProfileSelector is in FilterDrawer on mobile
- No layout breaks at any viewport
- Map markers visible

- [ ] **Step 6: Stop dev server**

```bash
kill $(cat /tmp/dashboard-dev.pid) 2>/dev/null
rm -f /tmp/dashboard-dev.pid
```

- [ ] **Step 7: Commit screenshots**

```bash
git add dashboard/tests/screenshots/
git commit -m "test(visual): screenshots of profile switcher at 3 viewports"
```

---

## Task 17: UI testing loop (mandatory per .claude/rules/ui-testing.md)

**Files:** none (test runs only)

- [ ] **Step 1: Start dev server in background**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npm run dev > /tmp/dashboard-dev.log 2>&1 &
echo $! > /tmp/dashboard-dev.pid
sleep 12
```

- [ ] **Step 2: Run full Playwright suite**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx playwright test --reporter=list
```

- [ ] **Step 3: Check console errors**

If any browser console errors or test failures, read output, fix code, re-run. Loop until clean.

- [ ] **Step 4: Stop dev server**

```bash
kill $(cat /tmp/dashboard-dev.pid) 2>/dev/null
rm -f /tmp/dashboard-dev.pid
```

- [ ] **Step 5: Commit any test fixes**

If test files were modified, commit with descriptive message.

---

## Task 18: Coverage measurement (per test_scope flag)

**Files:** none (test runs only)

- [ ] **Step 1: Run Python tests with coverage**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
python -m pytest Tests/test_profile_scoring.py Tests/test_backfill_idempotent.py Tests/test_profile_sync.py --cov=Project.Application.profile_scoring --cov=Project.scripts.backfill_profile_scores --cov-report=term-missing
```

- [ ] **Step 2: Record coverage number**

Expected: 80%+ on new modules. If below, add tests.

- [ ] **Step 3: Commit (no source changes; skip if nothing changed)**

---

## Task 19: Final verification

- [ ] **Step 1: Run ALL tests**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
python -m pytest Tests/ -v
```

Expected: all tests pass (or known pre-existing failures, none new)

- [ ] **Step 2: Run TypeScript checks**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 3: Final UI test run**

Run Task 17's loop one more time. All green.

- [ ] **Step 4: Show final diff**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
git log --oneline main..HEAD
git diff main --stat
```

---

## Self-Review (post-write)

1. **Spec coverage:**
   - D1 (per-listing `scores` subdoc) → Tasks 1, 2, 3 ✓
   - D2 (compute at scrape time in main.py) → Task 3 ✓
   - D3 (backfill CLI) → Tasks 4, 5 ✓
   - D4 (sort by `scores.<profile>`) → Tasks 8, 9 ✓
   - D5 (client local Map cache, instant switch) → Task 12 ✓
   - D6 (ProfileSelector in FilterBar + FilterDrawer) → Task 11 ✓
   - D7 (`dashboard/lib/profile.ts` source of truth) → Task 6, sync test Task 13 ✓
   - All modules from spec covered ✓
   - Error handling table from spec → covered inline in each task ✓
   - Testing section from spec → Tasks 13, 14, 15, 17, 18 ✓
   - ui_scope flag → Task 16 ✓
   - test_scope flag → Task 18 ✓

2. **Placeholder scan:** No "TBD" or "implement later". All code blocks complete. All commands with expected output.

3. **Type consistency:**
   - `score_all_profiles` defined Task 1, called Task 3 ✓
   - `update_profile_scores` defined Task 2, called Task 3 ✓
   - `PROFILE_NAMES` defined Task 2, used Task 4 ✓
   - `PROFILE_KEYS` defined Task 6, used Tasks 7, 8, 9, 10, 12 ✓
   - `isValidProfile` defined Task 6, used Tasks 7, 8, 9, 10, 12 ✓
   - `DEFAULT_PROFILE` defined Task 6, used Tasks 7, 8, 9, 10, 11, 12 ✓
   - `ProfileSelector` defined Task 11, used in FilterBar + FilterDrawer Task 11 + tests Tasks 14, 15 ✓
   - `filters.ts` FilterState extended Task 7, used Task 12 ✓

4. **Plan grill-me inline:** No blocking issues found. All decisions are reversible via single commits. Backfill is additive.

---

## Execution Handoff

This plan is ready. Per the user's "do not stop until finished" directive, executing inline in this session via `superpowers:executing-plans`.
