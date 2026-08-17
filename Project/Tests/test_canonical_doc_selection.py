import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Integration.mongodb_handler import pick_canonical_doc


def test_most_complete_doc_wins():
    docs = [
        {"_id": "a", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 100.0},
        {"_id": "b", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "area_m2": 62, "rooms": 3, "bezirk": "1010", "first_scraped_at": 200.0},
    ]
    assert pick_canonical_doc(docs)["_id"] == "b"


def test_tie_break_on_earliest_first_scraped_at():
    docs = [
        {"_id": "a", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 200.0},
        {"_id": "b", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 100.0},
    ]
    assert pick_canonical_doc(docs)["_id"] == "b"


def test_single_doc_returns_itself():
    docs = [{"_id": "a", "unit_fingerprint": "fp1", "title": "Flat"}]
    assert pick_canonical_doc(docs)["_id"] == "a"
