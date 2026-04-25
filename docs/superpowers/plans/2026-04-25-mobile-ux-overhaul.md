# Mobile UX Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the immo-scouter dashboard fully functional on mobile using a bottom-sheet pattern for the map page and stacked layout for the dashboard page, with touch-target fixes throughout.

**Architecture:** BottomSheet component wraps the map page's ListingSidebar on mobile, providing a draggable drawer with three snap states. FilterBar becomes desktop-only on the map page, replaced by a FilterDrawer modal triggered via FAB. Dashboard page switches to single-column on mobile. Touch target minimums enforced via CSS.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, CSS custom properties, Pointer Events API

---

## File Map

```
dashboard/
  app/
    globals.css                 # Modify — add mobile touch target CSS
    dashboard/
      page.tsx                 # Modify — mobile single-column grid + FAB
      map/
        page.tsx               # Modify — BottomSheet on mobile, FilterDrawer FAB
  components/
    BottomSheet.tsx            # Create — draggable drawer with snap states
    FilterDrawer.tsx          # Create — full-screen mobile filter modal
    FilterBar.tsx             # Modify — wrap in md:flex desktop-only div
```

---

## Task 1: Add mobile touch target CSS to globals.css

**Files:**
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Read current globals.css and append mobile touch target CSS**

Read `dashboard/app/globals.css`. Add the following at the end of the file (after the existing content, before any `@layer` or other directives if any):

```css
/* Mobile touch targets — enforce 44px minimum */
@media (max-width: 767px) {
  button,
  a,
  [role="button"],
  .btn {
    min-height: 44px;
    min-width: 44px;
  }

  input[type="text"],
  input[type="number"],
  input[type="email"],
  input[type="tel"],
  select {
    min-height: 44px;
    font-size: 16px; /* prevents iOS zoom on focus */
  }

  select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%238B8B8B' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/globals.css
git commit -m "feat(dashboard): enforce 44px touch targets on mobile"
```

---

## Task 2: Create BottomSheet component

**Files:**
- Create: `dashboard/components/BottomSheet.tsx`

- [ ] **Step 1: Write the BottomSheet component**

Create `dashboard/components/BottomSheet.tsx`:

```tsx
'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';

export type SheetState = 'collapsed' | 'half' | 'full';

interface BottomSheetProps {
  children: React.ReactNode;
  snapPoints: [collapsed: number, half: number, full: number];
  defaultState?: SheetState;
  onStateChange?: (state: SheetState) => void;
  count?: number; // number of listings to show in collapsed badge
}

const STATE_KEYS: SheetState[] = ['collapsed', 'half', 'full'];

export function BottomSheet({
  children,
  snapPoints,
  defaultState = 'half',
  onStateChange,
  count,
}: BottomSheetProps) {
  const [state, setState] = useState<SheetState>(defaultState);
  const [translateY, setTranslateY] = useState(0);
  const sheetRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef(0);
  const dragStartTranslate = useRef(0);
  const isDragging = useRef(false);

  const defaultHeights: Record<SheetState, number> = {
    collapsed: snapPoints[0],
    half: snapPoints[1],
    full: snapPoints[2],
  };

  // Initialize position based on defaultState
  useEffect(() => {
    const height = defaultHeights[defaultState];
    setTranslateY(window.innerHeight - height);
  }, [defaultState]);

  const snapToNearest = useCallback((currentY: number) => {
    const windowH = window.innerHeight;
    const heights = [snapPoints[0], snapPoints[1], snapPoints[2]].map((h) => windowH - h);
    let nearestIdx = 0;
    let nearestDist = Infinity;
    heights.forEach((targetY, idx) => {
      const dist = Math.abs(currentY - targetY);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = idx;
      }
    });
    const newState: SheetState = STATE_KEYS[nearestIdx];
    setState(newState);
    setTranslateY(heights[nearestIdx]);
    onStateChange?.(newState);
  }, [snapPoints, onStateChange]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    isDragging.current = true;
    dragStartY.current = e.clientY;
    dragStartTranslate.current = translateY;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [translateY]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current) return;
    const delta = dragStartY.current - e.clientY;
    const newTranslate = Math.max(
      window.innerHeight - snapPoints[2], // can't go above full
      Math.min(window.innerHeight - snapPoints[0], dragStartTranslate.current + delta) // can't go below collapsed
    );
    setTranslateY(newTranslate);
  }, [snapPoints]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    snapToNearest(translateY);
  }, [translateY, snapToNearest]);

  // Handle backdrop tap to collapse
  const handleBackdropClick = useCallback(() => {
    setState('collapsed');
    setTranslateY(window.innerHeight - snapPoints[0]);
    onStateChange?.('collapsed');
  }, [snapPoints, onStateChange]);

  const sheetStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    height: snapPoints[2],
    transform: `translateY(${translateY}px)`,
    transition: isDragging.current ? 'none' : 'transform 200ms ease-out',
    zIndex: 1000,
    display: 'flex',
    flexDirection: 'column',
  };

  return (
    <>
      {/* Backdrop — only visible when sheet is not collapsed */}
      {state !== 'collapsed' && (
        <div
          className="fixed inset-0 bg-black/10 z-50 md:hidden"
          onClick={handleBackdropClick}
        />
      )}

      {/* Sheet */}
      <div
        ref={sheetRef}
        className="bg-white rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.08)] flex flex-col overflow-hidden"
        style={sheetStyle}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Drag handle */}
        <div className="shrink-0 flex flex-col items-center pt-3 pb-2 cursor-grab active:cursor-grabbing select-none">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
          <div className="flex items-center gap-2 mt-2">
            {count !== undefined && (
              <span className="text-xs font-medium text-muted">
                {count} listings
              </span>
            )}
            {state === 'collapsed' ? (
              <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            ) : state === 'full' ? (
              <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            ) : (
              <div className="w-4" />
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/BottomSheet.tsx
git commit -m "feat(dashboard): add BottomSheet draggable drawer component"
```

---

## Task 3: Create FilterDrawer component

**Files:**
- Create: `dashboard/components/FilterDrawer.tsx`

- [ ] **Step 1: Write the FilterDrawer component**

Create `dashboard/components/FilterDrawer.tsx`:

```tsx
'use client';

import React, { useState, useEffect } from 'react';
import { FilterBar, SortOption } from './FilterBar';

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
}

export function FilterDrawer({
  open,
  onClose,
  minScore,
  onMinScoreChange,
  district,
  onDistrictChange,
  onRefresh,
  sortBy,
  onSortChange,
}: FilterDrawerProps) {
  // Local state so "Reset" doesn't affect parent until Apply
  const [localMinScore, setLocalMinScore] = useState(minScore);
  const [localDistrict, setLocalDistrict] = useState(district);
  const [localSortBy, setLocalSortBy] = useState(sortBy);

  // Sync local state when props change (e.g., parent resets)
  useEffect(() => {
    setLocalMinScore(minScore);
    setLocalDistrict(district);
    setLocalSortBy(sortBy);
  }, [minScore, district, sortBy]);

  if (!open) return null;

  const handleApply = () => {
    onMinScoreChange(localMinScore);
    onDistrictChange(localDistrict);
    onSortChange(localSortBy);
    onRefresh();
    onClose();
  };

  const handleReset = () => {
    setLocalMinScore('0');
    setLocalDistrict('');
    setLocalSortBy('score_desc');
  };

  return (
    <div className="fixed inset-0 z-[200] flex flex-col">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="relative mt-auto bg-white rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.1)] flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-lg font-semibold text-heading">Filters</h2>
          <button
            onClick={onClose}
            className="w-11 h-11 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            aria-label="Close filters"
          >
            <svg className="w-5 h-5 text-text" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Filter form */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Min Score */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Minimum Score</label>
            <input
              type="number"
              min="0"
              max="100"
              value={localMinScore}
              onChange={(e) => setLocalMinScore(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          {/* District */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">District</label>
            <input
              type="text"
              placeholder="e.g. 02"
              value={localDistrict}
              onChange={(e) => setLocalDistrict(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          {/* Sort */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Sort By</label>
            <select
              value={localSortBy}
              onChange={(e) => setLocalSortBy(e.target.value as SortOption)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="score_desc">Score (high to low)</option>
              <option value="price_asc">Price (low to high)</option>
              <option value="price_desc">Price (high to low)</option>
              <option value="date_desc">Newest first</option>
              <option value="area_desc">Largest first</option>
            </select>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-5 py-4 border-t border-border shrink-0">
          <button
            onClick={handleReset}
            className="flex-1 h-12 rounded-lg border border-border text-text font-medium hover:bg-gray-50 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            className="flex-1 h-12 rounded-lg bg-accent text-white font-semibold hover:opacity-90 transition-opacity"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/FilterDrawer.tsx
git commit -m "feat(dashboard): add FilterDrawer full-screen mobile modal"
```

---

## Task 4: Make FilterBar desktop-only on map page

**Files:**
- Modify: `dashboard/components/FilterBar.tsx`

- [ ] **Step 1: Wrap FilterBar in md:flex div**

Read `dashboard/components/FilterBar.tsx`. Find the outer `<div>` that wraps the filter controls and add `className="hidden md:flex flex-wrap gap-3 mb-6"` to it:

Current:
```tsx
<div className="flex flex-wrap gap-3 mb-6">
```

Change to:
```tsx
<div className="hidden md:flex flex-wrap gap-3 mb-6">
```

This hides the inline FilterBar on mobile screens (<768px) — it will be replaced by the FilterDrawer FAB.

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/FilterBar.tsx
git commit -m "feat(dashboard): hide FilterBar on mobile, replaced by FilterDrawer"
```

---

## Task 5: Integrate BottomSheet into map page

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Read current map page**

Read `dashboard/app/dashboard/map/page.tsx`.

- [ ] **Step 2: Import BottomSheet, FilterDrawer, and useState**

Add to the import section:
```tsx
import { BottomSheet } from '@/components/BottomSheet';
import { FilterDrawer } from '@/components/FilterDrawer';
```

- [ ] **Step 3: Add filterDrawerOpen state**

Add after the existing state declarations:
```tsx
const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
```

- [ ] **Step 4: Add snap points calculation**

Add a constant after the state declarations (before fetchListings). Use a function to avoid SSR `window` issues:
```tsx
const getSnapPoints = (): [number, number, number] => {
  const h = typeof window !== 'undefined' ? window.innerHeight : 800;
  return [64, Math.round(h * 0.45), Math.round(h * 0.9)];
};
```

- [ ] **Step 5: Add snapPoints state**

Add after the `filterDrawerOpen` state:
```tsx
const [snapPoints, setSnapPoints] = useState<[number, number, number]>([64, 360, 720]);

useEffect(() => {
  setSnapPoints(getSnapPoints());
  const handleResize = () => setSnapPoints(getSnapPoints());
  window.addEventListener('resize', handleResize);
  return () => window.removeEventListener('resize', handleResize);
}, []);
```

- [ ] **Step 5: Wrap ListingSidebar in BottomSheet, hide sidebar on mobile**

Find the `<ListingSidebar ... />` component and replace it entirely with:

```tsx
{/* Desktop sidebar — hidden on mobile */}
<div className="hidden md:block w-[280px] h-full shrink-0">
  <ListingSidebar
    listings={listings}
    minScore={minScore}
    onMinScoreChange={setMinScore}
    district={district}
    onDistrictChange={setDistrict}
    onRefresh={fetchListings}
    selectedId={selectedId}
    onSelect={handleSidebarSelect}
    sortBy={sortBy}
    onSortChange={setSortBy}
  />
</div>

{/* Mobile bottom sheet */}
<div className="md:hidden flex-1 relative">
  <BottomSheet
    snapPoints={snapPoints}
    defaultState="half"
    count={listings.length}
  >
    <div className="p-3">
      <div className="text-xs text-gray-500 font-medium mb-2">
        LISTINGS ({listings.length})
      </div>
      <div className="flex flex-col gap-1.5">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">No listings match your filters.</p>
        ) : (
          listings.map((l) => (
            <div
              key={l._id}
              onClick={() => handleSidebarSelect(l)}
              className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
                selectedId === l._id
                  ? 'border-accent ring-1 ring-accent'
                  : 'border-border hover:border-muted'
              }`}
            >
              <div className="w-16 h-16 rounded-md overflow-hidden bg-border shrink-0 flex items-center justify-center">
                {l.image_url ? (
                  <img src={l.image_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text line-clamp-1 leading-tight">{l.title || 'Untitled'}</p>
                <p className="font-bold text-heading mt-0.5">
                  {l.price_total ? `€${l.price_total.toLocaleString('de-AT')}` : '—'}
                </p>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`px-1 py-0.5 rounded text-[9px] font-medium text-white ${
                    l.coordinate_source === 'exact' ? 'bg-red-500' : l.coordinate_source === 'landmark' ? 'bg-orange-500' : 'bg-muted'
                  }`}>
                    {l.coordinate_source === 'exact' ? 'Pin' : l.coordinate_source === 'landmark' ? '~' : '—'}
                  </span>
                  {l.score && (
                    <span className="px-1 py-0.5 rounded bg-accent text-white text-[9px] font-medium">{l.score}</span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  </BottomSheet>
</div>
```

- [ ] **Step 6: Add FilterDrawer FAB button and modal**

Find the `<div className="flex-1 relative">` that contains the map (before the `{loading ?` check). Add the FAB button at the bottom-right corner of the map area:

Inside the `<div className="flex-1 relative">` just before the closing `</div>`, add:

```tsx
{/* Mobile filter FAB */}
<button
  onClick={() => setFilterDrawerOpen(true)}
  className="md:hidden absolute bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-50 hover:opacity-90 transition-opacity"
  aria-label="Open filters"
>
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
  </svg>
</button>

{/* Filter drawer modal */}
<FilterDrawer
  open={filterDrawerOpen}
  onClose={() => setFilterDrawerOpen(false)}
  minScore={minScore}
  onMinScoreChange={setMinScore}
  district={district}
  onDistrictChange={setDistrict}
  onRefresh={fetchListings}
  sortBy={sortBy}
  onSortChange={setSortBy}
/>
```

Place the FAB button as the **last child** inside the `<div className="flex-1 relative">` that wraps the MapView and MapLegend.

- [ ] **Step 7: Commit**

```bash
git add dashboard/app/dashboard/map/page.tsx
git commit -m "feat(dashboard): integrate BottomSheet and FilterDrawer on mobile map page"
```

---

## Task 6: Make dashboard page mobile-friendly

**Files:**
- Modify: `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Read current dashboard page**

Read `dashboard/app/dashboard/page.tsx`.

- [ ] **Step 2: Add FilterDrawer import and state**

Add to imports:
```tsx
import { FilterDrawer } from '@/components/FilterDrawer';
```

Add after existing state:
```tsx
const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
```

- [ ] **Step 3: Change grid to responsive columns**

Find:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
```

Change to:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
```

Actually the grid is already responsive (`grid-cols-1` on mobile). The issue is the FilterBar needs to be hidden on mobile and a FAB added. Let's keep the grid as-is but make the FilterBar desktop-only.

- [ ] **Step 4: Add FilterBar desktop-only wrapper and FAB**

The `FilterBar` is already in the page — wrap it in a desktop-only div and add the FAB after the `<main>` content or inside it at the appropriate place.

Find the `<FilterBar ... />` component and replace the surrounding `<div className="flex flex-wrap gap-3 mb-6">` (if it exists inline) or simply add a wrapper div around `<FilterBar>`:

```tsx
{/* Desktop-only filter bar */}
<div className="hidden md:block">
  <FilterBar
    minScore={minScore}
    onMinScoreChange={setMinScore}
    district={district}
    onDistrictChange={setDistrict}
    onRefresh={fetchListings}
    sortBy={sortBy}
    onSortChange={setSortBy}
  />
</div>
```

Then add the FAB and FilterDrawer modal. After the `</main>` closing tag and before the `{selectedId && ...}` modal, add:

```tsx
{/* Mobile filter FAB */}
<button
  onClick={() => setFilterDrawerOpen(true)}
  className="md:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-50 hover:opacity-90 transition-opacity"
  aria-label="Open filters"
>
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
  </svg>
</button>

{/* Filter drawer modal */}
<FilterDrawer
  open={filterDrawerOpen}
  onClose={() => setFilterDrawerOpen(false)}
  minScore={minScore}
  onMinScoreChange={setMinScore}
  district={district}
  onDistrictChange={setDistrict}
  onRefresh={fetchListings}
  sortBy={sortBy}
  onSortChange={setSortBy}
/>
```

- [ ] **Step 5: Make header sticky on mobile**

In the `<header>` element, add `sticky top-0 z-40` and ensure `bg-white` is set so it has a background color when scrolled:

```tsx
<header className="mb-6 md:sticky md:top-0 md:bg-white md:z-40 md:pb-4">
```

And ensure the main element has some bottom padding to account for the FAB:
```tsx
<main className="min-h-screen bg-gray-50 p-6 pb-24 md:pb-6">
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/dashboard/page.tsx
git commit -m "feat(dashboard): add mobile single-column grid, FilterDrawer FAB, sticky header"
```

---

## Task 7: TypeScript compilation check

**Files:**
- None (verification only)

- [ ] **Step 1: Run TypeScript compilation**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit 2>&1
```

Expected: no TypeScript errors.

If there are errors, fix them in the relevant files before proceeding.

- [ ] **Step 2: Dev server smoke test**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npm run dev &
sleep 5
# Test both pages load without console errors
kill %1 2>/dev/null
```

- [ ] **Step 3: Commit only if files were touched** (likely no changes needed here)

---

## Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Bottom sheet map + listing layout | Task 2 (BottomSheet), Task 5 (map page integration) |
| Draggable snap behavior | Task 2 (BottomSheet) |
| Filter FAB + drawer | Task 3 (FilterDrawer), Task 5+6 (integrated into both pages) |
| FilterDrawer full-screen modal | Task 3 |
| Responsive filter bar (desktop-only) | Task 4 |
| Stacked cards on mobile (grid-cols-1) | Task 6 (already existed, header sticky + FAB added) |
| Touch targets ≥44px | Task 1 |
| Mobile bottom sheet on map | Task 5 |
| FilterDrawer on dashboard page | Task 6 |

---

## Type Consistency Check

| Item | Type | Used in |
|------|------|---------|
| `SheetState` | `'collapsed' \| 'half' \| 'full'` | `BottomSheet.tsx` |
| `SortOption` | `'score_desc' \| 'price_asc' \| ...` | `FilterBar.tsx`, `FilterDrawer.tsx`, both page components |
| `FilterDrawerProps` | interface matching `FilterBar` props | `FilterDrawer.tsx` |
| `BottomSheetProps.snapPoints` | `[number, number, number]` | `BottomSheet.tsx`, `map/page.tsx` |
