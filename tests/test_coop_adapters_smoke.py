import sys, os, pytest, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping import genossenschaft_scraper as g


def _fetch_or_skip(name):
    url = g.SOURCES[name]["url"]
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
