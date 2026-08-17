import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from unittest.mock import MagicMock
from Application.analytics.district_snapshot import build_district_snapshot


def test_build_snapshot_computes_avg_and_median():
    from datetime import datetime
    listings = [
        {"bezirk": "1010", "price_total": 300000, "area_m2": 60, "listing_status": "active",
         "first_scraped_at": datetime(2026, 7, 1).timestamp()},
        {"bezirk": "1010", "price_total": 400000, "area_m2": 80, "listing_status": "active",
         "first_scraped_at": datetime(2026, 7, 1).timestamp()},
        {"bezirk": "1010", "price_total": 200000, "area_m2": 50, "listing_status": "taken",
         "first_scraped_at": datetime(2026, 7, 1).timestamp(), "taken_at": datetime(2026, 7, 11)},
    ]
    snap = build_district_snapshot("1010", "2026-07", listings, source="scraped")
    assert snap["bezirk"] == "1010"
    assert snap["period"] == "2026-07"
    assert snap["listing_count"] == 3
    assert snap["active_count"] == 2
    assert round(snap["avg_price_m2"], 1) == round((300000/60 + 400000/80 + 200000/50) / 3, 1)
    assert snap["source"] == "scraped"
    assert snap["avg_days_on_market"] == 10.0  # only the taken listing has a resolvable window


def test_build_snapshot_handles_empty_list():
    snap = build_district_snapshot("1010", "2026-07", [], source="scraped")
    assert snap["listing_count"] == 0
    assert snap["avg_price_m2"] is None
    assert snap["median_price_m2"] is None


from Application.analytics.district_snapshot import run_monthly_aggregation


def test_run_monthly_aggregation_writes_one_doc_per_bezirk():
    handler = MagicMock()
    handler.collection.find.return_value = [
        {"bezirk": "1010", "price_total": 300000, "area_m2": 60, "listing_status": "active",
         "processed_at": 1751328000.0},
        {"bezirk": "1020", "price_total": 250000, "area_m2": 55, "listing_status": "active",
         "processed_at": 1751328000.0},
    ]
    handler.db = {"district_snapshots": MagicMock()}

    written = run_monthly_aggregation(handler, "2026-07")
    assert written == 2
    assert handler.db["district_snapshots"].update_one.call_count == 2
