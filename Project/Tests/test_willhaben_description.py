import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.willhaben_scraper import WillhabenScraper  # noqa: E402


def test_private_alert_search_keeps_the_full_ad_body():
    body = "Einleitung. " + ("Nachmieter gesucht. " * 400)
    scraper = object.__new__(WillhabenScraper)
    scraper._get_advert_details = lambda soup: {"description": body}

    description = scraper.extract_listing_description(
        BeautifulSoup("<html></html>", "html.parser"))

    assert description == body.lower().strip()
    assert len(description) > 4000
