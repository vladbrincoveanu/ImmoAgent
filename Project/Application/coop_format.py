"""Formatting for co-op (Genossenschaft) Telegram alerts. Kept separate from
Application.main so lightweight runners (run_coop.py) don't import the heavy
scrape orchestration just to format a message."""
import html
from Domain.listing import Listing


def format_coop_message(l: Listing) -> str:
    """Format a co-op (Genossenschaft) listing as an HTML Telegram message.

    parse_mode defaults to "HTML" in TelegramBot.send_message, so tags are
    <b>...</b> here (not Markdown *...*) to actually render as intended.
    Scraped free-text fields (bautraeger, bezirk) are HTML-escaped since
    Telegram's HTML parser rejects unescaped &/</> in the message body."""
    bautraeger = html.escape(l.bautraeger) if l.bautraeger else None
    bezirk = html.escape(l.bezirk) if l.bezirk else None
    link = l.builder_url or l.url  # prefer the builder's own reservation page
    url = html.escape(link, quote=False) if link else ''
    ppm2 = f"{l.price_total / l.area_m2:.1f}€/m²" if (l.price_total and l.area_m2) else "–"
    tags = " ".join(t for t in [f"#{bezirk}" if bezirk else None,
                                f"#{bautraeger}" if bautraeger else None] if t)
    return (f"🏢 <b>{bautraeger or 'Genossenschaft'}</b> — {bezirk or ''}\n"
            f"{l.rooms or '?'} Zi · {l.area_m2 or '?'} m² · {ppm2}\n"
            f"Vergabe: {l.allocation_model or 'first_come'}\n"
            f"{url}\n{tags}")
