"""Regression tests for the current Dibeo-backed ImmoKurier feed."""

import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.immo_kurier_scraper import ImmoKurierScraper  # noqa: E402


SEARCH_HTML = """
<html><body>
  <a href="/expose/2262075">Apartment</a>
  <a data-href="https://www.dibeo.at/expose/2262076">Apartment 2</a>
  <a href="/assets/logo.svg">Logo</a>
</body></html>
"""


DETAIL_HTML = """
<html lang="de-AT">
  <head>
    <script type="application/ld+json">
      {"@type":"Product","name":"Fixture apartment",
       "image":"https://asset.dibeo.at/fixture/main.webp",
       "offers":{"@type":"Offer","price":100000,"priceCurrency":"EUR"}}
    </script>
    <script type="application/ld+json">
      {"@type":"PostalAddress","addressLocality":"Wien, AUT",
       "postalCode":"1220","streetAddress":null}
    </script>
  </head>
  <body>
    <h1>Fixture apartment</h1>
    <h2>1220 Wien</h2>
    <h3 class="article-params stylized">
      <span class="param">63 m<sup>2</sup></span>
      <span class="param">3 Zimmer</span>
    </h3>
  </body>
</html>
"""


def _scraper_without_network() -> ImmoKurierScraper:
    return object.__new__(ImmoKurierScraper)


def test_extracts_dibeo_expose_urls():
    scraper = _scraper_without_network()

    urls = scraper.extract_listing_urls(BeautifulSoup(SEARCH_HTML, "html.parser"))

    assert urls == [
        "https://www.dibeo.at/expose/2262075",
        "https://www.dibeo.at/expose/2262076",
    ]


def test_extracts_purchase_price_from_dibeo_json_ld():
    scraper = _scraper_without_network()
    soup = BeautifulSoup(DETAIL_HTML, "html.parser")

    assert scraper.extract_price(soup) == 100000


def test_extracts_dibeo_area_and_vienna_postal_address():
    scraper = _scraper_without_network()
    soup = BeautifulSoup(DETAIL_HTML, "html.parser")

    assert scraper.extract_area(soup) == 63
    assert scraper.extract_bezirk(soup) == "1220"
    assert scraper.extract_address(soup) == "1220 Wien"
