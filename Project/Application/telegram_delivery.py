import logging
import math
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Set, Tuple

from Application.helpers.listing_validator import compute_content_fingerprint, validate_url


logger = logging.getLogger(__name__)

VIENNA_CHANNEL = "vienna"
VIENNA_MIN_AREA_M2 = 75.0
VIENNA_MIN_ROOMS = 3.0
DELIVERY_STATE_FIELDS = (
    "telegram_delivery",
    "sent_to_telegram",
    "sent_to_telegram_at",
    "url_is_valid",
)


def listing_dict(listing: Any) -> Dict[str, Any]:
    """Return a shallow listing mapping without changing the source value."""
    if isinstance(listing, Mapping):
        return dict(listing)
    if is_dataclass(listing) and not isinstance(listing, type):
        return asdict(listing)
    if hasattr(listing, "__dict__"):
        return dict(vars(listing))
    return dict(listing)


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _policy_number(value: Any) -> Optional[float]:
    if isinstance(value, (str, bytes, bytearray)):
        return None
    return _finite_number(value)


_MISSING = object()


def vienna_filter_reason(
    listing: Any,
    score: Any,
    score_threshold: Any = _MISSING,
) -> Optional[str]:
    data = listing_dict(listing)
    if score_threshold is _MISSING:
        score_threshold = score
        score = data.get("score")
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return "missing or invalid URL"

    for field, minimum in (
        ("area_m2", VIENNA_MIN_AREA_M2),
        ("rooms", VIENNA_MIN_ROOMS),
    ):
        value = _policy_number(data.get(field))
        if value is None:
            return f"missing or invalid {field}"
        if value < minimum:
            return f"{field} {value:g} is below minimum {minimum:g}"

    score_value = _policy_number(score)
    if score_value is None:
        return "missing or invalid score"
    threshold_value = _policy_number(score_threshold)
    if threshold_value is None:
        return "missing or invalid score threshold"
    if score_value <= threshold_value:
        return f"score {score_value:g} does not exceed threshold {threshold_value:g}"
    return None


def delivery_keys(listing: Any) -> Tuple[str, ...]:
    data = listing_dict(listing)
    fingerprint = compute_content_fingerprint(data)
    url = data.get("url")
    if isinstance(url, str):
        return (url, fingerprint)
    return (fingerprint,)


def preserve_delivery_state(existing: Any, replacement: Any) -> Dict[str, Any]:
    result = listing_dict(replacement)
    prior = listing_dict(existing)
    for field in DELIVERY_STATE_FIELDS:
        if field in prior:
            result[field] = prior[field]
    return result


def send_vienna_listings(listings, bot, mongo, url_validator=validate_url) -> int:
    sent_count = 0
    seen_keys: Set[str] = set()
    score_threshold = getattr(bot, "min_score_threshold", 40)

    for listing in listings:
        try:
            data = listing_dict(listing)
            reason = vienna_filter_reason(data, data.get("score"), score_threshold)
            if reason is not None:
                logger.info("Skipping Vienna listing %r: %s", data.get("url"), reason)
                continue

            keys = delivery_keys(data)
            if seen_keys.intersection(keys):
                logger.info("Skipping same-run Vienna duplicate: %s", data["url"])
                continue

            url = data["url"]
            fingerprint = keys[-1]
        except Exception as exc:
            logger.error("Skipping Vienna candidate during preparation: %s", exc)
            continue

        try:
            url_is_valid = url_validator(url)
        except Exception as exc:
            logger.warning("Vienna URL validation failed for %s: %s", url, exc)
            url_is_valid = False
        if not url_is_valid:
            logger.warning("Skipping Vienna listing with invalid URL: %s", url)
            try:
                mongo.mark_url_invalid(url)
            except Exception as exc:
                logger.error("Could not mark Vienna URL invalid (%s): %s", url, exc)
            continue

        try:
            claimed = mongo.claim_listing_delivery(url, fingerprint, VIENNA_CHANNEL)
        except Exception as exc:
            logger.error("Could not claim Vienna listing %s: %s", url, exc)
            continue
        seen_keys.update(keys)
        if not claimed:
            logger.info("Skipping Vienna listing already claimed: %s", url)
            continue

        try:
            delivered = bot.send_property_notification(data)
        except Exception as exc:
            logger.error("Vienna Telegram send failed for %s: %s", url, exc)
            delivered = False

        if not delivered:
            try:
                mongo.release_listing_delivery(url, fingerprint, VIENNA_CHANNEL)
            except Exception as exc:
                logger.error("Could not release Vienna listing %s: %s", url, exc)
            continue

        try:
            marked = mongo.mark_listing_delivery_sent(url, fingerprint, VIENNA_CHANNEL)
        except Exception as exc:
            logger.error("Could not mark sent Vienna listing %s: %s", url, exc)
            marked = False
        if marked:
            sent_count += 1
            continue

        try:
            quarantined = mongo.quarantine_listing_delivery(
                url, fingerprint, VIENNA_CHANNEL
            )
        except Exception as exc:
            logger.error("Could not quarantine Vienna listing %s: %s", url, exc)
        else:
            if not quarantined:
                logger.error("Could not quarantine Vienna listing %s", url)

    return sent_count
