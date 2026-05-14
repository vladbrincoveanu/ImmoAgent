# Map Redesign — Booking.com Style

**Date:** 2026-05-14  
**Status:** Approved  
**Approach:** B — Full Booking.com Desktop

---

## Goal

Replace the current unusable map view (tiny dots, Leaflet popups, sidebar never updates to viewport) with a booking.com-style experience: price-label pins, viewport-filtered sidebar, floating selected card at map bottom, bidirectional hover sync.

---

## Scope

Desktop primary. Mobile bottom sheet untouched (out of scope). All changes are in `dashboard/`.

---

## Architecture

`map/page.tsx` is the single state owner. It passes data down into `MapView`, `ListingSidebar`, and the new `SelectedCard` overlay. No new API endpoints — viewport filtering is entirely client-side against the already-fetched `listings` array.

```
map/page.tsx
  ├── MapView.tsx          (modified — price pins, bounds tracking, hover events)
  ├── ListingSidebar.tsx   (modified — viewport count, hover sync, inline sort)
  ├── SelectedCard.tsx     (new — floating card over map bottom)
  └── ListingDetail.tsx    (unchanged — opened from SelectedCard "View details")
```

---

## State Changes in `map/page.tsx`

New state added:

```ts
const [hoveredId, setHoveredId] = useState<string | null>(null);
const [bounds, setBounds] = useState<L.LatLngBounds | null>(null);
```

Existing state kept: `highlightedId`, `detailId`, `listings`, `filteredListings`, `loading`, `minScore`, `district`, `sortBy`, `maxPrice`, `showUnfinanceable`.

New derived state via `useMemo`:

```ts
const viewportListings = useMemo(() => {
  if (!bounds) return filteredListings;
  return filteredListings.filter(
    (l) => l.coordinates != null && bounds.contains([l.coordinates.lat, l.coordinates.lon])
  );
}, [filteredListings, bounds]);
```

Before first `moveend` fires (`bounds` is null), sidebar shows all `filteredListings` — no flash of empty state.

---

## Module: MapView

- **Responsibility:** Renders Leaflet map with price-label divIcon pins; fires hover, select, and bounds-change events upward; owns no state.
- **Interface:**
  - Props in: `listings: MapListing[]`, `highlightedId: string | null`, `hoveredId: string | null`, `onPinClick: (l: MapListing) => void`, `onHover: (id: string) => void`, `onHoverEnd: () => void`, `onBoundsChange: (b: L.LatLngBounds) => void`, `onMapClick: () => void`
  - Props removed: `selectedListing: MapListing | null` (replaced by `highlightedId` string — MapView looks up the listing itself)
- **Dependencies:** `leaflet`, `react-leaflet`, `MapListing` type
- **Size target:** ~200 lines; `BoundsTracker` and `MapClickHandler` are small inner components

### Price-label pin format

```ts
function createPriceIcon(listing: MapListing, state: 'default' | 'hovered' | 'selected'): L.DivIcon {
  const price = listing.price_total
    ? `€${Math.round(listing.price_total / 1000)}k`
    : null;
  const color =
    state === 'selected' ? '#E07A5F'
    : state === 'hovered' ? '#c96a4f'
    : listing.coordinate_source === 'exact' ? '#ef4444'
    : listing.coordinate_source === 'landmark' ? '#f97316'
    : '#3B82F6';
  const scale = state === 'selected' ? 'scale(1.25)' : 'scale(1)';

  if (!price) {
    // null-price: small dot fallback (same as before)
    return L.divIcon({ html: `<div style="background:${color};width:10px;height:10px;border-radius:50%;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);transform:${scale}"></div>`, iconSize: [10,10], iconAnchor: [5,5], className: '' });
  }

  return L.divIcon({
    html: `<div style="background:${color};color:white;padding:3px 7px;border-radius:12px;font-size:11px;font-weight:700;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.35);transform:${scale};transform-origin:center bottom;border:1.5px solid rgba(255,255,255,0.4)">${price}</div>`,
    iconSize: [56, 22],
    iconAnchor: [28, 22],
    className: '',
  });
}
```

### BoundsTracker (inner component)

```tsx
function BoundsTracker({ onBoundsChange }: { onBoundsChange: (b: L.LatLngBounds) => void }) {
  const map = useMap();
  useMapEvents({
    moveend: () => onBoundsChange(map.getBounds()),
    zoomend: () => onBoundsChange(map.getBounds()),
  });
  useEffect(() => { onBoundsChange(map.getBounds()); }, []);
  return null;
}
```

Fires once on mount (initial bounds), then on every `moveend`/`zoomend`. No debounce — Leaflet fires these once per gesture end, not per pixel.

### MapViewController — pan-to-selected removed

`MapViewController` component is deleted entirely. The floating `SelectedCard` shows the property in-place; the map does not pan. No saved-viewport restore logic needed.

### Hover + selected icon update

```tsx
useEffect(() => {
  listings.forEach((l) => {
    const marker = markerRefs.current.get(l._id);
    if (!marker) return;
    const state =
      l._id === highlightedId ? 'selected'
      : l._id === hoveredId ? 'hovered'
      : 'default';
    marker.setIcon(createPriceIcon(l, state));
  });
}, [listings, highlightedId, hoveredId]);
```

Runs on every `highlightedId` or `hoveredId` change. Iterates all markers to reset previous states correctly (no stale hovered icon left behind).

---

## Module: BoundsTracker

Extracted above as inner component of MapView. Not a separate file.

---

## Module: SelectedCard

- **Responsibility:** Floating overlay card shown when a listing is selected on the map. Shows key listing info and a "View details" CTA.
- **Interface:**
  - Props: `listing: MapListing | null`, `onClose: () => void`, `onViewDetails: () => void`
  - Renders null when `listing` is null
- **Dependencies:** `MapListing` type, `EquityBadge`
- **Size target:** ~80 lines

```tsx
// Positioned absolute over the map area, bottom-center
// Visible only when listing != null
<div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] w-[340px] bg-white rounded-xl shadow-xl border border-border flex gap-3 p-3">
  {/* image 72×72 */}
  {/* title, price, score badge, EquityBadge */}
  {/* "View details →" button + ✕ close */}
</div>
```

Dismiss paths:
1. Click ✕ button → `onClose()`
2. Click map background → `onMapClick` in MapView → page calls `setHighlightedId(null)` → `listing` prop becomes null → card disappears

---

## Module: ListingSidebar

- **Responsibility:** Scrollable list of viewport-visible listings with hover sync and sort control.
- **Interface:**
  - New props added: `viewportCount: number`, `hoveredId: string | null`, `onHover: (id: string) => void`, `onHoverEnd: () => void`
  - Existing props kept: `listings` (now receives `viewportListings` from page), `selectedId`, `onSelect`, `sortBy`, `onSortChange`, `onRefresh`, `minScore`, `onMinScoreChange`, `district`, `onDistrictChange`
- **Dependencies:** `MapListing` type, `FilterBar` (existing, unchanged)
- **Size target:** ~120 lines

Header replaces `LISTINGS (N)` counter with `N in view` phrasing:

```tsx
<div className="px-3 py-2 text-xs text-gray-500 font-medium flex items-center justify-between">
  <span>{viewportCount} in view</span>
  <select value={sortBy} onChange={...} className="text-xs border-0 bg-transparent">...</select>
</div>
```

Card hover wiring:

```tsx
<div
  onMouseEnter={() => onHover(l._id)}
  onMouseLeave={() => onHoverEnd()}
  ...
>
```

---

## Changes to `map/page.tsx`

```tsx
// New state
const [hoveredId, setHoveredId] = useState<string | null>(null);
const [bounds, setBounds] = useState<L.LatLngBounds | null>(null);

// New derived
const viewportListings = useMemo(() => {
  if (!bounds) return filteredListings;
  return filteredListings.filter(
    (l) => l.coordinates != null && bounds.contains([l.coordinates.lat, l.coordinates.lon])
  );
}, [filteredListings, bounds]);

// MapView prop changes
<MapView
  listings={filteredListings}        // all listings with coords → all pins shown
  highlightedId={highlightedId}
  hoveredId={hoveredId}
  onPinClick={handlePinClick}
  onHover={setHoveredId}
  onHoverEnd={() => setHoveredId(null)}
  onBoundsChange={setBounds}
  onMapClick={handleCloseDetail}
/>

// SelectedCard overlay (inside the flex-1 relative map div)
<SelectedCard
  listing={highlightedListing}
  onClose={() => setHighlightedId(null)}
  onViewDetails={() => setDetailId(highlightedId)}
/>

// ListingSidebar prop changes
<ListingSidebar
  listings={viewportListings}        // only viewport listings
  viewportCount={viewportListings.length}
  hoveredId={hoveredId}
  onHover={setHoveredId}
  onHoverEnd={() => setHoveredId(null)}
  ...existing props...
/>
```

Note: `MapView` still receives `filteredListings` (not `viewportListings`) so all pins appear on the map. Only the sidebar filters to viewport.

---

## Files Modified

| File | Change |
|------|--------|
| `dashboard/components/MapView.tsx` | Replace Marker+Popup with price-label divIcon; add `BoundsTracker`; add hover props; remove `MapViewController`; add `onBoundsChange`, `hoveredId`, `onHover`, `onHoverEnd` props |
| `dashboard/components/ListingSidebar.tsx` | Add `viewportCount`, `hoveredId`, `onHover`, `onHoverEnd` props; add hover wiring to cards; replace LISTINGS counter with "N in view" |
| `dashboard/app/dashboard/map/page.tsx` | Add `hoveredId` + `bounds` state; add `viewportListings` useMemo; render `SelectedCard`; update MapView + ListingSidebar props |

## Files Created

| File | Purpose |
|------|---------|
| `dashboard/components/SelectedCard.tsx` | Floating card overlay for selected listing |

## Files Deleted

| File | Reason |
|------|--------|
| `dashboard/components/MapPopup.tsx` | Replaced by SelectedCard; Leaflet popups gone |

---

## What Does NOT Change

- Mobile BottomSheet — untouched
- `/dashboard` page (cards grid) — untouched
- All API routes — untouched
- `ListingDetail` modal — untouched (opened from SelectedCard CTA)
- `FilterDrawer` — untouched
- `MapLegend` — untouched
- Existing score/price/unfinanceable filters — untouched

---

## Edge Cases

1. **All listings have null coords** → `viewportListings` is empty, sidebar shows "0 in view", map is empty. Correct feedback.
2. **User pans to empty area** → sidebar shows "0 in view". Expected.
3. **Selected listing panned out of view** → SelectedCard stays visible (bound to `highlightedId` state, not viewport), pin remains on map (MapView uses `filteredListings` not `viewportListings`). Correct.
4. **hoveredId + highlightedId both set** → selected styling wins (`highlightedId` check comes first in ternary).
5. **Price is null** → pin renders as small dot (existing fallback), SelectedCard shows "—" for price.
6. **Resize while SelectedCard open** → card is `left-1/2 -translate-x-1/2`, stays centered. No issue.
