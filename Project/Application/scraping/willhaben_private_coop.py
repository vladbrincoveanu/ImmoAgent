"""Fast poll of Willhaben for private co-op transfers (Weitergabe / Ablöse).

Why this is separate from the daily Willhaben job: these ads are
first-come-first-served. A sitting tenant posts that they are passing on their
Genossenschaftswohnung, and the flat is gone within hours — often within the
first handful of replies. The daily scrape finds them long after they are dead.

Cost control is the whole design. A search page is one cheap request; a detail
page is an expensive one, and Willhaben will block a client that asks for too
many. So each poll fetches the search feed once, and only spends detail fetches
on URLs it has never seen before, capped per run. Classification then rides on
that single detail fetch — `scrape_single_listing` already tags `coop_kind`.

The external trigger runs every minute; GitHub-hosted notification delivery still
takes roughly 2–3 minutes end to end because runner startup and delivery are on
the critical path.

Every dependency is injected, so the tests below run without touching the network.
"""
import logging
import os
from typing import Callable, List, Optional

from bs4 import BeautifulSoup

from Domain.listing import Listing

logger = logging.getLogger(__name__)

# Wien rental feed, newest first. Overridable because Willhaben changes its query
# parameters periodically and a stale sort silently turns a fast poll into a slow
# one — the crawl keeps working, it just stops being first.
WILLHABEN_PRIVATE_COOP_URL = os.environ.get(
    "WILLHABEN_PRIVATE_COOP_URL",
    "https://www.willhaben.at/iad/immobilien/mietwohnungen/wien"
    "?sfId=&rows=90&sort=1",
)

# Detail fetches per poll. With the minutely external trigger this is at most ~25
# requests per minute in the worst case, and in the steady state far fewer,
# because only genuinely new URLs are fetched at all.
MAX_DETAIL_FETCHES_PER_POLL = 25


def is_private_transfer(listing) -> bool:
    """The original filter, now one `keep` predicate among others."""
    return getattr(listing, "coop_kind", None) == "private_transfer"


def crawl_newest(
    scraper,
    is_new: Callable[[str], bool],
    keep: Callable[[Listing], bool],
    search_url: Optional[str] = None,
    max_details: int = MAX_DETAIL_FETCHES_PER_POLL,
) -> List[Listing]:
    """One poll of the newest-first Willhaben feed → the new ads `keep` wants.

    `scraper` is a WillhabenScraper (needs `_fetch_with_retry`,
    `extract_listing_urls`, `scrape_single_listing`). `is_new` decides whether a
    URL is worth a detail fetch — in production that is a Mongo dedup check, so
    an ad costs one detail fetch ever, not one per poll.

    `keep` is the only thing that varies between callers: the private-Ablöse
    rubric wants transfers only, keyword alerts want everything new and do their
    own matching afterwards.

    Never raises: a blocked or reshaped search page must leave the mygewo half of
    the poll running."""
    url = search_url or WILLHABEN_PRIVATE_COOP_URL
    try:
        response = scraper._fetch_with_retry(url)
    except Exception as e:
        logger.error(f"willhaben newest search fetch failed: {e}")
        return []
    if response is None:
        logger.error("willhaben newest search returned nothing (blocked?)")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    urls = scraper.extract_listing_urls(soup)
    logger.info(f"🔍 willhaben newest: {len(urls)} url(s) on the feed")

    out: List[Listing] = []
    fetched = 0
    skipped_for_cap = 0
    for listing_url in urls:
        if not is_new(listing_url):
            continue
        if fetched >= max_details:
            skipped_for_cap += 1
            continue
        fetched += 1
        try:
            listing = scraper.scrape_single_listing(listing_url)
        except Exception as e:
            # One malformed ad must not end the poll.
            logger.warning(f"detail fetch failed for {listing_url}: {e}")
            continue
        if listing is None:
            continue
        if keep(listing):
            out.append(listing)

    if skipped_for_cap:
        # Never silent: a cap that hides new ads during a first-come-first-served
        # race is exactly the thing that must be visible. With keyword alerts the
        # candidate set is the whole feed, not just transfers, so this binds far
        # more often than it did for the rubric-only crawl.
        logger.warning(
            f"willhaben newest: {skipped_for_cap} new url(s) skipped, "
            f"detail cap {max_details} reached; they resolve on the next poll")

    logger.info(f"🏠 willhaben newest: {len(out)} kept "
                f"from {fetched} detail fetch(es)")
    return out


def crawl_private_coop(
    scraper,
    is_new: Callable[[str], bool],
    search_url: Optional[str] = None,
    max_details: int = MAX_DETAIL_FETCHES_PER_POLL,
) -> List[Listing]:
    """Private co-op transfers only — `crawl_newest` with the original filter."""
    return crawl_newest(scraper, is_new, is_private_transfer,
                        search_url=search_url, max_details=max_details)
