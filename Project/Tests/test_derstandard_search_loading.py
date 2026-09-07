"""Regression tests for rendered derStandard search-page loading."""

import os
import sys

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.derstandard_scraper import DerStandardScraper  # noqa: E402


class DelayedListingDriver:
    """Minimal browser double where the result link appears after the body."""

    def __init__(self):
        self.listing_link_checks = 0

    def get(self, _url):
        pass

    def find_element(self, by, value):
        if (by, value) == (By.TAG_NAME, "body"):
            return object()
        if (by, value) == (By.CSS_SELECTOR, 'a[href*="/detail/"]'):
            self.listing_link_checks += 1
            if self.listing_link_checks < 2:
                raise NoSuchElementException()
            return object()
        raise AssertionError(f"Unexpected selector: {by}={value}")

    @property
    def page_source(self):
        if self.listing_link_checks < 2:
            return "<html><body></body></html>"
        return '<html><body><a href="/detail/123456">Listing</a></body></html>'


def test_search_scrape_waits_for_rendered_listing_links(monkeypatch):
    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = True
    scraper.driver = DelayedListingDriver()
    scraper.base_url = "https://immobilien.derstandard.at"

    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.smart_sleep",
        lambda _seconds: None,
    )

    urls = scraper.extract_listing_urls(scraper.base_url + "/suche/wien/kaufen-wohnung", max_pages=1)

    assert urls == ["https://immobilien.derstandard.at/detail/123456"]
    assert scraper.driver.listing_link_checks >= 2


def test_search_scrape_retries_http_after_waf_render_timeout(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, **_kwargs):
            pass

        def is_available(self):
            return False

    class FakeResponse:
        text = '<html><body><a href="/detail/987654">Listing</a></body></html>'
        headers = {}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.StructuredAnalyzer",
        FakeAnalyzer,
    )
    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.ViennaGeocoder",
        lambda: object(),
    )
    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.MongoDBHandler",
        lambda **_kwargs: object(),
    )

    scraper = DerStandardScraper(
        config={
            "mongodb_uri": "mongodb://test",
            "scraping": {
                "user_agent": "Mozilla/5.0",
            },
            "derstandard": {
                "base_url": "https://immobilien.derstandard.at",
            },
        },
        use_selenium=False,
    )
    scraper.use_selenium = True
    scraper.driver = object()
    calls = []

    def timed_out(_url, **_kwargs):
        raise TimeoutException()

    def fetch_with_http(url):
        calls.append(url)
        assert scraper.session.headers["Accept"].startswith("text/html")
        return FakeResponse()

    monkeypatch.setattr(scraper, "get_page_with_selenium", timed_out)
    monkeypatch.setattr(scraper.session, "get", fetch_with_http)

    urls = scraper.extract_listing_urls(
        scraper.base_url + "/suche/wien/kaufen-wohnung",
        max_pages=1,
    )

    assert urls == ["https://immobilien.derstandard.at/detail/987654"]
    assert calls == [scraper.base_url + "/suche/wien/kaufen-wohnung"]
