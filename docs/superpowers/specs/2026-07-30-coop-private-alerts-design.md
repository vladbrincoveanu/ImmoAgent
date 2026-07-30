---
title: Co-op images, private-Ablöse rubric, and alerts dashboard
date: 2026-07-30
status: draft
ui_scope: true
graph_scope: false
test_scope: true
---

# Co-op images, private-Ablöse rubric, and alerts dashboard

Five sub-projects. P0 unblocks everything else; P1 and P2 are independent of each
other; P3 and P4 depend on P2 landing first.

## Verified starting state

Every claim below was checked against running code or the live deployment on
`main` (`a60bf57`), not inferred:

| Claim | Evidence |
|---|---|
| Co-op thumbnails render the placeholder for every row | Live `/coop` HTML contains **zero** `<img>` tags; `CoopThumb` emits `<img>` only when `src` is non-null |
| Photo probing already runs, and has already concluded | `run_coop.py` fetches the **mygewo** offer page and stores `_og_image(html)`; `""` is a deliberate terminal "nothing there" marker |
| `builder_url` resolution works | Live `/coop` links out to `gesiba.at`, `oesw.at`, `nhg.at`, `frieden.at`, `lebenswert-wohnen.at` |
| Telegram co-op alerts are dead | `TELEGRAM_COOP_CHANNEL_ID` is absent from `gh secret list`; the workflow warns non-fatally and continues |
| The co-op poll never touches Willhaben | `run_coop.py` imports `genossenschaft_scraper` only |
| Willhaben co-op detection already exists | `willhaben_scraper.py:492` sets `is_genossenschaft` via `extract_is_genossenschaft` |
| Alert infrastructure already exists | `saved_searches` collection, `/api/saved-searches` + `alert/` + `confirm/` routes, cookie user-id, `isPro` |

### Builder-page photo probe (measured 2026-07-30)

| Builder | `og:image` | `<img>` count |
|---|---|---|
| `lebenswert-wohnen.at` | yes (justimmo CDN) | 15 |
| `frieden.at` | yes (portego) | 9 |
| `gesiba.at` | **no** | 4 |
| `nhg.at` | **no** | 6 |

`og:image` alone covers roughly half the builders. A fallback that picks a
plausible `<img>` is required, or half the inventory keeps the placeholder.

## Decisions taken

| Decision | Choice |
|---|---|
| Rubric definition | Weitergabe/Ablöse only — private tenant passing on an existing co-op flat |
| Alerts model | Extend `saved_searches`; do not build a parallel model |
| Photo source | Second hop: `builder_url` → fetch → `og:image`, with `<img>` fallback |
| Poll cadence | Poll-window loop, **interval < 5 min**, window 06:00–17:00 Vienna |
| Telegram routing | New dedicated channel for private-Ablöse, separate from the mygewo feed |

## P0 — Telegram plumbing

Root cause of "no separate address for Telegram": the secret was never created.
The workflow's own warning text says alerts are disabled while scraping
continues, which is why runs are green and silent.

Two channels:

- `TELEGRAM_COOP_CHANNEL_ID` — existing mygewo feed (currently dead)
- `TELEGRAM_PRIVATE_COOP_CHANNEL_ID` — new Ablöse feed

**Manual step, owner-only:** create both Telegram channels, add the bot as
admin, and add both secrets under Settings → Secrets. This cannot be automated
from here.

Code change: wire `TELEGRAM_PRIVATE_COOP_CHANNEL_ID` into the workflow `env`,
and make a missing channel loud at startup — logged once per run with an
explicit "alerts DISABLED" line — rather than a warning that scrolls past.

### Module: `coop_alert_router`
- **Responsibility:** Pick the destination channel for one co-op listing based on its `coop_kind`.
- **Interface:** `route(listing) -> Optional[str]` (chat id, or None when that channel's secret is unset)
- **Dependencies:** env vars only
- **Size target:** ~40 lines

## P1 — Co-op images: second hop

`resolve_offer_details()` reads `og:image` from the mygewo offer page, which does
not carry unit photos. Every unit has therefore already been probed, stored `""`,
and is terminal. Two changes are needed: a new resolver, and a one-off reset of
the poisoned values.

### Module: `coop_image_resolver`
- **Responsibility:** Given a builder page URL, return an absolute unit-photo URL.
- **Interface:** `resolve_builder_image(builder_url) -> Optional[str]`
- **Dependencies:** `fetch()`, `_og_image()`, existing absolute-URL helper, `BeautifulSoup`
- **Size target:** ~90 lines

Resolution order:

1. `og:image` / `twitter:image` on the builder page.
2. Fallback: first `<img>` whose `src` does not match a logo/icon/sprite/svg
   pattern and whose path segment count suggests a content image. Reject
   anything under `/logo`, `/icon`, `/static/ui`, or ending `.svg`.
3. `None` if neither yields a candidate.

### Re-probe safety

`""` is currently terminal, which is correct behaviour for the old probe and
wrong for the new one. Add `image_probe_v: int` to the co-op document:

- Units with `image_probe_v` absent or `< 2` are eligible for exactly one
  re-probe under the new resolver.
- After the re-probe, set `image_probe_v = 2` regardless of outcome.
- `""` remains terminal *within* a version.

This makes the reset idempotent and bounded. Without the version marker, a reset
of `"" → None` would re-probe forever for every builder that genuinely has no
photo.

Reuses `MAX_DETAIL_FETCHES_PER_RUN = 40`, so a cold start settles over several
runs rather than hammering ~30 Bauträger domains at once.

No UI change: `CoopThumb` already swaps in the placeholder on 403/hotlink
failure, which is the expected outcome for some builder CDNs.

## P2 — Willhaben private-Ablöse crawler

The actual new feature. Willhaben is currently scraped only by the daily
`scrapeJob.yml`, never by the co-op poll.

### Module: `willhaben_private_coop`
- **Responsibility:** Poll Willhaben Wien rentals newest-first and keep private co-op transfer ads.
- **Interface:** `scrape_private_coop(max_pages: int) -> List[Listing]`, each with `coop_kind="private_transfer"`
- **Dependencies:** `willhaben_scraper` fetch primitives, `field_extractors.extract_is_genossenschaft`
- **Size target:** ~180 lines

Matching runs over title **and** description **and** full body text:
`Ablöse`, `Weitergabe`, `Nachmieter`, `Genossenschaftswohnung`, `Genossenschaft
abzugeben`. A hit on any field qualifies.

Wired into `run_coop.py` as a second adapter, so it inherits the existing poll
loop, `url_hash` dedup, and the `sent_to_telegram` re-send guard for free.

### Cadence

Per the owner's instruction: faster than 5 minutes, restricted to 06:00–17:00
Vienna.

- `POLL_INTERVAL_SECONDS: 120`
- Cron `*/15 4-15 * * 1-6` — GitHub cron is UTC, and Vienna is UTC+2 in summer,
  so `4-15` UTC is 06:00–17:00 local. **This drifts to 05:00–16:00 local in
  winter**; if that matters, the window needs a seasonal adjustment or an
  external scheduler.
- Poll window stays 55 min, giving ~27 polls per delivered run instead of ~11.

## P3 — `/coop/private` page and free-text search

Separate rubric page, per the owner's request. A keyword box queries title,
description, and body. Reuses the `/coop` filter-form pattern and the existing
`coop-filter` test ids.

Free-text needs a MongoDB text index on the co-op collection, or the query
degrades to an unindexed regex scan as the private-ad volume grows.

### Module: `coop_private_query`
- **Responsibility:** Turn the page's filter + keyword params into one co-op query and return matching rows.
- **Interface:** `queryPrivateCoop(params) -> { rows, total }`
- **Dependencies:** `lib/mongodb`, the co-op text index
- **Size target:** ~120 lines

### Module: `CoopPrivatePage`
- **Responsibility:** Render the private-Ablöse rubric — keyword box, filters, result rows.
- **Interface:** Next.js route `/coop/private`; consumes `coop_private_query`
- **Dependencies:** `coop_private_query`, `CoopThumb`, existing `/coop` filter-form components
- **Size target:** ~200 lines — decompose the filter form into its own component if it grows past that

`ui_scope: true` — goes through `frontend-design`, then Playwright DOM
assertions on the real rendered elements per cycle.

## P4 — Alerts dashboard

Extends `saved_searches` rather than duplicating it:

- `kind: 'listing' | 'coop_private'`
- `channels: { telegram_chat_id?: string, email?: string }`

The matcher runs inside the co-op poll: after each poll, new `coop_private`
listings are tested against every stored alert, and hits are delivered.

Email reuses the existing `confirm/` double-opt-in route. **Gap:** the co-op
workflow does not currently pass `SMTP_USER` / `SMTP_PASSWORD`, so email
delivery requires adding those to `coop-fast-poll.yml` env.

### Module: `alert_matcher`
- **Responsibility:** Test newly-seen private-coop listings against every stored alert and return the (alert, listing) pairs to deliver.
- **Interface:** `match(listings, alerts) -> List[(alert, listing)]`
- **Dependencies:** `mongodb_handler` (via existing methods only), the keyword matcher from P2
- **Size target:** ~110 lines

### Module: `alert_dispatcher`
- **Responsibility:** Deliver one matched pair to that alert's configured channels, recording delivery so nothing sends twice.
- **Interface:** `dispatch(alert, listing) -> DeliveryResult`
- **Dependencies:** `telegram_bot`, `outreach/email_sender`, `mongodb_handler`
- **Size target:** ~130 lines

### Module: `AlertsDashboardPage`
- **Responsibility:** CRUD UI for alerts — name, keyword, channel selection, verification state.
- **Interface:** Next.js route; consumes `/api/saved-searches` and `alert/` + `confirm/`
- **Dependencies:** existing saved-search API routes, `isPro` / `FREE_SAVED_SEARCH_LIMIT`
- **Size target:** ~220 lines — split the alert-row editor out if it grows past that

## Testing

Per project rule, every cycle ends with real-DOM verification, not screenshots
and not "it compiles".

- P1: unit tests for `resolve_builder_image` against saved HTML fixtures from all
  four measured builders — two with `og:image`, two without, proving the
  fallback path.
- P2: fixture-based tests for the keyword matcher, including the false-positive
  case below.
- P3: Playwright assertions on real selectors and text in `dashboard/tests/`.
- P4: matcher unit tests plus a delivery test with the sender stubbed.

## Risks

1. **First-come-first-served may be unwinnable regardless of cadence.** Ablöse
   ads draw replies within minutes. A 2-minute poll narrows the gap; it does not
   guarantee being first. The `repository_dispatch` hook stays wired for a real
   external scheduler later.
2. **Willhaben rate limiting.** Polling every 2 minutes for 11 hours a day is far
   heavier than the current daily job — roughly 330 polls/day against a source
   that today sees one. This is the single most likely thing to break, and it can
   fail as a silent block rather than an error. Reuse existing headers and
   backoff, cap pages per poll, and log HTTP status distribution so a block is
   visible.
3. **Keyword false positives.** "Ablöse" routinely refers to kitchen or furniture
   buyouts in ordinary rentals with no co-op involved. Expect noise in v1; the
   rubric page makes it filterable, and the fixture tests pin the known case.
4. **Winter time drift** on the UTC cron window, noted in P2.
5. **P0 is owner-blocked.** Nothing in P2/P4 delivers a notification until the
   two Telegram secrets exist.

## Sequencing

```
P0 (config, owner-blocked)
 ├─ P1 (images)          ← independent, ships anytime
 └─ P2 (Willhaben crawler)
     ├─ P3 (rubric page + search)
     └─ P4 (alerts dashboard)
```
