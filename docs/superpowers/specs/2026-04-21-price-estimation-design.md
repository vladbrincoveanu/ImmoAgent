# Preis auf Anfrage Price Estimation — Design Spec

> **Goal:** Show estimated prices for "Preis auf Anfrage" (price on request) listings using €7000/m² imputation, with a `~` prefix to signal the estimate.

## Context

The Python scraping pipeline already filters out "Preis auf Anfrage" listings at ingestion (see `mongodb_handler.py` and `listing_validator.py`). However, legacy listings with `price_total: null` already exist in MongoDB. The dashboard API currently returns these without any price or scoring accommodation, resulting in listings like "Wiener Wohnkultur" appearing with "Price on request" and no usable score.

This spec covers **dashboard-only changes** — no Python scraper changes needed.

## Architecture

```
MongoDB (price_total: null, area_m2: 83)
    → API route (imputes: 83 × PRICE_PER_SQM, sets price_is_estimated: true)
    → API response { price_total: 581000, price_is_estimated: true }
    → ListingCard / MapView popup (renders "~€581,000")
```

Price imputation uses `area_m2 × PRICE_PER_SQM` from `config.json`. The `price_is_estimated` flag flows through the API so UI components know to prefix with `~`.

## Data Model

### Module: types.ts
- **Interface:** Add `price_is_estimated?: boolean` to `ListingBase` and `MapListing`
- **Dependencies:** None
- **Size target:** 2 fields added, trivial change

### Module: config.json
- **Responsibility:** Store the price-per-sqm constant for dashboard use
- **Interface:** `{ "PRICE_PER_SQM": 7000 }`
- **Dependencies:** None (local config, not env vars)
- **Size target:** <10 lines

## API Changes

### Module: /api/listings/map/route.ts
- **Responsibility:** Return `price_total` with imputation and `price_is_estimated` flag
- **Interface:**
  - Input: MongoDB document with `price_total` (may be null) and `area_m2` (may be null)
  - Output: `{ ...listing, price_total: number, price_is_estimated: boolean }`
- **Logic:**
  ```typescript
  const PRICE_PER_SQM = config.PRICE_PER_SQM ?? 7000;
  const hasPrice = typeof l.price_total === 'number' && l.price_total > 0;
  const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && l.area_m2 > 0;
  const price_total = hasPrice
    ? l.price_total
    : price_is_estimated
      ? Math.round(l.area_m2 * PRICE_PER_SQM)
      : null;
  ```
- **Dependencies:** `config.json` (PRICE_PER_SQM), MongoDB document fields: `price_total`, `area_m2`
- **Size target:** ~8 lines added

### Module: /api/listings/top/route.ts
- **Responsibility:** Same imputation logic as map route
- **Interface:** Same as above
- **Dependencies:** Same as above
- **Size target:** ~8 lines added

## UI Changes

### Module: ListingCard.tsx
- **Responsibility:** Display estimated price with `~` prefix
- **Interface:**
  - Input: `price_total: number | null`, `price_is_estimated?: boolean`, `area_m2: number | null`
  - Output: Rendered price string
- **Logic:**
  ```
  if price_is_estimated && price_total:
      display "~€{price_total.toLocaleString('de-AT')}"
  else if price_total:
      display "€{price_total.toLocaleString('de-AT')}"
  else if area_m2 == null:
      display "Price on request"
  else:
      (impossible branch — price_is_estimated true implies price_total is set)
  ```
- **Dependencies:** None
- **Size target:** ~4 lines changed

### Module: MapView.tsx (Popup)
- **Responsibility:** Same `~` prefix treatment in map pin popup
- **Interface:** Same as ListingCard
- **Logic:** Same price formatting as ListingCard, applied in the Popup JSX
- **Dependencies:** None
- **Size target:** ~3 lines changed

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `price_total: null`, `area_m2: 83` | Impute €581,000, show `~€581,000` |
| `price_total: null`, `area_m2: null` | No imputation possible, show "Price on request" |
| `price_total: 350000`, `area_m2: 80` | Real price, show `€350,000` (no `~`) |
| `config.json` missing `PRICE_PER_SQM` | Fall back to hardcoded `7000` |
| `price_total: 0` | Treated as missing — imputed if area available |

## Files to Modify

| File | Action |
|------|--------|
| `dashboard/config.json` | Create — add `PRICE_PER_SQM` |
| `dashboard/lib/types.ts` | Modify — add `price_is_estimated?: boolean` |
| `dashboard/app/api/listings/map/route.ts` | Modify — add imputation logic |
| `dashboard/app/api/listings/top/route.ts` | Modify — add imputation logic |
| `dashboard/components/ListingCard.tsx` | Modify — `~` prefix display |
| `dashboard/components/MapView.tsx` | Modify — `~` prefix in popup |

## Verification

- API `/api/listings/map` returns `price_is_estimated: true` for null-price listings with area
- API `/api/listings/top` returns same
- ListingCard shows `~€XXX,XXX` for estimated prices
- MapView popup shows `~€XXX,XXX` for estimated prices
- Listings with neither price nor area still show "Price on request"
- Build succeeds: `npm run build`
