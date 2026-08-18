---
title: "[Superseded] Keyword alerts — dashboard-created fast poll"
date: 2026-07-31
status: superseded
superseded_by: 2026-08-17-fast-email-only-alerts-design.md
ui_scope: true
graph_scope: false
test_scope: true
supersedes_partially: 2026-07-30-coop-private-alerts-design.md (P4 section)
---

# [Superseded] Keyword alerts — dashboard-created fast poll

> This historical design is superseded by the [current approved design](2026-08-17-fast-email-only-alerts-design.md).
> Do not implement its old cadence, cancellation policy, retry timing, or
> Telegram-only assumptions. The [alert setup guide](../../ALERTS_SETUP.md) and
> newer spec are the current contract. The remaining sections are retained for
> historical rationale and are not operational guidance.

> **Current workflow contract:** cron-job.org sends one `repository_dispatch` per
> minute; automated dispatch and schedule runs perform one poll; only
> `workflow_dispatch` may hold an operator-selected window; and all triggers use
> the shared `coop-fast-poll` group with `cancel-in-progress: false`.

The superseded design proposed creating an alert on `/alerts` with a handful of
string keys and numeric filters. It described a fast poller crawling newly posted
ads across Willhaben and the Genossenschaft sources, then sending hits to a
Telegram DM. That proposal is retained only to explain the historical scope;
the current email-capable behavior is defined by the approved design above.

## Historical scope (not current)

**In:** the alert record, the matcher, crash-safe delivery, the `/alerts` UI, and
the historical trigger mechanism that was intended to make a faster cadence real.

**Out, and why:**

| Item | Status |
|---|---|
| Co-op images second hop (P1) | Already built on `relentless/coop-private-alerts`, unmerged |
| Willhaben private-coop crawler (P2) | Already built on the same branch, unmerged |
| `/coop/private` page (P3) | Already built on the same branch, unmerged |
| Genossenschaft availability | Separate spec, after this ships |
| Agent creation | Separate spec, after this ships |

This spec builds **on top of** that branch. It replaces the P4 section of
`2026-07-30-coop-private-alerts-design.md`; P0–P3 there still stand.

## Verified starting state

Checked against code, not assumed:

| Claim | Evidence |
|---|---|
| Alerts live in `alert_subscriptions`, not `saved_searches` | `dashboard/app/api/saved-searches/alert/route.ts` — `db.collection('alert_subscriptions').insertOne(doc)` |
| Alert creation is Pro-gated | Same route: `if (!(await isPro(db, userId)))` → 402 `upgrade_required` |
| Only ONE keyword is supported today | `keyword: (body.keyword ?? '').toString().trim().slice(0, 80)` — a scalar |
| No numeric filters exist per alert | The doc has `params`, `frequency`, `keyword` — no size/rooms/price fields |
| Numeric filter logic already exists, but globally | `run_coop.py:127 passes_filter` reads `bezirke` / `max_cost` / `min_rooms` / `min_area` from `coop_alerts.json` — one filter for the whole CI run, not per user |
| Delivery is not crash-safe | `run_coop.py:267` builds `new_transfers` in memory and delivers from it; a poll dying between upsert and send drops that ad permanently |
| GitHub `schedule:` cannot do 2 minutes | `coop-fast-poll.yml:4-8` records measured gaps of 153/106/140/79/84/57/80/46/53 min under `*/5` — median ~80 min, 40/40 runs green. GitHub drops ticks of high-frequency schedules |
| A dispatch escape hatch is already wired | `coop-fast-poll.yml` `repository_dispatch: types: [coop-poll]` |
| The matcher is title+body already | `alert_matcher.searchable_text` joins title, address, bezirk, description |

## Historical decisions (not current)

| Decision | Choice | Rationale |
|---|---|---|
| Cadence engine | External trigger → `repository_dispatch` | Historical rationale for bypassing `schedule:`; current cadence is defined by the approved design |
| Feed scope | Willhaben newest-first rentals **+** mygewo/Genossenschaft adapters, one loop | Widest coverage in a single poll |
| Multiple keys | **OR** — any key hits, anywhere in title or body | Matches how synonyms are listed; AND fails silently when one word is absent |
| Filters | `min/max_area`, `min/max_rooms`, `max_price` | Explicitly requested; district is covered by a plain keyword |
| Missing numeric data | **Send, flagged unverified** | Unknown ≠ fails the filter. A parse gap must not cost a hit when speed is the whole point |
| Telegram target | Owner's personal DM via the existing `TELEGRAM_MAIN_BOT_TOKEN` | No new channel, no new secret, works today — `TELEGRAM_COOP_CHANNEL_ID` still does not exist |
| Pro gate | Untouched; owner's `user_id` flipped to Pro in Mongo | Keeps the paywall honest; no auth-bypass code path in production |

## Historical architecture (not current)

```
cron-job.org  ──POST /dispatches every 2 min──►  GitHub Actions (coop-fast-poll)
                                                        │
                                    ┌───────────────────┴──────────────────┐
                                    ▼                                      ▼
                        willhaben_newest (page 1)              genossenschaft_scraper
                                    └───────────────┬──────────────────────┘
                                                    ▼
                                          mongodb upsert (url_hash dedup)
                                                    ▼
                                     alert_matcher  ──(alert, listing) pairs──►
                                                    ▼
                                          alert_dispatcher
                                     (alert_deliveries ledger)
                                                    ▼
                                            Telegram DM
```

### §1 Historical trigger tier (not operational)

The superseded design proposed that cron-job.org (free, 1-minute resolution)
issue a request every 2 minutes:

```
POST https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches
Authorization: Bearer <PAT>
Accept: application/vnd.github+json
{"event_type":"coop-poll"}
```

The old dispatch mechanism was not subject to the scheduler throttle that ate
`*/5`. Its workflow details are archived here for rationale only. Use the
[current approved design](2026-08-17-fast-email-only-alerts-design.md) and
[setup guide](../../ALERTS_SETUP.md) for the active cadence, fallback schedule,
poll-window behavior, and concurrency policy.

**Latency, stated honestly.** Runner pickup (5–30s) + checkout + cached pip
install (~30s) + fetch (~20s) means roughly **2–3 minutes** from ad posting to
Telegram, not seconds. That is ~40× better than the current ~80-minute median
and is the practical floor for a GitHub-hosted poller. A sub-minute figure would
require a long-lived process off GitHub — explicitly out of scope.

### §2 Poller tier

**Correction to the original plan of a new `willhaben_newest` module.**
`crawl_private_coop` (`Application/scraping/willhaben_private_coop.py:41`)
*already* fetches the newest-first Wien rental feed, page 1, with dedup via
`is_new` and a per-poll detail cap. It differs from what alerts need by exactly
one line — its final `coop_kind == "private_transfer"` filter. Writing a second
adapter would duplicate the fetch, the cap, and the block handling.

So: generalise the existing function instead of adding a module.

#### Module: `willhaben_private_coop` (generalised in place)
- **Responsibility:** One poll of the newest-first Willhaben feed → new listings the caller wants to keep.
- **Interface:** `crawl_newest(scraper, is_new, keep: Callable[[Listing], bool], search_url=None, max_details=25) -> List[Listing]`; `crawl_private_coop(...)` is retained as a thin wrapper passing `keep=is_private_transfer`, so existing callers and tests are untouched.
- **Dependencies:** unchanged
- **Size target:** ~120 lines (from ~100)

Page 1 only, as today. At the rapid cadence proposed by this historical design,
anything past page 1 was expected to be seen on an earlier poll; paging deeper
multiplies block risk for no new ads.

One consequence to accept: the alert feed's `keep` is "everything new", so the
per-poll detail-fetch cap (`MAX_DETAIL_FETCHES_PER_POLL = 25`) now binds on a
much larger candidate set. The existing `skipped_for_cap` warning already makes
that visible, and skipped URLs resolve on the next poll.

Adapter failures are isolated: a Willhaben block raises inside its own adapter
and is logged, and the Genossenschaft adapter still runs in the same poll.

### §3 Matcher

#### Module: `alert_matcher` (rewrite of the existing file)
- **Responsibility:** Test newly seen listings against every active alert and return the pairs to deliver, each tagged with whether its numeric filters could be evaluated.
- **Interface:** `match(listings, alerts) -> List[MatchPair]` where `MatchPair = (alert: Dict, listing, unverified: bool)`
- **Dependencies:** none beyond stdlib — pure functions, so it is unit-testable without Mongo or network
- **Size target:** ~130 lines

Rules:

1. **Keywords.** `alert["keywords"]` is a list. Case-insensitive substring, OR
   semantics, tested against `searchable_text` (title + address + bezirk +
   description). An empty list matches everything on the feed — deliberate, so a
   user can watch the whole stream without inventing a term.
2. **Numeric gates.** `min_area`, `max_area`, `min_rooms`, `max_rooms`,
   `max_price`. Each is optional on the alert; an unset gate always passes.
3. **Null listing values pass.** If the listing's `area_m2` is `None` and the
   alert sets `min_area: 60`, the pair is **kept** and `unverified` is `True`.
   Only a *present* value that violates a *set* gate rejects.

   Precisely: `unverified` is `True` **iff at least one gate is set on the alert
   and the corresponding listing field is `None`.** An alert with no gates at all
   never produces `unverified` — there is nothing it failed to check, so the
   warning banner would be noise on every single message.
4. **Legacy read.** `alert["keywords"] or ([alert["keyword"]] if alert.get("keyword") else [])`
   — old single-keyword records keep working without a migration script.

`channels_for` is retained unchanged: Telegram chat id as-is, email only when
`confirmed`.

### §4 Delivery

#### Module: `alert_dispatcher`
- **Responsibility:** Deliver one matched pair to that alert's channels exactly once, surviving a crash at any point.
- **Interface:** `dispatch(pair, handler) -> DeliveryResult`
- **Dependencies:** `telegram_bot`, `Application/alert_email`, `mongodb_handler`
- **Size target:** ~140 lines

New collection `alert_deliveries` with a **unique index on
`(alert_id, url_hash)`**.

Protocol per pair:

1. Insert `{alert_id, url_hash, status: "pending", created_at}`.
   A `DuplicateKeyError` means an earlier poll already owns this pair — skip.
2. Send to Telegram (and email if configured).
3. Update the row to `status: "sent", sent_at`.

Recovery: the stale-row timing described by this superseded design is obsolete.
The approved design defines the current channel-specific pending retry contract.
The unique index makes retry safe. Net semantics are at-least-once with no
visible duplicates.

**This replaces the in-memory `new_transfers` delivery path**, which loses an ad
permanently if the process dies between the Mongo upsert and the Telegram send.
The matcher's input becomes "listings seen this poll, plus anything with a
pending delivery row", not "listings the current process happens to hold".

Message format follows `telegram_bot.py` conventions (4096-char limit). When
`unverified` is true, the message is prefixed:

```
⚠️ Größe/Zimmer unbekannt — vor Ort prüfen
```

### §5 Dashboard

#### Module: `AlertsPage` (extension of `dashboard/app/alerts/page.tsx`)
- **Responsibility:** Create, list, test and delete keyword alerts.
- **Interface:** Next.js route `/alerts`; consumes `/api/saved-searches/alert`
- **Dependencies:** the alert API routes
- **Size target:** ~280 lines — split the alert-row editor into its own component if it exceeds that

Form fields:

| Field | Type | Notes |
|---|---|---|
| Stichwörter | text, comma-separated | Split on comma, trim, drop empties, max 10 keys × 80 chars |
| Größe von / bis | number, optional | m² |
| Zimmer von / bis | number, optional | |
| Preis max | number, optional | € |
| Telegram Chat-ID | text | Validated `^-?\d{5,20}$`, as today |
| E-Mail | email, optional | Double opt-in as today |

Two new actions on each listed alert:

- **Delete** — `DELETE /api/saved-searches/alert?id=…`, scoped to the caller's
  `user_id` so one user cannot delete another's alert.
- **Test** — `POST /api/saved-searches/alert/test`, sends one sample Telegram
  message to that alert's chat id. A wrong chat id must surface at setup time,
  not at 02:00 when a real hit is silently dropped.

### §6 Data model

`alert_subscriptions` gains:

```js
{
  keywords: string[],          // new; OR semantics
  keyword: string,             // legacy scalar, still written, read as fallback
  filters: {
    min_area?: number, max_area?: number,
    min_rooms?: number, max_rooms?: number,
    max_price?: number
  }
}
```

`alert_deliveries` (new):

```js
{ alert_id: ObjectId, url_hash: string, status: 'pending'|'sent',
  created_at: Date, sent_at?: Date }
// unique index: { alert_id: 1, url_hash: 1 }
```

Per project rule 4, all access goes through `mongodb_handler` methods —
`record_pending_delivery`, `mark_delivery_sent`, `pending_deliveries_older_than`
— never raw queries from the poller.

### §7 Rate limiting

Roughly 330 Willhaben polls/day against a source that today sees one. A block
typically arrives as an empty result set, not an exception, so it must be made
visible:

- One list fetch per poll, page 1, existing `willhaben_scraper` headers.
- Conditional GET (`If-None-Match` / `If-Modified-Since`) when the server offers
  validators; a `304` is a cheap no-op poll.
- Log an HTTP status histogram per poll so a shift from `200` to `429`/`403` is
  visible in the Actions log without reading bodies.
- On `429` or `403`: skip the Willhaben adapter for the next 15 minutes, log at
  `ERROR`. The Genossenschaft adapter continues.

## Testing

- `alert_matcher`: OR semantics across multiple keys; empty-keyword-list matches
  all; each numeric gate accepts and rejects; a `None` listing value passes a set
  gate and sets `unverified`; legacy scalar `keyword` still matches.
- `alert_dispatcher`: a second `dispatch` of the same pair sends nothing;
  a simulated crash between insert and send leaves `pending`, and the next poll
  delivers it exactly once (sender stubbed, no network).
- `willhaben_newest`: parses a saved HTML fixture into `Listing` objects;
  a `429` fixture triggers the backoff path rather than an empty success.
- Playwright (`dashboard/tests/alerts-page.spec.ts`): create an alert with three
  keywords and a size range, assert it appears in the list with those values,
  press Test, delete it, assert the empty state returns. DOM assertions on real
  selectors — no screenshots, per `.claude/rules/ui-testing.md`.
- Final gate: full Playwright suite, `cd Project/Tests && python -m pytest . -q`,
  `tsc` clean.

## Risks

1. **Willhaben blocking** is the single most likely failure, and it fails
   silently. §7 is the mitigation; the status histogram is what makes it
   diagnosable.
2. **Latency floor of 2–3 minutes** (§1). If a hit is genuinely first-come inside
   60 seconds, this architecture cannot win it. Stated so it is not discovered
   later.
3. **The PAT is a long-lived write credential** held by a third-party cron
   service. Use a fine-grained token, single repository, minimum scope needed
   for `dispatches`, and rotate it if cron-job.org is ever compromised.
4. **cron-job.org outage** degrades cadence to the `*/30` fallback. Degraded, not
   dead — by design.
5. **Keyword false positives.** "Ablöse" routinely means a kitchen buyout in an
   ordinary rental. OR semantics amplify this. Accepted: noise beats a missed
   hit, and `max_price` trims the worst of it.
6. **Pro gate.** Alert creation stays 402 for non-Pro users; the owner's
   `user_id` must be flipped to Pro in Mongo once. Clearing browser cookies
   issues a new `user_id` and requires redoing it.

## Historical owner-blocked steps (not current)

1. Create a GitHub **fine-grained PAT**, scoped to this repository only, with the
   permission required to POST `/dispatches`.
2. Configure the current one-minute cron-job.org request from the [approved
   design](2026-08-17-fast-email-only-alerts-design.md), using the [setup
   guide](../../ALERTS_SETUP.md) rather than this historical section.
3. `/start` the main Telegram bot, get the numeric chat id, paste it into the
   alert form.
4. Flip the owner's `user_id` to Pro in the `users` collection.

Nothing in §3–§5 delivers a message until steps 1–3 are done.

## Sequencing

```
S0  Merge relentless/coop-private-alerts (P1/P2/P3 already built, unverified)
 ├─ S1  alert_matcher rewrite + tests           ← pure, no deps, ships first
 ├─ S2  alert_deliveries ledger + dispatcher    ← depends on S1's pair shape
 ├─ S3  willhaben_newest adapter + wiring       ← independent of S1/S2
 ├─ S4  API: keywords[] + filters + DELETE + test  ← depends on S1's field names
 ├─ S5  /alerts UI                              ← depends on S4
 └─ S6  Workflow trigger changes + owner steps  ← last; nothing to trigger before it
```
