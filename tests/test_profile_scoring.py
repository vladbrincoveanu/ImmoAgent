"""Unit tests for profile_scoring.score_all_profiles()."""
import pytest
from Application.profile_scoring import score_all_profiles
from Application.buyer_profiles import BUYER_PROFILES


SAMPLE_LISTING = {
    '_id': 'test-1',
    'price_per_m2': 5000,
    'hwb_value': 60,
    'year_built': 1985,
    'ubahn_walk_minutes': 5,
    'school_walk_minutes': 10,
    'rooms': 3.0,
    'area_m2': 80,
    'balcony_terrace': 1,
    'floor_level': 2,
    'potential_growth_rating': 3,
    'renovation_needed_rating': 2,
}


def test_returns_dict_with_all_profiles():
    scores = score_all_profiles(SAMPLE_LISTING)
    assert isinstance(scores, dict)
    assert set(scores.keys()) == set(BUYER_PROFILES.keys())
    assert len(scores) == 10


def test_all_scores_are_floats_in_range():
    scores = score_all_profiles(SAMPLE_LISTING)
    for profile_key, score in scores.items():
        assert isinstance(score, float), f"{profile_key} not float"
        assert 0.0 <= score <= 100.0, f"{profile_key} out of range: {score}"


def test_missing_field_does_not_break_scoring():
    listing = {k: v for k, v in SAMPLE_LISTING.items() if k != 'hwb_value'}
    scores = score_all_profiles(listing)
    assert len(scores) == 10
    full_scores = score_all_profiles(SAMPLE_LISTING)
    assert scores['eco_conscious'] < full_scores['eco_conscious']


def test_different_profiles_yield_different_scores():
    scores = score_all_profiles(SAMPLE_LISTING)
    unique_scores = set(scores.values())
    assert len(unique_scores) >= 5, f"Expected diverse scores, got {scores}"


def test_empty_listing_returns_zero_scores():
    scores = score_all_profiles({'_id': 'empty'})
    assert len(scores) == 10
    for s in scores.values():
        assert s == 0.0
