---
title: Genossenschaft/gefördert aggregator — evaluation vs MyGEWO
date: 2026-07-14
status: draft (evaluation, pre-spec)
ui_scope: true
graph_scope: false
test_scope: true
---

# Genossenschaft aggregator (MyGEWO-style) — evaluation

**Question asked:** Is a co-op/subsidized-flat aggregator (like https://mygewo.at) a feature or a product? Copy or beat? Fit for immo-scouter?

**Short answer:** New *vertical* on immo-scouter (reuses ~80% of existing infra). Do NOT pure-clone; beat MyGEWO on its 3 cracks and go down-funnel where it stops. Best beachhead we've found for the rent pivot — reuses our scraper AND hits a proven payer.

---

## 1. Incumbent = MyGEWO (validated, occupied)
- MVP Software GmbH. 4.5★, 10k+ downloads. iOS + Android.
- Scrapes ~all gemeinnützige Bauträger every minute → filter (price/size/rooms/district/builder) → real-time push → apply redirects to each co-op site.
- **Money: freemium. Browsing free; instant notifications = Pro subscription (paywalled).** Reviews angry it got paywalled; some "accuracy" complaints.
- Speed is the moat: co-op ~€6.6/m² vs €8.1 private (~20% below market), scarce, "registration over in <30 min", "assigned in minutes."

## 2. Why it fits immo-scouter (near-zero marginal cost)
Loop = scrape → store → filter → alert → apply. We already own:
- `WillhabenScraper` engine + `field_extractors` (add co-op Bauträger as new sources)
- MongoDB + dedup + `listing_validator` (better accuracy than solo app)
- Telegram alert pipe (instant push, free — undercuts their paywall)
- Next.js map/dashboard + scoring (bundling a single-purpose app can't match)

## 3. Beat MyGEWO on its 3 cracks
1. **Free instant alert** via our Telegram infra (they paywalled it → users furious). Monetize down-funnel, not the alert.
2. **Accuracy + coverage** — reuse our validator/dedup; track more Bauträger + geförderte projects.
3. **Go past discovery** — eligibility check (Wiener Wohn-Ticket), Vormerkung guidance, one-tap register/dossier. MyGEWO stops at "here's the link." Nobody built the apply layer.

## 4. Beachhead logic (resolves rent-pivot §4 crux)
| Segment | Reuse our scraper | Proven payer | Pain | Inventory |
|---|---|---|---|---|
| Expat/student | ✗ (need furnished) | ✓ | strong | NEW market |
| Corp relocator | ✗ | ✓✓ | strong | NEW + B2B |
| Job-mover permanent | ✓ | ✗ (killed §1) | weak | ours |
| **Co-op hunter (this)** | **✓** | **✓ (mygewo)** | **strong (gone in min)** | **ours + co-op sites** |

Refutes rent-pivot §1 "renters don't pay for info": here info = access to a scarce below-market asset; speed = moat; they DO pay (mygewo proves it).

## 5. Money model
- **Free tier:** browse + delayed/Telegram alert (wedge, undercuts mygewo paywall).
- **Premium (proven):** instant push, saved multi-filters — mygewo already sells this.
- **Down-funnel (the real business, unbuilt by anyone):** eligibility check + Vormerkung + dossier/register assist. Upfront fee, enforceable (no success-fee capture leak — same logic as rent-pivot §5).

## 6. Risks (honest)
- **Thin data moat** — public co-op pages; incumbent already scrapes. Win = speed + coverage + down-funnel, not raw data.
- **Occupied market** — validated but not empty. Edge = bundling (buy + rent + co-op in one app) + free alert.
- **Feature-vs-business** — alert alone = feature. Business = down-funnel (eligibility/dossier/register).
- **Allocation nuance:** geförderte via Wohnberatung Wien = ranking-by-Wohn-Ticket-date (not speed); direct-Bauträger co-op units = first-come speed race. MyGEWO/we target the *speed-race subset*. Eligibility layer covers the ticket-based subset.

## 7. How to do it (build order)
1. **Source adapters** — scrape 5–10 biggest Bauträger (Sozialbau, BWSG, Wien-Süd, ÖVW, Arwag, Neue Heimat, GiWoG…) via existing scraper pattern. New `Application/scraping/genossenschaft_scraper.py`, wire into `main.py`, add `--genossenschaft-only`.
2. **Instant Telegram alert** — reuse `telegram_bot.py`; per-user saved filters → push on new match. This is the free wedge.
3. **Dashboard layer** — new "Genossenschaft" toggle/filter on existing map + grid (reuse `FilterBar`, `MapView`). `ui_scope: true` → Playwright DOM verify each cycle.
4. **Eligibility check** — form → Wohn-Ticket eligibility (residency, income limit, housing-need) + "which units need a ticket vs first-come."
5. **Dossier/register assist** (premium) — German packet + per-Bauträger register help.

## 8. Verdict
Build as a new vertical. Wedge = free instant Telegram alert (beat the paywall). Moat-building = coverage + accuracy + the apply/eligibility down-funnel MyGEWO never built. This is the strongest rent-pivot beachhead: reuses our engine, hits a proven payer, sharp local pain, huge TAM. Next: brainstorm → commit source list + eligibility rules → writing-plans.

## Sources
- MyGEWO: https://mygewo.at , https://mygewo.at/mygewo-app , Google Play `at.mvpsoftware.mygewo`, App Store id6477748990
- Wohn-Ticket / allocation: https://wohnberatung-wien.at/wohn-ticket , https://www.wohnnet.at/ratgeber/wohn-ticket-wien-beantragen-voraussetzungen-wartezeiten
- Co-op rents: https://www.wohnnet.at/ratgeber/genossenschaftswohnung-vergabekriterien-miethoehe-kaufoption
