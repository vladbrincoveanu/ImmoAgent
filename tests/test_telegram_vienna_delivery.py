import math
from unittest.mock import Mock, patch

import pymongo
import pytest

from Application.telegram_delivery import (
    VIENNA_CHANNEL,
    VIENNA_MIN_AREA_M2,
    VIENNA_MIN_ROOMS,
    send_vienna_listings,
    vienna_filter_reason,
)
from Integration.mongodb_handler import MongoDBHandler


def listing(**overrides):
    result = {
        "url": "https://example.test/listing-1",
        "title": "Testwohnung",
        "area_m2": 75.0,
        "rooms": 3.0,
        "score": 41.0,
    }
    result.update(overrides)
    return result


def test_vienna_policy_constants():
    assert VIENNA_CHANNEL == "vienna"
    assert VIENNA_MIN_AREA_M2 == 75.0
    assert VIENNA_MIN_ROOMS == 3.0


def test_area_boundary_is_inclusive():
    assert vienna_filter_reason(listing(area_m2=74.99), 40.0) is not None
    assert vienna_filter_reason(listing(area_m2=75.0), 40.0) is None


def test_rooms_boundary_is_inclusive():
    assert vienna_filter_reason(listing(rooms=2.99), 40.0) is not None
    assert vienna_filter_reason(listing(rooms=3.0), 40.0) is None


@pytest.mark.parametrize("field", ["area_m2", "rooms"])
@pytest.mark.parametrize(
    "invalid_value",
    [None, "75", "three", math.nan, math.inf, -math.inf],
)
def test_invalid_measurements_reject(field, invalid_value):
    assert vienna_filter_reason(listing(**{field: invalid_value}), 40.0) is not None


def test_missing_area_key_rejects():
    value = listing()
    value.pop("area_m2")

    assert vienna_filter_reason(value, 40.0) is not None


def test_missing_rooms_key_rejects():
    value = listing()
    value.pop("rooms")

    assert vienna_filter_reason(value, 40.0) is not None


def test_score_threshold_is_strictly_greater():
    assert vienna_filter_reason(listing(score=40.0), 40.0) is not None
    assert vienna_filter_reason(listing(score=40.01), 40.0) is None


def test_missing_url_rejects():
    candidate = listing()
    del candidate["url"]

    assert vienna_filter_reason(candidate, 40.0) is not None


def test_malformed_candidate_does_not_abort_delivery_batch():
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = True

    assert send_vienna_listings(
        [object(), listing()],
        bot,
        mongo,
        url_validator=lambda url: True,
    ) == 1

    bot.send_property_notification.assert_called_once_with(listing())
    mongo.claim_listing_delivery.assert_called_once()
    mongo.mark_listing_delivery_sent.assert_called_once()


def test_invalid_candidate_does_not_poison_same_content_dedup():
    first = listing(url="https://example.test/invalid")
    second = listing(url="https://example.test/valid")
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = True
    url_validator = Mock(side_effect=[False, True])

    assert send_vienna_listings(
        [first, second],
        bot,
        mongo,
        url_validator=url_validator,
    ) == 1

    mongo.mark_url_invalid.assert_called_once_with(first["url"])
    mongo.claim_listing_delivery.assert_called_once()
    bot.send_property_notification.assert_called_once_with(second)


def test_claim_listing_delivery_uses_atomic_route_query_and_lease():
    collection = Mock()
    collection.find_one_and_update.side_effect = [{"_id": "claimed"}, None]
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.claim_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1"
    ) is True
    assert mongo.claim_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1"
    ) is False

    query, update = collection.find_one_and_update.call_args_list[0].args[:2]
    identity = next(part for part in query["$and"] if "$or" in part)
    assert {"url": "https://example.test/listing-1"} in identity["$or"]
    assert {"content_fingerprint": "fingerprint-1"} in identity["$or"]

    state = next(part for part in query["$and"] if "telegram_delivery.vienna.state" in part)
    assert state == {
        "telegram_delivery.vienna.state": {"$nin": ["sent", "uncertain"]}
    }

    expiry = next(part for part in query["$and"] if "$or" in part and part != identity)
    expiry_conditions = expiry["$or"]
    assert {"telegram_delivery.vienna.claim_until": {"$exists": False}} in expiry_conditions
    assert {"telegram_delivery.vienna.claim_until": None} in expiry_conditions
    assert any(
        (condition.get("telegram_delivery.vienna.claim_until") or {}).get("$lte")
        is not None
        for condition in expiry_conditions
    )
    assert update["$set"]["telegram_delivery.vienna.state"] == "claimed"
    assert collection.find_one_and_update.call_args_list[0].kwargs["return_document"] == (
        pymongo.ReturnDocument.AFTER
    )


def test_listing_delivery_release_and_mark_update_route_and_legacy_state():
    collection = Mock()
    collection.update_one.return_value = Mock(modified_count=1)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.release_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1"
    ) is True
    with patch("Integration.mongodb_handler.time.time", return_value=1234.5):
        assert mongo.mark_listing_delivery_sent(
            "https://example.test/listing-1", "fingerprint-1"
        ) is True

    _, release_update = collection.update_one.call_args_list[0].args[:2]
    assert release_update["$set"]["telegram_delivery.vienna.state"] == "failed"
    assert release_update["$unset"] == {
        "telegram_delivery.vienna.claim_until": "",
        "telegram_delivery.vienna.claimed_at": "",
    }

    _, sent_update = collection.update_one.call_args_list[1].args[:2]
    assert sent_update["$set"] == {
        "telegram_delivery.vienna.state": "sent",
        "telegram_delivery.vienna.sent_at": 1234.5,
        "sent_to_telegram": True,
        "sent_to_telegram_at": 1234.5,
    }
    assert sent_update["$unset"] == {"telegram_delivery.vienna.claim_until": ""}


def test_quarantine_listing_delivery_sets_uncertain_route_state():
    collection = Mock()
    collection.update_one.return_value = Mock(modified_count=1)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    with patch("Integration.mongodb_handler.time.time", return_value=9876.5):
        assert mongo.quarantine_listing_delivery(
            "https://example.test/listing-1", "fingerprint-1"
        ) is True

    _, update = collection.update_one.call_args.args[:2]
    assert update["$set"] == {
        "telegram_delivery.vienna.state": "uncertain",
        "telegram_delivery.vienna.uncertain_at": 9876.5,
    }
    assert update["$unset"] == {"telegram_delivery.vienna.claim_until": ""}


def test_vienna_delivery_calls_real_handler_delivery_methods():
    collection = Mock()
    collection.find_one_and_update.return_value = {"_id": "claimed"}
    collection.update_one.return_value = Mock(modified_count=1)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = True

    assert send_vienna_listings(
        [listing()], bot, mongo, url_validator=lambda url: True
    ) == 1
