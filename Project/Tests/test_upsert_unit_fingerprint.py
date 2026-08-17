import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def test_upsert_sets_unit_fingerprint_on_new_doc(monkeypatch):
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.collection = MagicMock()
    handler.collection.find_one.return_value = None

    listing = {
        "url": "https://example.com/1", "price_total": 300000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
        "coordinate_source": "none",
    }
    ok = handler.upsert_listing_with_history(listing)
    assert ok is True
    inserted = handler.collection.insert_one.call_args[0][0]
    assert "unit_fingerprint" in inserted
