# Map Pin Preview Popup — Design Spec

> **Goal:** When clicking a map pin, show an enriched property preview popup with image, score badge, title, price (with `~` for estimated), area, rooms, and district — matching the ListingCard style.

## Context

The current map pin popup (react-leaflet `<Popup>`) shows only text: title, price, area/rooms/score. Clicking a pin should show a rich preview matching the ListingCard so users can evaluate the property without leaving the map. The `MapListing` type already has all required fields including `image_url`.

## Architecture

```
Marker click → onPinClick(listing) → selectedListing state updates
    → FlyTo animates map to listing
    → Marker re-renders with selected styling
    → Leaflet popup auto-opens on the selected marker
```

The popup content is replaced with an enriched card layout. Navigation on "View Details →" goes to `/dashboard/{id}` (existing behavior).

## Visual Layout

```
┌─────────────────────────────┐  ← popup: min-w-[240px]
│  [IMAGE 240×150]            │  ← aspect-[16/10], object-cover
│  ┌─────┐              [54] │  ← score badge top-right (white bg)
│  └─────┘ WH                │  ← source badge bottom-left
├─────────────────────────────┤
│  Charmante 4-Zimmer...       │  ← line-clamp-2, font-medium
│  ~€581,000                  │  ← ~ prefix if estimated, font-bold
│  83m² · 4 rooms             │  ← text-xs text-muted
│  1070                       │  ← district badge right-aligned
│  [View Details →]           │  ← text-xs text-blue-600, cursor-pointer
└─────────────────────────────┘
```

## Design Tokens (from existing warm system)

| Token | Value | Usage |
|-------|-------|-------|
| `bg-white` | `#FFFFFF` | Popup card background |
| `text-heading` | `#134E4A` | Title, price |
| `text-accent` | `#E07A5F` | Score badge |
| `text-muted` | `#6B7280` | Area/rooms text |
| `bg-warm-bg` | `#F5F0EB` | District badge |
| `border-border` | `#E5E1DC` | Popup border |
| `font-dm-sans` | DM Sans | All popup text |

## Components

### Module: MapPopup.tsx (new file)
- **Responsibility:** Renders an enriched property preview card inside a Leaflet popup
- **Interface:**
  - Props: `listing: MapListing`, `onViewDetails: (id: string) => void`
  - Renders image, score badge, source badge, title, price, area/rooms, district, CTA
- **Dependencies:** None — pure presentational, all data via props
- **Size target:** ~120 lines

### Module: MapView.tsx (modified)
- **Responsibility:** Replace existing `<Popup>` JSX with `<MapPopup>` component
- **Interface:** No change to `MapViewProps` — passes through to MapPopup
- **Dependencies:** `MapPopup` component
- **Size target:** ~15 lines changed

## Data Flow

```
selectedListing state (MapPage.tsx)
    → passed as prop to MapView
    → MapView passes to Marker (for styling)
    → MapView passes to MapPopup (for rendering)
    → onPinClick updates selectedListing
    → Leaflet opens popup on the clicked marker
```

## Interaction Details

| Action | Result |
|--------|--------|
| Click pin | Map flies to location, popup opens with preview |
| Click "View Details →" | Navigate to `/dashboard/{id}` |
| Click another pin | Previous popup closes, new one opens, map flies to new location |
| Click map background | Popup closes (Leaflet default) |

## Image Handling

- Use `listing.image_url` (from `MapListing`)
- `onError`: show fallback house SVG icon (same as ListingCard)
- No `image_url`: show fallback icon

## Edge Cases

| Case | Behavior |
|------|----------|
| No image | Show house SVG fallback icon |
| `price_total: null`, `area_m2: null` | Show "Price on request" |
| `price_total: null`, `area_m2: 83` | Show `~€581,000` |
| `title: null` | Show "Untitled" |
| No `bezirk` | Hide district badge row |
| `score: null` | Hide score badge |

## Files to Modify

| File | Action |
|------|--------|
| `dashboard/components/MapPopup.tsx` | Create — enriched popup component |
| `dashboard/components/MapView.tsx` | Modify — replace Popup JSX with MapPopup |

## Verification

- Clicking any pin shows popup with image + all card details
- Estimated prices show `~` prefix
- "View Details →" navigates to `/dashboard/{id}`
- Popup matches ListingCard styling (score badge, source badge, district badge)
- Build succeeds: `npm run build`
- No new TypeScript errors
