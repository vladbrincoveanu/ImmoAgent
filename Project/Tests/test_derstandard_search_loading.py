"""Regression tests for rendered derStandard search-page loading."""

import logging
import os
import sys

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.derstandard_scraper import DerStandardScraper  # noqa: E402


EXPECTED_LISTING_LINK_SELECTOR = (
    'a[href*="/detail/"], '
    'a[href*="/immobiliendetail/"], '
    'a[href*="/projektdetail/"]'
)


class DelayedListingDriver:
    """Minimal browser double where the result link appears after the body."""

    def __init__(self):
        self.listing_link_checks = 0
        self.listing_link_selector = None

    def get(self, _url):
        pass

    def find_element(self, by, value):
        if (by, value) == (By.TAG_NAME, "body"):
            return object()
        if by == By.CSS_SELECTOR:
            self.listing_link_checks += 1
            self.listing_link_selector = value
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
    assert scraper.driver.listing_link_selector == EXPECTED_LISTING_LINK_SELECTOR


def test_selenium_rejects_empty_rendered_page(monkeypatch):
    class EmptyPageDriver:
        def get(self, _url):
            pass

        def find_element(self, by, value):
            assert (by, value) == (By.TAG_NAME, "body")
            return object()

        @property
        def page_source(self):
            return "<html><body></body></html>"

    scraper = object.__new__(DerStandardScraper)
    scraper.driver = EmptyPageDriver()

    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.smart_sleep",
        lambda _seconds: None,
    )

    with pytest.raises(RuntimeError, match="empty rendered page"):
        scraper.get_page_with_selenium("https://immobilien.derstandard.at/detail/123456")


def test_selenium_rejects_nonempty_waf_challenge_page(monkeypatch):
    class ChallengePageDriver:
        def get(self, _url):
            pass

        def find_element(self, by, value):
            assert (by, value) == (By.TAG_NAME, "body")
            return object()

        @property
        def page_source(self):
            return (
                "<html><head><title>Challenge</title></head>"
                '<body><div id="challenge-container">Please wait</div></body></html>'
            )

    scraper = object.__new__(DerStandardScraper)
    scraper.driver = ChallengePageDriver()

    monkeypatch.setattr(
        "Application.scraping.derstandard_scraper.smart_sleep",
        lambda _seconds: None,
    )

    with pytest.raises(RuntimeError, match="AWS WAF challenge page"):
        scraper.get_page_with_selenium("https://immobilien.derstandard.at/detail/123456")


@pytest.mark.parametrize(
    "selenium_error",
    [TimeoutException, WebDriverException, RuntimeError],
    ids=["render-timeout", "webdriver-error", "invalid-session"],
)
def test_search_scrape_retries_http_after_selenium_failure(monkeypatch, selenium_error):
    class FakeAnalyzer:
        def __init__(self, **_kwargs):
            pass

        def is_available(self):
            return False

    class FakeResponse:
        status_code = 200
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

    def selenium_failed(_url, **_kwargs):
        raise selenium_error("Selenium failure")

    def fetch_with_http(url, **_kwargs):
        calls.append(url)
        assert scraper.session.headers["Accept"].startswith("text/html")
        return FakeResponse()

    monkeypatch.setattr(scraper, "get_page_with_selenium", selenium_failed)
    monkeypatch.setattr(scraper.session, "get", fetch_with_http)

    urls = scraper.extract_listing_urls(
        scraper.base_url + "/suche/wien/kaufen-wohnung",
        max_pages=1,
    )

    assert urls == ["https://immobilien.derstandard.at/detail/987654"]
    assert calls == [scraper.base_url + "/suche/wien/kaufen-wohnung"]


def test_collection_navigation_uses_waf_safe_http_helper(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '<html><body><a href="/detail/654321">Listing</a></body></html>'
        headers = {}

        def raise_for_status(self):
            pass

    class TrackingSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            assert kwargs["timeout"] == 30
            return FakeResponse()

    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = False
    scraper.session = TrackingSession()
    scraper.base_url = "https://immobilien.derstandard.at"
    scraper.timeout = 30

    collection_url = scraper.base_url + "/immobiliensuche/neubau/detail/1"
    urls = scraper.navigate_collection_listing(collection_url)

    assert urls == [scraper.base_url + "/detail/654321"]
    assert scraper.session.calls == [(collection_url, {"timeout": 30})]


def test_collection_navigation_retries_http_after_selenium_failure(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '<html><body><a href="/detail/654321">Listing</a></body></html>'
        headers = {}

        def raise_for_status(self):
            pass

    class TrackingSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            assert kwargs["timeout"] == 30
            return FakeResponse()

    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = True
    scraper.driver = object()
    scraper.session = TrackingSession()
    scraper.base_url = "https://immobilien.derstandard.at"
    scraper.timeout = 30

    def selenium_failed(_url, **_kwargs):
        raise RuntimeError("empty rendered page")

    monkeypatch.setattr(scraper, "get_page_with_selenium", selenium_failed)

    collection_url = scraper.base_url + "/immobiliensuche/neubau/detail/1"
    urls = scraper.navigate_collection_listing(collection_url)

    assert urls == [scraper.base_url + "/detail/654321"]
    assert scraper.session.calls == [(collection_url, {"timeout": 30})]


def test_detail_scrape_uses_waf_safe_http_fallback(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "<html><body></body></html>"
        headers = {}

        def raise_for_status(self):
            pass

    class TrackingSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            assert kwargs["timeout"] == 30
            return FakeResponse()

    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = True
    scraper.driver = object()
    scraper.session = TrackingSession()
    scraper.timeout = 30

    def selenium_failed(_url, **_kwargs):
        raise RuntimeError("Selenium session invalid")

    monkeypatch.setattr(scraper, "get_page_with_selenium", selenium_failed)
    monkeypatch.setattr(scraper, "is_collection_listing", lambda _soup: False)
    monkeypatch.setattr(scraper, "extract_property_data_from_json", lambda _soup: None)
    monkeypatch.setattr(scraper, "extract_from_html_selectors", lambda _soup, listing: listing)

    listing_url = "https://immobilien.derstandard.at/detail/654321"
    scraper.scrape_single_listing(listing_url)

    assert scraper.session.calls == [(listing_url, {"timeout": 30})]


def test_http_fallback_rejects_nonempty_waf_challenge_page():
    class WafResponse:
        status_code = 200
        text = (
            "<html><head><title>Challenge</title></head>"
            '<body><div id="challenge-container">Please wait</div></body></html>'
        )
        headers = {}

        def raise_for_status(self):
            pass

    class WafSession:
        def get(self, _url, **_kwargs):
            return WafResponse()

    scraper = object.__new__(DerStandardScraper)
    scraper.session = WafSession()
    scraper.timeout = 30

    with pytest.raises(RuntimeError, match="AWS WAF challenge page"):
        scraper._get_page_with_requests("https://immobilien.derstandard.at/detail/123456")


@pytest.mark.parametrize(
    ("headers", "expected_message"),
    [
        ({"x-amzn-waf-action": "challenge"}, "AWS WAF challenge"),
        ({}, "HTTP 202 response"),
    ],
    ids=["waf-header", "unexpected-202"],
)
def test_search_scrape_reports_waf_challenge_instead_of_empty_results(
    monkeypatch, caplog, headers, expected_message
):
    class WafResponse:
        status_code = 202
        text = ""

        def __init__(self):
            self.headers = headers

        def raise_for_status(self):
            pass

    class FakeSession:
        headers = {"Accept": "text/html"}

        def get(self, _url, **_kwargs):
            return WafResponse()

    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = True
    scraper.driver = object()
    scraper.base_url = "https://immobilien.derstandard.at"
    scraper.session = FakeSession()
    scraper.timeout = 30

    def timed_out(_url, **_kwargs):
        raise TimeoutException()

    monkeypatch.setattr(scraper, "get_page_with_selenium", timed_out)

    with caplog.at_level(logging.ERROR):
        urls = scraper.extract_listing_urls(scraper.base_url + "/suche/wien/kaufen-wohnung", max_pages=1)

    assert urls == []
    assert expected_message in caplog.text


def test_search_scrape_contains_http_fallback_errors(monkeypatch, caplog):
    class FailingSession:
        headers = {"Accept": "text/html"}

        def get(self, _url, **_kwargs):
            raise RuntimeError("network unavailable")

    scraper = object.__new__(DerStandardScraper)
    scraper.use_selenium = True
    scraper.driver = object()
    scraper.base_url = "https://immobilien.derstandard.at"
    scraper.session = FailingSession()
    scraper.timeout = 30

    def timed_out(_url, **_kwargs):
        raise TimeoutException()

    monkeypatch.setattr(scraper, "get_page_with_selenium", timed_out)

    with caplog.at_level(logging.ERROR):
        urls = scraper.extract_listing_urls(scraper.base_url + "/suche/wien/kaufen-wohnung", max_pages=1)

    assert urls == []
    assert "Error extracting URLs" in caplog.text
