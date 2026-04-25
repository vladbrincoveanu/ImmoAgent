# API Security Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add rate limiting and input validation to dashboard API routes to protect the MongoDB backend from abuse and bad input.

**Architecture:** Edge Middleware (`middleware.ts`) intercepts `/api/listings/*` requests and applies an in-memory sliding-window rate limiter (30 req/min per IP). Validators module (`lib/validators.ts`) sanitizes all query params before they reach MongoDB. Config path fix replaces broken `@/../../config.json` require with `path.resolve`.

**Tech Stack:** Next.js 14 Edge Middleware, TypeScript, Node.js `path`

---

## File Map

```
dashboard/
  middleware.ts                   # Create — Edge Middleware rate limiting
  lib/
    rate-limiter.ts              # Create — sliding window rate limiter
    validators.ts                # Create — district/sort/minScore/limit validators
  app/api/listings/
    map/route.ts                # Modify — use validators, fix config path
    top/route.ts                # Modify — use validators, fix config path
    [id]/route.ts               # Modify — use validators (id param validation)
```

---

## Task 1: Create rate-limiter utility

**Files:**
- Create: `dashboard/lib/rate-limiter.ts`

- [ ] **Step 1: Write the rate limiter**

Create `dashboard/lib/rate-limiter.ts`:

```typescript
/**
 * Sliding window rate limiter using an in-memory Map.
 * NOTE: State resets on Edge function cold starts. For production,
 * replace with Upstash Redis for durable state.
 */

interface RateLimitEntry {
  count: number;
  windowStart: number;
}

const entries = new Map<string, RateLimitEntry>();

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
}

export function checkRateLimit(
  ip: string,
  limit: number,
  windowMs: number
): RateLimitResult {
  const now = Date.now();
  const entry = entries.get(ip);

  if (!entry || now - entry.windowStart > windowMs) {
    // New window
    entries.set(ip, { count: 1, windowStart: now });
    return {
      allowed: true,
      remaining: limit - 1,
      resetAt: now + windowMs,
    };
  }

  entry.count++;
  entries.set(ip, entry);

  if (entry.count > limit) {
    return {
      allowed: false,
      remaining: 0,
      resetAt: entry.windowStart + windowMs,
    };
  }

  return {
    allowed: true,
    remaining: limit - entry.count,
    resetAt: entry.windowStart + windowMs,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/lib/rate-limiter.ts
git commit -m "feat(dashboard): add sliding window rate limiter utility"
```

---

## Task 2: Create validators utility

**Files:**
- Create: `dashboard/lib/validators.ts`

- [ ] **Step 1: Write the validators**

Create `dashboard/lib/validators.ts`:

```typescript
export type SortOption = 'score_desc' | 'price_asc' | 'price_desc' | 'date_desc' | 'area_desc';

const VALID_DISTRICTS = new Set([
  '1010', '1020', '1030', '1040', '1050', '1060', '1070', '1080', '1090',
  '1100', '1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180',
  '1190', '1200', '1210', '1220', '1230',
]);

const VALID_SORT_OPTIONS: SortOption[] = ['score_desc', 'price_asc', 'price_desc', 'date_desc', 'area_desc'];

/**
 * Validates a district string. Returns the district if valid, null if invalid or empty.
 */
export function validateDistrict(input: string | null): string | null {
  if (!input || input.trim() === '') return null;
  const trimmed = input.trim();
  return VALID_DISTRICTS.has(trimmed) ? trimmed : null;
}

/**
 * Validates a sort option. Returns the input if valid, 'score_desc' as default.
 */
export function validateSort(input: string | null): SortOption {
  if (!input) return 'score_desc';
  return VALID_SORT_OPTIONS.includes(input as SortOption) ? (input as SortOption) : 'score_desc';
}

/**
 * Validates minScore. Parses as float and clamps to [0, 100].
 */
export function validateMinScore(input: string | null): number {
  if (!input) return 0;
  const parsed = parseFloat(input);
  if (isNaN(parsed)) return 0;
  return Math.max(0, Math.min(100, parsed));
}

/**
 * Validates limit. Parses as int and clamps to [1, max].
 */
export function validateLimit(input: string | null, max: number): number {
  if (!input) return max;
  const parsed = parseInt(input, 10);
  if (isNaN(parsed)) return max;
  return Math.max(1, Math.min(max, parsed));
}

/**
 * Validates a MongoDB ObjectId string. Returns the id if valid, null otherwise.
 */
export function validateObjectId(input: string | null): string | null {
  if (!input) return null;
  // MongoDB ObjectId is a 24-character hex string
  return /^[a-fA-F0-9]{24}$/.test(input) ? input : null;
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/lib/validators.ts
git commit -m "feat(dashboard): add input validators for API route params"
```

---

## Task 3: Create Edge Middleware with rate limiting

**Files:**
- Create: `dashboard/middleware.ts`

- [ ] **Step 1: Write the Edge Middleware**

Create `dashboard/middleware.ts` in the `dashboard/` directory (NOT inside `app/`):

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { checkRateLimit } from '@/lib/rate-limiter';

const RATE_LIMIT = 30;
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 60 seconds
const LISTINGS_PATH_REGEX = /^\/api\/listings\//;

function getClientIp(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return request.ip ?? '127.0.0.1';
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only rate-limit /api/listings/* endpoints
  if (!LISTINGS_PATH_REGEX.test(pathname)) {
    return NextResponse.next();
  }

  const ip = getClientIp(request);
  const result = checkRateLimit(ip, RATE_LIMIT, RATE_LIMIT_WINDOW_MS);

  const response = result.allowed
    ? NextResponse.next()
    : NextResponse.json(
        { error: 'Too many requests. Please try again later.', retryAfter: 60 },
        { status: 429 }
      );

  // Always add rate limit headers
  response.headers.set('X-RateLimit-Limit', String(RATE_LIMIT));
  response.headers.set('X-RateLimit-Remaining', String(result.remaining));
  response.headers.set('X-RateLimit-Reset', String(Math.round(result.resetAt / 1000)));

  if (!result.allowed) {
    response.headers.set('Retry-After', '60');
  }

  return response;
}

export const config = {
  matcher: ['/api/listings/:path*'],
};
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/middleware.ts
git commit -m "feat(dashboard): add Edge Middleware with rate limiting for /api/listings/*"
```

---

## Task 4: Harden map/route.ts — validators + config fix

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts`

- [ ] **Step 1: Read current file and apply changes**

Read `dashboard/app/api/listings/map/route.ts`.

**Change 1 — Add imports at top:**
```typescript
import { validateDistrict, validateSort, validateMinScore, validateLimit } from '@/lib/validators';
import path from 'path';
```

**Change 2 — Replace the broken config require:**
```typescript
// OLD (broken):
const config = require('@/../../config.json');
// NEW:
const config = require(path.resolve(process.cwd(), 'config.json'));
```

**Change 3 — Replace the query param parsing section (the 4 lines after URL destructuring) with validated versions:**

OLD:
```typescript
const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200);
const minScore = parseFloat(searchParams.get('min_score') || '0');
const district = searchParams.get('district');
const sort = searchParams.get('sort') || 'score_desc';
```

NEW:
```typescript
const limit = validateLimit(searchParams.get('limit'), 200);
const minScore = validateMinScore(searchParams.get('min_score'));
const district = validateDistrict(searchParams.get('district'));
const sort = validateSort(searchParams.get('sort'));
```

**Change 4 — Add district validation warning at start of try block:**
After `try {`, add:
```typescript
if (district === null && searchParams.get('district') !== null) {
  console.warn('[/api/listings/map] Invalid district rejected:', searchParams.get('district'));
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit 2>&1 | grep -v "MapView.test.tsx"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts
git commit -m "fix(dashboard): apply validators and fix config path in map route"
```

---

## Task 5: Harden top/route.ts — validators + config fix

**Files:**
- Modify: `dashboard/app/api/listings/top/route.ts`

- [ ] **Step 1: Read current file and apply changes**

Read `dashboard/app/api/listings/top/route.ts`.

**Change 1 — Add imports at top:**
```typescript
import { validateDistrict, validateSort, validateMinScore } from '@/lib/validators';
import path from 'path';
```

**Change 2 — Replace the broken config require:**
```typescript
// OLD:
const config = require('@/../../config.json');
// NEW:
const config = require(path.resolve(process.cwd(), 'config.json'));
```

**Change 3 — Replace query param parsing:**
OLD:
```typescript
const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100);
const minScore = parseFloat(searchParams.get('min_score') || '0');
const district = searchParams.get('district');
const sort = searchParams.get('sort') || 'score_desc';
```

NEW:
```typescript
const limit = Math.min(validateLimit(searchParams.get('limit'), 100), 100);
const minScore = validateMinScore(searchParams.get('min_score'));
const district = validateDistrict(searchParams.get('district'));
const sort = validateSort(searchParams.get('sort'));
```

**Change 4 — Add district validation warning:**
After `try {`, add:
```typescript
if (district === null && searchParams.get('district') !== null) {
  console.warn('[/api/listings/top] Invalid district rejected:', searchParams.get('district'));
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit 2>&1 | grep -v "MapView.test.tsx"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/api/listings/top/route.ts
git commit -m "fix(dashboard): apply validators and fix config path in top route"
```

---

## Task 6: Harden [id]/route.ts — ObjectId validation

**Files:**
- Modify: `dashboard/app/api/listings/[id]/route.ts`

- [ ] **Step 1: Read current file and apply changes**

Read `dashboard/app/api/listings/[id]/route.ts`.

**Change 1 — Add import at top:**
```typescript
import { validateObjectId } from '@/lib/validators';
```

**Change 2 — Add validation at start of GET handler (before the MongoDB query):**

OLD:
```typescript
export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const listing = await getDb().collection('listings').findOne({
      _id: new ObjectId(params.id),
    });
```

NEW:
```typescript
export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const validId = validateObjectId(params.id);
  if (!validId) {
    return NextResponse.json({ error: 'Invalid listing ID', field: 'id' }, { status: 400 });
  }

  try {
    const listing = await getDb().collection('listings').findOne({
      _id: new ObjectId(validId),
    });
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npx tsc --noEmit 2>&1 | grep -v "MapView.test.tsx"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/api/listings/[id]/route.ts
git commit -m "fix(dashboard): add ObjectId validation to listing detail route"
```

---

## Task 7: Smoke test the API

**Files:**
- None (verification only)

- [ ] **Step 1: Start dev server**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard
npm run dev > /tmp/dev-api-test.log 2>&1 &
sleep 8
```

- [ ] **Step 2: Test valid request**

```bash
curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/api/listings/map?limit=5"
```

Expected: `200`

- [ ] **Step 3: Test invalid district (should return 200 but log warning — null district is silently ignored)**

```bash
curl -s "http://localhost:3000/api/listings/map?district=9999" | head -c 200
```

Expected: `200` with listings (invalid district silently ignored, no filter applied)

- [ ] **Step 4: Test invalid ObjectId (should return 400)**

```bash
curl -s -w "\n%{http_code}" "http://localhost:3000/api/listings/invalid-id"
```

Expected: `{"error":"Invalid listing ID","field":"id"}` with status `400`

- [ ] **Step 5: Test rate limit headers present**

```bash
curl -sI "http://localhost:3000/api/listings/map?limit=1" | grep -i "x-ratelimit"
```

Expected: `X-RateLimit-Limit: 30`, `X-RateLimit-Remaining:`, `X-RateLimit-Reset:` headers present

- [ ] **Step 6: Kill dev server**

```bash
kill %1 2>/dev/null; wait 2>/dev/null
```

- [ ] **Step 7: Commit only if files were touched** (this is verification-only — no commit)

---

## Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Rate limiter (30 req/min per IP) | Task 1 (rate-limiter.ts), Task 3 (middleware.ts) |
| X-RateLimit-* response headers | Task 3 (middleware.ts) |
| 429 with Retry-After | Task 3 (middleware.ts) |
| validateDistrict (strict Vienna districts) | Task 2 (validators.ts) |
| validateSort (whitelist) | Task 2 (validators.ts) |
| validateMinScore (clamp 0-100) | Task 2 (validators.ts) |
| validateLimit (clamp 1-max) | Task 2 (validators.ts) |
| validateObjectId | Task 2 (validators.ts), Task 6 ([id]/route.ts) |
| Config path fix | Task 4 (map/route.ts), Task 5 (top/route.ts) |
| District validation warning log | Task 4, Task 5 |

---

## Type Consistency Check

| Type/Function | Defined in | Used in |
|--------------|-----------|---------|
| `checkRateLimit(ip, limit, windowMs)` | `rate-limiter.ts` | `middleware.ts` |
| `validateDistrict(input)` | `validators.ts` | `map/route.ts`, `top/route.ts` |
| `validateSort(input)` | `validators.ts` | `map/route.ts`, `top/route.ts` |
| `validateMinScore(input)` | `validators.ts` | `map/route.ts`, `top/route.ts` |
| `validateLimit(input, max)` | `validators.ts` | `map/route.ts`, `top/route.ts` |
| `validateObjectId(input)` | `validators.ts` | `[id]/route.ts` |
| `RATE_LIMIT = 30` | `middleware.ts` | consistent throughout |
| `RATE_LIMIT_WINDOW_MS = 60000` | `middleware.ts` | consistent throughout |
