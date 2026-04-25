# Dashboard Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Property Dashboard with warm Airbnb-style visuals — image-top cards, terracotta accents, DM Sans typography, sort dropdown in filter bar.

**Architecture:** Warm color scheme applied via CSS custom properties in globals.css. New ListingCard component with image-top layout replaces the existing text-only card. Sort state lifted to page level, passed to API via sort query param.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, Google Fonts (DM Sans).

---

## File Map

```
dashboard/
  app/
    layout.tsx                  # Modify — add DM Sans font link
    globals.css                 # Modify — add CSS custom properties + warm background
    page.tsx                   # Modify — add sort state, pass to API
    dashboard/
      map/
        page.tsx               # Modify — add sort state, pass to API
    api/
      listings/
        top/route.ts           # Modify — accept sort query param
        map/route.ts          # Modify — accept sort query param
  components/
    FilterBar.tsx              # Modify — add sort dropdown
    ListingCard.tsx            # Modify — image-top layout redesign
    ListingSidebar.tsx         # Modify — use new card design
    ListingDetail.tsx          # No change (already has image fix)
    MapView.tsx               # Modify — warm popup styling
    MapLegend.tsx             # No change
    ScoreBadge.tsx             # Modify — terracotta background
```

---

## Task 1: Add DM Sans font and warm CSS variables

**Files:**
- Modify: `dashboard/app/layout.tsx`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Add DM Sans font to layout.tsx**

Read current layout.tsx, then edit the `<html>` tag to add the Google Fonts link:

```tsx
// dashboard/app/layout.tsx — change:
<html lang="en">
// to:
<html lang="en" className="font-dm-sans">
```

And add inside `<head>` (before closing):
```tsx
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Add CSS custom properties to globals.css**

Read current globals.css, then add at the top (before @tailwind):

```css
/* dashboard/app/globals.css — add after existing @imports */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

:root {
  --color-bg: #F9F7F4;
  --color-card: #FFFFFF;
  --color-accent: #E07A5F;
  --color-heading: #3D405B;
  --color-text: #2D2D2D;
  --color-muted: #8B8B8B;
  --color-border: #E8E4E0;
  --color-success: #81B29A;
}

body {
  background-color: var(--color-bg);
}
```

- [ ] **Step 3: Update tailwind.config.ts to extend font family**

Read tailwind.config.ts, then add:

```typescript
// dashboard/tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        'dm-sans': ['DM Sans', 'sans-serif'],
      },
      colors: {
        accent: '#E07A5F',
        heading: '#3D405B',
        muted: '#8B8B8B',
        border: '#E8E4E0',
        success: '#81B29A',
        'warm-bg': '#F9F7F4',
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: Apply warm background to page body**

In `dashboard/app/layout.tsx`, add `className="font-dm-sans"` to the `<body>` tag.

In `dashboard/app/page.tsx` and `dashboard/app/dashboard/map/page.tsx`, add `className="bg-warm-bg"` to the `<main>` element (or the root div of each page).

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/layout.tsx dashboard/app/globals.css dashboard/tailwind.config.ts
git commit -m "feat(dashboard): add DM Sans font and warm CSS variables"
```

---

## Task 2: Add sort dropdown to FilterBar

**Files:**
- Modify: `dashboard/components/FilterBar.tsx`

- [ ] **Step 1: Add sort options and state**

Read FilterBar.tsx. Edit to add the sort dropdown after the Refresh button:

```tsx
// Add at top of FilterBar component, after the existing interface:
const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'price_asc', label: 'Price (low to high)' },
  { value: 'price_desc', label: 'Price (high to low)' },
  { value: 'date_desc', label: 'Newest first' },
  { value: 'area_desc', label: 'Largest first' },
] as const;

type SortOption = typeof SORT_OPTIONS[number]['value'];
```

- [ ] **Step 2: Add props to FilterBarProps**

```typescript
// In FilterBarProps interface, add:
sortBy: SortOption;
onSortChange: (sort: SortOption) => void;
```

- [ ] **Step 3: Add sort dropdown JSX**

After the `<button onClick={onRefresh}>` in the JSX, add:

```tsx
<div className="flex items-center gap-2 ml-auto">
  <label className="text-sm font-medium text-gray-700">Sort</label>
  <select
    value={sortBy}
    onChange={(e) => onSortChange(e.target.value as SortOption)}
    className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
  >
    {SORT_OPTIONS.map((opt) => (
      <option key={opt.value} value={opt.value}>{opt.label}</option>
    ))}
  </select>
</div>
```

Also add `ml-auto` to the existing filter div to push sort to the right.

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/FilterBar.tsx
git commit -m "feat(dashboard): add sort dropdown to FilterBar"
```

---

## Task 3: Update API routes to accept sort param

**Files:**
- Modify: `dashboard/app/api/listings/top/route.ts`
- Modify: `dashboard/app/api/listings/map/route.ts`

- [ ] **Step 1: Update top/route.ts**

Read the route. Add `sort` param after the existing query params:

```typescript
// In top/route.ts GET function, after district:
const sort = searchParams.get('sort') || 'score_desc';

// Build sort object
const sortOptions: Record<string, Record<string, 1 | -1>> = {
  score_desc: { score: -1, processed_at: -1 },
  price_asc: { price_total: 1 },
  price_desc: { price_total: -1 },
  date_desc: { processed_at: -1 },
  area_desc: { area_m2: -1 },
};
const sortBy = sortOptions[sort] ?? sortOptions.score_desc;
```

Then change the `.sort()` call:
```typescript
.sort(sortBy)
```

- [ ] **Step 2: Update map/route.ts**

Same change — add `sort` param, `sortOptions` map, replace `.sort({ score: -1 })` with `.sort(sortBy)`.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/api/listings/top/route.ts dashboard/app/api/listings/map/route.ts
git commit -m "feat(dashboard): add sort param to listing API routes"
```

---

## Task 4: Wire sort state into page components

**Files:**
- Modify: `dashboard/app/page.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Update dashboard/page.tsx**

Read page.tsx. Add to state:
```typescript
const [sortBy, setSortBy] = useState<SortOption>('score_desc');
```

In `fetchListings`, add sort to params:
```typescript
params.set('sort', sortBy);
```

Add `sortBy` and `onSortChange` to `<FilterBar>`:
```tsx
<FilterBar
  sortBy={sortBy}
  onSortChange={setSortBy}
  // ... existing props
/>
```

- [ ] **Step 2: Update map/page.tsx**

Same changes as dashboard/page.tsx — add `sortBy` state, pass to params, pass to `<ListingSidebar>`.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/page.tsx dashboard/app/dashboard/map/page.tsx
git commit -m "feat(dashboard): wire sort state into pages"
```

---

## Task 5: Redesign ListingCard with image-top layout

**Files:**
- Modify: `dashboard/components/ListingCard.tsx`

- [ ] **Step 1: Write the new card**

Replace the entire `ListingCard.tsx` content with the new design:

```tsx
// dashboard/components/ListingCard.tsx
'use client';

import React, { useState } from 'react';
import { ListingBase } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';

interface ListingCardProps {
  listing: ListingBase;
  onClick: (id: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  willhaben: 'WH',
  immo_kurier: 'IK',
  derstandard: 'DS',
  unknown: '?',
};

export function ListingCard({ listing, onClick }: ListingCardProps) {
  const [imageError, setImageError] = useState(false);

  const hasImage = listing.image_url && !imageError;

  return (
    <div
      onClick={() => onClick(listing._id)}
      className="group bg-white rounded-xl shadow-sm border border-border overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    >
      {/* Image area */}
      <div className="relative aspect-[16/10] bg-warm-bg overflow-hidden">
        {hasImage ? (
          <img
            src={listing.image_url!}
            alt={listing.title || 'Property image'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-border">
            <svg className="w-8 h-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1m-4 0h4" />
            </svg>
          </div>
        )}

        {/* Score badge — top right */}
        {listing.score != null && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold text-white bg-accent">
              {listing.score}
            </span>
          </div>
        )}

        {/* Source badge — bottom left */}
        <div className="absolute bottom-2 left-2">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-heading bg-white bg-opacity-90">
            {SOURCE_LABELS[listing.source_enum] ?? '?'}
          </span>
        </div>
      </div>

      {/* Details area */}
      <div className="p-4">
        <h3 className="font-medium text-text line-clamp-2 text-sm leading-snug mb-2">
          {listing.title || 'Untitled'}
        </h3>

        <p className="font-bold text-heading text-base mb-1">
          {listing.price_total
            ? `€${listing.price_total.toLocaleString('de-AT')}`
            : 'Price on request'}
        </p>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted">
            {listing.area_m2 != null && <span>{listing.area_m2}m²</span>}
            {listing.rooms != null && <span>· {listing.rooms} rooms</span>}
          </div>
          {listing.bezirk && (
            <span className="text-[10px] font-medium text-muted bg-warm-bg px-1.5 py-0.5 rounded">
              {listing.bezirk}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/ListingCard.tsx
git commit -m "feat(dashboard): redesign ListingCard with image-top layout"
```

---

## Task 6: Update ListingSidebar to use new card design

**Files:**
- Modify: `dashboard/components/ListingSidebar.tsx`

- [ ] **Step 1: Replace card rendering in ListingSidebar**

Read ListingSidebar.tsx. Find the card rendering inside the map and replace it with a compact version of the new ListingCard. The cards in the sidebar should be more compact — show image thumbnail on left, details on right.

Replace the current card div with:

```tsx
// Inside listings.map — replace the existing card div with:
<div
  key={l._id}
  onClick={() => onSelect(l)}
  className={`flex gap-3 bg-white rounded-lg border p-2 cursor-pointer transition-all text-xs ${
    selectedId === l._id
      ? 'border-accent ring-1 ring-accent'
      : 'border-border hover:border-muted'
  }`}
>
  {/* Thumbnail */}
  <div className="w-16 h-16 rounded-md overflow-hidden bg-border shrink-0 flex items-center justify-center">
    {l.image_url ? (
      <img src={l.image_url} alt="" className="w-full h-full object-cover" />
    ) : (
      <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
      </svg>
    )}
  </div>

  {/* Info */}
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
```

Also update the outer container className from `flex flex-col gap-2` to `flex flex-col gap-1.5`.

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/ListingSidebar.tsx
git commit -m "feat(dashboard): update ListingSidebar with image thumbnails"
```

---

## Task 7: Warm styling for MapView popup and ScoreBadge

**Files:**
- Modify: `dashboard/components/MapView.tsx`
- Modify: `dashboard/components/ScoreBadge.tsx`

- [ ] **Step 1: Update MapView popup styling**

Read MapView.tsx. Find the `<Popup>` content and update the wrapper div:

Change the popup inner div from:
```tsx
<div className="text-sm min-w-[160px]">
```
To:
```tsx
<div className="text-sm min-w-[160px] font-dm-sans">
```

And update the title color class from `font-semibold` to `font-bold text-heading`, price from `text-blue-600` to `text-accent font-bold`.

- [ ] **Step 2: Update ScoreBadge to use terracotta**

Read ScoreBadge.tsx. Change the component to use the terracotta accent:

```tsx
// Current: likely blue. Change bg-blue-600 to bg-accent
<span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold text-white bg-accent">
  {score}
</span>
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/MapView.tsx dashboard/components/ScoreBadge.tsx
git commit -m "feat(dashboard): warm styling for map popup and score badge"
```

---

## Task 8: TypeScript compilation check

**Files:**
- None (verification only)

- [ ] **Step 1: Run TypeScript compilation**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit 2>&1 | grep -v "test.tsx" | grep -v "MapView.test\|types.test"
```

Expected: no errors (only pre-existing Jest test file errors).

- [ ] **Step 2: Commit**

Only if files were touched — if only verification, no commit needed.

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| DM Sans typography | Task 1 |
| Warm CSS variables | Task 1 |
| Sort dropdown in FilterBar | Task 2 |
| Sort API params | Task 3 |
| Sort wired to pages | Task 4 |
| Image-top card layout | Task 5 |
| ListingSidebar card redesign | Task 6 |
| Warm map popup | Task 7 |
| ScoreBadge terracotta | Task 7 |

---

## Type Consistency Check

- `SortOption` type defined in FilterBar, used in both pages
- `sortOptions` map in API routes uses same `SortOption` values: `score_desc`, `price_asc`, `price_desc`, `date_desc`, `area_desc`
- ListingCard uses `listing.image_url` — matches `ListingBase.image_url: string | null`
- `coordinate_source` in ListingSidebar — matches `MapListing.coordinate_source` field

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
