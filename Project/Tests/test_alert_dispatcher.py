"""Delivery must be exactly-once as the user sees it, and must survive a poll
that dies mid-send.

The ledger is what makes both true: a claim is atomic, so two concurrent polls
cannot both send, and a claimed-but-unsent row is retried by the next poll.
"""
import logging
import os
import sys
import time
from unittest.mock import MagicMock

import pymongo

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.alert_dispatcher import (  # noqa: E402
    UNVERIFIED_PREFIX, dispatch, retry_pending,
)
from Application.alert_email import build_alert_email  # noqa: E402
from Integration.mongodb_handler import MongoDBHandler  # noqa: E402
from run_coop import deliver_user_alerts  # noqa: E402


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
        self.leases = {}
        self.mark_calls = []
        self.mark_results = {}

    def claim_delivery(self, alert_id, url_hash, chat_id=None, message=None,
                       email=None, email_subject=None, email_body=None):
        key = (alert_id, url_hash)
        if key in self.rows:
            return False
        self.rows[key] = {"status": "pending", "alert_id": alert_id,
                          "url_hash": url_hash, "chat_id": chat_id,
                          "message": message, "email": email,
                          "email_subject": email_subject,
                          "email_body": email_body,
                          "telegram_sent": not bool(chat_id),
                          "email_sent": not bool(email)}
        return True

    def mark_delivery_sent(self, alert_id, url_hash):
        self.mark_calls.append(("legacy", alert_id, url_hash))
        if self.mark_results.get("telegram") is False:
            return False
        self.rows[(alert_id, url_hash)]["status"] = "sent"
        return True

    def mark_delivery_channel_sent(self, alert_id, url_hash, channel):
        self.mark_calls.append((channel, alert_id, url_hash))
        if self.mark_results.get(channel) is False:
            return False
        row = self.rows[(alert_id, url_hash)]
        field = {"telegram": "telegram_sent", "email": "email_sent"}[channel]
        row[field] = True
        self.leases.pop(((alert_id, url_hash), channel), None)
        if ((not row["chat_id"] or row["telegram_sent"])
                and (not row["email"] or row["email_sent"])):
            row["status"] = "sent"
        return True

    def claim_pending_delivery_channel(self, alert_id, url_hash, channel,
                                        lease_seconds=60):
        row = self.rows[(alert_id, url_hash)]
        field = {"telegram": "telegram_sent", "email": "email_sent"}[channel]
        lease_key = ((alert_id, url_hash), channel)
        if row.get(field, False) or self.leases.get(lease_key, 0) > time.monotonic():
            return False
        self.leases[lease_key] = time.monotonic() + lease_seconds
        return True

    def release_delivery_channel(self, alert_id, url_hash, channel):
        self.leases.pop(((alert_id, url_hash), channel), None)
        return True

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


def test_email_only_dispatch_sends_and_marks_email_sent():
    handler, sent = _Handler(), []
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}

    ok = dispatch(
        alert, _L(), False, handler, token=None,
        send_email=lambda address, listing: sent.append(address) or True,
    )

    assert ok is True
    assert sent == ["u@example.at"]
    row = next(iter(handler.rows.values()))
    assert row["email"] == "u@example.at"
    assert row["email_subject"] == "Neue passende Wohnungsanzeige"
    assert row["email_body"]
    assert row["email_sent"] is True
    assert row["status"] == "sent"


def test_email_failure_leaves_only_email_pending():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}

    assert dispatch(
        alert, _L(), False, handler, token=None,
        send_email=lambda address, listing: False,
    ) is False

    row = next(iter(handler.rows.values()))
    assert row["status"] == "pending"
    assert row["email_sent"] is False


def test_pending_email_is_retried_from_stored_payload():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    dispatch(alert, _L(), False, handler, token=None,
             send_email=lambda address, listing: False)
    row = next(iter(handler.rows.values()))

    sent = []
    assert retry_pending(
        handler, token=None,
        send_email=lambda address, subject, body: sent.append(
            (address, subject, body)) or True,
    ) == 1

    assert sent == [("u@example.at", row["email_subject"], row["email_body"])]
    assert row["email_sent"] is True
    assert row["status"] == "sent"


def test_marker_failure_keeps_successful_email_pending_and_uncounted():
    handler = _Handler()
    handler.mark_results["email"] = False
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}

    assert dispatch(
        alert, _L(), False, handler, token=None,
        send_email=lambda address, listing: True,
    ) is False

    row = next(iter(handler.rows.values()))
    assert row["status"] == "pending"
    assert row["email_sent"] is False


def test_second_retry_worker_cannot_claim_channel_with_active_lease():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    dispatch(alert, _L(), False, handler, token=None,
             send_email=lambda address, listing: False)
    row = next(iter(handler.rows.values()))

    assert handler.claim_pending_delivery_channel(
        row["alert_id"], row["url_hash"], "email", lease_seconds=60
    ) is True
    sent = []
    assert retry_pending(
        handler, token=None,
        send_email=lambda address, subject, body: sent.append(address) or True,
    ) == 0
    assert sent == []
    assert row["status"] == "pending"


def test_expired_channel_lease_can_be_claimed_again():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    dispatch(alert, _L(), False, handler, token=None,
             send_email=lambda address, listing: False)
    row = next(iter(handler.rows.values()))
    lease_key = ((row["alert_id"], row["url_hash"]), "email")
    handler.leases[lease_key] = time.monotonic() - 1

    assert handler.claim_pending_delivery_channel(
        row["alert_id"], row["url_hash"], "email", lease_seconds=60
    ) is True


def test_legacy_pending_row_without_chat_id_stays_pending():
    handler = _Handler()
    handler.rows[("legacy", "h1")] = {
        "alert_id": "legacy", "url_hash": "h1", "chat_id": None,
        "message": "old Telegram message", "status": "pending",
    }

    sent = []
    assert retry_pending(
        handler, token="t",
        send_telegram=lambda chat, message: sent.append(chat) or True,
    ) == 0
    assert sent == []
    assert handler.rows[("legacy", "h1")]["status"] == "pending"
    assert handler.mark_calls == []


def test_alert_email_body_is_neutral_and_can_flag_unverified_values():
    subject, body = build_alert_email(_L(), unverified=True)

    assert subject == "Neue passende Wohnungsanzeige"
    assert "Private Genossenschafts-Weitergabe" not in body
    assert UNVERIFIED_PREFIX.strip() in body


def test_alert_email_body_tolerates_malformed_numeric_values():
    listing = _L(area_m2="unknown", rooms=object(), price_total=object())

    _, body = build_alert_email(listing)

    assert "unknown" not in body
    assert body


def test_dispatch_malformed_listing_payload_never_raises():
    handler = _Handler()
    listing = _L(title=object())
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}

    assert dispatch(
        alert, listing, False, handler, token=None,
        send_email=lambda address, value: True,
    ) is False
    assert handler.rows == {}


def test_dispatch_malformed_numeric_payload_never_raises():
    handler = _Handler()
    listing = _L(area_m2="unknown", rooms=object(), price_total=object())
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}

    assert dispatch(
        alert, listing, False, handler, token=None,
        send_email=lambda address, value: True,
    ) is True


def test_default_email_sender_uses_stored_unverified_payload(monkeypatch):
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    sent = []

    def send(address, listing, unverified=False):
        sent.append(build_alert_email(listing, unverified)[1])
        return True

    monkeypatch.setattr("Application.alert_email.send_alert_email", send)
    assert dispatch(alert, _L(), True, handler, token=None) is True
    row = next(iter(handler.rows.values()))
    assert sent == [row["email_body"]]


def test_mongo_claim_duplicate_is_distinct_from_operational_failure(caplog):
    class _Collection:
        def __init__(self, error):
            self.error = error

        def insert_one(self, document):
            raise self.error

    handler = object.__new__(MongoDBHandler)
    duplicate = _Collection(pymongo.errors.DuplicateKeyError("duplicate"))
    handler.db = {"alert_deliveries": duplicate}
    assert handler.claim_delivery("a", "h") is False

    operational = _Collection(pymongo.errors.OperationFailure("database down"))
    handler.db = {"alert_deliveries": operational}
    with caplog.at_level(logging.ERROR):
        assert handler.claim_delivery("a", "h") is False
    assert "delivery claim failed" in caplog.text


def test_mongo_delivery_index_fails_closed(caplog):
    class _Collection:
        def create_index(self, fields, unique):
            raise pymongo.errors.OperationFailure("index unavailable")

    handler = object.__new__(MongoDBHandler)
    handler.db = {"alert_deliveries": _Collection()}
    with caplog.at_level(logging.ERROR):
        assert handler.ensure_delivery_index() is False
    assert "delivery index setup failed" in caplog.text


def test_mongo_channel_lease_uses_atomic_expiry_filter():
    class _Collection:
        def __init__(self):
            self.filter = None
            self.update = None

        def find_one_and_update(self, filter_doc, update_doc, **kwargs):
            self.filter = filter_doc
            self.update = update_doc
            return {"alert_id": "a", "url_hash": "h"}

    collection = _Collection()
    handler = object.__new__(MongoDBHandler)
    handler.db = {"alert_deliveries": collection}

    assert handler.claim_pending_delivery_channel("a", "h", "email") is True
    assert collection.filter["email_sent"] == {"$ne": True}
    assert collection.filter["email"] == {"$exists": True, "$nin": [None, ""]}
    assert len(collection.filter["$or"]) == 3
    assert "email_lease_until" in collection.update["$set"]


def test_delivery_stops_when_index_is_unavailable():
    handler = MagicMock()
    handler.get_active_alerts.return_value = [_ALERT]
    handler.ensure_delivery_index.return_value = False

    assert deliver_user_alerts(handler, [_L()]) == 0
    handler.stale_pending_deliveries.assert_not_called()
    handler.claim_delivery.assert_not_called()


def test_telegram_success_does_not_hide_email_failure():
    handler, telegram, email = _Handler(), [], []
    alert = {**_ALERT, "email": "u@example.at"}

    assert dispatch(
        alert, _L(), False, handler, token="t",
        send_telegram=lambda chat, message: telegram.append(chat) or True,
        send_email=lambda address, listing: email.append(address) or False,
    ) is True

    row = next(iter(handler.rows.values()))
    assert telegram == ["-100123456"]
    assert email == ["u@example.at"]
    assert row["status"] == "pending"
    assert row["telegram_sent"] is True
    assert row["email_sent"] is False


def test_retry_after_telegram_success_sends_only_email():
    handler = _Handler()
    alert = {**_ALERT, "email": "u@example.at"}
    dispatch(
        alert, _L(), False, handler, token="t",
        send_telegram=lambda chat, message: True,
        send_email=lambda address, listing: False,
    )

    telegram, email = [], []
    assert retry_pending(
        handler, token="t",
        send_telegram=lambda chat, message: telegram.append(chat) or True,
        send_email=lambda address, subject, body: email.append(address) or True,
    ) == 1

    assert telegram == []
    assert email == ["u@example.at"]


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
