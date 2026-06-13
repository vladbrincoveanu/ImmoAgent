# Test Coverage — Dashboard

## 2026-06-13 — Dashboard UI Redesign (`/dashboard/map`)

**Branch:** `relentless/dashboard-ui-redesign`

**Verification status (per `feedback-verify-on-real-data.md` — local Mongo is empty):**

- **tsc:** 0 errors (after `rm -rf .next/types` to clear stale generated route types; the 10 pre-existing Next.js 15 `params: Promise<{...}>` rot errors in `app/api/**/route.ts` were fixed and committed in `chore(dashboard/api): migrate 6 route handler params to Next.js 15 Promise shape` + `fix(dashboard/listings-page): migrate params to Next.js 15 Promise shape`).
- **Dev server smoke:** HTTP 200 at `http://localhost:3000/dashboard/map`. HTML contains `data-testid="map-top-bar"`, `data-testid="listing-rail"`, `data-testid="mobile-map-fallback"`, and the "Immo Scouter" brand.
- **Vercel prod build:** green (after the two Promise-type commits). Latest deploy: `dpl_DRywocZcMCoQZ1U43YymtymfBZqL` on `immo-agent-7prypa67n-vladbrincoveanus-projects.vercel.app`. URL is behind Vercel Authentication; `get_access_to_vercel_url` returns a shareable token but `web_fetch_vercel_url` re-401s — manual `vercel curl` or trusted-sources token required for end-to-end prod verification.
- **Visual baselines (3 viewports):** `.frontend-design/baselines/dashboard-map-{mobile,tablet,desktop}.png` captured from local dev server. New UI confirmed: "Immo Scouter" top bar, Buyer Profile select, Filters button, 340px listing rail on the left, map area on the right.

**Test files: 16** (was 14 before this work).

**Changes:**
- New: `tests/slim-listing-card.spec.ts`
- New: `tests/desktop-redesign.spec.ts` (T3+T4+T5+T6+T7+T8+T9 tests appended in one file)
- Updated: 5 existing files (`map-full`, `address-bank-declutter`, `commute-rent-insights`, `map-overhaul`, `map-interaction`, `pin-click`) — FilterDrawer/MapLayerToggle/MapLegend/MapGuide/PriceHeatmap references rewritten to new popovers or removed.

**Test suite gates:**
- Local `npx playwright test`: most tests fail because local Mongo is empty — expected per `feedback-verify-on-real-data.md`.
- Prod `npx playwright test --config=playwright.prod.config.ts`: requires the Vercel Authentication bypass to be configured for the agent host. Not run in this session due to the auth wall. The new code itself renders the new UI on the local dev server (verified by HTML inspection) and the prod build compiles green.

**Open follow-ups (out of scope for this branch):**
- The 7th modified API route file `app/api/listings/map/route.ts` (large 106-line refactor unrelated to Promise migration) remains uncommitted in the working tree from a prior session.
- A Vercel Authentication bypass needs configuration for automated prod playwright runs against `https://immo-agent-vienna.vercel.app`.
