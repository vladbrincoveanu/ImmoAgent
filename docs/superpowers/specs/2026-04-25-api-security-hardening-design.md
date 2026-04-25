# API Security Hardening — Design Spec

**Date:** 2026-04-25
**Phase:** 2 of 5 — API Security Hardening
**Scope:** Rate limiting and input validation on the immo-scouter dashboard API routes

---

## Overview

The dashboard API routes (`/api/listings/*`) are currently publicly accessible with no abuse prevention or input sanitization. This spec adds rate limiting via Next.js Edge Middleware and strict input validation to protect the MongoDB backend.

---

## Architecture

### Rate Limiting — Edge Middleware

**File:** `dashboard/middleware.ts` (new)

Deploys as Edge Middleware at the edge — before requests hit API routes. Uses an in-memory `Map` with sliding window per IP for the prototype (30 req/min per IP). Returns `429 Too Many Requests` with `Retry-After: 60` header when exceeded.

**Note:** In-memory rate limiting resets on Edge function cold starts (Vercel reuses instances). For production, consider upgrading to Upstash Redis. The interface is designed to make this swap trivial.

### Input Validation — Per-Route

Each API route validates and sanitizes its query parameters before passing to MongoDB. Invalid input returns `400 Bad Request` with a descriptive message.

---

## Module: RateLimiter

**File:** `dashboard/lib/rate-limiter.ts` (new)

- **Responsibility:** Sliding window rate limiter keyed by IP address
- **Interface:** `checkLimit(ip: string, limit: number, windowMs: number): { allowed: boolean; remaining: number; resetAt: number }`
- **Dependencies:** None (in-memory Map for prototype)
- **Size target:** ~60 lines

### Module: Edge Middleware

**File:** `dashboard/middleware.ts` (new)

- **Responsibility:** Intercept requests to `/api/listings/*`, apply rate limit, forward if allowed
- **Interface:** Next.js Edge Middleware exported function (`middleware(request)`)
- **Dependencies:** `RateLimiter`, `NextRequest`, `NextResponse`
- **Size target:** ~40 lines

### Module: Input Validators

**File:** `dashboard/lib/validators.ts` (new)

- **Responsibility:** Validate and sanitize query parameters for listing API routes
- **Interface:**
  - `validateDistrict(input: string | null): string | null` — returns valid district or null (rejects invalid)
  - `validateSort(input: string | null): SortOption` — returns default if invalid
  - `validateMinScore(input: string | null): number` — clamps to 0-100
  - `validateLimit(input: string | null, max: number): number` — clamps to 1-max
- **Dependencies:** None
- **Size target:** ~50 lines

### Module: Listing Routes Hardening

**Files:**
- `dashboard/app/api/listings/map/route.ts` — use validators, fix config path
- `dashboard/app/api/listings/top/route.ts` — use validators, fix config path
- `dashboard/app/api/listings/[id]/route.ts` — use validators

- **Responsibility:** Apply validated params to MongoDB queries, return proper error responses
- **Interface:** No API contract change — same request/response shapes
- **Dependencies:** `validators.ts`
- **Size target:** ~10 lines changed per route

---

## Rate Limiting Design

### Algorithm: Sliding Window Counter

```
entries: Map<ip, { count: number, windowStart: number }>

on request from ip:
  now = Date.now()
  entry = entries.get(ip)

  if entry is missing or now - entry.windowStart > WINDOW_MS:
    entry = { count: 1, windowStart: now }
  else:
    entry.count++

  entries.set(ip, entry)

  if entry.count > LIMIT:
    return 429 { remaining: 0, retryAfter: 60 }
  else:
    return 200 { remaining: LIMIT - entry.count, resetAt: entry.windowStart + WINDOW_MS }
```

**Limits:**
- Listing read endpoints (`/api/listings/*`): 30 requests / 60 seconds per IP
- No limit on static assets or other paths

**Response headers on all `/api/listings/*` responses:**
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: <n>
X-RateLimit-Reset: <unix timestamp>
```

**429 Response:**
```json
{ "error": "Too many requests. Please try again later.", "retryAfter": 60 }
```

---

## Input Validation Design

### District Validation (Strict)

Valid Vienna districts: `1010`, `1020`, `1030`, `1040`, `1050`, `1060`, `1070`, `1080`, `1090`, `1100`, `1110`, `1120`, `1130`, `1140`, `1150`, `1160`, `1170`, `1180`, `1190`, `1200`, `1210`, `1220`, `1230`

Regex: `/^(101[0-9]|10[2-9][0-9]|11[0-2][0-9]|1230)$/`

- Input `null` or `''`: pass through (no district filter)
- Input matches valid district: return as-is
- Input does not match: return `null` (route ignores invalid district, logs warning)

### Sort Validation

Whitelist: `score_desc`, `price_asc`, `price_desc`, `date_desc`, `area_desc`

- Input matches whitelist: return as-is
- Input does not match: return `score_desc` (default)

### Min Score Validation

- Parse as float, clamp to range [0, 100]
- Non-numeric input: return `0`
- NaN: return `0`

### Limit Validation

- Parse as int, clamp to range [1, max]
- `map/route.ts` max: 200
- `top/route.ts` max: 100
- Non-numeric input: return default (50 for map, 20 for top)

---

## Config Path Fix

**Problem:** `require('@/../../config.json')` uses a relative path from the file location, which breaks depending on where the code runs.

**Fix:** Use `path.resolve(process.cwd(), 'config.json')` instead.

```typescript
import path from 'path';
const config = require(path.resolve(process.cwd(), 'config.json'));
```

---

## Error Response Format

All validation errors return:

```json
{ "error": "<description>", "field": "<fieldname>" }
```

HTTP status `400` for validation errors, `429` for rate limit, `500` for server errors.

---

## Edge Cases

1. **Rate limiter memory growth**: The in-memory Map has no TTL cleanup for expired entries. For prototype this is fine (Edge functions are short-lived). For production, add periodic cleanup or switch to Upstash Redis.
2. **Multiple Vercel Edge instances**: In-memory rate limiting is per-instance. A user hitting different edge instances could get 30 × N requests. Acceptable for prototype.
3. **IP detection behind proxy**: Uses `request.headers.get('x-forwarded-for')?.split(',')[0]` or `request.ip`. Works for Vercel deployments.
4. **District validation returns null**: Routes should treat `null` district as "no filter" — same as current behavior when district param is absent.

---

## Out of Scope

- API key authentication (not requested)
- Upstash Redis upgrade
- CORS configuration
- Changes to frontend components
- Changes to Python scraper backend

---

## Spec Coverage

| Requirement | Section |
|-------------|---------|
| Rate limiting (30 req/min per IP) | Rate Limiting Design, Edge Middleware module |
| Input validation — district (strict) | Input Validation Design, Validators module |
| Input validation — sort, minScore, limit | Input Validation Design, Validators module |
| Config path fix | Config Path Fix |
| 429 response with Retry-After | Rate Limiting Design |
| X-RateLimit-* response headers | Rate Limiting Design |
| 400 response for invalid input | Input Validation Design |
