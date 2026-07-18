#!/usr/bin/env python3
"""Fast co-op poll → instant Telegram alerts.

Lightweight (requests + bs4, no Selenium, no scoring/geocoding): polls the
Genossenschaft Bauträger adapters, upserts new units, and DMs matches that
pass the coop_alerts filter. Built for GitHub Actions cron */5.

Run from Project/:  python run_coop.py [--dry-run]
"""
import json
import logging
import os

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
