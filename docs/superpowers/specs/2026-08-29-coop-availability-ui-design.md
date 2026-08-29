---
title: Co-op Availability UI Filtering
date: 2026-08-29
status: approved
ui_scope: true
---

# Co-op Availability UI Filtering

## Problem

The co-op pages can render rows whose offer is no longer available. The
dashboard links MyGEWO records to a resolved `builder_url`, but the shared
co-op queries do not exclude records marked `listing_status: "taken"`. The
revalidation job also probes only the stored canonical URL, which can remain
available after the builder offer page returns HTTP 404 or 410.

Taken rows must remain in MongoDB so availability and turnover statistics keep
their history, but they must not appear in active co-op feeds.

## Decisions

| Concern | Decision |
| --- | --- |
| Active UI rows | `/coop` and `/coop/private` exclude `listing_status: "taken"`. Missing or null status remains active for backward compatibility. |
| Availability probe | Revalidation probes `builder_url` when present; otherwise it probes the canonical `url`. |
| State update | When a probe identifies an unavailable offer, mark the canonical stored URL as taken. |
| Data retention | Never delete taken rows. Stats and taken-listings views retain them. |
| Query boundary | Keep the filter in shared query builders so list and co-op map surfaces use the same active definition. |
| Scope | No changes to ordinary listing filters, Telegram delivery, co-op upsert identity, or statistics aggregation. |

## Data Flow

```text
listing_status=taken
        |
        v
shared co-op query -> excluded from /coop and /coop/private (and co-op map)
        |
        +--> retained in listings collection -> stats remain complete

builder_url when present, otherwise url
        |
        v
availability revalidation -> 404/410 or request failure -> mark canonical url taken
```

The revalidation projection will include `builder_url` and continue to pass the
canonical `url` to `mark_listing_taken`. Existing non-co-op records have no
builder URL and therefore keep their current behavior.

## Modules

### `dashboard/lib/coop-query.ts`

Add the active-status predicate to both `coopBaseQuery()` and
`privateCoopQuery()`. Existing URL, Vienna, source, rental, and livable-area
guards remain unchanged.

### `Project/Application/cleanup.py`

Include `builder_url` in the active-listing projection and select it as the
probe target when present. Preserve canonical URL state updates and existing
status/statistics behavior.

### Regression tests

Add a dashboard browser regression that seeds active and taken developer and
private-transfer rows, then asserts taken rows are absent while active rows
remain. Add a cleanup unit regression proving a builder URL is probed while the
canonical URL is the URL marked taken.

## Error Handling

The existing fail-closed revalidation behavior remains: request exceptions are
treated as unavailable, and MongoDB update failures do not delete data. Query
failures continue to render the existing database error state.

## Success Criteria

- Taken developer offers do not render on `/coop`.
- Taken private transfers do not render on `/coop/private`.
- Active co-op rows still render.
- Co-op rows remain available to statistics queries after being marked taken.
- A builder URL returning HTTP 404/410 marks the canonical listing as taken.
- Focused tests and the full dashboard suite pass.
