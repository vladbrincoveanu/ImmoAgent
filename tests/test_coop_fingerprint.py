import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.helpers.listing_validator import compute_xsrc_fingerprint
from Domain.listing import Listing
from Domain.sources import Source


def _coop(bautraeger, address, area, rooms, source=Source.GENOSSENSCHAFT):
    return Listing(url="u", source=source, is_genossenschaft=True,
                   bautraeger=bautraeger, address=address, area_m2=area, rooms=rooms)


def test_same_unit_different_source_same_fingerprint():
    a = _coop("ÖVW", "Musterstraße 5, 1120 Wien", 62.0, 3.0, Source.GENOSSENSCHAFT)
    b = _coop("ÖVW", "musterstrasse  5, 1120 wien", 62.4, 3.0, Source.WILLHABEN)
    assert compute_xsrc_fingerprint(a) == compute_xsrc_fingerprint(b)


def test_different_units_different_fingerprint():
    a = _coop("ÖVW", "Musterstraße 5, 1120 Wien", 62.0, 3.0)
    b = _coop("ÖVW", "Andere Gasse 9, 1100 Wien", 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) != compute_xsrc_fingerprint(b)


def test_missing_bautraeger_returns_none():
    a = _coop(None, "Musterstraße 5", 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) is None


def test_missing_address_returns_none():
    a = _coop("ÖVW", None, 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) is None
