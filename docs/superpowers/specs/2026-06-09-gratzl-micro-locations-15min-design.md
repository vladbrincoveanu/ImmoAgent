# Grätzl Micro-Locations + 15-Minute City — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Scope:** v1 — Grätzl polygons overlay + 15-min circle radius tool

## 1. Architecture

Curated Grätzl GeoJSON + new amenity data (healthcare + daily amenities curated from OSM) + 15-min tool = circle around listing + amenity pins + summary count.

```
Listing click → 15-min tool activated
  → 1.2km circle rendered on map
  → amenity points queried (transit, schools, healthcare, daily)
  → counts per category returned
  → summary card shown
```

## 2. Data Assets

### `Project/data/wien_gratzl.geojson` (curated, new)
- FeatureCollection of Polygon (~130 features)
- Properties: `gratzl_id`, `name`, `bezirk` (1-23), `bezirk_name`, `population_density`, `area_km2`
- v1: ~30-50 most relevant Grätzl in 1.-13. Bezirk (where most listings are)
- Source: Stadt Wien, Bezirksvorstehungen, Wikipedia, manual research
- Stable IDs (`gratzl_innerfavoriten`, `gratzl_brigittenau_20+2`)

### `Project/data/healthcare.geojson` (curated, new)
- FeatureCollection of Point
- Properties: `facility_id`, `type` ('hospital'|'clinic'|'pharmacy'|'gp'), `name`, `address`, `opening_hours`
- v1: ~100 facilities (all Vienna hospitals + chain pharmacies)
- Source: OpenStreetMap via manual extraction, wien.gv.at

### `Project/data/daily_amenities.geojson` (curated, new)
- FeatureCollection of Point
- Properties: `amenity_id`, `type` ('supermarket'|'bakery'|'pharmacy'|'bank'|'post'), `name`, `chain`
- v1: chains only (Billa, Spar, Hofer, Merkur, dm, Bipa, banks, post) — ~300 points
- Source: OpenStreetMap via manual extraction, chain store locators

## 3. Module Design Blocks

### Module: `Project/data_loader.py` (extend `Project/Application/location.py` or new)
- **Responsibility:** load + cache all GeoJSON files at module init
- **Interface:** `get_gratzl()`, `get_healthcare()`, `get_daily_amenities()`, `get_existing_ubahn()`, `get_existing_schools()`
- All return list of dict features
- Cache invalidation: file mtime check
- Size target: +50 lines

### Module: `Project/Application/micro_location/gratzl_classifier.py` (new)
- **Responsibility:** point-in-polygon → Grätzl assignment
- **Interface:** `assign(lat, lon) -> str | None` (gratzl_id or None)
- Implementation: shapely contains, fallback to ray-casting
- Caches Grätzl polygons
- Size target: <80 lines

### Module: `Project/Application/micro_location/fifteen_min.py` (new)
- **Responsibility:** count amenities within 1.2km radius of a point
- **Interface:** `summarize(lat, lon) -> dict` returning:
  ```python
  {
    'transit_count': int,      # from ubahn_coordinates.json
    'schools_count': int,      # from vienna_schools.json
    'healthcare_count': int,   # from healthcare.geojson
    'daily_amenities_count': int,  # from daily_amenities.geojson
    'total_count': int,
    'amenities_in_radius': [
      {'type': 'transit', 'name': 'U1 Schwedenplatz', 'distance_m': 234},
      ...
    ]  # top 10 closest across categories
  }
  ```
- Implementation: haversine filter on each feature collection, sort by distance
- Size target: <150 lines

### Module: Listing model (extend)
- Add: `gratzl_id: str | None = None` (point-in-polygon assignment at enrich time)

### Module: `green_infra`/enrich (extend) — actually new `micro_location` enrich
- New: `Project/Application/micro_location/enrich.py`
- `enrich(listing) -> listing` — calls gratzl_classifier.assign, sets `listing.gratzl_id`

### Module: Scraper integration
- After green_infra enrich, call micro_location enrich → +3 lines per scraper

### Module: API types
- Add to `MapListing`: `gratzl_id: string | null`
- Add to `ListingDetail`: `gratzl_id`, `gratzl_name` (resolved from geojson)
- New endpoint: `GET /api/listings/[id]/fifteen-min` → returns `fifteen_min.summarize()` result

### Module: MapView Grätzl layer
- New Leaflet `<GeoJSON>` layer for wien_gratzl.geojson
- Style: `fillColor: '#94a3b8'`, `fillOpacity: 0.05`, `color: '#64748b'`, `weight: 1`, `dashArray: '4 4'`
- Toggle in MapLegend: "Grätzl boundaries" checkbox
- z-order: below zones, above base map
- Size target: +40 lines

### Module: 15-min tool UI
- **Trigger:** click on listing in MapView
- **Render:** 
  - 1.2km circle (semi-transparent blue fill, solid stroke) around selected listing
  - Amenity pins rendered with category-specific icons (transit = blue, schools = yellow, healthcare = red, daily = green)
  - Existing listing pin stays prominent
- **Summary card:** opens as side panel or in ListingDetail, shows counts + top 10 closest amenities with walking-distance estimate
- Size target: +100 lines

### Module: ListingDetail 15-min section
- New section: "15-minute walk"
- Display: 4 category counts (transit / schools / healthcare / daily) + "X total amenities within 1.2km"
- Click to expand: list of 10 closest with type icon + name + distance
- Size target: +60 lines

### Module: FilterBar / FilterDrawer (extend)
- New chip: "In Grätzl [name]" — opens dropdown of Grätzl names (from geojson), single-select
- URL param: `?gratzl_id=...`
- Size target: +25 lines per file

## 4. Data Flow

1. Scraper run → enrich with `gratzl_id` (point-in-polygon)
2. Dashboard load → /api/listings includes gratzl_id
3. MapView renders Grätzl polygons (toggleable)
4. User clicks listing → triggers 15-min tool:
   - API call: `/api/listings/[id]/fifteen-min`
   - Returns summary dict
   - Map renders circle + amenity pins
   - ListingDetail shows summary section
5. User clicks "In Grätzl" filter → URL `?gratzl_id=...` → API filters

## 5. Error Handling

- Grätzl point-in-polygon fails → `gratzl_id=None`
- Amenity file missing → category count = 0 (other categories still work)
- All 4 amenity files missing → tool shows "No data available"
- API `/fifteen-min` slow (>500ms) → render circle immediately, lazy-load amenities
- Lat/lon missing → tool disabled, shows "Location unavailable"
- 1.2km radius zero amenities → summary shows "0 amenities — rural area"

## 6. Testing

### Unit
- `gratzl_classifier.assign()`: 10 cases — inside/outside polygon, near boundary, lat/lon None
- `fifteen_min.summarize()`: 8 cases — listing at city center (high counts), rural area (low counts), edge of data, missing category
- Shapely vs ray-casting parity: 5 cases
- Haversine accuracy: 3 known distances verified

### API
- `/api/listings/[id]/fifteen-min`: returns valid summary for known listing, 404 for missing
- `/api/listings?gratzl_id=...` filters correctly

### Playwright
- /dashboard/map → MapLegend has "Grätzl boundaries" checkbox
- Toggle → polygons visible
- Click listing → circle appears, ListingDetail shows 15-min section
- Counts match expected ranges for known location

### Manual
- 3 listings in different Grätzl → verify name resolution
- Visual: Grätzl boundaries visible, click on one shows name in tooltip
- Pick 1 city-center listing (Wien Mitte) → expect transit > 5, schools > 3
- Pick 1 suburban listing → expect lower counts

## 7. Out of Scope (v1)

- True isochrone (network-aware) — user is researching, may add as opt-in v2
- Bike radius variant (5km circle variant)
- Time-of-day amenity availability (some closed evenings)
- Walkability score (combines density + diversity)
- Transit frequency integration (1min vs 10min wait)
- User-contributed amenity data

## 8. Migration & Rollout

- Branch: `relentless/gratzl-15min-city`
- Commits:
  1. `data: wien_gratzl.geojson (curated, ~30-50 features)`
  2. `data: healthcare.geojson + daily_amenities.geojson (curated)`
  3. `feat(micro_location): gratzl_classifier + fifteen_min modules`
  4. `feat(scrapers): wire micro_location enrich into 3 main scrapers`
  5. `feat(api): expose gratzl_id + /fifteen-min endpoint + filter param`
  6. `feat(map): Grätzl GeoJSON layer + 15-min circle rendering + amenity pins`
  7. `feat(ui): MapLegend Grätzl toggle + ListingDetail 15-min section`
  8. `feat(filters): Grätzl chip in FilterBar/FilterDrawer`
  9. `test: classifier + fifteen_min unit + playwright map`
- No feature flag

## 9. Known Risks

- **Grätzl boundary accuracy:** hand-curated polygons approximate. Wien Stadt publishes authoritative boundaries, but they require negotiation. v1 disclaimer in UI.
- **Amenity data staleness:** chains open/close locations. Quarterly manual review.
- **15-min circle misleading:** geometric circle counts "1.2km as crow flies" — actual walk may be 2km due to street network. UI must disclose.
- **Performance:** 4 amenity collections × haversine on every listing click. If >500ms, debounce + cache per listing_id.
- **User feedback pending:** user is researching isochrone vs circle. If user prefers isochrone after research, this spec is partial — circle layer stays, isochrone added as opt-in toggle.
