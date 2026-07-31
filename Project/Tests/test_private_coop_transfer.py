"""Private co-op transfer detection (Weitergabe / Ablöse).

These are the first-come-first-served ads: a sitting tenant passes on a
Genossenschaftswohnung directly, bypassing the waiting list. The hard part is not
finding "Ablöse" — it is NOT firing on the thousands of ordinary rentals that ask
an Ablöse for a fitted kitchen. Hence the two-marker rule.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.field_extractors import (  # noqa: E402
    extract_is_private_coop_transfer,
)


# --- true positives -----------------------------------------------------------

def test_genossenschaft_with_ablose():
    text = ("schöne genossenschaftswohnung in 1100 wien, "
            "ablöse für einbauküche eur 3.000, nachmieter gesucht")
    assert extract_is_private_coop_transfer(text) is True


def test_weitergabe_of_gefoerderte_wohnung():
    text = "geförderte wohnung weiterzugeben, finanzierungsbeitrag wird übernommen"
    assert extract_is_private_coop_transfer(text) is True


def test_nachmieter_for_gemeinnuetzige_wohnung():
    text = "gemeinnützige wohnung, nachmieterin ab sofort gesucht"
    assert extract_is_private_coop_transfer(text) is True


def test_genossenschaftswohnung_abzugeben():
    text = "genossenschaftswohnung abzugeben, eigenmittelanteil eur 12.000"
    assert extract_is_private_coop_transfer(text) is True


# --- the false positive this exists to prevent --------------------------------

def test_kitchen_ablose_in_ordinary_rental_is_not_a_transfer():
    """The dominant noise case: an Ablöse with no co-op involvement at all."""
    text = "helle 2-zimmer wohnung, küche gegen ablöse von eur 2.500 zu übernehmen"
    assert extract_is_private_coop_transfer(text) is not True


def test_freifinanziert_with_ablose_is_explicitly_false():
    """Free-financed is a positive statement that this is NOT a co-op."""
    text = ("freifinanzierte mietwohnung, genossenschaft in der nähe, "
            "ablöse für möbel verhandelbar")
    assert extract_is_private_coop_transfer(text) is False


def test_plain_coop_listing_without_transfer_wording_is_not_a_transfer():
    """A Bauträger listing a co-op unit is extract_is_genossenschaft's job."""
    text = "genossenschaftswohnung, wohnbauförderung, vergabe über wohnticket"
    assert extract_is_private_coop_transfer(text) is None


def test_no_signal_at_all():
    assert extract_is_private_coop_transfer("dachgeschosswohnung mit terrasse") is None


# --- spelling / diacritic robustness ------------------------------------------

def test_abloese_without_umlaut():
    text = "genossenschaftswohnung, abloese fuer kueche, nachmieter gesucht"
    assert extract_is_private_coop_transfer(text) is True


def test_wohnungstausch_counts_as_transfer():
    text = "wohnungstausch genossenschaftswohnung 1120 wien"
    assert extract_is_private_coop_transfer(text) is True
