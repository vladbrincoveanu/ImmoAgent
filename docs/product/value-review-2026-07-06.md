# Product Value Review — Profiles & Map Differentiation

Date: 2026-07-06 · Basis: live prod data (2,297 listings, all with per-profile scores as of today)

## 1. Do the buyer profiles make sense? (data-driven audit)

Spearman rank correlation between profile rankings over the current top-100 prod listings:

| Pair | ρ | Verdict |
|---|---|---|
| eco_conscious ↔ bank_loan_ready | 0.98 | duplicates |
| urban_professional ↔ prime_new_build | 0.96 | duplicates |
| default ↔ owner_occupier | 0.94 | duplicates |
| owner_occupier ↔ retiree | 0.86 | near-duplicates |
| diy_renovator ↔ prime_new_build | 0.00 | genuinely different |
| growing_family ↔ budget_buyer | 0.08 | genuinely different |
| diy_renovator ↔ urban_professional | 0.15 | genuinely different |

**Conclusion:** of 10 profiles only ~5 produce materially different rankings. A paying
user comparing eco_conscious vs bank_loan_ready sees the same list — that erodes trust
in the whole scoring product.

### Recommended consolidation: 10 → 5

| Keep | Absorbs | Tier |
|---|---|---|
| **Owner-Occupier** (rename of default) | owner_occupier, retiree | **Free** |
| **First-Time Buyer** | budget_buyer | Pro |
| **Growing Family** | — | Pro |
| **Renovator / Investor** | diy_renovator (+ add rent-yield weight) | Pro |
| **Urban Professional** | prime_new_build, eco_conscious, bank_loan_ready | Pro |

- Free tier gets one good default ranking — enough to demonstrate the scoring works.
- Pro (€19/mo) unlocks persona switching, which now visibly changes the ranking
  (verified: 4 profiles → 4 distinct top-10 orderings in prod).
- Enforcement: existing 402 freemium gate (`lib/user.ts`, PaywallModal). Gate the
  `profile` query param server-side: non-Pro + non-default profile → 402.
- Python: keep computing all profile scores at scrape time (cheap, already automatic
  via `_persist_profile_scores`); consolidation is a `buyer_profiles.py` +
  `dashboard/lib/profile.ts` change.

## 2. Map differentiation vs Willhaben / ImmoKurier / DerStandard

What the portals cannot do (they are single-source sell-side marketplaces):

| Differentiator | Status | Why portals can't copy easily |
|---|---|---|
| Cross-source aggregation (3 portals, deduped, one map) | ✅ live | Business-model conflict |
| Per-persona value score on every listing | ✅ live (today) | They rank by paid placement, not buyer value |
| Below-district-average deal detection (`price_vs_avg_pct`) | ✅ API exists | Sellers would revolt |
| District €/m² choropleth heatmap | ✅ live | Neutral market data undermines listing prices |
| U-Bahn + school overlays with walk times | ✅ fixed today | Generic maps exist, but not fused with scoring |
| Financing feasibility filter (equity/rate → affordable pins) | ✅ live | Portals sell leads to banks instead |
| Email alerts on new *undervalued* listings | Pro gate live | Portals alert on new, not on *mispriced* |

### Top 3 roadmap items to make the map obviously valuable (ranked)

1. **Deal lens (highest ROI):** color pins by `price_vs_avg_pct` — green = below
   district average, red = above; badge "−12% vs 1070 avg" on pin + card. This is the
   single clearest "why not Willhaben" feature and the data already exists.
2. **Persona-aware pins:** pin color/intensity driven by `scores[activeProfile]`, so
   switching persona visibly repaints the map. Pairs with the Pro gate on profiles.
3. **"Total monthly cost" mode:** price → estimated monthly (mortgage @ user
   equity/rate + Betriebskosten estimate); portals show sticker price only, buyers
   think in monthly cost.

Deferred (nice, not decisive): rent-yield overlay for investors, commute isochrones
(needs routing API — cost), 3D districts view.

## 3. Fixed today (evidence)

- Per-profile read models: backfilled `scores.{profile}` for all 2,297 prod listings
  (0 errors); `/api/listings/top?profile=X` verified to return distinct orderings and
  per-profile scores. New listings get scores automatically at scrape time.
- U-Bahn/school map layers: page never fetched `/api/geo/infrastructure`; now wired,
  layers default on, geo data bundled into the deployment (old code read
  `../Project/data`, which doesn't exist on Vercel).

## 4. Known remaining gaps

- `_fetch_and_score_listings` (Python, Telegram path) recalculates missing scores with
  startup-flag weights, not the requested profile — minor, listing scores are now
  precomputed everywhere.
- Prod listings are largely un-geocoded → pins sit on district centroids; per-listing
  `ubahn_walk_minutes` precision suffers. Needs a geocoding backfill run.
- Profile consolidation (10→5) and the Pro gate on profile switching are proposed, not
  yet implemented — awaiting product sign-off on this document.
