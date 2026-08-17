import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler_with_existing(existing_doc):
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.collection = MagicMock()
    handler.collection.find_one.return_value = existing_doc
    return handler


def test_relist_event_recorded_when_same_source_doc_was_taken():
    existing = {
        "_id": "abc", "price_total": 290000.0, "price_history": [],
        "listing_status": "taken", "taken_at": "2026-06-01T00:00:00",
        "source_enum": "willhaben", "content_fingerprint": "fp1",
    }
    handler = _handler_with_existing(existing)
    listing = {
        "url": "https://example.com/1", "price_total": 295000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
    }
    handler.upsert_listing_with_history(listing)

    update_call = handler.collection.update_one.call_args[0][1]["$set"]
    assert update_call["listing_status"] == "active"
    assert update_call["times_relisted"] == 1
    assert len(update_call["relist_events"]) == 1
    assert update_call["relist_events"][0]["price_at_relist"] == 295000.0


def test_no_relist_event_when_existing_doc_still_active():
    existing = {
        "_id": "abc", "price_total": 290000.0, "price_history": [],
        "listing_status": "active", "source_enum": "willhaben",
        "content_fingerprint": "fp1",
    }
    handler = _handler_with_existing(existing)
    listing = {
        "url": "https://example.com/1", "price_total": 295000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
    }
    handler.upsert_listing_with_history(listing)

    update_call = handler.collection.update_one.call_args[0][1]["$set"]
    assert "relist_events" not in update_call
    assert "times_relisted" not in update_call
