# Mobile UX Overhaul — Design Spec

**Date:** 2026-04-25
**Phase:** 1 of 5 — Bug Fixes + Performance Foundation
**Scope:** Mobile-responsive redesign of the immo-scouter dashboard

---

## Overview

The dashboard is currently desktop-first and breaks on mobile. This spec redesigns the layout using a bottom-sheet pattern for the map page and stacked layout for the main dashboard, with touch-target fixes throughout.

---

## Layout Architecture

### Map Page (`/dashboard/map`)

| Breakpoint | Layout |
|------------|--------|
| Mobile (<768px) | Full-screen map + bottom sheet (draggable drawer) |
| Desktop (≥768px) | Existing sidebar + map split (unchanged) |

**Bottom Sheet States:**
- **Collapsed**: 64px — shows handle bar + listing count badge + expand chevron
- **Half-expanded**: ~45% viewport height — shows compact listing cards (scrollable)
- **Fully expanded**: ~90% viewport height — shows full `ListingSidebar` content

The sheet is **draggable** — user can drag handle to snap between states.

### Dashboard Page (`/dashboard`)

| Breakpoint | Layout |
|------------|--------|
| Mobile (<768px) | Single-column stacked cards + collapsible filter drawer |
| Desktop (≥768px) | Existing 3-column grid (unchanged) |

---

## Component: BottomSheet

**File:** `dashboard/components/BottomSheet.tsx` (new)

**Responsibility:** A draggable drawer overlay rendered above the map.

**Interface:**
- `children: React.ReactNode` — content to render inside the sheet
- `snapPoints: [collapsed: number, half: number, full: number]` — heights in px for each snap state
- `defaultState?: 'collapsed' | 'half' | 'full'`

**Behavior:**
- Drag handle at top — pointer drag moves the sheet
- On pointer release, animate to nearest snap point
- Touch-friendly: handle is 44px tall minimum
- Backdrop tap on map area collapses sheet
- Does NOT block map interaction when collapsed (map is fully visible)

**States:**
```typescript
type SheetState = 'collapsed' | 'half' | 'full';
```

**Visual:**
- Rounded top corners (16px radius)
- White background with subtle shadow upward
- Handle bar: 40px wide, 4px tall, centered, gray (#D1D5DB), rounded

---

## Component: FilterDrawer

**File:** `dashboard/components/FilterDrawer.tsx` (new)

**Responsibility:** Full-screen modal on mobile that contains filter controls.

**Interface:**
- `open: boolean`
- `onClose: () => void`
- Same props as `FilterBar` — `minScore`, `onMinScoreChange`, `district`, `onDistrictChange`, `sortBy`, `onSortChange`

**Behavior:**
- Triggered by a floating "Filters" button on mobile (bottom-right FAB)
- Slides up as full-screen modal
- "Apply" button closes and triggers `onRefresh`
- "Reset" clears filters to defaults

**Visual:**
- White background, full-screen
- Header with title + close (X) button
- Same form controls as FilterBar but vertically stacked with more spacing

---

## Map Page Modifications

**File:** `dashboard/app/dashboard/map/page.tsx`

**Changes:**
1. Import `BottomSheet` and wrap `ListingSidebar` with it
2. Add CSS class `md:block hidden` to sidebar (hide on mobile, BottomSheet handles it)
3. Add `<FilterDrawer>` trigger button (mobile only)
4. No changes to desktop layout — sidebar remains visible

**BottomSheet Integration:**
```tsx
<BottomSheet
  snapPoints={[64, window.innerHeight * 0.45, window.innerHeight * 0.9]}
  defaultState="half"
>
  <ListingSidebar
    listings={listings}
    selectedId={selectedId}
    onSelect={setSelectedId}
    loading={loading}
    sortBy={sortBy}
    onSortChange={setSortBy}
  />
</BottomSheet>
```

---

## Dashboard Page Modifications

**File:** `dashboard/app/dashboard/page.tsx`

**Changes:**
1. Add `<FilterDrawer>` with trigger FAB (mobile only, visible when drawer closed)
2. On mobile: change grid to `grid-cols-1` (single column)
3. FilterBar becomes invisible on mobile (replaced by FilterDrawer)
4. Header becomes sticky on mobile

---

## Touch Target Fixes

Apply globally via `globals.css` or a dedicated `TouchTargets.css`:

```css
/* Mobile touch targets */
@media (max-width: 767px) {
  button, a, [role="button"] {
    min-height: 44px;
    min-width: 44px;
  }
  select, input[type="text"], input[type="number"] {
    min-height: 44px;
  }
}
```

Additional fixes in `MapView.tsx`:
- Map marker hit area: already handled via Leaflet marker sizing
- Popup close button: `min-w-[44px] min-h-[44px]`

---

## Responsive Filter Bar

`FilterBar.tsx` gets a responsive variant:

- **Desktop**: Inline horizontal layout (current behavior)
- **Mobile**: Hidden from view, replaced by FAB

```tsx
// In FilterBar.tsx — wrap sort/score/district in desktop-only div
<div className="hidden md:flex flex-wrap gap-3 mb-6">
  {/* existing FilterBar content */}
</div>
```

---

## Module: BottomSheet

- **Responsibility:** Draggable drawer overlay with snap-to states
- **Interface:** `children`, `snapPoints`, `defaultState`; exposes `SheetState` to parent via callback if needed
- **Dependencies:** React, pointer events API, CSS transforms
- **Size target:** ~180 lines

## Module: FilterDrawer

- **Responsibility:** Full-screen mobile filter modal
- **Interface:** `open`, `onClose`, `FilterBar` props passthrough
- **Dependencies:** React, `FilterBar` component
- **Size target:** ~100 lines

## Module: MapPage mobile wrapper

- **Responsibility:** Conditionally renders `BottomSheet` on mobile, sidebar on desktop
- **Interface:** No new props — adapts existing `ListingSidebar` layout
- **Dependencies:** `BottomSheet`, `ListingSidebar`, `FilterDrawer`
- **Size target:** ~30 lines changed

## Module: DashboardPage mobile card layout

- **Responsibility:** Single-column cards + FAB trigger on mobile
- **Interface:** No new props
- **Dependencies:** `FilterDrawer`
- **Size target:** ~20 lines changed

---

## Visual Design

| Token | Value | Usage |
|-------|-------|-------|
| Bottom sheet bg | `#FFFFFF` | Sheet background |
| Handle bar | `#D1D5DB` | Handle indicator |
| FAB bg | `var(--color-accent)` (#E07A5F) | Filter trigger button |
| FAB icon | `#FFFFFF` | Filter icon |
| Sheet shadow | `0 -4px 20px rgba(0,0,0,0.08)` | Elevation |

---

## Edge Cases

1. **No listings**: Bottom sheet shows empty state "No listings found" centered in the sheet
2. **Keyboard open**: On mobile with software keyboard, sheet should not overlap — half-expanded height should account for viewport resize
3. **Orientation change**: Sheet recalculates snap points on resize
4. **Selected listing on mobile**: When a listing is selected (modal opens), the bottom sheet stays in current state (doesn't auto-expand)
5. **Slow network**: Loading spinner in the sheet while listings fetch

---

## Out of Scope

- Changes to API routes (no backend changes)
- Changes to `ListingDetail` modal
- Changes to `MapView` marker rendering
- Desktop layout modifications
- New features beyond mobile UX

---

## Spec Coverage

| Requirement | Section |
|-------------|---------|
| Bottom sheet map + listing layout | Component: BottomSheet, Map Page Modifications |
| Stacked cards on mobile | Dashboard Page Modifications |
| Touch targets ≥44px | Touch Target Fixes |
| Filter FAB + drawer | Component: FilterDrawer |
| Responsive filter bar | Responsive Filter Bar |
| Draggable snap behavior | Component: BottomSheet |
