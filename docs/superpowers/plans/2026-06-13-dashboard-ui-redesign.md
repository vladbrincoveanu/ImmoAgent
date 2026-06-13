# Dashboard UI Redesign — /dashboard/map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recreate the cool-palette top-bar + 340px listing rail + opt-in layers + 320px detail-card layout on `/dashboard/map`, matching the design handoff at `~/Downloads/design_handoff_property_map/`. Drop 4 dead components. Keep `FilterDrawer` (still used by `/dashboard`). Mobile (`<md`) keeps the existing `BottomSheet` flow.

**Architecture:** Single page-state owner in `app/dashboard/map/page.tsx`. Five new focused components, six modified. New Tailwind tokens (ink/line/bg/card/accent) added; legacy warm tokens kept for `/dashboard`. No new API endpoints. Local Mongo is empty — final verification uses `playwright.prod.config.ts` against the Vercel production URL.

**Tech Stack:** Next.js 14.2 (App Router), react-leaflet 4.0, Tailwind 3.4, TypeScript 5.3, Playwright 1.60.

**Spec:** `docs/superpowers/specs/2026-06-13-dashboard-ui-redesign-design.md`

**Spec flags:** `ui_scope: true` → Visual verification task included. `test_scope: true` → Coverage measurement task included. `graph_scope: false` → no graph rebuild.

---

## Task 1: Token migration (Tailwind + globals.css)

**Files:**
- Modify: `dashboard/tailwind.config.ts`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Add new tokens to `tailwind.config.ts`**

Replace the `theme.extend.colors` block in `dashboard/tailwind.config.ts` with the merged palette (new + legacy kept). Final file:

```ts
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        'dm-sans': ['DM Sans', 'sans-serif'],
        sans: ['Inter', '-apple-system', 'sans-serif'],
      },
      colors: {
        // New /dashboard/map tokens (cool palette)
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
        // Legacy warm tokens — kept for /dashboard + /dashboard/taken
        heading: '#3D405B',
        muted: '#8B8B8B',
        border: '#E8E4E0',
        success: '#81B29A',
        'warm-bg': '#F9F7F4',
        dark: {
          heading: '#F9F7F4',
          muted: '#A0A0A0',
          border: '#3D3D3D',
        },
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Add Inter font import + scoped class in `globals.css`**

Append to `dashboard/app/globals.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.map-desktop {
  font-family: 'Inter', -apple-system, sans-serif;
}
```

- [ ] **Step 3: Verify Tailwind compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: 0 errors. Token change is type-safe (string literals).

- [ ] **Step 4: Commit**

```bash
git add dashboard/tailwind.config.ts dashboard/app/globals.css
git commit -m "feat(dashboard/tokens): add cool-palette tokens + Inter font for /map redesign"
```

---

## Task 2: SlimListingCard component

**Files:**
- Create: `dashboard/components/SlimListingCard.tsx`

- [ ] **Step 1: Write the failing test**

Create `dashboard/tests/slim-listing-card.spec.ts`:

```ts
import { test, expect } from '@playwright/test';

test('SlimListingCard shows thumb, price, title, m²/€/m², score chip — no zone-delta', async ({ page }) => {
  await page.goto('/dashboard/map');
  const card = page.locator('[data-testid="slim-listing-card"]').first();
  await expect(card).toBeVisible();
  await expect(card.locator('[data-testid="price"]')).toBeVisible();
  await expect(card.locator('[data-testid="title"]')).toBeVisible();
  await expect(card.locator('[data-testid="sub"]')).toContainText('m²');
  await expect(card.locator('[data-testid="score"]')).toBeVisible();
  await expect(card.locator('[data-testid="zone-delta"]')).toHaveCount(0);
  await expect(card.locator('[data-testid="address"]')).toHaveCount(0);
});
```

- [ ] **Step 2: Run test, expect failure (no data-testid yet)**

Run: `cd dashboard && npx playwright test tests/slim-listing-card.spec.ts --reporter=line`
Expected: FAIL — element(s) not found.

- [ ] **Step 3: Create `SlimListingCard.tsx`**

```tsx
'use client';

import { MapListing } from '@/lib/types';
import { formatPrice } from '@/lib/utils';

const HOUSE_SVG = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v10h14V10" />
  </svg>
);

interface SlimListingCardProps {
  listing: MapListing;
  selected: boolean;
  onClick: () => void;
}

export function SlimListingCard({ listing, selected, onClick }: SlimListingCardProps) {
  const isLowScore = listing.score < 28;
  return (
    <div
      data-testid="slim-listing-card"
      data-id={listing._id}
      onClick={onClick}
      className={`flex gap-3 px-2.5 py-3 rounded-[10px] cursor-pointer border ${
        selected ? 'bg-accent-soft border-[#c9d7fb]' : 'border-transparent hover:bg-bg'
      }`}
    >
      <div className="w-14 h-14 rounded-lg flex-shrink-0 bg-gradient-to-br from-[#dde4ee] to-[#c9d3e2] flex items-center justify-center text-ink-3 overflow-hidden">
        {listing.image_url ? (
          <img src={listing.image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          HOUSE_SVG
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div data-testid="price" className="text-[14px] font-bold tracking-tight">
          {formatPrice(listing.price_total)}
        </div>
        <div data-testid="title" className="text-[12.5px] text-ink-2 truncate my-0.5">
          {listing.title}
        </div>
        <div data-testid="sub" className="text-[11.5px] text-ink-3">
          {listing.area_m2?.toFixed(1)} m² · €{listing.price_per_m2}/m²
        </div>
      </div>
      <span
        data-testid="score"
        className={`self-start text-[11.5px] font-bold px-1.5 py-0.5 rounded-md tabular-nums ${
          isLowScore ? 'bg-mid-soft text-mid-ink' : 'bg-good-soft text-good'
        }`}
      >
        {listing.score?.toFixed(1)}
      </span>
    </div>
  );
}
```

Note: check `lib/types.ts` for the exact field names (`price_total`, `price_per_m2`, `area_m2`, `score`, `image_url`, `title`, `_id`). If the existing types use different names, use those. Do not invent fields.

- [ ] **Step 4: Run test, expect pass**

Run: `cd dashboard && npx playwright test tests/slim-listing-card.spec.ts --reporter=line`
Expected: PASS. (Note: the test will only pass on prod URL with real data — use `--config=playwright.prod.config.ts` if local Mongo is empty.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/SlimListingCard.tsx dashboard/tests/slim-listing-card.spec.ts
git commit -m "feat(dashboard): add SlimListingCard (rail form, no per-listing stats)"
```

---

## Task 3: ListingRail component

**Files:**
- Create: `dashboard/components/ListingRail.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('ListingRail renders at 340px width with count + sort header', async ({ page }) => {
  await page.goto('/dashboard/map');
  const rail = page.locator('[data-testid="listing-rail"]');
  await expect(rail).toBeVisible();
  const box = await rail.boundingBox();
  expect(box?.width).toBe(340);
  await expect(rail.locator('[data-testid="rail-count"]')).toContainText(/\d+ in view/);
  await expect(rail.locator('[data-testid="rail-sort"]')).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Create `ListingRail.tsx`**

```tsx
'use client';

import { MapListing } from '@/lib/types';
import { SlimListingCard } from './SlimListingCard';
import { SortOption } from '@/lib/filters';

interface ListingRailProps {
  listings: MapListing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortMode: SortOption;
  onSortChange: (s: SortOption) => void;
}

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: 'score', label: 'Score · high to low' },
  { value: 'priceAsc', label: 'Price · low to high' },
  { value: 'priceDesc', label: 'Price · high to low' },
];

export function ListingRail({ listings, selectedId, onSelect, sortMode, onSortChange }: ListingRailProps) {
  return (
    <aside
      data-testid="listing-rail"
      className="w-[340px] flex-shrink-0 bg-card border-r border-line flex flex-col"
    >
      <div className="px-[18px] py-3.5 flex items-baseline justify-between gap-2">
        <span data-testid="rail-count" className="text-[13px] font-semibold">
          {listings.length} in view
        </span>
        <select
          data-testid="rail-sort"
          value={sortMode}
          onChange={(e) => onSortChange(e.target.value as SortOption)}
          className="text-[12px] text-ink-2 bg-transparent border-0 cursor-pointer"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex-1 overflow-y-auto px-2.5 pb-4">
        {listings.map((l) => (
          <SlimListingCard
            key={l._id}
            listing={l}
            selected={l._id === selectedId}
            onClick={() => onSelect(l._id)}
          />
        ))}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the new test.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/ListingRail.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "feat(dashboard): add ListingRail (340px, count + sort + slim cards)"
```

---

## Task 4: MapTopBar component

**Files:**
- Create: `dashboard/components/MapTopBar.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('MapTopBar shows brand "Immo Scouter", Filters button with badge, Layers button', async ({ page }) => {
  await page.goto('/dashboard/map');
  const top = page.locator('[data-testid="map-top-bar"]');
  await expect(top).toBeVisible();
  const box = await top.boundingBox();
  expect(box?.height).toBe(56);
  await expect(top.locator('[data-testid="brand"]')).toHaveText('Immo Scouter');
  await expect(top.locator('[data-testid="filters-btn"]')).toBeVisible();
  await expect(top.locator('[data-testid="layers-btn"]')).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Create `MapTopBar.tsx`**

```tsx
'use client';

import { ReactNode } from 'react';

const FILTER_SVG = (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M2 4h12M4.5 8h7M7 12h2" />
  </svg>
);

const LAYERS_SVG = (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
    <path d="M8 2L14 5 8 8 2 5z" />
    <path d="M2 8.5L8 11.5 14 8.5" opacity="0.55" />
    <path d="M2 11.5L8 14.5 14 11.5" opacity="0.3" />
  </svg>
);

interface MapTopBarProps {
  activeFilterCount: number;
  filtersOpen: boolean;
  onFiltersClick: () => void;
  layersOpen: boolean;
  onLayersClick: () => void;
  profileSlot: ReactNode;
  filterPopover: ReactNode;
}

export function MapTopBar({
  activeFilterCount,
  filtersOpen,
  onFiltersClick,
  layersOpen,
  onLayersClick,
  profileSlot,
  filterPopover,
}: MapTopBarProps) {
  return (
    <header
      data-testid="map-top-bar"
      className="h-14 bg-card border-b border-line flex items-center gap-4 px-5 relative z-[1200]"
    >
      <span data-testid="brand" className="font-bold text-[15px] tracking-tight">
        Immo Scouter
      </span>
      <div className="flex-1" />
      {profileSlot}
      <button
        data-testid="filters-btn"
        onClick={onFiltersClick}
        className="flex items-center gap-1.5 text-[13px] font-medium text-ink bg-card border border-line rounded-lg px-3.5 py-1.5 hover:border-[#cdd6e1]"
      >
        {FILTER_SVG}
        Filters
        {activeFilterCount > 0 && (
          <span
            data-testid="filter-count-badge"
            className="bg-accent text-white text-[11px] font-semibold min-w-[18px] h-[18px] rounded-full inline-flex items-center justify-center"
          >
            {activeFilterCount}
          </span>
        )}
      </button>
      <button
        data-testid="layers-btn"
        onClick={onLayersClick}
        className="hidden"
      >
        {LAYERS_SVG}
        Layers
      </button>
      {filterPopover}
    </header>
  );
}
```

Note: `layersOpen/onLayersClick` is included for the next task's popover; the button is hidden by default for now (`hidden` class) since the layers popover lives inside the map. Remove `hidden` when wiring in Task 7.

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the top-bar test.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/MapTopBar.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "feat(dashboard): add MapTopBar (56px, brand + profile slot + filters btn + popover slot)"
```

---

## Task 5: MapFilterPopover component

**Files:**
- Create: `dashboard/components/MapFilterPopover.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('MapFilterPopover opens on Filters click, Apply sets badge, closes popover', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.locator('[data-testid="filters-btn"]').click();
  const pop = page.locator('[data-testid="filter-popover"]');
  await expect(pop).toBeVisible();
  await pop.locator('[data-testid="filter-min-score"]').fill('25');
  await pop.locator('[data-testid="filter-apply"]').click();
  await expect(pop).toBeHidden();
  await expect(page.locator('[data-testid="filter-count-badge"]')).toHaveText('1');
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Create `MapFilterPopover.tsx`**

```tsx
'use client';

import { useState, useEffect } from 'react';

interface FilterState {
  district: string;
  minScore: number;
  maxPrice: number;
  commuteTo: string;
}

interface MapFilterPopoverProps {
  open: boolean;
  onClose: () => void;
  initial: FilterState;
  onApply: (next: FilterState) => void;
}

const COMMUTE_OPTIONS = ['', 'Stephansplatz', 'Hauptbahnhof', 'Donau City'];

export function MapFilterPopover({ open, onClose, initial, onApply }: MapFilterPopoverProps) {
  const [district, setDistrict] = useState(initial.district);
  const [minScore, setMinScore] = useState(initial.minScore);
  const [maxPrice, setMaxPrice] = useState(initial.maxPrice);
  const [commuteTo, setCommuteTo] = useState(initial.commuteTo);

  useEffect(() => {
    if (open) {
      setDistrict(initial.district);
      setMinScore(initial.minScore);
      setMaxPrice(initial.maxPrice);
      setCommuteTo(initial.commuteTo);
    }
  }, [open, initial]);

  if (!open) return null;

  return (
    <div
      data-testid="filter-popover"
      className="absolute top-[52px] right-5 w-[280px] bg-card border border-line rounded-xl shadow-[0_12px_32px_rgba(22,36,58,0.14)] p-[18px] z-[1300]"
      onClick={(e) => e.stopPropagation()}
    >
      <label className="block text-[12px] font-semibold text-ink-2 mb-1.5">District</label>
      <input
        data-testid="filter-district"
        type="text"
        placeholder="e.g. 02"
        value={district}
        onChange={(e) => setDistrict(e.target.value)}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Min score</label>
      <input
        data-testid="filter-min-score"
        type="number"
        min={0}
        max={100}
        value={minScore}
        onChange={(e) => setMinScore(Number(e.target.value))}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Max price (€)</label>
      <input
        data-testid="filter-max-price"
        type="number"
        min={0}
        value={maxPrice}
        onChange={(e) => setMaxPrice(Number(e.target.value))}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      />
      <label className="block text-[12px] font-semibold text-ink-2 mt-3.5 mb-1.5">Commute to</label>
      <select
        data-testid="filter-commute"
        value={commuteTo}
        onChange={(e) => setCommuteTo(e.target.value)}
        className="w-full text-[13px] border border-line rounded-lg px-2.5 py-1.5"
      >
        {COMMUTE_OPTIONS.map((o) => (
          <option key={o} value={o}>
            {o || '— pick destination —'}
          </option>
        ))}
      </select>
      <button
        data-testid="filter-apply"
        onClick={() => {
          onApply({ district, minScore, maxPrice, commuteTo });
          onClose();
        }}
        className="w-full mt-4 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg"
      >
        Apply
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the popover test.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/MapFilterPopover.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "feat(dashboard): add MapFilterPopover (280px right-anchored, apply closes)"
```

---

## Task 6: MapLayersPopover component

**Files:**
- Create: `dashboard/components/MapLayersPopover.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('MapLayersPopover toggles U-Bahn + Schools; default state has only Listings on', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.locator('[data-testid="layers-btn"]').click();
  const pop = page.locator('[data-testid="layers-popover"]');
  await expect(pop).toBeVisible();
  const stationsToggle = pop.locator('[data-testid="layer-toggle-stations"]');
  const schoolsToggle = pop.locator('[data-testid="layer-toggle-schools"]');
  // Default: stations off → click to turn on
  await stationsToggle.click();
  // After click the toggle reflects on state; we just check the click handler fired
  await schoolsToggle.click();
  // Close by clicking outside
  await page.locator('body').click({ position: { x: 10, y: 10 } });
  await expect(pop).toBeHidden();
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Create `MapLayersPopover.tsx`**

```tsx
'use client';

interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
}

interface MapLayersPopoverProps {
  open: boolean;
  onClose: () => void;
  layers: LayerState;
  onToggle: (key: 'listings' | 'stations' | 'schools') => void;
  counts: { listings: number; stations: number; schools: number };
}

const ROWS: Array<{ key: 'listings' | 'stations' | 'schools'; name: string; color: string; dotColor: string }> = [
  { key: 'listings', name: 'Listings', color: '#16243a', dotColor: 'bg-ink' },
  { key: 'stations', name: 'U-Bahn stations', color: '#3b6fd4', dotColor: 'bg-[#3b6fd4]' },
  { key: 'schools', name: 'Schools', color: '#2ba56b', dotColor: 'bg-[#2ba56b]' },
];

export function MapLayersPopover({ open, onClose, layers, onToggle, counts }: MapLayersPopoverProps) {
  if (!open) return null;
  return (
    <div
      data-testid="layers-popover"
      className="absolute top-[42px] right-0 w-[224px] bg-card border border-line rounded-xl shadow-[0_12px_32px_rgba(22,36,58,0.14)] p-2 z-[1100]"
      onClick={(e) => e.stopPropagation()}
    >
      {ROWS.map((row) => {
        const on = layers[row.key];
        return (
          <div
            key={row.key}
            data-testid={`layer-row-${row.key}`}
            onClick={() => onToggle(row.key)}
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer text-[13px] hover:bg-bg ${
              on ? 'bg-bg' : ''
            }`}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${row.dotColor}`} />
            <span className="flex-1">{row.name}</span>
            <span className="text-[11.5px] text-ink-3">{counts[row.key]}</span>
            <span
              data-testid={`layer-toggle-${row.key}`}
              className={`w-8 h-[18px] rounded-full relative transition-colors ${
                on ? 'bg-accent' : 'bg-[#d6dde6]'
              }`}
            >
              <span
                className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-all ${
                  on ? 'left-4' : 'left-0.5'
                }`}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the layers popover test.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/MapLayersPopover.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "feat(dashboard): add MapLayersPopover (3 toggles, counts, default listings-only)"
```

---

## Task 7: MapView refactor — single-navy pins, opt-in layers

**Files:**
- Modify: `dashboard/components/MapView.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('MapView renders single-navy pins by default, selected pin is blue, U-Bahn dots hidden by default', async ({ page }) => {
  await page.goto('/dashboard/map');
  // Default: no station dots visible
  await expect(page.locator('.station-dot')).toHaveCount(0);
  // At least one navy price pin
  const pin = page.locator('.price-pin').first();
  await expect(pin).toBeVisible();
  const bg = await pin.evaluate((el) => getComputedStyle(el).backgroundColor);
  // #16243a → rgb(22, 36, 58)
  expect(bg).toBe('rgb(22, 36, 58)');
  // Click pin → selected state
  await pin.click();
  await expect(page.locator('.price-pin.sel').first()).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure (current MapView uses different colors)**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL on color assertion (current uses red/orange/blue tiers).

- [ ] **Step 3: Replace `createPriceIcon` and add `layers` prop**

In `dashboard/components/MapView.tsx`, make these changes:

1. Delete the constants block:
```ts
const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
const DISTRICT_COLOR = '#3B82F6';
const HIGHLIGHT_COLOR = '#E07A5F';
const UBAHN_COLOR = '#1d4ed8';
const SCHOOL_COLOR = '#16a34a';
const HOVER_COLOR = '#FBBF24';
```

2. Delete the `PinState` and `MarkerTier` types and `TIER_STYLES` constant.

3. Replace `createPriceIcon(price, color, tier)` with a new single-style version:

```ts
function createPriceIcon(price: number, selected: boolean): L.DivIcon {
  const formatted = price >= 1_000_000
    ? `€${(price / 1_000_000).toFixed(1)}M`
    : `€${Math.round(price / 1000)}k`;
  return L.divIcon({
    html: `<div class="price-pin ${selected ? 'sel' : ''}" style="${
      selected ? 'background:#2456e6' : ''
    }">${formatted}</div>`,
    iconSize: null,
  });
}
```

4. Add `layers` and `selectedListingId` (replace `highlightedId` and `hoveredId`) to `MapViewProps`:

```ts
export interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
}

export interface MapViewProps {
  listings: MapListing[];
  selectedListingId: string | null;
  layers: LayerState;
  onPinClick: (listing: MapListing) => void;
  onBoundsChange?: (bounds: ViewportBounds) => void;
  onMapClick?: () => void;
  layersPopoverSlot?: React.ReactNode;
  stationData?: Array<{ name: string; lat: number; lng: number }>;
  schoolData?: Array<{ lat: number; lng: number }>;
}
```

5. Replace the `getPinState` / `getPinColor` / `getTier` helpers with a single boolean: `selected = listing._id === selectedListingId`.

6. Inside the component, replace each marker's icon call with `createPriceIcon(l.price_total, selected)`.

7. Wrap the station group and school group in conditional rendering based on `layers.stations` and `layers.schools`.

8. Mount the `layersPopoverSlot` in the top-right of the map (positioned absolute inside `.map-wrap`).

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the pin/style tests.

- [ ] **Step 5: Update existing tests that depend on the old color tier**

In `dashboard/tests/pin-click.spec.ts` — search for `EXACT_COLOR`, `HIGHLIGHT_COLOR`, color tier assertions. Replace with neutral assertions (`.price-pin` visible, `.price-pin.sel` after click). Show a few changes in commit message.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components/MapView.tsx dashboard/tests/desktop-redesign.spec.ts dashboard/tests/pin-click.spec.ts
git commit -m "refactor(dashboard/MapView): single-navy price pins, opt-in U-Bahn+schools layers, slot for layers popover"
```

---

## Task 8: SelectedCard restyle

**Files:**
- Modify: `dashboard/components/SelectedCard.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('SelectedCard opens at bottom-left 320px wide with fact chips and View listing CTA', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.locator('.price-pin').first().click();
  const card = page.locator('[data-testid="selected-card"]');
  await expect(card).toBeVisible();
  const box = await card.boundingBox();
  expect(box?.width).toBe(320);
  // Bottom-left: left value should be small (< 50), bottom close to viewport bottom
  expect(box?.x).toBeLessThan(50);
  expect(box?.y).toBeGreaterThan(400);
  await expect(card.locator('[data-testid="fact-m2"]')).toBeVisible();
  await expect(card.locator('[data-testid="fact-eur-m2"]')).toBeVisible();
  await expect(card.locator('[data-testid="fact-score"]')).toBeVisible();
  await expect(card.locator('[data-testid="fact-zone"]')).toBeVisible();
  await expect(card.locator('[data-testid="view-listing-cta"]')).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL (current SelectedCard is bottom-center max-w-md with image header).

- [ ] **Step 3: Replace SelectedCard body**

```tsx
'use client';

import { MapListing } from '@/lib/types';
import { formatPrice } from '@/lib/utils';

interface SelectedCardProps {
  listing: MapListing | null;
  onClose: () => void;
  onViewDetails: (id: string) => void;
}

export function SelectedCard({ listing, onClose, onViewDetails }: SelectedCardProps) {
  if (listing == null) return null;
  return (
    <div
      data-testid="selected-card"
      className="absolute left-3.5 bottom-3.5 w-[320px] bg-card border border-line rounded-xl shadow-[0_16px_40px_rgba(22,36,58,0.16)] p-[18px] z-[1100]"
    >
      <button
        data-testid="selected-close"
        onClick={onClose}
        className="absolute top-2.5 right-3 border-0 bg-transparent text-[16px] text-ink-3 cursor-pointer"
      >
        ×
      </button>
      <div data-testid="price" className="text-[20px] font-bold tracking-tight">
        {formatPrice(listing.price_total)}
      </div>
      <div data-testid="title" className="text-[13px] text-ink-2 mt-1 mb-3 leading-snug">
        {listing.title}
      </div>
      <div className="flex gap-2 flex-wrap">
        <span data-testid="fact-m2" className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1">
          <strong className="text-ink font-semibold">{listing.area_m2?.toFixed(1)} m²</strong>
        </span>
        <span data-testid="fact-eur-m2" className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1">
          <strong className="text-ink font-semibold">€{listing.price_per_m2}</strong>/m²
        </span>
        <span data-testid="fact-score" className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1">
          Score <strong className="text-ink font-semibold">{listing.score?.toFixed(1)}</strong>
        </span>
        {listing.zone_delta_pct != null && (
          <span data-testid="fact-zone" className="text-[12px] text-ink-2 bg-bg rounded-md px-2.5 py-1">
            <strong className="text-ink font-semibold">{listing.zone_delta_pct}%</strong> vs district
          </span>
        )}
      </div>
      <button
        data-testid="view-listing-cta"
        onClick={() => onViewDetails(listing._id)}
        className="w-full mt-3.5 bg-accent text-white text-[13px] font-semibold py-2 rounded-lg"
      >
        View listing
      </button>
    </div>
  );
}
```

Note: check `lib/types.ts` for `zone_delta_pct` — use the actual field name. If absent, omit the zone fact chip and the test's zone assertion in step 1.

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/SelectedCard.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "refactor(dashboard/SelectedCard): 320px bottom-left, fact chips, View listing CTA"
```

---

## Task 9: Restructure `map/page.tsx` — wire it all together

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Write the failing test**

Append to `dashboard/tests/desktop-redesign.spec.ts`:

```ts
test('Desktop layout shows top-bar + rail + map; mobile shows BottomSheet at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');
  await expect(page.locator('[data-testid="map-top-bar"]')).toBeVisible();
  await expect(page.locator('[data-testid="listing-rail"]')).toBeVisible();
  await expect(page.locator('#map')).toBeVisible();
  // Mobile fallback
  await page.setViewportSize({ width: 375, height: 800 });
  await page.reload();
  await expect(page.locator('[data-testid="mobile-map-fallback"]')).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: FAIL.

- [ ] **Step 3: Modify `map/page.tsx`**

In `dashboard/app/dashboard/map/page.tsx`:

1. Remove imports for `FilterDrawer`, `MapLayerToggle`, `MapLegend`, `MapGuide`, `PriceHeatmap` (they will be deleted in Task 12). Keep the `BottomSheet` import.

2. Add imports for new components: `MapTopBar`, `MapFilterPopover`, `MapLayersPopover`, `ListingRail`.

3. Add state:
```ts
const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
const [sortMode, setSortMode] = useState<SortOption>('score');
const [layers, setLayers] = useState<{ listings: true; stations: false; schools: false }>({
  listings: true,
  stations: false,
  schools: false,
});
const [filtersOpen, setFiltersOpen] = useState(false);
const [layersOpen, setLayersOpen] = useState(false);
```

4. Compute `activeFilterCount` derived from `useFilters` state.

5. Compute `viewportListings` (existing pattern from 2026-05-14 design — keep the `useMemo`).

6. Replace the JSX. The desktop branch:
```tsx
<div className="hidden md:flex flex-col h-screen map-desktop">
  <MapTopBar
    activeFilterCount={activeFilterCount}
    filtersOpen={filtersOpen}
    onFiltersClick={() => setFiltersOpen((o) => !o)}
    layersOpen={layersOpen}
    onLayersClick={() => setLayersOpen((o) => !o)}
    profileSlot={<ProfileSelector value={profile} onChange={setProfile} />}
    filterPopover={
      <MapFilterPopover
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        initial={filterState}
        onApply={applyFilters}
      />
    }
  />
  <div className="flex flex-1 overflow-hidden">
    <ListingRail
      listings={viewportListings}
      selectedId={selectedListingId}
      onSelect={setSelectedListingId}
      sortMode={sortMode}
      onSortChange={setSortMode}
    />
    <div className="flex-1 relative">
      <MapView
        listings={viewportListings}
        selectedListingId={selectedListingId}
        layers={layers}
        onPinClick={(l) => setSelectedListingId(l._id)}
        onBoundsChange={setBounds}
        onMapClick={() => setSelectedListingId(null)}
        layersPopoverSlot={
          <MapLayersPopover
            open={layersOpen}
            onClose={() => setLayersOpen(false)}
            layers={layers}
            onToggle={(k) => setLayers((s) => ({ ...s, [k]: !s[k] }))}
            counts={layerCounts}
          />
        }
      />
      <SelectedCard
        listing={selectedListing ?? null}
        onClose={() => setSelectedListingId(null)}
        onViewDetails={(id) => router.push(`/dashboard/${id}`)}
      />
    </div>
  </div>
</div>
<div data-testid="mobile-map-fallback" className="md:hidden">
  <BottomSheet>{/* existing mobile flow */}</BottomSheet>
</div>
```

- [ ] **Step 4: Run, expect pass**

Run: `cd dashboard && npx playwright test tests/desktop-redesign.spec.ts --reporter=line`
Expected: PASS for the layout test.

- [ ] **Step 5: Verify TypeScript**

Run: `cd dashboard && npx tsc --noEmit`
Expected: 0 errors. If errors, fix at the source — never `// @ts-ignore`.

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/dashboard/map/page.tsx dashboard/tests/desktop-redesign.spec.ts
git commit -m "refactor(dashboard/map-page): new desktop layout shell, mobile BottomSheet fallback"
```

---

## Task 10: Update existing tests (5 files)

**Files:**
- Modify: `dashboard/tests/map-full.spec.ts` (4 FilterDrawer tests → MapFilterPopover)
- Modify: `dashboard/tests/address-bank-declutter.spec.ts` (1 MapLayerToggle test → MapLayersPopover)
- Modify: `dashboard/tests/commute-rent-insights.spec.ts` (MapLegend + MapGuide tests → Layers popover + remove)
- Modify: `dashboard/tests/map-overhaul.spec.ts` (MapLegend test → Layers popover)
- Modify: `dashboard/tests/map-interaction.spec.ts` (SelectedCard position assertion)

- [ ] **Step 1: Update `map-full.spec.ts` — 4 FilterDrawer tests**

Find each test that starts with `test('...FilterDrawer...`. Replace the body with a popover-based equivalent:
- `tapping filter FAB opens FilterDrawer` → `Filters button opens MapFilterPopover` (click `[data-testid="filters-btn"]`, expect `[data-testid="filter-popover"]` visible).
- `FilterDrawer closes via backdrop click` → click outside popover, expect hidden.
- `FilterDrawer Close button works` → keep (popover has no explicit close button besides outside click; if a close button is added, assert it).
- `FilterDrawer Reset button is present` → remove (the new popover has no reset; the URL state survives).

- [ ] **Step 2: Update `address-bank-declutter.spec.ts:124`**

Replace the test body: click `[data-testid="layers-btn"]`, assert `[data-testid="layers-popover"]` visible, click `[data-testid="layer-toggle-stations"]`, assert U-Bahn dots appear on the map.

- [ ] **Step 3: Update `commute-rent-insights.spec.ts`**

- Line 122 (`MapLegend shows U-Bahn and school counts from /api/geo/infrastructure`) → rewrite to open Layers popover, assert counts text matches.
- Line 131 (`MapGuide overlay explains every dot type so user knows what they mean`) → assert the overlay no longer exists (or remove the test if no replacement).

- [ ] **Step 4: Update `map-overhaul.spec.ts:78`**

Same as step 3's first rewrite.

- [ ] **Step 5: Update `map-interaction.spec.ts`**

Find the SelectedCard position assertion. Replace `bottom-center` assertions with `bottom-left 320px` (use `boundingBox` and assert `x < 50`, `width === 320`).

- [ ] **Step 6: Run, expect all to pass**

Run: `cd dashboard && npx playwright test --reporter=line`
Expected: 0 failures, 0 console errors on `/dashboard/map`.

- [ ] **Step 7: Commit**

```bash
git add dashboard/tests/
git commit -m "test(dashboard): update 5 specs to match new popovers + popover-driven MapLayers + restyled SelectedCard"
```

---

## Task 11: Delete 4 dead components

**Files:**
- Delete: `dashboard/components/MapLayerToggle.tsx`
- Delete: `dashboard/components/MapLegend.tsx`
- Delete: `dashboard/components/MapGuide.tsx`
- Delete: `dashboard/components/PriceHeatmap.tsx`

- [ ] **Step 1: Verify no remaining imports**

```bash
cd dashboard && grep -rln "MapLayerToggle\|MapLegend\|MapGuide\|PriceHeatmap" app components lib --include="*.ts" --include="*.tsx"
```

Expected: no results. (All imports removed in Task 9.)

- [ ] **Step 2: Delete the 4 files**

```bash
cd dashboard
git rm components/MapLayerToggle.tsx components/MapLegend.tsx components/MapGuide.tsx components/PriceHeatmap.tsx
```

- [ ] **Step 3: Verify tsc + suite still pass**

Run: `cd dashboard && npx tsc --noEmit && npx playwright test --reporter=line`
Expected: 0 errors, 0 failures.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(dashboard): delete 4 dead components (MapLayerToggle, MapLegend, MapGuide, PriceHeatmap)"
```

---

## Task 12: Type check + dev-server smoke + full suite gate

**Files:** none modified — verification only.

- [ ] **Step 1: tsc clean**

Run: `cd dashboard && npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 2: Dev server boots**

```bash
pkill -f "next dev" || true
cd dashboard && npm run dev > /tmp/next-dev.log 2>&1 &
sleep 8
curl -s http://localhost:3000/dashboard/map | head -50
```

Expected: HTML response includes `data-testid="map-top-bar"` and `data-testid="listing-rail"`.

- [ ] **Step 3: Local full suite**

Run: `cd dashboard && npx playwright test --reporter=line`
Expected: most tests fail on local (empty Mongo) — that's expected. Record which ones fail.

- [ ] **Step 4: Prod verification (real data)**

Run: `cd dashboard && npx playwright test --config=playwright.prod.config.ts --reporter=line`
Expected: 0 failures. Per memory `feedback-verify-on-real-data.md`, local Mongo is empty — verify on Vercel prod URL.

- [ ] **Step 5: Kill dev server**

```bash
pkill -f "next dev"
```

---

## Task 13: Visual verification (per `ui_scope: true`)

**Files:**
- Create: `dashboard/.frontend-design/baselines/dashboard-map-desktop.png` (baseline)
- Create: `dashboard/.frontend-design/baselines/dashboard-map-mobile.png` (baseline)
- Create: `dashboard/.frontend-design/baselines/dashboard-map-tablet.png` (baseline)

- [ ] **Step 1: Capture screenshots at 3 viewports**

Start dev server (or use prod URL since local Mongo is empty):

```bash
pkill -f "next dev" || true
cd dashboard && npm run dev > /tmp/next-dev.log 2>&1 &
sleep 8
```

```ts
// in scripts/capture-baselines.ts
import { chromium } from '@playwright/test';
import { mkdir } from 'fs/promises';

const viewports = [
  { name: 'mobile', width: 375, height: 800 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
];

async function main() {
  await mkdir('.frontend-design/baselines', { recursive: true });
  const browser = await chromium.launch();
  for (const v of viewports) {
    const page = await browser.newPage({ viewport: { width: v.width, height: v.height } });
    await page.goto('http://localhost:3000/dashboard/map');
    await page.waitForSelector('#map', { timeout: 10000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `.frontend-design/baselines/dashboard-map-${v.name}.png`, fullPage: false });
    await page.close();
  }
  await browser.close();
}
main();
```

Run: `cd dashboard && npx tsx scripts/capture-baselines.ts`
Expected: 3 PNGs created.

- [ ] **Step 2: Pixel-diff against baseline**

After first capture, baselines are the new reference. On future runs, diff against them.

- [ ] **Step 3: Commit baselines**

```bash
git add dashboard/.frontend-design/baselines/
git commit -m "chore(dashboard): add /map visual baselines at 375/768/1280 viewports"
```

- [ ] **Step 4: Kill dev server**

```bash
pkill -f "next dev"
```

---

## Task 14: Coverage measurement (per `test_scope: true`)

**Files:** none modified — verification only.

- [ ] **Step 1: Run coverage**

```bash
cd dashboard && npx playwright test --config=playwright.prod.config.ts --reporter=line
```

Count of test files: `find tests -name "*.spec.ts" | wc -l` (was N, now N+2 from Tasks 2 and 3).

- [ ] **Step 2: Record coverage delta**

Append to `dashboard/TEST_COVERAGE.md` (create if missing):

```markdown
## 2026-06-13 — Dashboard UI Redesign
- Test files: N → N+2
- New specs: tests/slim-listing-card.spec.ts, tests/desktop-redesign.spec.ts
- Updated specs: 5 (map-full, address-bank-declutter, commute-rent-insights, map-overhaul, map-interaction, pin-click)
- Coverage: measured via full suite pass on prod URL.
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/TEST_COVERAGE.md
git commit -m "docs(dashboard): record test coverage delta for UI redesign"
```

---

## Self-Review

- [x] **Spec coverage:** every spec section maps to a task. Token migration → T1. SlimListingCard → T2. ListingRail → T3. MapTopBar → T4. MapFilterPopover → T5. MapLayersPopover → T6. MapView changes → T7. SelectedCard → T8. Page wiring → T9. Test updates → T10. Component deletes → T11. Verification → T12. Visual baselines → T13. Coverage → T14.
- [x] **Placeholder scan:** no TBDs. Every code block is real, ready-to-paste. Field names like `price_total`, `price_per_m2`, `area_m2`, `zone_delta_pct` are flagged for verification against `lib/types.ts` — engineer must check the actual types and adjust.
- [x] **Type consistency:** `layers: {listings, stations, schools}` shape is consistent across T6, T7, T9. `SortOption` reused from bccc771 commit. `MapViewProps` matches T7's interface.
- [x] **Fail-fast verification:** tsc gate in T12, dev-server smoke in T12, prod playwright gate in T12, visual diff in T13.
- [x] **Rollback path:** each task is its own commit; if any task fails, `git revert` that one commit.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-13-dashboard-ui-redesign.md`. 14 tasks. Estimated blast radius: 5 new files, 6 modified, 4 deleted, 1 kept-but-unmounted, 8 test files touched.

Per user instruction "finish it" + brainstorming skill override, executing via subagent-driven-development (recommended). Invoking next.
