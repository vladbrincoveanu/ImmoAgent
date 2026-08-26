# Co-op channel: send exactly once + enforce alert filters

Status: **implemented 2026-08-24** on `relentless/coop-send-once`. Design approved
via `/grill-me` 2026-08-21.

Deviations from the design as written, all deliberate:

- `seed_dedup_key` builds an explicit `SimpleNamespace(bautraeger, address,
  area_m2, rooms)` rather than `SimpleNamespace(**doc)`. Mongo omits absent
  fields entirely and `compute_xsrc_fingerprint` reads area/rooms as attributes,
  so `**doc` raises `AttributeError` on exactly the sparse units that depend on
  the `url_hash` fallback.
- `Project/coop_alerts.json` is left in the tree but is no longer read by any
  code path. Nothing else references it.
- CLAUDE.md hard rule 5 amended (see "Conflict with CLAUDE.md" below).
Scope: the **broadcast channel feed** in `Project/run_coop.py`. The per-user
alert path (`alert_dispatcher.dispatch`) is already correct and is out of scope.

## Problem

The co-op Telegram channel re-sends the same listings every poll. `coop-fast-poll.yml`
is driven every minute by cron-job.org (`*/30 6-20 * * 1-6` is only a fallback),
so one stuck unit is ~900 messages/day.

### Root cause

`run_coop.py:445-459` gates the send on a document that may not exist:

```python
doc = handler.get_listing(listing.url)          # find_one({"url": url})
if doc and doc.get("sent_to_telegram"): continue
...
if bot and bot.send_message(...): handler.mark_sent(listing.url)
```

`upsert_coop_listing` returns **without creating a doc at that url** on three paths:

| Path | Location | Result |
|---|---|---|
| xsrc fingerprint duplicate | `mongodb_handler.py:315` | `"duplicate"`, no doc |
| content fingerprint duplicate | `mongodb_handler.py:330` | `"duplicate"`, no doc |
| validation failure | `mongodb_handler.py:297` | `"invalid"`, no doc |

`mark_sent` (`mongodb_handler.py:493`) is a bare `update_one` — **no upsert, and
`matched_count` is never checked** — so it writes nothing and still logs
`✅ Marked listing as sent`. The gate therefore passes forever.

Blast radius is set by how much the adapters overlap. mygewo is an aggregator of
the same builders that `coop.SOURCES` scrapes directly, so most units exist under
two URLs with one xsrc fingerprint. The migration branch at `:306` only rescues
the case where the incumbent is `coop_source == 'willhaben'`; a mygewo incumbent
falls through to `return "duplicate"`. Observed behaviour ("basically everything
repeats") is consistent with near-total overlap, **not** with failing writes —
confirmed by the dashboard showing fresh co-op units, i.e. writes are healthy.

### Second, independent defect

`Project/coop_alerts.json` is `{bezirke: [], max_cost: null, min_rooms: null, min_area: null}`
⇒ `matches_coop_alerts` returns `True` unconditionally. `COOP_ALERTS` is **not**
in the env block of `coop-fast-poll.yml` (lines 85-95), and `config.json` is
gitignored, so CI has no reachable filter at all. The channel is a firehose by
construction — a 31.74 m² 1-room unit reached a user whose alert asks for 75 m² / 3 rooms.

### Why nothing caught this

`Project/Tests/test_run_coop.py:156` builds `_mongo_mock` where `mark_sent` is a
MagicMock that always appears to succeed, and no test feeds a `"duplicate"`
upsert result into the send loop. The hole is invisible to the suite.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Dedicated **channel-send ledger**, insert-before-send | Independent of the listings-doc lifecycle, so `"duplicate"`/`"invalid"` upserts cannot reopen the hole |
| D2 | Unique index on `(chat_id, dedup_key)` | Once per unit **per channel**; a unit may legitimately appear in both mygewo and private_transfer feeds |
| D3 | `dedup_key = compute_xsrc_fingerprint(listing) or url_hash(url)` — **computed at send time**, see trap below | The xsrc key is what collapses the same unit across two URLs — it is what makes D4 work |
| D4 | **Seed the ledger as already-sent** from the existing co-op collection before first send | No flood on deploy. Accepted cost: a unit scraped-but-never-alerted stays silent forever |
| D5 | **Fail closed** on a ledger write error | Spam can never recur even if Mongo degrades. Must log at ERROR — silence is the failure mode |
| D6 | Channel filter = union of **active dashboard alerts** | Single source of truth, no redeploy to tune, and keywords work (`coop_alerts.json` has no keyword field) |
| D7 | **Strict** gates channel-side: `passes and not unverified` | Excludes unknown area/rooms. Implemented via the existing `gate_result` return — shared matcher semantics unchanged, so email alerts keep permissive behaviour |

## Design

### Ledger (`mongodb_handler.py` — hard rule 4: no raw queries outside this module)

New collection `coop_channel_sends`:

```
{ _id: ObjectId, chat_id: str, dedup_key: str, url: str,
  sent: bool, claimed_at: float, sent_at: float | None }
```

Unique index on `(chat_id, dedup_key)`.

Three methods, mirroring the proven `claim_delivery` shape:

- `ensure_channel_send_index() -> bool` — mirrors `ensure_delivery_index`; **False ⇒ skip all sends** (D5).
- `claim_channel_send(chat_id, dedup_key, url) -> bool` — insert `sent: False`. `DuplicateKeyError` ⇒ `False` (already handled, skip, not an error). Any other exception ⇒ `False` **and** log ERROR (D5).
- `mark_channel_send_sent(chat_id, dedup_key) -> bool` / `release_channel_send(chat_id, dedup_key)` — release deletes the claim so a transient Telegram failure does not suppress the unit permanently.

### Send loop (`run_coop.py`)

```python
if not is_coop_listing(listing):            continue
if not channel_match_any(listing, alerts):  continue   # D6 + D7
if not validate_url(listing.url):           ...        # hard rule 2, unchanged
key = compute_xsrc_fingerprint(listing) or url_hash(listing.url)   # NOT listing.content_fingerprint_xsrc
if not handler.claim_channel_send(chat_id, key, listing.url): continue   # D1/D5
if bot.send_message(format_coop_message(listing)):
    handler.mark_channel_send_sent(chat_id, key)
    handler.mark_sent(listing.url)          # best-effort, now fail-loud
else:
    handler.release_channel_send(chat_id, key)
```

**Accepted loss window:** a crash between claim and send drops that unit
permanently (no pending/retry queue, unlike `alert_dispatcher`). This is the
deliberate consequence of choosing fail-closed — silence over spam. Revisit only
if a missed first-come unit actually costs something.

#### Trap: the fingerprint is NOT on the Listing object

`Listing.content_fingerprint_xsrc` exists as a field (`Domain/listing.py:92`) but is
**never populated on the object** — `content_fingerprint_xsrc` is only ever written
into *dicts* inside Mongo write paths (`mongodb_handler.py:212,303`, `main.py:472`).
Reading `listing.content_fingerprint_xsrc` in the send loop yields `None` for every
listing, silently degrading every dedup_key to `url_hash` and defeating D4 seeding
outright. Compute it explicitly instead:

```python
from Application.helpers.listing_validator import compute_xsrc_fingerprint
from Application.alert_dispatcher import url_hash
```

`compute_xsrc_fingerprint` uses `getattr`, so it accepts a `Listing` directly (the
handler only wraps in `SimpleNamespace` because it holds a dict there).

Test 10 below exists specifically to pin this down.

### Filter (`run_coop.py`)

```python
from Application.alert_matcher import rubric_hit, keyword_hit, gate_result

def channel_match(alert, listing) -> bool:
    if not rubric_hit(alert, listing):  return False
    if not keyword_hit(alert, listing): return False
    passes, unverified = gate_result(alert, listing)
    return passes and not unverified                    # D7: strict
```

`channel_match_any` = `any(channel_match(a, l) for a in alerts)` over
`handler.get_active_alerts(...)`.

**Use every active alert, regardless of deliverability** — do NOT filter through
`channels_for`. The alert that prompted this report has an unconfirmed email and
therefore no usable channel, but it must still govern the broadcast feed.
Filtering ≠ delivery.

**Behaviour change, must be logged loudly:** zero active alerts now means zero
channel messages, where today it means "send everything".

### Seeding (D4)

One-off script, `mongodb_handler` methods only (hard rule 4). For every co-op doc
in the collection, insert a ledger row `sent: True` for **both** chat_ids
(mygewo and private_transfer) — seeding one channel only would let the other
flood. Idempotent: re-running hits `DuplicateKeyError` and is a no-op.

Fingerprint-less units (`compute_xsrc_fingerprint` returns None when `bautraeger`
or `address` is missing) fall back to `url_hash`, so a unit whose spamming URL
differs from its stored doc URL may emit exactly one more message. Bounded and
acceptable.

## Conflict with CLAUDE.md — must be resolved, not averaged

Hard rule 5 states: *"Dedup via `url`/`url_hash`; `sent_to_telegram` flag prevents
re-sends."* This design makes the **ledger** authoritative for the channel path,
because that flag provably does not prevent re-sends. `sent_to_telegram` keeps
being written best-effort (the dashboard reads it) but is no longer the gate.
**Hard rule 5 must be amended when this ships**, scoped to the channel path.

## Test plan (TDD — failing test first, per global rules)

The current `_mongo_mock` cannot express a unique index, so it cannot catch this
class of bug. Needs a fake collection with real duplicate-key semantics
(dict keyed on `(chat_id, dedup_key)`), or `mongomock`.

1. **Regression, the actual bug**: upsert returns `"duplicate"` ⇒ no listings doc ⇒ run the poll **twice** ⇒ assert exactly **one** `send_message`.
2. Same for `"invalid"`.
3. `mark_sent` with `matched_count == 0` returns False and logs ERROR.
4. `claim_channel_send` twice ⇒ second returns False.
5. Ledger write error ⇒ no send (D5, fail closed).
6. Send failure ⇒ claim released ⇒ next poll retries.
7. Both channels: one unit ⇒ one message each, never two in one channel (D2).
8. Strict gate: `area_m2=None` with `min_area` set ⇒ excluded from channel, still **delivered** by the email path (proves D7 didn't leak into shared semantics).
9. Zero active alerts ⇒ zero channel sends + a warning logged.
10. **Same unit under two different URLs ⇒ one message.** Two `Listing`s sharing `bautraeger`/`address`/`area`/`rooms` but with different `url` ⇒ exactly one send. Fails if the implementation reads `listing.content_fingerprint_xsrc` instead of computing it — this is the test that pins the trap above.

### Seed-key derivation (belongs with D4 above)

For every co-op doc, prefer the **stored** `content_fingerprint_xsrc` field, falling
back to `compute_xsrc_fingerprint(SimpleNamespace(**doc))`, then to `url_hash(doc['url'])`.
The stored field is only set when `is_genossenschaft` is true, so the fallback is
load-bearing, and it must produce byte-identical keys to the send loop or seeding
silently fails to suppress anything. One test asserting seed-key == send-key for
the same unit is worth more than the rest of the seeding tests combined.

## Rollback

Ledger and filter are independent and separately revertible. Reverting the filter
restores the firehose; reverting the ledger restores the spam. The seed rows are
inert once the ledger code is gone — no migration to undo, no schema change to
the listings collection.

## Open risks

- Root cause is inferred from code plus the "everything repeats" observation. The four log lines that would confirm it directly: `🚫 coop xsrc duplicate`, `🚫 coop fingerprint duplicate`, `coop upsert skipped`, `⚠️  MongoDB authentication required`. Worth grepping one poll run before implementing.
- If `bautraeger` normalises differently between the mygewo adapter and a builder-direct adapter, the xsrc fingerprints differ, no collapse happens, and the same unit sends once per URL. That is a *separate* near-duplicate defect this design does not address.
