import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Application.scraping.field_extractors import extract_seller_type


def test_private_marker_detected():
    text = "provisionsfrei, direkt vom eigentümer, keine käuferprovision"
    assert extract_seller_type(text) == "private"


def test_agency_marker_detected():
    text = "wir als immobilienbüro freuen uns, maklerprovision 3%"
    assert extract_seller_type(text) == "agency"


def test_bautraeger_from_genossenschaft_flag():
    text = "geförderte wohnung, warme miete"
    assert extract_seller_type(text, is_genossenschaft=True) == "bautraeger"


def test_unknown_when_no_marker():
    text = "schöne 3-zimmer wohnung mit balkon"
    assert extract_seller_type(text) == "unknown"


def test_agency_wins_over_bautraeger_when_both_present():
    text = "geförderte wohnung, vermittelt durch unser immobilienbüro"
    assert extract_seller_type(text, is_genossenschaft=True) == "agency"
