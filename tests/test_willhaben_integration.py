import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))
from bs4 import BeautifulSoup
from Application.scraping.willhaben_scraper import WillhabenScraper

def test_extract_price_formats():
    scraper = WillhabenScraper()
    test_cases = [
        ("€450.000", 450000.0),
        ("450.000 €", 450000.0),
        ("450000", 450000.0),
        ("450,000", 450000.0),
        ("€ 450.000,00", 450000.0),
        ("450k", 450000.0),
        ("1.2M", 1200000.0),
        ("", None),
        ("Preis auf Anfrage", None)
    ]
    for price_text, expected in test_cases:
        result = scraper.extract_price(price_text)
        print(f"DEBUG: '{price_text}' -> {result} (expected: {expected})")
        assert result == expected, f"Expected {expected} for '{price_text}', got {result}"

def test_is_project_url():
    scraper = WillhabenScraper()
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/neubauprojekt/wien/wien-1220/am-bienefeld-1475846939/"
    ) is True
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220/some-listing-1334111902/"
    ) is False
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/mietwohnung/wien/wien-1220/some-listing-1234567890/"
    ) is False


def test_extract_attributes_dict():
    scraper = WillhabenScraper()
    mock_html = """<html><head></head><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{"attributes":{"attribute":[
        {"name":"BUILDING_CONDITION","values":["Erstbezug"]},
        {"name":"FLOOR_SURFACE","values":["Parkettboden"]},
        {"name":"UNIT_NUMBER","values":["12"]},
        {"name":"FREE_AREA/FREE_AREA_AREA","values":["10,96"]}
    ]}}}}}
    </script>
    </body></html>"""
    soup = BeautifulSoup(mock_html, 'html.parser')
    attrs = scraper.extract_attributes_dict(soup)
    assert attrs.get('BUILDING_CONDITION') == ['Erstbezug']
    assert attrs.get('FLOOR_SURFACE') == ['Parkettboden']
    assert attrs.get('UNIT_NUMBER') == ['12']
    assert attrs.get('FREE_AREA/FREE_AREA_AREA') == ['10,96']
    assert attrs.get('NONEXISTENT') is None


def test_extract_attributes_dict_empty_on_bad_html():
    scraper = WillhabenScraper()
    soup = BeautifulSoup("<html><body>no next data here</body></html>", 'html.parser')
    attrs = scraper.extract_attributes_dict(soup)
    assert attrs == {}


def test_extract_coordinates_from_next_data():
    """Willhaben publishes exact lat/lon in the COORDINATES attribute of __NEXT_DATA__.
    We must capture it instead of geocoding the coarse address text."""
    scraper = WillhabenScraper()
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{"attributes":{"attribute":[
        {"name":"COORDINATES","values":["48.21126,16.393085"]},
        {"name":"LOCATION/ADDRESS_2","values":["Aichholzgasse"]}
    ]}}}}}
    </script></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    coords = scraper.extract_coordinates(soup)
    assert coords is not None, "Should parse COORDINATES attribute"
    assert abs(coords.lat - 48.21126) < 1e-6, f"lat wrong: {coords.lat}"
    assert abs(coords.lon - 16.393085) < 1e-6, f"lon wrong: {coords.lon}"


def test_extract_coordinates_missing_returns_none():
    scraper = WillhabenScraper()
    soup = BeautifulSoup("<html><body>no next data</body></html>", 'html.parser')
    assert scraper.extract_coordinates(soup) is None


def test_extract_coordinates_malformed_returns_none():
    scraper = WillhabenScraper()
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{"attributes":{"attribute":[
        {"name":"COORDINATES","values":["not-a-coordinate"]}
    ]}}}}}
    </script></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_coordinates(soup) is None


def test_extract_coordinates_out_of_range_returns_none():
    """Reject clearly invalid coordinates (e.g. swapped/garbage) rather than storing them."""
    scraper = WillhabenScraper()
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{"attributes":{"attribute":[
        {"name":"COORDINATES","values":["999.0,16.0"]}
    ]}}}}}
    </script></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_coordinates(soup) is None


def test_extract_street_from_description_recovers_house_number():
    """Neubauprojekt listings carry the house number only in the free-text title,
    e.g. 'Aichholzgasse 35 - Neubauprojekt ... 1120 Wien'."""
    scraper = WillhabenScraper()
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{
        "description":"Aichholzgasse 35 - Neubauprojekt in Schoenbrunn-Naehe - Gartenwohnung zu kaufen in 1120 Wien",
        "attributes":{"attribute":[
            {"name":"CONTACT/ADDRESS_STREET","values":["Bankgasse 1"]}
        ]}}}}}
    </script></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_street_from_description(soup) == "Aichholzgasse 35, 1120 Wien"


def test_extract_street_from_description_ignores_agent_address():
    """The broker office address (CONTACT/ADDRESS_STREET) must not leak into the
    listing address — only the description/Lage text is scanned."""
    scraper = WillhabenScraper()
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{
        "description":"Tolle 5-Zimmer Altbauwohnung mit viel Charme",
        "attributes":{"attribute":[
            {"name":"CONTACT/ADDRESS_STREET","values":["Bankgasse 1"]}
        ]}}}}}
    </script></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_street_from_description(soup) is None


def test_street_houseno_guard_distinguishes_district_from_real_address():
    """The address-upgrade guard must treat a district string (which still contains
    digits like the postcode/Bezirk number) as NOT having a real house number."""
    scraper = WillhabenScraper()
    assert scraper._STREET_HOUSENO_RE.search("1120 Wien, 12. Bezirk, Meidling") is None
    assert scraper._STREET_HOUSENO_RE.search("Aichholzgasse") is None
    assert scraper._STREET_HOUSENO_RE.search("Aichholzgasse 35, 1120 Wien") is not None
    assert scraper._STREET_HOUSENO_RE.search("Mariahilfer Straße 120, 1070 Wien") is not None


def test_real_willhaben_listing_extraction():
    scraper = WillhabenScraper()
    test_url = "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1190-doebling/perfekt-aufgeteilte-altbauwohnung-naehe-hohe-warte-1076664583/"
    listing = scraper.scrape_single_listing(test_url)
    print(f"DEBUG: Extracted listing: {listing}")
    assert listing is not None, "Failed to extract listing"
    assert listing.get('price_total') is not None, f"Missing price_total: {listing}"
    assert listing.get('area_m2') is not None, f"Missing area_m2: {listing}"
    assert listing.get('rooms') is not None, f"Missing rooms: {listing}"
    assert listing.get('address') is not None, f"Missing address: {listing}" 