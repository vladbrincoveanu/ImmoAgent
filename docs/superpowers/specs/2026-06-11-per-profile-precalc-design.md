---
title: Per-Profile Precalculated Listing Scores (Dashboard Buyer Profile Switcher)
date: 2026-06-11
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Per-Profile Precalculated Listing Scores

## Context

The dashboard currently sorts listings by a single `score` field set at scrape time with whatever buyer profile was active. Switching buyer profiles via the Python CLI (`run_top5.py --buyer-profile=...`) re-runs scoring; the dashboard has no equivalent. Users want to switch profiles in the UI and see the listing order change accordingly — instantly, including the map view.

## Goals

- Buyer profile selectable in the dashboard UI (10 profiles)
- Switching profile re-orders listings on `/dashboard` AND `/dashboard/map` instantly
- All scores precomputed at scrape time, no runtime re-scoring
- Profile persists in URL (`?profile=owner_occupier`) — shareable, back-button works
- Existing scraper pipeline (`run.py`) extended, not replaced
- Existing `run_top5.py` Telegram flow unaffected

## Non-Goals

- Per-profile listing subset filtering (we show all valid listings, just ranked)
- Per-profile `run_top5` Telegram digest (future work)
- UI for editing profile weights (out of scope; Python-only)
- Visualization of why one profile ranks a listing higher (future work)

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Store scores as `scores: { <profile>: <float> }` subdoc on each listing | Atomic write, single source of truth, indexed |
| D2 | Compute all 10 scores at scrape time inside `main.py` | Matches "eager precalc" user choice; no runtime scoring |
| D3 | Add `scripts/backfill_profile_scores.py` for legacy listings | Idempotent migration; no doc destruction |
| D4 | Sort by `scores.<profile>` desc when `?profile=` present; existing sorts still work | Backwards compatible with `?sort=price_asc` etc. |
| D5 | Client keeps all loaded listings + their 10 scores in a Map; switch re-derives sort without refetch | Instant switch UX |
| D6 | ProfileSelector component used in both desktop FilterBar and mobile FilterDrawer | Parity |
| D7 | `dashboard/lib/profile.ts` is the single source of profile list/labels on the client | Server (API) still accepts any string from PROFILES; client list is for UI |

## Architecture

```
Project/Application/main.py  ──┐
Project/scripts/                       │
  backfill_profile_scores.py  ───────┴─→ score_all_profiles(listing) → 10 scores
                                       │
                                       ▼
                              MongoDB listings collection
                              _id, ..., scores: {<10 floats>},
                                  scores_updated_at: ISODate
                              indexes: 10× {"scores.<p>": -1, processed_at: -1}
                                       │
                                       ▼
              ┌────────────────────────┴────────────────────────┐
              │                                                   │
   /api/listings/top?profile=X                   /api/listings/map?profile=X
              │                                                   │
              └────────────────────┬──────────────────────────────┘
                                   ▼
                       dashboard (client) — Map<id, {all scores}>
                                   │
                       ProfileSelector → URL ?profile= → re-sort locally (instant)
```

## Modules

### Module: `Project/Application/profile_scoring.py`
- **Responsibility:** Score one listing dict against all buyer profiles
- **Interface:** `score_all_profiles(listing_dict: dict) -> dict[str, float]`
- **Dependencies:** `Application.scoring.score_apartment_simple`, `Application.buyer_profiles.BUYER_PROFILES`
- **Size target:** <60 lines
- **Behavior:** Iterates `BUYER_PROFILES`; for each, calls `score_apartment_simple(listing, weights=profile['weights'])`. Skips profile on exception with `logging.warning`, continues others. Returns dict of `{profile_key: score_float}`.

### Module: `Project/Integration/mongodb_handler.py` (extended)
- **Responsibility:** Persist per-profile scores; serve per-profile sorted reads
- **Interface:**
  - `PROFILE_NAMES: list[str]` — frozen list of all profile keys
  - `ensure_profile_score_indexes(db)` — create 10 compound indexes `{"scores.<p>": -1, "processed_at": -1}`; called on `__init__`
  - `update_profile_scores(_id, scores: dict)` — `$set` scores + `scores_updated_at`
  - `get_top_listings(profile: str = "default", ...)` — existing fn extended; sorts by `scores[profile]` if profile != "default"
- **Dependencies:** pymongo
- **Size target:** +40 lines

### Module: `Project/scripts/backfill_profile_scores.py`
- **Responsibility:** One-shot CLI to compute scores for all existing listings
- **Interface:** `python -m Project.scripts.backfill_profile_scores [--batch 500] [--dry-run] [--profile <p>]`
- **Dependencies:** `Application.profile_scoring`, `Integration.mongodb_handler`
- **Size target:** <120 lines
- **Behavior:** Streams listings in batches; computes scores; writes `$set` update. Idempotent. Logs progress. `--dry-run` reports count without writing. `--profile` limits to one profile (faster iteration during weight tuning).

### Module: `dashboard/lib/profile.ts`
- **Responsibility:** Single source of truth for profile list + display labels on the client
- **Interface:**
  - `PROFILES: { key: string, label: string, description: string }[]` — array of 10
  - `PROFILE_KEYS: string[]` — keys only
  - `isValidProfile(s: string): boolean`
  - `defaultProfile = "default"`
- **Dependencies:** none
- **Size target:** <40 lines
- **Behavior:** Static list mirroring `Project/Application/buyer_profiles.py` BUYER_PROFILES keys + human labels. Comment: "keep in sync with buyer_profiles.py; CI smoke test asserts no drift."

### Module: `dashboard/components/ProfileSelector.tsx`
- **Responsibility:** Render dropdown for profile selection; push `?profile=` to URL
- **Interface:** `<ProfileSelector />` (no props — reads URL itself via `useSearchParams` + `useRouter`)
- **Dependencies:** `next/navigation`, `dashboard/lib/profile`
- **Size target:** <80 lines
- **Behavior:**
  - Renders `<select>` (desktop) + visible label
  - On change → `router.push(\`/dashboard?profile=${value}&...existingParams\`)`
  - Falls back to `default` if URL missing
  - Mobile: also rendered inside `FilterDrawer`

### Module: `dashboard/lib/filters.ts` (extended)
- **Responsibility:** URL ↔ state serialization
- **Interface:** `filtersFromParams`, `paramsFromFilters` (existing); add `profile: string` field
- **Dependencies:** `dashboard/lib/profile`
- **Size target:** +15 lines

### Touched (no new module)

- `Project/Application/main.py` — call `score_all_profiles(listing_dict)` after each listing upsert; pass result to mongo `update_profile_scores`
- `dashboard/app/api/listings/top/route.ts` — accept `?profile=`, validate against `PROFILE_KEYS`, build `sort` from `scores.<profile>`
- `dashboard/app/api/listings/map/route.ts` — same
- `dashboard/app/api/listings/[id]/route.ts` — return `score: l.scores[profile] ?? l.score` (profile from query param, default `default`)
- `dashboard/app/api/listings/stream/route.ts` — include all scores in payload so client can switch without refetch
- `dashboard/app/dashboard/page.tsx` — read `?profile=`, pass to `FilterBar`; store all listings + scores; re-derive sort on profile change
- `dashboard/app/dashboard/map/page.tsx` — same
- `dashboard/components/FilterBar.tsx` — render `<ProfileSelector />` between "Min Score" and "District" (logical grouping: filter intent)
- `dashboard/components/FilterDrawer.tsx` — same, mobile parity

## Data Flow

### Scrape-time (eager)
```
run.py → main()
  for each source → for each listing:
    existing doc = mongo.find_one({url_hash})
    listing_dict = {**existing, **new_fields}
    scores = score_all_profiles(listing_dict)  # {p1: 65.4, ..., p10: 42.1}
    mongo.update_listing(_id, {**fields, scores, scores_updated_at: now})
```

### Dashboard request
```
client → /api/listings/top?profile=owner_occupier&min_score=30
server:
  profile = validateProfile(searchParams.get('profile')) or 'default'
  sort = profile == 'default'
    ? {score: -1, processed_at: -1}                      # legacy path
    : {[`scores.${profile}`]: -1, processed_at: -1}     # new path
  results = mongo.find(filters).sort(sort).limit(N)
  return {listings: [{...listing, score: l.scores?.[profile] ?? l.score, profile}]}
```

### Client switch (instant)
```
URL changes from ?profile=default → ?profile=bank_loan_ready
client:
  listings_by_id (Map) already has all listings with all 10 scores from last fetch
  re-derive sortedList = sortBy(listings_by_id.values(), l => -l.scores[profile])
  setListings(sortedList)  // no network call
```

## Error Handling

| Failure | Behavior |
|---|---|
| `?profile=invalid` (not in `PROFILE_KEYS`) | 400 with `{error, validProfiles: [...]}`. UI dropdown prevents; server validates. |
| Listing has no `scores` field (pre-backfill) | `score = l.scores?.[profile] ?? l.score`; log `warn` once per (profile, missing_count). API still works, sort treats missing as 0. |
| `score_apartment` raises for one profile | `score_all_profiles` catches, logs `warning`, returns dict with that profile missing. Other 9 scores saved. |
| `score_all_profiles` raises for all profiles | `main.py` logs `error`, listing upsert proceeds without `scores` field (backfill can retry). |
| Weights change in `buyer_profiles.py` | Operator runs `backfill_profile_scores.py` to recompute. Documented in README. |
| New profile added to `buyer_profiles.py` | Old listings have no `scores.<new_key>`. API sorts missing as 0. Backfill re-run adds. |
| Mongo index creation fails | Logged at startup; read still works (full collection scan). Backfill can re-run. |
| `score_apartment` import error (circular) | Top-level import inside `score_all_profiles` to avoid cycle. |
| Profile switch race (rapid clicks) | `useSearchParams` is reactive; React batches. Last URL state wins. |

## Testing

### Unit (Python, `Tests/test_profile_scoring.py`)
- 1 synthetic listing × 10 profiles → dict of 10 floats
- Same listing with missing `hwb_value` → that criterion contributes 0 to all profiles
- `score_apartment` raises for 1 profile → returned dict has 9 entries, warning logged
- `sum(profile['weights'].values())` for all 10 = 1.0 ± 0.001

### Integration (Python, `Tests/test_backfill_idempotent.py`)
- Insert 3 listings with no `scores` field
- Run backfill (mocked mongo) → all 3 have `scores` after
- Run backfill again → no doc updates (idempotent)

### API (Next.js, `dashboard/tests/api-profile.spec.ts`)
- `GET /api/listings/top?profile=owner_occupier` → 200, all listings have non-null `score`
- `GET /api/listings/top?profile=garbage` → 400 with `validProfiles`
- `GET /api/listings/top` (no profile) → behaves as today (sort by `score`)
- `GET /api/listings/[id]?profile=urban_professional` → returns score matching profile
- `GET /api/listings/stream` → payload includes `scores` subdoc for all listings

### UI (Playwright, `dashboard/tests/profile-sort.spec.ts`, `profile-map.spec.ts`, `profile-url-state.spec.ts`)
- Load `/dashboard?profile=owner_occupier` → first card score = that profile's score for that listing (asserts via `data-testid="listing-card"` with `data-score`)
- Switch profile via dropdown → URL updates, no network refetch (assert via `page.on('request')`)
- Switch to `bank_loan_ready` → order differs from `owner_occupier`
- Load `/dashboard/map?profile=urban_professional` → at least 1 marker visible
- Refresh page → profile persists from URL
- Mobile viewport (375×667) → ProfileSelector visible in FilterDrawer
- `/dashboard?profile=invalid` → redirect to `?profile=default` OR show inline error (TBD: pick "redirect to default")

### Manual
- Scrape run with `--buyer-profile=owner_occupier` → listings have `scores.owner_occupier` ≈ raw `score` (sanity)
- Switch through all 10 profiles in UI → no console errors, no 500s
- `git diff main` review before merge

## Rollout

1. Spec committed (this file).
2. Plan written via `writing-plans` skill.
3. Branch `relentless/per-profile-precalc` auto-created.
4. Implementation order (each step = one commit):
   1. Add `Project/Application/profile_scoring.py` + unit tests
   2. Add `mongodb_handler` index + `update_profile_scores` + integrate into `main.py`
   3. Add `scripts/backfill_profile_scores.py` + idempotency test
   4. Run backfill on dev DB (verify counts)
   5. Add `dashboard/lib/profile.ts`
   6. Extend `dashboard/lib/filters.ts` with `profile`
   7. Extend API routes (`top`, `map`, `[id]`, `stream`)
   8. Add `ProfileSelector.tsx` + integrate in `FilterBar` + `FilterDrawer`
   9. Wire into `dashboard/page.tsx` and `map/page.tsx` (local Map cache, re-sort on switch)
   10. Add Playwright tests
   11. Run UI testing loop until 0 errors
5. No push to main. `git diff main` available for review.
6. `relentless` mode applies — no pauses for approval mid-execution per user directive.

## Spec Self-Review (post-write)

- **Placeholder scan:** None. TBD on `/dashboard?profile=invalid` behavior — resolved: redirect to default.
- **Internal consistency:** Architecture matches modules; modules match decisions; data flow matches modules.
- **Scope check:** Single dashboard feature, no decomposition needed.
- **Ambiguity check:** "Order only" decision explicit. "Eager precalc" explicit. URL state explicit. "No filtering per profile" explicit.
- **Type consistency:** `scores: dict[str, float]` (Python) ↔ `scores: Record<string, number>` (TS) — aligned.
- **Fail-fast:** Backfill CLI exits non-zero on Mongo error. API returns 4xx/5xx on bad input. UI shows toast on error.
- **Rollback:** Each step is a single commit. `git revert` per step works. Backfill is additive (no doc destruction).

## Open Questions

None — all disambiguated with user via AskUserQuestion (3 questions, all "Recommended" accepted).
