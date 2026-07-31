# Alert setup — the four manual steps

Nothing is delivered until these are done. Each is owner-only; none can be
automated from inside the repo.

## Why an external trigger at all

GitHub's `schedule:` cannot deliver a 2-minute cadence. Measured on this repo
over 2026-07-29 under a `*/5` cron, the gaps between consecutive delivered runs
were 153, 106, 140, 79, 84, 57, 80, 46 and 53 minutes — a median of ~80, with
40/40 runs green and zero cancellations. GitHub silently drops most ticks of a
high-frequency schedule, and deprioritises the more aggressively you ask.

`repository_dispatch` is not throttled that way. So an external scheduler fires
the dispatch, and the workflow's own cron stays only as a fallback for when the
external one dies.

## 1. GitHub PAT

Settings → Developer settings → Personal access tokens → Fine-grained tokens.

- Repository access: **only** `vladbrincoveanu/ImmoAgent`
- Permission: **Contents: Read and write**. This is what `POST /dispatches`
  requires; there is no narrower permission for it.
- Expiry: the shortest you are willing to rotate

Copy the token once — GitHub never shows it again.

## 2. cron-job.org job

Create a job at **every 2 minutes**, active in whatever local hours you want to
be alerted.

Set the active hours *here*, not in the workflow. cron-job.org schedules in local
time and handles DST; GitHub cron has no timezone, so a narrow window there
drifts an hour every winter — which is exactly what the old `*/15 4-15` cron did.

- URL: `https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches`
- Method: `POST`
- Headers:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer <the PAT from step 1>`
  - `Content-Type: application/json`
- Body: `{"event_type":"coop-poll"}`

A correct call returns **204 No Content**. A 404 almost always means the token
lacks Contents: write, not that the URL is wrong — GitHub returns 404 rather
than 403 for unauthorised repository access, to avoid confirming a repo exists.

## 3. Telegram chat id

1. Open Telegram, find the bot behind `TELEGRAM_MAIN_BOT_TOKEN`, and send
   `/start`. The bot cannot message you first, so this step is mandatory.
2. Get your numeric id from `https://api.telegram.org/bot<TOKEN>/getUpdates` —
   it is `result[0].message.chat.id`.
3. Paste it into the Telegram field on `/alerts`, then press **Test** on the
   created alert. A test message must arrive before you rely on the alert.

## 4. Mark yourself Pro

Alert creation is Pro-gated (`isPro` in `dashboard/lib/user.ts`; the route
returns 402 `upgrade_required`). In MongoDB, set your `user_id` — the `uid`
cookie value from the dashboard — to Pro in the `users` collection.

Clearing browser cookies issues a new `user_id`, and this step has to be redone.

## What you actually get

Roughly **2–3 minutes** from an ad appearing to the Telegram message. Runner
pickup, checkout and a cached pip install cost ~60–90s before the fetch even
starts. That is ~40× better than the ~80-minute median it replaces, and it is
the practical floor for a GitHub-hosted poller. Sub-minute would need a
long-lived process off GitHub.

## Verifying the whole chain

1. cron-job.org job history shows 204s.
2. `gh run list --workflow=coop-fast-poll.yml` shows runs roughly every 2 min,
   each completing in ~1–2 min. A run lasting ~55 min means it took the fallback
   window path instead of the single-poll path.
3. A run's log contains `🔍 willhaben newest: N url(s) on the feed`.
4. `🔔 user alerts: N delivery(ies)` appears once an alert exists and matches.

If step 3 shows a steady `0 url(s)`, Willhaben is blocking the runner. That
failure mode is silent by nature — it returns an empty page, not an error — so
check this line before changing anything else.

## Known gaps

- **No HTTP status histogram yet.** A Willhaben block shows up as `0 url(s)`
  rather than an explicit 429 count. Instrumenting it means changing
  `willhaben_scraper._fetch_with_retry`, which the daily `scrapeJob` also
  depends on, so it is deliberately deferred rather than bundled in here.
- **Email delivery is not retried.** The delivery ledger stores one Telegram
  destination per row; re-deriving an address on retry risks mailing the wrong
  person. A failed email is logged and stays failed. Telegram is retried.
