import os
import sys
from unittest.mock import MagicMock

from pymongo.errors import DuplicateKeyError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Integration.mongodb_handler import MongoDBHandler  # noqa: E402


def _handler():
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.db = MagicMock()
    return handler


def test_claim_delivery_inserts_pending_row():
    handler = _handler()
    handler.db["alert_deliveries"].find_one_and_update.return_value = None

    assert handler.claim_delivery("alert-1", "url-1", "-1001", "message") is True

    handler.db["alert_deliveries"].find_one_and_update.assert_called_once()
    row = handler.db["alert_deliveries"].find_one_and_update.call_args.args[1][
        "$setOnInsert"
    ]
    assert row["status"] == "pending"
    assert row["message"] == "message"


def test_duplicate_delivery_claim_is_not_owned_twice():
    handler = _handler()
    handler.db["alert_deliveries"].find_one_and_update.side_effect = DuplicateKeyError(
        "duplicate"
    )

    assert handler.claim_delivery("alert-1", "url-1", "-1001", "message") is False


def test_stale_pending_deliveries_returns_rows():
    handler = _handler()
    expected = [{"alert_id": "alert-1", "url_hash": "url-1"}]
    handler.db["alert_deliveries"].find.return_value = expected

    assert handler.stale_pending_deliveries() == expected


def test_active_alerts_accepts_legacy_and_general_feed_kinds():
    handler = _handler()
    handler.db["alert_subscriptions"].find.return_value = []

    assert handler.get_active_alerts(["coop_private", "keyword"]) == []

    query = handler.db["alert_subscriptions"].find.call_args.args[0]
    assert query == {
        "kind": {"$in": ["coop_private", "keyword"]},
        "$or": [
            {"telegram_chat_id": {"$exists": True, "$nin": [None, ""]}},
            {
                "email": {"$exists": True, "$nin": [None, ""]},
                "confirmed": True,
            },
        ],
    }


def test_active_alerts_keeps_telegram_channel_when_email_is_unconfirmed():
    handler = _handler()
    handler.db["alert_subscriptions"].find.return_value = []

    handler.get_active_alerts("keyword")

    query = handler.db["alert_subscriptions"].find.call_args.args[0]
    assert query == {
        "kind": {"$in": ["keyword"]},
        "$or": [
            {"telegram_chat_id": {"$exists": True, "$nin": [None, ""]}},
            {
                "email": {"$exists": True, "$nin": [None, ""]},
                "confirmed": True,
            },
        ],
    }
