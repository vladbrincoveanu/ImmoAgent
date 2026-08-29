---
title: Co-op Telegram New-Only Size Filter
date: 2026-08-19
status: draft
ui_scope: false
graph_scope: false
test_scope: true
---

# Co-op Telegram New-Only Size Filter

## Problem

The co-op source feed currently iterates the full adapter inventory after every
poll. It relies on a non-atomic legacy `sent_to_telegram` check and the tracked
co-op alert configuration has no minimum size or room constraints. This allows
old inventory, repeated deliveries, one-room units, and units below 75 m² into
the source Telegram channels.

The screenshot feed is the target. User-created alert deliveries and the
Vienna buyer/property feed are separate products and remain unchanged.

## Decisions

| Concern | Decision |
| --- | --- |
| Scope | Source co-op Telegram feeds only: main co-op feed and private co-op feed. |
| Newness | Only URLs absent before the current poll may enter source-channel delivery. Existing unsent inventory is not backfilled. |
| Identity | A URL is sent at most once, even if scraped details later change. Existing cross-source unit migration remains responsible for preserving state. |
| Area | Known finite `area_m2 >= 75.0`, inclusive. Missing, non-numeric, non-finite, or smaller values fail. |
| Rooms | Known finite `rooms >= 3.0`, inclusive. Missing, non-numeric, non-finite, or smaller values fail. |
| URL | Existing `validate_url()` runs before any Telegram call. Invalid URLs are marked and skipped. |
| Claim order | MongoDB atomically claims before Telegram is called. A listing that cannot be claimed is never sent. |
| Ambiguous send | After a Telegram attempt, failure to confirm durable state becomes terminal `uncertain`; it is never automatically retried. This favors no duplicate over recovering a possibly missed message. |
| Existing user alerts | `deliver_user_alerts()` and its configured alert filters are unchanged. |
| Vienna buyer feed | `send_vienna_listings()` and its permanent Vienna route remain unchanged. |
| Batch report | `run_top5.py` remains unchanged. |
| MongoDB failure | Candidate lookup or claim uncertainty fails closed for source-channel delivery. |

Distinct new URLs remain distinct candidates. The change suppresses repeated
occurrences of one listing URL; it does not collapse every unit in one builder
project into one message.

## Data Flow

```text
adapter inventory
      |
      v
batch URL lookup before upsert
      | existing/error -> exclude from source feed
      v
new candidate set
      |
      v
area >= 75 + rooms >= 3 + valid URL
      | fail -> skip, no Telegram call
      v
atomic claim(route=coop or private_coop)
      | no claim -> skip, no Telegram call
      v
Telegram send
      | confirmed success -> state=sent
      | any unconfirmed outcome -> state=uncertain (terminal)
```

The fast poll uses its existing batch lookup and `new_alert_candidates()` as the
source-candidate boundary. The main crawl performs an equivalent batch URL
lookup before saving its co-op candidates. Both paths call the same policy and
atomic delivery helper.

## Delivery State Contract

The existing route ledger is extended with stable source-feed routes:

```json
{
  "telegram_delivery": {
    "coop": {"state": "claimed | sent | uncertain"},
    "private_coop": {"state": "claimed | sent | uncertain"}
  }
}
```

The claim query is URL-scoped for this behavior. It excludes `sent`,
`uncertain`, and already `claimed` records. Source-feed claims do not expire:
an orphaned `claimed` record is manually reconciled rather than automatically
retried. A claim is written before the external Telegram call. A successful
call is marked `sent`; an exception, false result, or marker failure is
quarantined as `uncertain`, so a later poll cannot send a possible duplicate.
Listing replacement continues to preserve route state and legacy send markers.

## Modules

### Module: `Application.telegram_delivery`
- **Responsibility:** Own strict co-op source policy and pre-send claim/send/terminal-state orchestration.
- **Interface:** Listing + route + TelegramBot-compatible sender + MongoDBHandler -> boolean delivery result.
- **Dependencies:** `validate_url`, `format_coop_message`, MongoDB route-state methods.
- **Size target:** 260 lines max; policy and delivery helpers remain small and testable.

### Module: `Integration.mongodb_handler.MongoDBHandler`
- **Responsibility:** Provide atomic route claims and durable `sent`/`uncertain` transitions for source feeds.
- **Interface:** URL + route + claim token -> boolean state transition.
- **Dependencies:** MongoDB listings collection and existing Vienna delivery methods.
- **Size target:** 80 changed lines max; no raw queries outside the handler.

### Module: `run_coop.py`
- **Responsibility:** Restrict fast-poll source-channel delivery to new, qualifying candidates while preserving user alerts and upserts.
- **Interface:** Adapter results + pre-upsert URL map -> source feed delivery candidates.
- **Dependencies:** `new_alert_candidates`, shared co-op delivery helper, existing channel router.
- **Size target:** 45 changed lines max; no unrelated poll refactor.

### Module: `Application.main`
- **Responsibility:** Restrict daily-crawl co-op delivery to URLs absent before that crawl and route through shared delivery state.
- **Interface:** Scraped listings + MongoDB handler + configured co-op bot -> source-channel sends.
- **Dependencies:** batch URL lookup, shared co-op policy/delivery helper, existing score/storage flow.
- **Size target:** 55 changed lines max; Vienna property flow remains separate.

### Module: Regression tests
- **Responsibility:** Prove new-only selection, hard boundaries, pre-send ordering, atomic duplicate suppression, and terminal uncertainty.
- **Interface:** pytest/unittest fixtures with mocked MongoDB, URL validation, and Telegram sender -> deterministic assertions.
- **Dependencies:** shared helper, `run_coop`, `main`, MongoDB handler methods.
- **Size target:** 300 lines max for focused additions; no live services or secrets.

## Test Scope

Tests must prove before production implementation:

- `74.99` m² and `2.99` rooms are rejected; `75.0` m² and `3.0` rooms pass.
- Missing, string, boolean, NaN, and infinite area/room values are rejected.
- Existing URL lookup excludes old inventory, including existing rows with no send marker.
- Batch lookup failure produces no source-channel candidates.
- URL validation occurs before Mongo claim and Telegram send.
- A sent URL is skipped before `send_message()` is called.
- Atomic claim winner sends once; a second claim, including after a process
  crash or stale claim, does not call Telegram.
- Telegram false/exception or marker failure becomes terminal `uncertain` and is not retried.
- User-created alert matching and Vienna property delivery remain unchanged.

## Non-Goals

- No Telegram history/API synchronization.
- No change to scraper search URLs or MongoDB storage eligibility.
- No change to user-created alert thresholds or destinations.
- No change to Vienna property thresholds, score behavior, or destination.
- No change to co-op message formatting or channel routing.
- No project-level grouping of distinct new URLs.

## Success Criteria

- Screenshot-style one-room and sub-75 m² units never reach source co-op Telegram.
- Existing co-op inventory is not emitted as a rollout backfill.
- One listing URL causes at most one source-channel Telegram attempt after rollout.
- Duplicate checks and claims occur before Telegram send.
- Ambiguous delivery states never trigger automatic duplicate sends.
- Focused and full regression tests pass; graph is updated after implementation.
