# Alert Setup

Alerts use the `coop-fast-poll` GitHub Actions workflow. cron-job.org is the
primary trigger; the workflow's GitHub schedule is only a fallback. A
`repository_dispatch` run performs one poll through
`.github/scripts/coop-poll-window.sh`. Scheduled runs also perform one poll;
only `workflow_dispatch` retains its operator-selected polling window.

All triggers use the shared `coop-fast-poll` non-cancelling concurrency group.
GitHub keeps one run active and one run pending, so the next minute waits
instead of cancelling an active poll. If another event arrives while the
pending slot is occupied, GitHub keeps the newest pending event; the queue is
bounded rather than accumulating one runner per minute. Automated runs are
one poll, while a manual run may intentionally hold its configured window.

## 1. Configure the GitHub PAT

Create a fine-grained personal access token under GitHub Settings → Developer
settings → Personal access tokens.

- Repository access: **only** `vladbrincoveanu/ImmoAgent`
- Repository permission: **Contents: Read and write**
- Store the token only in cron-job.org's `Authorization` header. Do not put it
  in the URL, request body, repository, or documentation.

GitHub shows the token once. Set an expiry that can be rotated safely.

## 2. Configure cron-job.org

Create an active job that runs **every minute** in the `Europe/Vienna` time
zone. Configure local active hours in cron-job.org if alerts should be limited
to a daytime window; it handles Vienna DST. The GitHub schedule must not be used
as the primary cadence because GitHub can drop frequent scheduled ticks.

Use this exact request:

- Method: `POST`
- URL: `https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches`
- Headers:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer <fine-grained PAT>`
  - `Content-Type: application/json`
  - `X-GitHub-Api-Version: 2022-11-28`
- Raw JSON body: `{"event_type":"coop-poll"}`

A healthy request returns **204 No Content**. The corresponding run appears in
GitHub Actions as `coop-fast-poll`.

## 3. Configure alert channels

Create an alert at `/alerts`. At least one destination is required:

- **Email-only:** enter a valid email address and leave Telegram empty. Click
  the confirmation link sent to that address. An unconfirmed email is not an
  active delivery channel.
- **Telegram:** optionally enter a numeric Telegram chat ID. Telegram does not
  require email confirmation.
- **Both:** configure both destinations; each channel is tested and delivered
  independently.

Use the row's **Test notification** button after creating the alert. An
email-only test works after confirmation and does not need a Telegram token or
chat ID. The dashboard reports the channel that succeeded and any provider
error.

The Telegram bot token identifies the sender; it does not identify a destination.
For source-channel notifications, `TELEGRAM_COOP_CHANNEL_ID` and
`TELEGRAM_PRIVATE_COOP_CHANNEL_ID` must contain the signed numeric chat IDs of
the co-op channels/groups. Add the bot as an administrator in each destination
before setting those secrets. The same ID may be used for both feeds if they
intentionally share one destination.

For the GitHub Actions poll job, configure repository secrets without putting
their values in this repository:

- `MONGODB_URI` — database connection used by the poll.
- `SMTP_USER` and `SMTP_PASSWORD` — required for email-only alert delivery.
- Telegram secrets remain optional for Telegram delivery and the co-op channel
  feeds: `TELEGRAM_MAIN_BOT_TOKEN`, `TELEGRAM_COOP_CHANNEL_ID`, and
  `TELEGRAM_PRIVATE_COOP_CHANNEL_ID`. The bot token alone cannot send to a
  channel without its chat ID.

The Python email sender defaults to `smtp.gmail.com:587`. A missing or failing
SMTP configuration leaves the email channel pending so a later poll can retry
it. The dashboard confirmation email also needs `SMTP_USER` and
`SMTP_PASSWORD` in the Vercel project's Production environment. GitHub Actions
secrets and Vercel environment variables are separate stores; setting SMTP in
one does not configure the other.

## 4. What each poll delivers

Each poll collects new mygewo units and newly crawled Willhaben listings. New
mygewo URLs are checked in one batch; Willhaben candidates come from the newest
feed. The poll matches both active `coop_private` and `keyword` alerts before
the listing detail/upsert loop, then records each `(alert, listing)` delivery
in the Mongo ledger.

Telegram and email are tracked separately. If one channel succeeds and the
other fails, only the failed channel remains pending. The next poll retries
from the stored destination and rendered content; it does not need a fresh
listing lookup. A dead row becomes eligible after one minute, just beyond the
60-second per-channel lease, so this also recovers a poll that crashed during
delivery without waiting five minutes.

## Latency and fallback behavior

The honest GitHub-hosted SLA is about **2–3 minutes** from a listing appearing
to a Telegram or email notification. One minute belongs to the external
trigger; runner pickup, checkout, dependency installation, scraping, and
delivery add roughly another 60–90 seconds. GitHub Actions is the latency
floor, not a sub-minute alerting system.

The workflow keeps these non-primary paths:

- `repository_dispatch`: one poll, then exit.
- `workflow_dispatch`: manual run; `window_minutes` defaults to 55 and `0`
  means one poll.
- `schedule`: `*/30 6-20 * * 1-6` UTC, fallback only. Each delivered fallback
  run performs one poll; primary local active hours and DST remain controlled by
  cron-job.org.

The Willhaben fast path considers the ten newest feed URLs by default. Override
this with the `WILLHABEN_PRIVATE_COOP_MAX_FEED_URLS` repository variable when a
different newest-feed window is needed. Mygewo continues to page through the
full Vienna rental inventory because older units can still be new to the
database.

## Operational checks

1. cron-job.org history shows `204 No Content` responses every minute while the
   job is active.
2. `gh run list --workflow=coop-fast-poll.yml` shows dispatched runs. A normal
   dispatched or fallback run logs `window complete: 1 polls, 0 failed`; a manual
   run has more than one poll only when its configured window is nonzero.
3. Source logs include `🔍 willhaben newest: N url(s) on the feed` and
   `🏠 willhaben newest: N kept from N detail fetch(es)`. The mygewo adapter logs
   `🔍 MYGEWO: N listing(s) parsed`.
4. Once confirmed alerts match new listings, the run logs
   `🔔 user alerts: N delivery(ies) for M new listing(s) across K alert(s)`.
5. Pending recovery logs begin with
   `↻ retrying N pending alert delivery(ies)`. Successful channels log
   `✅ alert ... delivery channel succeeded`.

## Troubleshooting

### cron-job.org returns 404

Check the URL exactly and inspect the request headers. GitHub commonly returns
404 when the `Authorization: Bearer <PAT>` header is missing, malformed, or
uses a token without access to `vladbrincoveanu/ImmoAgent`. Confirm the
fine-grained token is repository-only for this repository and grants
`Contents: Read and write`. Never move the PAT into the URL or body.

### cron-job.org returns 401

The token is invalid, expired, revoked, or the Bearer value is malformed.
Create or rotate the fine-grained PAT and update the header, keeping the exact
`Authorization: Bearer <PAT>` format.

### A 204 response exists but no workflow run appears

Confirm `.github/workflows/coop-fast-poll.yml` is present on the repository's
default branch, its `repository_dispatch` event includes `coop-poll`, and
GitHub Actions is enabled. Check the Actions workflow list and the event type
before changing the cron schedule. A successful API response alone does not
prove that a workflow file on another branch was eligible to run.

### The run reports zero listings

For Willhaben, inspect `🔍 willhaben newest: 0 url(s) on the feed`. A steady zero
usually means the runner received an empty or blocked page; check this before
changing alert filters. For mygewo, inspect its parsed-count line and any
adapter error. If sources work but no user delivery appears, verify that the
email is confirmed when email delivery is desired, the alert has a usable
Telegram chat ID or email, matching keywords/filters, and a newly seen listing.

### Email or SMTP failures

Use the dashboard **Test notification** button first. In Actions, verify
`SMTP_USER` and `SMTP_PASSWORD` are set and valid; for Gmail, use an app
password. The poll logs either `SMTP_USER/SMTP_PASSWORD unset — alert email NOT
sent to ...` or `alert email to ... failed: ...`. A failed email remains pending
and is retried on a later poll. If confirmation mail never arrives, fix the
dashboard deployment's SMTP configuration and resend/create the alert; the
poller delivers confirmed email-only subscriptions and Telegram-enabled
subscriptions; it never sends an email until that email is confirmed.

Never include PATs, SMTP passwords, bot tokens, MongoDB URIs, or other secrets
in this guide, issue reports, or chat.
