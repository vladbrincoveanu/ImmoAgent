---
title: Coop photos on /coop + coop pins on the map
date: 2026-07-28
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Coop photos + map pins

Two defects, one branch.

## Problem

1. `/coop` rows render no image; every other listing surface (`ListingCard`) has one.
2. `/dashboard/map?genossenschaft=true` shows (near) zero pins even though every mygewo
   unit already carries an exact lat/lon.

Root cause of (2): `app/api/listings/map/route.ts` gates every row on
`price_total / area_m2 >= 2500` — a *purchase* €/m² floor. Coop rows store the
**monthly rent** in `price_total` (€700 / 60 m² ≈ €12/m²), so all of them fail.
Coordinates are fine: `genossenschaft_scraper.py` decodes mygewo's EWKB point and
stamps `coordinate_source: "exact"`.

Root cause of (1): the scraper extracts no image field at all.

## Module: coop image capture (scraper)

- **Responsibility:** give each mygewo rental an `image_url`.
- **Interface:** in → mygewo unit dicts / offer pages; out → `Listing.image_url`.
- **Dependencies:** `genossenschaft_scraper.py`, existing HTTP session + rate limit.
- **Size target:** ~60 added lines.

Three tiers, first hit wins:

- **T1 (free):** regex the unit literal for an image key (`image:`, `photo:`,
  `images:[`). Implementation step 0 is a live probe of the payload to learn whether
  such a key exists — this is unverified (a sandbox rule blocked the probe during design).
- **T2 (bounded fetch):** no field → one GET of the unit's `/angebot/<uuid>` page,
  read `og:image`. **Only** for units not already stored with an `image_url`, capped at
  40 fetches per poll, 1 req/s. Without that guard the 5-minute poller would re-fetch
  the whole inventory every cycle.
- **T3:** nothing found → `image_url = None`; the UI renders a placeholder.

`Listing.image_url` already exists (`Project/Domain/listing.py:40`) — no schema change.
Existing rows backfill as they are re-polled.

## Module: `CoopThumb.tsx`

- **Responsibility:** render one coop thumbnail, degrade to a placeholder.
- **Interface:** `{ src: string | null, bezirk: string | null }` → 96×72 rounded `<img>`;
  null `src` or `onError` → neutral tile with 🏘️ + district.
- **Dependencies:** none.
- **Size target:** ~40 lines.

Plain `<img>`, not `next/image`: builder image domains are arbitrary and would each need
a `next.config` remote-pattern entry. `ListingCard.tsx:43` makes the same call.
Client component because `/coop` is a Server Component and `onError` needs a client boundary.

## Module: `/coop` row layout

- **Responsibility:** place the thumb without disturbing the filter panel.
- **Interface:** `CoopRow` gains `image_url`; new testids `coop-thumb`, `coop-thumb-fallback`.
- **Dependencies:** `CoopThumb`.
- **Size target:** existing file, ~15 changed lines.

Thumb left, current text block right, flex row. Filters, query logic and all existing
testids unchanged.

## Module: `lib/coop-query.ts`

- **Responsibility:** single source of truth for "what counts as a listable coop rental".
- **Interface:** exports the base Mongo filter document.
- **Dependencies:** none.
- **Size target:** ~25 lines.

Extracted from `app/coop/page.tsx`'s `BASE_QUERY`; imported by both the page and the map
route so the two surfaces cannot drift.

## Module: map coop exemption

- **Responsibility:** let coop rentals reach the map with rent-appropriate gates.
- **Interface:** `/api/listings/map?genossenschaft=true`.
- **Dependencies:** `lib/coop-query.ts`.
- **Size target:** existing file, ~25 changed lines.

- `genossenschaft=true` → use the coop query, **drop the €/m² gates**, default sort to
  newest (coop rows have no score).
- `genossenschaft` unset → add an explicit `is_genossenschaft: { $ne: true }`, so rentals
  never leak into the purchase map once the €/m² gate stops excluding them by accident.
- `minScore` needs no change: `route.ts` already lets `score == null` through.
- Pin label: coop pin styling already exists (`MapView.tsx:32-35`, 🏘️ + its own colour).
  Only change `€700` → `€700/Mt` so rent does not read as a purchase price. `SelectedCard`
  labels the figure "Miete".

## Out of scope (flagged, not fixed)

- `/api/listings/top` carries the same purchase-€/m² trap.
- Mirroring hotlinked builder images to MinIO. Hotlink 403s are absorbed by the
  `CoopThumb` fallback.

## Testing

- Python: image extraction asserted against a saved mygewo fixture.
- Playwright DOM assertions (per `.claude/rules/ui-testing.md`):
  - `coop.spec.ts` — thumb renders; fallback renders when `image_url` is null.
  - `map-genossenschaft.spec.ts` — pin count > 0 at `?genossenschaft=true`; label contains `/Mt`.
- The suite has 92 pre-existing failures on `main` (a `layers-btn` cluster). Gate is:
  new specs pass, and no *new* failures versus the `main` baseline.
