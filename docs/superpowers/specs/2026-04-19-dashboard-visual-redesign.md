# Dashboard Visual Redesign — Design Spec

## Overview

Redesign the Property Dashboard with warm, inviting visuals inspired by Airbnb — image-forward cards, a cream color scheme, and improved sort/filter controls. Applies to both the list view (`/dashboard`) and the map sidebar (`/dashboard/map`).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Card layout | Image top, details bottom | Airbnb-style, showcases photography |
| Sort order | Score ↓, then Price as tiebreaker | Matches user priority (score first) |
| Sort control | Dropdown in filter bar | Already has filter bar, simple addition |
| Overall style | Warm & inviting | Cream backgrounds, warm accents, rounded corners |

## Color Palette

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#F9F7F4` | Page background — warm off-white |
| Card background | `#FFFFFF` | White cards on warm background |
| Primary accent | `#E07A5F` | Terracotta — buttons, active states, score badge |
| Secondary accent | `#3D405B` | Dark slate — headings, prices |
| Text primary | `#2D2D2D` | Near-black for body text |
| Text muted | `#8B8B8B` | Secondary text, metadata |
| Border | `#E8E4E0` | Warm gray borders |
| Success | `#81B29A` | Green — available status |
| Error | `#E07A5F` | Same as primary accent |

## Typography

- **Headings**: `DM Sans` (Google Font) — friendly, modern, warm
- **Body**: `DM Sans` — consistent, clean
- **Price**: Bold, `#3D405B`, slightly larger
- **Score badge**: Bold, white on `#E07A5F`

## Card Component

### Image Area
- Full-width image, 16:10 aspect ratio
- `object-fit: cover` — photos fill the area without distortion
- Fallback: warm gray placeholder (`#E8E4E0`) with house icon if `image_url` is null
- Rounded top corners (`rounded-xl`)
- Subtle shadow below image

### Details Area
- White background, rounded bottom corners
- Padding: 16px
- **Title**: 1-2 lines, `line-clamp-2`, font-medium, `#2D2D2D`
- **Price**: Bold, `#3D405B`, `€` prefix, no decimals — `€420,000`
- **Meta row**: Area (m²), rooms, district badge
- **District badge**: Small pill, `#F9F7F4` background, `#8B8B8B` text — e.g., `1060`
- **Score badge**: Top-right of image, `#E07A5F` background, white text — e.g., `Score 78`
- **Source badge**: Bottom-right of image, small white pill with source abbreviation (`WH`, `DS`, `IK`)

### States
- **Hover**: Card lifts slightly (`shadow-md` → `shadow-lg`, `translateY(-2px)`), 200ms transition
- **Cursor**: `cursor-pointer`
- **Broken image**: Gray placeholder, not broken icon

## Filter Bar (Updated)

Keep existing filter inputs (min score, district). Add:

```
[Sorted by: ▼ Score (high to low)]
```

Dropdown options:
- Score (high to low) — **default**
- Price (low to high)
- Price (high to low)
- Newest first
- Largest first (area m²)

Dropdown styling: warm rounded border, cream background, terracotta accent on selected.

## Sort Dropdown Implementation

Add to `FilterBar.tsx`:

```typescript
const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'price_asc', label: 'Price (low to high)' },
  { value: 'price_desc', label: 'Price (high to low)' },
  { value: 'date_desc', label: 'Newest first' },
  { value: 'area_desc', label: 'Largest first' },
] as const;

type SortOption = typeof SORT_OPTIONS[number]['value'];
```

Add `sortBy: SortOption` prop to `FilterBar`. On change, call `onSortChange` callback.

Update `dashboard/page.tsx` and `map/page.tsx` to pass `sortBy` to API and re-fetch when changed.

Update API `top/route.ts` and `map/route.ts` to accept `sort` param:
- `score_desc` → `{ score: -1 }` (default)
- `price_asc` → `{ price_total: 1 }`
- `price_desc` → `{ price_total: -1 }`
- `date_desc` → `{ processed_at: -1 }`
- `area_desc` → `{ area_m2: -1 }`

## ListingCard (New Design)

### New Layout

```
┌──────────────────────────────┐
│  [IMAGE: 16:10 ratio]    [78]
│                         [WH] │  ← score badge + source badge
├──────────────────────────────┤
│  3-Zimmer-Wohnung in        │
│  Leopoldstadt               │  ← title (line-clamp-2)
│                              │
│  €420,000                   │  ← bold price
│  75m² · 3 rooms   [1060]   │  ← meta + district badge
└──────────────────────────────┘
```

### Implementation

In `ListingCard.tsx`:
- Wrap card in a `div` with `overflow-hidden rounded-xl shadow-sm bg-white hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-pointer`
- Image area: `relative` with absolute-positioned score badge (top-2 right-2) and source badge (bottom-2 left-2)
- Use `aspect-video` or fixed `h-40` for image container
- Conditionally render `<img>` or fallback div

In `ListingSidebar.tsx`:
- Same card design (reuse `ListingCard` component or extract shared design)
- Cards are selectable — on click call `onSelect(listing)`

## Map Page — MapView Component

No major changes to map behavior. Update pin popup to match warm style:
- Popup background: white, rounded, warm shadow
- Title: `#3D405B` bold
- Price: `#E07A5F` terracotta
- Use same card fonts

## Module Design

### Module: ListingCard (Redesign)
- **Responsibility:** Display a single listing as a card with image top, details bottom
- **Interface:** Props: `listing: ListingBase | MapListing`, `onClick: (id: string) => void`
- **Dependencies:** None — pure presentational
- **Size target:** ~100 lines

### Module: FilterBar (Sort Addition)
- **Responsibility:** Filter inputs + sort dropdown, emits filter/sort changes
- **Interface:** Props: `onSortChange: (sort: SortOption) => void`, existing filter props
- **Dependencies:** None
- **Size target:** ~80 lines

### Module: Sort Dropdown
- **Responsibility:** Styled select with warm theme matching design system
- **Interface:** Inside FilterBar, reads/writes `sortBy` state
- **Dependencies:** DM Sans font loaded globally
- **Size target:** ~30 lines

## Implementation Tasks

1. Add DM Sans font to `app/layout.tsx` via Google Fonts
2. Update `globals.css` with warm color variables (CSS custom properties)
3. Add `sortBy` prop and dropdown to `FilterBar.tsx`
4. Update `dashboard/page.tsx` to handle sort state and pass to API
5. Update `top/route.ts` to accept `sort` query param
6. Update `map/route.ts` to accept `sort` query param (same sort options)
7. Redesign `ListingCard.tsx` with image-top layout
8. Update `ListingSidebar.tsx` to use same card design
9. Verify TypeScript compiles
10. Live test with real data

## Anti-Goals

- Do NOT change the map pin behavior or clustering
- Do NOT add authentication
- Do NOT change the detail modal design (already has image fix)
- Do NOT add dark mode
