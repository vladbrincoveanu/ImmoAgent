# Rent-Regulated Map Layer — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Scope:** v1 layer toggle + scrape-time enrichment for MRG/WGG status

## 1. Architecture

Add rent-regulatory status to listings at scrape time, expose via API, render pins with edge-color override, add MapLegend 3-state filter.

```
Scraper extract → detector (regex) → fallback classifier (age+bezirk)
  → listing.rent_regulated: bool|None
  → listing.rent_regulated_source: 'regex'|'inferred'|None
  → MongoDB → /api/listings → MapView pin render
  → MapLegend 3-state filter (All | Regulated | Free)
```

## 2. Data Model

### Listing (extend `Project/Domain/listing.py`)

```python
rent_regulated: bool | None = None
rent_regulated_source: Literal['regex', 'inferred'] | None = None
```

Both nullable. `None` = unknown (no inference possible). Non-breaking.

## 3. Module Design Blocks

### Module: `Project/Application/regulatory/detector.py` (new)
- **Responsibility:** regex match German listing text for MRG/WGG/freifinanziert markers
- **Interface:** `detect(text: str) -> Literal['regex'] | None` ; `extract_bool(text: str) -> bool | None`
- **Patterns:** MRG, WGG, "Mietzinsbildung gemäß", "gefördert", "freifinanziert", "Preis nach MRG", "Wohnbauförderung", "§45 MRG", "Richtwert"
- **Pos markers** (regulated): `MRG`, `WGG`, `Mietzinsbildung`, `gefördert`, `Wohnbauförderung`, `Richtwert`, `§45`, `§16 MRG`
- **Neg markers** (free): `freifinanziert`, `Neubau freifinanziert`, `kein MRG`, `ausgenommen MRG`
- **Conflict:** neg wins (conservative — claim free only when explicit)
- **Dependencies:** `re` stdlib only
- **Size target:** <120 lines

### Module: `Project/Application/regulatory/classifier.py` (new)
- **Responsibility:** infer regulated status from year_built + bezirk when regex absent
- **Interface:** `classify(year_built: int|None, bezirk: str|None) -> Literal['inferred'] | None`
- **Logic:** if `year_built` and `year_built < 1945` and `bezirk` and `int(bezirk) in range(1, 10)` → return `'inferred'`; else `None`
- **Note:** returns source tag only, not bool — caller interprets inferred as `True` (default conservative)
- **Dependencies:** none
- **Size target:** <60 lines

### Module: Scraper hook (extend 3 scrapers)
- **Responsibility:** enrich extracted listing with regulatory status post-extract
- **Files:** `Project/Application/scraping/willhaben_scraper.py`, `immokurier_scraper.py`, `derstandard_scraper.py`
- **Behavior:** concat title+description+features → call `detector.detect()`. If match → set `rent_regulated=extract_bool()`, `source='regex'`. Else → call `classifier.classify(year_built, bezirk)`. If `'inferred'` → set `rent_regulated=True`, `source='inferred'`. Else → leave `None, None`.
- **Size target:** +15 lines per scraper

### Module: API types (`dashboard/lib/types.ts`)
- **Add to `MapListing`:** `rent_regulated: boolean | null; rent_regulated_source: 'regex' | 'inferred' | null`
- **Add to `ListingDetail`:** same fields
- **Add filter param:** `?rent_regulated=true|false` (omitted = all)

### Module: API routes
- `/api/listings/route.ts`: extend Mongo query to accept `rent_regulated` filter
- `/api/listings/[id]/route.ts`: include new fields in response
- `ListingContext` (in `/api/listings/[id]/context/route.ts` if exists, else new): include fields

### Module: MapView pin rendering (`dashboard/components/MapView.tsx`)
- **Add CSS class** `pin-regulated` in `MapView.tsx` style or globals.css:
  - Default pin → no change
  - `rent_regulated === true` → 3px solid `#16a34a` (green) ring around pin
  - `rent_regulated === false` → no change
  - `rent_regulated === null` → no change (no false signal)
- Apply via class on existing `<div className="pin ...">` element
- Size target: +20 lines

### Module: MapLegend (`dashboard/components/MapLegend.tsx` extend)
- **Current:** single chip/dropdown (842B)
- **Add:** 3-state segmented control — `All | Regulated | Free`
- **Behavior:** click sets `?rent_regulated=true|false` in URL, refetches
- **Disclaimers** below toggle: italic small text "Status = scraping + age/district proxy. Verify with landlord before commitment."
- **Size target:** +60 lines (still under 200 total)

### Module: ListingDetail panel (`dashboard/components/ListingDetail.tsx` extend)
- **Add row** in detail metadata: "Rent status" with icon
  - Regulated → green check + "Regulated" + source badge (regex/inferred)
  - Free → gray "Free-market" + source badge
  - Unknown → gray "Unknown"
- **Footnote** for inferred: "Based on building year + district. Verify status before relying on it."
- Size target: +25 lines

### Module: FilterBar / FilterDrawer (extend existing)
- New chip in `FilterBar.tsx` and `FilterDrawer.tsx`: "Regulated" / "Free" / "All" (single-select, mutually exclusive)
- Persist to URL params
- Size target: +20 lines per file

## 4. Data Flow

1. Scraper extracts listing text. `extract_listing()` calls `detector.detect(text)`.
2. If `'regex'`: set `rent_regulated` from `extract_bool()`, `source='regex'`.
3. Else: `classifier.classify(year_built, bezirk)`. If `'inferred'`: set `True, 'inferred'`.
4. Else: leave `None, None`.
5. MongoDB write includes new fields.
6. `/api/listings` reads, includes in MapListing response.
7. MapView reads `rent_regulated`, applies CSS class.
8. User clicks Regulated filter in MapLegend → URL `?rent_regulated=true` → API filters `rent_regulated: true` → re-render.
9. **Unknown handling (per user):** listings with `rent_regulated=null` are HIDDEN under both Regulated and Free filters. Shown only under All.

## 5. Error Handling

- Detector regex compile error → log warning, return None → classifier kicks in
- Year/bezirk both None → regulated stays None → pin uncolored
- API filter param invalid (`?rent_regulated=foo`) → return all (lenient)
- Mongo write missing field → safe (nullable, default None)
- Scraper pre-existing: year_built may be string in some scrapers — cast `int()` with try/except, fall through to None

## 6. Testing

### Unit (extend `Tests/test_regulatory.py` new file)
- Detector: 20+ fixtures covering MRG/WGG/gefördert/freifinanziert/Richtwert/§45, plus 5 negative cases (no markers), plus 3 conflict cases (neg wins)
- Classifier: 10 matrix cases — pre/post 1945 × in/out 1-9, plus None year, None bezirk
- Conflict resolution: 3 cases where neg + pos present

### API (extend `dashboard/tests/api/`)
- `/api/listings?rent_regulated=true` returns only true
- `/api/listings?rent_regulated=false` returns only false (no nulls)
- `/api/listings` (no param) returns all incl. null

### Playwright (extend `dashboard/tests/smoke.spec.ts`)
- /dashboard/map → MapLegend shows 3-state toggle
- Click "Regulated" → URL has `?rent_regulated=true`, pin count drops
- Click "Free" → URL has `?rent_regulated=false`, different pins
- Click "All" → URL has no param, all pins back
- Regulated pins have green ring (check via `getComputedStyle`)

### Manual
- Open 5 known-regulated listings (WGG) and verify green ring renders
- Open 5 known-free listings (Neubau freifinanziert) and verify no ring
- 5 unknown listings → no ring, hidden under both filters

## 7. Out of Scope (v1 defer)

- Per-cap % breakdown (1% vs 4% vs index-linked)
- Historical rent trajectory per property
- "Apply for cap eligibility" CTA
- Conflict resolution UI when both markers present (silent neg-wins for v1)
- Bulk re-classification of historical listings (only new scrapes get classified)

## 8. Migration & Rollout

- Branch: `relentless/rent-regulated-layer`
- Commits:
  1. `feat(domain): add rent_regulated fields to Listing`
  2. `feat(regulatory): detector + classifier modules`
  3. `feat(scrapers): enrich 3 scrapers with regulatory status`
  4. `feat(api): expose rent_regulated in /api/listings + filter param`
  5. `feat(map): pin CSS class for regulated listings`
  6. `feat(ui): MapLegend 3-state toggle + FilterBar chip`
  7. `feat(detail): ListingDetail rent status row`
  8. `test: detector fixtures + classifier matrix + playwright`
- No feature flag (internal tool)
- Rollback: per-commit revert safe; no destructive schema change

## 9. Known Risks

- **Classifier false positives:** pre-1945 + 1-9 bezirk ≈ MRG, but some buildings exempt (Denkmalschutz carve-outs, post-renovation Neubau within 1-9). Disclaimer mitigates; not loading-bearing for any decision.
- **Willhaben listing text variability:** some listings omit regulatory disclosure entirely → unknown status → hidden under filters → 30-50% listings may not appear in filtered view initially.
- **No official data source:** status is scraper-derived, not authoritative. UI must reflect this (disclaimers + source badge).
