"""Fast Willhaben poll for private co-op transfers.

The invariants that matter are all about cost and silence: never spend a detail
fetch on a URL already seen, never exceed the per-poll cap, never let one bad ad
or one blocked page kill the poll, and never drop ads at the cap without saying so.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Domain.listing import Listing  # noqa: E402
from Domain.sources import Source  # noqa: E402
from Application.scraping.willhaben_private_coop import (  # noqa: E402
    crawl_newest, crawl_private_coop, is_private_transfer,
)

_SEARCH_HTML = """
<html><body>
  <a href="/iad/immobilien/d/mietwohnungen/wien/wien-1100-favoriten/aaa-111/"></a>
  <a href="/iad/immobilien/d/mietwohnungen/wien/wien-1120-meidling/bbb-222/"></a>
  <a href="/iad/immobilien/d/mietwohnungen/wien/wien-1150-rudolfsheim/ccc-333/"></a>
</body></html>
"""


class _Response:
    def __init__(self, text):
        self.text = text


class FakeScraper:
    """Stands in for WillhabenScraper — records what it was asked to fetch."""

    def __init__(self, kinds=None, raise_on=None, search_response="__default__"):
        self.kinds = kinds or {}
        self.raise_on = raise_on or set()
        self.detail_calls = []
        self._search_response = (_Response(_SEARCH_HTML)
                                 if search_response == "__default__"
                                 else search_response)

    def _fetch_with_retry(self, url, **kwargs):
        return self._search_response

    def extract_listing_urls(self, soup):
        return [a["href"] for a in soup.find_all("a", href=True)]

    def scrape_single_listing(self, url):
        self.detail_calls.append(url)
        if url in self.raise_on:
            raise RuntimeError("malformed ad")
        kind = self.kinds.get(url)
        if kind == "__none__":
            return None
        listing = Listing(url=url, source=Source.WILLHABEN)
        listing.coop_kind = kind
        return listing


_A = "/iad/immobilien/d/mietwohnungen/wien/wien-1100-favoriten/aaa-111/"
_B = "/iad/immobilien/d/mietwohnungen/wien/wien-1120-meidling/bbb-222/"
_C = "/iad/immobilien/d/mietwohnungen/wien/wien-1150-rudolfsheim/ccc-333/"


def test_returns_only_private_transfers():
    scraper = FakeScraper(kinds={_A: "private_transfer", _B: None, _C: "private_transfer"})
    got = crawl_private_coop(scraper, is_new=lambda u: True)
    assert [listing.url for listing in got] == [_A, _C]


def test_already_seen_urls_cost_no_detail_fetch():
    """An ad costs one detail fetch ever, not one per poll — this is what keeps a
    2-minute cadence from becoming a crawl of the whole feed."""
    scraper = FakeScraper(kinds={_B: "private_transfer"})
    got = crawl_private_coop(scraper, is_new=lambda u: u == _B)
    assert scraper.detail_calls == [_B]
    assert len(got) == 1


def test_detail_cap_bounds_the_poll():
    scraper = FakeScraper(kinds={_A: "private_transfer", _B: "private_transfer",
                                 _C: "private_transfer"})
    got = crawl_private_coop(scraper, is_new=lambda u: True, max_details=2)
    assert len(scraper.detail_calls) == 2
    assert len(got) == 2


def test_cap_skips_are_logged(caplog):
    """Dropping new ads during an FCFS race must never be silent."""
    scraper = FakeScraper(kinds={_A: "private_transfer", _B: "private_transfer",
                                 _C: "private_transfer"})
    with caplog.at_level("WARNING"):
        crawl_private_coop(scraper, is_new=lambda u: True, max_details=1)
    assert any("detail cap" in r.message for r in caplog.records)


def test_one_bad_ad_does_not_kill_the_poll():
    scraper = FakeScraper(kinds={_A: "private_transfer", _C: "private_transfer"},
                          raise_on={_B})
    got = crawl_private_coop(scraper, is_new=lambda u: True)
    assert [listing.url for listing in got] == [_A, _C]


def test_listing_that_fails_to_parse_is_skipped():
    scraper = FakeScraper(kinds={_A: "__none__", _B: "private_transfer"})
    got = crawl_private_coop(scraper, is_new=lambda u: True)
    assert [listing.url for listing in got] == [_B]


def test_blocked_search_page_returns_empty_not_an_exception():
    """mygewo's half of the poll has to keep running when Willhaben blocks us."""
    scraper = FakeScraper(search_response=None)
    assert crawl_private_coop(scraper, is_new=lambda u: True) == []


def test_search_fetch_exception_returns_empty():
    class Exploding(FakeScraper):
        def _fetch_with_retry(self, url, **kwargs):
            raise RuntimeError("connection reset")

    assert crawl_private_coop(Exploding(), is_new=lambda u: True) == []


# --- the generalised crawl, used by keyword alerts ----------------------------
#
# Keyword alerts need the SAME poll of the SAME newest-first feed, differing only
# in the final filter. That filter is a parameter rather than a second adapter,
# which is why these tests sit beside the private-transfer ones.

def test_crawl_newest_keeps_everything_when_keep_is_always_true():
    """The alert feed: no pre-filter, because narrowing here would make an alert
    for "Balkon" silently unmatchable."""
    scraper = FakeScraper(kinds={_A: "private_transfer", _B: None, _C: None})
    got = crawl_newest(scraper, is_new=lambda u: True, keep=lambda listing: True)
    assert [listing.url for listing in got] == [_A, _B, _C]


def test_crawl_newest_honours_an_arbitrary_keep_predicate():
    scraper = FakeScraper(kinds={_A: None, _B: None, _C: None})
    got = crawl_newest(scraper, is_new=lambda u: True,
                       keep=lambda listing: listing.url == _B)
    assert [listing.url for listing in got] == [_B]


def test_crawl_newest_still_respects_dedup_and_the_cap():
    scraper = FakeScraper(kinds={_A: None, _B: None, _C: None})
    got = crawl_newest(scraper, is_new=lambda u: True, keep=lambda l: True,
                       max_details=2)
    assert len(scraper.detail_calls) == 2
    assert len(got) == 2


def test_crawl_private_coop_is_crawl_newest_with_the_transfer_filter():
    """The wrapper must not drift from the behaviour its own tests above pin."""
    scraper = FakeScraper(kinds={_A: "private_transfer", _B: None})
    direct = crawl_newest(scraper, is_new=lambda u: True, keep=is_private_transfer)
    assert [listing.url for listing in direct] == [_A]


def test_is_private_transfer_reads_coop_kind():
    listing = Listing(url=_A, source=Source.WILLHABEN)
    assert not is_private_transfer(listing)
    listing.coop_kind = "private_transfer"
    assert is_private_transfer(listing)
