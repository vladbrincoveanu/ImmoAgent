---
name: ui-testing
description: Use when making ANY change to dashboard/ files (components, pages, API routes, styles, config, or lib files)
---

# UI Testing Rule

**This rule is non-negotiable. Violations = broken production.**

## Trigger

ANY change to files under `dashboard/` — including but not limited to:
- `app/**/*.tsx`, `app/**/*.ts`
- `components/**/*.tsx`
- `lib/**/*.ts`
- `app/**/*.css`
- `middleware.ts`
- `next.config.js`
- `tailwind.config.ts`
- `playwright.config.ts`

If the change is in `dashboard/`, this rule applies. No exceptions.

## Required Loop (Never Skip)

After EVERY dashboard change:

1. **Start dev server**: `cd dashboard && npm run dev &`
2. **Wait for server**: `sleep 10` or until `localhost:3000` is reachable
3. **Run playwright tests**: `cd dashboard && npx playwright test --reporter=list`
4. **Read ALL errors** — browser console errors, test failures, network failures
5. **Fix immediately** — every error must be addressed before declaring done
6. **Re-run tests** until all pass clean (0 failures, 0 console errors)
7. **Stop dev server**: `pkill -f "next dev"` or kill the background job

## No Exceptions

These rationalizations are **forbidden** — they mean STOP and test:
- "It's a small change"
- "I didn't change any UI logic"
- "Tests would pass anyway"
- "The change is only in lib/ types"
- "I already tested manually"
- "It worked before"
- "Just a CSS tweak"

If the code changed in `dashboard/`, the UI must be tested. Full stop.

## When Tests Fail

If playwright tests fail or show console errors:
1. Read the error output carefully
2. Identify the root cause — do NOT just patch symptoms
3. Fix the code
4. Re-run tests
5. Repeat until clean

**Never commit dashboard changes when tests are failing.**

## Playwright Test Scope

Run ALL tests in `dashboard/tests/smoke.spec.ts`:
- Root page redirects to /dashboard
- /dashboard page loads without errors
- /dashboard/map page loads without errors
- Listing cards render or empty state shows
- Leaflet map container is visible

If you modify dashboard code, add tests for the new behavior. Tests are not optional.

## Skill Loading

**REQUIRED**: Use `playwright-pro` skill for any Playwright test authoring or debugging:
```
load skill: playwright-pro
```

## Verification

Before declaring done after ANY dashboard change:
- `npx playwright test --reporter=list` ran
- All 5 smoke tests passed
- Zero browser console errors on all 3 routes
- Dev server stopped after testing
