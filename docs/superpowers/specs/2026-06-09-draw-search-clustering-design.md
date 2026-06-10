# Draw-to-Search + Dynamic Clustering — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Scope:** v1 — leaflet-draw + leaflet.markercluster integration

## 1. Architecture

Two Leaflet plugins integrated as opt-in layers: `leaflet.markercluster` for low-zoom grouping, `leaflet-draw` for shape drawing. Drawn shape → GeoJSON → URL param → API `$geoIntersects` filter. Both toggled via MapLegend checkboxes.

```
Toggle "Cluster" → ClusterLayer replaces raw markers → user zooms → clusters group/disperse
Toggle "Draw" → DrawToolbar activates → user draws shape → ShapeFilter encodes → URL → API filters
```

## 2. Module Design Blocks

### Module: `dashboard/components/ClusterLayer.tsx` (new)
- **Responsibility:** render markers as clustered group
- **Interface:** takes `MapListing[]`, renders `L.markerClusterGroup`
- **Config:**
  - `chunkedLoading: true`
  - `spiderfyOnMaxZoom: true`
  - `showCoverageOnHover: false`
  - `maxClusterRadius: 80` (px)
  - `disableClusteringAtZoom: 16`
- **Custom iconFn:** 3 size tiers (small < 10 listings, medium < 50, large >= 50) with color from avg cluster score
- **Dependencies:** `leaflet.markercluster` npm
- **Size target:** <100 lines

### Module: `dashboard/components/DrawToolbar.tsx` (new)
- **Responsibility:** leaflet-draw integration with custom styling
- **Interface:** emits `onShapeDrawn(latlngs: LatLng[])`
- **Modes:** polygon (freehand), rectangle, circle (default: polygon)
- **Style:** drawn shape fill blue 0.1 opacity, stroke blue 2px
- **Toolbar:** Polygon | Rectangle | Circle | Edit | Delete
- **Edit support:** drag vertices, drag whole shape
- **Dependencies:** `leaflet-draw` npm
- **Size target:** <120 lines

### Module: `dashboard/components/ShapeFilter.tsx` (new)
- **Responsibility:** convert drawn shape to/from API query param
- **Interface:** `encode(latlngs: LatLng[]): string` (base64 GeoJSON), `decode(s: string): LatLng[] | null`
- **Output:** URL param `?shape=<base64>`
- **Cap:** max 50 vertices to keep URL under 4096 chars
- **Size target:** <60 lines

### Module: API shape filter (`/api/listings/route.ts` extend)
- **Add param:** `?shape=<base64-geojson>`
- **Logic:** decode → for each listing, run point-in-polygon
- **Performance:** use MongoDB `$geoIntersects` with `2dsphere` index on `loc` field (GeoJSON Point)
- **Fallback:** in-memory `@turf/boolean-point-in-polygon` if Mongo query fails
- **Size target:** +30 lines
- **Dependencies:** `@turf/boolean-point-in-polygon`

### Module: MapLegend additions (`dashboard/components/MapLegend.tsx` extend)
- **Add checkboxes:**
  - "Cluster pins at low zoom" (default on)
  - "Draw to search" (default off)
- **Size target:** +20 lines

### Module: MapView integration (`dashboard/components/MapView.tsx` extend)
- **When "Cluster" enabled:** render ClusterLayer instead of raw marker loop
- **When "Draw" enabled:** mount DrawToolbar in top-left of map
- **On shape drawn:** ShapeFilter.encode → URL update + API refetch
- **On shape cleared:** URL param removed + full listings
- **Co-existence:** Grätzl, zones, anergy, heatmap layers stay; cluster sits at marker z-order
- **Size target:** +40 lines (refactor existing marker loop)

### Module: Draw toolbar UI affordances (extend DrawToolbar)
- **FAB:** "Draw area" → enters draw mode (only when not already active)
- **Active draw:** cursor = crosshair, map drag disabled
- **Esc:** cancel current draw
- **Right-click on existing shape:** context menu — Filter inside | Filter outside | Delete
- **Toast on draw complete:** "Filter applied — N listings shown"
- **Size target:** +40 lines

### Module: Shape state persistence (extend ModeProvider/ShapeProvider)
- **URL param persists** across reloads
- **localStorage backup:** `immo-shape` for last drawn shape
- **Cleared** on explicit Delete action or user clears URL
- **Size target:** +30 lines (new ShapeProvider similar to ModeProvider)

### Module: Cluster click UX (extend ClusterLayer)
- **Click cluster:** zoom to bounds (animated)
- **Click cluster at max zoom (16+):** spiderfy opens individual pins
- **Click individual pin:** existing ListingDetail open flow
- **Cluster icon hover:** tooltip with count + price range
- **Size target:** +20 lines

## 3. Data Flow

1. User toggles "Cluster pins" → MapView re-renders with ClusterLayer
2. User zooms out → clusters group dynamically
3. User zooms past 16 → clusters disable, individual markers show
4. User clicks cluster → smooth zoom to bounds OR spiderfy at max zoom
5. User toggles "Draw to search" → DrawToolbar mounts
6. User picks mode + draws shape
7. DrawToolbar emits onShapeDrawn → ShapeFilter.encode → URL `?shape=<base64>`
8. ShapeProvider syncs URL + localStorage
9. /api/listings refetches with shape param
10. API runs $geoIntersects (or in-memory turf) → only inside-shape listings return
11. MapView updates markers/cluster with filtered set
12. User can Edit (drag vertices) or Delete shape
13. Delete → URL param removed → full listings

## 4. Error Handling

- Drawn shape < 3 vertices (degenerate) → reject, toast "Draw a valid area"
- Shape filter > 2s → loading indicator, debounce
- GeoJSON decode fails → ignore param, return all listings
- Cluster lib not loaded → fall back to raw markers (existing behavior)
- Draw lib not loaded → toolbar hidden, MapLegend checkbox disabled
- MongoDB $geoIntersects fails → log + fall back to in-memory point-in-polygon
- Listing without lat/lon → excluded from shape filter (no in-shape = filtered out)
- Base64 URL > 4096 chars → cap at 50 vertices, reject larger
- Map drag while drawing → disable drag, restore on cancel/complete
- No listings in shape → "0 listings in this area — try a different shape"

## 5. Testing

### Unit
- `ShapeFilter.encode/decode`: 5 cases (polygon, rectangle, circle, malformed, large)
- `ShapeFilter` cap at 50 vertices: 2 cases (50 OK, 51 reject)
- GeoJSON validation: 3 cases (valid, invalid, missing coordinates)
- Base64 roundtrip: 5 cases (small/medium/large polygons, special chars)

### API
- `/api/listings?shape=...` returns only inside-shape listings
- `/api/listings?shape=invalid` returns all (lenient)
- Performance: 1000 listings × shape filter < 500ms
- MongoDB `$geoIntersects` (with `2dsphere` index) faster than in-memory

### Playwright
- ClusterLayer renders on map (assertion: at least 1 cluster icon at zoom 11)
- Zoom in past 16 → clusters disable, individual pins show
- DrawToolbar visible when "Draw to search" toggled
- Draw polygon → shape appears, URL has `?shape=`, listings filtered
- Draw rectangle → same flow
- Draw circle → same flow
- Edit shape → URL updates, listings re-filter
- Delete shape → URL cleared, all listings back
- Esc key cancels draw
- Reload page with `?shape=...` → shape restored

### Manual
- 500+ listings → cluster icons reasonable, smooth zoom
- Drawn shape persists across reload (URL + localStorage)
- 1 known shape over Innerfavoriten → only Innerfavoriten listings show
- Right-click on shape → context menu appears
- Draw mode disables map drag

## 6. Out of Scope (v1)

- Multi-shape filters (AND/OR of multiple drawn shapes)
- Save shapes for later use
- Shape templates ("exclude industrial zones" preset)
- GeoJSON file import
- Snap-to-road while drawing
- Shape sharing via URL (URL param works, no UI share button)
- Custom cluster icons per buyer profile (always avg-score color)
- Animation on shape complete (just appear)

## 7. Migration & Rollout

- Branch: `relentless/draw-search-clustering`
- Commits (10):
  1. `chore(deps): add leaflet.markercluster + leaflet-draw + @turf packages`
  2. `feat(cluster): ClusterLayer component + MapView integration`
  3. `feat(legend): "Cluster pins" checkbox in MapLegend`
  4. `feat(draw): DrawToolbar component with polygon/rectangle/circle modes`
  5. `feat(shape): ShapeFilter encode/decode + URL + localStorage persistence`
  6. `feat(legend): "Draw to search" checkbox in MapLegend`
  7. `feat(api): shape filter param + MongoDB $geoIntersects + turf fallback`
  8. `feat(ui): draw affordances (FAB, toolbar, Esc, right-click menu)`
  9. `test: ShapeFilter unit + API shape filter + playwright draw + cluster`
  10. `docs: README update with draw/cluster usage`
- No feature flag
- Rollback: per-commit revert; both checkboxes off → existing marker behavior

## 8. Known Risks

- **leaflet.markercluster perf on 1000+:** may lag on heavy datasets. Test with realistic data volume. Fallback to supercluster (v2) if needed.
- **leaflet-draw freehand UX:** freehand polygon is awkward without snap. Users may draw weird shapes. Prominent "Clear" button mitigates.
- **MongoDB 2dsphere index:** requires `loc` field as GeoJSON Point. Verify scraper populates correctly. Add migration if not.
- **Base64 URL length:** large complex polygons → long URLs. Cap at 50 vertices to stay under 4096.
- **Draw mode interferes with map nav:** while drawing, pan/zoom may conflict. Disable map drag during draw.
- **Shape + filter combo:** drawn shape + filter chips → both apply (intersection). UI must communicate this clearly.
- **Cluster + heatmap overlap:** at low zoom, clusters + heatmap may visually clash. Heatmap auto-hides when cluster active (one or other, not both).
- **Edit shape edge case:** dragging a vertex outside Austria → invalid. Clamp to Austria bbox.

## 9. Follow-Ups (post v1)

- Switch to supercluster if markercluster perf insufficient
- Multi-shape support
- Shape templates + presets
- GeoJSON file import
- "Draw to exclude" mode (inverted filter)
- Custom cluster icons per buyer profile / mode
- Shape sharing via URL with share button
