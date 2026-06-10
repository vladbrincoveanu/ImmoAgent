# immo-scouter Repository Audit

**Date:** 2026-06-10
**Auditor:** Principal-level engineering review
**Scope:** Whole repository, no code modifications
**Maturity calibration:** Internal personal tool, single user, ~12K lines Python + ~3.7K lines TypeScript

---

## Executive Summary

**Health grade: C+** — Functional and well-tested personal tool with strong design discipline (20+ specs, recent fix cadence), but carries 2+ years of accumulated dead code, parallel implementations, and at least one Critical security issue (hardcoded test/test123 backdoor in active Flask route).

**Top 3 risks:**
1. **CRITICAL: Hardcoded auth backdoor** in `Project/Api/app.py:138` (`if username == 'test' and password == 'test123'`) — exposed if Flask app ever runs.
2. **HIGH: Two parallel web stacks** (Next.js dashboard in `dashboard/`, Flask app in `Project/Api/`) — Flask is dead but its files ship, including the broken twin `app_broken.py`.
3. **HIGH: Session has no expiration** in `dashboard/lib/auth.ts:13-15` — cookie session is forever.

**Top 3 opportunities:**
1. **Delete dead code** — `app_broken.py` (24.9K), unused `next-auth` dep, dead `Project/Api/` Flask stack, legacy scoring globals alongside contextvars.
2. **Add input validation layer** — `getDb()` returns null in dashboard client but most routes don't check, leading to NPE-style failures.
3. **Consolidate config loader** — `ensure_config_json_on_path()` copy-pasted across 3+ entry points; one canonical `load_config()` exists in helpers but not consistently used.

---

## Repo Map

**Purpose:** Vienna real estate scraping, scoring, financial feasibility, Telegram alerts, web dashboard. Personal single-user tool, used daily by owner for property search + outreach.

**Stack:** Python 3.11 (scraper/scoring/Telegram/Flask API) + Next.js 14 App Router (dashboard) + MongoDB Atlas (data) + Telegram Bot API (alerts) + MinIO (image storage, optional) + GitHub Actions (daily cron).

**Architecture sketch:**
```
[3 Scrapers: willhaben, immo_kurier, derstandard]
    → Application/main.py orchestrator (37.8K)
    → Application/scoring.py + Application/feasibility.py (financial)
    → Application/buyer_profiles.py (10 personas)
    → Integration/mongodb_handler.py (37K — CRUD + history)
    → Integration/telegram_bot.py (alerts)
    ↓
[MongoDB Atlas] ← → [Next.js Dashboard @ dashboard/]
                  ├── Leaflet map (MapView, MapLegend)
                  ├── FilterBar / FilterDrawer / BottomSheet
                  ├── ListingCard / ListingDetail / ListingSidebar
                  └── /api/listings/* routes (4 endpoints)
                  ↓
                  [Flask legacy API @ Project/Api/app.py — DEAD]
                  └── /api/auth/login, /login, /property/<id>, etc.
```

**Key directories (one-line each):**

| Path | Purpose | Notes |
|------|---------|-------|
| `Project/Application/main.py` | Scraping orchestrator | 37.8K — large but linear flow |
| `Project/Application/scraping/` | 3 source-specific scrapers | 228K combined — huge, mostly inline regex/HTML |
| `Project/Application/scoring.py` | Weighted property scoring | Thread-safe via contextvars + legacy global |
| `Project/Application/buyer_profiles.py` | 10 buyer personas with weight sets | 10.6K |
| `Project/Application/feasibility.py` | Austrian bank/financial model | 8.7K — well-tested |
| `Project/Application/cleanup.py` | DB hygiene, taken-listings tracker | 18.2K |
| `Project/Integration/mongodb_handler.py` | All MongoDB CRUD | 37K — large data layer |
| `Project/Integration/telegram_bot.py` | Telegram formatting + sending | 24K |
| `Project/Domain/listing.py` | Listing dataclass (70+ fields) | Single source of truth for listing shape |
| `Project/Api/app.py` | Legacy Flask web app + auth | **DEAD but ships** |
| `Project/Api/app_broken.py` | Half-rewritten Flask twin | **DEAD, dangerous** |
| `dashboard/app/` | Next.js App Router pages + API | Current web UI |
| `dashboard/components/` | 12 React components (map, cards, filters) | Clean separation |
| `dashboard/lib/` | types, mongodb client, auth, validators, rate-limiter, sse | 7 modules |
| `Tests/` | 90+ Python test files | 12K lines — heavy, possibly stale |
| `docs/superpowers/specs/` | 20 design specs | Strong design discipline |
| `docs/superpowers/plans/` | Implementation plans | Mature process |
| `.github/workflows/` | 4 cron workflows | Daily revalidation, migrations, outreach |

**Surprises:**
- `Project/run.py` is a 12-line stub that delegates to `Application.main` via `runpy`.
- `Project/Domain/sources.py` is 7 lines (just defines the Source enum).
- `app_broken.py` exists alongside `app.py` and is self-named as broken.
- `next-auth` is in `package.json` but only `<SessionProvider>` wrapper is used; the actual auth is a custom cookie decoded via base64.
- `Listing` dataclass has 70+ fields; the field count keeps growing (10 new fields proposed in the 5 new specs).

---

## Audit Report

Findings grouped by dimension, sorted by severity within each. **15 high-confidence findings.** Each finding has: (a) what, (b) where, (c) why it matters, (d) severity.

### Security

#### S1. CRITICAL — Hardcoded test/test123 backdoor in live Flask auth
- **Where:** `Project/Api/app.py:138` — `if username == 'test' and password == 'test123':`
- **Why:** Active code path in `authenticate_user()`. If Flask app ever serves a request (current intent unclear; not deployed but ships), anyone with the URL can authenticate as `test`. The `app_broken.py` twin at line 138 likely has the same flaw (file size 24.9K suggests it was a partial rewrite).
- **Severity:** CRITICAL.

#### S2. HIGH — Session has no expiration
- **Where:** `dashboard/lib/auth.ts:13-15` (`validateSession` only checks format, not time)
- **Why:** Cookie format is `base64(user:timestamp)`. The `timestamp` is parsed via `isNaN(Number(...))` which only fails on non-numeric strings. There's no comparison against `Date.now()`. A stolen cookie from 2024 still authenticates in 2026.
- **Severity:** HIGH.

#### S3. HIGH — Hardcoded admin password default in `app_broken.py`
- **Where:** `Project/Api/app_broken.py:110` — `admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')`
- **Why:** The fallback `'admin123'` ships with the file. If env var is unset and this version is ever used, default credentials grant admin. (The active `app.py:117` correctly requires `ADMIN_PASSWORD` without default — confirming this was a known fix.)
- **Severity:** HIGH (in `app_broken.py` which is dead) → would be CRITICAL if file is ever revived.

#### S4. MEDIUM — Next.js image proxy allows any HTTPS host
- **Where:** `dashboard/next.config.js:5-7` — `remotePatterns: [{ protocol: 'https', hostname: '**' }]`
- **Why:** Wildcard hostname in `next/image` remotePatterns lets the image proxy fetch any HTTPS URL. While Next.js image proxy is sandboxed, this widens the SSRF/SSO surface unnecessarily. Should be restricted to known image hosts (`cdn.immoscout24.at`, `img.derstandard.at`, etc.).
- **Severity:** MEDIUM.

#### S5. MEDIUM — Dead `next-auth` dependency
- **Where:** `dashboard/package.json:14` — `"next-auth": "^4.24.14"`. `AuthProvider.tsx` wraps `<SessionProvider>` but never calls `signIn`/`signOut`. Middleware checks custom cookie, not next-auth session.
- **Why:** Two auth systems coexist (custom cookie for actual auth, next-auth for unused UI context). `next-auth` adds ~50KB gzipped + attack surface (JWT secret handling) for zero value. Past commit `11bda7c` removed the dead NextAuth route but missed the dep + wrapper.
- **Severity:** MEDIUM.

### Architecture & Design

#### A1. HIGH — Two parallel web stacks (Flask + Next.js)
- **Where:** `Project/Api/app.py` (Flask, 27.7K, 9 routes) + `dashboard/` (Next.js, current)
- **Why:** Flask app is not referenced in `.github/workflows/`, `dashboard/package.json`, or any current entry point (verified by grep across repo). Yet it ships with the full Flask-Login setup, user registration, hardcoded backdoor. Suggests the migration to Next.js was incomplete — Flask is dead code that increases attack surface and confuses new contributors.
- **Severity:** HIGH.

#### A2. HIGH — `app_broken.py` (24.9K) is dead code with hardcoded secrets
- **Where:** `Project/Api/app_broken.py` (existence) + `Project/Api/auth_api.py` (9K) + `Project/Api/__init__.py`
- **Why:** File name is self-incriminating. 24.9K of Flask code with `admin123` default, the `secrets` module import for `SECRET_KEY` generation, password hashing — all unreferenced. Keeping it makes git history noisy and risks accidental import.
- **Severity:** HIGH.

#### A3. MEDIUM — Dual sources of truth for scoring weights
- **Where:** `Project/Application/scoring.py:23` (contextvars `_current_weights`) + `Project/Application/scoring.py:27` (legacy global `CRITERIA_WEIGHTS`)
- **Why:** Thread-safe contextvars introduced later, but the legacy global is kept "for backward compatibility" and updated in `set_buyer_profile()` (line 73-74). Two writes per profile change. Either keep the contextvar only and remove the global, or use a single source.
- **Severity:** MEDIUM.

#### A4. MEDIUM — `Listing` dataclass has 70+ fields; growth trajectory is unsustainable
- **Where:** `Project/Domain/listing.py:7-83`
- **Why:** 70+ typed fields including mortgage details, energy, infrastructure distances, regulatory flags (added May/June), 10+ new fields proposed in current specs (rent_regulated, wieneu_zone, anergy_distance, gratzl_id, rental_yield, etc.). At 100+ fields, the dataclass becomes a god object; cross-field invariants (e.g., `estimated_down_pct` and `estimated_equity_eur`) become uncheckable. Consider grouping into nested dataclasses (`MortgageDetails`, `EnergyProfile`, `LocationContext`).
- **Severity:** MEDIUM (preventive).

### Code Quality

#### C1. HIGH — `dashboard/lib/types.ts` has duplicate `MapListing` interface
- **Where:** `dashboard/lib/types.ts:17` (first declaration) and `dashboard/lib/types.ts:41` (second declaration)
- **Why:** TypeScript silently merges or overrides the duplicate (depending on file structure). The second declaration has 3 extra fields (`bank_score_confidence`, `estimated_down_pct_kimv`, etc.) — properties in `ListingDetail` may not exist on `MapListing` at runtime. Also: `export type ListingDetail = any;` (line 38) disables type checking for the most-consumed shape.
- **Severity:** HIGH.

#### C2. HIGH — `MongoDBHandler.__init__` mutates URI string with TLS hack
- **Where:** `Project/Integration/mongodb_handler.py:36-44` (the `if "mongodb.net" in self.uri` block)
- **Why:** Sniffs for "mongodb.net" substring to add `tlsAllowInvalidCertificates=true`. Substring match is brittle (any host with "mongodb.net" in path triggers it). `tlsAllowInvalidCertificates=true` disables cert validation — defeats TLS purpose. Should be explicit env var (`MONGO_TLS_INSECURE=true` for local dev only).
- **Severity:** HIGH.

#### C3. MEDIUM — Massive scraper files with copy-paste extraction
- **Where:** `Project/Application/scraping/willhaben_scraper.py` (85.8K, 80+ methods), `derstandard_scraper.py` (87.7K), `immo_kurier_scraper.py` (54.4K)
- **Why:** Each scraper implements its own `extract_price`, `extract_area`, `extract_rooms`, `extract_year_built`, etc. — same field names, different HTML. Logic is duplicated. The 5.7K `field_extractors.py` exists but only Willhaben uses it (visible from imports). A 228K-line scrape layer with 3x duplication is a maintenance trap when sites change.
- **Severity:** MEDIUM (works, but slows future scraper work).

#### C4. MEDIUM — `ensure_config_json_on_path()` copy-pasted across entry points
- **Where:** `Project/run.py` + `Project/run_top5.py:35-49` + `Project/run_outreach.py`
- **Why:** Identical 14-line config-path-search logic in 3+ places, including hardcoded `/home/runner/work/ImmoAgent/...` paths. A canonical `load_config()` exists in `Application/helpers/utils.py` (per `mongodb_handler.py:14`) but isn't used consistently. The hardcoded GitHub Actions paths will break when repo name changes.
- **Severity:** MEDIUM.

### Testing

#### T1. HIGH — `ListingDetail = any` disables type checking on the most-tested surface
- **Where:** `dashboard/lib/types.ts:38` — `export type ListingDetail = any;`
- **Why:** Playwright tests assert on ListingDetail rendering. With `any`, the TS compiler can't catch missing fields, wrong types in the 70+ listing fields. Past commits (e.g., `c2312c6 fix: create missing lib/types.ts, add missing fields to API routes, fix ListingDetail type`) show this is a recurring problem.
- **Severity:** HIGH.

#### T2. MEDIUM — Test suite of 90+ files with significant staleness
- **Where:** `Tests/` directory (12K lines, 90+ test files)
- **Why:** Many files are iterative debug tests (`test_derstandard_debug_criteria.py`, `test_criteria_debug.py`, `test_derstandard_data_debug.py`, `test_derstandard_enhanced_logging.py`, etc.) — 5+ files are debug-only with `_debug` in the name. These aren't regression tests; they were used to diagnose a specific issue then never cleaned up. Test discovery becomes slow; test selection for CI becomes hard. Per past session note: "Most Python tests pass except test_auth.py requiring running Flask app" — auth tests are the only ones tied to a specific (dead) endpoint.
- **Severity:** MEDIUM.

#### T3. MEDIUM — 5 specs propose adding to a Listing model with no test for the dataclass itself
- **Where:** `Project/Domain/listing.py` (no `test_listing.py` or `test_listing_fields.py` beyond the 729B `test_listing_fields.py` and 1012B `test_listing_coordinates.py`)
- **Why:** The 70+ field dataclass is the API contract. Tests exist for individual field extractors (scraper tests) but no test verifies the dataclass itself instantiates with all proposed new fields. When ideas #1-5 add ~10 more fields, there's no central regression check that the model + MongoDB serialization still round-trips.
- **Severity:** MEDIUM.

### Performance / DevEx

#### P1. LOW — `app.py:8` imports `werkzeug.security`, `flask_login` — Flask stack ships but doesn't run
- **Where:** `Project/Api/app.py:9-14` and many other imports
- **Why:** If Flask is dead, these imports are dead too. Cold-start cost of `Project/` for any tooling (lint, type-check, test discovery) increases. Module-level imports also run in subprocess tests.
- **Severity:** LOW.

---

## Strengths

The repo is **not** a mess. These are worth preserving:

- **Strong design discipline** — 20 design specs in `docs/superpowers/specs/`, with grill-me iterations. Recent specs (rent-regulated, green infra, Grätzl) follow consistent template.
- **Active bug-fix cadence** — last 30 commits include 5+ targeted fixes (auth simplification, dead code removal, missing imports, type-safety holes). The pattern is "find issue, spec the fix, commit." Mature.
- **Validation single source of truth** — `is_valid_listing_data()` in `mongodb_handler.py` is used everywhere. The CLAUDE.md explicitly forbids inline `> 0` checks. This is rare discipline.
- **Financial feasibility engine** — `Project/Application/feasibility.py` (8.7K) has Austrian tax law baked in (GGG §26a exemption, GrESt rates, annuity math). Well-tested. Genuinely useful.
- **Buyer profile system** — 10 personas with weighted scoring, contextvars for thread safety, weighted-sum validation. Clean separation of who (profile) from how (scoring).
- **Recent UI/UX commitment** — 3 Playwright spec files (898 lines), CI-required smoke tests, hard rule "no commit dashboard changes when tests are failing."
- **Taken-listings tracking** — committed June 7 (`7ca1be7`) — meaningful v2 feature with proper spec, plan, grill-me iterations.
- **URL validation in display path** — `run_top5.py` validates URLs before Telegram send. CLAUDE.md rule 2 enforces this across display paths.

---

## Improvement Strategy

### Theme 1: Remove dead code & consolidate parallel implementations (1-2 days)
**Principle:** If two implementations exist, delete one. Dead code in a personal repo is debt, not safety.
**Target state:** Single web stack (Next.js). No `app_broken.py`, no unused `next-auth`, no Flask imports in Project/. Scoring has one weight storage (contextvar OR global, not both).
**Not fixing:** Old specs in `docs/superpowers/specs/` are historical — keep. Legacy buyer profile defaults in `BUYER_PROFILES` are referenced — keep but document.

### Theme 2: Fix the auth + types stack (1 day)
**Principle:** The dashboard is the user-facing surface; auth and types are the load-bearing parts. Make both correct.
**Target state:** Custom cookie auth with 7-day expiry + server-side secret. `ListingDetail` is a proper TypeScript interface (not `any`). Duplicate `MapListing` removed.
**Not fixing:** Migrating to next-auth (overkill for personal tool with one user).

### Theme 3: Make the Listing model maintainable (1-2 days, preventive)
**Principle:** Prevent the 70-field dataclass from becoming 100+ fields across 5 upcoming specs. Group related fields.
**Target state:** Nested dataclasses (`MortgageDetails`, `EnergyProfile`, `LocationContext`, `RegulatoryProfile`). The 5 upcoming spec field additions group naturally:
- Idea #1: `RegulatoryProfile` (rent_regulated, source)
- Idea #2: `GreenInfra` (nearest_wieneu_zone, anergy_distance_m, subsidy_eligible)
- Idea #3: `LocationContext` (gratzl_id) — already exists for ubahn/school distances
- Idea #4: `InvestmentProfile` (rental_yield_pct, price_per_m2_history)
- Idea #5: none (UI-only)

**Not fixing:** MongoDB migration. Backward compat handled via None defaults.

### Theme 4: Test suite hygiene (half day)
**Principle:** Test files named `*_debug*.py` are diagnostic scratch, not regression tests. Move to `scratchpad/` or delete.
**Target state:** `Tests/` contains only regression tests. CI runs them in <30s. Debug files archived.
**Not fixing:** Adding more tests. The current coverage of feasibility + scoring is reasonable.

### Theme 5: Config + secrets single source (half day)
**Principle:** `load_config()` should be the only config loader. `ensure_config_json_on_path()` is one search-path set, not three.
**Target state:** `load_config()` in `helpers/utils.py` is canonical. Entry points import it. Hardcoded `/home/runner/...` paths removed (replaced with env var `IMMO_CONFIG_PATH` or relative path).
**Not fixing:** Env-var-only config (user still uses `config.json` for local dev — that's fine).

### Done signals (measurable)
- [ ] `git grep "app_broken" Project/Api/` returns 0 results.
- [ ] `git grep "next-auth" dashboard/` returns 0 results.
- [ ] `dashboard/lib/types.ts` has no duplicate `MapListing`, no `any` types.
- [ ] `dashboard/lib/auth.ts` checks `Date.now() - timestamp < SESSION_TTL_MS`.
- [ ] `Project/Api/app.py` deleted. `Project/Api/` either removed or replaced with `__init__.py` only.
- [ ] `Project/Domain/listing.py` reduced from 70+ top-level fields to <40 + 4 nested dataclasses.
- [ ] `Tests/test_*_debug*.py` files: 0 (or moved to scratchpad/).
- [ ] `git grep "ensure_config_json_on_path"` returns 0 (or 1, in `load_config()` only).

---

## Task Plan

### Milestone 0: Safety net (S total)
| # | Task | Files | Effort | Risk | Notes |
|---|------|-------|--------|------|-------|
| 0.1 | Snapshot current main, branch `audit/cleanup-2026-06` | git | S | none | All work on branch, no push to main |
| 0.2 | Run `python Tests/run_tests.py` baseline — record pass count | CI | S | none | 6-9 tests may fail (auth-related) |
| 0.3 | Add type-check baseline `cd dashboard && npx tsc --noEmit` | dashboard | S | none | Already passing per recent fixes |

### Milestone 1: Critical fixes (1-2 days)
| # | Task | Files | Effort | Risk | Notes |
|---|------|-------|--------|------|-------|
| 1.1 | **Remove `if username == 'test' and password == 'test123'` backdoor** | `Project/Api/app.py:138` | S | low | Dead code, but if Flask app ever runs... |
| 1.2 | **Delete `Project/Api/app_broken.py`** (24.9K) | `Project/Api/app_broken.py` | S | low | Pure dead code |
| 1.3 | **Delete `Project/Api/` entire directory** (Flask legacy) | `Project/Api/` | M | medium | Verify nothing in `dashboard/` or workflows imports it. Then delete. |
| 1.4 | **Remove `next-auth` dep + `AuthProvider.tsx` wrapper** | `dashboard/package.json`, `dashboard/components/AuthProvider.tsx`, `dashboard/app/layout.tsx` | S | low | Per task #5 idea, user wants auth drop anyway |
| 1.5 | **Add session expiration to dashboard auth** | `dashboard/lib/auth.ts` | S | low | Check `Date.now() - timestamp < 7*24*3600*1000` |
| 1.6 | **Restrict Next.js image proxy remotePatterns** | `dashboard/next.config.js` | S | low | Whitelist known image hosts |
| 1.7 | **Remove TLS hack from MongoDBHandler URI sniff** | `Project/Integration/mongodb_handler.py:36-44` | S | low | Use explicit `MONGO_TLS_INSECURE` env var |

### Milestone 2: High-leverage improvements (1-2 days)
| # | Task | Files | Effort | Risk | Notes |
|---|------|-------|--------|------|-------|
| 2.1 | **Fix duplicate `MapListing` interface** | `dashboard/lib/types.ts` | S | low | Delete line 41 (duplicate) |
| 2.2 | **Replace `ListingDetail = any` with real interface** | `dashboard/lib/types.ts` | M | medium | Generate from 70+ Listing fields + new spec fields |
| 2.3 | **Consolidate config loader** — `ensure_config_json_on_path()` lives in `load_config()` only | `Project/run_top5.py`, `Project/run_outreach.py` | S | low | Remove hardcoded `/home/runner/...` paths |
| 2.4 | **Remove legacy scoring global** | `Project/Application/scoring.py:27` | S | low | Verify no external code reads `CRITERIA_WEIGHTS` |
| 2.5 | **Add regression test for Listing dataclass** | `Tests/test_listing_dataclass.py` (new) | S | low | Round-trip all 70+ fields through Mongo serialization |

### Milestone 3: Quality & polish (1-2 days)
| # | Task | Files | Effort | Risk | Notes |
|---|------|-------|--------|------|-------|
| 3.1 | **Move 12 `*_debug*.py` test files to scratchpad/** | `Tests/test_*_debug*.py` | S | low | Or delete; not in regression path |
| 3.2 | **Refactor `Listing` into nested dataclasses** (groups per Theme 3) | `Project/Domain/listing.py` | L | high | Backward compat via property aliases. Big PR — do after 5 specs land, or 1 of them ships. |
| 3.3 | **Restrict Next.js middleware to `/dashboard/:path*` matcher** (already done) | — | — | — | Verified in `dashboard/middleware.ts:18` |
| 3.4 | **Add CI step: `dashboard` lint + typecheck + Playwright** | `.github/workflows/dashboard-ci.yml` (new) | M | low | Currently dashboard CI is implicit/manual |
| 3.5 | **Document session/auth model in dashboard README** | `dashboard/README.md` (new) | S | none | After auth decision (drop or keep) |

### Quick wins (do immediately, <1h each)
- **QW1:** Remove `next-auth` dep + `AuthProvider.tsx` wrapper (M1.4)
- **QW2:** Delete `app_broken.py` (M1.2)
- **QW3:** Remove `test/test123` backdoor (M1.1)
- **QW4:** Restrict Next.js image proxy (M1.6)
- **QW5:** Fix duplicate `MapListing` interface (M2.1)
- **QW6:** Add session expiration (M1.5)

### Top 3 task implementation sketches

**Task 1.1: Remove hardcoded backdoor**
- **Approach:** Delete the 4-line `if username == 'test' and password == 'test123':` block in `Project/Api/app.py:138`.
- **Gotcha:** This is a Flask app line. If user has not yet decided to drop Flask entirely, this is the safer partial fix. Otherwise, task 1.3 (delete Flask) is preferred.
- **Verification:** `grep -n "test123" Project/Api/app.py` returns 0.

**Task 2.2: Replace `ListingDetail = any` with real interface**
- **Approach:** Generate the interface from `Project/Domain/listing.py` field list. Manually mirror the 70+ fields. Use TypeScript optional `?` for nullable fields.
- **Key steps:**
  1. Read `Project/Domain/listing.py:7-83` field-by-field
  2. Mirror each as `field_name: type | null` in `ListingDetail`
  3. Remove the `any` line
  4. Run `npx tsc --noEmit` to find any consumer type mismatches
  5. Fix consumers in `dashboard/components/ListingDetail.tsx` etc.
- **Gotcha:** Nested `Dict[str, Any]` fields (`mortgage_details`, `betriebskosten_breakdown`, `infrastructure_distances`, `structured_analysis`) need their own interfaces or stay as `Record<string, unknown>`. Some can be typed precisely (e.g., `mortgage_details: MortgageDetails` if schema is known).
- **Verification:** `npx tsc --noEmit` passes; `git grep "ListingDetail = any"` returns 0.

**Task 3.2: Refactor Listing into nested dataclasses (after at least 1 of the 5 new specs lands)**
- **Approach:** Introduce 4 nested dataclasses, migrate fields, keep backward compat via property aliases for 1 release.
- **Key steps:**
  1. Add `MortgageDetails`, `EnergyProfile`, `LocationContext`, `RegulatoryProfile` dataclasses in `Project/Domain/`
  2. In `Listing`, replace 30+ top-level fields with `mortgage: Optional[MortgageDetails] = None`
  3. Add property aliases (`@property def own_funds(self): return self.mortgage.own_funds if self.mortgage else None`)
  4. Update MongoDB serialization: keep flat top-level keys (use `dataclasses.asdict` + flat merge) for backward compat with existing docs
  5. Update dashboard types to mirror new shape
  6. Add `Tests/test_listing_dataclass.py` to verify all property aliases still work
- **Gotcha:** MongoDB has 1000s of existing docs with flat fields. Migration script must either: (a) leave flat fields + add nested view on read, (b) backfill to nested (one-time script). Option (a) safer. Don't break existing queries.
- **Verification:** All existing queries still return correct data; new specs populate nested fields; flat fields still readable via aliases.

---

## Open Questions

These need user (owner) decisions before proceeding:

1. **Flask app fate:** Delete entirely (M1.3) or keep for any reason? If the Flask `UI/` templates or static assets are referenced anywhere, that's a blocker.
2. **Auth fate:** Per user's earlier pivot ("drop dashboard auth entirely"), is the Next.js custom cookie auth also being removed? If yes, M1.5 (expiration) is moot — just delete auth files. The 6th spec writeup mentioned login drop as a follow-up.
3. **TLS insecure mode:** Is the `tlsAllowInvalidCertificates=true` MongoDB hack used in production or just for one-off debugging? If production, M1.7 needs a real TLS cert setup, not just removing the hack.
4. **Test debug files:** Delete or move to `scratchpad/`? 12 files × ~5K avg = 60K of likely-stale test code. The user may have diagnostic notes in them.
5. **Listing refactor timing (M3.2):** Do 5 specs first, then refactor? Or refactor first so specs land on the new shape? Refactor-first is more correct; specs-first is less work upfront but adds tech debt.
6. **5 specs in flight:** All 5 specs (rent-regulated, green infra, Grätzl, dual mode, draw/cluster) are written and committed. Implementation can begin in any order. Are they all priority, or some v2-deferred? Currently scoped as "v1 each" but each adds 200-700 lines of code + tests. Total new code = ~3000-5000 lines if all implemented.
7. **Dashboard type safety push:** The audit recommends M2.2 (replace `any` with real interface). With 5 new spec field additions, the `ListingDetail` interface would grow by 10+ fields. Worth doing before or after the new specs land?
8. **MongoDB index for shape filter (idea #5):** Spec requires `2dsphere` index on `loc` field. Is this index already present? `git grep "2dsphere" Project/` would tell. If not, requires a migration script.

---

**End of audit. No code modified per constraint. Document committed separately for review.**
