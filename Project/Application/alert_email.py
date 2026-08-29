"""Plain-text email delivery for user-created co-op alerts.

Deliberately NOT reusing outreach/email_sender.EmailSender: that class is built
for cold outreach to landlords — German sales templates, unsubscribe tokens, rate
limiting, campaign bookkeeping. An alert is a two-line notification to someone who
asked for it, and inheriting that machinery would mean inheriting its footguns.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
ALERT_EMAIL_SUBJECT = "Neue passende Wohnungsanzeige"


def _format_number(value, label: str):
    if value is None:
        return None
    try:
        return f"{round(float(value))} {label}"
    except (TypeError, ValueError, OverflowError):
        return None


def _body(listing, unverified: bool = False) -> str:
    bits = []
    title = getattr(listing, "title", None) or getattr(listing, "address", None)
    if title:
        bits.append(str(title))
    rent = _format_number(getattr(listing, "price_total", None), "Miete")
    spec = " · ".join(s for s in [
        _format_number(getattr(listing, "rooms", None), "Zimmer"),
        _format_number(getattr(listing, "area_m2", None), "m²"),
        f"€{rent}" if rent else None,
    ] if s)
    if spec:
        bits.append(spec)
    bits.append(str(getattr(listing, "url", "") or ""))
    bits.append("")
    bits.append("Passende Wohnungsanzeige — Angaben bitte vor Ort prüfen.")
    if unverified:
        bits.append("⚠️ Größe/Zimmer/Preis unbekannt — vor Ort prüfen")
    return "\n".join(bits)


def build_alert_email(listing, unverified: bool = False) -> tuple[str, str]:
    return ALERT_EMAIL_SUBJECT, _body(listing, unverified)


def send_alert_email_content(to_addr: str, subject: str, body: str) -> bool:
    """Send prepared alert content, returning False on configuration or SMTP errors.

    The poll must survive a broken mail server: the scrape and the upserts that
    feed the website are more important than any single notification."""
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not user or not password:
        # Loud, because a silently unsent alert is indistinguishable from no match.
        logger.error("SMTP_USER/SMTP_PASSWORD unset — alert email NOT sent to "
                     f"{to_addr}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"alert email to {to_addr} failed: {e}")
        return False


def send_alert_email(to_addr: str, listing, unverified: bool = False) -> bool:
    """Build and send one alert using the shared SMTP implementation."""
    subject, body = build_alert_email(listing, unverified)
    return send_alert_email_content(to_addr, subject, body)
