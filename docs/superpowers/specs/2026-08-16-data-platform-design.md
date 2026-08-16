---
title: Data platform upgrades — cross-source dedup, relist tracking, precise geo, richer capture, district drift analytics
date: 2026-08-16
status: approved
ui_scope: false
graph_scope: true
test_scope: true
---

# Data Platform Design: Dedup, Precise Geo, Richer Capture, Historical Analytics

5 sub-projects, one coherent data model. Current state confirmed by reading `mongodb_handler.py`, `listing.py`, `geocoding.py`, `listing_validator.py`, `contact_extractor.py`.

`graph_scope: true` — the fingerprint field changes (sub-project 1) touch multiple modules across scraping, validation, and Mongo write paths, so the knowledge graph should be updated after implementation.

## 0. Current state (baseline)

| Capability | Exists today | Gap |
|---|---|---|
| Price history | ✅ `price_history[]` pushed on price change | — |
| Listing lifecycle | ✅ `listing_status` (active/taken), `taken_at` | No relist-cycle counter; reappearance after "taken" not distinguished from a plain update |
| Dedup | ✅ `content_fingerprint` = md5(title+area+rooms+bezirk+source) | Title-based → fragile (agent edits title = "new" listing); scoped to one source → same physical unit on Willhaben + ImmoKurier stored twice |
| Coordinates | ✅ `coordinate_source`: exact / landmark / none. Willhaben ships exact coords; others geocode coarse address text via Nominatim | No precision estimate stored; distance calcs (school/U-Bahn) not recomputed when coords later upgrade landmark→exact |
| Seller type | Partial — `agent_name`/agency parsed in `contact_extractor.py`, used only for outreach | Not written back to the listing document → can't filter/query "private sellers only" in dashboard or Mongo |
| District/time rollups | ❌ none | No collection aggregates price/m² or listing counts by district over time |

## Data flow — where each subsystem plugs in

```
Scrapers (Willhaben / ImmoKurier / DerStandard / Genossenschaft)
  -> is_valid_listing_data
  -> compute_content_fingerprint_xsrc   [NEW: coord+area+rooms, cross-source]
  -> upsert_listing_with_history
       |
       +-- existing doc, status=taken, fingerprint match
       |     -> record_relist_event     [NEW]
       |     -> listings collection
       |
       +-- existing doc, status=active
       |     -> push price_history
       |     -> listings collection
       |
       +-- new doc
             -> insert w/ seller_type + coordinate_precision_m
             -> geocode_listing (exact / landmark)
             -> recompute distances     [NEW: on coord upgrade]
             -> listings collection

listings collection
  -> monthly aggregation job            [NEW]
  -> district_snapshots collection      [NEW]
  -> Dashboard: district drift charts
```

## 1. Dedup + relist-cycle tracking

**Approach chosen (of 3 considered):** replace the title-based fingerprint with a *content fingerprint* built from stable physical attributes, reusing the pattern already proven in the co-op vertical (`content_fingerprint_xsrc`).

| Option | Trade-off |
|---|---|
| A. Keep title-based, per-source (status quo) | Simple, but breaks on title edits; can't merge cross-source dupes. Rejected. |
| **B. Coordinate+area+rooms+bezirk fingerprint, cross-source (recommended)** | Stable across title edits and across Willhaben/ImmoKurier/DerStandard for the same unit. Needs coordinate rounding (~30m) to avoid two ads for the same flat differing by geocoding jitter. |
| C. ML/fuzzy text similarity dedup | Higher recall on partial data, but nondeterministic, needs tuning + review queue. Overkill for current scale. Rejected — revisit if B's false-negative rate is high in practice. |

### Module: content_fingerprint_xsrc (extended)

- **Responsibility:** stable id for "same physical unit" across sources and across title edits.
- **Interface:** input listing dict → output md5 string. Inputs: `round(lat,3), round(lon,3)` if coords available, else `bezirk+street`; `area_m2` rounded to nearest 1m²; `rooms`; district.
- **Dependencies:** `Application/helpers/listing_validator.py` (extends existing coop fingerprint fn to all verticals).
- **Size target:** ~30 lines, pure function, unit-testable.

### Module: record_relist_event

- **Responsibility:** when an incoming listing's fingerprint matches an existing doc with `listing_status="taken"`, log the delist→republish cycle instead of silently flipping status back to active.
- **Interface:** called from `upsert_listing_with_history` before the existing-doc branch. Appends to `relist_events: [{delisted_at, republished_at, days_off_market, price_at_relist}]`, increments `times_relisted`, resets `listing_status="active"`.
- **Dependencies:** `mongodb_handler.py` only.
- **Size target:** ~20 lines, added inline to existing upsert method.

**Cross-source merge display:** documents stay separate (one per source, needed for per-source price/outreach tracking) but share `unit_fingerprint`. Dashboard/top-5 queries dedupe by picking one canonical doc per `unit_fingerprint` (most-complete-data wins, tie-break on earliest `first_scraped_at` — see Resolved decisions).

## 2. Private-seller + precise geo

### Module: seller_type classification (moved earlier in pipeline)

- **Responsibility:** classify each listing private / agency / bautraeger at scrape time, not just at outreach time.
- **Interface:** reuse existing `contact_extractor.py` regex logic (agency/makler class detection), called from each scraper's parse step, written to new `Listing.seller_type` field.
- **Dependencies:** `Application/outreach/contact_extractor.py` (logic extracted/shared, not duplicated).
- **Size target:** extend contact_extractor with a lightweight classify_seller() helper (~15 lines), call from each scraper.

### Module: coordinate_precision_m + distance recompute trigger

- **Responsibility:** attach a numeric confidence radius to every coordinate, and re-trigger school/U-Bahn distance calc when precision improves.
- **Interface:** `coordinate_source="exact"` → ~10m; `"landmark"` → ~200m (street/district centroid); `"none"` → null. `main.py`'s geocode step (line ~508) already checks `coordinate_source != 'none'` before updating coords — extend that branch to also re-run `get_walking_distance_to_nearest_school` / U-Bahn calc when precision tightens.
- **Dependencies:** `Application/helpers/geocoding.py`, `Application/main.py`.
- **Size target:** ~15 lines added to existing geocode branch.

**Geo strategy:** best-effort only — no new detail-page scraping. Use Willhaben's own exact coords when present; Nominatim-geocode the coarse address text otherwise. This means private-seller listings on sources that only expose a district-level address will stay at "landmark" precision (~200m) — good enough for U-Bahn/school walk-time bucket, not exact-address precision. This is a hard ceiling, not a bug to chase.

## 3. Richer data capture (standardize across sources)

Audit finding: several fields (`doppelmakler`, `maklerprovision_pct`, `sonderumlage_risk`) are extracted via source-agnostic regex in `field_extractors.py` but only *called* from Willhaben/DerStandard/ImmoKurier scrapers inconsistently.

Fix: audit call sites, wire missing extractor calls into whichever scraper omits them. No new fields needed — this is a coverage-consistency fix, not new schema. ("Gather more data" scoped to closing this coverage gap plus the seller_type/precision fields above, not inventing speculative new fields like floor plan images or virtual tour links — that would be a separate future sub-project.)

## 4. Historical / district drift analytics

### Module: district_snapshots aggregation job

- **Responsibility:** monthly rollup of price/m², listing volume, days-on-market by `bezirk`, written to a new collection so district comparisons don't require scanning the full listings collection.
- **Interface:** cron/script reads `listings` filtered by `processed_at` in month window + `price_history`, writes one doc per (bezirk, month): `{bezirk, period, avg_price_m2, median_price_m2, listing_count, active_count, avg_days_on_market, relisted_pct}`.
- **Dependencies:** `mongodb_handler.py` (new `district_snapshots` collection), run via existing pipeline scheduler pattern (cron / GitHub Actions, matching `coop-fast-poll` precedent).
- **Size target:** ~120 lines, new file `Application/analytics/district_snapshot.py`.

**Flag — retroactive 10-year history is not possible from this DB alone.** The scraper has only been running since this project started; there's no 2016 data sitting in Mongo. Resolved: backfill from an external open-data source is in scope as sub-project 5 below, rather than starting snapshots flat from today.

## Schema diff summary

```
Listing (new/changed fields):
  unit_fingerprint: str            # replaces per-source content_fingerprint for cross-source dedup
  relist_events: List[Dict]        # [{delisted_at, republished_at, days_off_market, price_at_relist}]
  times_relisted: int
  seller_type: str                 # 'private' | 'agency' | 'bautraeger' | 'unknown'
  coordinate_precision_m: int      # 10 | 200 | null

New collection: district_snapshots
  {bezirk, period, avg_price_m2, median_price_m2, listing_count,
   active_count, avg_days_on_market, relisted_pct, source}
```

## 5. External historical backfill (Statistik Austria / Immobilienpreisspiegel)

### Module: district_snapshot_backfill (one-time import)

- **Responsibility:** populate `district_snapshots` with pre-scraper years (aim: back to ~2016) from an external open-data source so district drift charts have a real 10-year baseline instead of starting flat from today.
- **Interface:** one-off script, not part of the daily pipeline. Writes docs tagged `source="external_backfill"` (vs. `source="scraped"` for the ongoing monthly job) into the same collection/shape — dashboard queries merge both by `(bezirk, period)`, scraped data takes precedence where both exist for the same month.
- **Dependencies:** external API/CSV from Statistik Austria (Immobilienpreisspiegel, published by WKO/Statistik Austria — free, publicly licensed aggregate data, no scraping ToS concern since it's an official open-data publication, not a listings site).
- **Size target:** ~150 lines, new file `Application/analytics/district_snapshot_backfill.py`. Run once manually, not on a schedule.

**Granularity ceiling (unresolved detail):** external source publishes at Bezirk (23-district) level, typically yearly or semi-annual — not monthly like the scraped snapshots. Expect a granularity seam where backfilled rows are sparser (1-2 points/year) than scraped rows (12 points/year) once live. Chart should show this honestly (e.g. dashed line pre-2026, solid after) rather than interpolating fake monthly points. Exact data shape/API from Statistik Austria has not been verified yet (no WebFetch done — host not on sandbox allowlist); confirm shape before implementing sub-project 5's import script.

## Resolved decisions

| Question | Decision |
|---|---|
| Canonical doc for cross-source duplicates | Most-complete-data wins (most non-null fields). Tie-break on equal completeness: earliest `first_scraped_at`. |
| Relist-cycle window | No time limit — any fingerprint match after `taken_at` counts as a relist. Gap length is preserved in `relist_events[].days_off_market` for later filtering, not discarded at write time. |
| 10-year backfill | In scope — sub-project 5 above. |
| Richer data capture | Coverage-consistency fix only, no new fields. |

## Key files

`Project/Integration/mongodb_handler.py`, `Project/Domain/listing.py`, `Project/Application/helpers/listing_validator.py`, `Project/Application/helpers/geocoding.py`, `Project/Application/outreach/contact_extractor.py`, `Project/Application/main.py`.
