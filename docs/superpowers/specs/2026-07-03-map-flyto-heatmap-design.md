---
title: Map — click-to-fly, honest coordinates, district price choropleth
date: 2026-07-03
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Map Upgrade: Click-to-Fly, Honest Coords, District Price Heatmap

## Problem (from user)
1. Clicking a property does **not** open/pan the map to its exact location (bug — map stays zoomed out over the Vienna Woods while a listing is selected).
2. Concern that stored locations may be "garbage".
3. Want a semi-transparent price overlay showing pricier vs cheaper **zones** ("biomes").

## Investigation results (evidence)
- **Bug confirmed:** `selectedListingId` flows through, marker recolors, but there is **no** `flyTo`/`setView`/`panTo` anywhere (`dashboard/components/MapView.tsx`). Selection never moves the viewport.
- **Coords are legit** when present: exact Nominatim/OSM geocoding of the full address (`Project/Application/helpers/geocoding.py:100-131`), tagged `coordinate_source` = `'exact'` | `'landmark'`.
- **The one bad path:** `dashboard/app/api/listings/map/route.ts:102-113` applies a **district-centroid fallback** — listings that fail geocoding are dumped on the geometric center of their Bezirk (`coordinate_source:'district'`), visually indistinguishable from precise pins.
- **Heatmap data ready:** per-district avg €/m² already computed as `zoneStats` (`route.ts:71-88`); every listing has `bezirk` + `price_per_m2`. Missing only a 23-Bezirk boundary GeoJSON.

## Decisions (locked with user)
- Heatmap = **district choropleth** (23 Bezirke), colored by **avg €/m²**.
- Listings with **no real coordinates are NOT shown on the map** (drop the centroid fallback). They remain in the rail.
- **One combined spec, phased**: Phase 1 = fly + honest coords; Phase 2 = choropleth.

## Phase 1 — Click→fly + honest map

### Module: SelectionAnimator (new, inside MapView.tsx)
- **Responsibility:** Fly the visible Leaflet map to the selected listing's coords when `selectedListingId` changes.
- **Interface:** Props/context: `selectedListingId`, `listings`; uses `useMap()`. Effect: `map.flyTo([lat,lon], 16, {duration:1.2, easeLinearity:0.25})`.
- **Dependencies:** react-leaflet `useMap`; must **guard** `const s = map.getSize(); if (s.x === 0 || s.y === 0) return;` so the hidden mobile map never hijacks focus (same guard pattern as BoundsTracker fix, commit 2f32f06).
- **Size target:** ~30 lines.

### Module: map API centroid removal (edit)
- **Responsibility:** Stop fabricating coordinates for un-geocoded listings.
- **Interface:** `dashboard/app/api/listings/map/route.ts:102-113` — remove the `resolveCoordinates`→centroid branch; when no stored coords, return `coordinates: null`, `coordinate_source: 'none'`. Also `dashboard/app/dashboard/map/page.tsx:84` (drops the `'district'` assignment).
- **Dependencies:** existing viewport filter already excludes `coordinates:null` (`page.tsx:164-171`) — no extra filtering needed.
- **Size target:** net negative LOC.

### Rail count honesty (edit)
- Rail header shows "N in view" — after the change this reflects only on-map listings. Add a subtle "X of Y with location" note if Y−X is non-trivial. (Optional; confirm during impl.)

## Phase 2 — District price choropleth

### Module: vienna-districts.geojson (new asset)
- **Responsibility:** 23 Bezirk polygons with a `bezirk` property matching the 4-digit postal code used on listings ('1010'…'1230').
- **Source:** data.gv.at / OSM (admin_level=9). Simplify to ~50KB. Stored at `dashboard/public/vienna-districts.geojson`.

### Module: /api/district-heatmap (new route)
- **Responsibility:** Return `{ "1010": { avg_price_per_m2, count }, ... }` for all 23 districts.
- **Interface:** GET, optional `profile`/`min_score` passthrough; reuses the `zoneStats` `$group`/`$avg`/`$divide` aggregation already in `route.ts:71-88`.
- **Dependencies:** MongoDB `listings` (via existing db handle). Same validity filters (`url_is_valid != false`, `listing_status != 'taken'`, `price_total>0`, `area_m2>0`).
- **Size target:** ~40 lines.

### Module: DistrictHeatmapLayer (new, in MapView.tsx)
- **Responsibility:** Render `<GeoJSON>` with per-feature fill color from avg €/m².
- **Interface:** Props: `districtStats`, `visible`. Color scale: green (≈€3,500/m²) → yellow (≈€5,500) → red (≈€8,000+), thresholds from `scoring.py` NORMALIZATION_RANGES so it matches the scoring model. `fillOpacity: 0.45`, thin border, hover tooltip "1070 · Ø €6,200/m² · 42 listings". Non-interactive to clicks (don't steal marker clicks).
- **Dependencies:** react-leaflet `GeoJSON`; heatmap data from `/api/district-heatmap`.
- **Size target:** ~60 lines.

### Module: layer toggle + legend (edit)
- `LayerState` gains `heatmap: boolean` (default **false**). Add checkbox to `MapLayersPopover.tsx`. Small gradient legend (green→red, €/m² labels) shown when active.

## Testing (test_scope: true — non-skippable per cycle)
Per `.claude/rules/ui-testing.md`, verify with **/playwright-pro** against real DOM after each cycle:
- **P1:** select a rail card → assert map center moves to that listing's coords (read Leaflet center via `browser_evaluate`); assert a listing with `coordinate_source:'none'` has **no** marker on the desktop map (`.map-desktop`); regression: hidden mobile map must not move the desktop map (extend existing `map-bounds-clobber.spec.ts`).
- **P2:** toggle heatmap → assert 23 `path` polygons render with non-empty fill; hover → tooltip text; toggle off → polygons gone. Legend visible only when active.
- Final gate: full suite `npx playwright test --reporter=line`, 0 failures, 0 console errors on `/`, `/dashboard`, `/dashboard/map`.

## Out of scope
- Grätzl (sub-district) granularity — deferred.
- Backfilling failed geocodes — separate task.
- Changing the Python geocoder.
