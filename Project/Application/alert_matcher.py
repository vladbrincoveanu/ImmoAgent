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


def searchable_text(listing) -> str:
    """The text an alert keyword is tested against, lowercased."""
    parts = [
        getattr(listing, "title", None),
        getattr(listing, "address", None),
        getattr(listing, "bezirk", None),
        getattr(listing, "description", None),
    ]
    return " ".join(p for p in parts if p).lower()


def alert_matches(alert: Dict, listing) -> bool:
    """True when this alert wants this listing.

    An empty keyword means "every hit on this feed" — deliberate, so a user can
    watch the whole private-transfer stream without inventing a term."""
    keyword = (alert.get("keyword") or "").strip().lower()
    if not keyword:
        return True
    return keyword in searchable_text(listing)


def channels_for(alert: Dict) -> Tuple[Optional[str], Optional[str]]:
    """(telegram_chat_id, email) for one alert, each None when unusable.

    Email is only returned when confirmed — `get_active_alerts` already filters
    on that, but an alert may carry an unconfirmed address alongside a confirmed
    Telegram id, and mailing it would be delivery to an unverified third party."""
    chat_id = alert.get("telegram_chat_id") or None
    email = alert.get("email") if alert.get("confirmed") else None
    return chat_id, email or None


def match(listings: List, alerts: List[Dict]) -> List[Tuple[Dict, object]]:
    """Every (alert, listing) pair that should be delivered.

    Order is alert-major so one noisy listing cannot starve later alerts if the
    caller truncates."""
    pairs: List[Tuple[Dict, object]] = []
    for alert in alerts:
        chat_id, email = channels_for(alert)
        if not chat_id and not email:
            # An alert with no reachable channel is a record of nothing. Say so:
            # silently skipping it looks identical to "no matches" to the user.
            logger.warning(
                f"alert {alert.get('_id')} has no usable channel — skipping")
            continue
        for listing in listings:
            if alert_matches(alert, listing):
                pairs.append((alert, listing))
    return pairs
