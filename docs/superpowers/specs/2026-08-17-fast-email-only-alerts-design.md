---
title: Fast email-only keyword alerts
date: 2026-08-17
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# Fast Email-Only Keyword Alerts

## Goal

Make a dashboard alert usable with a confirmed email and no Telegram chat ID,
while keeping notification latency as the primary constraint. The alert must be
created, confirmed, tested, matched, delivered, and retried through email alone.
New Genossenschaft listings from the mygewo feed must be eligible for the same
criteria as new Willhaben listings.

## Latency Contract

cron-job.org is the external trigger and is configured for one request per
minute. It sends a `repository_dispatch` event to the repository workflow. A
dispatched workflow performs one poll, rather than opening a polling window.

This minimizes trigger delay, but GitHub runner pickup, checkout, dependency
setup, scraping, and SMTP delivery remain on the critical path. The honest
end-to-end target is approximately 2-3 minutes from source visibility to
notification. Sub-minute delivery is out of scope until the poller runs on a
persistent worker outside GitHub Actions.

## Scope

In scope:

- Email-only alert verification from the dashboard.
- Email-only delivery from the Python poller.
- Durable retry of failed or interrupted email delivery.
- Independent delivery state for Telegram and email on a combined alert.
- Matching newly discovered mygewo listings as well as new Willhaben listings.
- Dispatching user alerts before upserting listings, so a canceled one-shot run
  cannot turn a fresh listing into an unmatchable existing row.
- cron-job.org and workflow documentation for the one-minute trigger.
- Tests for route behavior, DOM behavior, matching, dispatch, retry, and poll
  candidate collection.

Out of scope:

- A new email provider or digest scheduling.
- Alert editing or unsubscribe management.
- A persistent worker deployment.
- Changing the existing email confirmation consent model.
- Sending unconfirmed email addresses.

## Existing Behavior and Gaps

1. The alert creation API already accepts an email without Telegram and requires
   at least one valid destination.
2. The poller already matches confirmed email-only alerts and calls the Python
   SMTP sender.
3. The dashboard test route rejects an email-only alert with
   `This alert has no Telegram chat ID.`
4. The delivery ledger stores one Telegram destination and the rendered Telegram
   message, so pending email cannot be retried after a failure or process crash.
5. A combined alert is marked sent when either channel succeeds; one channel can
   therefore hide failure of the other.
6. `run_coop.py` passes only `new_from_willhaben` to user alerts. New mygewo
   listings are not evaluated against dashboard alerts.
7. The workflow and setup guide describe a two-minute trigger, while the owner
   has configured cron-job.org for minutely dispatches.

## Architecture

```text
cron-job.org (every minute, local Vienna time)
        |
        | POST /repos/vladbrincoveanu/ImmoAgent/dispatches
        v
GitHub Actions repository_dispatch (one poll)
        |
        v
mygewo + Willhaben newest feeds
        |
        | new candidate listings
        v
alert_matcher -> alert_dispatcher -> alert_deliveries ledger
                                  |                     |
                                  v                     v
                              Telegram              confirmed email
```

The user-alert path is intentionally separate from the owner's existing co-op
channel alerts. The same poll may feed both paths, but a dashboard alert's
destination and delivery ledger decide whether it receives a listing.

## Data Flow

1. `run_coop.run` fetches configured Genossenschaft sources and the newest
   Willhaben feed.
2. It identifies new candidates before upsert. Willhaben already exposes only
   new URLs; mygewo candidates are those whose URL is not present in Mongo.
3. If sending is enabled, `deliver_user_alerts` runs against the combined
   candidate list before the normal co-op upsert/channel path. This prioritizes
   alert latency and makes a canceled run safe: the next run can still see an
   unupserted listing, while a claimed delivery is recoverable from its ledger.
4. `alert_matcher.match` applies rubric, OR-keyword, numeric-gate, and confirmed
   channel rules.
5. `alert_dispatcher.dispatch` claims each `(alert_id, url_hash)` once, stores
   both channel payloads, sends configured channels, and marks each successful
   channel independently.
6. The normal poll continues to upsert and process owner channel alerts.
7. `retry_pending` retries stale incomplete channel work before matching new
   candidates.

## Channel Rules

- Telegram is optional. No Telegram token or chat ID is needed for an
  email-only alert.
- Email is usable only when `confirmed` is true.
- Telegram-only records remain active immediately, as before.
- An alert with both channels can deliver through either channel independently.
- A test request sends a probe to every configured, usable channel. If the email
  is unconfirmed and Telegram exists, Telegram can still be tested; the response
  explains that email confirmation is still required. If no usable channel can
  be tested, the route returns a clear `400` error.

## Delivery Ledger

The existing unique key `(alert_id, url_hash)` remains unchanged. New rows add:

```js
{
  alert_id,
  url_hash,
  status: "pending" | "sent",
  chat_id,
  message,
  telegram_sent: boolean,
  email,
  email_subject,
  email_body,
  email_sent: boolean,
  created_at,
  sent_at
}
```

For a configured channel, its sent flag starts false. An unconfigured channel
starts true. The row becomes `sent` only when every configured channel has its
sent flag set. Stale pending rows retry only incomplete channels. Existing
Telegram rows without the new flags remain retryable through their old
`chat_id`/`message` fields; no alert subscription migration is required.

The guarantee remains at-least-once. A crash after a provider accepts a message
but before the ledger update may cause a duplicate on retry; it must not lose a
fresh alert.

### Module: Alert Test Route

- **Responsibility:** Verify each configured alert destination without assuming Telegram exists.
- **Interface:** `POST /api/saved-searches/alert/test` with `{ id }`; returns JSON success or actionable error.
- **Dependencies:** MongoDB, user cookie, Telegram API, dashboard mailer.
- **Size target:** 100 lines max.

### Module: Dashboard Alert Mailer

- **Responsibility:** Render and send a small HTML test email using the existing SMTP transport.
- **Interface:** `alertTestEmail(keys) -> string`; existing `sendMail(...) -> { ok, error }` remains the transport boundary.
- **Dependencies:** nodemailer and SMTP environment variables.
- **Size target:** 80 lines max.

### Module: Alert Test Channel Policy

- **Responsibility:** Decide which stored alert channels are eligible for a test request without touching MongoDB or external providers.
- **Interface:** `testChannels(alert) -> { telegram: boolean, email: boolean, error?: string }`.
- **Dependencies:** none beyond TypeScript types.
- **Size target:** 60 lines max.

### Module: Alert Dispatcher

- **Responsibility:** Claim one alert/listing pair, send each configured channel, and retry incomplete channels.
- **Interface:** `dispatch(...) -> bool`; `retry_pending(...) -> int`; injected senders remain available for tests.
- **Dependencies:** `alert_matcher.channels_for`, `alert_email`, and the Mongo handler ledger methods.
- **Size target:** 240 lines max.

### Module: Mongo Delivery Ledger

- **Responsibility:** Own all MongoDB reads/writes for alert delivery claims and channel state.
- **Interface:** Extend `claim_delivery` with email payload fields; add channel-specific sent marking while retaining the existing final-mark method for stored-row compatibility.
- **Dependencies:** MongoDB and existing handler connection lifecycle.
- **Size target:** 100 lines for the alert-ledger slice.

### Module: Fast Co-op Poll

- **Responsibility:** Poll feeds, identify new listings from both sources, prioritize user alert delivery, then upsert and send owner channel alerts.
- **Interface:** Existing `run(no_send=False) -> int`; internal candidate collection remains deterministic and testable.
- **Dependencies:** source adapters, MongoDB handler, matcher, dispatcher, URL validation, and Telegram owner channels.
- **Size target:** 450 lines max; keep candidate selection in one small helper if needed.

### Module: Alerts Dashboard

- **Responsibility:** Create, list, test, and delete alerts while accurately describing Telegram-or-email delivery.
- **Interface:** Next.js `/alerts` page and existing alert API routes.
- **Dependencies:** alert API and existing styling conventions.
- **Size target:** 380 lines max; no visual redesign.

### Module: cron-job.org Workflow Contract

- **Responsibility:** Document and support the external one-minute trigger for one-poll GitHub runs.
- **Interface:** HTTP `POST` with repository dispatch headers/body; workflow `repository_dispatch` event.
- **Dependencies:** fine-grained GitHub PAT, GitHub Actions secrets, cron-job.org configuration.
- **Size target:** workflow comments and setup documentation only.

## Error Handling

- Invalid Telegram IDs remain rejected by the alert API.
- Unconfirmed email-only test returns a confirmation error rather than attempting
  SMTP delivery.
- SMTP configuration or provider errors return a setup/delivery error and leave
  the Python ledger pending.
- Telegram failures do not prevent email delivery, and email failures do not
  prevent Telegram delivery.
- A source adapter failure is isolated; the other source continues.
- A failed workflow is visible in cron-job.org history and GitHub Actions.
- No PAT, SMTP password, bot token, or other credential is committed.

## UI Copy

Replace Telegram-only wording with notification-neutral wording:

- Page latency copy: `Telegram or email notification`.
- Test button: `Test notification`.
- Help copy: email can be used alone; email must be confirmed before delivery.
- Keep the existing optional Telegram and email fields and at-least-one-channel
  validation.

## Testing

- Python matcher tests: confirmed email-only channel remains usable.
- Python dispatcher tests: email-only dispatch, SMTP failure leaves pending,
  pending email retry, Telegram regression, and mixed-channel partial failure.
- Python poll tests: new mygewo listings join user-alert candidates; existing
  mygewo listings do not; candidate delivery occurs before upsert.
- Dashboard unit tests: alert test email renderer escapes dynamic keyword text.
- Playwright tests: the page describes email delivery, an email-only stored row
  can invoke the test endpoint, and API success/error text reaches the real DOM.
- Workflow shell tests remain green with one-poll dispatch behavior.
- Final gates: targeted Playwright test, full Playwright suite, Python alert/poll
  tests, and TypeScript check/build used by the repository.

## Operational Setup

cron-job.org must call:

```text
POST https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches
```

with the repository dispatch headers and body:

```json
{"event_type":"coop-poll"}
```

The configured job runs every minute in `Europe/Vienna`. A healthy request
returns `204 No Content`; the resulting workflow run appears under
`coop-fast-poll`.

## Acceptance Criteria

1. A user can create an alert with a valid email and no Telegram chat ID.
2. After email confirmation, the dashboard Test action sends a probe email and
   reports success without requiring a Telegram token or chat ID.
3. A matching new mygewo or Willhaben listing reaches that confirmed email.
4. Email failure or a crash leaves durable pending state and a later poll retries
   the email.
5. Combined-channel alerts retry only the channel that failed.
6. cron-job.org's minutely dispatch starts one poll per trigger and no code path
   describes Telegram as mandatory.
7. Tests and type/build checks pass, with no credentials added to the repository.
