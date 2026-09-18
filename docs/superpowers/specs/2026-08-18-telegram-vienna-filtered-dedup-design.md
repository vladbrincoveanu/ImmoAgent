---
title: Vienna Telegram Filtered Feed and Permanent Deduplication
date: 2026-08-18
status: approved
ui_scope: false
graph_scope: false
test_scope: true
---

# Vienna Telegram Filtered Feed and Permanent Deduplication

## Problem

The crawler currently initializes property notifications from
`telegram_main`, although the repository already supports a separate
`telegram_vienna` destination. The crawler's source criteria are broad enough
to admit listings below the intended Vienna-channel threshold, and the
existing seven-day check is not durable: `save_listings_to_mongodb()` can
replace a document and erase its Telegram send markers. A later crawl can
therefore repost a listing.

The requested behavior is a quiet, high-signal Vienna feed:

- Crawl and store valid listings broadly.
- Send property posts only to the explicitly configured `telegram_vienna`
  destination during the main crawl.
- Require known `area_m2 >= 75`, known `rooms >= 3`, existing configured score
  threshold, and a valid URL.
- Suppress the same listing permanently after a successful Vienna delivery.
- Send no crawl summary or no-result notice to the Vienna feed.
- Start deduplication at rollout; do not attempt historical Telegram sync.

## Decisions

| Concern | Decision |
| --- | --- |
| Filter scope | Vienna delivery gate only; do not narrow scraping or database storage. |
| Area | Minimum 75 m², inclusive. Missing, non-numeric, non-finite, or smaller values fail. |
| Rooms | Minimum 3 rooms, inclusive. Missing, non-numeric, non-finite, or smaller values fail. |
| Importance | Reuse existing `telegram.min_score_threshold`; retain current strict `score > threshold` behavior. |
| Destination | Explicit `telegram_vienna` only. No fallback to `telegram_main`. |
| Property routing | Main crawl property notifications go to Vienna feed only. Existing co-op routing remains separate. |
| Batch report | `run_top5.py` remains unchanged; it is a separate deliberate batch report. |
| Non-listing messages | No summary or no-result message is sent by this crawl to the Vienna feed. |
| URL validation | Run existing `validate_url()` immediately before delivery; invalid URLs are marked and skipped. |
| Dedup window | Permanent for the Vienna route after rollout. |
| Dedup identity | Existing Mongo listing URL or content fingerprint. Same-run candidates are also collapsed by URL/fingerprint. |
| History | No Telegram history reader. Bot API cannot fetch old channel posts; old posts are outside rollout scope. |
| MongoDB failure | Fail closed: no durable unsent claim means no Telegram send. |

## Data Flow

```text
source scrapers
      |
      v
listing validation -> MongoDB save (preserve delivery state)
      |
      v
score all listings
      |
      v
Vienna policy: score + known area >=75 + known rooms >=3
      |
      v
URL validation
      |
      v
atomic MongoDB claim for route=vienna
      | no claim -> skip
      v
TelegramBot.send_property_notification()
      | failure -> release claim
      | success -> mark route permanently sent
```

## Delivery State Contract

Each listing may carry a route-specific state document:

```json
{
  "telegram_delivery": {
    "vienna": {
      "state": "claimed | sent | uncertain",
      "claim_until": 1755520000.0,
      "claimed_at": 1755519700.0,
      "sent_at": 1755519705.0
    }
  }
}
```

Rules:

1. `claim_listing_delivery(url, content_fingerprint, "vienna")` performs one
   atomic `find_one_and_update()` over either the URL or content fingerprint.
   It succeeds only when no permanent `sent` or `uncertain` state exists and
   no active claim exists. A short lease prevents concurrent crawls from
   sending simultaneously.
2. A successful Telegram call is followed by
   `mark_listing_delivery_sent()`, which sets route state to `sent`, removes
   the lease, and preserves the legacy `sent_to_telegram` and
   `sent_to_telegram_at` fields used by existing reports.
3. A failed Telegram call releases the claim, allowing a later crawl to retry.
4. If Telegram confirms success but the marker update fails, the claim is not
   released automatically. The delivery is logged as uncertain and requires
   the state update to be retried/reconciled rather than risking an immediate
   duplicate.
5. Listing replacement/upsert paths preserve `telegram_delivery`,
   `sent_to_telegram`, `sent_to_telegram_at`, and `url_is_valid` from the
   existing document.

The external Telegram call and MongoDB update cannot form one transaction.
The claim lease prevents normal concurrent duplicates; the uncertain state
policy favors no duplicate over automatic retry when post-send persistence is
not confirmed.

## Modules

### Module: `Application/telegram_delivery.py`
- **Responsibility:** Apply Vienna-channel eligibility, same-run deduplication, URL validation, claim/send/mark orchestration.
- **Interface:** Listing objects or dictionaries plus a Telegram bot and MongoDB handler -> sent count and structured logging.
- **Dependencies:** `listing_validator`, `TelegramBot`-compatible sender, `MongoDBHandler` delivery methods.
- **Size target:** 180 lines max; pure policy helpers separated from delivery side effects.

### Module: `Integration.mongodb_handler.MongoDBHandler` delivery methods
- **Responsibility:** Provide atomic, route-specific listing delivery claims and durable send-state transitions.
- **Interface:** URL + content fingerprint + route -> claim/release/mark/quarantine booleans.
- **Dependencies:** MongoDB listings collection and existing PyMongo error handling.
- **Size target:** 120 new lines max; reuse existing alert-delivery atomic update patterns.

### Module: `Application.main` Telegram orchestration
- **Responsibility:** Initialize explicit Vienna and existing co-op bots, score listings, persist listings, and invoke the Vienna delivery module without summaries.
- **Interface:** CLI `--send-to-telegram`, loaded config, scraped listings, MongoDB handler.
- **Dependencies:** `telegram_delivery`, `TelegramBot`, existing scoring, co-op routing, URL validation.
- **Size target:** 60 changed/new lines in the dispatch path; no unrelated refactor.

### Module: Telegram configuration and setup helpers
- **Responsibility:** Preserve explicit Vienna credentials and prevent accidental fallback to the main destination.
- **Interface:** Config file/environment variables -> `telegram_vienna` credentials or an unavailable destination.
- **Dependencies:** `load_config()`, `TELEGRAM_BOT_VIENNA_TOKEN`, `TELEGRAM_BOT_VIENNA_CHAT_ID`, setup/README documentation.
- **Size target:** 35 changed lines total across config/setup/docs.

### Module: Regression test suite
- **Responsibility:** Verify filter boundaries, routing, state transitions, replacement preservation, and failure behavior without live Telegram/MongoDB.
- **Interface:** pytest/unittest fixtures and mocks -> deterministic assertions.
- **Dependencies:** delivery policy, MongoDB handler methods, existing test conventions.
- **Size target:** 250 lines max for focused tests; no live credentials or network calls.

## Implementation Details

### Configuration

- Read `telegram.telegram_vienna` after environment supplementation.
- Environment variables override config values using the existing names
  `TELEGRAM_BOT_VIENNA_TOKEN` and `TELEGRAM_BOT_VIENNA_CHAT_ID`.
- A missing or incomplete Vienna destination disables Vienna delivery and logs
  a warning. It must not fall back to main credentials.
- The no-config fallback in `load_config()` must not manufacture Vienna
  credentials from main credentials. The setup helper must write the channel
  under `telegram_vienna`, and README wording must no longer claim an implicit
  main-channel fallback.

### Main crawl

- Remove the current seven-day raw `collection.find_one()` cooldown from the
  scoring loop. Scores still calculate and listings still save on every crawl.
- Keep co-op candidates on their existing dedicated route and out of the
  Vienna property candidate list.
- After the save completes, pass scored non-co-op candidates to the Vienna
  delivery module. It applies the hard filter, validates URLs, claims state,
  sends, and records state.
- Do not call the old main property sender, summary sender, or no-result sender
  from this crawl path.

### URL/content identity

- Use the existing `compute_content_fingerprint()` for cross-URL same-content
  detection within the current source model.
- A candidate with no URL cannot be sent and cannot be claimed.
- Same-run dedup treats either a repeated URL or repeated content fingerprint
  as the same delivery candidate.

### Logging

Log explicit reasons for skipped candidates: missing/invalid filter data, low
score, co-op routing, invalid URL, already sent, active claim, unavailable
destination, MongoDB claim failure, Telegram failure, and uncertain marker.
Logs must not include bot tokens or full credential values.

## Test Scope

Focused tests must prove:

- `74.99` m² rejects; `75` m² accepts; `3` rooms accepts; `2.99` rooms rejects.
- Missing, string-invalid, NaN, and infinite area/rooms reject.
- Score at threshold rejects and score above threshold passes.
- URL validation is called before sender invocation; invalid URLs are marked and
  never sent.
- A listing is sent only to the Vienna bot; main property sender and summary /
  no-result sender are not called.
- Missing `telegram_vienna` credentials never routes to main.
- Two same-run candidates sharing URL or content fingerprint produce one send.
- Atomic claim allows one winner, blocks `sent` and `uncertain` states, and
  permits an expired claim to retry.
- Failed Telegram send releases its claim; successful send marks route state
  and legacy fields; marker failure leaves the claim non-retryable/uncertain.
- Listing replacement preserves all delivery markers.
- Existing co-op delivery behavior and `run_top5.py` remain unaffected.

Verification commands:

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter-telegram-dedup
pytest -q tests/test_telegram_vienna_delivery.py
cd Project && python -m unittest discover -s ../tests -p 'test_*.py'
graphify update .
```

No live Telegram API, MongoDB production database, or secret-bearing config is
used by tests.

## Non-Goals

- Reading or importing historical Telegram channel messages.
- Changing scraper search URLs or global crawl criteria.
- Changing the Telegram message format.
- Changing co-op channel routing.
- Changing the Top-5 batch report destination or resend semantics.
- Adding a new score threshold or user-facing CLI flag.

## Success Criteria

- Main crawl sends only qualifying property listings to explicit
  `telegram_vienna`.
- No Vienna summary/no-result messages are emitted.
- Same URL/content listing is permanently suppressed after successful rollout
  delivery.
- Listing refreshes cannot erase delivery state.
- MongoDB or configuration uncertainty fails closed.
- Focused and full regression tests pass, and graph is updated after code
  changes.
