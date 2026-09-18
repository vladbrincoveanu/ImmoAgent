#!/usr/bin/env python3
"""Seed the co-op channel send ledger from units already in Mongo.

Run once, before the first poll that uses the ledger:
    python Project/scripts/seed_coop_channel_ledger.py

Without this, every unit already in the collection looks never-sent to the new
ledger and both channels flood on the first poll after deploy. Accepted cost of
seeding: a unit that was scraped but never actually alerted stays silent forever.

Idempotent — a second run hits the unique index and inserts nothing.
"""
import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from Application.alert_dispatcher import url_hash                    # noqa: E402
from Application.coop_alert_router import route                      # noqa: E402
from Application.helpers.listing_validator import (                  # noqa: E402
    compute_xsrc_fingerprint)
from Integration.mongodb_handler import MongoDBHandler               # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_coop_channel_ledger")

CHANNEL_KINDS = ("mygewo", "private_transfer")


def seed_dedup_key(doc: dict) -> str:
    """The ledger key for a stored co-op doc.

    MUST agree byte-for-byte with `run_coop.channel_dedup_key` for the same unit,
    or seeding suppresses nothing and the flood happens anyway — silently. The
    stored field is only written for is_genossenschaft units, so the computed
    fallback is load-bearing rather than decorative."""
    stored = doc.get("content_fingerprint_xsrc")
    if stored:
        return stored
    # Named fields, not SimpleNamespace(**doc): Mongo omits absent fields
    # entirely, and compute_xsrc_fingerprint reads area/rooms as attributes —
    # `**doc` would raise AttributeError on exactly the sparse units that most
    # need the url_hash fallback.
    unit = SimpleNamespace(
        bautraeger=doc.get("bautraeger"), address=doc.get("address"),
        area_m2=doc.get("area_m2"), rooms=doc.get("rooms"))
    return compute_xsrc_fingerprint(unit) or url_hash(doc.get("url") or "")


def seed(handler) -> int:
    """Mark every stored co-op unit as already sent on every channel.

    Both channels, always: seeding one would leave the other free to flood.
    Returns the number of ledger rows inserted."""
    if not handler.ensure_channel_send_index():
        logger.error("❌ ledger index unavailable; seeding nothing (rows without "
                     "the unique index are not something the send path can trust)")
        return 0

    chat_ids = [chat_id for chat_id in (route(kind) for kind in CHANNEL_KINDS)
                if chat_id]
    if not chat_ids:
        logger.error("❌ no co-op channel configured; nothing to seed")
        return 0

    inserted = 0
    units = 0
    for doc in handler.get_coop_listings_for_seed():
        units += 1
        key = seed_dedup_key(doc)
        for chat_id in chat_ids:
            if handler.seed_channel_send(chat_id, key, doc.get("url")):
                inserted += 1
    logger.info(f"🌱 seeded {inserted} ledger row(s) from {units} co-op unit(s) "
                f"across {len(chat_ids)} channel(s)")
    return inserted


def main() -> int:
    handler = MongoDBHandler()
    if handler.collection is None:
        logger.error("❌ No MongoDB connection; aborting")
        return 1
    try:
        seed(handler)
    finally:
        handler.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
