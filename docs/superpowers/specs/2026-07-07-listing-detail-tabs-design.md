---
title: Tabbed listing detail panel
date: 2026-07-07
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Tabbed listing detail panel

## Problem
`dashboard/components/ListingDetail.tsx` renders ~15 sections in one 90vh scroll
(image, title, facts, location, bank financing, investment metrics, district
trend, estimated financing, infrastructure, score breakdown, zone analytics,
actions, commute+rent, comparables). Data is good but the single stack is
overwhelming. Split into tabs.

## Decision
Tabs (user-chosen over accordion / progressive disclosure). Pure presentational
reorg — no API, data model, or scoring change. Existing rendered blocks move into
tab panels.

## Layout
- **Sticky summary header** (all tabs): `ScoreBadge`, title (1-line truncate),
  key chips (price · area · district · U-Bahn min), market badges, close button.
  Compact — no big image pinned.
- **Sticky tab bar** under header.
- **Scroll area**: active panel only.
- **Sticky action footer** (all tabs): `Open Original` CTA + `Recheck
  Availability` + availability pill.

## Tabs (auto-hidden when no data; Overview always on, default)
| Tab | Contents | Show when |
|-----|----------|-----------|
| Overview | image, full facts grid, `AddressBlock`, Infrastructure | always |
| Financing | `BankFinancingPanel` + estimated-financing block | `price_total` |
| Investment | `InvestmentMetricsPanel` + `CommuteAndRentPanel` | `price_total && area_m2` |
| Area & Market | `DistrictTrendChart`, Zone Analytics, Comparables, Score Breakdown | `bezirk` |

Gates derive from stable `listing` fields (not async fetches) → no tab flicker.
Async blocks (zoneStats, comparables) appear inside Area tab as they load.

## Module: ListingDetail (tabbed)
- **Responsibility:** render one listing's full detail in a tabbed modal.
- **Interface:** props `{ id, onClose }`; fetches `/api/listings/:id`,
  `/zone-stats`, `/comparables` (unchanged).
- **Dependencies:** ScoreBadge, AddressBlock, BankFinancingPanel,
  InvestmentMetricsPanel, DistrictTrendChart, CommuteAndRentPanel, MarketBadges.
- **State:** `tab: 'overview'|'financing'|'investment'|'area'` (reset to
  `overview` on `id` change).
- **Size target:** ~470 lines (single file; sections already componentised).

## Test hooks
`data-testid` on each tab button (`tab-overview`…) + panel (`panel-financing`…);
preserve `comparables-section`. New spec `dashboard/tests/listing-detail-tabs.spec.ts`
asserts: Overview default active, tab switch reveals correct panel, empty tabs
hidden, summary header persists across tabs, action footer always present.

## Risks handled
- Sparse data → empty tabs hidden via stable-field gates.
- Context loss → summary header + action footer pinned.
- Regression → test hooks preserved; new Playwright spec; verify vs live prod.
