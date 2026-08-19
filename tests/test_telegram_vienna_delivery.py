import math

import pytest

from Application.telegram_delivery import (
    VIENNA_CHANNEL,
    VIENNA_MIN_AREA_M2,
    VIENNA_MIN_ROOMS,
    vienna_filter_reason,
)


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
