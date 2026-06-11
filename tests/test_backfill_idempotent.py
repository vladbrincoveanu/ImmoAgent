"""Integration test: backfill_profile_scores is idempotent."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT_PATH = Path(__file__).parent.parent / 'Project' / 'scripts' / 'backfill_profile_scores.py'
spec = importlib.util.spec_from_file_location('backfill_profile_scores', SCRIPT_PATH)
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)


def _make_fake_mongo(listings_first_pass, listings_second_pass):
    """Returns a MagicMock MongoDBHandler with 2 distinct cursor states."""
    fake_collection = MagicMock()

    def _make_cursor(docs):
        cur = MagicMock()
        cur.batch_size = MagicMock(return_value=cur)
        cur.__iter__ = lambda self: iter(docs)
        return cur

    cursor_first = _make_cursor(listings_first_pass)
    cursor_second = _make_cursor(listings_second_pass)
    fake_collection.find.side_effect = [cursor_first, cursor_second]

    fake_mongo = MagicMock()
    fake_mongo.collection = fake_collection

    # Wire update_profile_scores to actually call the fake collection's update_one
    def _real_update_scores(listing_id, scores):
        from datetime import datetime, timezone
        fake_collection.update_one(
            {"_id": listing_id},
            {"$set": {"scores": scores, "scores_updated_at": datetime.now(timezone.utc)}},
        )
    fake_mongo.update_profile_scores.side_effect = _real_update_scores
    return fake_mongo, fake_collection


def test_first_run_updates_missing_score_listings():
    listings = [
        {'_id': 'a', 'price_per_m2': 5000, 'area_m2': 80, 'rooms': 3},
        {'_id': 'b', 'price_per_m2': 6000, 'area_m2': 90, 'rooms': 4},
    ]
    # First pass: all have NO scores. Second pass: all have scores.
    fake_mongo, fake_collection = _make_fake_mongo(
        [{'_id': 'a'}, {'_id': 'b'}],
        [{'_id': 'a'}, {'_id': 'b'}],
    )
    # find_one returns the full listing on first pass (no scores), then with scores on second
    fake_collection.find_one.side_effect = [
        {'_id': 'a', 'price_per_m2': 5000, 'area_m2': 80, 'rooms': 3},
        {'_id': 'b', 'price_per_m2': 6000, 'area_m2': 90, 'rooms': 4},
        # second pass
        {'_id': 'a', 'scores': {'default': 1.0, 'owner_occupier': 2.0, 'diy_renovator': 3.0,
                                'growing_family': 4.0, 'urban_professional': 5.0, 'eco_conscious': 6.0,
                                'retiree': 7.0, 'budget_buyer': 8.0, 'prime_new_build': 9.0,
                                'bank_loan_ready': 10.0}},
        {'_id': 'b', 'scores': {'default': 1.0, 'owner_occupier': 2.0, 'diy_renovator': 3.0,
                                'growing_family': 4.0, 'urban_professional': 5.0, 'eco_conscious': 6.0,
                                'retiree': 7.0, 'budget_buyer': 8.0, 'prime_new_build': 9.0,
                                'bank_loan_ready': 10.0}},
    ]
    with patch.object(backfill, 'MongoDBHandler', return_value=fake_mongo):
        stats1 = backfill.run_backfill(dry_run=False, batch=10)
        first_updates = fake_collection.update_one.call_count
        fake_collection.update_one.reset_mock()
        stats2 = backfill.run_backfill(dry_run=False, batch=10)
        second_updates = fake_collection.update_one.call_count

    assert stats1['updated'] == 2
    assert first_updates == 2
    # Second pass: all have scores → 0 updates
    assert stats2['updated'] == 0
    assert second_updates == 0


def test_dry_run_does_not_write():
    listings = [{'_id': 'a', 'price_per_m2': 5000, 'area_m2': 80, 'rooms': 3}]
    fake_mongo, fake_collection = _make_fake_mongo(
        [{'_id': 'a'}],
        [{'_id': 'a'}],
    )
    fake_collection.find_one.side_effect = [
        {'_id': 'a', 'price_per_m2': 5000, 'area_m2': 80, 'rooms': 3},
    ]
    with patch.object(backfill, 'MongoDBHandler', return_value=fake_mongo):
        stats = backfill.run_backfill(dry_run=True, batch=10)
    assert stats['updated'] == 1
    assert fake_collection.update_one.call_count == 0
