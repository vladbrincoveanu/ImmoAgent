# Map — Click-to-Fly, Honest Coords, District Price Choropleth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Vienna map fly to a listing's exact location on selection, stop plotting fabricated (district-centroid) coordinates, and add a semi-transparent per-district price choropleth.

**Architecture:** Two phases inside the existing Next.js + react-leaflet map. Phase 1 adds a `SelectionAnimator` (react-leaflet `useMap` + `map.flyTo`) and removes the district-centroid fallback in the map API so un-geocoded listings return `coordinates:null` (already filtered out of the viewport). Phase 2 adds a committed 23-Bezirk GeoJSON asset, a `/api/district-heatmap` aggregation route, a `DistrictHeatmapLayer` `<GeoJSON>` overlay colored by avg €/m² (scale aligned to `scoring.py` NORMALIZATION_RANGES), plus a layer toggle and legend.

**Tech Stack:** Next.js 15 App Router, react-leaflet 4.2.1, Leaflet, MongoDB aggregation, Playwright (E2E), TypeScript, Tailwind.

**Spec:** `docs/superpowers/specs/2026-07-03-map-flyto-heatmap-design.md` (`ui_scope: true`, `test_scope: true`).

**Working dir:** all `npx`/`node` commands run from `dashboard/`. Dev server: `npm run dev` (localhost:3000). Follow `.claude/rules/ui-testing.md` — run only the changed spec per cycle, full suite as the final gate.

---

## File Structure

**Phase 1**
- Modify `dashboard/components/MapView.tsx` — add `SelectionAnimator` component (flyTo on selection, hidden-map guard, test hook exposing the live map on its container), mount it in `<MapContainer>`.
- Modify `dashboard/app/api/listings/map/route.ts` — delete the centroid fallback (lines 102–115) and the now-unused `resolveCoordinates` import (line 7); return `coordinates:null` / `coordinate_source:'none'` for un-geocoded listings.
- Modify `dashboard/app/dashboard/map/page.tsx:84` — SSE-merged new listings get `coordinate_source:'none'` (they already carry `coordinates:null`).
- (Optional) Modify `dashboard/components/ListingRail.tsx` + `dashboard/app/dashboard/map/page.tsx` — show a "N without map location" note.
- Create `dashboard/tests/map-flyto-honest.spec.ts` — Phase 1 E2E.

**Phase 2**
- Create `dashboard/scripts/build-districts-geojson.mjs` — fetch/transform the district boundaries.
- Create `dashboard/public/vienna-districts.geojson` — committed asset (output of the script).
- Create `dashboard/app/api/district-heatmap/route.ts` — per-district avg €/m² + count.
- Create `dashboard/lib/heatmap-color.ts` — price→color scale.
- Modify `dashboard/components/MapView.tsx` — add `DistrictHeatmapLayer`, a legend, and `heatmap` to `LayerState`.
- Modify `dashboard/components/MapLayersPopover.tsx` — add the `heatmap` row + widen types.
- Modify `dashboard/app/dashboard/map/page.tsx` — default `heatmap:false`, `layerCounts.heatmap`.
- Create `dashboard/tests/map-heatmap.spec.ts` — Phase 2 E2E.

---

# PHASE 1 — Click→Fly + Honest Coordinates

## Task 1: SelectionAnimator (fly the map to the selected listing)

**Files:**
- Modify: `dashboard/components/MapView.tsx`
- Test: `dashboard/tests/map-flyto-honest.spec.ts` (written in Task 4; behavior verified there)

- [ ] **Step 1: Add the `SelectionAnimator` component**

Insert after `BoundsTracker` (after line 112 in `MapView.tsx`). `useMap`, `useEffect`, `MapListing`, and `L` are already imported.

```tsx
function SelectionAnimator({
  selectedListingId,
  listings,
}: {
  selectedListingId: string | null;
  listings: MapListing[];
}) {
  const map = useMap();

  // Test hook: expose the live Leaflet map on its container element so E2E
  // tests can read map.getCenter(). Harmless in production.
  useEffect(() => {
    (map.getContainer() as unknown as { __map?: L.Map }).__map = map;
  }, [map]);

  useEffect(() => {
    if (!selectedListingId) return;
    const target = listings.find((l) => l._id === selectedListingId);
    if (!target || !target.coordinates) return;
    // A hidden map (the mobile instance at desktop width, 0x0 / display:none)
    // must never hijack focus — same guard as BoundsTracker (commit 2f32f06).
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;
    map.flyTo([target.coordinates.lat, target.coordinates.lon], 16, {
      duration: 1.2,
      easeLinearity: 0.25,
    });
  }, [map, selectedListingId, listings]);

  return null;
}
```

- [ ] **Step 2: Mount `SelectionAnimator` inside `<MapContainer>`**

In the `MapView` return, add it right after `<BoundsTracker ... />` (currently line 298):

```tsx
        <BoundsTracker onBoundsChange={onBoundsChange} />
        <SelectionAnimator selectedListingId={selectedListingId} listings={listings} />
        <MapClickHandler onMapClick={onMapClick} />
```

- [ ] **Step 3: Type-check**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new errors (pre-existing errors unrelated to `MapView.tsx` are acceptable; none should reference `SelectionAnimator`).

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/MapView.tsx
git commit -m "feat(dashboard/map): fly map to selected listing on selection"
```

---

## Task 2: Remove the district-centroid fabrication (honest coordinates)

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts:7,102-115`
- Modify: `dashboard/app/dashboard/map/page.tsx:84`
- Test: `dashboard/tests/map-flyto-honest.spec.ts` (Task 4)

- [ ] **Step 1: Replace the centroid fallback block in `route.ts`**

Replace the current lines 102–115:

```tsx
      // Use actual coordinates if available, otherwise fall back to district centroid
      let coordinates = l.coordinates as { lat: number; lon: number } | null | undefined;
      const COORD_SOURCES = new Set(['exact', 'landmark', 'district', 'none']);
      const rawSource = (l.coordinate_source as string) || 'none';
      let coordinate_source: 'exact' | 'landmark' | 'district' | 'none' =
        COORD_SOURCES.has(rawSource) ? (rawSource as 'exact' | 'landmark' | 'district' | 'none') : 'none';

      if (!coordinates) {
        const centroid = resolveCoordinates(undefined, l.bezirk as string | null);
        if (centroid) {
          coordinates = centroid;
          coordinate_source = 'district';
        }
      }
```

with (honest coords — no fabrication; `let` → `const`):

```tsx
      // Honest coordinates: only plot listings we could actually geocode.
      // Un-geocoded listings return coordinates:null and are hidden from the
      // map (the viewport filter in page.tsx already drops null-coord
      // listings). No more district-centroid fabrication.
      const coordinates = (l.coordinates as { lat: number; lon: number } | null | undefined) ?? null;
      const COORD_SOURCES = new Set(['exact', 'landmark', 'district', 'none']);
      const rawSource = (l.coordinate_source as string) || 'none';
      const coordinate_source: 'exact' | 'landmark' | 'district' | 'none' = !coordinates
        ? 'none'
        : COORD_SOURCES.has(rawSource)
          ? (rawSource as 'exact' | 'landmark' | 'district' | 'none')
          : 'exact';
```

- [ ] **Step 2: Remove the now-unused import in `route.ts`**

Delete line 7:

```tsx
import { resolveCoordinates } from '@/lib/district-centroids';
```

(Leave `dashboard/lib/district-centroids.ts` in place — `getDistrictCentroid`/`DISTRICT_CENTROIDS` may be used elsewhere; only this import becomes unused.)

- [ ] **Step 3: Fix the SSE merge source tag in `page.tsx:84`**

Change:

```tsx
          coordinate_source: 'district',
```

to:

```tsx
          coordinate_source: 'none',
```

- [ ] **Step 4: Type-check + lint**

Run: `cd dashboard && npx tsc --noEmit && npx eslint app/api/listings/map/route.ts app/dashboard/map/page.tsx`
Expected: no unused-var error for `resolveCoordinates`; no `prefer-const` error; no new type errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts dashboard/app/dashboard/map/page.tsx
git commit -m "fix(dashboard/map): stop fabricating district-centroid coords; return null for un-geocoded"
```

---

## Task 3 (Optional): Rail "without map location" honesty note

Spec marks this optional. Implement only if the executor confirms it reads cleanly; otherwise skip and note the skip.

**Files:**
- Modify: `dashboard/components/ListingRail.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Add a `noCoordCount` prop to `ListingRail`**

In `ListingRail.tsx`, extend the props interface (after line 12) and header (after line 32):

```tsx
interface ListingRailProps {
  listings: MapListing[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortMode: SortOption;
  onSortChange: (s: SortOption) => void;
  noCoordCount?: number;
}
```

```tsx
export function ListingRail({ listings, selectedId, onSelect, sortMode, onSortChange, noCoordCount = 0 }: ListingRailProps) {
```

Add under the `rail-count` span (after line 32):

```tsx
        {noCoordCount > 0 && (
          <span data-testid="rail-no-coord" className="text-[11px] text-ink-3">
            {noCoordCount} without map location
          </span>
        )}
```

- [ ] **Step 2: Compute and pass it from `page.tsx`**

Add a memo near `viewportListings` (after line 171):

```tsx
  const noCoordCount = useMemo(
    () => filteredListings.filter((l) => !l.coordinates).length,
    [filteredListings]
  );
```

Pass to the desktop `<ListingRail>` (currently lines 285–291):

```tsx
          <ListingRail
            listings={sortedRailListings}
            selectedId={selectedListingId}
            onSelect={setSelectedListingId}
            sortMode={railSort}
            onSortChange={setRailSort}
            noCoordCount={noCoordCount}
          />
```

- [ ] **Step 3: Type-check + commit**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new errors.

```bash
git add dashboard/components/ListingRail.tsx dashboard/app/dashboard/map/page.tsx
git commit -m "feat(dashboard/map): rail shows count of listings without map location"
```

---

## Task 4: Phase 1 E2E verification (fly + honest markers)

**Files:**
- Create: `dashboard/tests/map-flyto-honest.spec.ts`

- [ ] **Step 1: Write the Phase 1 spec**

Fixtures: four listings with real coords across central Vienna + one with `coordinates:null, coordinate_source:'none'`. The `none` listing must NOT get a marker; clicking a rail card must fly the map so its coords become the map center.

```ts
import { test, expect } from '@playwright/test';

// Four geocoded fixtures (in the default zoom-13 viewport) + one un-geocoded.
const GEOCODED = [
  { lat: 48.2089, lon: 16.3965 },
  { lat: 48.2050, lon: 16.3700 },
  { lat: 48.2100, lon: 16.3600 },
  { lat: 48.1984, lon: 16.3850 },
].map((c, i) => ({
  _id: `geo-${i}`,
  title: `Geocoded ${i}`,
  url: `https://example.com/g${i}`,
  source_enum: 'willhaben',
  bezirk: '1030',
  price_total: 300000 + i * 10000,
  area_m2: 70 + i,
  rooms: 3,
  score: 40 - i,
  image_url: null,
  coordinates: { lat: c.lat, lon: c.lon },
  coordinate_source: 'exact',
  landmark_hint: null,
  price_is_estimated: false,
}));

const NO_COORD = {
  _id: 'none-0',
  title: 'No location listing',
  url: 'https://example.com/n0',
  source_enum: 'willhaben',
  bezirk: '1100',
  price_total: 250000,
  area_m2: 60,
  rooms: 2,
  score: 30,
  image_url: null,
  coordinates: null,
  coordinate_source: 'none',
  landmark_hint: null,
  price_is_estimated: false,
};

const FIXTURES = [...GEOCODED, NO_COORD];

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ listings: FIXTURES, total: FIXTURES.length }),
    });
  });
  await page.route('**/api/listings/stream**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' });
  });
});

test('un-geocoded listing has no marker on the desktop map', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  const markers = page.locator('.map-desktop .leaflet-marker-icon');
  await expect(markers.first()).toBeVisible({ timeout: 10000 });
  // Exactly the four geocoded fixtures render; the 'none' listing does not.
  await expect(markers).toHaveCount(4);
});

test('clicking a rail card flies the map to that listing', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  await expect(page.locator('.map-desktop .leaflet-marker-icon').first()).toBeVisible({ timeout: 10000 });

  // Click the rail card for geo-3 (bottom of the viewport).
  await page.locator('[data-testid="slim-listing-card"][data-id="geo-3"]').click();

  // flyTo runs ~1.2s; poll the live map center exposed on the container.
  await expect
    .poll(async () => {
      return page.evaluate(() => {
        const el = document.querySelector('.map-desktop .leaflet-container') as
          | (Element & { __map?: { getCenter(): { lat: number; lng: number } } })
          | null;
        const c = el?.__map?.getCenter();
        return c ? Math.round(c.lat * 1000) : null;
      });
    }, { timeout: 8000 })
    .toBe(Math.round(48.1984 * 1000));

  const lng = await page.evaluate(() => {
    const el = document.querySelector('.map-desktop .leaflet-container') as
      | (Element & { __map?: { getCenter(): { lat: number; lng: number } } })
      | null;
    return el?.__map?.getCenter().lng ?? null;
  });
  expect(lng).not.toBeNull();
  expect(Math.abs((lng as number) - 16.3850)).toBeLessThan(0.002);
});
```

- [ ] **Step 2: Start the dev server (once) and run the spec**

```bash
cd dashboard && npm run dev &   # wait for "Ready" on localhost:3000
npx playwright test tests/map-flyto-honest.spec.ts --reporter=dot
```
Expected: 2 passed. If the fly test fails on the center value, confirm the `__map` hook (Task 1 Step 1) is present and the card `data-id` matches `geo-3`.

- [ ] **Step 3: Regression — existing bounds-clobber spec still passes**

Run: `npx playwright test tests/map-bounds-clobber.spec.ts --reporter=dot`
Expected: 1 passed (SelectionAnimator's guard must not break the hidden-map behavior).

- [ ] **Step 4: Commit**

```bash
git add dashboard/tests/map-flyto-honest.spec.ts
git commit -m "test(dashboard/map): verify fly-to-selection and honest (no-fabricated-coord) markers"
```

---

# PHASE 2 — District Price Choropleth

## Task 5: Build & commit `vienna-districts.geojson`

**Files:**
- Create: `dashboard/scripts/build-districts-geojson.mjs`
- Create: `dashboard/public/vienna-districts.geojson`

- [ ] **Step 1: Write the build script**

```js
// dashboard/scripts/build-districts-geojson.mjs
// Fetch Vienna Bezirksgrenzen (district boundaries) from the City of Vienna
// open-data WFS, remap to 4-digit postal 'bezirk' codes ('1010'..'1230'),
// round coordinates to shrink the file, and write public/vienna-districts.geojson.
import { writeFileSync } from 'node:fs';

const WFS =
  'https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature&version=1.1.0' +
  '&typeName=ogdwien:BEZIRKSGRENZEOGD&srsName=EPSG:4326&outputFormat=json';

const round = (n) => Math.round(n * 1e4) / 1e4; // ~11 m precision
function roundCoords(c) {
  return typeof c[0] === 'number' ? [round(c[0]), round(c[1])] : c.map(roundCoords);
}

const res = await fetch(WFS);
if (!res.ok) throw new Error(`WFS fetch failed: ${res.status}`);
const raw = await res.json();

const features = raw.features.map((f) => {
  const p = f.properties;
  const bezNr = Number(p.BEZNR ?? p.BEZ ?? p.DISTRICT_CODE);
  const bezirk = `1${String(bezNr).padStart(2, '0')}0`;
  return {
    type: 'Feature',
    properties: { bezirk, name: p.NAMEG ?? p.NAME ?? bezirk },
    geometry: { type: f.geometry.type, coordinates: roundCoords(f.geometry.coordinates) },
  };
});

const bad = features.filter((f) => f.properties.bezirk.includes('NaN'));
if (bad.length) {
  throw new Error(
    `Unmapped district code — inspect property keys: ${Object.keys(raw.features[0].properties).join(', ')}`,
  );
}
if (features.length !== 23) {
  throw new Error(`Expected 23 districts, got ${features.length}`);
}

const out = { type: 'FeatureCollection', features };
writeFileSync(new URL('../public/vienna-districts.geojson', import.meta.url), JSON.stringify(out));
console.log(`Wrote ${features.length} districts, ${(JSON.stringify(out).length / 1024).toFixed(0)}KB`);
```

- [ ] **Step 2: Run it (network — sandbox override may be required)**

Run: `node dashboard/scripts/build-districts-geojson.mjs`
- `data.wien.gv.at` is not in the sandbox allowlist; if the fetch fails with a network/permission error, re-run with the sandbox disabled for this one command.
Expected stdout: `Wrote 23 districts, <N>KB`. If it throws "Unmapped district code", read the printed property keys and update the `bezNr` line to the correct field, then re-run.

- [ ] **Step 3: Sanity-check the asset**

Run: `node -e "const g=require('./dashboard/public/vienna-districts.geojson');console.log(g.features.length, g.features.map(f=>f.properties.bezirk).sort().slice(0,3).join(','), g.features.map(f=>f.properties.bezirk).sort().slice(-1)[0])"`
Expected: `23 1010,1020,1030 1230`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/scripts/build-districts-geojson.mjs dashboard/public/vienna-districts.geojson
git commit -m "feat(dashboard/map): add 23-Bezirk boundary GeoJSON + build script"
```

---

## Task 6: `/api/district-heatmap` route

**Files:**
- Create: `dashboard/app/api/district-heatmap/route.ts`

- [ ] **Step 1: Write the route**

Reuses the same validity filters and `$avg`/`$divide` shape as `route.ts:75-88`, grouped across all districts.

```ts
import { NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET() {
  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }

    const stats = await db
      .collection('listings')
      .aggregate<{ _id: string; avg_price_per_m2: number; count: number }>([
        {
          $match: {
            url_is_valid: { $ne: false },
            listing_status: { $ne: 'taken' },
            price_total: { $gt: 0 },
            area_m2: { $gt: 0 },
            bezirk: { $nin: [null, ''] },
          },
        },
        {
          $group: {
            _id: '$bezirk',
            avg_price_per_m2: { $avg: { $divide: ['$price_total', '$area_m2'] } },
            count: { $sum: 1 },
          },
        },
      ])
      .toArray();

    const districts: Record<string, { avg_price_per_m2: number; count: number }> = {};
    for (const s of stats) {
      if (typeof s._id === 'string' && s._id.length > 0) {
        districts[s._id] = { avg_price_per_m2: Math.round(s.avg_price_per_m2), count: s.count };
      }
    }

    return NextResponse.json({ districts });
  } catch (err) {
    console.error('[/api/district-heatmap]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/api/district-heatmap/route.ts
git commit -m "feat(dashboard/api): district-heatmap route returns avg €/m² + count per Bezirk"
```

---

## Task 7: Color scale + `DistrictHeatmapLayer` + legend

**Files:**
- Create: `dashboard/lib/heatmap-color.ts`
- Modify: `dashboard/components/MapView.tsx`

- [ ] **Step 1: Write the color scale util**

Anchored to `scoring.py` `NORMALIZATION_RANGES['price_per_m2']` (min 3500 = cheapest/green, max 8000 = priciest/red).

```ts
// dashboard/lib/heatmap-color.ts
// Price-per-m² → color, aligned to scoring.py NORMALIZATION_RANGES.price_per_m2
// (min_val 3500 = best/cheapest = green, max_val 8000 = worst/priciest = red).
export const HEATMAP_MIN = 3500;
export const HEATMAP_MAX = 8000;

type RGB = [number, number, number];
const GREEN: RGB = [26, 152, 80];
const YELLOW: RGB = [255, 221, 100];
const RED: RGB = [215, 48, 39];

const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);
const mix = (c1: RGB, c2: RGB, t: number) =>
  `rgb(${lerp(c1[0], c2[0], t)}, ${lerp(c1[1], c2[1], t)}, ${lerp(c1[2], c2[2], t)})`;

export function priceToColor(pricePerM2: number): string {
  const t = Math.max(0, Math.min(1, (pricePerM2 - HEATMAP_MIN) / (HEATMAP_MAX - HEATMAP_MIN)));
  return t <= 0.5 ? mix(GREEN, YELLOW, t / 0.5) : mix(YELLOW, RED, (t - 0.5) / 0.5);
}
```

- [ ] **Step 2: Extend imports + `LayerState` in `MapView.tsx`**

Update the react-leaflet import (line 3) to add `GeoJSON`, and add supporting imports below the existing Leaflet import (line 4):

```tsx
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import type { Feature, GeoJsonObject } from 'geojson';
import { priceToColor } from '@/lib/heatmap-color';
```

Extend `LayerState` (lines 14–18):

```tsx
export interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
  heatmap: boolean;
}
```

- [ ] **Step 3: Add the `DistrictHeatmapLayer` component**

Insert after `SchoolsLayer` (after line 266). Self-fetches the asset + stats when `visible`.

```tsx
type DistrictStats = Record<string, { avg_price_per_m2: number; count: number }>;

function DistrictHeatmapLayer({ visible }: { visible: boolean }) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [stats, setStats] = useState<DistrictStats>({});

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    Promise.all([
      fetch('/vienna-districts.geojson').then((r) => r.json()),
      fetch('/api/district-heatmap').then((r) => r.json()),
    ])
      .then(([gj, s]) => {
        if (cancelled) return;
        setGeojson(gj as GeoJsonObject);
        setStats((s?.districts ?? {}) as DistrictStats);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [visible]);

  if (!visible || !geojson) return null;

  const styleFn = (feature?: Feature): L.PathOptions => {
    const bezirk = feature?.properties?.bezirk as string | undefined;
    const stat = bezirk ? stats[bezirk] : undefined;
    if (!stat) return { fillOpacity: 0, weight: 0, opacity: 0 };
    return { fillColor: priceToColor(stat.avg_price_per_m2), fillOpacity: 0.45, color: '#ffffff', weight: 1 };
  };

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const bezirk = feature.properties?.bezirk as string | undefined;
    const stat = bezirk ? stats[bezirk] : undefined;
    if (bezirk && stat) {
      layer.bindTooltip(
        `${bezirk} · Ø €${stat.avg_price_per_m2.toLocaleString('de-AT')}/m² · ${stat.count} listings`,
        { sticky: true, direction: 'top' },
      );
    }
  };

  // key forces GeoJSON to re-apply styles once async stats arrive (it snapshots
  // style/onEachFeature at mount).
  return <GeoJSON key={Object.keys(stats).length} data={geojson} style={styleFn} onEachFeature={onEachFeature} />;
}
```

- [ ] **Step 4: Mount the layer + legend in `MapView`**

In the return, add the layer after `<TileLayer>` and before `<BoundsTracker>` (polygons live in `overlayPane`, below markers in `markerPane`, so pins stay clickable):

```tsx
        {layers.heatmap && <DistrictHeatmapLayer visible={layers.heatmap} />}

        <BoundsTracker onBoundsChange={onBoundsChange} />
```

Add the legend just before the closing `</div>` of the outer wrapper (after the `layersPopoverSlot` block, ~line 318):

```tsx
      {layers.heatmap && (
        <div
          data-testid="heatmap-legend"
          className="absolute bottom-4 left-3 z-[1000] bg-white/95 rounded-lg shadow px-3 py-2 text-[11px]"
        >
          <div className="font-semibold mb-1">Ø €/m²</div>
          <div
            className="h-2 w-32 rounded"
            style={{ background: 'linear-gradient(to right, rgb(26,152,80), rgb(255,221,100), rgb(215,48,39))' }}
          />
          <div className="flex justify-between w-32 mt-0.5">
            <span>3.5k</span>
            <span>8k+</span>
          </div>
        </div>
      )}
```

- [ ] **Step 5: Type-check**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new errors. (`LayerState` now requires `heatmap`; page.tsx is updated in Task 8 — a temporary error there is expected until Task 8 is done. Do Task 8 next.)

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/heatmap-color.ts dashboard/components/MapView.tsx
git commit -m "feat(dashboard/map): district price choropleth layer + legend + color scale"
```

---

## Task 8: Wire the heatmap layer toggle

**Files:**
- Modify: `dashboard/components/MapLayersPopover.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Extend `MapLayersPopover` types + add the row**

Update the interface (lines 3–15) and `ROWS` (lines 17–21):

```tsx
interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
  heatmap: boolean;
}

interface MapLayersPopoverProps {
  open: boolean;
  onClose: () => void;
  layers: LayerState;
  onToggle: (key: 'listings' | 'stations' | 'schools' | 'heatmap') => void;
  counts: { listings: number; stations: number; schools: number; heatmap: number };
}

const ROWS: Array<{ key: 'listings' | 'stations' | 'schools' | 'heatmap'; name: string; color: string; dotColor: string }> = [
  { key: 'listings', name: 'Listings', color: '#16243a', dotColor: 'bg-ink' },
  { key: 'stations', name: 'U-Bahn stations', color: '#3b6fd4', dotColor: 'bg-[#3b6fd4]' },
  { key: 'schools', name: 'Schools', color: '#2ba56b', dotColor: 'bg-[#2ba56b]' },
  { key: 'heatmap', name: 'District prices', color: '#d73027', dotColor: 'bg-[#d73027]' },
];
```

- [ ] **Step 2: Default state + counts in `page.tsx`**

`layers` default (lines 57–61):

```tsx
  const [layers, setLayers] = useState<LayerState>({
    listings: true,
    stations: false,
    schools: false,
    heatmap: false,
  });
```

`layerCounts` memo (lines 230–234) — 23 Bezirke:

```tsx
  const layerCounts = useMemo(() => ({
    listings: listings.length,
    stations: 0,
    schools: 0,
    heatmap: 23,
  }), [listings]);
```

(The existing `onToggle={(k) => setLayers((s) => ({ ...s, [k]: !s[k] }))}` already handles the new key.)

- [ ] **Step 3: Type-check**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no errors (Task 6/7 errors now resolved).

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/MapLayersPopover.tsx dashboard/app/dashboard/map/page.tsx
git commit -m "feat(dashboard/map): heatmap layer toggle in layers popover"
```

---

## Task 9: Phase 2 E2E verification (choropleth)

**Files:**
- Create: `dashboard/tests/map-heatmap.spec.ts`

- [ ] **Step 1: Write the Phase 2 spec**

Mocks `/vienna-districts.geojson` (2 tiny polygons) and `/api/district-heatmap` for determinism.

```ts
import { test, expect } from '@playwright/test';

const LISTINGS = [
  {
    _id: 'geo-0', title: 'A', url: 'https://example.com/0', source_enum: 'willhaben',
    bezirk: '1070', price_total: 300000, area_m2: 70, rooms: 3, score: 40,
    image_url: null, coordinates: { lat: 48.2, lon: 16.35 }, coordinate_source: 'exact',
    landmark_hint: null, price_is_estimated: false,
  },
];

const GEOJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { bezirk: '1070', name: 'Neubau' },
      geometry: { type: 'Polygon', coordinates: [[[16.33, 48.19], [16.36, 48.19], [16.36, 48.21], [16.33, 48.21], [16.33, 48.19]]] },
    },
    {
      type: 'Feature',
      properties: { bezirk: '1010', name: 'Innere Stadt' },
      geometry: { type: 'Polygon', coordinates: [[[16.36, 48.20], [16.39, 48.20], [16.39, 48.22], [16.36, 48.22], [16.36, 48.20]]] },
    },
  ],
};

const HEATMAP = { districts: { '1070': { avg_price_per_m2: 6200, count: 42 }, '1010': { avg_price_per_m2: 9000, count: 12 } } };

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ listings: LISTINGS, total: LISTINGS.length }) }));
  await page.route('**/api/listings/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }));
  await page.route('**/vienna-districts.geojson', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GEOJSON) }));
  await page.route('**/api/district-heatmap', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(HEATMAP) }));
});

test('toggling District prices renders choropleth polygons, tooltip and legend', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');
  await expect(page.locator('.map-desktop .leaflet-marker-icon').first()).toBeVisible({ timeout: 10000 });

  // Open the layers popover and toggle the heatmap on.
  await page.locator('[data-testid="layers-btn"]').click();
  await page.locator('[data-testid="layer-row-heatmap"]').click();

  // Two polygons render in the desktop overlay pane.
  const polys = page.locator('.map-desktop .leaflet-overlay-pane path');
  await expect(polys.first()).toBeVisible({ timeout: 10000 });
  await expect(polys).toHaveCount(2);

  // Legend visible while active.
  await expect(page.locator('[data-testid="heatmap-legend"]')).toBeVisible();

  // Hover a polygon → tooltip shows district + €/m².
  await polys.first().hover();
  await expect(page.locator('.leaflet-tooltip')).toContainText('/m²');

  // Toggle off → polygons and legend gone.
  await page.locator('[data-testid="layer-row-heatmap"]').click();
  await expect(page.locator('[data-testid="heatmap-legend"]')).toHaveCount(0);
  await expect(page.locator('.map-desktop .leaflet-overlay-pane path')).toHaveCount(0);
});
```

- [ ] **Step 2: Run the spec**

Run: `cd dashboard && npx playwright test tests/map-heatmap.spec.ts --reporter=dot`
Expected: 1 passed. If polygons don't appear, verify the layers popover opens (`layers-btn`) and the `layer-row-heatmap` row exists (Task 8), and that the `key={Object.keys(stats).length}` remount fired after stats loaded.

- [ ] **Step 3: Commit**

```bash
git add dashboard/tests/map-heatmap.spec.ts
git commit -m "test(dashboard/map): verify district price choropleth toggle, tooltip, legend"
```

---

# FINAL GATES

## Task 10: Visual verification (ui_scope)

Per `.claude/rules/ui-testing.md`, screenshot to disk only (do NOT pull screenshots into context). Confirm the redesigned map renders at all viewports with the new features.

**Files:**
- Create: `dashboard/tests/map-visual-check.spec.ts` (screenshots to `dashboard/.test-out/`)

- [ ] **Step 1: Write a screenshot spec (3 viewports)**

```ts
import { test } from '@playwright/test';

const FIXTURES = [{
  _id: 'geo-0', title: 'A', url: 'https://example.com/0', source_enum: 'willhaben',
  bezirk: '1070', price_total: 300000, area_m2: 70, rooms: 3, score: 40,
  image_url: null, coordinates: { lat: 48.2, lon: 16.35 }, coordinate_source: 'exact',
  landmark_hint: null, price_is_estimated: false,
}];

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ listings: FIXTURES, total: 1 }) }));
  await page.route('**/api/listings/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }));
});

for (const w of [375, 768, 1280]) {
  test(`map renders @ ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto('/dashboard/map');
    await page.locator('.leaflet-container').first().waitFor({ timeout: 10000 });
    await page.screenshot({ path: `.test-out/map-${w}.png`, fullPage: false });
  });
}
```

- [ ] **Step 2: Run + eyeball the PNGs on disk (not in context)**

Run: `cd dashboard && npx playwright test tests/map-visual-check.spec.ts --reporter=dot`
Expected: 3 passed; `dashboard/.test-out/map-375.png|map-768.png|map-1280.png` exist and show the map (not a blank screen).

- [ ] **Step 3: Commit**

```bash
git add dashboard/tests/map-visual-check.spec.ts
git commit -m "test(dashboard/map): visual smoke screenshots at 375/768/1280"
```

## Task 11: Full suite gate + coverage record (test_scope)

- [ ] **Step 1: Run the full Playwright suite**

Run: `cd dashboard && npx playwright test --reporter=line`
Expected: 0 failures. Investigate and fix any regression before proceeding (do not proceed with a red suite).

- [ ] **Step 2: Confirm zero console errors on the key routes**

The suite already asserts on `/`, `/dashboard`, `/dashboard/map`. If a dedicated console-error check spec exists, run it; otherwise verify no test logged `error|fail` from the console:
Run: `npx playwright test --reporter=line 2>&1 | grep -iE "console (error|warning)|pageerror" || echo "no console errors surfaced"`
Expected: `no console errors surfaced` (or a clean list).

- [ ] **Step 3: Record test coverage of new behavior**

New behavior is covered by new specs: `map-flyto-honest.spec.ts` (fly + honest markers), `map-heatmap.spec.ts` (choropleth), `map-visual-check.spec.ts` (render), plus the retained `map-bounds-clobber.spec.ts` regression. Note the added spec count in the final summary. (The dashboard uses Playwright E2E, not a line-coverage tool; "coverage" here = every new user-visible behavior has a passing E2E assertion.)

- [ ] **Step 4: Stop the dev server**

Run: `pkill -f "next dev"`

- [ ] **Step 5: Final commit (if anything changed) + summary**

```bash
git add -A
git commit -m "chore(dashboard/map): map fly-to + honest coords + choropleth — full suite green" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage:**
- Click→fly → Task 1 + Task 4.
- Hide un-geocoded (drop centroid fallback) → Task 2 (route + page.tsx:84) + Task 4 marker-absence test.
- Rail count honesty (optional) → Task 3.
- 23-Bezirk GeoJSON asset → Task 5.
- `/api/district-heatmap` → Task 6.
- `DistrictHeatmapLayer` (color scale from scoring.py, 0.45 opacity, tooltip, below markers) → Task 7.
- Layer toggle + legend → Task 7 (legend) + Task 8 (toggle).
- Testing (P1, P2, final gate) → Tasks 4, 9, 11.
- `ui_scope` → Task 10. `test_scope` → Task 11.

**Placeholder scan:** none — every code step has full code; commands have expected output.

**Type consistency:** `LayerState` gains `heatmap: boolean` in all three definitions (MapView, MapLayersPopover, page default); `onToggle`/`counts` union widened consistently; `priceToColor`, `DistrictStats`, and the `{ districts }` API shape match between Task 6, 7, and the Task 9 mock; the `__map` test hook (Task 1) is read by Task 4's `.__map?.getCenter()`; rail card selector `[data-testid="slim-listing-card"][data-id="…"]` matches `SlimListingCard.tsx` (`data-testid="slim-listing-card"`, `data-id={listing._id}`); layers button `[data-testid="layers-btn"]` matches `MapTopBar.tsx`; popover row `[data-testid="layer-row-heatmap"]` matches `MapLayersPopover` (`layer-row-${key}`).

**Known risks / notes:**
- WFS property name (`BEZNR`) is the documented field; the script fails loud with the real keys if it differs (Task 5 Step 2).
- `data.wien.gv.at` needs a sandbox override for the fetch (Task 5 Step 2).
- Heatmap polygons stay interactive (for hover tooltips) but sit in `overlayPane` below `markerPane`, so marker clicks are never stolen (spec requirement satisfied without `interactive:false`).
- `layerCounts.heatmap` is a static `23` (cosmetic count in the popover); the layer self-fetches real stats.
