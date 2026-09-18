import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.helpers.listing_validator import compute_unit_fingerprint
from Domain.listing import Listing
from Domain.sources import Source
from Domain.location import Coordinates


def _listing(lat, lon, coord_source, area, rooms, bezirk, source=Source.WILLHABEN):
    return Listing(
        url="u", source=source, bezirk=bezirk, area_m2=area, rooms=rooms,
        coordinates=Coordinates(lat=lat, lon=lon) if lat is not None else None,
        coordinate_source=coord_source,
    )


def test_same_unit_exact_coords_two_sources_same_fingerprint():
    a = _listing(48.21091, 16.37372, "exact", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.21093, 16.37369, "exact", 62.4, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) == compute_unit_fingerprint(b)


def test_both_landmark_precision_does_not_merge_on_coords():
    # Two different landmark-precision docs must NOT collapse just because
    # rounded coords/area/rooms happen to match - false-positive risk for
    # adjacent units in the same building.
    a = _listing(48.21091, 16.37372, "landmark", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.21093, 16.37369, "landmark", 62.4, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) is None


def test_different_coords_different_fingerprint():
    a = _listing(48.21091, 16.37372, "exact", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.19500, 16.33000, "exact", 62.0, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) != compute_unit_fingerprint(b)


def test_no_coords_falls_back_to_bezirk_street_key():
    a = Listing(url="u1", source=Source.WILLHABEN, bezirk="1010",
                address="Musterstraße 5, 1010 Wien", area_m2=62.0, rooms=3.0,
                coordinate_source="none")
    b = Listing(url="u2", source=Source.DERSTANDARD, bezirk="1010",
                address="musterstrasse  5, 1010 wien", area_m2=62.0, rooms=3.0,
                coordinate_source="none")
    assert compute_unit_fingerprint(a) == compute_unit_fingerprint(b)
    assert compute_unit_fingerprint(a) is not None


def test_no_coords_and_no_address_returns_none():
    a = Listing(url="u1", source=Source.WILLHABEN, bezirk="1010",
                area_m2=62.0, rooms=3.0, coordinate_source="none")
    assert compute_unit_fingerprint(a) is None
