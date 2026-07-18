#!/usr/bin/env python3
"""Fast co-op poll → instant Telegram alerts.

Lightweight (requests + bs4, no Selenium, no scoring/geocoding): polls the
Genossenschaft Bauträger adapters, upserts new units, and DMs matches that
pass the coop_alerts filter. Built for GitHub Actions cron */5.

Run from Project/:  python run_coop.py [--dry-run]
"""
import hashlib
import json
import logging
import os
from typing import List, Optional, Tuple

import requests

from Domain.listing import Listing
from Application.helpers.utils import load_config

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
