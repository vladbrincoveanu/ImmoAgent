import pytest
from Project.Application.scraping.willhaben_scraper import WillhabenScraper

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