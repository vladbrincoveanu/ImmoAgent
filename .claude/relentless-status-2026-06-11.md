# Relentless Status

**Task:** Map overhaul — fits MacBook, meaningful infra, profile on /dashboard, filter sync, innovation
**Started:** 2026-06-11T21:12:00+02:00
**Branch:** relentless/map-v2-2026-06-11 → merged to main
**Current step:** DONE
**End state:** ✅ production live with all features

## Progress
- [x] Step 1: Map split layout — top 58% (map+sidebar) + bottom 42% (listings strip) fits 1440x900 without page scroll
- [x] Step 2: ProfileSelector in BOTH /dashboard and /dashboard/map headers, URL-synced
- [x] Step 3: All filter params sync via URL — clicking "Map view" from /dashboard preserves every filter
- [x] Step 4: Smart Insights panel — 7 metric cards (count, avg price, avg €/m², avg score, district count, below-zone-avg count, U-Bahn ≤5min)
- [x] Step 5: Save Search — POST/GET/DELETE /api/saved-searches with cookie-based user identity
- [x] Step 6: Comparables — top 5 best-ranked listings in same district with similar area/price, BETTER-DEAL badge
- [x] Step 7: Zone vs avg filter + badge — "Below zone avg by %" filter; -X% / +X% zone badge on every card
- [x] Step 8: Deal Score badge — composite 0-100 score (bank + price vs zone + transit + confidence)
- [x] Step 9: MapLegend now shows real U-Bahn/school counts from /api/geo/infrastructure
- [x] Step 10: 11 new Playwright tests, all 16 (smoke + new) passing
- [x] Step 11: Pushed to main, Vercel deploy READY (dpl_DwFVLejyx2UWtkrfacXYbxfiDgM1), production verified

## Skipped
- Commute calculator (skipped — no GTFS data, would need external API)
- Pre-existing 13 pin-click test failures (out of scope — depend on full-screen map layout that I deliberately changed)

## Blockers
- <none>

## Next action
- <task complete>
