"""Deliver one matched (alert, listing) pair exactly once.

The problem this solves: the previous path iterated an in-memory list of newly
seen listings and sent from it. A poll that died between the Mongo upsert and
the Telegram send lost that ad permanently — the next poll no longer considered
it new, so it was never delivered and nothing recorded that it hadn't been.

The ledger fixes both halves. `claim_delivery` is atomic, so concurrent polls
cannot double-send. A claimed row that is never marked sent is a visible record
of a failed delivery, and `retry_pending` picks it up on the next poll.

Every sender and URL validator is injected through module-level seams so the
tests run without network or Mongo.

## Note on URL validation

Project rule 2 requires `listing_validator.validate_url` before anything is
displayed or sent. Dispatch keeps the cheap structural check as a fast reject,
then performs the live validation immediately before claiming a delivery. This
also protects listings that enter the alert path from a source other than the
full scrape pipeline.
"""
import html
import logging
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

from Application.alert_matcher import channels_for
from Application.helpers.listing_validator import compute_xsrc_fingerprint, validate_url
from Application.helpers.url_hash import url_hash

logger = logging.getLogger(__name__)

# Telegram's hard limit. The formatter is bounded, but an ad body is not, so the
# message is truncated defensively rather than rejected by the API at 2am.
TELEGRAM_MAX_CHARS = 4096

UNVERIFIED_PREFIX = "⚠️ Größe/Zimmer/Preis unbekannt — vor Ort prüfen\n"
COOP_ALERT_KINDS = frozenset(("coop_private", "mygewo"))


def is_sendable_url(url: Optional[str]) -> bool:
    """Structural URL check — see the module docstring for why not validate_url."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _validate_url_once(url: str, validation_cache: Dict[str, bool]) -> bool:
    """Live-validate a URL, reusing only successful checks in this poll."""
    if url in validation_cache:
        return validation_cache[url]
    try:
        url_is_valid = bool(validate_url(url))
    except Exception as e:
        logger.warning(f"alert delivery URL validation failed: {e}")
        return False
    # A transient failure must not suppress every later alert for this URL in
    # the same batch, but a successful check is safe to reuse.
    if url_is_valid:
        validation_cache[url] = True
    return url_is_valid


def _coop_delivery_fingerprint(alert, listing) -> Optional[str]:
    """Return an xsrc key only for classified co-op alert deliveries."""
    if ((alert or {}).get("kind") not in COOP_ALERT_KINDS
            or not getattr(listing, "is_genossenschaft", False)):
        return None
    # Let dispatch catch computation failures and defer this delivery. Falling
    # back to a URL key after an exception can duplicate a unit that was claimed
    # earlier under its stable xsrc fingerprint. A deliberate None from the
    # helper still means the record lacks a safe cross-source key and may use
    # the legacy URL key for compatibility.
    return compute_xsrc_fingerprint(listing)


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


def _default_email(unverified: bool = False) -> Callable[[str, object], bool]:
    from Application.alert_email import send_alert_email

    def send(address: str, listing) -> bool:
        return bool(send_alert_email(address, listing, unverified=unverified))

    return send


def _default_email_content() -> Callable[[str, str, str], bool]:
    from Application.alert_email import send_alert_email_content

    def send(address: str, subject: str, body: str) -> bool:
        return bool(send_alert_email_content(address, subject, body))

    return send


def _mark_delivery_channel_sent(handler, alert_id, key: str, channel: str,
                                legacy_telegram: bool = False) -> bool:
    try:
        if legacy_telegram and channel == "telegram":
            # Rows created before channel flags existed are Telegram-only.
            result = handler.mark_delivery_sent(alert_id, key)
        else:
            result = handler.mark_delivery_channel_sent(alert_id, key, channel)
        if result is False:
            logger.error(f"❌ could not mark alert {channel} delivery sent")
            return False
        return True
    except Exception as e:
        logger.error(f"❌ could not mark alert {channel} delivery sent: {e}")
        return False


def _release_delivery_channel(handler, alert_id, key: str, channel: str) -> None:
    release = getattr(handler, "release_delivery_channel", None)
    if not callable(release):
        return
    try:
        if release(alert_id, key, channel) is False:
            logger.error(f"❌ could not release alert {channel} delivery lease")
    except Exception as e:
        logger.error(f"❌ could not release alert {channel} delivery lease: {e}")


def _claim_pending_delivery_channel(handler, alert_id, key: str, channel: str) -> bool:
    claim = getattr(handler, "claim_pending_delivery_channel", None)
    if not callable(claim):
        return True
    try:
        return bool(claim(alert_id, key, channel))
    except Exception as e:
        logger.error(f"❌ could not claim alert {channel} delivery lease: {e}")
        return False


def dispatch(
    alert: dict,
    listing,
    unverified: bool,
    handler,
    token: Optional[str],
    send_telegram: Optional[Callable[[str, str], bool]] = None,
    send_email: Optional[Callable[[str, object], bool]] = None,
    url_validation_cache: Optional[Dict[str, bool]] = None,
    validation_failures: Optional[set[str]] = None,
) -> bool:
    """Deliver one pair. True only when something was actually sent.

    Never raises: one dead channel must not abort the poll that feeds the
    website."""
    chat_id, email = channels_for(alert)
    if not chat_id and not email:
        return False

    canonical_url = getattr(listing, "url", None)
    if not is_sendable_url(canonical_url):
        logger.warning(
            f"alert delivery skipped, unusable url: {canonical_url!r}")
        return False
    validation_cache = url_validation_cache if url_validation_cache is not None else {}
    if not _validate_url_once(canonical_url, validation_cache):
        logger.warning(f"alert delivery skipped, URL failed validation: {canonical_url!r}")
        if validation_failures is not None:
            validation_failures.add(canonical_url)
        return False

    # MyGEWO alerts may display the builder's reservation page instead of the
    # canonical aggregator URL. Validate that URL too: Rule 2 applies to the
    # exact link placed in the Telegram message, not only to the ledger key.
    display_url = getattr(listing, "builder_url", None) or canonical_url
    if not is_sendable_url(display_url):
        logger.warning(f"alert delivery skipped, unusable display URL: {display_url!r}")
        if validation_failures is not None:
            validation_failures.add(canonical_url)
        return False
    if display_url != canonical_url and not _validate_url_once(display_url, validation_cache):
        logger.warning(f"alert delivery skipped, display URL failed validation: {display_url!r}")
        if validation_failures is not None:
            validation_failures.add(canonical_url)
        return False
    if validation_failures is not None:
        validation_failures.discard(canonical_url)

    try:
        alert_id = alert.get("_id")
        fingerprint = _coop_delivery_fingerprint(alert, listing)
        key = fingerprint or url_hash(listing.url)
        message = build_message(listing, unverified)
        email_subject = email_body = None
        if email:
            from Application.alert_email import build_alert_email

            email_subject, email_body = build_alert_email(listing, unverified)
    except Exception as e:
        logger.error(f"❌ alert {alert_id} payload/fingerprint preparation failed: {e}")
        return False
    # The message and destination go onto the claim row BEFORE the send. That is
    # what makes retry possible without a url_hash -> listing reverse lookup,
    # which the schema does not support.
    try:
        claimed = handler.claim_delivery(
            alert_id, key, chat_id, message, email, email_subject, email_body,
            delivery_fingerprint=fingerprint,
            legacy_delivery_url_hash=url_hash(listing.url) if fingerprint else None,
        )
    except Exception as e:
        logger.error(f"❌ alert {alert_id} claim failed: {e}")
        return False
    if not claimed:
        # Someone already owns this pair. Not an error — this is the guarantee.
        return False

    delivered = False

    if chat_id and token:
        sender = send_telegram or _default_telegram(token)
        try:
            if sender(chat_id, message):
                if _mark_delivery_channel_sent(handler, alert_id, key, "telegram"):
                    delivered = True
                else:
                    _release_delivery_channel(handler, alert_id, key, "telegram")
        except Exception as e:
            logger.error(f"❌ alert telegram send failed ({chat_id}): {e}")

    if email:
        sender = send_email or _default_email(unverified)
        try:
            if sender(email, listing):
                if _mark_delivery_channel_sent(handler, alert_id, key, "email"):
                    delivered = True
                else:
                    _release_delivery_channel(handler, alert_id, key, "email")
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
        alert_id, key = row.get("alert_id"), row.get("url_hash")
        chat_id, message = row.get("chat_id"), row.get("message")
        new_fields = (
            "email", "email_subject", "email_body", "telegram_sent", "email_sent"
        )
        legacy_telegram = not any(field in row for field in new_fields)
        if legacy_telegram:
            if not chat_id:
                logger.error(
                    f"❌ legacy alert delivery {alert_id}/{key} has no chat_id; "
                    "leaving pending"
                )
                continue
            if not message:
                logger.error(
                    f"❌ legacy alert delivery {alert_id}/{key} has no message; "
                    "leaving pending"
                )
                continue
            if not token or not _claim_pending_delivery_channel(
                handler, alert_id, key, "telegram"
            ):
                continue
            sender = send_telegram or _default_telegram(token)
            try:
                sent = bool(sender(chat_id, message))
            except Exception as e:
                _release_delivery_channel(handler, alert_id, key, "telegram")
                logger.error(f"❌ retry failed for {chat_id}: {e}")
                continue
            if not sent:
                _release_delivery_channel(handler, alert_id, key, "telegram")
                continue
            if _mark_delivery_channel_sent(
                handler, alert_id, key, "telegram", legacy_telegram=True
            ):
                resent += 1
            else:
                _release_delivery_channel(handler, alert_id, key, "telegram")
            continue

        if not all(field in row for field in new_fields):
            logger.error(
                f"❌ incomplete alert delivery {alert_id}/{key}; leaving pending"
            )
            continue

        telegram_sent = bool(row["telegram_sent"])
        email = row["email"]
        email_subject = row["email_subject"]
        email_body = row["email_body"]
        email_sent = bool(row["email_sent"])
        row_delivered = False

        if chat_id and not telegram_sent:
            if not message:
                logger.error(f"❌ alert delivery {alert_id}/{key} has no Telegram message")
            elif token and _claim_pending_delivery_channel(
                handler, alert_id, key, "telegram"
            ):
                sender = send_telegram or _default_telegram(token)
                try:
                    sent = bool(sender(chat_id, message))
                except Exception as e:
                    _release_delivery_channel(handler, alert_id, key, "telegram")
                    logger.error(f"❌ retry failed for {chat_id}: {e}")
                else:
                    if not sent:
                        _release_delivery_channel(handler, alert_id, key, "telegram")
                    elif _mark_delivery_channel_sent(
                        handler, alert_id, key, "telegram"
                    ):
                        row_delivered = True
                    else:
                        _release_delivery_channel(handler, alert_id, key, "telegram")

        if email and not email_sent:
            if email_subject is None or email_body is None:
                logger.error(
                    f"❌ alert delivery {alert_id}/{key} has incomplete email payload"
                )
            elif _claim_pending_delivery_channel(handler, alert_id, key, "email"):
                sender = send_email or _default_email_content()
                try:
                    sent = bool(sender(email, email_subject, email_body))
                except Exception as e:
                    _release_delivery_channel(handler, alert_id, key, "email")
                    logger.error(f"❌ retry failed for {email}: {e}")
                else:
                    if not sent:
                        _release_delivery_channel(handler, alert_id, key, "email")
                    elif _mark_delivery_channel_sent(handler, alert_id, key, "email"):
                        row_delivered = True
                    else:
                        _release_delivery_channel(handler, alert_id, key, "email")
        if not chat_id and not email:
            logger.error(f"❌ alert delivery {alert_id}/{key} has no configured channel")
        if row_delivered:
            resent += 1
    return resent
