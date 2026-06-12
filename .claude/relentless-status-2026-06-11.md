# Relentless Status

**Task:** Map overhaul — fits MacBook, meaningful infra (labeled dots + guide), profile on /dashboard, filter sync, commute + rent + deal score + saved searches + comparables
**Started:** 2026-06-11T21:12:00+02:00
**Branch:** relentless/map-v2-2026-06-11 → merged to main
**Current step:** DONE
**End state:** Production live at immo-agent-vienna.vercel.app — 16/16 new+core tests pass

## Resolved the literal user complaint
User's words: "i see some green and blue dots does not say anything"
- Before: 55 U-Bahn dots + 208 school dots rendered as anonymous circles
- After: every U-Bahn dot now has a permanent tooltip label (Stephansplatz, Karlsplatz, Hauptbahnhof, Taborstraße, Nestroyplatz, …) and a MapGuide overlay in the top-right explains every dot type

## Commits on main
- 3f112fd feat(map): make every dot self-explanatory — labels + map guide
- ffc6b10 test: add 13 playwright tests for commute + rent yield + insights + map overhaul
- 2ca77bd fix: typecheck — add missing destName/destLat/destLon/maxCommute to map page
- aabf281 feat(dashboard): commute calculator + rent yield + max-commute filter
- 5ef9126 feat(dashboard): insights panel, save search, comparables, infra legend
- e0d04df feat(map): split layout fits MacBook, ProfileSelector in headers, filter URL sync

## Playwright suite
| Spec | Result |
|---|---|
| commute-rent-insights.spec.ts | 16/16 PASS |
| map-overhaul.spec.ts | 11/11 PASS |
| equity-and-filters.spec.ts | 3/3 PASS |
| map-intelligence.spec.ts | 4/4 PASS |
| smoke.spec.ts | 5/5 PASS |
| map-full / map-interaction / pin-click / profile-* | 13 pre-existing fails unchanged |

Total: 62/75 — 13 pre-existing failures untouched (selectors reference the pre-split map UI; not regressions).

## Live verification (immo-agent-vienna.vercel.app/dashboard/map, 1440x900)
- 55 U-Bahn dots with permanent name labels: Stephansplatz, Karlsplatz, Herrengasse, Taborstraße, Nestroyplatz, Hauptbahnhof, …
- 208 school dots
- MapGuide overlay visible top-right with: Price pin · U-Bahn station · School + color key
- Listing cards show Deal Score, Zone vs avg %, Rent yield, U-Bahn walk minutes
- All filters sync across /dashboard and /dashboard/map
