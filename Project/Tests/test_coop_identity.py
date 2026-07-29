"""Co-op unit identity: coop_uid + the strengthened cross-source fingerprint.

Guards both halves of the loss that took /coop from ~58 available units to 17:
distinct apartments must get distinct keys (Problem 1), while a genuine
Willhaben↔Bauträger pair for ONE apartment must still collapse (the risk that
strengthening the key introduces).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.helpers.listing_validator import compute_xsrc_fingerprint  # noqa: E402
from Application.scraping.coop.identity import coop_uid, derive_unit_id  # noqa: E402
from Domain.listing import Listing  # noqa: E402
from Domain.sources import Source  # noqa: E402


def _unit(**kw) -> Listing:
    base = dict(url="https://bt.at/projekt-a", source=Source.GENOSSENSCHAFT,
                is_genossenschaft=True, bautraeger="Siedlungsunion",
                address="Saikogasse, 1220 Wien", area_m2=68.0, rooms=3.0,
                price_total=700.0)
    base.update(kw)
    return Listing(**base)


# --- coop_uid -----------------------------------------------------------------

def test_coop_uid_is_namespaced_by_source():
    assert coop_uid("mygewo", "abc") == "mygewo:abc"
    # Two sources numbering their units independently must never collide.
    assert coop_uid("mygewo", "17") != coop_uid("sozialbau", "17")


def test_coop_uid_is_none_without_an_id():
    # An id-less unit must fall back to url-keyed upserts, NOT share one empty
    # key with every other id-less unit.
    for missing in (None, "", "   "):
        assert coop_uid("mygewo", missing) is None
    assert coop_uid("", "abc") is None


def test_coop_uid_accepts_non_string_ids():
    assert coop_uid("mygewo", 22755) == "mygewo:22755"


def test_derive_unit_id_is_stable_and_discriminating():
    a = derive_unit_id("bt", "Saikogasse", 68.0, 3.0, 700.0)
    assert a == derive_unit_id("bt", "Saikogasse", 68.0, 3.0, 700.0)
    assert a != derive_unit_id("bt", "Saikogasse", 68.0, 3.0, 710.0)
    assert derive_unit_id("bt", None, 1) == derive_unit_id("bt", None, 1)


# --- strengthened fingerprint -------------------------------------------------

def test_distinct_flats_in_one_building_get_distinct_fingerprints():
    """The pathological case: one address, one builder, identical size/rooms.
    Under the old key all four hashed alike and three were dropped."""
    flats = [
        _unit(unit_number="Top 4", floor=1),
        _unit(unit_number="Top 5", floor=1),
        _unit(unit_number="Top 6", floor=2),
        _unit(unit_number="Top 7", floor=2),
    ]
    assert len({compute_xsrc_fingerprint(f) for f in flats}) == 4


def test_price_alone_separates_flats_when_top_is_unknown():
    # mygewo publishes no Top/Stiege, so price is the only discriminator left.
    a = _unit(price_total=700.0)
    b = _unit(price_total=812.0)
    assert compute_xsrc_fingerprint(a) != compute_xsrc_fingerprint(b)


def test_cross_source_pair_for_one_flat_still_collapses():
    """The accepted risk, gated. Willhaben publishes no Top and rounds the rent
    differently; the same flat from both sources must still hash alike."""
    bautraeger_side = _unit(coop_source="bautraeger_direct", price_total=700.0)
    willhaben_side = _unit(url="https://willhaben.at/1", coop_source="willhaben",
                           price_total=708.0)   # within the €25 bucket
    assert (compute_xsrc_fingerprint(bautraeger_side)
            == compute_xsrc_fingerprint(willhaben_side))


def test_price_bucket_boundary_does_not_silently_split_a_pair():
    # €25 buckets round to the nearest multiple, so a pair may straddle one.
    # This documents the limit rather than pretending it away.
    assert (compute_xsrc_fingerprint(_unit(price_total=700.0))
            == compute_xsrc_fingerprint(_unit(price_total=712.0)))
    assert (compute_xsrc_fingerprint(_unit(price_total=700.0))
            != compute_xsrc_fingerprint(_unit(price_total=713.0)))


@pytest.mark.parametrize("missing", [{"bautraeger": None}, {"address": None}])
def test_weak_key_returns_none(missing):
    # No builder or no address = too weak to collapse anything on.
    assert compute_xsrc_fingerprint(_unit(**missing)) is None


def test_fingerprint_is_source_independent():
    a = _unit(coop_source="bautraeger_direct")
    b = _unit(url="https://willhaben.at/2", coop_source="willhaben")
    assert compute_xsrc_fingerprint(a) == compute_xsrc_fingerprint(b)
