---
title: Data Platform — Dedup, Precise Geo, Richer Capture, Historical Analytics
date: 2026-08-16
status: approved
ui_scope: false
graph_scope: false
test_scope: true
---

# Data Platform Design

5 sub-projects, one coherent data model. Corrected after tracing the real write path in
`Application/main.py` — the original draft targeted `mongodb_handler.upsert_listing_with_history`,
which is dead code (zero callers). All fixes below target the actual production path.

## 0. Baseline (verified against code)

| Capability | Exists today | Gap |
|---|---|---|
| Price history | `price_history[]` field defined, read by 4 dashboard routes | **Never written.** `upsert_listing_with_history` (the only writer) has 0 callers. Field is always empty in practice. |
| Dedup, non-co-op | `content_fingerprint` = md5(title+area+rooms+bezirk+source) | Title-based → breaks on ad-text edits. Per-source only (Willhaben+ImmoKurier dupes of the same unit both stored). |
| Dedup, co-op | `content_fingerprint_xsrc` = cross-source, already stable (`compute_xsrc_fingerprint`) | Proven pattern — not yet reused for non-co-op listings. |
| Listing lifecycle | `listing_status`/`taken_at` set by `mark_listing_taken` (`cleanup.py`, real caller, confirmed live) | Real write path (`main.py:490-521`) has 3 branches and none of them intentionally restore `listing_status`: `existing_by_url` → `replace_one` with a dict that has no `listing_status` key, silently **dropping** the field (not explicitly setting 'active'); `existing_by_fingerprint` → skip entirely, no update at all. |
| Coordinates | `coordinate_source`: exact / landmark / none. Willhaben ships exact; others geocode via Nominatim | No confidence radius stored; distance calcs not recomputed if coords later upgrade landmark→exact. |
| Seller type | `contact_extractor.py` parses agency/makler class regex, used only for outreach | Not written back to the listing doc — can't query "private sellers" in Mongo/dashboard. |
| District/time rollups | None | No collection aggregates price/m² or volume by district over time. |

## 1. Real write path (`Application/main.py:485-521`)

```
listing_dict built → fingerprint = compute_content_fingerprint(...)
├─ is_genossenschaft:  xsrc-fingerprint dedup, skip on match (own branch, unaffected by this spec)
├─ existing_by_url:    collection.replace_one(_id=existing._id, listing_dict)
│                      → full replace; listing_status/taken_at/price_history NOT in listing_dict → dropped
├─ existing_by_fingerprint (different url, same content):
│                      → duplicate_count++, skip; only backfills coordinates if missing
└─ else:               collection.insert_one(listing_dict)
```

## 2. Dedup + relist-cycle tracking

**Chosen approach** (of 3 considered — title-based status quo rejected for fragility, ML/fuzzy dedup
rejected as overkill for current scale): extend the co-op vertical's proven cross-source fingerprint
pattern (`compute_xsrc_fingerprint`) to all listing types, and fix the two non-co-op branches in
`main.py` to actually update instead of blind-replace / silent-skip.

### Module: `compute_content_fingerprint` v2 (extend, `Application/helpers/listing_validator.py`)
- **Responsibility:** stable id for "same physical unit" across sources and across ad-text edits.
- **Interface:** input listing dict → md5 string. Key = `round(lat,3),round(lon,3)` if coords available, else `bezirk+street`; `area_m2` rounded to nearest whole m²; `rooms`; district. Falls back to old title-based key only when address AND coords are both absent (documented degraded case, not silently wrong).
- **Dependencies:** none beyond stdlib `hashlib`.
- **Size target:** ~30 lines, pure function, unit-tested against the existing `compute_xsrc_fingerprint` test cases as a shape reference.

### Module: `handle_fingerprint_match` (new, `Integration/mongodb_handler.py`)
- **Responsibility:** replace the current bare `continue` (skip, no-op) in `main.py`'s `existing_by_fingerprint` branch with an actual update: always push a `price_history` entry on price change; additionally log a relist cycle when the matched doc was `taken`.
- **Interface:** `handle_fingerprint_match(existing_doc, incoming_listing_dict) -> None`. Price change (any status): append `{price_total, recorded_at}` to `price_history`. If `existing_doc["listing_status"] == "taken"`: also append to `relist_events: [{delisted_at, republished_at, days_off_market, price_at_relist}]`, increment `times_relisted`, set `listing_status="active"`, `taken_at=None`. If already `active`: relist fields untouched.
- **Dependencies:** `Integration/mongodb_handler.py` only.
- **Size target:** ~25 lines.

### Module: `existing_by_url` price-history fix (`main.py:492-495`)
- **Responsibility:** stop `replace_one` from silently dropping `listing_status`/`taken_at`/`price_history` and from skipping price-change tracking.
- **Interface:** before `replace_one`, merge forward: `listing_dict['listing_status'] = existing_by_url.get('listing_status', 'active')`, `listing_dict['taken_at'] = existing_by_url.get('taken_at')`; if `price_total` changed, push old price into `listing_dict['price_history']` (seeded from `existing_by_url.get('price_history', [])`).
- **Dependencies:** none new.
- **Size target:** ~15 lines added inline.

**Cross-source merge display:** documents stay separate per source (needed for per-source price/outreach tracking) but share `unit_fingerprint`. Dashboard/top-5 queries pick one canonical doc per `unit_fingerprint`: most non-null fields wins; tie-break on earliest `first_scraped_at`.

**Relist window:** no time limit — any fingerprint match after `taken_at` counts as a relist. Gap length preserved in `relist_events[].days_off_market`, not discarded at write time.

## 3. Private-seller + precise geo

### Module: `seller_type` classification (moved earlier in pipeline)
- **Responsibility:** classify private / agency / bautraeger at scrape time, not just at outreach time.
- **Interface:** reuse `contact_extractor.py`'s existing agency/makler regex, extracted into `classify_seller(text) -> str`, called from each scraper's parse step, written to new `Listing.seller_type` field.
- **Dependencies:** `Application/outreach/contact_extractor.py` (logic shared, not duplicated).
- **Size target:** ~15 lines new helper + one call site per scraper.

### Module: `coordinate_precision_m` + distance recompute trigger
- **Responsibility:** attach a numeric confidence radius to every coordinate; re-trigger school/U-Bahn distance calc when precision improves.
- **Interface:** `coordinate_source="exact"` → ~10m; `"landmark"` → ~200m; `"none"` → null. Extend `main.py`'s geocode branch (the `geocoded.get('coordinate_source') != 'none'` checks at lines ~508/519) to also re-run `get_walking_distance_to_nearest_school`/U-Bahn calc when precision tightens from a prior scrape.
- **Dependencies:** `Application/helpers/geocoding.py`, `Application/main.py`.
- **Size target:** ~15 lines added to existing geocode branch.

**Geo strategy:** best-effort only, no new detail-page scraping. Willhaben's own exact coords when present; Nominatim-geocode the coarse address text otherwise. Distance-sensitive logic (school/U-Bahn walk time) reads only `coordinate_source="exact"` rows — landmark-precision listings are captured and stored, just excluded from that specific calculation, per your answer. This is a hard ceiling for sources that only expose district-level addresses, not a bug to chase.

## 4. Richer data capture (coverage-consistency fix)

Audit: `doppelmakler`, `maklerprovision_pct`, `sonderumlage_risk` are extracted via source-agnostic
regex in `field_extractors.py` but called inconsistently across scrapers. Fix: audit call sites, wire
missing extractor calls into whichever scraper omits them. No new fields — this is a coverage gap, not
new schema. (If genuinely new data points are wanted later — floor plans, virtual tours — that's a
separate sub-project, not scoped here.)

## 5. Historical / district drift analytics

### Module: `district_snapshots` aggregation job (new, `Application/analytics/district_snapshot.py`)
- **Responsibility:** monthly rollup of price/m², listing volume, days-on-market by `bezirk`.
- **Interface:** script reads `listings` filtered by `processed_at` in month window + `price_history`, writes one doc per (bezirk, month): `{bezirk, period, avg_price_m2, median_price_m2, listing_count, active_count, avg_days_on_market, relisted_pct, source}`.
- **Dependencies:** `mongodb_handler.py` (new `district_snapshots` collection), scheduled via the existing cron pattern (matches `coop-fast-poll` precedent).
- **Size target:** ~120 lines.

### Module: `district_snapshot_backfill` (new, one-time import, `Application/analytics/district_snapshot_backfill.py`)
- **Responsibility:** populate `district_snapshots` with pre-scraper years (target: back to ~2016) from Statistik Austria's Immobilienpreisspiegel (official open aggregate data — no ToS concern, not a listings site) so district drift charts have a real multi-year baseline instead of starting flat from today.
- **Interface:** writes docs tagged `source="external_backfill"` vs `source="scraped"` for the ongoing job, same shape, same collection. Dashboard merges both by `(bezirk, period)`, scraped data wins where both exist.
- **Dependencies:** external API/CSV from Statistik Austria.
- **Size target:** ~150 lines. Run once manually, not on a schedule.
- **Granularity ceiling:** external source publishes yearly/semi-annual at Bezirk level, not monthly. Chart shows this honestly (e.g. dashed pre-2026, solid after) rather than interpolating fake monthly points.

## Schema diff summary

```
Listing (new/changed fields):
  unit_fingerprint: str            # replaces per-source content_fingerprint for cross-source dedup
  relist_events: List[Dict]        # [{delisted_at, republished_at, days_off_market, price_at_relist}]
  times_relisted: int
  seller_type: str                 # 'private' | 'agency' | 'bautraeger' | 'unknown'
  coordinate_precision_m: int      # 10 | 200 | null
  price_history: List[Dict]        # now actually populated (was dead field)

New collection: district_snapshots
  {bezirk, period, avg_price_m2, median_price_m2, listing_count,
   active_count, avg_days_on_market, relisted_pct, source}
```

## Resolved decisions

| Question | Decision |
|---|---|
| Canonical doc for cross-source duplicates | Most non-null fields wins; tie-break on earliest `first_scraped_at`. |
| Relist-cycle window | No time limit; gap length preserved in `relist_events[].days_off_market`. |
| 10-year backfill | In scope — sub-project 5. |
| Richer data capture | Coverage-consistency fix only, no new fields. |
| Integration point for dedup/relist/price-history fixes | Corrected to the real write path (`main.py:485-521`), not the dead `upsert_listing_with_history` method. |
| Geo precision for distance logic | Exact-only; landmark-precision listings still captured/stored, just excluded from school/U-Bahn walk-time calcs. |
| Private-seller scope | General flag across all listing types, not just co-op. |

## Testing

- Unit tests for `compute_content_fingerprint` v2 (coord-based, title-edit-stable) and `classify_seller`, following existing `Tests/` patterns.
- Regression test for the `existing_by_url` branch: verify `listing_status`/`taken_at`/`price_history` survive a `replace_one` when the incoming scrape lacks those keys.
- Regression test for `record_listing_relist`: a fingerprint match against a `taken` doc must flip it back to `active` and append one `relist_events` entry.
