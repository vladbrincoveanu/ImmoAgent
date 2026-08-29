#!/usr/bin/env python3
"""Fast co-op poll -> Telegram/email alerts.

Lightweight (requests + bs4, no Selenium, no scoring/geocoding): polls the
Genossenschaft Bauträger adapters, upserts new units, and delivers matches that
pass the coop_alerts filter. Driven by minutely repository_dispatch runs with a
scheduled fallback.

Run from Project/:  python run_coop.py [--no-send]
"""
import argparse
import hashlib
import logging
import os
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

import requests

from Domain.listing import Listing
from Domain.sources import Source
from Application.observability import init_sentry
from Application.helpers.utils import load_config
from Application.scraping import genossenschaft_scraper as coop
from Application.alert_dispatcher import dispatch, retry_pending, url_hash
from Application.alert_matcher import gate_result, keyword_hit, match, rubric_hit
from Application.coop_alert_router import missing_channels, route
from Application.scraping.willhaben_private_coop import (
    crawl_newest, is_private_transfer)
from Application.scraping.willhaben_scraper import WillhabenScraper
from Application.coop_format import format_coop_message
from Application.helpers.listing_validator import (
    compute_xsrc_fingerprint, validate_url)
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_coop")

# Ceiling on per-unit mygewo offer-page fetches in a single poll (see the loop in
# `run`). Wien's whole co-op inventory is <150 units, so a cold start settles
# within a few polls while no single run hammers mygewo.
MAX_DETAIL_FETCHES_PER_RUN = 40

# Bumped whenever the photo-resolution strategy changes. v1 read og:image off the
# mygewo offer page, which never carries a unit photo, so every unit settled on
# the terminal "" and /coop rendered a placeholder on every row. v2 hops to the
# builder's own page instead. A unit whose stored version is below this earns
# exactly one re-probe; afterwards "" is terminal again, which is what stops a
# genuinely photo-less builder from being re-fetched on every poll of every day.
IMAGE_PROBE_V = 2


# Feeds that user-created alerts watch. 'listings' is the legacy dashboard
# modal's broad feed; 'coop_private' is the private-transfer rubric; 'keyword'
# is the general feed created on /alerts; 'mygewo' is builder-direct only.
USER_ALERT_KINDS = ["listings", "coop_private", "keyword", "mygewo", None]
# Legacy broad alerts are private user subscriptions, not permission to reopen
# the broadcast co-op channels. Those channels remain governed by the explicit
# co-op alert kinds only.
CHANNEL_ALERT_KINDS = ["coop_private", "keyword"]
_LOOKUP_NOT_PROVIDED = object()


def is_coop_listing(listing) -> bool:
    """True for the co-op inventory the Telegram CHANNEL feeds carry.

    mygewo units come from `coop.SOURCES` and carry no `coop_kind` of their own,
    so they are identified by their aggregator URL. Willhaben ads only qualify
    once the scraper has actually classified them."""
    if getattr(listing, "coop_kind", None):
        return True
    if getattr(listing, "is_genossenschaft", None):
        return True
    return "mygewo.at" in (getattr(listing, "url", None) or "")


def deliver_user_alerts(handler, listings: List[Listing]) -> int:
    """Deliver newly-seen listings to the alerts users created on /alerts.

    Returns the number of successful deliveries. Never raises: an alert-delivery
    failure must not fail the poll that feeds the website."""
    try:
        alerts = handler.get_active_alerts(USER_ALERT_KINDS)
    except Exception as e:
        logger.error(f"❌ could not load user alerts: {e}")
        return 0
    if not alerts:
        return 0

    try:
        index_ready = handler.ensure_delivery_index()
    except Exception as e:
        logger.error(f"❌ user alert delivery index check failed: {e}")
        return 0
    if not index_ready:
        logger.error("❌ user alert delivery index unavailable; skipping delivery")
        return 0
    token = os.environ.get("TELEGRAM_MAIN_BOT_TOKEN")

    # Repair before delivering. A previous poll that died mid-send left rows
    # claimed but unsent; those ads are no longer in the "new" set, so this is
    # the only path that can still deliver them.
    delivered = retry_pending(handler, token)

    for alert, listing, unverified in match(listings, alerts):
        if dispatch(alert, listing, unverified, handler, token):
            delivered += 1
    logger.info(f"🔔 user alerts: {delivered} delivery(ies) "
                f"for {len(listings)} new listing(s) across {len(alerts)} alert(s)")
    return delivered


def _coop_source_urls(seen: List[Listing]) -> List[str]:
    urls = []
    known = set()
    for listing in seen:
        url = getattr(listing, "url", None) or ""
        if is_coop_listing(listing) and url and url not in known:
            known.add(url)
            urls.append(url)
    return urls


def _mygewo_urls(seen: List[Listing]) -> List[str]:
    urls = []
    known = set()
    for listing in seen:
        url = getattr(listing, "url", None) or ""
        if "mygewo.at" in url and url not in known:
            known.add(url)
            urls.append(url)
    return urls


def new_alert_candidates(handler, seen: List[Listing],
                         new_from_willhaben: List[Listing],
                         existing_by_url=_LOOKUP_NOT_PROVIDED) -> List[Listing]:
    """Return crawl-new Willhaben listings and mygewo units once each."""
    if existing_by_url is _LOOKUP_NOT_PROVIDED:
        existing_by_url = handler.get_listings_by_urls(_mygewo_urls(seen))

    candidates = []
    candidate_urls = set()

    for listing in new_from_willhaben:
        url = getattr(listing, "url", None) or ""
        if url in candidate_urls:
            continue
        candidate_urls.add(url)
        candidates.append(listing)

    if existing_by_url is None:
        return candidates

    for listing in seen:
        url = getattr(listing, "url", None) or ""
        if ("mygewo.at" not in url or url in candidate_urls
                or url in existing_by_url):
            continue
        candidate_urls.add(url)
        candidates.append(listing)

    return candidates


def new_source_candidates(handler, seen: List[Listing],
                          new_from_willhaben: List[Listing],
                          existing_by_url=_LOOKUP_NOT_PROVIDED) -> List[Listing]:
    """Return new source-channel co-op units without widening user alerts."""
    if existing_by_url is _LOOKUP_NOT_PROVIDED:
        existing_by_url = handler.get_listings_by_urls(_coop_source_urls(seen))

    candidates = new_alert_candidates(
        handler, seen, new_from_willhaben, existing_by_url
    )
    if existing_by_url is None:
        return candidates

    candidate_urls = {getattr(listing, "url", None) for listing in candidates}
    for listing in seen:
        url = getattr(listing, "url", None) or ""
        if (
            is_coop_listing(listing)
            and url
            and url not in candidate_urls
            and url not in existing_by_url
        ):
            candidate_urls.add(url)
            candidates.append(listing)
    return candidates


def maybe_reprobe_image(stored: dict, resolve) -> dict:
    """Re-probe one unit's photo if it predates the current probe version.

    Returns the fields to persist. `resolve` is injected so the poll passes the
    real network call and tests pass a stub."""
    out = dict(stored)
    if (out.get("image_probe_v") or 1) >= IMAGE_PROBE_V:
        return out
    if not out.get("builder_url"):
        return out
    # `or ""` is what makes a miss terminal within this version.
    out["image_url"] = resolve(out["builder_url"]) or ""
    out["image_probe_v"] = IMAGE_PROBE_V
    return out


def channel_match(alert: Dict, listing) -> bool:
    """True when this alert wants this unit on a broadcast channel.

    Stricter than the per-user path, deliberately. `gate_result`'s `unverified`
    — a gate is set and the source did not publish the field — is delivered to
    the user who asked for it, flagged. On a public feed that same match is
    noise, so the channel takes `passes and not unverified`. The strictness lives
    here rather than in the shared matcher, which keeps email behaviour untouched.

    Deliverability is NOT consulted: an alert whose email is still unconfirmed
    has no usable channel of its own, yet it is still a statement of what this
    feed is for. Filtering is not delivery."""
    if not rubric_hit(alert, listing):
        return False
    if not keyword_hit(alert, listing):
        return False
    passes, unverified = gate_result(alert, listing)
    return passes and not unverified


def channel_match_any(listing, alerts: List[Dict]) -> bool:
    """The channel filter: the union of every active alert.

    Replaces the old static `coop_alerts.json` filter, whose fields were all null
    in CI — so it matched everything and the channel was a firehose. Alerts are a
    single source of truth the owner can retune without a redeploy, and they
    carry keywords, which the static filter had no field for."""
    return any(channel_match(alert, listing) for alert in alerts)


def channel_dedup_key(listing) -> str:
    """The ledger key for one unit.

    The xsrc fingerprint is what collapses the same unit under its mygewo URL and
    its Bauträger-direct URL into a single send. It is COMPUTED here and never
    read off the Listing: `content_fingerprint_xsrc` is a declared field that no
    code path ever populates on the object (only into Mongo dicts), so reading it
    would yield None for every unit and silently degrade every key to url_hash."""
    return compute_xsrc_fingerprint(listing) or url_hash(listing.url or "")


_UA = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter-coop/1.0; +alerts)"}


def _page_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def conditional_fetch(url: str, meta: dict, session=requests) -> Tuple[bool, Optional[str], dict]:
    """Conditional GET. Returns (changed, html, new_meta).

    changed=False when the server returns 304 OR the body hash matches the
    stored one — caller then skips parsing. new_meta carries etag/last_modified/
    page_hash to persist (empty on 304 so a good stored ETag isn't clobbered)."""
    headers = dict(_UA)
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    resp = session.get(url, headers=headers, timeout=20)
    if resp.status_code == 304:
        return False, None, {}
    resp.raise_for_status()
    new_hash = _page_hash(resp.text)
    new_meta = {
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "page_hash": new_hash,
    }
    if meta.get("page_hash") and new_hash == meta["page_hash"]:
        return False, None, new_meta
    return True, resp.text, new_meta


def _to_doc(listing: Listing) -> dict:
    """Listing → BSON-safe dict. Source is a plain Enum (verified not
    BSON-encodable), so stringify it. price_per_m2 filled when derivable."""
    d = asdict(listing)
    d["source"] = listing.source.value if hasattr(listing.source, "value") else listing.source
    d["source_enum"] = Source.GENOSSENSCHAFT.value
    if listing.price_total and listing.area_m2 and not d.get("price_per_m2"):
        d["price_per_m2"] = listing.price_total / listing.area_m2
    return d


def poll_source(name: str, cfg: dict, handler, session=requests) -> List[Listing]:
    """Fetch one adapter. HTML parsers use a conditional GET and parse only when
    the page changed; self-crawling fetchers always run (see below)."""
    if cfg.get("fetcher"):
        # Self-contained crawl (mygewo pages its full inventory via an RPC).
        # NO change-gate here: the gate hashes SSR page 0 only, so a unit added
        # on page 3 would leave page 0 byte-identical and the whole crawl would
        # be skipped. Always crawl — a few extra RPC calls beat missing units.
        return _log_parsed(name, getattr(coop, cfg["fetcher"])(cfg.get("states", "28_")))

    meta = handler.get_source_meta(name) or {}
    changed, html_text, new_meta = conditional_fetch(cfg["url"], meta, session=session)
    if new_meta:
        handler.set_source_meta(name, **new_meta)
    if not changed:
        logger.info(f"↔️  {name}: unchanged, skipping parse")
        return []
    return _log_parsed(name, getattr(coop, cfg["parser"])(html_text))


def _log_parsed(name: str, listings: List[Listing]) -> List[Listing]:
    logger.info(f"🔍 {name}: {len(listings)} listing(s) parsed")
    return listings


def run(no_send: bool = False) -> int:
    """Poll → upsert → alert. Exit 0 unless MongoDB is down or ALL adapters fail."""
    # Name every unset channel up front. Previously a missing secret produced one
    # warning that looked identical to a quiet market, and the poll ran green for
    # weeks while delivering nothing.
    for name in missing_channels():
        logger.warning(f"⚠️ {name} is unset — source-channel notifications for that "
                       "feed are disabled. Scraping, upserts, and user-created "
                       "email alerts continue.")
    handler = MongoDBHandler()
    if handler.collection is None:
        logger.error("❌ No MongoDB connection; aborting")
        return 1

    # One bot per feed. Co-op alerts go ONLY to co-op channels — the main channel
    # excludes co-ops by design, so no TELEGRAM_MAIN_CHAT_ID fallback here.
    bots = {}
    chat_ids = {}                       # the ledger is keyed per channel (D2)
    if not no_send:
        token = os.environ.get("TELEGRAM_MAIN_BOT_TOKEN")
        if token:
            for kind in ("mygewo", "private_transfer"):
                chat_id = route(kind)
                if chat_id:
                    bots[kind] = TelegramBot(token, chat_id)
                    chat_ids[kind] = chat_id
        if not bots:
            logger.warning("⚠️ no Telegram bot token or co-op channel configured; "
                           "Telegram source-channel notifications are disabled, "
                           "but polling/upserts and user-created email alerts continue")

    seen: List[Listing] = []
    ok_adapters = 0
    for name, cfg in coop.SOURCES.items():
        try:
            seen.extend(poll_source(name, cfg, handler, session=requests))
            ok_adapters += 1
        except Exception as e:
            logger.error(f"❌ adapter {name} failed: {e}")

    if ok_adapters == 0:
        logger.error("❌ All adapters failed")
        handler.close()
        return 1

    # Willhaben is polled here rather than in the daily scrape because private
    # co-op transfers are first-come-first-served — a sitting tenant passing on
    # their flat, gone within hours. Only genuinely new URLs cost a detail fetch,
    # so this rides the minutely dispatch cadence without crawling the whole feed.
    #
    # Deliberately AFTER the all-adapters-failed gate and outside ok_adapters: it
    # is an extra feed, not one of coop.SOURCES, and it must never mask a total
    # mygewo outage by making a dead poll look half-alive.
    new_from_willhaben: List[Listing] = []
    if os.environ.get("WILLHABEN_PRIVATE_COOP", "1") != "0":
        try:
            new_from_willhaben = crawl_newest(
                WillhabenScraper(config=load_config() or {}),
                is_new=lambda u: handler.get_listing(u) is None,
                # Everything new: keyword alerts do their own matching, and the
                # transfer rubric is re-applied per listing just below. Narrowing
                # here would make an alert for "Balkon" silently unmatchable.
                keep=lambda listing: True,
            )
            # Per listing, not blanket. Every ad this returned used to be a
            # transfer by construction; with the widened feed, tagging them all
            # would route ordinary rentals into the private-Ablöse channel and
            # corrupt /coop/private.
            for listing in new_from_willhaben:
                if is_private_transfer(listing):
                    listing.coop_kind = "private_transfer"
            seen.extend(new_from_willhaben)
        except Exception as e:
            # A Willhaben block must not take the mygewo half of the poll with it.
            logger.error(f"❌ willhaben newest adapter failed: {e}")

    source_existing: Optional[Dict[str, Dict]] = {}
    source_lookup_failed = False
    source_channel_candidates: List[Listing] = []
    if not no_send:
        source_urls = _coop_source_urls(seen)
        if source_urls:
            # One batch lookup feeds both candidate classification and detail reuse.
            # None means the query failed, not that every unit is new.
            source_existing = handler.get_listings_by_urls(source_urls)
            source_lookup_failed = source_existing is None
            if source_lookup_failed:
                logger.error(
                    "❌ co-op source lookup failed; deferring mygewo detail/upsert and "
                    "owner alerts so user alerts can retry next poll")
        source_channel_candidates = new_source_candidates(
            handler, seen, new_from_willhaben, source_existing)
        user_alert_candidates = new_alert_candidates(
            handler, seen, new_from_willhaben, source_existing)
        deliver_user_alerts(handler, user_alert_candidates)
    else:
        # Dry-run keeps its existing preview behavior without treating the
        # inventory as new or touching the delivery ledger.
        source_channel_candidates = seen

    # The offer-page fetch is the only per-unit request this poll makes. It runs
    # at most once per unit ever and is capped per run so a mass re-scrape — or a
    # mygewo change that blanks the stored values — can't turn a minutely poll into a
    # crawl of the entire inventory.
    #
    # "At most once" requires distinguishing "not resolved yet" from "resolved,
    # and the page had no builder link / no photo". Both would otherwise read
    # back as a falsy value and re-fetch on the next poll — forever, for every
    # unit whose offer page simply has no og:image. With minutely polling over 15h
    # that is ~900 runs/day × the cap = thousands of pointless requests, and it is silent,
    # because a missing photo is a placeholder tile rather than an error.
    # So: None means "never fetched", "" means "fetched, nothing there" and is
    # terminal. Downstream both are falsy — `builder_url || url` and CoopThumb's
    # `!src` placeholder already treat "" exactly like None.
    detail_fetches = 0
    for listing in seen:
        if source_lookup_failed and "mygewo.at" in (listing.url or ""):
            continue
        # mygewo units store the aggregator URL; resolve the builder's own
        # reservation page and the unit photo once, reusing values already
        # resolved on an earlier poll.
        if "mygewo.at" in (listing.url or "") and (
                listing.builder_url is None or listing.image_url is None):
            existing = (source_existing or {}).get(listing.url, {})
            if listing.builder_url is None:
                listing.builder_url = existing.get("builder_url")
            if listing.image_url is None:
                listing.image_url = existing.get("image_url")
            if listing.builder_url is None or listing.image_url is None:
                if detail_fetches < MAX_DETAIL_FETCHES_PER_RUN:
                    detail_fetches += 1
                    details = coop.resolve_offer_details(listing.url)
                    # `or ""` is what makes a miss terminal — see above.
                    if listing.builder_url is None:
                        listing.builder_url = details["builder_url"] or ""
                    if listing.image_url is None:
                        listing.image_url = details["image_url"] or ""
                elif detail_fetches == MAX_DETAIL_FETCHES_PER_RUN:
                    detail_fetches += 1  # log the cap once, not per remaining unit
                    logger.warning(
                        f"offer-detail fetches capped at {MAX_DETAIL_FETCHES_PER_RUN} "
                        "this run; remaining units resolve on the next poll")

            # v1 probed the mygewo offer page, which has no unit photo, so every
            # unit above settled on "". Hop to the builder page once per unit.
            # Version-gated BEFORE spending a fetch slot: units already at v2 must
            # not consume the budget that unprobed units need. Reuses `existing`
            # rather than re-reading Mongo — this loop runs per unit per poll.
            stored = existing
            if ((stored.get("image_probe_v") or 1) < IMAGE_PROBE_V
                    and listing.builder_url
                    and detail_fetches < MAX_DETAIL_FETCHES_PER_RUN):
                detail_fetches += 1
                probed = maybe_reprobe_image(
                    {"builder_url": listing.builder_url,
                     "image_url": stored.get("image_url"),
                     "image_probe_v": stored.get("image_probe_v")},
                    coop.resolve_builder_image,
                )
                listing.image_url = probed["image_url"] or None
                listing.image_probe_v = probed["image_probe_v"]
        handler.upsert_coop_listing(_to_doc(listing))

    # What the channel carries is whatever a live alert asks for. Zero alerts is
    # therefore zero messages, where the old static filter meant "send
    # everything" — a behaviour change that must never be silent.
    # Every subscription, not `get_active_alerts`: that view drops an alert whose
    # only address is unconfirmed, and such an alert still says what this feed is
    # for even though nothing can be delivered to it.
    try:
        channel_alerts = handler.get_alert_subscriptions(CHANNEL_ALERT_KINDS)
    except Exception as e:
        logger.error(f"❌ could not load the channel alert filter: {e}")
        channel_alerts = []
    if not channel_alerts:
        logger.warning("⚠️ no active alerts — the co-op channels stay silent this "
                       "poll. Polling, upserts and user alerts are unaffected.")

    # The unique index is what makes a claim a claim. Without it, skip every send
    # rather than risk re-opening the per-minute repeat (fail closed: a missed
    # unit is recoverable, a channel nobody can read is not).
    ledger_ready = True
    if not no_send and bots:
        ledger_ready = handler.ensure_channel_send_index()
        if not ledger_ready:
            logger.error("❌ co-op channel send ledger unavailable; skipping all "
                         "channel sends this poll")

    sent = 0
    for listing in source_channel_candidates:
        if source_lookup_failed and "mygewo.at" in (listing.url or ""):
            continue
        # The channel feeds are co-op only. The candidate list can also carry new
        # Willhaben rental, because keyword alerts poll the whole newest-first
        # feed — without this guard the mygewo channel would receive the entire
        # Wien rental market.
        if not is_coop_listing(listing):
            continue
        if not channel_match_any(listing, channel_alerts):
            continue
        if not validate_url(listing.url):            # CLAUDE.md hard rule 2
            logger.warning(f"🚫 broken URL, skipping: {listing.url}")
            handler.mark_url_invalid(listing.url)
            continue
        if no_send:
            logger.info(f"[no-send] would alert: {listing.url}")
            sent += 1
            continue
        # mygewo units carry no coop_kind of their own — they are the default feed.
        kind = getattr(listing, "coop_kind", None) or "mygewo"
        bot, chat_id = bots.get(kind), chat_ids.get(kind)
        if not bot or not chat_id or not ledger_ready:
            continue
        # Claim BEFORE sending. The listings doc cannot be the gate: the
        # duplicate and invalid upsert paths never create one at this url, so
        # `sent_to_telegram` had nothing to latch onto and the unit went out on
        # every poll. Cost of claiming first: a crash between here and the send
        # drops this unit permanently. Deliberate — silence over spam.
        key = channel_dedup_key(listing)
        if not handler.claim_channel_send(chat_id, key, listing.url):
            continue
        if bot.send_message(format_coop_message(listing)):
            handler.mark_channel_send_sent(chat_id, key)
            # Best-effort, for the dashboard only — no longer the send gate.
            handler.mark_sent(listing.url)
            sent += 1
        else:
            # Release, or one bad minute at Telegram silences the unit forever.
            handler.release_channel_send(chat_id, key)
            logger.error(f"❌ send failed (retry next run): {listing.url}")

    logger.info(f"📱 coop: {sent} alerted/queued from {len(seen)} seen "
                f"across {ok_adapters}/{len(coop.SOURCES)} adapters")
    handler.close()
    return 0


def main():
    init_sentry()
    parser = argparse.ArgumentParser(description="Fast co-op poll → Telegram alerts")
    parser.add_argument("--no-send", "--dry-run", dest="no_send", action="store_true",
                        help="poll and upsert but skip Telegram sends "
                             "(--dry-run kept as a deprecated alias)")
    args = parser.parse_args()
    raise SystemExit(run(no_send=args.no_send))


if __name__ == "__main__":
    main()
