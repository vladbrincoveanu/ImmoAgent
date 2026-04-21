# Preis auf Anfrage Price Estimation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Impute `price_total` for "Preis auf Anfrage" listings using `area_m2 × €7000` and display with a `~` prefix.

**Architecture:** A `config.json` holds the `PRICE_PER_SQM` constant. Both API routes (`/api/listings/map`, `/api/listings/top`) independently impute `price_total` when null and add a `price_is_estimated` boolean flag. The UI components (`ListingCard`, `MapView` popup) read the flag and prefix the price with `~`.

**Tech Stack:** Next.js 14 App Router, TypeScript, MongoDB, react-leaflet

---

## Task 1: Create config.json

**Files:**
- Create: `dashboard/config.json`

- [ ] **Step 1: Create config.json**

```json
{
  "PRICE_PER_SQM": 7000
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/config.json
git commit -m "feat(dashboard): add PRICE_PER_SQM config constant"
```

---

## Task 2: Add price_is_estimated to types

**Files:**
- Modify: `dashboard/lib/types.ts:17-31` (MapListing interface)
- Modify: `dashboard/lib/types.ts:1-13` (ListingBase interface)

- [ ] **Step 1: Read current types.ts**

```typescript
// dashboard/lib/types.ts — current MapListing interface
export interface MapListing {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  image_url: string | null;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
}
```

- [ ] **Step 2: Edit types.ts — add `price_is_estimated` to MapListing**

Find:
```typescript
export interface MapListing {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  image_url: string | null;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
}
```

Replace with:
```typescript
export interface MapListing {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  image_url: string | null;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: CoordinateSource;
  landmark_hint: string | null;
  price_is_estimated?: boolean;
}
```

- [ ] **Step 3: Edit types.ts — add `price_is_estimated` to ListingBase**

Find:
```typescript
export interface ListingBase {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  processed_at: number | null;
  image_url: string | null;
}
```

Replace with:
```typescript
export interface ListingBase {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  processed_at: number | null;
  image_url: string | null;
  price_is_estimated?: boolean;
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/types.ts
git commit -m "feat(dashboard): add price_is_estimated to ListingBase and MapListing"
```

---

## Task 3: Update /api/listings/map — imputation logic

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts:73-101` (the .map() block)

- [ ] **Step 1: Read current map route mapping block**

```typescript
// dashboard/app/api/listings/map/route.ts — current mapping (lines 73-101)
const result: MapListing[] = listings.map((l: WithId<Document>) => {
  // Use actual coordinates if available, otherwise fall back to district centroid
  let coordinates = l.coordinates as { lat: number; lon: number } | null | undefined;
  let coordinate_source: string = (l.coordinate_source as string) || 'none';

  if (!coordinates) {
    const centroid = getDistrictCentroid(l.bezirk as string | null);
    if (centroid) {
      coordinates = centroid;
      coordinate_source = 'district';
    }
  }

  return {
    _id: l._id.toString(),
    title: l.title,
    url: l.url,
    source_enum: l.source_enum,
    bezirk: l.bezirk,
    price_total: l.price_total,
    area_m2: l.area_m2,
    rooms: l.rooms,
    score: l.score,
    image_url: l.image_url || null,
    coordinates: coordinates ?? null,
    coordinate_source: coordinate_source as MapListing['coordinate_source'],
    landmark_hint: l.landmark_hint || null,
  };
});
```

- [ ] **Step 2: Add PRICE_PER_SQM constant and imputation logic**

Find the import section at the top of the file (after line 4), add:
```typescript
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('@/../../config.json');
```

And in the `listings.map()` block, replace the `price_total` and add `price_is_estimated`:

```typescript
const PRICE_PER_SQM = (config?.PRICE_PER_SQM as number | undefined) ?? 7000;
const hasPrice = typeof l.price_total === 'number' && (l.price_total as number) > 0;
const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && (l.area_m2 as number) > 0;
const price_total = hasPrice
  ? (l.price_total as number)
  : price_is_estimated
    ? Math.round((l.area_m2 as number) * PRICE_PER_SQM)
    : null;
```

Then update the return object to include `price_is_estimated`.

Full replacement of the mapping block:
```typescript
const result: MapListing[] = listings.map((l: WithId<Document>) => {
  // Price imputation: use area_m2 × PRICE_PER_SQM when price_total is missing
  const PRICE_PER_SQM = (config?.PRICE_PER_SQM as number | undefined) ?? 7000;
  const hasPrice = typeof l.price_total === 'number' && (l.price_total as number) > 0;
  const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && (l.area_m2 as number) > 0;
  const price_total = hasPrice
    ? (l.price_total as number)
    : price_is_estimated
      ? Math.round((l.area_m2 as number) * PRICE_PER_SQM)
      : null;

  // Use actual coordinates if available, otherwise fall back to district centroid
  let coordinates = l.coordinates as { lat: number; lon: number } | null | undefined;
  let coordinate_source: string = (l.coordinate_source as string) || 'none';

  if (!coordinates) {
    const centroid = getDistrictCentroid(l.bezirk as string | null);
    if (centroid) {
      coordinates = centroid;
      coordinate_source = 'district';
    }
  }

  return {
    _id: l._id.toString(),
    title: l.title,
    url: l.url,
    source_enum: l.source_enum,
    bezirk: l.bezirk,
    price_total,
    area_m2: l.area_m2,
    rooms: l.rooms,
    score: l.score,
    image_url: l.image_url || null,
    coordinates: coordinates ?? null,
    coordinate_source: coordinate_source as MapListing['coordinate_source'],
    landmark_hint: l.landmark_hint || null,
    price_is_estimated,
  };
});
```

- [ ] **Step 3: Verify build**

```bash
cd dashboard && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` with no new errors in `route.ts`

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts
git commit -m "feat(dashboard): impute price from area_m2 × PRICE_PER_SQM for null-price listings"
```

---

## Task 4: Update /api/listings/top — imputation logic

**Files:**
- Modify: `dashboard/app/api/listings/top/route.ts:50-63` (the .map() block)

- [ ] **Step 1: Read current top route mapping block**

```typescript
// dashboard/app/api/listings/top/route.ts — current mapping (lines 50-63)
const result = listings.map((l: WithId<ListingDocument>) => ({
  _id: l._id.toString(),
  title: l.title,
  url: l.url,
  source_enum: l.source_enum,
  bezirk: l.bezirk,
  price_total: l.price_total,
  area_m2: l.area_m2,
  rooms: l.rooms,
  score: l.score,
  processed_at: l.processed_at,
  image_url: l.image_url || l.minio_image_path || null,
  url_is_valid: l.url_is_valid !== false,
}));
```

- [ ] **Step 2: Add PRICE_PER_SQM require and imputation logic**

Add after the imports at the top:
```typescript
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('@/../../config.json');
```

Replace the `result = listings.map(...)` block with:
```typescript
const PRICE_PER_SQM = (config?.PRICE_PER_SQM as number | undefined) ?? 7000;

const result = listings.map((l: WithId<ListingDocument>) => {
  const hasPrice = typeof l.price_total === 'number' && l.price_total > 0;
  const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && l.area_m2 > 0;
  const price_total = hasPrice
    ? l.price_total
    : price_is_estimated
      ? Math.round(l.area_m2 * PRICE_PER_SQM)
      : null;

  return {
    _id: l._id.toString(),
    title: l.title,
    url: l.url,
    source_enum: l.source_enum,
    bezirk: l.bezirk,
    price_total,
    area_m2: l.area_m2,
    rooms: l.rooms,
    score: l.score,
    processed_at: l.processed_at,
    image_url: l.image_url || l.minio_image_path || null,
    url_is_valid: l.url_is_valid !== false,
    price_is_estimated,
  };
});
```

- [ ] **Step 3: Verify build**

```bash
cd dashboard && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/api/listings/top/route.ts
git commit -m "feat(dashboard): impute price in top listings API"
```

---

## Task 5: Update ListingCard — ~ prefix for estimated prices

**Files:**
- Modify: `dashboard/components/ListingCard.tsx:69-73` (price display)

- [ ] **Step 1: Read current price display (lines 69-73)**

```tsx
<p className="font-bold text-heading text-base mb-1">
  {listing.price_total
    ? `€${listing.price_total.toLocaleString('de-AT')}`
    : 'Price on request'}
</p>
```

- [ ] **Step 2: Replace with ~ prefix logic**

```tsx
<p className="font-bold text-heading text-base mb-1">
  {listing.price_total != null
    ? `${listing.price_is_estimated ? '~' : ''}€${listing.price_total.toLocaleString('de-AT')}`
    : 'Price on request'}
</p>
```

- [ ] **Step 3: Verify build**

```bash
cd dashboard && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/ListingCard.tsx
git commit -m "feat(dashboard): show ~ prefix for estimated prices in ListingCard"
```

---

## Task 6: Update MapView popup — ~ prefix for estimated prices

**Files:**
- Modify: `dashboard/components/MapView.tsx:91-107` (Popup block)

- [ ] **Step 1: Read current Popup price display (lines 91-96)**

```tsx
<p className="text-accent font-bold">
  {listing.price_total ? `€${listing.price_total.toLocaleString()}` : 'N/A'}
</p>
```

- [ ] **Step 2: Replace with ~ prefix logic**

```tsx
<p className="text-accent font-bold">
  {listing.price_total != null
    ? `${listing.price_is_estimated ? '~' : ''}€${listing.price_total.toLocaleString()}`
    : 'N/A'}
</p>
```

- [ ] **Step 3: Verify build**

```bash
cd dashboard && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/MapView.tsx
git commit -m "feat(dashboard): show ~ prefix for estimated prices in MapView popup"
```

---

## Final Verification

- [ ] **Step 1: Full build**

```bash
cd dashboard && npm run build
```

Expected: all routes compile, no TypeScript errors.

- [ ] **Step 2: Run lint**

```bash
cd dashboard && npm run lint
```

Expected: no errors.
