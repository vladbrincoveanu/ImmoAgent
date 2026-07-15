import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping.field_extractors import extract_is_genossenschaft


def test_positive_genossenschaft():
    assert extract_is_genossenschaft("provisionsfrei, genossenschaftswohnung mit finanzierungsbeitrag") is True


def test_positive_gefoerdert():
    assert extract_is_genossenschaft("gefördert, gemeinnütziger bauträger, mietkauf möglich") is True


def test_negative_freifinanziert():
    assert extract_is_genossenschaft("freifinanzierte eigentumswohnung, provisionsfrei vom bauträger") is False


def test_none_when_no_signal():
    assert extract_is_genossenschaft("schöne altbauwohnung im 7. bezirk") is None
