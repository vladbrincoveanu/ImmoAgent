"""Deliver one matched (alert, listing) pair exactly once.

The problem this solves: the previous path iterated an in-memory list of newly
seen listings and sent from it. A poll that died between the Mongo upsert and
the Telegram send lost that ad permanently — the next poll no longer considered
it new, so it was never delivered and nothing recorded that it hadn't been.

The ledger fixes both halves. `claim_delivery` is atomic, so concurrent polls
cannot double-send. A claimed row that is never marked sent is a visible record
of a failed delivery, and `retry_pending` picks it up on the next poll.

Every sender is injected so the tests run without network or Mongo.

## Note on URL validation

Project rule 2 requires `listing_validator.validate_url` before anything is
displayed or sent. That function performs a live GET of up to 50KB. Running it
here would put a second network round trip on the critical path of a
first-come-first-served alert, and would re-fetch a page the poller downloaded
successfully seconds earlier — `scrape_single_listing` only returns a Listing
after a 200. So this module does a structural check instead, and the expensive
liveness check stays where it already runs, in the scrape path. A dead URL
cannot reach here without also having been alive one poll earlier.
"""
import hashlib
import html
import logging
from typing import Callable, Optional
from urllib.parse import urlparse

from Application.alert_matcher import channels_for

logger = logging.getLogger(__name__)

# Telegram's hard limit. The formatter is bounded, but an ad body is not, so the
# message is truncated defensively rather than rejected by the API at 2am.
TELEGRAM_MAX_CHARS = 4096

UNVERIFIED_PREFIX = "⚠️ Größe/Zimmer/Preis unbekannt — vor Ort prüfen\n"


def is_sendable_url(url: Optional[str]) -> bool:
    """Structural URL check — see the module docstring for why not validate_url."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def url_hash(url: str) -> str:
    """Stable per-ad key for the ledger, matching the project's dedup scheme."""
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


def _num(value, suffix: str = "") -> str:
    """Render a number for the message, or an explicit '?' when unknown.

    '?' rather than a blank: a missing value is information here — it is why the
    unverified banner is on the message — and a blank reads as zero."""
    if value is None:
        return "?"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def build_message(listing, unverified: bool) -> str:
    """The Telegram body for one alert hit, truncated to the API limit.

    Deliberately NOT `coop_format.format_coop_message`: that one opens with
    "🏢 Genossenschaft" and a "Vergabe:" line, which is right for the co-op feed
    and wrong for most of what keyword alerts now match. Since the alert feed is
    the whole newest-first rental list, the framing has to be neutral, and the
    co-op detail is added only when the listing actually is one.

    parse_mode is HTML (TelegramBot's default), so scraped free text is escaped —
    Telegram rejects a message containing an unescaped & or < in the body."""
    title = html.escape(listing.title) if getattr(listing, "title", None) else "Neues Inserat"
    bezirk = html.escape(listing.bezirk) if getattr(listing, "bezirk", None) else None
    link = getattr(listing, "builder_url", None) or listing.url
    url = html.escape(link, quote=False) if link else ""

    price = getattr(listing, "price_total", None)
    facts = " · ".join([
        f"{_num(getattr(listing, 'rooms', None))} Zi",
        f"{_num(getattr(listing, 'area_m2', None))} m²",
        f"{_num(price, ' €')}" if price is not None else "? €",
    ])

    lines = [f"🔔 <b>{title}</b>"]
    if bezirk:
        lines.append(f"📍 {bezirk}")
    lines.append(facts)
    if getattr(listing, "coop_kind", None) == "private_transfer":
        lines.append("🤝 Private Weitergabe / Ablöse")
    lines.append(url)

    body = "\n".join(line for line in lines if line)
    if unverified:
        body = UNVERIFIED_PREFIX + body
    if len(body) > TELEGRAM_MAX_CHARS:
        body = body[: TELEGRAM_MAX_CHARS - 1] + "…"
    return body


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


def _default_email_content() -> Callable[[str, str, str], bool]:
    from Application.alert_email import send_alert_email_content

    def send(address: str, subject: str, body: str) -> bool:
        return bool(send_alert_email_content(address, subject, body))

    return send


def _mark_delivery_channel_sent(handler, alert_id, key: str, channel: str,
                                legacy_telegram: bool = False) -> None:
    try:
        if legacy_telegram and channel == "telegram":
            # Rows created before channel flags existed are Telegram-only.
            handler.mark_delivery_sent(alert_id, key)
        else:
            handler.mark_delivery_channel_sent(alert_id, key, channel)
    except Exception as e:
        logger.error(f"❌ could not mark alert {channel} delivery sent: {e}")


def dispatch(
    alert: dict,
    listing,
    unverified: bool,
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
    send_email: Optional[Callable[[str, object], bool]] = None,
) -> bool:
    """Deliver one pair. True only when something was actually sent.

    Never raises: one dead channel must not abort the poll that feeds the
    website."""
    chat_id, email = channels_for(alert)
    if not chat_id and not email:
        return False

    if not is_sendable_url(getattr(listing, "url", None)):
        logger.warning(
            f"alert delivery skipped, unusable url: {getattr(listing, 'url', None)!r}")
        return False

    alert_id, key = alert.get("_id"), url_hash(listing.url)
    message = build_message(listing, unverified)
    email_subject = email_body = None
    if email:
        from Application.alert_email import build_alert_email

        email_subject, email_body = build_alert_email(listing)
    # The message and destination go onto the claim row BEFORE the send. That is
    # what makes retry possible without a url_hash -> listing reverse lookup,
    # which the schema does not support.
    if not handler.claim_delivery(
        alert_id, key, chat_id, message, email, email_subject, email_body
    ):
        # Someone already owns this pair. Not an error — this is the guarantee.
        return False

    delivered = False

    if chat_id and token:
        sender = send_telegram or _default_telegram(token)
        try:
            if sender(chat_id, message):
                delivered = True
                _mark_delivery_channel_sent(handler, alert_id, key, "telegram")
        except Exception as e:
            logger.error(f"❌ alert telegram send failed ({chat_id}): {e}")

    if email:
        sender = send_email or _default_email()
        try:
            if sender(email, listing):
                delivered = True
                _mark_delivery_channel_sent(handler, alert_id, key, "email")
        except Exception as e:
            logger.error(f"❌ alert email send failed ({email}): {e}")

    if delivered:
        logger.info(f"✅ alert {alert_id} delivery channel succeeded")
    else:
        # The row stays `pending` on purpose. That is the retry signal, and it is
        # also the only durable evidence that a delivery was attempted and lost.
        logger.error(f"❌ alert {alert_id} delivery failed; row left pending")
    return delivered


def retry_pending(
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
    send_email: Optional[Callable[[str, str, str], bool]] = None,
) -> int:
    """Re-send deliveries that were claimed but never sent. Returns the count.

    This is what makes the guarantee at-LEAST-once rather than at-most-once. A
    poll that dies between the claim and the send leaves a `pending` row; every
    later poll picks it up. Because the row carries the rendered message and the
    destination, no listing lookup is needed — the ad may not even be "new" any
    more by the time this runs.

    Both channels are retried from their stored destination and rendered content;
    no current alert or listing lookup is needed."""
    try:
        # Materialised inside the try: a handler that returns a cursor can fail
        # on iteration rather than on the call, and that must not abort the poll.
        rows = list(handler.stale_pending_deliveries() or [])
    except Exception as e:
        logger.error(f"❌ could not load pending deliveries: {e}")
        return 0
    if not rows:
        return 0
    logger.warning(f"↻ retrying {len(rows)} pending alert delivery(ies)")
    resent = 0
    for row in rows:
        chat_id, message = row.get("chat_id"), row.get("message")
        telegram_sent = bool(row.get("telegram_sent", False))
        email = row.get("email")
        email_subject = row.get("email_subject")
        email_body = row.get("email_body")
        email_sent = bool(row.get("email_sent", False))
        legacy_telegram = not any(
            key in row for key in
            ("email", "email_subject", "email_body", "telegram_sent", "email_sent")
        )
        row_delivered = False

        if chat_id and message and token and not telegram_sent:
            sender = send_telegram or _default_telegram(token)
            try:
                if sender(chat_id, message):
                    _mark_delivery_channel_sent(
                        handler, row.get("alert_id"), row.get("url_hash"),
                        "telegram", legacy_telegram=legacy_telegram,
                    )
                    row_delivered = True
            except Exception as e:
                # Stays pending, gets picked up again next poll.
                logger.error(f"❌ retry failed for {chat_id}: {e}")

        if email and email_subject is not None and email_body is not None and not email_sent:
            sender = send_email or _default_email_content()
            try:
                if sender(email, email_subject, email_body):
                    _mark_delivery_channel_sent(
                        handler, row.get("alert_id"), row.get("url_hash"), "email"
                    )
                    row_delivered = True
            except Exception as e:
                # Stays pending, gets picked up again next poll.
                logger.error(f"❌ retry failed for {email}: {e}")
        if row_delivered:
            resent += 1
    return resent
