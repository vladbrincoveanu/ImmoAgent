---
name: ui-testing
description: Use when making ANY change to dashboard/ files (components, pages, API routes, styles, config, or lib files)
---

# UI Testing Rule

Any change under `dashboard/` must be verified before declaring done. No exceptions ("small change", "CSS tweak", "lib types only" — still test).

## Iteration loop (token-efficient)
1. Start dev server once: `cd dashboard && npm run dev &`, wait for localhost:3000.
2. While iterating, run ONLY the spec(s) covering what you changed:
   `npx playwright test <spec> --reporter=dot`
3. On failure read only the failing test's error block; fix root cause; re-run that spec.
4. Do NOT take screenshots into context. Assert on DOM text/selectors. Screenshot to disk only on final unexplained failure.
5. Do NOT dump full console logs; grep them for `error|fail`.

## Final gate (before declaring done / committing)
- Full suite once: `npx playwright test --reporter=line` — 0 failures, 0 console errors on `/`, `/dashboard`, `/dashboard/map`.
- New behavior requires a new/updated test in `dashboard/tests/`.
- Stop dev server: `pkill -f "next dev"`.

Never commit dashboard changes with failing tests. Use `playwright-pro` skill for authoring/debugging tests.
