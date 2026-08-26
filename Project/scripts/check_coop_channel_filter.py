#!/usr/bin/env python3
"""Report exactly what the co-op Telegram channels will and will not carry.

    python Project/scripts/check_coop_channel_filter.py [--limit N] [--all]

Answers one question against production data: "is my channel governed by the
alert I set, and nothing else?" It reads the same alert rows and calls the same
`run_coop.channel_match` the poller does, so its verdict cannot drift from the
poller's — a diagnostic that re-derived the filter could reassure the owner about
a channel that then misbehaves.

Read-only. It sends nothing, writes nothing and touches no ledger row.

Two things it is designed to expose:

  * Alerts that constrain NOTHING. The channel filter is a UNION, so one alert
    with no keywords and no gates would broadcast the entire feed. Those rows are
    listed separately as NOT governing.
  * Alerts that are not yours. The union spans every subscription of these kinds,
    whoever created it, so the report prints the owner of each one.

By default only units that would be sent are listed; `--all` adds the excluded
ones with the reason, which is what you want when a unit you expected never
arrived.
"""
import argparse
import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import run_coop                                                      # noqa: E402
from Application.alert_matcher import (alert_keywords, gate_result,  # noqa: E402
                                       keyword_hit, rubric_hit)
from Integration.mongodb_handler import MongoDBHandler               # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("check_coop_channel_filter")

# The attributes the matcher reads. Listed explicitly because Mongo omits absent
# fields entirely: `SimpleNamespace(**doc)` would raise AttributeError on exactly
# the sparse units whose gates most need evaluating.
_UNIT_FIELDS = ("title", "address", "bezirk", "description",
                "area_m2", "rooms", "price_total", "coop_kind",
                "bautraeger", "url")


def doc_to_unit(doc: dict):
    """A stored co-op doc as something the alert matcher can read."""
    return SimpleNamespace(**{f: doc.get(f) for f in _UNIT_FIELDS})


def describe_alert(alert: dict) -> dict:
    """One alert as the report shows it.

    `gates` keeps only non-null values: `{"min_area": None}` is the all-null
    shape of the old static filter, and printing it as a gate would claim the
    channel is narrowed when it is not."""
    filters = alert.get("filters") or {}
    return {
        "id": str(alert.get("_id")),
        "kind": alert.get("kind"),
        "owner": alert.get("email") or alert.get("telegram_chat_id") or "—",
        "keywords": alert_keywords(alert),
        "gates": {k: v for k, v in filters.items() if v is not None},
        "governs": run_coop.channel_alert_constrains(alert),
    }


def _exclusion_reason(alert: dict, unit) -> str:
    """Why this alert refused this unit — the poller's own order of checks."""
    if not run_coop.channel_alert_constrains(alert):
        return "alert constrains nothing"
    if not rubric_hit(alert, unit):
        return "not a private transfer"
    if not keyword_hit(alert, unit):
        return "no keyword match"
    passes, unverified = gate_result(alert, unit)
    if not passes:
        return "outside gates"
    if unverified:
        return "gate set but field missing (channel is strict)"
    return "matched"


def preview(docs, alerts) -> list:
    """Per unit: which alerts admit it to a channel, and whether any does.

    Units nothing admits are included too — a report that listed only the sends
    could not tell "correctly filtered out" apart from "never scraped"."""
    rows = []
    for doc in docs:
        unit = doc_to_unit(doc)
        matched = [str(a.get("_id")) for a in alerts
                   if run_coop.channel_match(a, unit)]
        rows.append({
            "url": doc.get("url"),
            "title": doc.get("title") or doc.get("address") or "—",
            "matched_by": matched,
            "would_send": bool(matched),
            "reasons": ([] if matched else
                        sorted({_exclusion_reason(a, unit) for a in alerts})),
        })
    return rows


def report(alerts, docs, show_all=False) -> None:
    described = [describe_alert(a) for a in alerts]
    governing = [d for d in described if d["governs"]]
    ignored = [d for d in described if not d["governs"]]

    logger.info("\n=== ALERTS THAT GOVERN THE CHANNEL "
                f"({len(governing)} of {len(described)}) ===")
    for d in governing:
        logger.info(f"  [{d['kind']}] {d['id']}  owner={d['owner']}\n"
                    f"      keywords={d['keywords'] or '(none — kind is the filter)'}"
                    f"  gates={d['gates'] or '(none)'}")
    if not governing:
        logger.info("  (none — the channels stay SILENT)")

    if ignored:
        logger.info(f"\n=== ALERTS THAT DO **NOT** GOVERN ({len(ignored)}) ===")
        logger.info("  No keywords and no gates: these would have broadcast the "
                    "whole feed, so the channel ignores them.")
        for d in ignored:
            logger.info(f"  [{d['kind']}] {d['id']}  owner={d['owner']}")

    rows = preview(docs, alerts)
    sends = [r for r in rows if r["would_send"]]
    logger.info(f"\n=== WOULD BROADCAST {len(sends)} of {len(rows)} stored "
                f"co-op unit(s) ===")
    logger.info("(Units already in the send ledger are NOT re-sent; this shows "
                "what the filter admits, not what the next poll will deliver.)")
    for r in sends:
        logger.info(f"  ✅ {r['title'][:70]}\n     {r['url']}\n"
                    f"     via alert(s): {r['matched_by']}")
    if show_all:
        for r in (r for r in rows if not r["would_send"]):
            logger.info(f"  ⛔ {r['title'][:70]}\n     {r['url']}\n"
                        f"     excluded: {r['reasons']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show what the co-op channels would carry (read-only)")
    parser.add_argument("--limit", type=int, default=200,
                        help="how many stored co-op units to evaluate")
    parser.add_argument("--all", action="store_true", dest="show_all",
                        help="also list excluded units and why")
    args = parser.parse_args()

    handler = MongoDBHandler()
    if handler.collection is None:
        logger.error("❌ No MongoDB connection; aborting")
        return 1
    try:
        alerts = handler.get_alert_subscriptions(run_coop.ALERT_KINDS)
        docs = list(handler.get_coop_listings_for_seed())[:args.limit]
        report(alerts, docs, show_all=args.show_all)
    finally:
        handler.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
