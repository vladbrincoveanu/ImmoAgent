# Dashboard Security, Dependency, and Performance Maintenance

**Date:** 2026-08-19
**Status:** Design approved in conversation; written-spec review follows commit.
**Scope:** Public Next.js dashboard, its API data path, safe dependency refresh, and proven-dead cleanup.

## Summary

Deliver one bounded maintenance tranche without changing the dashboard's product behavior or performing a framework migration.

The tranche has four layers:

1. Patch current-major dependencies and close fixable npm audit findings.
2. Harden public API inputs, abuse handling, response shape, and security headers.
3. Reduce dashboard database, network, and Leaflet rendering work.
4. Consolidate repeated code and remove only unreachable dashboard files and dependencies.

The dashboard is treated as public internet software. No authentication redesign, payment work, or distributed rate-limit service is included.

## Goals

- Remove fixable high-severity npm findings without major-version migration.
- Run a complete Python dependency audit and explicitly disposition the unresolved `diskcache` finding.
- Preserve listing filters, profile scoring, co-op behavior, URL validation, response shapes, and mobile/desktop behavior.
- Reduce listing API payload and database materialization.
- Prevent stale filter requests and duplicate hidden Leaflet mounts.
- Reduce marker update complexity and unnecessary image work.
- Remove only cleanup candidates proven unreachable by import, route, test, and build checks.
- Verify changes with dependency, type, unit, build, and targeted browser gates.

## Non-Goals

- No Next.js 16, React 19, MongoDB 7, React-Leaflet 5, Tailwind 4, or TypeScript 7 migration.
- No new authentication model.
- No external Redis or paid service for rate limiting.
- No MongoDB data migration or destructive index operation.
- No deletion of historical specifications, uncertain Python modules, or externally addressable routes.

## Current Findings

- `npm audit --omit=dev` reports high `nanoid` below `3.3.18`.
- Full `npm audit` also reports high `js-yaml` below `3.15.1`.
- `npm audit fix --dry-run` reports only `nanoid 3.3.16 -> 3.3.18` and `js-yaml 3.15.0 -> 3.15.1`.
- `pip-audit -r Project/requirements.txt` reports `diskcache 5.6.3` (`CVE-2025-69872` / `PYSEC-2026-2447`) with no fixed release.
- `diskcache` is transitive through `outlines`; `outlines` is referenced by analyzer code and tests, so it is not deleted in this tranche.
- `StructuredAnalyzer` currently delegates normal runtime work to `LightweightAnalyzer`; this does not justify removing the retained optional analyzer code without a separate decision.
- `/api/listings/top` and `/api/listings/map` duplicate query and response-mapping logic.
- Listing routes load more Mongo fields than their card/map responses require.
- Insights materializes an unbounded projected listing result for secondary counts.
- The map page renders desktop and mobile map branches simultaneously, even when one is hidden by CSS.
- Leaflet marker cleanup repeatedly scans the listing array.
- Listing image elements do not consistently opt into lazy decoding/loading.
- Parked `next-themes`, theme components, and `ListingSidebar` are documented as unreferenced by Knip configuration.

## Architecture

### Shared Listing Data Module

Add one route-only module, `dashboard/lib/listing-data.ts`, with small pure and database-facing functions:

- Build validated purchase/co-op filters and sort specifications.
- Define projections for map and card payloads.
- Load district averages without materializing unrelated listing documents.
- Map Mongo documents to the existing `MapListing` and `ListingBase` response shapes.

Routes retain control of HTTP parsing and status codes. The module does not import Next.js request/response types and is not imported by client components.

### Shared Geo Math

Add a dependency-free `dashboard/lib/geo.ts` for Haversine distance and walking-minute calculation. Use it from dashboard pages and commute UI where calculations are currently duplicated. Keep API-specific transit calculations unchanged unless tests prove equivalence.

### Public API Guard

Add a small in-process sliding-window limiter and middleware matcher for expensive public read routes. The limiter uses the platform request IP when available, otherwise the first trusted `x-forwarded-for` address, returns `429`, `Retry-After`, and rate headers, and has bounded cleanup for expired entries.

This is per-process defense in depth. It is not presented as a distributed limit for multiple Vercel instances.

### Client Map Ownership

The map page determines viewport mode after hydration and mounts one Leaflet instance. Before mode resolution it renders a neutral loading shell. Existing desktop rail and mobile bottom-sheet layouts remain unchanged after selection.

## Data Flow

1. Client builds the same validated query parameters used today.
2. API route parses and validates input before database access.
3. Shared listing module builds the filter, sort, and narrow projection.
4. Listing query and district-average work run concurrently when their inputs allow it; otherwise the second query uses only the districts returned by the first.
5. Presenter computes existing coordinate fallback, estimated price, profile score, and zone percentage fields.
6. Route returns the existing JSON envelope with short public cache headers.
7. Client keeps current results visible while a new request is pending, aborts superseded requests, and applies only the latest successful response.
8. Map receives only viewport-filtered listings and updates markers using an ID set for O(n) removal checks.

The existing post-mapping `min_score` behavior remains until an equivalence test proves that moving it into Mongo produces the same result set and ordering.

## Security and Dependency Changes

### Dependency Policy

- Refresh safe patch/minor versions within existing major ranges.
- Update the existing `js-yaml` override to at least `3.15.1`.
- Add an override for `nanoid` at least `3.3.18`.
- Regenerate `dashboard/package-lock.json` from the manifest; never use `npm audit fix --force`.
- Leave major candidates for a separate migration.
- Do not remove `outlines`, `transformers`, or analyzer code solely to hide the Python audit result.
- Record the `diskcache` finding, exploit precondition, absent fix, and follow-up decision in the verification report.

### Input and Abuse Controls

- Numeric validators reject partial parses, `NaN`, infinity, empty values, and out-of-range values instead of accepting prefixes such as `10abc`.
- District, sort, profile, status, limit, and ObjectId inputs remain allowlisted and capped.
- Expensive public read routes receive the limiter; streaming remains uncached and has one client connection with existing backoff behavior.
- Error responses remain generic for database and internal failures.
- Invalid-input logs contain truncated, non-sensitive values only.

### Response and Browser Controls

- Map/top/detail response fields remain explicitly shaped; full Mongo documents are not serialized for list views.
- Existing allowlisted image hosts remain the only remote image sources.
- Add low-risk headers: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, and a restrictive `Permissions-Policy`.
- Add short cache headers only to public, non-user-specific listing, insight, infrastructure, and heatmap responses. Never cache mutation or SSE responses.

## Performance Changes

### Server

- Replace duplicate top/map query construction and mapping with `listing-data.ts`.
- Add Mongo projections for map and card fields.
- Replace insights' unbounded `find(...).toArray()` secondary pass with bounded aggregation.
- Run independent district statistics concurrently where safe.
- Inspect query plans before adding indexes. Add only non-destructive indexes with measured benefit; otherwise leave the schema unchanged.

### Client

- Add `AbortController` to dashboard and map listing fetches.
- Check `response.ok` before parsing and keep previous data during refetch.
- Remove redundant local profile sorting when the API has already returned profile-sorted results.
- Mount one map per viewport rather than two hidden maps.
- Replace repeated marker `find` calls with a `Set` of listing IDs.
- Add `loading="lazy"` and `decoding="async"` to non-primary listing images with stable dimensions.
- Do not add list virtualization until measurements show the current capped list needs it.
- Cache deterministic infrastructure and heatmap responses for their safe freshness window.

## Cleanup

Delete only after import, route, test, Knip, TypeScript, and production-build checks:

- `dashboard/components/ThemeProvider.tsx`
- `dashboard/components/ThemeToggle.tsx`
- `dashboard/components/ListingSidebar.tsx`
- `next-themes` from `dashboard/package.json` and its lockfile entries

Also remove unused imports and dead locals, including the direct `MapView` value import that bypasses dynamic loading and the unused dashboard `taxAmount` calculation.

Keep the full-page listing detail route because direct URLs can reach it even without internal links. Keep historical docs and Python analyzer/AI files because they are referenced by runtime code or tests.

## Error Handling

- `400` for invalid request parameters with a stable `{ error, field }` shape where a field is known.
- `429` for rate-limit rejection with retry metadata.
- `503` when MongoDB is unavailable.
- `500` with generic body and server-side diagnostic logging for unexpected failures.
- Aborted client requests are silent; non-abort failures preserve prior data and expose a recoverable UI state.
- Cache windows are short enough that new listings and availability changes do not remain hidden for a meaningful period.

## Verification

Run from the isolated worktree:

1. `npm audit --json` and `npm audit --omit=dev --json`; expected: zero high/critical npm findings.
2. `python -m pip_audit -r Project/requirements.txt`; expected: known `diskcache` exception only, with no unreviewed finding.
3. `npm ls --depth=0`, TypeScript no-emit, lint, Jest, and production build.
4. Knip and `git diff --check`.
5. Existing Python suite from `Tests/run_tests.py`.
6. Targeted Playwright tests for map/list filters, stale request handling, one map mount, marker selection, image loading, and mobile/desktop rendering.
7. Before/after measurements for response bytes, request count, first usable map/list render, filter-to-render latency, Leaflet instance count, and marker update time.
8. `graphify update .` after source changes.

Acceptance requires behavior parity, no new security finding, zero fixable npm high/critical findings, explicit Python audit disposition, and measurable improvement on the dashboard hot path.

## Rollback

Changes land in independently reviewable milestones:

1. Dependency/security fixes.
2. Shared query/presenter and API hardening.
3. Client render and fetch improvements.
4. Proven-dead cleanup.

If a milestone fails its build, targeted tests, or behavior checks, revert only that milestone. Keep unrelated worktree changes untouched. No database rollback is required because no destructive migration is part of this design.
