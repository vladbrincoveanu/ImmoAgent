import inspect
import math
import uuid
from unittest.mock import MagicMock, Mock, patch

import pymongo
import pytest

from Application.helpers.listing_validator import compute_content_fingerprint
from Application.telegram_delivery import (
    COOP_MIN_AREA_M2,
    COOP_MIN_ROOMS,
    VIENNA_CHANNEL,
    VIENNA_MIN_AREA_M2,
    VIENNA_MIN_ROOMS,
    coop_filter_reason,
    preserve_delivery_state,
    send_coop_listing,
    send_vienna_listings,
    vienna_filter_reason,
)
from Domain.listing import Listing
from Domain.location import Coordinates
from Domain.sources import Source
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


def coop_listing(**overrides):
    value = {
        "url": "https://example.test/coop-1",
        "title": "Neue Genossenschaft",
        "area_m2": 75.0,
        "rooms": 3.0,
    }
    value.update(overrides)
    return value


def test_coop_policy_uses_inclusive_area_and_room_boundaries():
    assert COOP_MIN_AREA_M2 == 75.0
    assert COOP_MIN_ROOMS == 3.0
    assert coop_filter_reason(coop_listing(area_m2=75.0, rooms=3.0)) is None
    assert coop_filter_reason(coop_listing(area_m2=74.99)) is not None
    assert coop_filter_reason(coop_listing(rooms=2.99)) is not None


@pytest.mark.parametrize("field", ["area_m2", "rooms"])
@pytest.mark.parametrize("value", [None, "75", True, math.nan, math.inf, -math.inf])
def test_coop_policy_rejects_missing_invalid_and_nonfinite_measurements(field, value):
    assert coop_filter_reason(coop_listing(**{field: value})) is not None


@pytest.mark.parametrize("field", ["area_m2", "rooms"])
def test_coop_policy_rejects_missing_measurements(field):
    candidate = coop_listing()
    del candidate[field]

    assert coop_filter_reason(candidate) is not None


def test_coop_delivery_claims_before_sending_and_marks_success():
    bot = Mock()
    mongo = Mock()
    events = []
    mongo.claim_listing_delivery.side_effect = lambda *args, **kwargs: events.append("claim") or True
    bot.send_message.side_effect = lambda *args, **kwargs: events.append("send") or True
    mongo.mark_listing_delivery_sent.side_effect = lambda *args, **kwargs: events.append("mark") or True

    assert send_coop_listing(
        coop_listing(), bot, mongo, "coop",
        url_validator=lambda url: events.append("url") or True,
        message_formatter=lambda listing: events.append("format") or "message",
    ) is True
    assert events == ["url", "claim", "format", "send", "mark"]
    bot.send_message.assert_called_once_with("message")


def test_coop_delivery_skips_before_bot_when_claim_is_lost():
    bot = Mock()
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = False

    assert send_coop_listing(coop_listing(), bot, mongo, "coop", url_validator=lambda _: True) is False
    bot.send_message.assert_not_called()


@pytest.mark.parametrize("send_result", [False, RuntimeError("telegram uncertain")])
def test_coop_delivery_quarantines_any_unconfirmed_attempt(send_result):
    bot = Mock()
    events = []
    if isinstance(send_result, Exception):
        def send_with_error(*args, **kwargs):
            events.append("send")
            raise send_result

        bot.send_message.side_effect = send_with_error
    else:
        bot.send_message.side_effect = lambda *args, **kwargs: events.append("send") or send_result
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.quarantine_listing_delivery.side_effect = lambda *args, **kwargs: events.append("quarantine") or True

    assert send_coop_listing(coop_listing(), bot, mongo, "coop", url_validator=lambda _: True) is False
    bot.send_message.assert_called_once()
    mongo.release_listing_delivery.assert_not_called()
    mongo.quarantine_listing_delivery.assert_called_once()
    mongo.mark_listing_delivery_sent.assert_not_called()
    assert events == ["send", "quarantine"]


def test_vienna_policy_constants():
    assert VIENNA_CHANNEL == "vienna"
    assert VIENNA_MIN_AREA_M2 == 75.0
    assert VIENNA_MIN_ROOMS == 3.0


def test_preserve_delivery_state_keeps_existing_state_and_fresh_listing_fields():
    existing = {
        "telegram_delivery": {"vienna": {"state": "sent"}},
        "sent_to_telegram": True,
        "sent_to_telegram_at": 1234.5,
        "url_is_valid": True,
        "builder_url": "",
        "image_url": "https://example.test/old-image.jpg",
        "image_probe_v": 2,
    }
    replacement = {
        "title": "Fresh title",
        "telegram_delivery": {},
        "sent_to_telegram": False,
        "sent_to_telegram_at": None,
        "url_is_valid": False,
        "builder_url": None,
        "image_url": None,
        "image_probe_v": None,
    }
    replacement_before = replacement.copy()

    result = preserve_delivery_state(existing, replacement)

    assert result is not replacement
    assert result["telegram_delivery"] == existing["telegram_delivery"]
    assert result["sent_to_telegram"] is True
    assert result["sent_to_telegram_at"] == 1234.5
    assert result["url_is_valid"] is True
    assert result["title"] == "Fresh title"
    assert result["builder_url"] == ""
    assert result["image_url"] == "https://example.test/old-image.jpg"
    assert result["image_probe_v"] == 2
    assert replacement == replacement_before


def test_preserve_delivery_state_prefers_fresh_coop_resolved_values():
    existing = {
        "builder_url": "https://example.test/old-builder",
        "image_url": "https://example.test/old-image.jpg",
        "image_probe_v": 2,
    }
    replacement = {
        "title": "Fresh title",
        "builder_url": "https://example.test/fresh-builder",
        "image_url": "https://example.test/fresh-image.jpg",
        "image_probe_v": 3,
    }

    result = preserve_delivery_state(existing, replacement)

    assert result["title"] == "Fresh title"
    assert result["builder_url"] == "https://example.test/fresh-builder"
    assert result["image_url"] == "https://example.test/fresh-image.jpg"
    assert result["image_probe_v"] == 3


def test_coop_replacement_preserves_telegram_delivery_state():
    collection = Mock()
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection
    existing = {
        "_id": "listing-id",
        "telegram_delivery": {"vienna": {"state": "sent"}},
        "sent_to_telegram": True,
        "sent_to_telegram_at": 1234.5,
        "url_is_valid": True,
        "builder_url": "",
        "image_url": "https://example.test/old-image.jpg",
        "image_probe_v": 2,
    }
    replacement = {
        "title": "Fresh title",
        "telegram_delivery": {},
        "sent_to_telegram": False,
        "sent_to_telegram_at": None,
        "url_is_valid": False,
        "builder_url": None,
        "image_url": None,
        "image_probe_v": None,
    }
    replacement_before = replacement.copy()

    mongo._replace_preserving_state(existing, replacement)

    replaced = collection.replace_one.call_args.args[1]
    assert replaced["telegram_delivery"] == existing["telegram_delivery"]
    assert replaced["sent_to_telegram"] is True
    assert replaced["sent_to_telegram_at"] == 1234.5
    assert replaced["url_is_valid"] is True
    assert replaced["title"] == "Fresh title"
    assert replaced["builder_url"] == ""
    assert replaced["image_url"] == "https://example.test/old-image.jpg"
    assert replaced["image_probe_v"] == 2
    assert replacement == replacement_before


def test_main_cross_source_migration_replaces_fresh_listing_and_preserves_state():
    from Application import main as main_module

    collection = Mock()
    existing_xsrc = {
        "_id": "willhaben-id",
        "url": "https://willhaben.test/old",
        "coop_source": "willhaben",
        "telegram_delivery": {"vienna": {"state": "sent"}},
        "sent_to_telegram": True,
        "sent_to_telegram_at": 1234.5,
        "url_is_valid": True,
        "builder_url": "https://example.test/old-builder",
        "image_url": "https://example.test/old-image.jpg",
        "image_probe_v": 2,
        "area_m2": 55.0,
        "special_features": ["old feature"],
    }
    collection.find_one.return_value = existing_xsrc
    database = MagicMock()
    database.__getitem__.return_value = collection
    client = MagicMock()
    client.__getitem__.return_value = database
    mongo_handler = Mock()
    fresh = Listing(
        url="https://builder.test/fresh",
        source=Source.GENOSSENSCHAFT,
        title="Fresh title",
        address="Musterstraße 1, 1100 Wien",
        price_total=1200.0,
        area_m2=70.0,
        rooms=3.0,
        coordinates=Coordinates(48.2, 16.3),
        source_enum=Source.GENOSSENSCHAFT,
        is_genossenschaft=True,
        bautraeger="ÖVW",
        coop_source="bautraeger_direct",
        special_features=["fresh feature"],
    )

    with patch("Integration.mongodb_handler.MongoDBHandler", return_value=mongo_handler), \
            patch.object(main_module.pymongo, "MongoClient", return_value=client):
        assert main_module.save_listings_to_mongodb([fresh]) == 0

    mongo_handler.close.assert_called_once()
    client.close.assert_called_once()
    collection.update_one.assert_not_called()
    collection.replace_one.assert_called_once()
    replaced = collection.replace_one.call_args.args[1]
    assert replaced["_id"] == "willhaben-id"
    assert replaced["url"] == "https://builder.test/fresh"
    assert replaced["title"] == "Fresh title"
    assert replaced["area_m2"] == 70.0
    assert replaced["special_features"] == ["fresh feature"]
    assert replaced["coordinates"] == {"lat": 48.2, "lon": 16.3}
    assert replaced["telegram_delivery"] == existing_xsrc["telegram_delivery"]
    assert replaced["sent_to_telegram"] is True
    assert replaced["sent_to_telegram_at"] == 1234.5
    assert replaced["url_is_valid"] is True
    assert replaced["builder_url"] == "https://example.test/old-builder"
    assert replaced["image_url"] == "https://example.test/old-image.jpg"
    assert replaced["image_probe_v"] == 2


def test_insert_listing_cross_source_migration_replaces_without_mutating_input():
    collection = Mock()
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection
    existing_xsrc = {
        "_id": "willhaben-id",
        "url": "https://willhaben.test/old",
        "coop_source": "willhaben",
        "telegram_delivery": {"vienna": {"state": "sent"}},
        "area_m2": 55.0,
        "price_total": 999.0,
        "special_features": ["old feature"],
        "coordinates": {"lat": 48.1, "lon": 16.2},
        "builder_url": "https://example.test/old-builder",
        "image_url": "https://example.test/old-image.jpg",
        "image_probe_v": 2,
    }
    collection.find_one.return_value = existing_xsrc
    incoming = {
        "url": "https://builder.test/fresh",
        "title": "Fresh title",
        "source": "genossenschaft",
        "source_enum": "genossenschaft",
        "is_genossenschaft": True,
        "coop_source": "bautraeger_direct",
        "bautraeger": "ÖVW",
        "address": "Musterstraße 1, 1100 Wien",
        "rooms": 3.0,
        "area_m2": 70.0,
        "price_total": 1200.0,
        "buyable": False,
        "special_features": ["fresh feature"],
        "coordinates": {"lat": 48.2, "lon": 16.3},
        "builder_url": "https://example.test/fresh-builder",
        "image_url": "https://example.test/fresh-image.jpg",
        "image_probe_v": None,
        "telegram_delivery": {},
    }
    incoming_before = incoming.copy()

    assert mongo.insert_listing(incoming) is True

    collection.update_one.assert_not_called()
    collection.replace_one.assert_called_once()
    replaced = collection.replace_one.call_args.args[1]
    assert replaced["_id"] == "willhaben-id"
    assert replaced["url"] == "https://builder.test/fresh"
    assert replaced["title"] == "Fresh title"
    assert replaced["content_fingerprint"] == compute_content_fingerprint(incoming)
    assert replaced["area_m2"] == 70.0
    assert replaced["price_total"] == 1200.0
    assert replaced["special_features"] == ["fresh feature"]
    assert replaced["coordinates"] == {"lat": 48.2, "lon": 16.3}
    assert replaced["builder_url"] == "https://example.test/fresh-builder"
    assert replaced["image_url"] == "https://example.test/fresh-image.jpg"
    assert replaced["image_probe_v"] == 2
    assert replaced["telegram_delivery"] == existing_xsrc["telegram_delivery"]
    assert incoming == incoming_before
    assert "content_fingerprint_xsrc" not in incoming
    assert "content_fingerprint" not in incoming
    assert "_id" not in incoming


def test_upsert_coop_listing_does_not_mutate_input_fingerprints():
    collection = Mock()
    collection.find_one.return_value = None
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection
    incoming = {
        "url": "https://builder.test/fresh",
        "title": "Fresh title",
        "source": "genossenschaft",
        "source_enum": "genossenschaft",
        "is_genossenschaft": True,
        "coop_source": "bautraeger_direct",
        "bautraeger": "ÖVW",
        "address": "Musterstraße 1, 1100 Wien",
        "rooms": 3.0,
        "area_m2": 70.0,
        "price_total": 1200.0,
        "buyable": False,
    }
    incoming_before = incoming.copy()

    assert mongo.upsert_coop_listing(incoming) == "inserted"

    inserted = collection.insert_one.call_args.args[0]
    assert "content_fingerprint_xsrc" in inserted
    assert "content_fingerprint" in inserted
    assert incoming == incoming_before
    assert "content_fingerprint_xsrc" not in incoming
    assert "content_fingerprint" not in incoming


def test_resolve_vienna_telegram_bot_uses_vienna_config_without_main_fallback():
    from Application import main as main_module

    config = {
        "telegram": {
            "telegram_main": {
                "bot_token": "main-token",
                "chat_id": "main-chat",
            },
            "telegram_vienna": {
                "bot_token": "vienna-token",
                "chat_id": "vienna-chat",
            },
        }
    }

    with patch("Application.main.os.getenv", return_value=None) as getenv, \
            patch("Application.main.TelegramBot") as telegram_bot:
        result = main_module.resolve_vienna_telegram_bot(config)

    assert result is telegram_bot.return_value
    telegram_bot.assert_called_once_with("vienna-token", "vienna-chat")
    assert {
        call.args[0] for call in getenv.call_args_list
    } == {
        "TELEGRAM_BOT_VIENNA_TOKEN",
        "TELEGRAM_BOT_VIENNA_CHAT_ID",
    }


def test_resolve_vienna_telegram_bot_returns_none_without_vienna_credentials():
    from Application import main as main_module

    config = {
        "telegram": {
            "telegram_main": {
                "bot_token": "main-token",
                "chat_id": "main-chat",
            }
        }
    }

    with patch("Application.main.os.getenv", return_value=None) as getenv, \
            patch("Application.main.TelegramBot") as telegram_bot:
        result = main_module.resolve_vienna_telegram_bot(config)

    assert result is None
    telegram_bot.assert_not_called()
    assert {
        call.args[0] for call in getenv.call_args_list
    } == {
        "TELEGRAM_BOT_VIENNA_TOKEN",
        "TELEGRAM_BOT_VIENNA_CHAT_ID",
    }


def test_was_listing_sent_recently_detects_recent_coop_timestamp():
    from Application import main as main_module

    now = 1_000_000.0
    mongo = Mock()
    mongo.get_listing.return_value = {
        "sent_to_telegram_at": now - (6 * 86400),
    }

    with patch("Application.main.time.time", return_value=now):
        assert main_module.was_listing_sent_recently(mongo, "https://example.test/coop") is True

    mongo.get_listing.assert_called_once_with("https://example.test/coop")


@pytest.mark.parametrize(
    "document",
    [
        {"sent_to_telegram_at": 1_000_000.0 - (8 * 86400)},
        None,
        {},
        {"sent_to_telegram_at": "not-a-timestamp"},
        {"sent_to_telegram_at": math.nan},
        {"sent_to_telegram_at": True},
    ],
)
def test_was_listing_sent_recently_allows_old_or_missing_coop_timestamp(document, caplog):
    from Application import main as main_module

    mongo = Mock()
    mongo.get_listing.return_value = document

    with caplog.at_level("WARNING"), patch("Application.main.time.time", return_value=1_000_000.0):
        assert main_module.was_listing_sent_recently(mongo, "https://example.test/coop") is False

    timestamp = document.get("sent_to_telegram_at") if isinstance(document, dict) else None
    if (
        not isinstance(timestamp, (int, float))
        or isinstance(timestamp, bool)
        or not math.isfinite(timestamp)
    ):
        assert caplog.records


def test_was_listing_sent_recently_allows_coop_when_lookup_errors(caplog):
    from Application import main as main_module

    mongo = Mock()
    mongo.get_listing.side_effect = RuntimeError("database unavailable")

    with caplog.at_level("WARNING"):
        assert main_module.was_listing_sent_recently(mongo, "https://example.test/coop") is False

    assert "could not check" in caplog.text.lower()


def test_calculate_listing_score_uses_telegram_bot_when_available():
    from Application import main as main_module

    candidate = listing()
    telegram_bot = Mock()
    telegram_bot.calculate_listing_score.return_value = 61.5

    assert main_module.calculate_listing_score(candidate, telegram_bot) == 61.5
    telegram_bot.calculate_listing_score.assert_called_once_with(candidate)


def test_calculate_listing_score_falls_back_without_vienna_bot():
    from Application import main as main_module

    candidate = listing()

    with patch("Application.scoring.score_apartment_simple", return_value=27.5) as score_listing:
        assert main_module.calculate_listing_score(candidate, None) == 27.5

    score_listing.assert_called_once_with(candidate)


def test_main_completes_coop_route_without_dev_or_vienna_bot():
    from Application import main as main_module

    coop_listing = Listing(
        url="https://example.test/coop-main",
        source=Source.GENOSSENSCHAFT,
        title="Co-op listing",
        area_m2=70.0,
        rooms=3.0,
        is_genossenschaft=True,
        coop_source="bautraeger_direct",
    )
    config = {
        "telegram": {"telegram_main": {}},
        "cleanup": {"enabled": False},
        "criteria": {},
        "max_pages": 1,
    }
    mongo = Mock()
    mongo.get_listing.return_value = None
    coop_bot = Mock()
    coop_bot.send_message.return_value = True
    ratings = {
        "potential_growth_rating": 1,
        "renovation_needed_rating": 2,
        "balcony_terrace": False,
        "floor_level": 1,
    }

    with patch.dict(
        "os.environ",
        {
            "TELEGRAM_MAIN_BOT_TOKEN": "main-token",
            "TELEGRAM_COOP_CHANNEL_ID": "coop-chat",
        },
        clear=True,
    ), patch("sys.argv", ["main.py", "--skip-images", "--willhaben-only", "--send-to-telegram"]), \
            patch("Application.main.load_config", return_value=config), \
            patch("Application.main.test_system_components", return_value={"mongodb": True}), \
            patch("Application.main.MongoDBHandler", return_value=mongo), \
            patch("Application.main.scrape_willhaben", return_value=([coop_listing], "genossenschaft")), \
            patch("Application.main.mark_taken_listings", return_value={"newly_taken": 0, "already_taken": 0}), \
            patch("Application.main.TelegramBot", return_value=coop_bot) as telegram_bot, \
            patch("Application.main.save_listings_to_mongodb", return_value=1) as save_listings, \
            patch("Application.main.validate_url", return_value=True), \
            patch("Application.main.compute_xsrc_fingerprint", return_value="xsrc"), \
            patch("Application.main.format_coop_message", return_value="co-op message"), \
            patch("Application.main.print_listing_summary"), \
            patch("Application.rating_calculator.calculate_all_ratings", return_value=ratings), \
            patch("Application.scoring.set_buyer_profile"), \
            patch("Application.scoring.score_apartment_simple", return_value=12.5) as score_listing:
        main_module.main()

    telegram_bot.assert_called_once_with("main-token", "coop-chat")
    score_listing.assert_called_once_with(coop_listing.__dict__)
    save_listings.assert_called_once_with([coop_listing])
    coop_bot.send_message.assert_called_once_with("co-op message")
    mongo.mark_sent.assert_called_once_with(coop_listing.url)


def test_main_uses_vienna_delivery_without_property_summary_or_cooldown():
    from Application import main as main_module

    source = inspect.getsource(main_module.main)

    assert "send_vienna_listings(high_score_listings, telegram_bot, mongo)" in source
    assert "telegram_bot.send_property_notification" not in source
    assert "telegram_bot.send_message" not in source
    assert "summary_message" not in source
    assert "no_results_message" not in source
    assert "sent_to_telegram_at" not in source


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
        "https://example.test/listing-1", "fingerprint-1",
        claim_token="claim-token",
    ) is True
    assert mongo.claim_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1",
        claim_token="claim-token",
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
    assert update["$set"]["telegram_delivery.vienna.claim_token"] == "claim-token"
    assert collection.find_one_and_update.call_args_list[0].kwargs["return_document"] == (
        pymongo.ReturnDocument.AFTER
    )


def test_listing_delivery_release_and_mark_update_route_and_legacy_state():
    collection = Mock()
    collection.update_one.return_value = Mock(modified_count=1)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.release_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1",
        claim_token="claim-token",
    ) is True
    with patch("Integration.mongodb_handler.time.time", return_value=1234.5):
        assert mongo.mark_listing_delivery_sent(
            "https://example.test/listing-1", "fingerprint-1",
            claim_token="claim-token",
        ) is True

    release_query, release_update = collection.update_one.call_args_list[0].args[:2]
    assert {"telegram_delivery.vienna.claim_token": "claim-token"} in release_query["$and"]
    assert release_update["$set"]["telegram_delivery.vienna.state"] == "failed"
    assert release_update["$unset"] == {
        "telegram_delivery.vienna.claim_until": "",
        "telegram_delivery.vienna.claimed_at": "",
        "telegram_delivery.vienna.claim_token": "",
    }

    sent_query, sent_update = collection.update_one.call_args_list[1].args[:2]
    assert {"telegram_delivery.vienna.claim_token": "claim-token"} in sent_query["$and"]
    assert sent_update["$set"] == {
        "telegram_delivery.vienna.state": "sent",
        "telegram_delivery.vienna.sent_at": 1234.5,
        "sent_to_telegram": True,
        "sent_to_telegram_at": 1234.5,
    }
    assert sent_update["$unset"] == {
        "telegram_delivery.vienna.claim_until": "",
        "telegram_delivery.vienna.claim_token": "",
    }


def test_quarantine_listing_delivery_sets_uncertain_route_state():
    collection = Mock()
    collection.update_one.return_value = Mock(modified_count=1)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    with patch("Integration.mongodb_handler.time.time", return_value=9876.5):
        assert mongo.quarantine_listing_delivery(
            "https://example.test/listing-1", "fingerprint-1",
            claim_token="claim-token",
        ) is True

    query, update = collection.update_one.call_args.args[:2]
    assert {"telegram_delivery.vienna.claim_token": "claim-token"} in query["$and"]
    assert update["$set"] == {
        "telegram_delivery.vienna.state": "uncertain",
        "telegram_delivery.vienna.uncertain_at": 9876.5,
    }
    assert update["$unset"] == {
        "telegram_delivery.vienna.claim_until": "",
        "telegram_delivery.vienna.claim_token": "",
    }


def test_wrong_claim_token_cannot_transition_claimed_row():
    collection = Mock()
    collection.update_one.return_value = Mock(modified_count=0)
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.release_listing_delivery(
        "https://example.test/listing-1", "fingerprint-1",
        claim_token="different-token",
    ) is False
    with patch("Integration.mongodb_handler.time.time", return_value=1234.5):
        assert mongo.mark_listing_delivery_sent(
            "https://example.test/listing-1", "fingerprint-1",
            claim_token="different-token",
        ) is False

    for call in collection.update_one.call_args_list:
        query = call.args[0]
        assert {"telegram_delivery.vienna.claim_token": "different-token"} in query["$and"]


@pytest.mark.parametrize("method_name", [
    "claim_listing_delivery",
    "release_listing_delivery",
    "mark_listing_delivery_sent",
    "quarantine_listing_delivery",
])
@pytest.mark.parametrize("claim_token", [None, "", "  ", "\t", {}, [], 123])
def test_delivery_methods_require_nonblank_claim_token(method_name, claim_token):
    collection = Mock()
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert getattr(mongo, method_name)(
        "https://example.test/listing-1", "fingerprint-1",
        claim_token=claim_token,
    ) is False
    collection.find_one_and_update.assert_not_called()
    collection.update_one.assert_not_called()


@pytest.mark.parametrize("method_name", [
    "claim_listing_delivery",
    "release_listing_delivery",
    "mark_listing_delivery_sent",
    "quarantine_listing_delivery",
])
def test_delivery_methods_require_claim_token_argument(method_name):
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = Mock()

    with pytest.raises(TypeError):
        getattr(mongo, method_name)(
            "https://example.test/listing-1", "fingerprint-1"
        )


@pytest.mark.parametrize("method_name", [
    "claim_listing_delivery",
    "release_listing_delivery",
    "mark_listing_delivery_sent",
    "quarantine_listing_delivery",
])
@pytest.mark.parametrize(
    "url, fingerprint",
    [
        (None, "fingerprint-1"),
        ("", "fingerprint-1"),
        ("  ", "fingerprint-1"),
        ({"$ne": ""}, "fingerprint-1"),
        (["https://example.test/listing-1"], "fingerprint-1"),
        ("https://example.test/listing-1", None),
        ("https://example.test/listing-1", {"$ne": ""}),
        ("https://example.test/listing-1", ["fingerprint-1"]),
    ],
)
def test_delivery_methods_reject_malformed_identity_before_mongo(
    method_name, url, fingerprint
):
    collection = Mock()
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert getattr(mongo, method_name)(
        url, fingerprint, claim_token="valid-token"
    ) is False
    collection.find_one_and_update.assert_not_called()
    collection.update_one.assert_not_called()


def test_empty_fingerprint_is_allowed_with_valid_url():
    collection = Mock()
    collection.find_one_and_update.return_value = {"_id": "claimed"}
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.claim_listing_delivery(
        "https://example.test/listing-1", "", claim_token="claim-token"
    ) is True
    query = collection.find_one_and_update.call_args.args[0]
    identity = next(part for part in query["$and"] if "$or" in part)
    assert identity["$or"] == [{"url": "https://example.test/listing-1"}]


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


def test_vienna_delivery_reuses_claim_token_for_send_transitions():
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = True

    with patch("uuid.uuid4", return_value=uuid.UUID("00000000-0000-0000-0000-000000000001")):
        assert send_vienna_listings(
            [listing()], bot, mongo, url_validator=lambda url: True
        ) == 1

    token = "00000000000000000000000000000001"
    mongo.claim_listing_delivery.assert_called_once_with(
        listing()["url"], mongo.claim_listing_delivery.call_args.args[1],
        VIENNA_CHANNEL, claim_token=token,
    )
    mongo.mark_listing_delivery_sent.assert_called_once_with(
        listing()["url"], mongo.claim_listing_delivery.call_args.args[1],
        VIENNA_CHANNEL, claim_token=token,
    )


def test_vienna_delivery_reuses_claim_token_when_send_fails():
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = False
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True

    with patch("uuid.uuid4", return_value=uuid.UUID("00000000-0000-0000-0000-000000000002")):
        assert send_vienna_listings(
            [listing()], bot, mongo, url_validator=lambda url: True
        ) == 0

    token = "00000000000000000000000000000002"
    fingerprint = mongo.claim_listing_delivery.call_args.args[1]
    mongo.release_listing_delivery.assert_called_once_with(
        listing()["url"], fingerprint, VIENNA_CHANNEL, claim_token=token
    )
    mongo.mark_listing_delivery_sent.assert_not_called()
    mongo.quarantine_listing_delivery.assert_not_called()


def test_vienna_delivery_reuses_claim_token_when_marking_fails():
    bot = Mock(min_score_threshold=40)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = False
    mongo.quarantine_listing_delivery.return_value = True

    with patch("uuid.uuid4", return_value=uuid.UUID("00000000-0000-0000-0000-000000000003")):
        assert send_vienna_listings(
            [listing()], bot, mongo, url_validator=lambda url: True
        ) == 0

    token = "00000000000000000000000000000003"
    fingerprint = mongo.claim_listing_delivery.call_args.args[1]
    mongo.mark_listing_delivery_sent.assert_called_once_with(
        listing()["url"], fingerprint, VIENNA_CHANNEL, claim_token=token
    )
    mongo.quarantine_listing_delivery.assert_called_once_with(
        listing()["url"], fingerprint, VIENNA_CHANNEL, claim_token=token
    )
