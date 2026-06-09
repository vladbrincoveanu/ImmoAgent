# Green Infrastructure / WieNeu+ Zones — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Scope:** v1 — 3 data files, map overlay, listing enrichment

## 1. Architecture

3 data assets (curated zones + scraped anergy + curated subsidy) + per-listing enrichment at scrape time + new map layers + ListingDetail panel.

```
Scraper run → green_infra_context.enrich(listing) →
  nearest_wieneu_zone (point-in-polygon or centroid distance)
  anergy_distance_m (haversine, EFH hidden)
  subsidy_eligible (zone_id + district match)
→ MongoDB → /api/listings → MapView GeoJSON layers → ListingDetail panel

Anergy scraper (separate cron, weekly) → refreshes anergy_network.geojson
```

## 2. Data Assets

### `Project/data/wieneu_zones.geojson` (curated, in repo)
- FeatureCollection of Polygon
- Properties: `zone_id`, `name`, `program` ('wieneu+'|'gratzi20+2'), `start_year`, `district` (1-23), `subsidy_program_id`
- v1 features:
  - Innerfavoriten (10. district, polygon)
  - Grätzl 20+2 (20. district, polygon)
- Source: Stadt Wien open data + research
- Stable IDs (`zone_innerfavoriten`, `zone_gratzi20plus2`)

### `Project/data/anergy_network.geojson` (scraped, in repo, refreshable)
- FeatureCollection of LineString (trunk pipes) + Point (substations)
- Properties: `network_id`, `type` ('anergy_low_temp'|'geothermal_deep'), `operator`, `online_year`
- v1: 2-3 known features (manual seed) — augmented by scraper

### `Project/data/subsidy_rules.json` (curated, in repo)
- Schema:
  ```json
  {
    "zone_innerfavoriten": {
      "program": "Grätzlförderung",
      "max_amount_eur": 20000,
      "eligible_measures": ["solar_pv", "solar_thermal", "geothermal", "cirular_economy"],
      "eligibility_conditions": {"ownership_required": true, "primary_residence": true}
    },
    "zone_gratzi20plus2": {...}
  }
  ```
- Source: wien.gv.at/grätzl-förderung, manual research

## 3. Module Design Blocks

### Module: `Project/Application/green_infra/context.py` (new)
- **Responsibility:** enrich a listing with nearest zone + anergy distance + subsidy eligibility
- **Interface:** `enrich(listing: Listing) -> Listing` (in-place mutation + return)
- **Steps:**
  1. Load `wieneu_zones.geojson` (cached at module init)
  2. Load `anergy_network.geojson` (cached at module init)
  3. Load `subsidy_rules.json` (cached at module init)
  4. `point_in_polygon(listing.lat, listing.lon, zone.geometry)` → if True, assign that zone; else nearest by haversine to centroid
  5. Skip anergy if `listing.property_type == 'EFH'` or `'HAUS'` → leave `anergy_distance_m=None`
  6. Else: haversine to nearest anergy LineString (sample vertices) or Point feature
  7. If zone_id present in subsidy_rules + district match → `subsidy_eligible=True`
- **Dependencies:** shapely (point-in-polygon fallback to ray-casting if missing), existing haversine
- **Size target:** <200 lines

### Module: `Project/Application/scraping/anergy_scraper.py` (new)
- **Responsibility:** refresh `anergy_network.geojson` from wien.gv.at WFS or fallback to manual seed
- **Interface:** `scrape() -> int` (count of features written)
- **Logic:** fetch → parse → write file. On error → log + leave file unchanged.
- **Schedule:** weekly cron (separate from main scraper)
- **Size target:** <150 lines
- **Dependencies:** `requests`, `json`

### Module: Listing model (extend `Project/Domain/listing.py`)
- Add fields:
  ```python
  nearest_wieneu_zone: str | None = None        # zone_id
  anergy_distance_m: int | None = None          # meters
  subsidy_eligible: bool | None = None          # True/False/None
  ```
- All nullable, non-breaking

### Module: Scraper integration (extend 3 scrapers)
- After `extract_listing()`, call `green_infra_context.enrich(listing)` before Mongo write
- +3 lines per scraper

### Module: API types (`dashboard/lib/types.ts`)
- Add to `MapListing`: `nearest_wieneu_zone: string | null; anergy_distance_m: number | null; subsidy_eligible: boolean | null`
- Add to `ListingDetail`: same + `subsidy_program_id: string | null; eligible_measures: string[]`

### Module: API routes (extend)
- `/api/listings/route.ts`: add filter param `?in_wieneu_zone=true` (filters `nearest_wieneu_zone != null`)
- `/api/listings/[id]/route.ts`: include new fields

### Module: MapView layer (`dashboard/components/MapView.tsx`)
- New: Leaflet `<GeoJSON>` layer for wieneu zones — polygons with `fillColor: '#16a34a'`, `fillOpacity: 0.15`, `color: '#16a34a'`, `weight: 2`
- New: anergy network layer — `LineString` → polyline color `#0ea5e9`; `Point` → CircleMarker radius 6
- z-order: anergy (bottom) → zones (middle) → pins (top)
- Toggle UI: 2 new checkboxes in MapLegend
- Size target: +80 lines

### Module: MapLegend (extend)
- Add: "WieNeu+ zones" checkbox (default on) + "Anergy network" checkbox (default off)
- Size target: +30 lines

### Module: ListingDetail panel (extend)
- New section: "Green infrastructure" (after location/distance)
- Contents:
  - Zone badge: e.g. "Innerfavoriten (WieNeu+)" or "Not in renewal zone"
  - Anergy distance: e.g. "120m to nearest anergy line" (only if Wohnung)
  - Subsidy eligibility: ✓ icon + "Eligible for Grätzlförderung (€X,XXX max)" + bulleted eligible_measures
- Size target: +50 lines

### Module: FilterBar / FilterDrawer (extend)
- New chip: "WieNeu+ zone" — single-select, URL param `?in_wieneu_zone=true`
- Size target: +15 lines per file

## 4. Data Flow

1. **Anergy scraper** runs weekly (cron) → updates `anergy_network.geojson`
2. **Main scraper** runs → extracts listing → calls `green_infra_context.enrich()` → writes enriched Mongo doc
3. **Dashboard load** → fetches `/api/listings` → MapView renders pins on top of zones + anergy (toggleable)
4. **User clicks zone checkbox** → toggle visibility (no API refetch, just Leaflet addLayer/removeLayer)
5. **User clicks WieNeu+ chip in FilterBar** → API refetch with `?in_wieneu_zone=true`
6. **User clicks listing in zone** → ListingDetail shows zone + distance + subsidy info

## 5. Error Handling

- Shapely not installed → fallback to ray-casting point-in-polygon (slower, no dep)
- GeoJSON malformed → log + skip enrichment for that listing
- Anergy scrape fails (timeout/5xx) → keep last good file, log
- Subsidy rules missing zone_id → `subsidy_eligible=False`
- Listing outside all zones + no anergy within 5km → both `None`
- EFH listing → `anergy_distance_m=None` (intentional skip, not error)
- Lat/lon missing → skip all enrichment, leave None

## 6. Testing

### Unit
- `green_infra_context.enrich()`: 12 cases
  - Inside Innerfavoriten polygon → zone assigned
  - Outside, nearest centroid → assigned with distance
  - EFH → anergy_distance_m stays None
  - Wohnung near anergy line → distance reasonable
  - Zone in subsidy_rules + district match → eligible=True
  - Zone in subsidy_rules + district mismatch → eligible=False
  - Zone not in subsidy_rules → eligible=False
  - Lat/lon missing → all None
  - Malformed GeoJSON → returns listing unchanged, no crash
- Anergy scraper: 3 cases (200/500/timeout) — file unchanged on failure
- Shapely vs ray-casting: 5 cases give same result

### API
- `/api/listings?in_wieneu_zone=true` returns only listings with `nearest_wieneu_zone != null`
- Listing detail includes new fields

### Playwright
- /dashboard/map → MapLegend shows "WieNeu+ zones" + "Anergy network" checkboxes
- Toggle zones → polygon visible (assertion: at least 1 polygon path in DOM)
- Toggle anergy → line/point features visible
- Click WieNeu+ chip → URL has `?in_wieneu_zone=true`, pin count drops
- Click listing in Innerfavoriten → ListingDetail shows zone badge

### Manual
- Visual: Innerfavoriten polygon overlays 10. district on map
- Pick 3 listings near known anergy line → distance in expected range
- 1 in-zone + 1 out-of-zone listing → subsidy eligibility correct

## 7. Out of Scope (v1)

- Live scrape fallback (manual refresh only on failure)
- Historical zone join dates
- Solar/geothermal install cost estimate
- "Apply for Grätzlförderung" CTA / form
- Carbon savings calculator
- Per-network operator comparison
- Anergy subscription pricing data

## 8. Migration & Rollout

- Branch: `relentless/green-infrastructure-wieneu`
- Commits:
  1. `data: add wieneu_zones.geojson + subsidy_rules.json (curated)`
  2. `feat(green_infra): enrich module with zone + anergy + subsidy`
  3. `feat(scrapers): anergy scraper with weekly refresh`
  4. `feat(scrapers): wire green_infra enrich into 3 main scrapers`
  5. `feat(api): expose green_infra fields + filter param`
  6. `feat(map): WieNeu+ zones GeoJSON layer + anergy network layer`
  7. `feat(ui): MapLegend checkboxes for zones + anergy`
  8. `feat(detail): green infrastructure section in ListingDetail`
  9. `feat(filters): WieNeu+ zone chip in FilterBar/FilterDrawer`
  10. `test: enrich unit + anergy scraper + playwright map layer`
- No feature flag

## 9. Known Risks

- **Polygon accuracy:** hand-curated polygons may differ from official boundaries. Verify with Wien Stadt GIS before claiming regulatory status.
- **Anergy data freshness:** scraper may break on wien.gv.at WFS schema changes. Quarterly manual review.
- **Subsidy rule staleness:** Grätzlförderung amounts change yearly. Annual manual refresh.
- **EFH vs Wohnung detection:** scraper property_type field may be inconsistent. EFH filter is regex-based — false negatives possible.

## 10. Login Drop (separate follow-up)

User requested: drop dashboard auth entirely. This is a follow-up task, not in this spec. Will be addressed after all 5-idea brainstorm specs complete.
