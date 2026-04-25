# Map Mobile Responsive Design

## Overview

Add mobile-first responsive behavior to the Property Map page without modifying existing desktop functionality. The map view becomes map-first on mobile with a bottom sheet for listings, while desktop retains the existing left sidebar with a new collapse toggle.

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Mobile primary experience | Map-first |
| Pin tap action | Bottom sheet with peek + expand |
| Mobile filters | Filter icon → slide-out drawer |
| Mobile legend | Hidden, in filter drawer |
| Mobile header | Minimal with hamburger |
| Desktop sidebar | Collapsible with mini preview |
| Desktop collapsed behavior | Mini preview updates on new pin select |

---

## Module: BottomSheetPanel

- **Responsibility:** Mobile-only bottom sheet that slides up from bottom on pin tap, showing listing preview with swipe-to-expand gesture
- **Interface:** Props: `isOpen`, `listing`, `onClose`, `onViewDetails`
- **Dependencies:** `react-swipeable`, existing `MapPopup` styles
- **Size target:** ~150 lines

## Module: FilterDrawer

- **Responsibility:** Mobile-only slide-out drawer containing filter controls (min score, district, sort) and map legend
- **Interface:** Props: `isOpen`, `onClose`
- **Dependencies:** Existing `FilterBar` component
- **Size target:** ~100 lines

## Module: CollapsibleSidebar

- **Responsibility:** Desktop-only wrapper that toggles between full sidebar (280px) and mini preview (48px thumbnail)
- **Interface:** Props: `isCollapsed`, `selectedListing`, `onToggle`
- **Dependencies:** Existing `ListingSidebar`
- **Size target:** ~80 lines

## Module: MobileHeader

- **Responsibility:** Slim mobile-only header with hamburger menu and minimal nav
- **Interface:** No props needed
- **Dependencies:** None
- **Size target:** ~30 lines

---

## Responsive Breakpoints

- **Mobile: < 768px** (`sm` and below) — bottom sheet, filter drawer, mobile header
- **Desktop: >= 768px** (`md` and above) — collapsible sidebar, existing header

---

## Implementation Notes

### State Flow
- `selectedId` lives in `page.tsx` (already exists)
- `isBottomSheetOpen` is a new state in `page.tsx` for mobile
- `isFilterDrawerOpen` is a new state in `page.tsx` for mobile
- `isSidebarCollapsed` is a new state in `page.tsx` for desktop
- `MapView` onPinClick already calls `handlePinClick` — no change needed
- `page.tsx` passes `selectedListing` to both `MapView` and the new `BottomSheetPanel`

### Bottom Sheet Behavior
- Default peek height: ~120px (shows thumbnail, title, price)
- Swipe up or tap to expand full screen
- Swipe down to dismiss (closes sheet, does NOT deselect pin — keeps selection)
- "View Details" button opens full `ListingDetail` modal (same as desktop)
- Always rendered in DOM when `selectedListing` exists, visibility controlled by CSS transform

### Filter Drawer Behavior
- Opens from left (like Airbnb)
- Contains: FilterBar controls + MapLegend
- Close on backdrop tap or X button

### Sidebar Collapse Behavior
- Toggle button at top of sidebar (eye icon)
- Collapsed state: 48px wide showing selected listing thumbnail
- Mini preview updates immediately when new pin is selected
- Tap thumbnail to expand sidebar back open

### Mobile Header
- Height: 44px
- Contains: hamburger icon (opens nav drawer), title
- Existing header hidden on mobile via `hidden md:flex`

### New Dependencies
- `react-swipeable` for bottom sheet gestures

---

## Files to Modify

1. `app/dashboard/map/page.tsx` — responsive layout wrapper, new state for mobile panels and sidebar collapse
2. `components/ListingSidebar.tsx` — wrap in collapse logic, add toggle button
3. `components/MapView.tsx` — no changes needed
4. `components/BottomSheetPanel.tsx` — new component
5. `components/FilterDrawer.tsx` — new component
6. `components/MobileHeader.tsx` — new component
7. `app/globals.css` — bottom sheet and drawer animations, CSS custom properties
8. `package.json` — add `react-swipeable` dependency

---

## Out of Scope

- Tablet layout
- Touch gestures on desktop
- Changes to desktop popup behavior
- API changes
