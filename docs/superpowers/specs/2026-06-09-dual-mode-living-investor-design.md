# Dual Dashboard Mode (Living vs Investor) — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Scope:** v1 — top-level mode toggle, mode-aware UI, live ROI calculator

## 1. Architecture

Mode is orthogonal to Buyer Profile. Profile controls scoring weights; mode controls UI surfaces (filters, ListingDetail sections, map overlays, API defaults). Single React context + URL/localStorage persistence + 2-state segmented control in top nav.

```
URL ?mode=living|investor → ModeContext
  → filter registry swap
  → MapView overlay swap (heatmap on for Investor)
  → ListingDetail section swap
  → /api/listings?mode=... refetch with new defaults
```

## 2. Module Design Blocks

### Module: `dashboard/components/ModeProvider.tsx` (new)
- **Responsibility:** app-wide mode state with persistence
- **Interface:** React context `{ mode: 'living' | 'investor'; setMode: (m) => void }`
- **Resolution order:** URL `?mode=...` → localStorage `immo-mode` → default `'living'`
- **Side effects:** on change, sync URL param + localStorage
- **Size target:** <100 lines

### Module: `dashboard/components/ModeSelector.tsx` (new)
- **Responsibility:** top-nav 2-state segmented control
- **Interface:** two pill buttons; calls `setMode` on click
- **Style:** current mode = filled (blue/green palette), other = outline
- **Placement:** top nav, right of buyer profile selector
- **Size target:** <60 lines

### Module: `dashboard/lib/filters.ts` (extend)
- **Add:** `getFiltersForMode(mode: 'living' | 'investor'): FilterChip[]`
- **Living filters:** price, area, rooms, district, **[NEW]** commute_time_max, parks_within_walk, school_district_id, deposit_max
- **Investor filters:** price, area, rooms, district, **[NEW]** price_per_m2_max, rental_yield_min, **[NEW]** construction_year_min, **[NEW]** energy_class (HWB)
- **Shared:** regulatory, WieNeu+, Grätzl (from ideas #1, #2, #3)
- **Size target:** +40 lines

### Module: API filter defaults (`/api/listings/route.ts` extend)
- **Add param:** `?mode=living|investor`
- **Living:** no extra filter
- **Investor:** sort by `rental_yield_pct` desc, return investor fields (`rental_yield_pct`, `estimated_monthly_rent_eur`, `price_per_m2_history`)
- **Size target:** +20 lines

### Module: Listing model (extend `Project/Domain/listing.py`)
- **Add fields:**
  ```python
  estimated_rental_yield_pct: float | None = None
  estimated_monthly_rent_eur: int | None = None
  price_per_m2_history: list[dict] | None = None  # [{date, eur_per_m2}]
  ```
- All nullable

### Module: `Project/Application/financial/rental_yield.py` (new)
- **Responsibility:** estimate monthly rent from bezirk + area + property_type
- **Interface:** `estimate(bezirk: str|None, area_m2: float|None, property_type: str|None) -> int | None`
- **Data:** `Project/data/vienna_rent_avg.json` (curated, 23 districts × 2 property types = 46 entries)
- **Logic:** lookup; if missing → return None
- **Yield:** `(monthly_rent * 12) / purchase_price * 100`
- **Size target:** <100 lines

### Module: `dashboard/components/ROICalculator.tsx` (new)
- **Responsibility:** live ROI calc per listing
- **Inputs (with defaults):**
  - Down payment % (default 20)
  - Mortgage rate % (default 3.5 — current Austrian avg 2026)
  - Term years (default 25)
  - Monthly rent override (default = `estimated_monthly_rent_eur`)
  - Operating costs % of rent (default 25)
  - Vacancy % (default 5)
- **Outputs:**
  - Loan amount (purchase - down)
  - Monthly mortgage payment (annuity formula)
  - Gross rental income (monthly)
  - Net rental income (after vacancy + operating costs)
  - Monthly cashflow (rent - mortgage - costs)
  - Cap rate (NOI / purchase price)
  - Cash-on-cash return (annual cashflow / down payment)
  - Break-even rent (minimum to cover costs)
  - 10-year projection (2% appreciation, 3% rent growth)
- **Formula:** `M = P * r(1+r)^n / ((1+r)^n - 1)` standard annuity
- **Size target:** <250 lines

### Module: `dashboard/components/PriceHeatmapLayer.tsx` (new)
- **Responsibility:** render properties as heatmap overlay
- **Interface:** takes `MapListing[]`, renders Leaflet.heat layer
- **Color:** green (low €/m²) → yellow → red (high €/m²)
- **Default:** ON in Investor mode, OFF in Living mode
- **z-order:** below pins, above Grätzl polygons
- **Dependencies:** `leaflet.heat` npm package (8KB gzipped)
- **Size target:** <80 lines

### Module: ListingDetail mode-aware rendering (`dashboard/components/ListingDetail.tsx` extend)
- **Living mode sections (replace/extend current):**
  - "Schools within 1.2km" (from 15-min tool, idea #3)
  - "Commute estimate" (placeholder card — "Routing not available in v1, see ubahn walking time")
  - "Upfront costs" (Nebenkosten: 3.5% GrESt + 1.8% Escrow + 1.1% Bank/Notary + 3.6% broker conditional)
  - "Parks within 1.2km" (count only, parks data deferred)
- **Investor mode sections:**
  - "€/m² vs bezirk avg" (delta %)
  - "Estimated rental yield: X%" + "Estimated monthly rent: €X"
  - "ROI Calculator" (full panel)
  - "Price trajectory" (sparkline from price_per_m2_history)
  - "Energy class impact" (HWB-based yield adjustment: better HWB = higher achievable rent)
- **Shared sections:** title, photos, address, basic metadata, score, regulatory status (idea #1), green infra (idea #2), 15-min (idea #3)
- **Conditional render:** wrapped in `{mode === 'investor' && <InvestorSection />}`
- **Size target:** +200 lines

### Module: MapLegend mode-aware additions (`dashboard/components/MapLegend.tsx` extend)
- **Investor mode:** "€/m² heatmap" toggle (default ON)
- **Living mode:** "Schools" + "Commute" overlay toggles (commute deferred to v2)
- **Size target:** +30 lines

## 3. Data Flow

1. Page load → ModeProvider reads URL/localStorage → defaults to `'living'`
2. User clicks "Investor" → setMode('investor') → URL updates → API refetch with `?mode=investor`
3. API returns: sorted by yield desc, includes investor fields
4. FilterBar re-renders with investor chip set
5. MapView shows heatmap overlay (toggleable)
6. User clicks listing → ListingDetail shows Investor sections + ROI Calculator activates with defaults
7. User edits ROI inputs → live recalc, no refetch

## 4. Error Handling

- Missing rental yield estimate → ROI Calc shows "€—" + manual rent input prompt
- Mortgage rate negative or term 0 → input validation, clamp or show error
- Heatmap lib not installed → fallback to pin color gradient (existing code)
- mode URL param invalid → localStorage → default
- Heatmap on 0 listings → layer renders empty, no error
- Switching modes rapidly → debounce 300ms to avoid API thrash

## 5. Testing

### Unit
- `rental_yield.estimate()`: 5 cases (Wohnung 10./50m², EFH 22./150m², missing bezirk, missing area, edge)
- `ROICalculator` formula: 6 cases (different rate/term, break-even, cap rate, cash-on-cash)
- `ModeProvider`: 3 cases (URL wins, localStorage fallback, default)
- Filter registry: 2 cases (Living chips ≠ Investor chips)

### API
- `/api/listings?mode=investor` sorted by yield desc, includes investor fields
- `/api/listings?mode=living` no extra sort
- Listing detail includes all mode-relevant fields

### Playwright
- ModeSelector visible in top nav
- Click Investor → filter chips swap, heatmap appears, URL has `?mode=investor`
- Click Living → chips swap back, heatmap hides
- Refresh → mode persists
- Investor + listing click → ListingDetail shows ROI Calculator
- ROI inputs editable → output updates live

### Manual
- ROI calc outputs verified against known Austrian mortgage formula
- 1 known listing → compute ROI manually + via tool → match
- Heatmap visual: low €/m² green, high red
- Mode swap latency < 500ms (no jank)

## 6. Out of Scope (v1)

- Per-user saved scenarios (mortgage rate presets)
- Tax modeling (capital gains tax, depreciation)
- Multi-listing portfolio ROI
- Live mortgage rate from API (use config-driven default)
- Rent control impact on yield (idea #1 rent_regulated feeds v2)
- Commute routing (true isochrone, see idea #3)

## 7. Migration & Rollout

- Branch: `relentless/dual-mode-living-investor`
- Commits (11):
  1. `data: vienna_rent_avg.json curated (46 entries)`
  2. `feat(financial): rental_yield estimator module`
  3. `feat(financial): ROI Calculator component with full formula`
  4. `feat(domain): add rental yield + history fields to Listing`
  5. `feat(scrapers): wire rental_yield into 3 main scrapers + price history from existing tracker`
  6. `feat(ui): ModeProvider context + ModeSelector component`
  7. `feat(ui): mode-aware filter registry + FilterBar/FilterDrawer swap`
  8. `feat(map): €/m² heatmap layer (leaflet.heat) + MapLegend toggle`
  9. `feat(detail): mode-aware ListingDetail sections + ROI panel mount`
  10. `feat(api): mode filter param + investor field exposure`
  11. `test: rental_yield + ROI + ModeProvider + playwright mode swap`
- No feature flag (internal)
- Rollback: per-commit revert safe; mode defaults to living; existing UI unchanged on rollback

## 8. Known Risks

- **ROI calc assumptions mislead:** defaults (3.5% rate, 5% vacancy, 25% operating) are educated guesses, not personalized. Heavy disclaimer in UI: "Estimates only. Verify with your bank + tax advisor."
- **Heatmap performance:** leaflet.heat on 100+ points is fine; 1000+ may lag. Test with realistic data volume.
- **Rental yield crudeness:** bezirk avg ignores floor, condition, exact street. Real yield varies ±30%.
- **Mode toggling rapidly:** debounce 300ms on mode change → API refetch.
- **Investor mode data gap:** many listings lack price history → sparkline shows "Insufficient data" gracefully.
- **Two contexts coupling:** Buyer Profile + Mode are orthogonal but UI needs to render both clearly. Risk of confusion if both shown simultaneously without clear visual hierarchy.
