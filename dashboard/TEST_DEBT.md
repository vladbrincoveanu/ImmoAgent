# Dashboard Test Debt — follow-up

Created 2026-07-07 after the map visual redesign (commit `23e7352`).
The redesign itself is verified: targeted specs 8/8 green locally, and the
`desktop-redesign` spec 7/7 green against **live production**
(`https://immo-agent-vienna.vercel.app`) via `playwright.prod.config.ts`.

These items are **pre-existing** suite failures and local scratch — none are
regressions from the redesign. Fix them as a separate, self-contained task.

## Baseline at time of writing
Full local suite (prod build on `:3060`, real Mongo, 200 listings):
**83 pass / 34 fail**. All 34 failures trace to the two root causes below.

## Issues to fix

### 1. `networkidle` waits never resolve (SSE keeps the page busy)
- **Symptom:** specs that `await page.waitForLoadState('networkidle')` time out
  on `/`, `/dashboard`, `/dashboard/map`.
- **Cause:** the listings SSE stream (`/api/listings/stream`) holds an open
  connection, so the network is never idle.
- **Fix:** replace `networkidle` waits with deterministic waits on a concrete
  DOM selector that proves the page is ready (e.g. first listing card / map
  pin / rail count), matching the pattern already used in
  `tests/desktop-redesign.spec.ts`.
- **Find them:** `grep -rn "networkidle" dashboard/tests`

### 2. `map-full` spec asserts the pre-redesign sidebar
- **Symptom:** `tests/map-full*.spec.ts` assert the old sidebar/layout that the
  redesign replaced (top-bar + `ListingRail` + `SlimListingCard`).
- **Fix:** rewrite those assertions against the current layout. Use
  `tests/desktop-redesign.spec.ts` as the source of truth for the new selectors
  (`ListingRail` at 340px, `MapTopBar` brand/Filters/Layers, `SelectedCard`
  bottom-left 320px, navy→blue pin selection).

## Untracked local scratch to delete or gitignore
Not part of the deliverable; currently inflating the failure count and cluttering
`git status`:
- `dashboard/tests/debug.spec.ts`
- `dashboard/tests/debug-gate.spec.ts`
- `dashboard/tests/prod-check.spec.ts`
- `dashboard/../capture-baselines.mjs` (repo root)
- `dashboard/../map-redesign-desktop.jpeg` (repo root)

**Action:** either `git rm`-nothing (they're untracked) → just delete them, or
add throwaway patterns to `.gitignore` (`tests/debug*.spec.ts`, `*-baselines.mjs`,
`*-redesign-*.jpeg`).

## Definition of done for the follow-up task
- `npx playwright test --config playwright.local.config.ts` → 0 failures on a
  prod build served at `:3060` with real data.
- No `networkidle` waits remain in `dashboard/tests`.
- Untracked debug specs removed; `git status` clean under `dashboard/tests`.
