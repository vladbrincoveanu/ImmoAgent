import sys, os, pytest, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping import genossenschaft_scraper as g

# ÖVW/Familienwohnbau/BWSG are disabled in SOURCES (mygewo aggregates them and
# these standalone adapters leaked non-Wien and buy-option units) but their
# parse_* functions are kept for reference — smoke test them directly against
# their real URLs rather than through the (now adapter-less) SOURCES dict.
_URLS = {
    "ÖVW": "https://www.oevw.at/suche/wohnen",
    "Familienwohnbau": "https://www.familienwohnbau.at/de/immobilien",
    "BWSG": "https://www.bwsg.at/immobilien/immobilie-suchen/",
}


def _fetch_or_skip(name):
    url = _URLS[name]
    try:
        return g.fetch(url)
    except (requests.RequestException, Exception) as e:
        pytest.skip(f"{name} unreachable: {e}")


@pytest.mark.smoke
def test_oevw_parser_yields_valid_coop():
    html = _fetch_or_skip("ÖVW")
    listings = g.parse_oevw(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.is_genossenschaft is True
    assert first.bautraeger == "ÖVW"
    assert first.coop_source == "bautraeger_direct"
    assert first.url and first.url.startswith("http")
    assert first.address or first.bezirk


@pytest.mark.smoke
def test_familienwohnbau_parser_yields_valid_coop():
    html = _fetch_or_skip("Familienwohnbau")
    listings = g.parse_familienwohnbau(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.is_genossenschaft is True
    assert first.bautraeger == "Familienwohnbau"
    assert first.coop_source == "bautraeger_direct"
    assert first.url and first.url.startswith("http")
    assert first.address or first.bezirk


@pytest.mark.smoke
def test_bwsg_parser_yields_valid_coop():
    html = _fetch_or_skip("BWSG")
    listings = g.parse_bwsg(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.is_genossenschaft is True
    assert first.bautraeger == "BWSG"
    assert first.coop_source == "bautraeger_direct"
    assert first.url and first.url.startswith("http")
    assert first.address or first.bezirk
