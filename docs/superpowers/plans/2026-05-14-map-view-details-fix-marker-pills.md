# Map: Fix "View Details" Button + Restyle Price Marker Pills

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the non-functional "View details" button on the map popup card, and restyle map price pills to be smaller by default and larger/bolder when hovered or highlighted.

**Architecture:** Two independent fixes. (1) The "View details" bug: `ListingDetail` renders at `z-50` while `SelectedCard` stays at `z-[1000]`, hiding the modal behind the card; fix by adding a `handleViewDetails` callback that clears `highlightedId` (dismisses SelectedCard) and bumping `ListingDetail` to `z-[2000]`. (2) Marker pill sizing: replace the single `createPriceIcon` function with a size-tier system — small pill for default state, medium for hover, large for highlighted.

**Tech Stack:** React 18, Next.js App Router, Leaflet (via react-leaflet), TypeScript, Tailwind CSS

---

## File Map

| File | Change |
|------|--------|
| `dashboard/app/dashboard/map/page.tsx` | Add `handleViewDetails` callback; pass to SelectedCard |
| `dashboard/components/ListingDetail.tsx` | Bump outer div from `z-50` → `z-[2000]` |
| `dashboard/components/MapView.tsx` | Restyle `createPriceIcon` with size-tier pill styles |
| `dashboard/tests/smoke.spec.ts` | Add test: clicking "View details" opens detail modal |

---

### Task 1: Fix "View details" — clear SelectedCard when detail opens

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`

**Context:** Currently `onViewDetails={setDetailId}` is passed to `SelectedCard`. Clicking "View details" sets `detailId` but leaves `highlightedId` set, so `SelectedCard` stays rendered at `z-[1000]`. The `ListingDetail` modal renders behind it at `z-50`. Fix: introduce `handleViewDetails` that sets `detailId` and clears `highlightedId`.

- [ ] **Step 1: Add `handleViewDetails` callback in MapPage**

In `dashboard/app/dashboard/map/page.tsx`, find the existing callbacks block (around line 98–114) and add after `handleCloseDetail`:

```tsx
const handleViewDetails = useCallback((id: string) => {
  setDetailId(id);
  setHighlightedId(null);
}, []);
```

- [ ] **Step 2: Wire `handleViewDetails` into SelectedCard**

In the same file, find:
```tsx
<SelectedCard
  listing={highlightedListing}
  onClose={handleCloseDetail}
  onViewDetails={setDetailId}
/>
```

Replace `onViewDetails={setDetailId}` with:
```tsx
<SelectedCard
  listing={highlightedListing}
  onClose={handleCloseDetail}
  onViewDetails={handleViewDetails}
/>
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/dashboard/map/page.tsx
git commit -m "fix(map): clear SelectedCard when View Details clicked"
```

---

### Task 2: Fix "View details" — bump ListingDetail z-index

**Files:**
- Modify: `dashboard/components/ListingDetail.tsx`

**Context:** `ListingDetail` renders at `z-50` (z-index: 50). `SelectedCard` is at `z-[1000]`. Even after Task 1 clears `highlightedId` (which unmounts SelectedCard), other Leaflet controls are at z-index 800–1000. Bumping to `z-[2000]` ensures the modal always appears above everything.

- [ ] **Step 1: Bump z-index on ListingDetail outer div**

In `dashboard/components/ListingDetail.tsx` line 51, find:
```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
```

Replace with:
```tsx
<div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4">
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/ListingDetail.tsx
git commit -m "fix(map): raise ListingDetail z-index above Leaflet controls"
```

---

### Task 3: Restyle price marker pills — size tiers

**Files:**
- Modify: `dashboard/components/MapView.tsx`

**Context:** All 151 markers currently render the same price pill regardless of state, cluttering the map. The new design: default state = small pill (9px font, 1px border), hovered = medium pill (10px font, 1.5px border), highlighted = large pill (12px font, 2px border, drop shadow emphasis).

- [ ] **Step 1: Replace `createPriceIcon` with a tiered version**

In `dashboard/components/MapView.tsx`, find and replace the entire `createPriceIcon` function (lines 26–33):

```tsx
// OLD — single size for all states
function createPriceIcon(price: number, color: string, size: number): L.DivIcon {
  return L.divIcon({
    html: `<div style="background:${color};color:white;font-size:10px;font-weight:700;padding:2px 5px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.35);border:1.5px solid white;font-family:system-ui,-apple-system,sans-serif;">€${formatPrice(price)}</div>`,
    iconSize: [size * 3, size * 1.5],
    iconAnchor: [size * 1.5, size * 0.75],
    className: '',
  });
}
```

Replace with:

```tsx
type MarkerTier = 'default' | 'hovered' | 'highlighted';

function getTier(state: PinState): MarkerTier {
  if (state === 'highlighted') return 'highlighted';
  if (state === 'hovered') return 'hovered';
  return 'default';
}

const TIER_STYLES: Record<MarkerTier, {
  fontSize: string;
  padding: string;
  border: string;
  shadow: string;
  width: number;
  height: number;
}> = {
  default: {
    fontSize: '9px',
    padding: '1px 4px',
    border: '1px solid white',
    shadow: '0 1px 3px rgba(0,0,0,0.3)',
    width: 44,
    height: 16,
  },
  hovered: {
    fontSize: '10px',
    padding: '2px 5px',
    border: '1.5px solid white',
    shadow: '0 2px 6px rgba(0,0,0,0.35)',
    width: 52,
    height: 20,
  },
  highlighted: {
    fontSize: '12px',
    padding: '3px 7px',
    border: '2px solid white',
    shadow: '0 3px 8px rgba(0,0,0,0.45)',
    width: 64,
    height: 24,
  },
};

function createPriceIcon(price: number, color: string, tier: MarkerTier): L.DivIcon {
  const s = TIER_STYLES[tier];
  return L.divIcon({
    html: `<div style="background:${color};color:white;font-size:${s.fontSize};font-weight:700;padding:${s.padding};border-radius:999px;white-space:nowrap;box-shadow:${s.shadow};border:${s.border};font-family:system-ui,-apple-system,sans-serif;">€${formatPrice(price)}</div>`,
    iconSize: [s.width, s.height],
    iconAnchor: [s.width / 2, s.height / 2],
    className: '',
  });
}
```

- [ ] **Step 2: Update `MarkerLayer` to pass `tier` instead of `size`**

In the `MarkerLayer` `useEffect` (around line 154–174), find:

```tsx
const state = getPinState(listing, highlightedId ?? null, hoveredId ?? null);
const color = getPinColor(state);
const size = getPinSize(state);
const icon = createPriceIcon(listing.price_total ?? 0, color, size);
```

Replace with:

```tsx
const state = getPinState(listing, highlightedId ?? null, hoveredId ?? null);
const color = getPinColor(state);
const tier = getTier(state);
const icon = createPriceIcon(listing.price_total ?? 0, color, tier);
```

- [ ] **Step 3: Remove now-unused `getPinSize` function and size constants**

Find and delete these lines (around lines 14–18 and 55–63):

```tsx
const EXACT_SIZE = 14;
const LANDMARK_SIZE = 14;
const DISTRICT_SIZE = 14;
const HIGHLIGHT_SIZE = 20;
const HOVER_SIZE = 18;
```

```tsx
function getPinSize(state: PinState): number {
  switch (state) {
    case 'highlighted': return HIGHLIGHT_SIZE;
    case 'hovered': return HOVER_SIZE;
    case 'landmark': return LANDMARK_SIZE;
    case 'district': return DISTRICT_SIZE;
    default: return EXACT_SIZE;
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/MapView.tsx
git commit -m "feat(map): tiered price pill sizing — small default, larger on hover/highlight"
```

---

### Task 4: Playwright smoke test — "View details" opens modal

**Files:**
- Modify: `dashboard/tests/smoke.spec.ts`

**Context:** The existing smoke tests check page loads and map renders, but do not exercise the "View details" flow. Add a test that mocks the map listings API, clicks a marker pin, waits for SelectedCard to appear, clicks "View details", and asserts the detail modal is visible.

- [ ] **Step 1: Add test to `smoke.spec.ts`**

Open `dashboard/tests/smoke.spec.ts`. Append the following test to the existing `test.describe` block (or as a standalone test):

```ts
test('View details opens listing detail modal', async ({ page }) => {
  // Intercept map listings API with minimal fixture
  await page.route('**/api/listings/map*', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        listings: [
          {
            _id: '507f1f77bcf86cd799439011',
            title: 'Test Apartment',
            url: 'https://example.com/listing',
            source_enum: 'willhaben',
            bezirk: '1020',
            price_total: 350000,
            area_m2: 65,
            rooms: 3,
            score: 42,
            image_url: null,
            coordinates: { lat: 48.213, lon: 16.39 },
            coordinate_source: 'exact',
            landmark_hint: null,
          },
        ],
        total: 1,
      }),
    });
  });

  // Intercept detail API
  await page.route('**/api/listings/507f1f77bcf86cd799439011', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        _id: '507f1f77bcf86cd799439011',
        title: 'Test Apartment',
        url: 'https://example.com/listing',
        source_enum: 'willhaben',
        bezirk: '1020',
        price_total: 350000,
        area_m2: 65,
        rooms: 3,
        score: 42,
        image_url: null,
        address: null,
        year_built: null,
        floor: null,
        condition: null,
        heating: null,
        parking: null,
        betriebskosten: null,
        energy_class: null,
        hwb_value: null,
        fgee_value: null,
        calculated_monatsrate: null,
        total_monthly_cost: null,
        ubahn_walk_minutes: null,
        school_walk_minutes: null,
        infrastructure_distances: {},
        processed_at: null,
        url_is_valid: true,
      }),
    });
  });

  await page.goto('/dashboard/map');
  // Wait for map to render
  await page.waitForSelector('.leaflet-container', { timeout: 10000 });
  // Wait for marker to appear (price pill)
  await page.waitForSelector('.leaflet-marker-icon', { timeout: 8000 });
  // Click the marker
  await page.locator('.leaflet-marker-icon').first().click();
  // SelectedCard should appear with "View details"
  await page.waitForSelector('button:has-text("View details")', { timeout: 5000 });
  await page.click('button:has-text("View details")');
  // Detail modal should be visible — identified by "Open Original" link inside
  await page.waitForSelector('a:has-text("Open Original")', { timeout: 5000 });
  await expect(page.locator('a:has-text("Open Original")')).toBeVisible();
});
```

- [ ] **Step 2: Run the new test only**

```bash
cd dashboard && npx playwright test --grep "View details opens" --reporter=list
```

Expected: PASS. If FAIL with "marker icon not found", increase timeout or check that map API mock is being applied correctly (the route intercept must match the full URL pattern).

- [ ] **Step 3: Run full smoke suite**

```bash
cd dashboard && npx playwright test --reporter=list
```

Expected: all tests pass, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add dashboard/tests/smoke.spec.ts
git commit -m "test(map): smoke test for View Details button opening listing modal"
```

---

### Task 5: Manual UI verification

**Files:** None — verification only.

- [ ] **Step 1: Start dev server**

```bash
cd dashboard && npm run dev &
sleep 10
```

- [ ] **Step 2: Open `/dashboard/map` in browser**

Navigate to `http://localhost:3000/dashboard/map`. Verify:
- Map loads with price pills on markers
- Default (non-selected) markers show small pills (9px, thin border)
- Hovering a marker shows medium pill
- Clicking a marker shows the SelectedCard popup at bottom center

- [ ] **Step 3: Test "View details" flow**

Click any marker → SelectedCard appears. Click "View details". Verify:
- SelectedCard disappears
- Dark modal backdrop appears covering the map
- White modal card visible above backdrop with listing details
- X button and Escape key close the modal

- [ ] **Step 4: Stop dev server**

```bash
pkill -f "next dev"
```

---

## Self-Review

**Spec coverage:**
- ✅ "View details" fix: Task 1 (state), Task 2 (z-index)
- ✅ Tiered price pills: Task 3
- ✅ Test coverage: Task 4
- ✅ Manual verification: Task 5

**Placeholder scan:** None found. All steps contain exact code.

**Type consistency:**
- `MarkerTier` type defined in Task 3 Step 1, used in `getTier` and `createPriceIcon` in same task
- `handleViewDetails` defined in Task 1 Step 1, wired in Task 1 Step 2
- `tier` variable in Task 3 Step 2 matches the `MarkerTier` return type of `getTier`
