# Dashboard Security, Dependency, and Performance Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the public dashboard, refresh safe dependencies, reduce map/list work, and remove proven-dead dashboard code without changing listing behavior.

**Architecture:** Keep HTTP parsing in route handlers, move shared listing query/projection/presentation logic into a route-only module, and use small dependency-free helpers for rate limiting and geo math. Preserve response envelopes and current score/filter semantics while reducing Mongo materialization and client rendering work.

**Tech Stack:** Next.js 15 App Router, TypeScript, MongoDB Node driver, React 18, React-Leaflet 4, Jest, Playwright, npm audit, pip-audit.

---

## File Map

Create:

- `dashboard/lib/listing-data.ts` - shared validated listing filters, projections, district stats, and response presenters.
- `dashboard/lib/geo.ts` - pure Haversine and walking-time helpers.
- `dashboard/lib/rate-limit.ts` - bounded in-process sliding-window limiter.
- `dashboard/middleware.ts` - public expensive-read route limiter.
- `dashboard/lib/geo.test.ts` - geo helper tests.
- `dashboard/lib/rate-limit.test.ts` - limiter tests.
- `dashboard/lib/listing-data.test.ts` - projection, filter, and presenter contract tests.
- `dashboard/app/api/route-contracts.test.ts` - stable public API `400/429/503/500` status contracts.
- `dashboard/tests/dashboard-performance.spec.ts` - mocked API/browser hot-path regressions.

Modify:

- `dashboard/package.json`
- `dashboard/package-lock.json`
- `dashboard/next.config.js`
- `dashboard/lib/validators.ts`
- `dashboard/lib/validators.test.ts`
- `dashboard/app/api/listings/map/route.ts`
- `dashboard/app/api/listings/top/route.ts`
- `dashboard/app/api/listings/[id]/route.ts`
- `dashboard/app/api/insights/route.ts`
- `dashboard/app/api/geo/infrastructure/route.ts`
- `dashboard/app/api/district-heatmap/route.ts`
- `dashboard/app/dashboard/page.tsx`
- `dashboard/app/dashboard/map/page.tsx`
- `dashboard/components/MapView.tsx`
- `dashboard/components/ListingCard.tsx`
- `dashboard/components/SlimListingCard.tsx`
- `dashboard/components/CommuteBadge.tsx`

Delete after proof:

- `dashboard/components/ThemeProvider.tsx`
- `dashboard/components/ThemeToggle.tsx`
- `dashboard/components/ListingSidebar.tsx`

Do not modify `.env*`, `config.json`, secrets, historical specs, or uncertain Python analyzer files.

## Milestone 0: Baseline and Safety Net

### Task 1: Capture Baseline

**Files:**
- Create: `scratchpad/dashboard-security-performance-baseline.txt` (local measurement artifact, not committed)

- [ ] **Step 1: Verify isolated worktree state**

Run:

```bash
git status --short --branch
git log --oneline -3
```

Expected: feature worktree contains only the approved design and plan commits before implementation starts.

- [ ] **Step 2: Install dashboard dependencies from the lockfile**

Run:

```bash
cd dashboard
npm ci
```

Expected: install completes without editing `package-lock.json`.

- [ ] **Step 3: Record security and static baselines**

Run:

```bash
npm audit --json > ../scratchpad/dashboard-npm-audit-before.json
npm audit --omit=dev --json > ../scratchpad/dashboard-npm-audit-prod-before.json
npm ls --depth=0 > ../scratchpad/dashboard-npm-tree-before.txt
npx tsc --noEmit > ../scratchpad/dashboard-tsc-before.txt
```

Expected: audit files record the known `nanoid` and `js-yaml` findings; typecheck output is preserved even if pre-existing errors appear.

- [ ] **Step 4: Record Python dependency disposition**

From the repository root, run:

```bash
python -m pip_audit -r Project/requirements.txt --format json > scratchpad/python-audit-before.json
```

Expected: known `diskcache 5.6.3` finding is recorded with no fixed version. Do not remove active `outlines` code to make this command look clean.

- [ ] **Step 5: Record browser hot-path baseline**

Run the existing production-style dashboard suite against the configured local Mongo instance:

```bash
cd dashboard
npx playwright test tests/page-health.spec.ts tests/map-filter-render.spec.ts tests/profile-sort.spec.ts --reporter=line
```

If local Mongo has no data, record the data precondition and use the mocked performance spec from Task 8 for deterministic before/after measurements.

- [ ] **Step 6: Do not commit baseline artifacts**

Confirm `scratchpad/dashboard-security-performance-baseline.txt` and generated JSON/TXT measurements are ignored or remove them by renaming into the existing scratchpad convention. No baseline output belongs in the feature commit.

## Milestone 1: Dependency and Public API Security

### Task 2: Add Failing Validator and Rate-Limiter Tests

**Files:**
- Modify: `dashboard/lib/validators.test.ts`
- Create: `dashboard/lib/rate-limit.test.ts`

- [ ] **Step 1: Add strict numeric validator cases**

Append tests to `dashboard/lib/validators.test.ts`:

```ts
describe('strict numeric parsing', () => {
  it('rejects partial numeric prefixes', () => {
    expect(validateMinScore('10abc')).toBe(0);
    expect(validateLimit('3items', 200)).toBe(200);
  });

  it('rejects non-finite values', () => {
    expect(validateMinScore('NaN')).toBe(0);
    expect(validateMinScore('Infinity')).toBe(0);
    expect(validateLimit('Infinity', 200)).toBe(200);
  });
});
```

- [ ] **Step 2: Add deterministic rate-limit tests**

Create `dashboard/lib/rate-limit.test.ts` with an injectable clock:

```ts
import { describe, expect, it } from '@jest/globals';
import { SlidingWindowRateLimiter } from './rate-limit';

describe('SlidingWindowRateLimiter', () => {
  it('allows the configured number of requests and then rejects', () => {
    const limiter = new SlidingWindowRateLimiter();
    expect(limiter.check('ip', 2, 60_000, 1_000).allowed).toBe(true);
    expect(limiter.check('ip', 2, 60_000, 1_001).allowed).toBe(true);
    const blocked = limiter.check('ip', 2, 60_000, 1_002);
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.resetAt).toBe(61_000);
  });

  it('resets an expired window and removes expired entries', () => {
    const limiter = new SlidingWindowRateLimiter();
    expect(limiter.check('ip', 1, 1_000, 1_000).allowed).toBe(true);
    expect(limiter.check('ip', 1, 1_000, 2_000).allowed).toBe(true);
    expect(limiter.size()).toBe(1);
    limiter.clearExpired(3_001);
    expect(limiter.size()).toBe(0);
  });
});
```

- [ ] **Step 3: Run the focused tests and verify failure**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/validators.test.ts lib/rate-limit.test.ts
```

Expected: the new validator cases fail against prefix-accepting `parseFloat`/`parseInt`, and the limiter test fails because `rate-limit.ts` does not exist yet.

### Task 3: Implement Strict Validators and Limiter

**Files:**
- Modify: `dashboard/lib/validators.ts`
- Create: `dashboard/lib/rate-limit.ts`
- Test: `dashboard/lib/validators.test.ts`, `dashboard/lib/rate-limit.test.ts`

- [ ] **Step 1: Replace prefix parsing with finite full-string parsing**

Add private parsers and route all numeric validators through them:

```ts
const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;
const INTEGER = /^[+-]?\d+$/;

function parseFiniteDecimal(input: string | null): number | null {
  if (input == null || !DECIMAL.test(input.trim())) return null;
  const value = Number(input.trim());
  return Number.isFinite(value) ? value : null;
}

function parseFiniteInteger(input: string | null): number | null {
  if (input == null || !INTEGER.test(input.trim())) return null;
  const value = Number(input.trim());
  return Number.isSafeInteger(value) ? value : null;
}
```

`validateMinScore` uses `parseFiniteDecimal`; `validateLimit` uses `parseFiniteInteger`; existing defaults and clamps remain unchanged.

- [ ] **Step 2: Implement bounded sliding-window storage**

Create `dashboard/lib/rate-limit.ts`:

```ts
export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

type Entry = { count: number; resetAt: number };

export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();

  check(key: string, limit: number, windowMs: number, now = Date.now()): RateLimitResult {
    this.clearExpired(now);
    const current = this.entries.get(key);
    const entry = current && current.resetAt > now
      ? { count: current.count + 1, resetAt: current.resetAt }
      : { count: 1, resetAt: now + windowMs };
    this.entries.set(key, entry);
    const allowed = entry.count <= limit;
    return {
      allowed,
      remaining: allowed ? Math.max(0, limit - entry.count) : 0,
      resetAt: entry.resetAt,
    };
  }

  clearExpired(now = Date.now()): void {
    for (const [key, entry] of this.entries) {
      if (entry.resetAt <= now) this.entries.delete(key);
    }
  }

  size(): number {
    return this.entries.size;
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
```

The middleware calls `clearExpired` on every check. This keeps the process-local map bounded by expiry rather than allowing one permanent entry per client.

- [ ] **Step 3: Run focused tests and verify pass**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/validators.test.ts lib/rate-limit.test.ts
```

Expected: all validator and limiter tests pass.

- [ ] **Step 4: Refresh safe current-major dependencies**

Update the existing override block in `dashboard/package.json` without changing framework major versions:

```json
"overrides": {
  "postcss": "^8.5.24",
  "brace-expansion": "^5.0.9",
  "js-yaml": "^3.15.1",
  "nanoid": "^3.3.18",
  "sharp": "^0.35.0"
}
```

Refresh only packages whose existing ranges already permit current-major updates:

```bash
cd dashboard
npm update @playwright/test @types/leaflet @types/node @types/react autoprefixer nodemailer postcss ts-jest
npm install --package-lock-only
npm ci
```

Do not add `--force`. Do not update Next.js, React, React-Leaflet, MongoDB, Tailwind, or TypeScript to a new major. Run the focused audit after reinstall:

```bash
npm audit --json
npm audit --omit=dev --json
```

Expected: `nanoid` is at least `3.3.18`, `js-yaml` is at least `3.15.1`, and neither audit reports a high or critical vulnerability.

### Task 4: Wire Public API Limiting and Security Headers

**Files:**
- Create: `dashboard/middleware.ts`
- Create: `dashboard/app/api/route-contracts.test.ts`
- Modify: `dashboard/next.config.js`
- Modify: `dashboard/package.json`
- Modify: `dashboard/package-lock.json`
- Test: `dashboard/lib/rate-limit.test.ts`

- [ ] **Step 1: Add middleware for expensive public reads**

Create `dashboard/middleware.ts`:

```ts
import { NextRequest, NextResponse } from 'next/server';
import { apiRateLimiter } from '@/lib/rate-limit';

const LIMIT = 30;
const WINDOW_MS = 60_000;

function clientKey(request: NextRequest): string {
  return request.headers.get('x-real-ip')
    ?? request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
    ?? 'unknown';
}

export function middleware(request: NextRequest) {
  const result = apiRateLimiter.check(clientKey(request), LIMIT, WINDOW_MS);
  const response = result.allowed
    ? NextResponse.next()
    : NextResponse.json(
        { error: 'Too many requests. Please try again later.', retryAfter: 60 },
        { status: 429 },
      );

  response.headers.set('X-RateLimit-Limit', String(LIMIT));
  response.headers.set('X-RateLimit-Remaining', String(result.remaining));
  response.headers.set('X-RateLimit-Reset', String(Math.ceil(result.resetAt / 1000)));
  if (!result.allowed) response.headers.set('Retry-After', '60');
  return response;
}

export const config = {
  matcher: [
    '/api/listings/:path*',
    '/api/insights',
    '/api/district-heatmap',
  ],
};
```

Use platform-provided `x-real-ip` first. The forwarded address is a fallback for deployments that do not provide the former. Document in the module that this is per-process defense in depth.

- [ ] **Step 2: Add low-risk response headers**

Extend `dashboard/next.config.js` without changing `images.remotePatterns`:

```js
headers: async () => ([
  {
    source: '/(.*)',
    headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
    ],
  },
]),
```

- [ ] **Step 3: Add HTTP status contract tests**

Create `dashboard/app/api/route-contracts.test.ts`:

```ts
import { describe, expect, it, jest } from '@jest/globals';
import { NextRequest } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { GET as getMap } from './listings/map/route';
import { GET as getDetail } from './listings/[id]/route';

jest.mock('@/lib/mongodb', () => ({
  getDb: jest.fn(),
  ObjectId: class ObjectId {},
}));

const mockedGetDb = jest.mocked(getDb);

describe('public API status contracts', () => {
  it('returns 503 when the map database is unavailable', async () => {
    mockedGetDb.mockReturnValue(null);
    const response = await getMap(new NextRequest('http://localhost/api/listings/map'));
    expect(response.status).toBe(503);
  });

  it('returns 400 before database access for an invalid detail id', async () => {
    const response = await getDetail(
      new NextRequest('http://localhost/api/listings/bad'),
      { params: Promise.resolve({ id: 'bad' }) },
    );
    expect(response.status).toBe(400);
    expect(mockedGetDb).not.toHaveBeenCalled();
  });

  it('returns 500 for an unexpected map database failure', async () => {
    mockedGetDb.mockReturnValue({ collection: () => { throw new Error('boom'); } } as never);
    const response = await getMap(new NextRequest('http://localhost/api/listings/map'));
    expect(response.status).toBe(500);
  });
});
```

The `429` contract is covered by the deterministic limiter result tests because middleware uses that result directly. Reset the mock between tests with `beforeEach(() => mockedGetDb.mockReset())` if the test runner retains mock state.

- [ ] **Step 4: Run build/type checks**

Run:

```bash
cd dashboard
npx tsc --noEmit
npm run build
```

Expected: middleware and config compile without changing the existing image allowlist or route output.

- [ ] **Step 5: Commit Milestone 1**

Run:

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/lib/validators.ts dashboard/lib/validators.test.ts dashboard/lib/rate-limit.ts dashboard/lib/rate-limit.test.ts dashboard/middleware.ts dashboard/next.config.js dashboard/app/api/route-contracts.test.ts
git commit -m "fix: harden public dashboard api"
```

## Milestone 2: Shared Listing Data and API Efficiency

### Task 5: Add Geo Helper Tests and Implementation

**Files:**
- Create: `dashboard/lib/geo.test.ts`
- Create: `dashboard/lib/geo.ts`
- Modify: `dashboard/components/CommuteBadge.tsx`
- Modify: `dashboard/app/dashboard/page.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Write geo tests**

Create `dashboard/lib/geo.test.ts`:

```ts
import { describe, expect, it } from '@jest/globals';
import { estimateWalkMinutes, haversineKm } from './geo';

describe('geo helpers', () => {
  it('returns zero for identical coordinates', () => {
    expect(haversineKm({ lat: 48.2, lon: 16.37 }, { lat: 48.2, lon: 16.37 })).toBe(0);
  });

  it('is symmetric and produces a positive Vienna-scale distance', () => {
    const a = { lat: 48.2082, lon: 16.3738 };
    const b = { lat: 48.198, lon: 16.369 };
    expect(haversineKm(a, b)).toBeGreaterThan(1);
    expect(haversineKm(a, b)).toBeCloseTo(haversineKm(b, a), 8);
  });

  it('uses the walking speed used by the current commute filter', () => {
    expect(estimateWalkMinutes(4.8)).toBe(60);
  });
});
```

- [ ] **Step 2: Run the new test and verify failure**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/geo.test.ts
```

Expected: fail because `geo.ts` does not exist.

- [ ] **Step 3: Implement the pure helper**

Create `dashboard/lib/geo.ts`:

```ts
export type GeoPoint = { lat: number; lon: number };

const EARTH_RADIUS_KM = 6371;
const WALK_KMH = 4.8;

export function haversineKm(a: GeoPoint, b: GeoPoint): number {
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLon = (b.lon - a.lon) * Math.PI / 180;
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;
  const x = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(x));
}

export function estimateWalkMinutes(distanceKm: number): number {
  return Math.round((distanceKm / WALK_KMH) * 60);
}
```

- [ ] **Step 4: Replace duplicate client calculations**

Remove local `WALK_KMH` and `haversineKm` definitions from both dashboard pages and replace them with:

```ts
import { estimateWalkMinutes, haversineKm } from '@/lib/geo';

const walkMin = estimateWalkMinutes(haversineKm(origin, destination));
```

Use the same helper in `CommuteBadge`. Do not change `dashboard/app/api/commute/route.ts` in this task; its transit-specific calculation has additional semantics.

- [ ] **Step 5: Run geo and existing commute tests**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/geo.test.ts lib/district-centroids.test.ts
npx playwright test tests/commute-rent-insights.spec.ts --reporter=dot
```

Expected: helper tests pass and commute UI behavior remains unchanged.

### Task 6: Test Shared Listing Data Contracts

**Files:**
- Create: `dashboard/lib/listing-data.test.ts`
- Create: `dashboard/lib/listing-data.ts`

- [ ] **Step 1: Define contract fixtures and failing tests**

Create tests around pure exports from `listing-data.ts`:

```ts
import { describe, expect, it } from '@jest/globals';
import {
  MAP_PROJECTION,
  TOP_PROJECTION,
  buildListingSort,
  presentMapListing,
} from './listing-data';

const doc = {
  _id: '507f1f77bcf86cd799439011',
  title: 'Test flat',
  url: 'https://example.test/listing',
  source_enum: 'willhaben',
  bezirk: '1010',
  price_total: 420000,
  area_m2: 60,
  rooms: 2,
  score: 72,
  scores: { default: 72, urban_professional: 81 },
  coordinates: null,
  coordinate_source: 'none',
};

describe('listing-data contracts', () => {
  it('projects only fields needed by each list surface', () => {
    expect(MAP_PROJECTION.title).toBe(1);
    expect(TOP_PROJECTION.processed_at).toBe(1);
    expect(MAP_PROJECTION.structured_analysis).toBeUndefined();
  });

  it('sorts profile scores without changing sort option names', () => {
    expect(buildListingSort('urban_professional', 'score_desc')).toEqual({
      'scores.urban_professional': -1,
      processed_at: -1,
    });
  });

  it('preserves district-centroid fallback and profile score', () => {
    const result = presentMapListing(doc, {
      profile: 'urban_professional',
      pricePerSqm: 7000,
      zoneAverage: 400000,
    });
    expect(result.score).toBe(81);
    expect(result.coordinates).not.toBeNull();
    expect(result.coordinate_source).toBe('district');
    expect(result.price_vs_avg_pct).toBe(5);
  });
});
```

The fixture intentionally omits optional database fields. The presenter must remain null-safe.

- [ ] **Step 2: Run the contract test and verify failure**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/listing-data.test.ts
```

Expected: fail because the shared module and exports do not exist.

- [ ] **Step 3: Implement projections and shared query helpers**

Define the module's stable exports:

```ts
import { DEFAULT_PROFILE } from './profile';
import type { SortOption } from './validators';

export const MAP_PROJECTION = {
  title: 1, url: 1, source_enum: 1, bezirk: 1, price_total: 1,
  area_m2: 1, rooms: 1, score: 1, scores: 1, image_url: 1,
  coordinates: 1, coordinate_source: 1, landmark_hint: 1,
  estimated_down_pct: 1, estimated_down_pct_kimv: 1,
  estimated_equity_eur: 1, bank_score_confidence: 1,
  ubahn_walk_minutes: 1, is_genossenschaft: 1,
};

export const TOP_PROJECTION = {
  ...MAP_PROJECTION,
  processed_at: 1, price_history: 1, address: 1, url_is_valid: 1,
  minio_image_path: 1,
};

export type ListingMode = 'purchase' | 'coop';

export function buildListingSort(
  profile: string,
  sort: SortOption,
  mode: ListingMode = 'purchase',
): Record<string, 1 | -1> {
  const options: Record<SortOption, Record<string, 1 | -1>> = {
    score_desc: profile === DEFAULT_PROFILE
      ? { score: -1, processed_at: -1 }
      : { [`scores.${profile}`]: -1, processed_at: -1 },
    price_asc: { price_total: 1 },
    price_desc: { price_total: -1 },
    date_desc: { processed_at: -1 },
    area_desc: { area_m2: -1 },
  };
  return mode === 'coop' && sort === 'score_desc'
    ? options.date_desc
    : options[sort] ?? options.score_desc;
}
```

The implementation must copy the current route filter predicates exactly, including purchase price-per-square-meter gates, co-op query, taken-listing handling, and district filtering. `buildListingSort` must preserve profile score sorting and co-op newest-first behavior.

Add presenters that call the existing `resolveCoordinates`, price-estimation, and score-selection logic. Pass `pricePerSqm` and district averages into the presenter rather than reading config or Mongo inside it. Keep `MapListing` and `ListingBase` response types distinct.

- [ ] **Step 4: Run shared data tests**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/listing-data.test.ts lib/geo.test.ts lib/validators.test.ts
npx tsc --noEmit
```

Expected: all pure contract tests pass and no type errors are introduced.

### Task 7: Migrate Listing Routes to Shared Data and Bounded Work

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts`
- Modify: `dashboard/app/api/listings/top/route.ts`
- Modify: `dashboard/app/api/listings/[id]/route.ts`
- Modify: `dashboard/app/api/insights/route.ts`
- Modify: `dashboard/app/api/geo/infrastructure/route.ts`
- Modify: `dashboard/app/api/district-heatmap/route.ts`
- Test: `dashboard/lib/listing-data.test.ts`, `dashboard/lib/validators.test.ts`

- [ ] **Step 1: Replace duplicate map/top query construction**

For each route, keep the existing `NextRequest` parsing and status handling, then call the shared module:

```ts
const listings = await db
  .collection<ListingDocument>('listings')
  .find(filter, { projection: MAP_PROJECTION })
  .sort(sortBy)
  .limit(limit)
  .toArray();
```

Use `TOP_PROJECTION` in the top route. Keep `min_score` filtering after presentation until a parity test proves an earlier Mongo predicate is equivalent.

- [ ] **Step 2: Make district statistics bounded and non-blocking**

Do not call `find(...).toArray()` for insights' secondary counts. Use a Mongo aggregation that computes district average prices and the below-average/transit counts server-side, then return one summary document. Use `$setWindowFields` partitioned by `bezirk` so each document can compare its price with its district average without transferring every listing to Node:

```ts
{
  $setWindowFields: {
    partitionBy: '$bezirk',
    sortBy: { _id: 1 },
    output: {
      district_avg_price: { $avg: '$price_total', window: { documents: ['unbounded', 'unbounded'] } },
    },
  },
}
```

Follow with a `$group` that counts `price_total <= district_avg_price * 0.9` and `ubahn_walk_minutes <= 5`. Retain the current top-level aggregate fields and response names. If the local Mongo version lacks `$setWindowFields`, use a projected async Mongo cursor for the secondary counts so Node holds one document at a time; do not add a limit that would change counts, and record the compatibility fallback in verification.

- [ ] **Step 3: Shape public detail responses**

Replace the detail route's `Object.entries(listing)` copy of every field with an explicit allowlist containing fields consumed by `ListingDetailType`. Preserve ObjectId string conversion and profile score override. Add a pure assertion in `listing-data.test.ts` that an unlisted field is absent from the public result.

- [ ] **Step 4: Add safe cache headers**

Use short public cache headers on public, non-user-specific JSON responses:

```ts
const CACHE = 'public, max-age=15, s-maxage=15, stale-while-revalidate=60';
return NextResponse.json({ listings: finalResult, total: finalResult.length }, {
  headers: { 'Cache-Control': CACHE },
});
```

Use a longer window for static infrastructure and daily heatmap data. In the infrastructure route, return:

```ts
return NextResponse.json({ type: 'FeatureCollection', features }, {
  headers: { 'Cache-Control': 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=86400' },
});
```

In the heatmap route, use the same headers with `{ districts }` as the JSON body.

Do not add this header to mutation routes or the SSE stream; explicitly retain `Cache-Control: no-cache, no-transform` there.

- [ ] **Step 5: Validate route contracts**

Run:

```bash
cd dashboard
npx tsc --noEmit
npx playwright test tests/map-filter-render.spec.ts tests/profile-sort.spec.ts --reporter=dot
```

Expected: coordinate fallback, score-less minimum-score behavior, profile selection, and list/map rendering remain green.

- [ ] **Step 6: Inspect query plans before optional indexes**

Use read-only Mongo `explain('executionStats')` against the deployed schema for the top/map and insights filters. Add only non-destructive indexes if they measurably reduce examined documents without making writes unacceptable. If no index meets that condition, make no index change.

- [ ] **Step 7: Commit Milestone 2**

Run:

```bash
git add dashboard/lib/geo.ts dashboard/lib/geo.test.ts dashboard/lib/listing-data.ts dashboard/lib/listing-data.test.ts dashboard/lib/validators.ts dashboard/lib/validators.test.ts dashboard/app/api/listings/map/route.ts dashboard/app/api/listings/top/route.ts dashboard/app/api/listings/[id]/route.ts dashboard/app/api/insights/route.ts dashboard/app/api/geo/infrastructure/route.ts dashboard/app/api/district-heatmap/route.ts dashboard/app/dashboard/page.tsx dashboard/app/dashboard/map/page.tsx dashboard/components/CommuteBadge.tsx
git commit -m "perf: share dashboard listing data path"
```

## Milestone 3: Client Hot-Path Rendering

### Task 8: Add Deterministic Dashboard Performance Coverage

**Files:**
- Create: `dashboard/tests/dashboard-performance.spec.ts`

- [ ] **Step 1: Mock public data routes before navigation**

Use `page.route` to return a small listing fixture for `/api/listings/top`, `/api/listings/map`, `/api/geo/infrastructure`, `/api/insights`, and `/api/listings/stream`. The fixture must include one exact-coordinate and one district-fallback listing. This keeps performance tests independent of local Mongo data.

- [ ] **Step 2: Assert one map and one request per transition**

Add tests with the existing Playwright API:

```ts
test('desktop mounts one Leaflet map and preserves data during refresh', async ({ page }) => {
  const listingRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/listings/map')) listingRequests.push(request.url());
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');
  await expect(page.locator('.leaflet-container')).toHaveCount(1);
  expect(listingRequests).toHaveLength(1);
});

test('mobile mounts one Leaflet map', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto('/dashboard/map');
  await expect(page.locator('.leaflet-container')).toHaveCount(1);
});
```

Add a deferred-response case proving that a superseded request cannot overwrite the latest response. Use a request counter and resolve the second response first.

- [ ] **Step 3: Record deterministic performance fields**

Capture these values from the browser and response handlers: listing response bytes, listing request count, `domContentLoaded`, first visible map/list selector time, `.leaflet-container` count, and marker count. Write only local before/after values to `scratchpad/`.

- [ ] **Step 4: Run the focused browser spec**

Run:

```bash
cd dashboard
npx playwright test tests/dashboard-performance.spec.ts --reporter=dot
```

Expected: mocked tests pass without requiring MongoDB, and each viewport has exactly one mounted Leaflet container.

### Task 9: Fix Fetch Races and Redundant Client Work

**Files:**
- Modify: `dashboard/app/dashboard/page.tsx`
- Modify: `dashboard/app/dashboard/map/page.tsx`

- [ ] **Step 1: Make listing fetches abortable**

Keep the current `fetchListings` callback shape but accept an optional signal:

Keep each page's existing `URLSearchParams` construction. Immediately before the request, dashboard uses `const url = \`/api/listings/top?${params.toString()}\`;` and map uses the same expression with `/api/listings/map`.

```ts
const fetchListings = useCallback(async (signal?: AbortSignal) => {
  setLoading(true);
  try {
    const response = await fetch(url, { signal });
    if (!response.ok) throw new Error(`Listings request failed: ${response.status}`);
    const data = await response.json();
    if (signal?.aborted) return;
    const items = data.listings ?? [];
    setListings(items);
    const scoreMap: Record<string, Record<string, number | null>> = {};
    for (const item of items) {
      scoreMap[item._id] = item.scores ?? { [profile]: item.score ?? null };
    }
    setScoresById(scoreMap);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return;
    setError('Listings unavailable');
  } finally {
    if (!signal?.aborted) setLoading(false);
  }
}, [minScore, district, sortBy, profile, maxPrice, maxEquity, belowAvgPct]);

useEffect(() => {
  const controller = new AbortController();
  void fetchListings(controller.signal);
  return () => controller.abort();
}, [fetchListings]);
```

For `dashboard/app/dashboard/map/page.tsx`, retain its existing additional dependencies: `equity`, `rate`, `showUnfinanceable`, and `genossenschaft`.

Use the existing page-specific error state or add a small local string state. Do not clear current listings before a replacement response arrives.

- [ ] **Step 2: Preserve visible content during refresh**

Change the render condition from `loading ? full-page loading : data` to `data + non-blocking loading indicator` when listings already exist. Keep the empty-state loading shell only for the initial request.

- [ ] **Step 3: Remove redundant profile re-sort effects**

The API already sorts by the requested profile and returns profile scores. Remove the `useEffect` that copies and re-sorts the entire listing array after every profile response. Keep the profile dependency in the request callback for correctness of the server result set.

- [ ] **Step 4: Run client regression tests**

Run:

```bash
cd dashboard
npm test -- --runInBand lib/validators.test.ts lib/geo.test.ts
npx playwright test tests/dashboard-performance.spec.ts tests/profile-sort.spec.ts tests/map-interaction.spec.ts --reporter=dot
```

Expected: latest response wins, prior data remains visible during refresh, and profile/filter behavior remains unchanged.

### Task 10: Mount One Map and Reduce Marker/Image Work

**Files:**
- Modify: `dashboard/app/dashboard/map/page.tsx`
- Modify: `dashboard/components/MapView.tsx`
- Modify: `dashboard/components/ListingCard.tsx`
- Modify: `dashboard/components/SlimListingCard.tsx`
- Modify: `dashboard/components/ListingDetail.tsx`

- [ ] **Step 1: Stop importing the dynamic map eagerly**

Change the page import to type-only:

```ts
import type {
  ViewportBounds,
  LayerState,
  StationFeature,
  SchoolFeature,
} from '@/components/MapView';
```

Keep `MapViewDynamic` as the only runtime import of the Leaflet module.

- [ ] **Step 2: Render one viewport branch after hydration**

Track `isDesktop: boolean | null` using `window.matchMedia('(min-width: 768px)')` in an effect. Render the existing desktop branch only when true, the existing mobile branch only when false, and the current neutral loading shell while null. Register a `change` listener and remove it on cleanup.

- [ ] **Step 3: Make marker cleanup linear**

Replace the per-marker `listings.find` check in `MarkerLayer` with one ID set per effect:

```ts
const listingIds = new Set(listings.map((listing) => listing._id));
const toRemove: string[] = [];
markerInstances.current.forEach((_, id) => {
  if (!listingIds.has(id)) toRemove.push(id);
});
```

Keep existing icon selection, click handlers, selection animation, and layer cleanup unchanged.

- [ ] **Step 4: Defer non-primary image work**

Add native loading hints to listing images:

```tsx
<img
  src={listing.image_url!}
  alt={listing.title || 'Property image'}
  loading="lazy"
  decoding="async"
  className="w-full h-full object-cover"
  onError={() => setImageError(true)}
/>
```

Apply the same hints to `SlimListingCard` and comparable listing thumbnails. Do not replace the established raw image strategy with a new image dependency.

In `ListingDetail.tsx`, apply lazy loading only to comparable-listing thumbnails. Keep the primary detail image eager so opening a selected listing does not wait for a lazy threshold.

- [ ] **Step 5: Run map and health regressions**

Run:

```bash
cd dashboard
npx playwright test tests/dashboard-performance.spec.ts tests/map-filter-render.spec.ts tests/map-bounds-clobber.spec.ts tests/pin-click.spec.ts tests/page-health.spec.ts --reporter=dot
```

Expected: one map per viewport, no map-container initialization error, pins and rail cards remain visible, and page health reports no new console or request failures.

- [ ] **Step 6: Commit Milestone 3**

Run:

```bash
git add dashboard/app/dashboard/page.tsx dashboard/app/dashboard/map/page.tsx dashboard/components/MapView.tsx dashboard/components/ListingCard.tsx dashboard/components/SlimListingCard.tsx dashboard/components/ListingDetail.tsx dashboard/tests/dashboard-performance.spec.ts
git commit -m "perf: reduce dashboard map rendering work"
```

## Milestone 4: Proven-Dead Cleanup and Final Gates

### Task 11: Remove Parked Dashboard Code

**Files:**
- Delete: `dashboard/components/ThemeProvider.tsx`
- Delete: `dashboard/components/ThemeToggle.tsx`
- Delete: `dashboard/components/ListingSidebar.tsx`
- Modify: `dashboard/package.json`
- Modify: `dashboard/package-lock.json`
- Modify: `dashboard/knip.jsonc`
- Modify: `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Prove no runtime or test references**

Run:

```bash
git grep -n -E 'ThemeProvider|ThemeToggle|ListingSidebar|next-themes' -- dashboard
```

Expected before deletion: only the three parked files, `package.json`, lockfile, and Knip comments/config appear. Any route, component, or test import blocks deletion and must be investigated rather than removed.

- [ ] **Step 2: Remove the parked files and dependency**

Delete the three files. Remove `next-themes` from `dependencies`, remove its lockfile entries through `npm install --package-lock-only`, and remove obsolete Knip ignore entries/comments.

- [ ] **Step 3: Remove confirmed unused code**

In `dashboard/app/dashboard/page.tsx`, remove unused `useRouter`, `usePathname`, `isValidProfile`, and `SortOption` imports. Remove the unused `taxAmount` local. Keep all rendered filter props and callbacks.

- [ ] **Step 4: Prove cleanup with static tooling**

Run:

```bash
cd dashboard
npx --yes knip@5 --config knip.jsonc
npx tsc --noEmit
npm run build
```

Expected: no references to deleted files, no TypeScript errors, and a successful production build.

- [ ] **Step 5: Commit Milestone 4**

Run:

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/knip.jsonc dashboard/app/dashboard/page.tsx
git rm dashboard/components/ThemeProvider.tsx dashboard/components/ThemeToggle.tsx dashboard/components/ListingSidebar.tsx
git commit -m "chore: remove dead dashboard components"
```

## Final Verification

### Task 12: Run Full Gates and Compare Measurements

**Files:**
- Modify: none unless a test exposes a regression.
- Inspect: all milestone diffs and scratchpad measurements.

- [ ] **Step 1: Run npm security gates**

Run:

```bash
cd dashboard
npm audit --json
npm audit --omit=dev --json
npm ls --depth=0
```

Expected: zero high/critical npm findings; only approved current-major packages remain.

With the production server running, verify the browser security headers:

```bash
curl -fsSI http://localhost:3010/ | grep -E 'X-Content-Type-Options|Referrer-Policy|X-Frame-Options|Permissions-Policy'
```

Expected: all four headers appear with the values defined in `next.config.js`.

- [ ] **Step 2: Run Python audit and record exception**

From the repository root, run:

```bash
python -m pip_audit -r Project/requirements.txt --format json
```

Expected: `diskcache 5.6.3` is the only known finding, with no fixed release. Record its pickle/write-access precondition and do not claim a completely clean Python audit.

- [ ] **Step 3: Run dashboard static and unit gates**

Run:

```bash
cd dashboard
npx tsc --noEmit
npm run lint
npm test -- --runInBand
npm run build
git diff --check
```

Expected: all commands pass. If `next lint` is unsupported by the installed Next version, use the repository's configured ESLint command and record the substitution rather than skipping lint.

- [ ] **Step 4: Run full UI gate**

Start the production-style Playwright server through the existing config and run:

```bash
cd dashboard
npx playwright test --reporter=line
```

Expected: zero failures and no console errors on `/`, `/dashboard`, or `/dashboard/map`. Stop the production server after the run with:

```bash
pkill -f "next start"
```

Do not commit screenshots unless a visual failure cannot be diagnosed through DOM assertions.

- [ ] **Step 5: Compare performance measurements**

Compare baseline and final scratchpad values for:

- map/top response bytes;
- listing request count per initial load and filter transition;
- first visible list/map selector time;
- mounted Leaflet container count;
- marker update timing;
- browser image request count before scrolling.

Acceptance requires no regression in behavior and a measured reduction in at least one primary hot-path cost without increasing the others materially.

- [ ] **Step 6: Run Python regression suite**

From the repository root, run the documented command:

```bash
cd Tests
python run_tests.py
```

Expected: no new failures attributable to this dashboard-only change. Existing unrelated failures must be recorded with their test names and baseline status.

- [ ] **Step 7: Refresh the graph**

From the repository root, run:

```bash
graphify update .
```

Then query the affected concepts:

```bash
graphify query "What files implement the shared dashboard listing data path and map rendering?"
```

Expected: `listing-data.ts`, API routes, dashboard pages, and `MapView.tsx` appear in the updated graph.

- [ ] **Step 8: Review final diff and status**

Run:

```bash
git status --short --branch
git diff main...HEAD --stat
git log --oneline -10
```

Then scan the final diff for accidental credentials:

```bash
if git diff main...HEAD -- . ':!dashboard/package-lock.json' | grep -Ei '(api[_-]?key|password|secret|token|mongodb\+srv)'; then
  exit 1
fi
```

Confirm only intended files changed, no secrets or environment files are staged, all milestone commits are present, and the original dirty worktree remains untouched.
