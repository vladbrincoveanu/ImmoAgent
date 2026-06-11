# Map Overhaul — Reliability & Standard Flow

**Date:** 2026-06-07
**Scope:** `/dashboard/map` — fix broken interactions, enrich data shown, add price/district context
**Goal:** Make standard work reliably. Pin click opens detail. Detail shows what user needs. URL reflects state. No "better-looking" UI work — features and ease of use only.
**Non-goals:** Map clustering, heatmaps, drawing tools, advanced filters, redesign of pin visual style.

---

## 1. Architecture

### Current state (broken paths)

```
Pin click
  → handlePinClick → setHighlightedId(id)
  → Leaflet click bubbles to map
  → MapClickHandler → onMapClick → handleCloseDetail
  → queueMicrotask(setHighlightedId(null))
  → SelectedCard never renders  ← BUG (no-op)

Sidebar card click
  → handleSidebarSelect (2-state: 1st highlight, 2nd open detail)  ← BUG (2-click friction)

SSE new listing
  → merged with coordinates: null, coordinate_source: 'district' hardcoded
  → never appears on map  ← BUG (data loss)

Empty state
  → checks listings.length === 0 (not filteredListings)
  → shows "no listings" only when DB is empty, not when filter is too tight  ← BUG (UX confusion)

"Open Original" button
  → always rendered as active <a>, ignores urlValid: false
  → user clicks dead link  ← BUG
```

### Target state

```
Pin click → stopPropagation → setDetailId(id) → modal opens (1 click)
Sidebar click → setDetailId(id) → modal opens (1 click)
SSE new listing → fetch coordinates from /api/listings/[id] OR skip on map until next full refresh
Empty state → checks filteredListings.length
"Open Original" → disabled + warning if urlValid === false
URL reflects detailId, district, minScore, maxPrice → shareable, back-button works
Detail modal shows: prominent €/m², distance to center, distance to nearest U-Bahn, district median €/m², price history sparkline (if exists)
```

---

## 2. Module Design Blocks

### Module: MapView (pin click event)
- **Responsibility:** Render markers, fire pin click with event stopped so it does not bubble to map.
- **Interface:** Props unchanged. Internal: `marker.on('click', (e) => { L.DomEvent.stopPropagation(e); onPinClick(listing); })`.
- **Dependencies:** Leaflet, react-leaflet.
- **Size target:** ~230 lines (current 228 + 1 line change). No new file.

### Module: MapPage (click flow refactor)
- **Responsibility:** Own listing state, filter state, detail state. Sync detailId, district, minScore, maxPrice to URL via `useSearchParams`.
- **Interface:**
  - `handlePinClick(listing) → setDetailId(listing._id)` (was: setHighlightedId)
  - `handleSidebarSelect(listing) → setDetailId(listing._id)` (was: 2-stage)
  - `handleCloseDetail() → setDetailId(null)` (drop microtask + highlightedId clearing)
  - `useEffect` syncs URL → state on mount, state → URL on change.
- **Dependencies:** MapView, ListingDetail, ListingSidebar, BottomSheet, FilterDrawer, useListingsSSE, next/navigation.
- **Size target:** ~280 lines (current 308 + URL sync logic - SelectedCard - highlight state - 2-stage select).

### Module: ListingDetail (enrichment)
- **Responsibility:** Show full listing data with focus on price context and locality.
- **Interface:** Props unchanged: `{ id, onClose }`. Internal: fetch /api/listings/[id] (existing) + /api/listings/[id]/context (new) in parallel.
- **New sections rendered:**
  1. **Prominent €/m² header**: rendered as `<h3 className="text-lg font-bold">€{price_per_m2.toFixed(1)}k/m²</h3>` directly under price, NOT inside the small 2-col grid. Removed from grid.
  2. **Distance row**: 3 inline items. Format: "City center: 2.4 km · U-Bahn Stephansplatz: 320 m · Nearest school: 180 m". Distances ≥1000m formatted as km with 1 decimal, <1000m as m integer.
  3. **District context block**: median €/m² in district · this listing's percentile · trend (last 90 days, if data). Format example: "1080 median: €7.2k/m² · this listing: 35th percentile (cheaper than 65%) · trend 90d: −2.1%".
  4. **Price history sparkline** (if `price_history.length >= 2`): inline 120×32 SVG, no labels, color green if last < first else red.
- **"Open Original" fix:** if `urlValid === false`, render disabled button with text "Listing offline (last checked: X)" + working "Recheck Availability" button.
- **Dependencies:** ScoreBadge, new Sparkline component, fetch.
- **Size target:** Current 222 lines → ~320 lines (adds 4 sections, ~25 lines each). If exceeds 300, split district context into own subcomponent.

### Module: Sparkline (new)
- **Responsibility:** Render inline price history as SVG polyline. No axes, no labels — just the trend line.
- **Interface:** Props `{ points: Array<{price: number, recorded_at: string}>, width?: number, height?: number }`. Default 120×32.
- **Dependencies:** None (raw SVG).
- **Size target:** ~50 lines. New file `components/Sparkline.tsx`.

### Module: /api/listings/[id]/context (new endpoint)
- **Responsibility:** Return locality + district stats for a single listing.
- **Interface:**
  - GET `/api/listings/[id]/context`
  - Response:
    ```ts
    {
      distance_to_center_km: number | null,    // Stephansplatz 48.2082, 16.3738; haversine km, 2 decimals
      nearest_ubahn: { name: string, distance_m: number } | null,  // distance in meters, integer
      district_stats: {
        median_price_per_m2: number | null,    // EUR/m²
        listing_percentile: number | null,     // 0-100, lower = cheaper than 1st pct of district
        sample_size: number,                   // active listings in district (url_is_valid=true)
        trend_90d_pct: number | null           // % change in median over last 90 days
      }
    }
    ```
- **Dependencies:** mongodb_handler (db.collection('listings')), ubahn_coordinates.json (read at module init).
- **Implementation notes:**
  - Distance: haversine in module, inline (~10 lines).
  - District stats: aggregation `{ $match: { bezirk, url_is_valid: true, price_per_m2: { $gt: 0 } } }` → `$group: { median: $median, count: $sum }`. MongoDB 6+ supports `$median`.
  - Trend: same aggregation filtered by `processed_at` 90 days vs prior 90 days, diff %.
  - All fields nullable — never block render on stats failure.
- **Size target:** ~120 lines. New file `app/api/listings/[id]/context/route.ts`.

### Module: MapListing type (add url_is_valid)
- **Responsibility:** Already defined. Add one field.
- **Interface:** Add `url_is_valid?: boolean`.
- **Dependencies:** None.
- **Size target:** +1 line in `lib/types.ts`.
- **Propagation:** `/api/listings/map/route.ts` must include `url_is_valid: listing.url_is_valid ?? true` in projected output.

### Module: SSE merge fix (in MapPage)
- **Responsibility:** When new listing arrives via SSE, do not silently drop coordinates.
- **Strategy:** v1 — skip SSE merge on map page entirely (do not add to `listings`). Show a toast/banner "N new listings available — click to refresh" that calls `fetchListings()`. Reason: cheaper than per-listing coord fetch, avoids stale coord state.
- **Interface:** New state `pendingNewCount: number`, banner component, manual refresh button.
- **Size target:** ~30 lines in MapPage.

### Module: Empty state fix (in MapPage)
- **Responsibility:** Trivial. Change `listings.length === 0` to `filteredListings.length === 0` on line 273.
- **Size target:** 1 line.

### Module: SelectedCard (delete)
- **Responsibility:** Removed. 1-click pin → modal replaces preview card.
- **Migration:** Delete `components/SelectedCard.tsx`. Remove import + JSX from MapPage. Remove related test `tests/map-interaction.spec.ts` line 156 case ("pin click shows SelectedCard"), replace with "pin click opens detail modal".

---

## 3. Data Flow

```
GET /dashboard/map?detail=ID&district=1080&min_score=30
  → MapPage reads URL → state
  → fetchListings(/api/listings/map?district=1080&min_score=30)
  → renders MapView (pins) + Sidebar (cards)
  → if detail=ID in URL → renders <ListingDetail id=ID>
     → parallel fetch:
        - /api/listings/ID  (existing — full doc with price_history)
        - /api/listings/ID/context  (new — distance, district stats)
     → renders prominent €/m² · distance row · district block · sparkline · standard fields · financing · "Open Original" (disabled if urlValid=false)

Pin click on map
  → stopPropagation
  → setDetailId(listing._id)
  → URL updates to ?detail=ID
  → modal opens

Sidebar card click
  → setDetailId(listing._id) (same path)

Close modal (Escape, X, click backdrop)
  → setDetailId(null)
  → URL updates (detail param removed)

Filter change (district, min_score, max_price)
  → state updates → URL updates
  → fetchListings re-runs

SSE new listing arrives
  → banner "N new — click to refresh"
  → user clicks → fetchListings() → state replaced
```

---

## 4. Error Handling

| Failure | Behavior |
|---|---|
| `/api/listings/[id]` returns 404 | Modal shows "Listing not found" + close button (existing) |
| `/api/listings/[id]/context` fails or times out | Modal renders WITHOUT district block, distance row shows "—". No blocking error. |
| `price_history` missing or length < 2 | Sparkline section omitted entirely. |
| District has < 5 active listings | District block shows "Not enough data" instead of percentile/trend. |
| `url_is_valid === false` | "Open Original" disabled, label "Listing offline". "Recheck Availability" still active. |
| `coordinates === null` on listing in `listings` array | Skip in MarkerLayer (existing behavior). Still appears in sidebar. |
| SSE connection drops | Existing reconnect logic in `useListingsSSE` unchanged. Banner counter resets on full refresh. |
| Stephansplatz distance > 50 km | Treat as nullable, show "—" (defensive — likely coord bug if hit). |
| MongoDB `$median` unsupported (version < 6) | Aggregation fails → context endpoint returns `median_price_per_m2: null`. Log once at startup; do not retry. |

---

## 5. Testing

### Playwright smoke tests (extend `dashboard/tests/smoke.spec.ts`)

Existing tests must continue to pass. New cases:

1. **Pin click opens detail in 1 click** — load map, wait for pins, click first pin, assert `dialog`-role modal visible within 500ms.
2. **Sidebar click opens detail in 1 click** — load map with desktop viewport, click first sidebar card, assert modal visible.
3. **URL reflects detail state** — open modal, assert `page.url()` contains `?detail=`. Close modal, assert `?detail=` removed.
4. **Empty filter shows empty state** — set `min_score=100` (no listings match), assert "No listings match your filters" text visible.
5. **"Open Original" disabled when urlValid=false** — seed a listing with `url_is_valid: false`, open detail, assert button has `disabled` attribute and text "Listing offline".

### Unit tests (new — `dashboard/tests/api/`)

6. **/api/listings/[id]/context** — given a listing with bezirk=1080 and 10 listings in district, returns numeric `median_price_per_m2`, `listing_percentile` between 0-100.
7. **Sparkline** — given 3 points, renders polyline with 3 (x, y) pairs.
8. **Sparkline** — given 0 or 1 point, renders null (does not throw).

### Manual smoke (post-deploy)

- Open `/dashboard/map?detail=<known_id>` directly. Modal opens on load.
- Click pin. No-op bug gone. Modal opens.
- Open in browser, set min_score=80. Empty state shows.
- Open a listing detail. Sparkline visible (if price_history exists). District percentile visible (if district has data).

---

## 6. Out of Scope (defer to v2)

- Distance to nearest park (no park data file exists; defer until `vienna_parks.json` curated)
- Pin clustering at low zoom
- Map heatmap of €/m²
- Drawing tools (draw area → filter listings inside)
- Saved searches
- Compare 2 listings side by side
- Price prediction / "good deal" badge on pins (color = €/m² percentile)
- Per-listing photo gallery
- Inline map switching to satellite view

These are good features. Not in this scope. They go in a separate spec after v1 ships and gets used.

---

## 7. Migration & Rollout

- One commit per module (8 commits, all on `main`).
- No feature flag — internal personal tool, user is only consumer.
- Order:
  1. Add `url_is_valid` to `MapListing` type + API projection.
  2. Fix empty state line (1-line change).
  3. Fix pin click stopPropagation in MapView.
  4. Refactor MapPage click flow (1-click pin/sidebar → modal, delete SelectedCard, drop highlight state).
  5. Add URL sync to MapPage.
  6. Add `/api/listings/[id]/context` endpoint.
  7. Create Sparkline component.
  8. Enrich ListingDetail (prominent €/m², distance row, district block, sparkline, fix "Open Original").
  9. Fix SSE merge → banner pattern.
  10. Update Playwright tests.

Each commit must pass `npx playwright test --reporter=list` per project rule `.claude/rules/ui-testing.md`.

---

## 8. Known Risks

| Risk | Mitigation |
|---|---|
| MongoDB `$median` not supported in deployed version | Confirm before implementing; fall back to client-side median if needed (sort + middle element from ~100-listing district array). |
| `price_history` field rarely populated → sparkline almost never shows | Acceptable for v1. Triggers future work to backfill from scrape logs. |
| URL sync breaks back-button if pushState used wrong | Use Next's `useRouter().push(url, { scroll: false })` — never `window.history.replaceState`. |
| Removing SelectedCard breaks existing test | Test rewrite is part of work, listed in §5. |
| `L.DomEvent.stopPropagation` syntax error in latest Leaflet | Verify import works; fallback `e.originalEvent.stopPropagation()`. |
