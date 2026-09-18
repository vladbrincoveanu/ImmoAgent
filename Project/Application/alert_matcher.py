"""Match new private co-op transfers against user-created alerts.

Users create these on /alerts: a free-text keyword plus at least one channel
(Telegram chat id, confirmed email, or both). The poller tests every newly seen
transfer against every active alert and returns the pairs to deliver.

Matching is substring, case-insensitive, across title + address + the ad body.
The body is the important part: "Nachmieter gesucht" and the district are usually
buried in the description, so a title-only match would miss most of the feed.
"""
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Numeric gates are data so the missing-value rule stays consistent across all
# supported fields.
_MIN_GATES = (
    ("min_area", "area_m2"),
    ("min_rooms", "rooms"),
)
_MAX_GATES = (
    ("max_area", "area_m2"),
    ("max_rooms", "rooms"),
    ("max_price", "price_total"),
)


def searchable_text(listing) -> str:
    """The text an alert keyword is tested against, lowercased."""
    parts = [
        getattr(listing, "title", None),
        getattr(listing, "address", None),
        getattr(listing, "bezirk", None),
        getattr(listing, "description", None),
    ]
    return " ".join(p for p in parts if p).lower()


def alert_keywords(alert: Dict) -> List[str]:
    """Return normalized multi-key values, with legacy scalar fallback."""
    raw = alert.get("keywords")
    if not raw:
        legacy = alert.get("keyword")
        raw = [legacy] if legacy else []
    return [k.strip().lower() for k in raw if k and k.strip()]


def keyword_hit(alert: Dict, listing) -> bool:
    """True when any keyword appears in the listing text."""
    keys = alert_keywords(alert)
    if not keys:
        return True
    haystack = searchable_text(listing)
    return any(key in haystack for key in keys)


def gate_result(alert: Dict, listing) -> Tuple[bool, bool]:
    """Return (passes, unverified) for the alert's numeric filters.

    A missing source value never fails a gate. It is flagged instead so a fresh
    ad is not silently dropped merely because its first feed page is sparse.
    """
    filters = alert.get("filters") or {}
    unverified = False
    for key, attr in _MIN_GATES:
        limit = filters.get(key)
        if limit is None:
            continue
        value = getattr(listing, attr, None)
        if value is None:
            unverified = True
        elif value < limit:
            return False, False
    for key, attr in _MAX_GATES:
        limit = filters.get(key)
        if limit is None:
            continue
        value = getattr(listing, attr, None)
        if value is None:
            unverified = True
        elif value > limit:
            return False, False
    return True, unverified


def alert_matches(alert: Dict, listing) -> bool:
    """True when this alert wants this listing, ignoring warning metadata."""
    return keyword_hit(alert, listing) and gate_result(alert, listing)[0]


def channels_for(alert: Dict) -> Tuple[Optional[str], Optional[str]]:
    """(telegram_chat_id, email) for one alert, each None when unusable.

    Email is only returned when confirmed — `get_active_alerts` already filters
    on that, but an alert may carry an unconfirmed address alongside a confirmed
    Telegram id, and mailing it would be delivery to an unverified third party."""
    chat_id = alert.get("telegram_chat_id") or None
    email = alert.get("email") if alert.get("confirmed") else None
    return chat_id, email or None


def match(listings: List, alerts: List[Dict]) -> List[Tuple[Dict, object, bool]]:
    """Every (alert, listing, unverified) triple that should be delivered.

    Order is alert-major so one noisy listing cannot starve later alerts if the
    caller truncates."""
    pairs: List[Tuple[Dict, object, bool]] = []
    for alert in alerts:
        chat_id, email = channels_for(alert)
        if not chat_id and not email:
            # An alert with no reachable channel is a record of nothing. Say so:
            # silently skipping it looks identical to "no matches" to the user.
            logger.warning(
                f"alert {alert.get('_id')} has no usable channel — skipping")
            continue
        for listing in listings:
            if not keyword_hit(alert, listing):
                continue
            passes, unverified = gate_result(alert, listing)
            if passes:
                pairs.append((alert, listing, unverified))
    return pairs
