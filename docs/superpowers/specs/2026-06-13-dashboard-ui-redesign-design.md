---
title: Dashboard UI Redesign — /dashboard/map
date: 2026-06-13
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Dashboard UI Redesign — /dashboard/map

## Context

The `/dashboard/map` page has accumulated visual clutter: price pins, 55 U-Bahn station labels, 208 school dots, two competing legend boxes, a sidebar list, and a duplicate card grid below the map. A static design handoff in `design_handoff_property_map/` (HTML + CSS + README, not code to copy) proposes a calmer layout: a single top bar with popovers, a 340px listing rail, a price-pin-only map with opt-in infrastructure layers, and an on-demand detail card. The prototype's Core Design Principle is **progressive disclosure**: price pins by default, everything else one click away.

**Scope:** `/dashboard/map` only. `/dashboard` (listings) and `/dashboard/taken` are out of scope and stay on the current warm theme.

**Theme:** Match the new design tokens exactly. Cool palette, Inter font, blue accent. This is a brand shift on the map page only — the rest of the dashboard stays warm until a future redesign.

**Reference files:**
- `~/Downloads/design_handoff_property_map/README.md` — full spec
- `~/Downloads/design_handoff_property_map/Property Map Redesign.html` — prototype
- `~/Downloads/design_handoff_property_map/map-styles.css` — design tokens in `:root`

## Architecture

Single owner: `app/dashboard/map/page.tsx`. All listing/filter/selection/layer state lives here. Children mount UI; no child owns shared state.

```
app/dashboard/map/page.tsx                (modified — state, layout)
├── <MapTopBar>                            (new — 56px white bar, brand + filter btn + layers btn)
│   ├── <MapFilterPopover>                 (new — 280px right-anchored)
│   └── <MapLayersPopover>                 (new — mounted inside MapView, top-right of map)
├── <ListingRail>                          (modified from ListingSidebar — 340px left rail)
│   └── <SlimListingCard>                  (new — thumb + price + title + m²/€/m² + score chip)
└── <MapView>                              (modified — single-navy pins, opt-in infra)
    ├── <MapLayersPopover>                 (anchored inside map top-right)
    └── <SelectedCard>                     (restyled — 320px bottom-left, fact chips)

Mobile <md: <BottomSheet> (unchanged) for the rail.
```

The page wraps the desktop layout in `hidden md:flex` and keeps the existing `<BottomSheet>` flow inside `md:hidden`. Both share URL state via `useFilters`.

## State Model

Held in `map/page.tsx`:

| State | Type | Source | Notes |
|---|---|---|---|
| `selectedListingId` | `string \| null` | `useState` | Single source of truth for "what's selected" |
| `sortMode` | `'score' \| 'priceAsc' \| 'priceDesc'` | new | URL-synced via `parseSort` (already in `lib/filters.ts` from commit bccc771) |
| `filters` | `{district, minScore, maxPrice, commuteTo, ...}` | existing `useFilters` | URL-synced; unchanged |
| `layers` | `{listings: true, stations: false, schools: false}` | `useState` | NOT URL-synced (transient UI state) |
| `viewportListings` | derived | `useMemo` | exists from 2026-05-14 design |
| `activeFilterCount` | derived | count of non-empty filter fields | drives the badge on the Filters button |

**Click flow:** Both pin click and rail card click set `selectedListingId`. Closing the detail card = `null`. Map pans to selected listing unless click came from the map itself (avoids feedback loop). Rail scrolls the matching card into view via container scroll (not `scrollIntoView`).

## Module Design Blocks

### Module: `MapTopBar` (new)
- **Responsibility:** Renders the 56px white top bar with brand, profile selector slot, Filters button (with count badge), Layers button.
- **Interface:** Props: `activeFilterCount: number`, `onFiltersClick: () => void`, `onLayersClick: () => void`. Internal: owns popover open/close state via a small reducer or two booleans.
- **Dependencies:** `MapFilterPopover`, `MapLayersPopover`, `ProfileSelector` (existing).
- **Size target:** ~120 lines.

### Module: `MapFilterPopover` (new)
- **Responsibility:** 280px right-anchored popover with District, Min score, Max price, Commute-to fields. Apply commits to `useFilters`, closes popover.
- **Interface:** Props: `open: boolean`, `onClose: () => void`, `onApply: () => void`. Reads/writes filter state via `useFilters` hook.
- **Dependencies:** `useFilters`.
- **Size target:** ~150 lines.

### Module: `MapLayersPopover` (new)
- **Responsibility:** 224px top-right popover with three toggle rows (Listings, U-Bahn, Schools). Calls into `layers` state in page.
- **Interface:** Props: `open: boolean`, `onClose: () => void`, `layers: {listings, stations, schools}`, `onToggle: (key: 'stations' | 'schools') => void`, `counts: {listings: number, stations: number, schools: number}`.
- **Dependencies:** None.
- **Size target:** ~80 lines.

### Module: `ListingRail` (new — replaces ListingSidebar on /map)
- **Responsibility:** 340px left rail with header (count + sort) and scrollable card list. Renders only listings currently in viewport.
- **Interface:** Props: `listings: MapListing[]`, `selectedId: string | null`, `onSelect: (id: string) => void`, `sortMode: SortOption`, `onSortChange: (s: SortOption) => void`.
- **Dependencies:** `SlimListingCard`, `lib/filters.ts` for sort.
- **Size target:** ~80 lines.

### Module: `SlimListingCard` (new)
- **Responsibility:** Compact listing row. Thumb (real `image_url` or house-SVG fallback), price, 1-line ellipsis title, `m² · €/m²`, score chip (green ≥28, amber <28). NO zone-delta, NO address, NO price_vs_avg_pct.
- **Interface:** Props: `listing: MapListing`, `selected: boolean`, `onClick: () => void`.
- **Dependencies:** `ScoreBadge` (existing).
- **Size target:** ~70 lines.

### Module: `MapView` (modified)
- **Responsibility:** Leaflet map with single-navy price pins, opt-in U-Bahn/schools groups, bounds tracker, layer popover mount point. No state.
- **Interface:** Props in: `listings: MapListing[]`, `selectedListingId: string \| null`, `hoveredId: string \| null`, `layers: {listings, stations, schools}`, `onPinClick`, `onHover`, `onHoverEnd`, `onBoundsChange`, `onMapClick`, `layersPopover: ReactNode` (slot).
- **Dependencies:** `leaflet`, `react-leaflet`.
- **Size target:** ~250 lines (current 302 + new layers logic − removed color tier code).

### Module: `SelectedCard` (modified)
- **Responsibility:** Floating 320px card at `bottom-14 left-14`. Fact chips (m², €/m², Score, zone-delta vs district). × close. "View listing" CTA opens full `ListingDetail` modal.
- **Interface:** Props unchanged: `{listing, onClose, onViewDetails}`.
- **Dependencies:** `ListingDetail` (existing).
- **Size target:** ~80 lines (current 75 + 5).

### Module: `map/page.tsx` (modified)
- **Responsibility:** State owner, layout, mobile fallback, URL sync.
- **Interface:** URL params: `district`, `minScore`, `maxPrice`, `commuteTo`, `sort`, `listing` (selectedListingId). On mount, read from URL; on state change, write to URL.
- **Dependencies:** `MapTopBar`, `ListingRail`, `MapView`, `SelectedCard`, `BottomSheet` (mobile), `useFilters`, `useListingsSSE`.
- **Size target:** ~340 lines (current 330 + state + URL sync + layout switch).

## Component Decisions — Keep / Modify / Delete

Verified by grep across `dashboard/` and `dashboard/tests/`:

| Component | Used on /map? | Used on /dashboard? | Tests reference? | Action |
|---|---|---|---|---|
| `FilterDrawer` | yes (currently) | **yes** (line 7, 237) | 4 tests in `map-full.spec.ts` | **KEEP** — still used by `/dashboard`. Stop mounting on `/map`. Update 4 tests in `map-full.spec.ts` to use new `MapFilterPopover`. |
| `MapLayerToggle` | yes | no | 1 test in `address-bank-declutter.spec.ts:124` | **DELETE** component. Rewrite test to use new `MapLayersPopover`. |
| `MapLegend` | yes | no | 2 tests (commute-rent-insights, map-overhaul) | **DELETE** component. Rewrite tests to assert new Layers popover counts. |
| `MapGuide` | yes | no | 1 test in `commute-rent-insights.spec.ts:131` | **DELETE** component. Rewrite test to assert no overlay (or remove if no replacement). |
| `PriceHeatmap` | yes | no | none | **DELETE** component. No test to update. |

**Net:** 4 deletes + 1 keep-and-stop-mounting. The 4 tests that touch the deleted components must be rewritten in the same PR.

## Token Migration

### `tailwind.config.ts` — replace `theme.extend.colors`

```ts
colors: {
  ink: '#16243a',
  'ink-2': '#5b6b80',
  'ink-3': '#93a1b3',
  line: '#e6eaf0',
  bg: '#f7f8fa',
  card: '#ffffff',
  accent: '#2456e6',
  'accent-soft': '#eef2fe',
  good: '#0f8a5f',
  'good-soft': '#e8f5ef',
  'mid-ink': '#b06c0a',
  'mid-soft': '#fdf3e4',
  // legacy aliases (used elsewhere in the codebase, not just /map)
  'warm-bg': '#F9F7F4',
  heading: '#3D405B',
  muted: '#8B8B8B',
  border: '#E8E4E0',
  success: '#81B29A',
  dark: { /* unchanged dark mode tokens */ },
}
```

The new tokens are added; legacy warm tokens are KEPT (still used by `/dashboard` and `/dashboard/taken`). New `/map` components use only the new tokens.

### `app/globals.css`
- Add `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap')`.
- Add `font-family: 'Inter', -apple-system, sans-serif` to the `.map-desktop` class (or a CSS layer scoped to the new layout).
- Remove `font-dm-sans` from `fontFamily.dm-sans` ONLY if no other code uses it. Otherwise keep both.

## Map Changes

### Pins
Replace `createPriceIcon(price, color, tier)` with a single `createPriceIcon(price)`:
- `background: #16243a`
- `color: #fff`
- `font-size: 11.5px; font-weight: 600`
- `padding: 4px 9px; border-radius: 999px; border: 1.5px solid #fff`
- `box-shadow: 0 2px 6px rgba(22,36,58,0.25)`
- Hover: `transform: scale(1.08)`
- Selected: `background: #2456e6`

Delete constants `EXACT_COLOR`, `LANDMARK_COLOR`, `DISTRICT_COLOR`, `HIGHLIGHT_COLOR`, `UBAHN_COLOR`, `SCHOOL_COLOR`, `HOVER_COLOR`. Drop the `PinState` / `MarkerTier` types. The `selectedListingId` from page state is the only pin-state signal.

### Layers
- `MapView` accepts `layers: {listings, stations, schools}`.
- Listings layer always renders (matches `listings: true` default; can be toggled off in popover for a map-only view).
- U-Bahn group renders only when `layers.stations`.
- Schools group renders only when `layers.schools`.
- Count badges in the popover come from `/api/geo/infrastructure` (same source `MapLegend` used).

### Tiles
The new design calls for CARTO Positron (`https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png`). If the current tile URL is already Positron, no change. If it's the default OSM, switch the `TileLayer` URL.

### Bounds + click
- `BoundsTracker` (existing) keeps current `onBoundsChange` contract.
- `MapClickHandler` keeps the `stopPropagation` fix from the 2026-06-07 overhaul.

## Mobile Fallback

`map/page.tsx` structure:

```tsx
<div>
  <div className="hidden md:flex"> {/* new desktop layout */}
    <MapTopBar ... />
    <div className="flex-1 flex">
      <ListingRail ... />
      <MapView ... />
    </div>
  </div>
  <div className="md:hidden"> {/* existing mobile flow */}
    {/* <BottomSheet>, current map+filter+rail pattern */}
  </div>
</div>
```

URL state is shared. The mobile branch keeps the existing FilterDrawer, MapLayerToggle (no — these are deleted, use the new popovers? — see open question below), and BottomSheet as-is.

**Open question to resolve during implementation:** Should the mobile branch also use the new popovers + new SelectedCard styling, or keep the current mobile components entirely? Current spec says "leave mobile on BottomSheet" — interpreted as: keep the mobile LAYOUT (bottom sheet) but use the new popovers and new card style. **Decision during implementation:** use the new components on both branches; only the layout (rail vs sheet) changes by breakpoint.

## Testing

### Update existing tests
| File | Change |
|---|---|
| `tests/map-full.spec.ts` | 4 FilterDrawer tests → rewrite to use new `MapFilterPopover` (open via Filters button, apply closes, badge count updates). Also: rail width assertion (340px), top bar assertion, layers popover assertion. |
| `tests/address-bank-declutter.spec.ts:124` | `MapLayerToggle lets user turn U-Bahn / Schools / Pins on and off` → rewrite to use new `MapLayersPopover`. |
| `tests/commute-rent-insights.spec.ts:122` | `MapLegend shows U-Bahn and school counts` → rewrite to assert new Layers popover counts. |
| `tests/commute-rent-insights.spec.ts:131` | `MapGuide overlay explains every dot type` → remove (no replacement) OR rewrite to assert no overlay. |
| `tests/map-overhaul.spec.ts:78` | `MapLegend shows U-Bahn and school counts` → rewrite to use Layers popover. |
| `tests/pin-click.spec.ts` | Update pin style assertions (no color tier, single navy). Selected state = #2456e6. |
| `tests/map-interaction.spec.ts` | Update SelectedCard position assertion (was bottom-center, now bottom-left 320px). |

### Add new tests
- `tests/desktop-redesign.spec.ts` — top bar renders, brand "Immo Scouter", filter popover opens/closes, layers popover toggles U-Bahn/schools, rail width = 340px, selected card position = bottom-left 320px, mobile shows BottomSheet at 375px viewport.
- `tests/slim-listing-card.spec.ts` — rail card shows thumb+price+title+m²/€/m²+score; no zone-delta or price_vs_avg_pct on rail cards.

## Verification

Per `dashboard/.claude/rules/ui-testing.md` and memory `feedback-verify-on-real-data.md`:

1. `cd dashboard && npm run dev &` (kill any existing `next dev` first).
2. Iterate with single specs: `npx playwright test tests/desktop-redesign.spec.ts --reporter=dot`.
3. On failure, read only the failing test's error block. Fix root cause. Re-run that spec.
4. Final gate: `npx playwright test --reporter=line` — 0 failures, 0 console errors on `/dashboard/map`.
5. **Real-data verification:** local Mongo is empty. Use `npx playwright test --config=playwright.prod.config.ts` against the Vercel production URL to verify with real listings.
6. `pkill -f "next dev"`.

## Open Risks

- **Theme clash on the page:** the top bar/rail/map use new cool tokens; if any imported component (e.g. `ProfileSelector`, `ScoreBadge`) renders in a warm tone that bleeds into the new shell, it will look inconsistent. Mitigation: render all new shell components in cool tokens; only allow `ProfileSelector` / `ScoreBadge` to render inside their existing well-defined boxes.
- **FilterDrawer kept:** users on `/map` will see the new popover; users on `/dashboard` see the drawer. Two filter UIs in the same app — different but not contradictory.
- **Inter font load:** adds a network request. Acceptable for a /map-only redesign; not a global change.
- **Coordinate-source signal lost:** pins no longer color-code exact/landmark/district. Users who relied on that signal lose it. Acceptable per decision; the detail card still shows coordinate accuracy hints via the existing `coordinate_source` field if needed.

## Files to Modify / Create / Delete

### Create (5)
- `dashboard/components/MapTopBar.tsx`
- `dashboard/components/MapFilterPopover.tsx`
- `dashboard/components/MapLayersPopover.tsx`
- `dashboard/components/ListingRail.tsx`
- `dashboard/components/SlimListingCard.tsx`

### Modify (6)
- `dashboard/app/dashboard/map/page.tsx`
- `dashboard/components/MapView.tsx`
- `dashboard/components/SelectedCard.tsx`
- `dashboard/lib/filters.ts` (reuse `SortOption` from bccc771)
- `dashboard/tailwind.config.ts`
- `dashboard/app/globals.css`

### Delete (4)
- `dashboard/components/MapLayerToggle.tsx`
- `dashboard/components/MapLegend.tsx`
- `dashboard/components/MapGuide.tsx`
- `dashboard/components/PriceHeatmap.tsx`

### Keep but stop mounting (1)
- `dashboard/components/FilterDrawer.tsx` — used by `/dashboard` (the list page)

### Test files (update + new = 9 files)
- 6 test updates + 2 new test files (8 files modified, 2 created) — see Testing section.

## Spec Self-Review

- [x] **Placeholder scan:** No TBDs. Every module has a Design Block.
- [x] **Internal consistency:** Component list matches architecture diagram. State model matches interfaces. Delete-vs-keep table matches grep results.
- [x] **Scope check:** Single page (`/dashboard/map`). One PR. Estimated ~14 component files + 8 test files. Within range for a single spec.
- [x] **Ambiguity check:** "Mobile fallback" open question explicitly flagged for implementation-time decision. "Theme clash" risk called out.
- [x] **Type consistency:** `layers: {listings, stations, schools}` shape is consistent across `MapView` props, `MapLayersPopover` props, and state model.
- [x] **Verification fail-fast:** full playwright suite must pass on prod URL with real listings; can't pass with empty data.
