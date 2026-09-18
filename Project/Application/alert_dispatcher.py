"""Durable delivery for user-created alert matches.

The poller must not rely on its in-memory list of newly seen ads: a process can
die after the database upsert and before the network send. A claim row makes the
pair visible to a later retry while preventing concurrent polls from sending the
same alert twice.
"""
import hashlib
import html
import logging
from typing import Callable, Optional
from urllib.parse import urlparse

from Application.alert_matcher import channels_for

logger = logging.getLogger(__name__)

TELEGRAM_MAX_CHARS = 4096
UNVERIFIED_PREFIX = "⚠️ Größe/Zimmer/Preis unbekannt — vor Ort prüfen\n"


def is_sendable_url(url: Optional[str]) -> bool:
    """Reject malformed destinations before claiming or sending an alert."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def url_hash(url: str) -> str:
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


def _number(value, suffix: str = "") -> str:
    if value is None:
        return "?"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def build_message(listing, unverified: bool) -> str:
    """Build a bounded Telegram-safe message from one listing."""
    title = html.escape(getattr(listing, "title", None) or "Neues Inserat")
    district = getattr(listing, "bezirk", None)
    link = getattr(listing, "builder_url", None) or getattr(listing, "url", "")
    facts = " · ".join([
        f"{_number(getattr(listing, 'rooms', None))} Zi",
        f"{_number(getattr(listing, 'area_m2', None))} m²",
        f"{_number(getattr(listing, 'price_total', None), ' €')}",
    ])
    lines = [f"🔔 <b>{title}</b>"]
    if district:
        lines.append(f"📍 {html.escape(str(district))}")
    lines.append(facts)
    if getattr(listing, "coop_kind", None) == "private_transfer":
        lines.append("🤝 Private Weitergabe / Ablöse")
    if link:
        lines.append(html.escape(str(link), quote=False))
    message = "\n".join(lines)
    if unverified:
        message = UNVERIFIED_PREFIX + message
    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[: TELEGRAM_MAX_CHARS - 1] + "…"
    return message


def _default_telegram(token: str) -> Callable[[str, str], bool]:
    from Integration.telegram_bot import TelegramBot

    def send(chat_id: str, message: str) -> bool:
        return bool(TelegramBot(token, chat_id).send_message(message))

    return send


def _default_email() -> Callable[[str, object], bool]:
    from Application.alert_email import send_alert_email

    def send(address: str, listing) -> bool:
        return bool(send_alert_email(address, listing))

    return send


def dispatch(
    alert: dict,
    listing,
    unverified: bool,
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
    send_email: Optional[Callable[[str, object], bool]] = None,
) -> bool:
    """Deliver one alert pair and return whether a channel succeeded."""
    chat_id, email_address = channels_for(alert)
    if not chat_id and not email_address:
        return False
    if not is_sendable_url(getattr(listing, "url", None)):
        logger.warning("alert delivery skipped, unusable url: %r",
                       getattr(listing, "url", None))
        return False

    key = url_hash(listing.url)
    message = build_message(listing, unverified)
    if not handler.claim_delivery(alert.get("_id"), key, chat_id, message):
        return False

    delivered = False
    if chat_id and token:
        sender = send_telegram or _default_telegram(token)
        try:
            delivered = bool(sender(chat_id, message)) or delivered
        except Exception as exc:
            logger.error("alert telegram send failed (%s): %s", chat_id, exc)
    if email_address:
        sender = send_email or _default_email()
        try:
            delivered = bool(sender(email_address, listing)) or delivered
        except Exception as exc:
            logger.error("alert email send failed (%s): %s", email_address, exc)

    if delivered:
        handler.mark_delivery_sent(alert.get("_id"), key)
    else:
        logger.error("alert %s delivery failed; row left pending", alert.get("_id"))
    return delivered


def retry_pending(
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
) -> int:
    """Retry stale Telegram claims left pending by an interrupted poll."""
    try:
        rows = list(handler.stale_pending_deliveries() or [])
    except Exception as exc:
        logger.error("could not load pending deliveries: %s", exc)
        return 0
    if not rows:
        return 0
    if not token:
        return 0
    sender = send_telegram or _default_telegram(token)
    resent = 0
    for row in rows:
        chat_id, message = row.get("chat_id"), row.get("message")
        if not chat_id or not message:
            continue
        try:
            if sender(chat_id, message):
                handler.mark_delivery_sent(row.get("alert_id"), row.get("url_hash"))
                resent += 1
        except Exception as exc:
            logger.error("alert retry failed for %s: %s", chat_id, exc)
    return resent
