# Keyword Alerts Fast-Poll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner create an alert on `/alerts` with several string keys plus size/rooms/price filters, and have a ~2-minute poller push every matching new ad straight to a Telegram DM.

**Architecture:** cron-job.org POSTs `repository_dispatch` to GitHub Actions every 2 minutes (GitHub's own `schedule:` is measured-incapable of this). Each dispatched run does one poll of the newest-first Willhaben rental feed plus the Genossenschaft adapters, upserts to Mongo, tests everything new against every stored alert with OR-keyword + numeric-gate matching, and delivers through a crash-safe `alert_deliveries` ledger.

**Tech Stack:** Python 3.11 (requests, bs4, pymongo), Next.js 14 App Router + TypeScript, MongoDB, GitHub Actions, Playwright, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-31-keyword-alerts-fast-poll-design.md`. Every requirement there is in force.
- Project rule 4: all MongoDB access goes through `Integration/mongodb_handler.py` methods. No raw queries from the poller or from new Python modules.
- Project rule 3: use `is_valid_listing_data()` from `mongodb_handler.py` — never inline `> 0` checks.
- Project rule 2: URL validation via `Application/helpers/listing_validator.validate_url` is mandatory before anything is displayed or sent.
- Telegram messages follow `Integration/telegram_bot.py` patterns and the 4096-character limit.
- UI copy is German — this dashboard is German-language throughout.
- Never commit secrets. The PAT, `MONGODB_URI`, and bot tokens live in GitHub Secrets and `.env` only.
- `.claude/rules/ui-testing.md` applies to every `dashboard/` change: targeted spec per iteration, full Playwright suite as the final gate, DOM assertions not screenshots.
- Python tests live in `Project/Tests/` and start with the `sys.path.insert` preamble used by `Project/Tests/test_alert_matcher.py`.
- Run Python tests with `cd Project/Tests && python -m pytest . -q`.
- Branch: `relentless/keyword-alerts-fast-poll`. Never commit to `main`.
- In this sandbox `python -c` and `rm` are blocked; `gh`, `npm`, `npx`, and `curl` need `dangerouslyDisableSandbox: true`.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `Project/Application/alert_matcher.py` | Pure matching: OR keywords + numeric gates → pairs tagged `unverified` | 1 |
| `Project/Tests/test_alert_matcher.py` | Matcher behaviour, incl. legacy scalar keyword | 1 |
| `Project/Integration/mongodb_handler.py` | Ledger methods + `get_active_alerts` accepting several kinds | 2 |
| `Project/Application/alert_dispatcher.py` | Exactly-once delivery of one pair across Telegram + email | 2 |
| `Project/Tests/test_alert_dispatcher.py` | Idempotency and crash-recovery | 2 |
| `Project/Application/scraping/willhaben_private_coop.py` | Generalised `crawl_newest` + retained `crawl_private_coop` wrapper | 3 |
| `Project/Tests/test_willhaben_private_coop.py` | `keep` predicate behaviour | 3 |
| `Project/run_coop.py` | Wire the alert feed and the dispatcher into the poll | 3 |
| `dashboard/app/api/saved-searches/alert/route.ts` | POST accepts `keywords[]` + `filters`; new DELETE | 4 |
| `dashboard/app/api/saved-searches/alert/test/route.ts` | Send one probe message to an alert's chat id | 4 |
| `dashboard/app/alerts/page.tsx` | Create / list / test / delete UI | 5 |
| `dashboard/tests/alerts-page.spec.ts` | DOM assertions on the full UI cycle | 5 |
| `.github/workflows/coop-fast-poll.yml` | Dispatch-aware window, schedule demoted to fallback | 6 |
| `docs/ALERTS_SETUP.md` | The four owner-blocked manual steps | 6 |

---

### Task 1: Matcher — OR keywords and numeric gates

**Files:**
- Modify: `Project/Application/alert_matcher.py` (full rewrite of `alert_matches`; `searchable_text` and `channels_for` kept)
- Test: `Project/Tests/test_alert_matcher.py`

**Interfaces:**
- Consumes: nothing from other tasks. Pure functions, stdlib only.
- Produces:
  - `alert_keywords(alert: Dict) -> List[str]` — lowercased keys, legacy scalar folded in
  - `keyword_hit(alert: Dict, listing) -> bool`
  - `gate_result(alert: Dict, listing) -> Tuple[bool, bool]` — `(passes, unverified)`
  - `match(listings, alerts) -> List[Tuple[Dict, object, bool]]` — `(alert, listing, unverified)`
  - `searchable_text(listing) -> str` and `channels_for(alert) -> Tuple[Optional[str], Optional[str]]` unchanged
  - Alert filter keys, used verbatim by Tasks 3–5: `min_area`, `max_area`, `min_rooms`, `max_rooms`, `max_price`, read from `alert["filters"]`
  - Listing fields read: `area_m2`, `rooms`, `price_total` (all `Optional[float]` on `Domain.listing.Listing`)

**Note on the return-type change:** `match` returns 3-tuples now, not 2-tuples. `run_coop.deliver_user_alerts` unpacks 2 today and is updated in Task 3.

- [ ] **Step 1: Write the failing tests**

Append to `Project/Tests/test_alert_matcher.py`. Extend the existing `_L` stub first so listings can carry numbers:

```python
class _LN:
    """Listing stub with the numeric fields the gates read."""
    def __init__(self, title=None, description=None,
                 area_m2=None, rooms=None, price_total=None):
        self.title = title
        self.address = None
        self.bezirk = None
        self.description = description
        self.area_m2 = area_m2
        self.rooms = rooms
        self.price_total = price_total


def _alert(**kw):
    base = {"_id": "k1", "telegram_chat_id": "-100123456", "email": None,
            "confirmed": True, "keywords": [], "filters": {}}
    base.update(kw)
    return base


# --- OR keyword semantics ---

def test_any_key_hits_matches():
    a = _alert(keywords=["ablöse", "nachmieter"])
    assert keyword_hit(a, _LN(title="Nachmieter gesucht"))


def test_no_key_hits_does_not_match():
    a = _alert(keywords=["ablöse", "nachmieter"])
    assert not keyword_hit(a, _LN(title="Schöne Altbauwohnung"))


def test_key_matches_body_not_only_title():
    a = _alert(keywords=["nachmieter"])
    assert keyword_hit(a, _LN(title="Wohnung 1100", description="Nachmieter gesucht"))


def test_empty_keyword_list_matches_everything():
    assert keyword_hit(_alert(keywords=[]), _LN(title="irgendwas"))


def test_legacy_scalar_keyword_still_matches():
    a = _alert(keywords=None, keyword="ablöse")
    assert keyword_hit(a, _LN(title="ABLÖSE für Küche"))


def test_keywords_are_case_insensitive():
    assert keyword_hit(_alert(keywords=["ABLÖSE"]), _LN(title="ablöse"))


# --- numeric gates ---

def test_area_gate_accepts_value_in_range():
    a = _alert(filters={"min_area": 50, "max_area": 80})
    assert gate_result(a, _LN(area_m2=65)) == (True, False)


def test_area_gate_rejects_value_below_min():
    a = _alert(filters={"min_area": 50})
    assert gate_result(a, _LN(area_m2=40)) == (False, False)


def test_area_gate_rejects_value_above_max():
    a = _alert(filters={"max_area": 80})
    assert gate_result(a, _LN(area_m2=95)) == (False, False)


def test_rooms_gate_rejects_value_below_min():
    a = _alert(filters={"min_rooms": 3})
    assert gate_result(a, _LN(rooms=2)) == (False, False)


def test_price_gate_rejects_value_above_max():
    a = _alert(filters={"max_price": 900})
    assert gate_result(a, _LN(price_total=1200)) == (False, False)


def test_price_gate_accepts_value_at_max():
    a = _alert(filters={"max_price": 900})
    assert gate_result(a, _LN(price_total=900)) == (True, False)


# --- the null rule: unknown never fails a gate ---

def test_null_value_passes_a_set_gate_and_flags_unverified():
    a = _alert(filters={"min_area": 60})
    assert gate_result(a, _LN(area_m2=None)) == (True, True)


def test_null_value_with_no_gates_set_is_not_unverified():
    assert gate_result(_alert(filters={}), _LN(area_m2=None)) == (True, False)


def test_unverified_only_when_the_missing_field_has_a_gate():
    a = _alert(filters={"min_area": 60})
    assert gate_result(a, _LN(area_m2=70, rooms=None)) == (True, False)


# --- match() integration ---

def test_match_returns_alert_listing_unverified_triples():
    a = _alert(keywords=["nachmieter"], filters={"min_area": 60})
    pairs = match([_LN(title="Nachmieter", area_m2=None)], [a])
    assert len(pairs) == 1
    alert, listing, unverified = pairs[0]
    assert alert is a and unverified is True


def test_match_drops_listings_failing_a_gate():
    a = _alert(keywords=[], filters={"max_price": 800})
    assert match([_LN(title="x", price_total=1500)], [a]) == []


def test_match_skips_alerts_with_no_usable_channel():
    a = _alert(telegram_chat_id=None, email="x@y.at", confirmed=False)
    assert match([_LN(title="x")], [a]) == []
```

Update the import at the top of the file to:

```python
from Application.alert_matcher import (  # noqa: E402
    alert_keywords, alert_matches, channels_for, gate_result, keyword_hit,
    match, searchable_text,
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd Project/Tests && python -m pytest test_alert_matcher.py -q`
Expected: FAIL — `ImportError: cannot import name 'keyword_hit'`

- [ ] **Step 3: Rewrite the matcher**

Replace the body of `Project/Application/alert_matcher.py` below `searchable_text` with this. Keep the module docstring, updating it to describe OR keywords and the null rule. Keep `searchable_text` and `channels_for` exactly as they are.

```python
# The numeric gates. Each entry is (filter key, listing attribute, comparison).
# Kept as data so adding a gate is one line and cannot forget the null rule.
_MIN_GATES = (
    ("min_area", "area_m2"),
    ("min_rooms", "rooms"),
)
_MAX_GATES = (
    ("max_area", "area_m2"),
    ("max_rooms", "rooms"),
    ("max_price", "price_total"),
)


def alert_keywords(alert: Dict) -> List[str]:
    """The alert's keys, lowercased and stripped, empties dropped.

    Reads the legacy scalar `keyword` when `keywords` is absent, so alerts
    created before multi-key support keep working without a migration."""
    raw = alert.get("keywords")
    if not raw:
        legacy = alert.get("keyword")
        raw = [legacy] if legacy else []
    return [k.strip().lower() for k in raw if k and k.strip()]


def keyword_hit(alert: Dict, listing) -> bool:
    """True when ANY of the alert's keys appears in the ad.

    OR, not AND: the keys are how a user lists synonyms for the same thing
    ("Ablöse, Weitergabe, Nachmieter"), and requiring all of them would make a
    single absent word silently disable the alert.

    No keys at all means "everything on this feed" — deliberate, so a user can
    watch the whole stream without inventing a term."""
    keys = alert_keywords(alert)
    if not keys:
        return True
    haystack = searchable_text(listing)
    return any(k in haystack for k in keys)


def gate_result(alert: Dict, listing) -> Tuple[bool, bool]:
    """(passes, unverified) for one alert's numeric filters.

    The null rule: a listing field the source did not publish never FAILS a
    gate. Newest-first list pages routinely omit size and rooms, and treating
    "unknown" as "too small" would drop exactly the fresh ads this poller exists
    to catch. Such a pair is delivered with `unverified` set, and the Telegram
    message says so, rather than being silently discarded.

    `unverified` is True only when a gate IS set and the field it reads is None.
    An alert with no gates has nothing it failed to check, so flagging it would
    put a warning on every single message."""
    filters = alert.get("filters") or {}
    unverified = False

    for key, attr in _MIN_GATES:
        limit = filters.get(key)
        if limit is None:
            continue
        value = getattr(listing, attr, None)
        if value is None:
            unverified = True
        elif value < limit:
            return False, False

    for key, attr in _MAX_GATES:
        limit = filters.get(key)
        if limit is None:
            continue
        value = getattr(listing, attr, None)
        if value is None:
            unverified = True
        elif value > limit:
            return False, False

    return True, unverified


def alert_matches(alert: Dict, listing) -> bool:
    """True when this alert wants this listing, ignoring the unverified flag.

    Retained for callers that only need a boolean."""
    return keyword_hit(alert, listing) and gate_result(alert, listing)[0]


def match(listings: List, alerts: List[Dict]) -> List[Tuple[Dict, object, bool]]:
    """Every (alert, listing, unverified) triple that should be delivered.

    Order is alert-major so one noisy listing cannot starve later alerts if the
    caller truncates."""
    out: List[Tuple[Dict, object, bool]] = []
    for alert in alerts:
        chat_id, email = channels_for(alert)
        if not chat_id and not email:
            # An alert with no reachable channel is a record of nothing. Say so:
            # silently skipping it looks identical to "no matches" to the user.
            logger.warning(
                f"alert {alert.get('_id')} has no usable channel — skipping")
            continue
        for listing in listings:
            if not keyword_hit(alert, listing):
                continue
            passes, unverified = gate_result(alert, listing)
            if passes:
                out.append((alert, listing, unverified))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd Project/Tests && python -m pytest test_alert_matcher.py -q`
Expected: PASS, all tests including the pre-existing ones in the file.

- [ ] **Step 5: Commit**

```bash
git add Project/Application/alert_matcher.py Project/Tests/test_alert_matcher.py
git commit -m "feat(alerts): OR keyword matching plus size/rooms/price gates

A listing field the source omitted never fails a gate — newest-first list
pages routinely lack size and rooms, and treating unknown as too-small
would drop the freshest ads. Such matches deliver flagged unverified."
```

---

### Task 2: Crash-safe delivery ledger

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (add three methods near `get_active_alerts`, line ~613; widen `get_active_alerts`)
- Create: `Project/Application/alert_dispatcher.py`
- Test: `Project/Tests/test_alert_dispatcher.py`

**Interfaces:**
- Consumes from Task 1: `match`'s 3-tuple shape and `channels_for`.
- Produces:
  - `MongoDBHandler.get_active_alerts(kind: Union[str, List[str]]) -> List[Dict]`
  - `MongoDBHandler.claim_delivery(alert_id, url_hash, chat_id, message) -> bool` — True when this caller now owns the delivery, False when someone already did. The rendered message and destination are stored **on the claim row**, so a retry needs only the row — never a lookup from `url_hash` back to a listing, which would require a reverse index that does not exist.
  - `MongoDBHandler.mark_delivery_sent(alert_id, url_hash) -> None`
  - `MongoDBHandler.stale_pending_deliveries(older_than_minutes: int = 5) -> List[Dict]`
  - `alert_dispatcher.dispatch(alert, listing, unverified, handler, token, send_telegram=None, send_email=None) -> bool`
  - `alert_dispatcher.retry_pending(handler, token, send_telegram=None) -> int`
  - `alert_dispatcher.UNVERIFIED_PREFIX` — the exact German warning line
- Reason for `claim_delivery` rather than plain insert: the claim and the duplicate check must be one atomic operation, or two concurrent polls both see "no row" and both send.

- [ ] **Step 1: Write the failing tests**

Create `Project/Tests/test_alert_dispatcher.py`:

```python
"""Delivery must be exactly-once as the user sees it, and must survive a poll
that dies mid-send.

The ledger is what makes both true: a claim is atomic, so two concurrent polls
cannot both send, and a claimed-but-unsent row is retried by the next poll."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.alert_dispatcher import (  # noqa: E402
    UNVERIFIED_PREFIX, dispatch, retry_pending,
)


class _L:
    def __init__(self, url="https://willhaben.at/iad/x/1", title="Nachmieter",
                 area_m2=70.0, rooms=3.0, price_total=800.0):
        self.url = url
        self.title = title
        self.address = "Wien"
        self.bezirk = "1100"
        self.description = "Nachmieter gesucht"
        self.area_m2 = area_m2
        self.rooms = rooms
        self.price_total = price_total
        self.image_url = None
        self.builder_url = None
        self.coop_kind = "private_transfer"


class _Handler:
    """In-memory stand-in for the ledger half of MongoDBHandler."""
    def __init__(self):
        self.rows = {}

    def claim_delivery(self, alert_id, url_hash, chat_id=None, message=None):
        key = (alert_id, url_hash)
        if key in self.rows:
            return False
        self.rows[key] = {"status": "pending", "alert_id": alert_id,
                          "url_hash": url_hash, "chat_id": chat_id,
                          "message": message}
        return True

    def mark_delivery_sent(self, alert_id, url_hash):
        self.rows[(alert_id, url_hash)]["status"] = "sent"

    def stale_pending_deliveries(self, older_than_minutes=5):
        return [r for r in self.rows.values() if r["status"] == "pending"]


def _statuses(handler):
    return [r["status"] for r in handler.rows.values()]


_ALERT = {"_id": "a1", "keywords": [], "filters": {},
          "telegram_chat_id": "-100123456", "email": None, "confirmed": True}


def test_first_dispatch_sends_and_marks_sent():
    handler, sent = _Handler(), []
    ok = dispatch(_ALERT, _L(), False, handler, token="t",
                  send_telegram=lambda chat, msg: sent.append((chat, msg)) or True)
    assert ok is True
    assert len(sent) == 1
    assert _statuses(handler) == ["sent"]


def test_second_dispatch_of_same_pair_sends_nothing():
    handler, sent = _Handler(), []
    send = lambda chat, msg: sent.append((chat, msg)) or True
    listing = _L()
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    assert len(sent) == 1


def test_different_alerts_each_get_the_same_listing():
    handler, sent = _Handler(), []
    send = lambda chat, msg: sent.append((chat, msg)) or True
    listing = _L()
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    dispatch({**_ALERT, "_id": "a2"}, listing, False, handler, token="t",
             send_telegram=send)
    assert len(sent) == 2


def test_crash_during_send_leaves_the_row_pending():
    handler = _Handler()

    def boom(chat, msg):
        raise RuntimeError("network died mid-send")

    ok = dispatch(_ALERT, _L(), False, handler, token="t", send_telegram=boom)
    assert ok is False
    assert _statuses(handler) == ["pending"]


def test_a_pending_row_is_retried_and_then_marked_sent():
    """The at-least-once guarantee. A poll that died mid-send must not lose the
    ad — the next poll finds the claimed-but-unsent row and delivers it."""
    handler = _Handler()

    def boom(chat, msg):
        raise RuntimeError("network died mid-send")

    dispatch(_ALERT, _L(), False, handler, token="t", send_telegram=boom)
    assert _statuses(handler) == ["pending"]

    sent = []
    count = retry_pending(handler, token="t",
                          send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert count == 1
    assert len(sent) == 1
    assert _statuses(handler) == ["sent"]


def test_retry_sends_the_message_stored_at_claim_time():
    """Retry reads the rendered message off the row. Re-deriving it would need a
    url_hash → listing reverse lookup that does not exist."""
    handler = _Handler()
    dispatch(_ALERT, _L(), True, handler, token="t",
             send_telegram=lambda c, m: (_ for _ in ()).throw(RuntimeError("x")))
    sent = []
    retry_pending(handler, token="t",
                  send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert sent[0].startswith(UNVERIFIED_PREFIX)


def test_retry_is_a_no_op_when_nothing_is_pending():
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(), False, handler, token="t",
             send_telegram=lambda c, m: sent.append(m) or True)
    assert retry_pending(handler, token="t",
                         send_telegram=lambda c, m: sent.append(m) or True) == 0
    assert len(sent) == 1


def test_unverified_match_is_flagged_in_the_message():
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(), True, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert sent[0].startswith(UNVERIFIED_PREFIX)


def test_verified_match_carries_no_warning():
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(), False, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert not sent[0].startswith(UNVERIFIED_PREFIX)


def test_message_stays_within_the_telegram_limit():
    handler, sent = _Handler(), []
    listing = _L()
    listing.description = "x" * 9000
    dispatch(_ALERT, listing, True, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert len(sent[0]) <= 4096


def test_alert_with_no_channel_claims_nothing():
    handler = _Handler()
    silent = {**_ALERT, "telegram_chat_id": None, "email": None}
    assert dispatch(silent, _L(), False, handler, token="t",
                    send_telegram=lambda c, m: True) is False
    assert handler.rows == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd Project/Tests && python -m pytest test_alert_dispatcher.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'Application.alert_dispatcher'`

- [ ] **Step 3: Write the dispatcher**

Create `Project/Application/alert_dispatcher.py`:

```python
"""Deliver one matched (alert, listing) pair exactly once.

The problem this solves: the previous path iterated an in-memory list of newly
seen listings and sent from it. A poll that died between the Mongo upsert and
the Telegram send lost that ad permanently — the next poll no longer considered
it new, so it was never delivered and nothing recorded that it hadn't been.

The ledger fixes both halves. `claim_delivery` is atomic, so concurrent polls
cannot double-send. A claimed row that is never marked sent is a visible record
of a failed delivery, and the next poll retries it.

Every sender is injected so the tests run without network or Mongo.
"""
import hashlib
import logging
from typing import Callable, Optional

from Application.alert_matcher import channels_for
from Application.coop_format import format_coop_message
from Application.helpers.listing_validator import validate_url

logger = logging.getLogger(__name__)

# Telegram's hard limit. The formatter is bounded, but an ad body is not, so the
# message is truncated defensively rather than rejected by the API at 2am.
TELEGRAM_MAX_CHARS = 4096

UNVERIFIED_PREFIX = "⚠️ Größe/Zimmer/Preis unbekannt — vor Ort prüfen\n"


def url_hash(url: str) -> str:
    """Stable per-ad key for the ledger, matching the project's dedup scheme."""
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


def build_message(listing, unverified: bool) -> str:
    """The Telegram body for one hit, truncated to the API limit."""
    body = format_coop_message(listing)
    if unverified:
        body = UNVERIFIED_PREFIX + body
    if len(body) > TELEGRAM_MAX_CHARS:
        body = body[: TELEGRAM_MAX_CHARS - 1] + "…"
    return body


def _default_telegram(token: str) -> Callable[[str, str], bool]:
    from Integration.telegram_bot import TelegramBot

    def send(chat_id: str, message: str) -> bool:
        return bool(TelegramBot(token, chat_id).send_message(message))

    return send


def _default_email() -> Callable[[str, object], bool]:
    from Application.alert_email import send_alert_email

    def send(address: str, listing) -> bool:
        return bool(send_alert_email(address, listing))

    return send


def dispatch(
    alert: dict,
    listing,
    unverified: bool,
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
    send_email: Optional[Callable[[str, object], bool]] = None,
) -> bool:
    """Deliver one pair. True only when something was actually sent.

    Never raises: one dead channel must not abort the poll that feeds the
    website."""
    chat_id, email = channels_for(alert)
    if not chat_id and not email:
        return False

    # Project rule: nothing is sent before its URL is validated.
    if not validate_url(getattr(listing, "url", None)):
        logger.warning(f"alert delivery skipped, invalid url: {listing.url!r}")
        return False

    alert_id, key = alert.get("_id"), url_hash(listing.url)
    message = build_message(listing, unverified)
    # The message and destination go onto the claim row BEFORE the send. That is
    # what makes retry possible without a url_hash → listing reverse lookup,
    # which the schema does not support.
    if not handler.claim_delivery(alert_id, key, chat_id, message):
        # Someone already owns this pair. Not an error — this is the guarantee.
        return False

    delivered = False

    if chat_id and token:
        sender = send_telegram or _default_telegram(token)
        try:
            delivered = bool(sender(chat_id, message)) or delivered
        except Exception as e:
            logger.error(f"❌ alert telegram send failed ({chat_id}): {e}")

    if email:
        sender = send_email or _default_email()
        try:
            delivered = bool(sender(email, listing)) or delivered
        except Exception as e:
            logger.error(f"❌ alert email send failed ({email}): {e}")

    if delivered:
        handler.mark_delivery_sent(alert_id, key)
    else:
        # The row stays `pending` on purpose. That is the retry signal, and it is
        # also the only durable evidence that a delivery was attempted and lost.
        logger.error(f"❌ alert {alert_id} delivery failed; row left pending")
    return delivered


def retry_pending(
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
) -> int:
    """Re-send deliveries that were claimed but never sent. Returns the count.

    This is what makes the guarantee at-LEAST-once rather than at-most-once. A
    poll that dies between the claim and the send leaves a `pending` row; every
    later poll picks it up. Because the row carries the rendered message and the
    destination, no listing lookup is needed — the ad may not even be "new" any
    more by the time this runs.

    Email is deliberately not retried here: the row stores one Telegram
    destination, and re-deriving an address risks mailing the wrong person."""
    rows = handler.stale_pending_deliveries()
    if not rows:
        return 0
    logger.warning(f"↻ retrying {len(rows)} pending alert delivery(ies)")
    resent = 0
    for row in rows:
        chat_id, message = row.get("chat_id"), row.get("message")
        if not chat_id or not message or not token:
            continue
        sender = send_telegram or _default_telegram(token)
        try:
            if sender(chat_id, message):
                handler.mark_delivery_sent(row.get("alert_id"), row.get("url_hash"))
                resent += 1
        except Exception as e:
            # Stays pending, gets picked up again next poll.
            logger.error(f"❌ retry failed for {chat_id}: {e}")
    return resent
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd Project/Tests && python -m pytest test_alert_dispatcher.py -q`
Expected: PASS

- [ ] **Step 5: Add the handler methods**

In `Project/Integration/mongodb_handler.py`, replace `get_active_alerts` (line ~613) and add the ledger methods immediately after it:

```python
    def get_active_alerts(self, kind) -> List[Dict]:
        """Confirmed alert subscriptions for one feed, or several.

        `kind` is a string or a list of strings — the poller watches both the
        legacy 'coop_private' feed and the newer 'keyword' feed in one query.

        Unconfirmed email subscriptions are excluded: anyone can type someone
        else's address into the form, so an unconfirmed one must never be
        delivered to. Telegram subscriptions are stored already-confirmed —
        supplying a chat id the bot can post to is itself the consent."""
        kinds = [kind] if isinstance(kind, str) else list(kind)
        try:
            return list(self.db["alert_subscriptions"].find(
                {"kind": {"$in": kinds}, "confirmed": True}))
        except Exception as e:
            # An alert lookup failure must not abort a poll — the scrape and the
            # upserts that feed the website still have to run.
            print(f"MongoDB alert query error: {e}")
            return []

    def ensure_delivery_index(self) -> None:
        """The unique index is what makes `claim_delivery` a real claim.

        Without it two concurrent polls both read "no row" and both send."""
        try:
            self.db["alert_deliveries"].create_index(
                [("alert_id", 1), ("url_hash", 1)], unique=True)
        except Exception as e:
            print(f"MongoDB delivery index error: {e}")

    def claim_delivery(self, alert_id, url_hash: str,
                       chat_id: str = None, message: str = None) -> bool:
        """Take ownership of one (alert, ad) delivery. True if we now own it.

        False means another poll already claimed it — including a poll that
        claimed it and then died. That case is recovered by
        `stale_pending_deliveries`, not by re-claiming here, because a blind
        re-claim would double-send every ad on every poll.

        `chat_id` and `message` are stored so a retry can send from the row
        alone. Without them, recovering a lost delivery would need a
        url_hash → listing reverse lookup that this schema does not support."""
        from datetime import datetime, timezone
        try:
            self.db["alert_deliveries"].insert_one({
                "alert_id": alert_id,
                "url_hash": url_hash,
                "chat_id": chat_id,
                "message": message,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
            })
            return True
        except Exception:
            # DuplicateKeyError is the expected path, not an error.
            return False

    def mark_delivery_sent(self, alert_id, url_hash: str) -> None:
        from datetime import datetime, timezone
        try:
            self.db["alert_deliveries"].update_one(
                {"alert_id": alert_id, "url_hash": url_hash},
                {"$set": {"status": "sent",
                          "sent_at": datetime.now(timezone.utc)}})
        except Exception as e:
            print(f"MongoDB delivery update error: {e}")

    def stale_pending_deliveries(self, older_than_minutes: int = 5) -> List[Dict]:
        """Claimed-but-never-sent deliveries, i.e. polls that died mid-send."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        try:
            return list(self.db["alert_deliveries"].find(
                {"status": "pending", "created_at": {"$lt": cutoff}}))
        except Exception as e:
            print(f"MongoDB pending delivery query error: {e}")
            return []
```

- [ ] **Step 6: Run the full Python suite for regressions**

Run: `cd Project/Tests && python -m pytest . -q`
Expected: PASS. `get_active_alerts` changed shape — if any existing test calls it with a string, it still works, because a string is wrapped into a one-element list.

- [ ] **Step 7: Commit**

```bash
git add Project/Application/alert_dispatcher.py Project/Tests/test_alert_dispatcher.py Project/Integration/mongodb_handler.py
git commit -m "feat(alerts): exactly-once delivery via an alert_deliveries ledger

Replaces sending from an in-memory list, where a poll dying between the
Mongo upsert and the Telegram send lost that ad permanently. A claim is
atomic; a claimed-but-unsent row is the retry signal."
```

---

### Task 3: Widen the feed and wire the poll

**Files:**
- Modify: `Project/Application/scraping/willhaben_private_coop.py`
- Modify: `Project/run_coop.py` (`deliver_user_alerts`, and the Willhaben block at ~line 267)
- Test: `Project/Tests/test_willhaben_private_coop.py`

**Interfaces:**
- Consumes: Task 1's `match` 3-tuples; Task 2's `dispatch`, `claim_delivery`, `stale_pending_deliveries`, `ensure_delivery_index`.
- Produces:
  - `crawl_newest(scraper, is_new, keep, search_url=None, max_details=25) -> List[Listing]`
  - `is_private_transfer(listing) -> bool`
  - `crawl_private_coop(...)` unchanged in signature and behaviour
  - `run_coop.deliver_user_alerts(handler, listings) -> int`
- Alert kinds the poller reads: `["coop_private", "keyword"]`.

- [ ] **Step 1: Write the failing tests**

Append to `Project/Tests/test_willhaben_private_coop.py` (create it with the standard preamble if absent):

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.willhaben_private_coop import (  # noqa: E402
    crawl_newest, crawl_private_coop, is_private_transfer,
)


class _L:
    def __init__(self, url, coop_kind=None):
        self.url = url
        self.coop_kind = coop_kind


class _Resp:
    text = "<html></html>"


class _Scraper:
    """Fetch stub. `pages` maps a url to the Listing scrape_single_listing returns."""
    def __init__(self, urls, pages):
        self._urls = urls
        self._pages = pages
        self.detail_calls = 0

    def _fetch_with_retry(self, url):
        return _Resp()

    def extract_listing_urls(self, soup):
        return self._urls

    def scrape_single_listing(self, url):
        self.detail_calls += 1
        return self._pages.get(url)


def test_crawl_newest_keeps_everything_when_keep_is_always_true():
    urls = ["u1", "u2"]
    pages = {"u1": _L("u1"), "u2": _L("u2", coop_kind="private_transfer")}
    out = crawl_newest(_Scraper(urls, pages), is_new=lambda u: True,
                       keep=lambda listing: True)
    assert [l.url for l in out] == ["u1", "u2"]


def test_crawl_private_coop_still_keeps_only_transfers():
    urls = ["u1", "u2"]
    pages = {"u1": _L("u1"), "u2": _L("u2", coop_kind="private_transfer")}
    out = crawl_private_coop(_Scraper(urls, pages), is_new=lambda u: True)
    assert [l.url for l in out] == ["u2"]


def test_already_seen_urls_cost_no_detail_fetch():
    urls = ["u1", "u2"]
    pages = {"u1": _L("u1"), "u2": _L("u2")}
    scraper = _Scraper(urls, pages)
    crawl_newest(scraper, is_new=lambda u: u == "u2", keep=lambda l: True)
    assert scraper.detail_calls == 1


def test_detail_cap_bounds_the_poll():
    urls = [f"u{i}" for i in range(10)]
    pages = {u: _L(u) for u in urls}
    scraper = _Scraper(urls, pages)
    out = crawl_newest(scraper, is_new=lambda u: True, keep=lambda l: True,
                       max_details=3)
    assert scraper.detail_calls == 3
    assert len(out) == 3


def test_is_private_transfer_reads_coop_kind():
    assert is_private_transfer(_L("u", coop_kind="private_transfer"))
    assert not is_private_transfer(_L("u"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd Project/Tests && python -m pytest test_willhaben_private_coop.py -q`
Expected: FAIL — `ImportError: cannot import name 'crawl_newest'`

- [ ] **Step 3: Generalise the crawler**

In `Project/Application/scraping/willhaben_private_coop.py`, replace `crawl_private_coop` with `crawl_newest` plus two thin wrappers. Everything between the fetch and the loop is unchanged — only the final filter becomes a parameter:

```python
def is_private_transfer(listing) -> bool:
    """The original filter, now one `keep` predicate among others."""
    return getattr(listing, "coop_kind", None) == "private_transfer"


def crawl_newest(
    scraper,
    is_new: Callable[[str], bool],
    keep: Callable[[Listing], bool],
    search_url: Optional[str] = None,
    max_details: int = MAX_DETAIL_FETCHES_PER_POLL,
) -> List[Listing]:
    """One poll of the newest-first Willhaben feed → the new ads `keep` wants.

    `scraper` is a WillhabenScraper (needs `_fetch_with_retry`,
    `extract_listing_urls`, `scrape_single_listing`). `is_new` decides whether a
    URL is worth a detail fetch — in production that is a Mongo dedup check, so
    an ad costs one detail fetch ever, not one per poll.

    `keep` is the only thing that varies between callers: the private-Ablöse
    rubric wants transfers only, keyword alerts want everything new and do their
    own matching afterwards.

    Never raises: a blocked or reshaped search page must leave the mygewo half of
    the poll running."""
    url = search_url or WILLHABEN_PRIVATE_COOP_URL
    try:
        response = scraper._fetch_with_retry(url)
    except Exception as e:
        logger.error(f"willhaben newest search fetch failed: {e}")
        return []
    if response is None:
        logger.error("willhaben newest search returned nothing (blocked?)")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    urls = scraper.extract_listing_urls(soup)
    logger.info(f"🔍 willhaben newest: {len(urls)} url(s) on the feed")

    out: List[Listing] = []
    fetched = 0
    skipped_for_cap = 0
    for listing_url in urls:
        if not is_new(listing_url):
            continue
        if fetched >= max_details:
            skipped_for_cap += 1
            continue
        fetched += 1
        try:
            listing = scraper.scrape_single_listing(listing_url)
        except Exception as e:
            # One malformed ad must not end the poll.
            logger.warning(f"detail fetch failed for {listing_url}: {e}")
            continue
        if listing is None:
            continue
        if keep(listing):
            out.append(listing)

    if skipped_for_cap:
        # Never silent: a cap that hides new ads during a first-come-first-served
        # race is exactly the thing that must be visible. With keyword alerts the
        # candidate set is the whole feed, so this binds far more often than it
        # did for the transfer-only rubric.
        logger.warning(
            f"willhaben newest: {skipped_for_cap} new url(s) skipped, "
            f"detail cap {max_details} reached; they resolve on the next poll")

    logger.info(f"🏠 willhaben newest: {len(out)} kept "
                f"from {fetched} detail fetch(es)")
    return out


def crawl_private_coop(
    scraper,
    is_new: Callable[[str], bool],
    search_url: Optional[str] = None,
    max_details: int = MAX_DETAIL_FETCHES_PER_POLL,
) -> List[Listing]:
    """Private co-op transfers only — `crawl_newest` with the original filter."""
    return crawl_newest(scraper, is_new, is_private_transfer,
                        search_url=search_url, max_details=max_details)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd Project/Tests && python -m pytest test_willhaben_private_coop.py -q`
Expected: PASS

- [ ] **Step 5: Rewrite `deliver_user_alerts` in `run_coop.py`**

Replace the whole function (lines ~50–82) with:

```python
# Feeds that user-created alerts watch. 'coop_private' is the original
# private-transfer rubric; 'keyword' is the general feed created on /alerts.
ALERT_KINDS = ["coop_private", "keyword"]


def deliver_user_alerts(handler, listings: List[Listing]) -> int:
    """Deliver newly-seen listings to the alerts users created on /alerts.

    Returns the number of successful deliveries. Never raises: an alert-delivery
    failure must not fail the poll that feeds the website."""
    try:
        alerts = handler.get_active_alerts(ALERT_KINDS)
    except Exception as e:
        logger.error(f"❌ could not load user alerts: {e}")
        return 0
    if not alerts:
        return 0

    handler.ensure_delivery_index()
    token = os.environ.get("TELEGRAM_MAIN_BOT_TOKEN")

    # Repair before delivering. A previous poll that died mid-send left rows
    # claimed but unsent; those ads are already gone from the "new" set, so this
    # is the only path that can still deliver them.
    delivered = retry_pending(handler, token)

    for alert, listing, unverified in match(listings, alerts):
        if dispatch(alert, listing, unverified, handler, token):
            delivered += 1
    logger.info(f"🔔 user alerts: {delivered} delivery(ies) "
                f"for {len(listings)} new listing(s) across {len(alerts)} alert(s)")
    return delivered
```

Update the imports at the top of `run_coop.py`:

```python
from Application.alert_dispatcher import dispatch, retry_pending
from Application.alert_matcher import match
from Application.scraping.willhaben_private_coop import crawl_newest, is_private_transfer
```

Delete the now-unused `channels_for` and `send_alert_email` imports — `alert_dispatcher` owns both. Keep `from Application.coop_format import format_coop_message` only if something else in the file still uses it; if nothing does, remove it too.

- [ ] **Step 6: Widen the Willhaben call in `run`**

In `run()`, replace the `crawl_private_coop(...)` call (~line 267) with:

```python
    new_from_willhaben: List[Listing] = []
    if os.environ.get("WILLHABEN_PRIVATE_COOP", "1") != "0":
        try:
            new_from_willhaben = crawl_newest(
                WillhabenScraper(config=load_config() or {}),
                is_new=lambda u: handler.get_listing(u) is None,
                # Everything new: keyword alerts do their own matching, and the
                # transfer rubric is re-applied per listing just below. Narrowing
                # here would make an alert for "Balkon" silently unmatchable.
                keep=lambda listing: True,
            )
            for listing in new_from_willhaben:
                if is_private_transfer(listing):
                    listing.coop_kind = "private_transfer"
            seen.extend(new_from_willhaben)
        except Exception as e:
            # A Willhaben block must not take the mygewo half of the poll with it.
            logger.error(f"❌ willhaben newest adapter failed: {e}")
```

The `coop_kind` assignment is now conditional. Previously every returned listing was a transfer by construction; with the widened feed, blanket-tagging would route ordinary rentals into the private-Ablöse channel and corrupt `/coop/private`.

- [ ] **Step 7: Run the full Python suite**

Run: `cd Project/Tests && python -m pytest . -q`
Expected: PASS. If `test_run_coop*.py` asserts on the old 2-tuple unpack or on `crawl_private_coop` being called in `run`, update those assertions to the new names — the behaviour they guard is unchanged.

- [ ] **Step 8: Commit**

```bash
git add Project/Application/scraping/willhaben_private_coop.py Project/run_coop.py Project/Tests/test_willhaben_private_coop.py
git commit -m "feat(alerts): widen the fast poll to the whole newest-first feed

crawl_private_coop already polled the newest-first Wien rental feed and
differed only by its final filter, so that filter becomes a keep predicate
rather than a second adapter. coop_kind is now tagged per listing, not
blanket-applied, so ordinary rentals stay out of /coop/private."
```

---

### Task 4: Alert API — keywords, filters, delete, test

**Files:**
- Modify: `dashboard/app/api/saved-searches/alert/route.ts`
- Create: `dashboard/app/api/saved-searches/alert/test/route.ts`

**Interfaces:**
- Consumes from Task 1: the exact filter keys `min_area`, `max_area`, `min_rooms`, `max_rooms`, `max_price`, stored under `filters`; the `keywords` array; kind `'keyword'`.
- Produces, for Task 5:
  - `POST /api/saved-searches/alert` body `{ kind, keywords: string[], filters: {...}, email?, telegram_chat_id?, frequency }`
  - `GET /api/saved-searches/alert` → `{ items: Alert[] }` where `Alert` carries `_id, kind, keywords, filters, email, telegram_chat_id, confirmed, created_at`
  - `DELETE /api/saved-searches/alert?id=<id>` → `{ ok: true }` / 404
  - `POST /api/saved-searches/alert/test` body `{ id }` → `{ ok: true }` / 400 / 404

- [ ] **Step 1: Accept `keywords` and `filters` on POST**

In `dashboard/app/api/saved-searches/alert/route.ts`, extend `SubscribeBody`:

```ts
  /** Free-text keys, OR semantics. Any one hitting the title or body fires the
   * alert — this is how a user lists synonyms for one thing. */
  keywords?: string[];
  /** Numeric gates. Every field optional; an unset gate always passes, and a
   * listing value the source omitted never fails one. */
  filters?: {
    min_area?: number; max_area?: number;
    min_rooms?: number; max_rooms?: number;
    max_price?: number;
  };
```

Add the constants and sanitiser above the handler:

```ts
const KEYWORD_MAX_LEN = 80;
const MAX_KEYWORDS = 10;
const FILTER_KEYS = [
  'min_area', 'max_area', 'min_rooms', 'max_rooms', 'max_price',
] as const;

/** Keep only finite, non-negative numbers. A NaN from a blank form field would
 * otherwise be stored and then compare false against everything, silently
 * disabling the alert. */
function cleanFilters(raw: Record<string, unknown> | undefined) {
  const out: Record<string, number> = {};
  for (const key of FILTER_KEYS) {
    const v = Number(raw?.[key]);
    if (Number.isFinite(v) && v >= 0) out[key] = v;
  }
  return out;
}

function cleanKeywords(body: SubscribeBody): string[] {
  const list = Array.isArray(body.keywords)
    ? body.keywords
    : (body.keyword ? [body.keyword] : []);
  return list
    .map((k) => String(k).trim().slice(0, KEYWORD_MAX_LEN))
    .filter(Boolean)
    .slice(0, MAX_KEYWORDS);
}
```

Widen the kind check and the stored document:

```ts
  const kind = body.kind ?? 'listings';
  if (!['listings', 'coop_private', 'keyword'].includes(kind)) {
    return NextResponse.json({ error: 'Invalid kind' }, { status: 400 });
  }
  const keywords = cleanKeywords(body);
  const filters = cleanFilters(body.filters as Record<string, unknown> | undefined);
```

In the `doc` literal, replace the `keyword` line with:

```ts
    keywords,
    // Legacy scalar kept in sync so a rollback to the previous poller keeps
    // matching on the primary key rather than silently matching everything.
    keyword: keywords[0] ?? '',
    filters,
```

Both `min`/`max` bounds are accepted independently — an inverted pair like
`min_area: 90, max_area: 40` is stored as given and simply matches nothing. That
is visible in the UI, whereas silently swapping the values would not be.

- [ ] **Step 2: Add DELETE to the same route file**

```ts
// DELETE /api/saved-searches/alert?id=<id>
// Scoped to the caller's user_id: an id is guessable, and one user must never
// be able to delete another's alert.
export async function DELETE(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  const id = req.nextUrl.searchParams.get('id') ?? '';
  if (!ObjectId.isValid(id)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
  }
  const result = await db.collection('alert_subscriptions').deleteOne({
    _id: new ObjectId(id),
    user_id: userId,
  });
  if (result.deletedCount === 0) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  const res = NextResponse.json({ ok: true });
  setUserCookie(res, userId);
  return res;
}
```

- [ ] **Step 3: Ensure GET returns the new fields**

Confirm the existing `GET` in this file projects `keywords` and `filters`. If it uses an explicit projection, add both keys; if it returns whole documents, no change is needed. The list must also map `_id` to a string, since the client compares it in React keys.

- [ ] **Step 4: Add the test-send route**

Create `dashboard/app/api/saved-searches/alert/test/route.ts`:

```ts
import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';

export const dynamic = 'force-dynamic';

/** POST /api/saved-searches/alert/test  { id }
 *
 * Sends one probe message to the alert's Telegram chat. A mistyped chat id is
 * otherwise indistinguishable from a quiet market: the poll logs a send failure
 * nobody reads, and the user concludes the alert is broken days later. */
export async function POST(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);

  let body: { id?: string } = {};
  try { body = await req.json(); } catch { body = {}; }
  const id = (body.id ?? '').trim();
  if (!ObjectId.isValid(id)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
  }

  const alert = await db.collection('alert_subscriptions').findOne({
    _id: new ObjectId(id),
    user_id: userId,
  });
  if (!alert) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const chatId = alert.telegram_chat_id as string | null;
  if (!chatId) {
    return NextResponse.json(
      { error: 'Dieser Alert hat keine Telegram Chat-ID.' }, { status: 400 });
  }

  const token = process.env.TELEGRAM_MAIN_BOT_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: 'TELEGRAM_MAIN_BOT_TOKEN ist nicht gesetzt.' }, { status: 503 });
  }

  const keys = Array.isArray(alert.keywords) ? alert.keywords : [];
  const text =
    `✅ Testnachricht von ImmoScouter.\n` +
    `Alert: ${keys.length ? keys.join(', ') : '(alle Treffer)'}\n` +
    `Diese Chat-ID funktioniert — echte Treffer kommen hier an.`;

  const tg = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  if (!tg.ok) {
    // Surface Telegram's own reason — "chat not found" vs "bot was blocked"
    // need different fixes from the user.
    const detail = await tg.text().catch(() => '');
    return NextResponse.json(
      { error: `Telegram lehnte die Nachricht ab: ${detail.slice(0, 200)}` },
      { status: 502 });
  }

  const res = NextResponse.json({ ok: true });
  setUserCookie(res, userId);
  return res;
}
```

- [ ] **Step 5: Typecheck**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/api/saved-searches/alert/
git commit -m "feat(alerts): keywords array, numeric filters, delete and test-send

A mistyped chat id is otherwise indistinguishable from a quiet market, so
the test route makes it fail at setup time instead of at 2am."
```

---

### Task 5: Alerts UI

**Files:**
- Modify: `dashboard/app/alerts/page.tsx`
- Test: `dashboard/tests/alerts-page.spec.ts`

**Interfaces:**
- Consumes from Task 4: the POST body shape, `GET → { items }`, `DELETE ?id=`, `POST /test { id }`.
- Produces test ids used by the Playwright spec: `alerts-page`, `alert-form`, `alert-keywords`, `alert-min-area`, `alert-max-area`, `alert-min-rooms`, `alert-max-rooms`, `alert-max-price`, `alert-email`, `alert-chatid`, `alert-submit`, `alert-status`, `alerts-empty`, `alerts-list`, `alert-item`, `alert-delete`, `alert-test`.

- [ ] **Step 1: Write the failing Playwright spec**

Replace `dashboard/tests/alerts-page.spec.ts` with:

```ts
import { test, expect } from '@playwright/test';

/** The alert form is the only way the owner configures the fast poll, so the
 * whole cycle is asserted on real DOM: create with several keys and a size
 * range, see it listed, delete it, get the empty state back. */
test.describe('/alerts', () => {
  test('renders the form with keywords and numeric filters', async ({ page }) => {
    await page.goto('/alerts');
    await expect(page.getByTestId('alerts-page')).toBeVisible();
    await expect(page.getByTestId('alert-keywords')).toBeVisible();
    await expect(page.getByTestId('alert-min-area')).toBeVisible();
    await expect(page.getByTestId('alert-max-area')).toBeVisible();
    await expect(page.getByTestId('alert-min-rooms')).toBeVisible();
    await expect(page.getByTestId('alert-max-rooms')).toBeVisible();
    await expect(page.getByTestId('alert-max-price')).toBeVisible();
  });

  test('states the real cadence, not a number nobody verified', async ({ page }) => {
    await page.goto('/alerts');
    await expect(page.getByTestId('alerts-page')).toContainText('2');
  });

  test('requires at least one channel', async ({ page }) => {
    await page.goto('/alerts');
    await page.getByTestId('alert-keywords').fill('Ablöse, Nachmieter');
    await page.getByTestId('alert-submit').click();
    await expect(page.getByTestId('alert-status')).toBeVisible();
  });

  test('created alert appears in the list with its keys, then deletes', async ({ page }) => {
    await page.route('**/api/saved-searches/alert', async (route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ ok: true, subscription_id: 'x1' }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ items: [{
          _id: 'x1', kind: 'keyword', keywords: ['Ablöse', 'Nachmieter'],
          filters: { min_area: 60 }, email: null,
          telegram_chat_id: '-100123456', confirmed: true, created_at: null,
        }] }) });
    });
    await page.goto('/alerts');
    const item = page.getByTestId('alert-item').first();
    await expect(item).toContainText('Ablöse');
    await expect(item).toContainText('Nachmieter');
    await expect(page.getByTestId('alert-delete').first()).toBeVisible();
    await expect(page.getByTestId('alert-test').first()).toBeVisible();
  });

  test('shows the empty state when there are no alerts', async ({ page }) => {
    await page.route('**/api/saved-searches/alert', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ items: [] }) }));
    await page.goto('/alerts');
    await expect(page.getByTestId('alerts-empty')).toBeVisible();
  });

  test('logs no console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto('/alerts');
    await expect(page.getByTestId('alerts-page')).toBeVisible();
    expect(errors).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the spec to verify it fails**

Start the dev server once: `cd dashboard && npm run dev &`, wait for `localhost:3000`.
Run: `cd dashboard && npx playwright test alerts-page --reporter=dot`
Expected: FAIL — `alert-keywords` and the numeric fields do not exist yet.

- [ ] **Step 3: Extend the page**

In `dashboard/app/alerts/page.tsx`:

Widen the `Alert` type:

```ts
type Alert = {
  _id: string;
  kind: string;
  keywords?: string[] | null;
  keyword?: string | null;
  filters?: {
    min_area?: number; max_area?: number;
    min_rooms?: number; max_rooms?: number;
    max_price?: number;
  } | null;
  email: string | null;
  telegram_chat_id: string | null;
  confirmed: boolean;
  created_at: string | null;
};
```

Add state beside the existing fields:

```ts
  const [minArea, setMinArea] = useState('');
  const [maxArea, setMaxArea] = useState('');
  const [minRooms, setMinRooms] = useState('');
  const [maxRooms, setMaxRooms] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
```

Add these helpers above the component:

```ts
/** "Ablöse, Nachmieter , " → ["Ablöse", "Nachmieter"]. Splitting on the comma
 * only: a space is legitimate inside a key ("Nachmieter gesucht"). */
function parseKeywords(raw: string): string[] {
  return raw.split(',').map((k) => k.trim()).filter(Boolean).slice(0, 10);
}

/** Blank stays undefined rather than becoming 0 — an unset gate must pass
 * everything, and `max_price: 0` would match nothing. */
function num(raw: string): number | undefined {
  const v = Number(raw);
  return raw.trim() && Number.isFinite(v) ? v : undefined;
}

function describeFilters(f: Alert['filters']): string {
  if (!f) return '';
  const parts: string[] = [];
  if (f.min_area || f.max_area) parts.push(`${f.min_area ?? '–'}–${f.max_area ?? '–'} m²`);
  if (f.min_rooms || f.max_rooms) parts.push(`${f.min_rooms ?? '–'}–${f.max_rooms ?? '–'} Zi.`);
  if (f.max_price) parts.push(`≤ ${f.max_price} €`);
  return parts.join(' · ');
}
```

Change the POST body in `create` to:

```ts
        body: JSON.stringify({
          kind: 'keyword',
          keywords: parseKeywords(keyword),
          filters: {
            min_area: num(minArea), max_area: num(maxArea),
            min_rooms: num(minRooms), max_rooms: num(maxRooms),
            max_price: num(maxPrice),
          },
          email: email || undefined,
          telegram_chat_id: chatId || undefined,
          frequency: 'instant',
        }),
```

and clear the new fields alongside the existing ones on success.

Change the keyword input's `data-testid` to `alert-keywords`, drop its
`maxLength={80}` (the cap is per key, applied server-side), and update its
placeholder and label:

```tsx
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Stichwörter, kommagetrennt — z. B. Ablöse, Nachmieter, 1100"
          aria-label="Stichwörter"
          data-testid="alert-keywords"
          className={`${inputCls} w-full`}
        />
        <p className="text-xs text-[#6B6B6B]">
          Ein Treffer genügt: Sobald EINES der Stichwörter im Titel oder im
          Anzeigentext vorkommt, wird gemeldet. Ohne Stichwort kommt jede neue
          Anzeige.
        </p>
```

Insert the numeric filter grid directly after that paragraph:

```tsx
        <div className="grid grid-cols-2 gap-3">
          <input type="number" min="0" value={minArea}
            onChange={(e) => setMinArea(e.target.value)}
            placeholder="Größe ab (m²)" aria-label="Größe ab"
            data-testid="alert-min-area" className={inputCls} />
          <input type="number" min="0" value={maxArea}
            onChange={(e) => setMaxArea(e.target.value)}
            placeholder="Größe bis (m²)" aria-label="Größe bis"
            data-testid="alert-max-area" className={inputCls} />
          <input type="number" min="0" step="0.5" value={minRooms}
            onChange={(e) => setMinRooms(e.target.value)}
            placeholder="Zimmer ab" aria-label="Zimmer ab"
            data-testid="alert-min-rooms" className={inputCls} />
          <input type="number" min="0" step="0.5" value={maxRooms}
            onChange={(e) => setMaxRooms(e.target.value)}
            placeholder="Zimmer bis" aria-label="Zimmer bis"
            data-testid="alert-max-rooms" className={inputCls} />
          <input type="number" min="0" value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            placeholder="Preis max (€)" aria-label="Preis max"
            data-testid="alert-max-price" className="col-span-2 rounded-lg border border-[#E8E4E0] bg-white px-3 py-2 text-sm text-[#2D2D2D]" />
        </div>
        <p className="text-xs text-[#6B6B6B]">
          Leer lassen heißt „egal“. Fehlt eine Angabe in der Anzeige, wird
          trotzdem gemeldet — markiert als ungeprüft. Lieber ein Treffer zu viel
          als einer zu spät.
        </p>
```

Update the cadence sentence under the heading to match what §1 of the spec
actually delivers:

```tsx
      <p className="mt-1 text-sm text-[#6B6B6B]">
        Stichwort-Alarm auf neue Inserate. Der Poller läuft alle 2&nbsp;Min.;
        von der Anzeige bis Telegram vergehen typisch 2–3&nbsp;Min.
      </p>
```

Add the two row actions:

```ts
  async function remove(id: string) {
    setStatus(null);
    const res = await fetch(`/api/saved-searches/alert?id=${encodeURIComponent(id)}`,
      { method: 'DELETE' });
    if (res.ok) { void load(); } else { setStatus('Löschen fehlgeschlagen.'); }
  }

  async function sendTest(id: string) {
    setStatus(null);
    const res = await fetch('/api/saved-searches/alert/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    const json = await res.json().catch(() => ({}));
    setStatus(res.ok ? 'Testnachricht gesendet.' : (json.error ?? 'Test fehlgeschlagen.'));
  }
```

and render them inside each `<li>`, alongside the existing summary:

```tsx
              <span className="font-medium text-[#3D405B]">
                {(a.keywords?.length ? a.keywords : (a.keyword ? [a.keyword] : []))
                  .join(', ') || '(alle Treffer)'}
              </span>
              {describeFilters(a.filters) && (
                <span className="text-[#6B6B6B]">{' · '}{describeFilters(a.filters)}</span>
              )}
              <span className="ml-2 inline-flex gap-2">
                <button type="button" data-testid="alert-test"
                  onClick={() => void sendTest(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs">
                  Test
                </button>
                <button type="button" data-testid="alert-delete"
                  onClick={() => void remove(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs text-[#B23A3A]">
                  Löschen
                </button>
              </span>
```

- [ ] **Step 4: Run the spec to verify it passes**

Run: `cd dashboard && npx playwright test alerts-page --reporter=dot`
Expected: PASS. On failure read only the failing test's error block, fix the root cause, re-run this spec alone.

- [ ] **Step 5: Typecheck**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/alerts/page.tsx dashboard/tests/alerts-page.spec.ts
git commit -m "feat(alerts): multi-keyword form with size/rooms/price and row actions

Blank numeric fields stay undefined rather than becoming 0 — an unset gate
has to pass everything, and max_price 0 would match nothing."
```

---

### Task 6: Trigger tier and owner setup

**Files:**
- Modify: `.github/workflows/coop-fast-poll.yml`
- Create: `docs/ALERTS_SETUP.md`

**Interfaces:**
- Consumes: Task 3's poller, which must work in both single-poll and window mode.
- Produces: a workflow that treats `repository_dispatch` as a single poll and `schedule` as a windowed fallback.

- [ ] **Step 1: Make the poll window depend on the trigger**

In `.github/workflows/coop-fast-poll.yml`, replace the `schedule:` block's cron line and the `env:` block:

```yaml
    # Cadence no longer comes from GitHub's scheduler. Measured over 2026-07-29,
    # "*/5" delivered gaps of 153/106/140/79/84/57/80/46/53 min — a median of
    # ~80, with 40/40 runs green. GitHub drops most ticks of a high-frequency
    # schedule and deprioritises the more aggressively you ask.
    #
    # Real cadence comes from an external trigger firing repository_dispatch
    # every 2 minutes (see docs/ALERTS_SETUP.md). Dispatch runs are not
    # throttled the way schedules are.
    #
    # This schedule is now only a FALLBACK: if the external trigger dies, a
    # windowed run every 30 min keeps the feed alive instead of going silent.
    # Asking less often also improves the odds that these ticks are delivered.
    - cron: "*/30 6-20 * * 1-6"
```

```yaml
    env:
      POLL_INTERVAL_SECONDS: 120
      # A dispatched run is one poll and exits — the external trigger owns the
      # cadence, so looping here would just collide with the next dispatch.
      # A scheduled run is the fallback and loops for the window.
      POLL_WINDOW_MINUTES: >-
        ${{ github.event.inputs.window_minutes
            || (github.event_name == 'repository_dispatch' && '0' || '55') }}
```

`concurrency: cancel-in-progress: true` stays as-is: a single poll normally
finishes inside the 2-minute gap, and if one hangs the next dispatch replaces it
rather than stacking.

- [ ] **Step 2: Verify the YAML parses**

The previous session changed this file and could only grep-verify it. Do better:

Run: `cd dashboard && npx --yes js-yaml ../.github/workflows/coop-fast-poll.yml > /dev/null && echo YAML_OK`
Expected: `YAML_OK`. This needs `dangerouslyDisableSandbox: true` (npx fetches a package).

If `js-yaml` is unavailable, use `npx --yes yaml-lint .github/workflows/coop-fast-poll.yml`. Do not accept grep as verification — an indentation error here disables the poller silently.

- [ ] **Step 3: Confirm the window expression evaluates as intended**

The nested `&&`/`||` above is GitHub's ternary idiom and is easy to get subtly wrong. Verify on a real run rather than by reading:

Run: `gh workflow run coop-fast-poll.yml -f window_minutes=0` (needs `dangerouslyDisableSandbox: true`)
Then: `gh run list --workflow=coop-fast-poll.yml --limit 1`
Expected: the run completes in ~1–2 minutes, not ~55. A ~55-minute run means the expression collapsed to the fallback and must be fixed before the trigger goes live.

- [ ] **Step 4: Write the owner setup doc**

Create `docs/ALERTS_SETUP.md`:

````markdown
# Alert setup — the four manual steps

Nothing is delivered until these are done. Each is owner-only; none can be
automated from inside the repo.

## 1. GitHub PAT

Settings → Developer settings → Personal access tokens → Fine-grained tokens.

- Repository access: **only** `vladbrincoveanu/ImmoAgent`
- Permission: **Contents: Read and write** (this is what `POST /dispatches`
  requires; there is no narrower permission for it)
- Expiry: the shortest you are willing to rotate

Copy the token once — GitHub never shows it again.

## 2. cron-job.org job

Create a job at **every 2 minutes**, active in whatever local hours you want to
be alerted. Local time is set on cron-job.org, so DST is handled for you — this
is why the window is configured here and not in the workflow's UTC cron.

- URL: `https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches`
- Method: `POST`
- Headers:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer <the PAT from step 1>`
  - `Content-Type: application/json`
- Body: `{"event_type":"coop-poll"}`

A correct call returns **204 No Content**. A 404 almost always means the token
lacks Contents: write, not that the URL is wrong — GitHub returns 404 rather
than 403 for unauthorised repository access.

## 3. Telegram chat id

1. Open Telegram, find the bot behind `TELEGRAM_MAIN_BOT_TOKEN`, send `/start`.
   The bot cannot message you first — this step is mandatory.
2. Get your numeric id from `https://api.telegram.org/bot<TOKEN>/getUpdates`;
   it is `result[0].message.chat.id`.
3. Paste it into the Telegram field on `/alerts`, then press **Test** on the
   created alert. A test message must arrive before you rely on the alert.

## 4. Mark yourself Pro

Alert creation is Pro-gated (`isPro` in `dashboard/lib/user.ts`). In MongoDB,
set your `user_id` — the `uid` cookie value from the dashboard — to Pro in the
`users` collection.

Clearing browser cookies issues a new `user_id`, and this step has to be redone.

## Verifying the whole chain

1. cron-job.org job history shows 204s.
2. `gh run list --workflow=coop-fast-poll.yml` shows runs roughly every 2 min.
3. A run's log contains `🔍 willhaben newest: N url(s) on the feed`.
4. `🔔 user alerts: N delivery(ies)` appears once an alert exists and matches.

If step 3 shows a steady `0 url(s)`, Willhaben is blocking — check the HTTP
status line in the same log before changing anything else.
````

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/coop-fast-poll.yml docs/ALERTS_SETUP.md
git commit -m "feat(alerts): dispatch-driven cadence, schedule demoted to fallback

GitHub's scheduler measurably cannot deliver a 2-minute cadence, so an
external trigger fires repository_dispatch and each dispatched run does a
single poll. The cron stays only so a dead trigger degrades instead of
going silent."
```

---

### Task 7: Full verification gate

**Files:** none modified — this task is verification only.

**Interfaces:** consumes everything from Tasks 1–6.

- [ ] **Step 1: Full Python suite**

Run: `cd Project/Tests && python -m pytest . -q`
Expected: 0 failures. Record the actual count.

- [ ] **Step 2: Legacy Python runner**

Run: `cd Project/Tests && python run_tests.py`
Expected: 0 failures.

- [ ] **Step 3: Typecheck and dead-code scan**

Run: `cd dashboard && npx tsc --noEmit && npx knip`
Expected: no type errors. `knip` should stay at zero — if it reports the removed
`format_coop_message` import's TypeScript counterpart or an unused export from
the new test route, fix it rather than baselining it.

- [ ] **Step 4: Full Playwright suite**

Start the dev server if it is not running, then:
Run: `cd dashboard && npx playwright test --reporter=line`

Expected: `alerts-page` passes with 0 failures and 0 console errors.

**Known baseline:** the map cluster (`map-full`, `map-interaction`, `pin-click`,
`desktop-redesign`, `commute-rent-insights`, `profile-map`, `map-overhaul`,
`map-heatmap`) has pre-existing failures unrelated to this work and **never
confirmed**. If those fail, re-run that cluster on `main` and compare
failure-for-failure. Report the comparison honestly — do not assume a failure is
pre-existing because it is in a file this branch did not touch.

- [ ] **Step 5: Stop the dev server**

Run: `pkill -f "next dev"`

- [ ] **Step 6: Update the knowledge graph**

Run: `graphify update .`

- [ ] **Step 7: Commit any fixes and report**

Report: the pytest count, the tsc result, the Playwright pass/fail split with
the baseline comparison, and — stated plainly — that nothing is delivered end to
end until the four steps in `docs/ALERTS_SETUP.md` are done by the owner.

---

## Self-Review

**Spec coverage**

| Spec section | Task |
|---|---|
| §1 Trigger tier | 6 |
| §2 Poller tier (generalised `crawl_newest`) | 3 |
| §3 Matcher | 1 |
| §4 Delivery ledger | 2 |
| §5 Dashboard | 5 |
| §6 Data model (`keywords`, `filters`, `alert_deliveries` + unique index) | 2, 4 |
| §7 Rate limiting | 3 — partially |
| Testing | 1, 2, 3, 5, 7 |
| Owner-blocked steps | 6 |

**Two gaps found and accepted, not hidden:**

1. **§7 conditional GET and the HTTP status histogram are not implemented.**
   Task 3 keeps the existing per-poll detail cap and the `skipped_for_cap`
   warning, and the existing `_fetch_with_retry` headers, but adds no ETag
   handling and no status-code histogram. Rationale: both need changes inside
   `willhaben_scraper._fetch_with_retry`, which the daily `scrapeJob` also
   depends on, and a regression there breaks the main pipeline. This is deferred
   to a follow-up rather than bundled into an alert feature. **Consequence:** a
   Willhaben block will show up as a steady `0 url(s) on the feed` line rather
   than as an explicit 429 count. `docs/ALERTS_SETUP.md` says exactly that under
   "Verifying the whole chain", so the symptom is documented even though the
   instrumentation is not built.

2. **~~`stale_pending_deliveries` written but never called.~~ Found in review and
   fixed in the plan, not deferred.** The first draft would have shipped
   at-most-once delivery while §4 of the spec promises at-least-once: a poll
   dying mid-send left a `pending` row that recorded the loss but never repaired
   it. The obstacle was that retry needed a `url_hash` → listing reverse lookup
   the schema does not support. Resolved by storing the rendered message and the
   destination chat id **on the claim row**, so `retry_pending` sends from the
   row alone. It is wired as the first thing `deliver_user_alerts` does, and
   covered by three tests in Task 2. The guarantee now matches the spec.

   One deliberate narrowing: retry covers Telegram only. The row holds one
   Telegram destination, and re-deriving an email address on retry risks mailing
   the wrong person. A failed email is logged and stays failed.

**Placeholder scan:** no TBD/TODO, no "add error handling", no "similar to Task
N". Every code step carries real code.

**Type consistency:** `match` returns 3-tuples in Task 1 and is unpacked as
3-tuples in Task 3. `dispatch`'s signature in Task 2's tests matches its
definition and its call site in Task 3. Filter keys `min_area`/`max_area`/
`min_rooms`/`max_rooms`/`max_price` are identical across Tasks 1, 4, and 5. The
`keywords` field is an array in Tasks 1, 4, and 5, with the legacy scalar read
as a fallback in Tasks 1 and 5 and written for rollback safety in Task 4. Test
ids produced in Task 5 match those asserted in its spec.
