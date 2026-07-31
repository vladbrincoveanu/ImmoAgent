"""Match newly seen listings against user-created alerts.

Users create these on /alerts: a handful of free-text keys, optional size, room
and price gates, plus at least one channel (Telegram chat id, confirmed email,
or both). The poller tests every newly seen ad against every active alert and
returns the pairs to deliver.

Two rules carry the design.

Keys are OR, not AND. They are how a user lists synonyms for one thing —
"Ablöse, Weitergabe, Nachmieter" — so requiring all of them would let a single
absent word silently disable the alert.

A listing field the source did not publish never FAILS a gate. Newest-first list
pages routinely omit size and rooms, and treating unknown as too-small would
drop exactly the fresh ads this poller exists to catch. Those matches are
delivered flagged `unverified` instead.

Matching is substring, case-insensitive, across title + address + district + the
ad body. The body is the important part: "Nachmieter gesucht" and the district
are usually buried in the description, so a title-only match would miss most of
the feed.
"""
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The numeric gates, kept as data so adding one is a single line and cannot
# forget the null rule. Each entry is (alert filter key, Listing attribute).
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
    """The alert's keys, lowercased and stripped, empties dropped.

    Falls back to the legacy scalar `keyword` when `keywords` is absent, so
    alerts created before multi-key support keep working with no migration."""
    raw = alert.get("keywords")
    if not raw:
        legacy = alert.get("keyword")
        raw = [legacy] if legacy else []
    return [k.strip().lower() for k in raw if k and k.strip()]


def keyword_hit(alert: Dict, listing) -> bool:
    """True when ANY of the alert's keys appears in the ad.

    No keys at all means "everything on this feed" — deliberate, so a user can
    watch the whole stream without inventing a term."""
    keys = alert_keywords(alert)
    if not keys:
        return True
    haystack = searchable_text(listing)
    return any(k in haystack for k in keys)


def gate_result(alert: Dict, listing) -> Tuple[bool, bool]:
    """(passes, unverified) for one alert's numeric filters.

    `unverified` is True only when a gate IS set and the field it reads is None.
    An alert with no gates has nothing it failed to check, so flagging it would
    put a warning on every single message."""
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
    """True when this alert wants this listing, ignoring the unverified flag.

    Retained for callers that only need a boolean."""
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
    out: List[Tuple[Dict, object, bool]] = []
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
                out.append((alert, listing, unverified))
    return out
