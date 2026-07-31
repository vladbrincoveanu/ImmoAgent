"""Delivery must be exactly-once as the user sees it, and must survive a poll
that dies mid-send.

The ledger is what makes both true: a claim is atomic, so two concurrent polls
cannot both send, and a claimed-but-unsent row is retried by the next poll.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.alert_dispatcher import (  # noqa: E402
    UNVERIFIED_PREFIX, dispatch, retry_pending,
)


class _L:
    def __init__(self, url="https://www.willhaben.at/iad/immobilien/d/mietwohnungen/wien/wien-1100-favoriten/test-1234567/",
                 title="Nachmieter", area_m2=70.0, rooms=3.0, price_total=800.0):
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
        self.bautraeger = None
        self.total_monthly_cost = None


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


# --- exactly-once -------------------------------------------------------------

def test_first_dispatch_sends_and_marks_sent():
    handler, sent = _Handler(), []
    ok = dispatch(_ALERT, _L(), False, handler, token="t",
                  send_telegram=lambda chat, msg: sent.append((chat, msg)) or True)
    assert ok is True
    assert len(sent) == 1
    assert _statuses(handler) == ["sent"]


def test_second_dispatch_of_same_pair_sends_nothing():
    handler, sent = _Handler(), []
    def send(chat, msg):
        sent.append((chat, msg))
        return True
    listing = _L()
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    assert len(sent) == 1


def test_different_alerts_each_get_the_same_listing():
    handler, sent = _Handler(), []
    def send(chat, msg):
        sent.append((chat, msg))
        return True
    listing = _L()
    dispatch(_ALERT, listing, False, handler, token="t", send_telegram=send)
    dispatch({**_ALERT, "_id": "a2"}, listing, False, handler, token="t",
             send_telegram=send)
    assert len(sent) == 2


def test_alert_with_no_channel_claims_nothing():
    handler = _Handler()
    silent = {**_ALERT, "telegram_chat_id": None, "email": None}
    assert dispatch(silent, _L(), False, handler, token="t",
                    send_telegram=lambda c, m: True) is False
    assert handler.rows == {}


def test_invalid_url_is_never_sent():
    """Project rule: URL validation is mandatory before anything is sent."""
    handler = _Handler()
    assert dispatch(_ALERT, _L(url="not-a-url"), False, handler, token="t",
                    send_telegram=lambda c, m: True) is False
    assert handler.rows == {}


# --- crash recovery -----------------------------------------------------------

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
    url_hash -> listing reverse lookup that does not exist."""
    handler = _Handler()

    def boom(chat, msg):
        raise RuntimeError("x")

    dispatch(_ALERT, _L(), True, handler, token="t", send_telegram=boom)
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


# --- message shape ------------------------------------------------------------

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
    """The title is unbounded scraped text and DOES reach the message, so this
    exercises the truncation rather than passing by construction."""
    handler, sent = _Handler(), []
    listing = _L(title="Wohnung " * 2000)
    dispatch(_ALERT, listing, True, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert len(sent[0]) <= 4096
    assert sent[0].endswith("…")


def test_free_text_is_html_escaped():
    """Telegram's HTML parser rejects a body containing a bare & or <, and the
    whole message is then silently not delivered."""
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(title="Küche & Bad <neu>"), False, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert "&amp;" in sent[0] and "&lt;neu&gt;" in sent[0]


def test_message_is_not_framed_as_a_coop_unless_it_is_one():
    """The alert feed is the whole rental list now — labelling every hit as a
    Genossenschaft would be wrong on most of them."""
    handler, sent = _Handler(), []
    listing = _L()
    listing.coop_kind = None
    dispatch(_ALERT, listing, False, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert "Weitergabe" not in sent[0]


def test_private_transfer_is_labelled():
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(), False, handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert "Private Weitergabe" in sent[0]


def test_unknown_numbers_render_as_question_marks():
    handler, sent = _Handler(), []
    dispatch(_ALERT, _L(area_m2=None, rooms=None, price_total=None), True,
             handler, token="t",
             send_telegram=lambda chat, msg: sent.append(msg) or True)
    assert "? Zi" in sent[0] and "? m²" in sent[0]
