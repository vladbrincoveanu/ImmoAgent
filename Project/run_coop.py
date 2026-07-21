#!/usr/bin/env python3
"""Fast co-op poll → instant Telegram alerts.

Lightweight (requests + bs4, no Selenium, no scoring/geocoding): polls the
Genossenschaft Bauträger adapters, upserts new units, and DMs matches that
pass the coop_alerts filter. Built for GitHub Actions cron */5.

Run from Project/:  python run_coop.py [--no-send]
"""
import argparse
import hashlib
import json
import logging
import os
from dataclasses import asdict
from typing import List, Optional, Tuple

import requests

from Domain.listing import Listing
from Domain.sources import Source
from Application.helpers.utils import load_config
from Application.scraping import genossenschaft_scraper as coop
from Application.coop_format import format_coop_message
from Application.helpers.listing_validator import validate_url
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_coop")


def load_coop_alerts() -> dict:
    """Alert filter. Precedence: COOP_ALERTS env (JSON) > config.json coop_alerts
    > Project/coop_alerts.json > {} (send all). config.json is gitignored/absent
    in CI, so the tracked coop_alerts.json is the CI-visible source."""
    env = os.environ.get("COOP_ALERTS")
    if env:
        try:
            data = json.loads(env)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            logger.warning("COOP_ALERTS env is not valid JSON; ignoring")
    cfg = load_config() or {}
    if isinstance(cfg.get("coop_alerts"), dict):
        return cfg["coop_alerts"]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coop_alerts.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def matches_coop_alerts(listing: Listing, alerts: dict) -> bool:
    """True if the listing passes the (optional) alert filter. Empty/missing
    filter field = no constraint. Missing LISTING field = permissive (never
    excludes) — for a single power-user, speed/coverage beats precision."""
    bezirke = alerts.get("bezirke") or []
    if bezirke and listing.bezirk and listing.bezirk not in bezirke:
        return False
    max_cost = alerts.get("max_cost")
    if max_cost is not None and listing.price_total is not None and listing.price_total > max_cost:
        return False
    min_rooms = alerts.get("min_rooms")
    if min_rooms is not None and listing.rooms is not None and listing.rooms < min_rooms:
        return False
    min_area = alerts.get("min_area")
    if min_area is not None and listing.area_m2 is not None and listing.area_m2 < min_area:
        return False
    return True


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
    """Fetch one adapter with conditional GET; parse only when the page changed."""
    meta = handler.get_source_meta(name) or {}
    changed, html_text, new_meta = conditional_fetch(cfg["url"], meta, session=session)
    if new_meta:
        handler.set_source_meta(name, **new_meta)
    if not changed:
        logger.info(f"↔️  {name}: unchanged, skipping parse")
        return []
    if cfg.get("fetcher"):
        # Self-contained crawl (mygewo pages its full inventory via an RPC); the
        # change-gate above still gets us the free 304/unchanged skip on the SSR
        # page, but the listings come from the fetcher, not the fetched HTML.
        listings = getattr(coop, cfg["fetcher"])(cfg.get("states", "28_"))
    else:
        listings = getattr(coop, cfg["parser"])(html_text)
    logger.info(f"🔍 {name}: {len(listings)} listing(s) parsed")
    return listings


def run(no_send: bool = False) -> int:
    """Poll → upsert → alert. Exit 0 unless MongoDB is down or ALL adapters fail."""
    alerts = load_coop_alerts()
    handler = MongoDBHandler()
    if handler.collection is None:
        logger.error("❌ No MongoDB connection; aborting")
        return 1

    bot = None
    if not no_send:
        token = os.environ.get("TELEGRAM_MAIN_BOT_TOKEN")
        # Coop alerts go ONLY to the coop channel — the main channel excludes
        # co-ops by design, so no TELEGRAM_MAIN_CHAT_ID fallback here.
        chat_id = os.environ.get("TELEGRAM_COOP_CHANNEL_ID")
        if token and chat_id:
            bot = TelegramBot(token, chat_id)
        else:
            logger.error("❌ TELEGRAM_COOP_CHANNEL_ID/bot token not set; "
                         "alerts DISABLED, polling/upserts continue")

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

    for listing in seen:
        # mygewo units store the aggregator URL; resolve the builder's own
        # reservation page once (reuse a previously-resolved value from the DB so
        # we only fetch a detail page for genuinely new offers).
        if "mygewo.at" in (listing.url or "") and not listing.builder_url:
            existing = handler.get_listing(listing.url) or {}
            listing.builder_url = existing.get("builder_url") or coop.resolve_builder_url(listing.url)
        handler.upsert_coop_listing(_to_doc(listing))

    sent = 0
    for listing in seen:
        if not matches_coop_alerts(listing, alerts):
            continue
        doc = handler.get_listing(listing.url)
        if doc and doc.get("sent_to_telegram"):
            continue
        if not validate_url(listing.url):            # CLAUDE.md hard rule 2
            logger.warning(f"🚫 broken URL, skipping: {listing.url}")
            handler.mark_url_invalid(listing.url)
            continue
        if no_send:
            logger.info(f"[no-send] would alert: {listing.url}")
            sent += 1
            continue
        if bot and bot.send_message(format_coop_message(listing)):
            handler.mark_sent(listing.url)
            sent += 1
        elif bot:
            logger.error(f"❌ send failed (retry next run): {listing.url}")

    logger.info(f"📱 coop: {sent} alerted/queued from {len(seen)} seen "
                f"across {ok_adapters}/{len(coop.SOURCES)} adapters")
    handler.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Fast co-op poll → Telegram alerts")
    parser.add_argument("--no-send", "--dry-run", dest="no_send", action="store_true",
                        help="poll and upsert but skip Telegram sends "
                             "(--dry-run kept as a deprecated alias)")
    args = parser.parse_args()
    raise SystemExit(run(no_send=args.no_send))


if __name__ == "__main__":
    main()
