"""Monthly district (bezirk) rollup: price/m², volume, days-on-market.
Written to the district_snapshots collection for dashboard drift charts."""
import statistics
from typing import Dict, List, Any, Optional


def _days_on_market(listing: Dict[str, Any]) -> Optional[float]:
    """Days between first_scraped_at and taken_at, for COMPLETED cycles only
    (listing_status == 'taken'). Still-active listings are excluded rather
    than measured against "now" - that would make avg_days_on_market drift
    every time the job reruns for the same historical period, which defeats
    the point of a monthly snapshot. first_scraped_at is epoch-seconds
    (per upsert_listing_with_history), taken_at is a datetime (per
    mark_listing_taken). Returns None if the cycle isn't complete or either
    endpoint is missing/malformed."""
    from datetime import datetime
    if listing.get("listing_status") != "taken":
        return None
    first = listing.get("first_scraped_at")
    taken_at = listing.get("taken_at")
    if not first or not isinstance(taken_at, datetime):
        return None
    # first_scraped_at is produced elsewhere via `datetime.utcnow().timestamp()`
    # (see mongodb_handler.py), which treats the naive "UTC" wall-clock value as
    # local time when converting to an epoch. datetime.fromtimestamp() is the
    # matching inverse (also local-time-based), so it round-trips back to the
    # original naive value regardless of the machine's timezone. Using
    # utcfromtimestamp() here would introduce a UTC-offset-sized drift on any
    # non-UTC machine.
    first_dt = datetime.fromtimestamp(first) if isinstance(first, (int, float)) else first
    if not isinstance(first_dt, datetime):
        return None
    return (taken_at - first_dt).total_seconds() / 86400.0


def build_district_snapshot(bezirk: str, period: str, listings: List[Dict[str, Any]],
                             source: str = "scraped") -> Dict[str, Any]:
    prices_per_m2 = []
    active_count = 0
    relisted_count = 0
    days_on_market = []

    for l in listings:
        price = l.get("price_total")
        area = l.get("area_m2")
        if price and area:
            prices_per_m2.append(price / area)
        if l.get("listing_status") == "active":
            active_count += 1
        if l.get("times_relisted"):
            relisted_count += 1
        dom = _days_on_market(l)
        if dom is not None:
            days_on_market.append(dom)

    listing_count = len(listings)
    avg_price_m2 = statistics.fmean(prices_per_m2) if prices_per_m2 else None
    median_price_m2 = statistics.median(prices_per_m2) if prices_per_m2 else None
    avg_days_on_market = statistics.fmean(days_on_market) if days_on_market else None
    relisted_pct = (relisted_count / listing_count * 100) if listing_count else None

    return {
        "bezirk": bezirk,
        "period": period,
        "avg_price_m2": avg_price_m2,
        "median_price_m2": median_price_m2,
        "listing_count": listing_count,
        "active_count": active_count,
        "avg_days_on_market": avg_days_on_market,
        "relisted_pct": relisted_pct,
        "source": source,
    }


def run_monthly_aggregation(mongo_handler, period: str) -> int:
    """Query listings for the given YYYY-MM period, grouped by bezirk, and
    upsert one district_snapshots doc per bezirk. Returns count of docs written."""
    from datetime import datetime
    year, month = (int(x) for x in period.split("-"))
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), (month % 12) + 1, 1)

    cursor = mongo_handler.collection.find({
        "processed_at": {"$gte": start.timestamp(), "$lt": end.timestamp()},
    })
    by_bezirk: Dict[str, List[Dict[str, Any]]] = {}
    for doc in cursor:
        bezirk = doc.get("bezirk")
        if not bezirk:
            continue
        by_bezirk.setdefault(bezirk, []).append(doc)

    written = 0
    for bezirk, docs in by_bezirk.items():
        snap = build_district_snapshot(bezirk, period, docs, source="scraped")
        mongo_handler.db["district_snapshots"].update_one(
            {"bezirk": bezirk, "period": period, "source": "scraped"},
            {"$set": snap},
            upsert=True,
        )
        written += 1
    return written
