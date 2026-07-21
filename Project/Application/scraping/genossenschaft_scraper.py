"""Genossenschaft (co-op) Bauträger scrapers — v1 pilot: ÖVW, Familienwohnbau, BWSG.
Concrete parsers (no shared engine yet). Each parse_<x>(html) -> List[Listing].
Post-pilot: review HTML variance to decide whether to extract a shared engine."""
import logging
import os
import re
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
from Domain.listing import Listing
from Domain.sources import Source

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter/1.0)"}

# mygewo.at is itself the aggregator of ~30 Vienna Bauträger — one server-rendered
# search page carries every developer's units already filtered server-side, so a
# single adapter gives full parity (and stays in sync) instead of N brittle scrapers.
# The filter URL is provided by the operator (the GitHub Action) via MYGEWO_SEARCH_URL;
# the default below matches: ≥3 rooms · ≥51 m² · rent <€1000 · Wien.
MYGEWO_DEFAULT_URL = (
    "https://mygewo.at/genossenschaftswohnungen/suche"
    "?rooms=3_4&area=2_3_4&rent=1_2_3&states=28_"
)

# Filled in per adapter task from live inspection.
SOURCES = {
    "MYGEWO":          {"url": os.environ.get("MYGEWO_SEARCH_URL") or MYGEWO_DEFAULT_URL, "parser": "parse_mygewo"},
    "ÖVW":             {"url": "https://www.oevw.at/suche/wohnen", "parser": "parse_oevw"},
    "Familienwohnbau": {"url": "https://www.familienwohnbau.at/de/immobilien", "parser": "parse_familienwohnbau"},
    "BWSG":            {"url": "https://www.bwsg.at/immobilien/immobilie-suchen/", "parser": "parse_bwsg"},
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _new_coop_listing(url: str, bautraeger: str) -> Listing:
    return Listing(
        url=url, source=Source.GENOSSENSCHAFT,
        is_genossenschaft=True, bautraeger=bautraeger,
        coop_source="bautraeger_direct", allocation_model="first_come",
    )


def _text(block, sel: str) -> Optional[str]:
    el = block.select_one(sel)
    return el.get_text(" ", strip=True) if el else None


def _parse_number(text: str) -> Optional[float]:
    m = re.search(r"\d+(?:[.,]\d+)*", text)
    if not m:
        return None
    raw = m.group()
    if "," in raw:  # European format, e.g. "1.432,73" -> 1432.73
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:  # "1.234.567" -> 1234567 (multiple dot-groups are always thousands seps)
        raw = raw.replace(".", "")
    elif "." in raw:
        int_part, frac_part = raw.split(".")
        if len(frac_part) == 3:  # "350.000" -> 350000 (dot-thousands, no decimal comma)
            raw = int_part + frac_part
        # else a 1-2 digit tail is a real decimal point, e.g. "77.5" -> 77.5
    return float(raw)


def _num(block, sel: str) -> Optional[float]:
    el = block.select_one(sel)
    return _parse_number(el.get_text(" ")) if el else None


def _num_by_keyword(block, sel: str, keyword: str) -> Optional[float]:
    for el in block.select(sel):
        text = el.get_text(" ")
        if keyword in text:
            return _parse_number(text)
    return None


def _num_before_keyword(text: str, keyword: str) -> Optional[float]:
    """Number immediately preceding keyword, e.g. "3" from "3 Zimmer" inside
    "77,29 m² | 3 Zimmer" — anchoring to the keyword (not just "first number
    in the string") avoids picking up an unrelated figure from elsewhere in
    the same text when multiple keyword/number pairs share one text node."""
    m = re.search(r"([\d.,]+)\s*" + re.escape(keyword), text)
    return _parse_number(m.group(1)) if m else None


def _bezirk_from(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(\d{4})\s+Wien", text)  # same convention as willhaben_scraper.extract_bezirk
    return m.group(1) if m else None


def parse_oevw(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select(".thumb--unit"):
        a = block.select_one(".thumb__link a[href]")
        if not a:
            continue
        href = a.get("href", "")
        url = href if href.startswith("http") else "https://www.oevw.at" + href
        listing = _new_coop_listing(url, "ÖVW")
        street = _text(block, ".thumb__heading")
        info = _text(block, ".thumb__info")  # e.g. "Wohnung – Miete – 1100 Wien"
        listing.address = f"{street}, {info}" if street and info else (street or info)
        listing.bezirk = _bezirk_from(info)
        listing.area_m2 = _num(block, ".thumb__subheading__list li:nth-of-type(1)")
        listing.price_total = _num(block, ".thumb__subheading__list li:nth-of-type(2)")
        listing.rooms = _num(block, ".thumb__text__list li:nth-of-type(1)")
        out.append(listing)
    return out


def parse_familienwohnbau(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select('a[href^="/de/objekt/"]'):
        href = block.get("href", "")
        if not href:
            continue
        title = _text(block, "p.uppercase")
        if title and "garage" in title.lower():  # parking spots, not housing units
            continue
        rooms = _num_by_keyword(block, "div.flex-1 p", "Zimmer")
        area = _num_by_keyword(block, "div.flex-1 p", "m²")
        if rooms is None and area is None:  # multi-unit project overview, no single-unit data
            continue
        url = href if href.startswith("http") else "https://www.familienwohnbau.at" + href
        listing = _new_coop_listing(url, "Familienwohnbau")
        listing.address = _text(block, "p.text-gray-700.pt-1") or title
        listing.bezirk = _bezirk_from(listing.address)
        listing.area_m2 = area
        listing.rooms = rooms
        listing.price_total = _num(block, "p.text-primary")
        out.append(listing)
    return out


def parse_bwsg(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select(".res_immobiliensuche__immobilien__item"):
        href = block.get("href", "")
        if not href:
            continue
        row1 = _text(block, ".res_immobiliensuche__immobilien__item__content__meta__row_1") or ""
        rooms = _num_before_keyword(row1, "Zimmer")
        area = _num_before_keyword(row1, "m²")
        if rooms is None and area is None:  # project overview card, no single-unit data
            continue
        url = href if href.startswith("http") else "https://www.bwsg.at" + href
        listing = _new_coop_listing(url, "BWSG")
        title = _text(block, ".res_immobiliensuche__immobilien__item__content__title")
        listing.address = _text(block, ".res_immobiliensuche__immobilien__item__content__meta__location") or title
        listing.bezirk = _bezirk_from(listing.address)
        listing.area_m2 = area
        listing.rooms = rooms
        listing.price_total = _num(block, ".res_immobiliensuche__immobilien__item__content__meta__preis")
        out.append(listing)
    return out


_MYGEWO_BASE = "https://mygewo.at"


def _mygewo_bautraeger(card_text: str, href: str) -> Optional[str]:
    """Developer name. mygewo prints "gefunden auf <domain>.at"; fall back to the
    trailing "<name>-<uuid>" token in the offer slug (e.g. ...-oesw-<uuid>)."""
    m = re.search(r"gefunden auf\s+([\w.\-]+\.at)", card_text, re.I)
    if m:
        return m.group(1).replace(".at", "").upper()
    m = re.search(r"-([a-z]{2,10})-[0-9a-f]{8}-", href)
    return m.group(1).upper() if m else None


def parse_mygewo(html: str) -> List[Listing]:
    """Parse the mygewo.at aggregated co-op search results.

    Each result is an <a href="/genossenschaftswohnungen/angebot/…-<uuid>"> card
    whose text reads like: "gefunden auf oesw.at · vor 13 Tagen · Miete: €945 ·
    70,09 m² · 3 Zimmer · Kapital: €2.922 · Erzherzog-Karl-Straße 140 1220 Wien".
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    seen: set = set()
    for a in soup.select('a[href^="/genossenschaftswohnungen/angebot/"]'):
        href = a.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)
        text = a.get_text(" ", strip=True)

        area = _num_before_keyword(text, "m²")
        rooms = _num_before_keyword(text, "Zimmer")
        rent = None
        m = re.search(r"Miete:\s*€?\s*([\d.,]+)", text)
        if m:
            rent = _parse_number(m.group(1))
        if rooms is None and area is None and rent is None:
            continue  # not a real unit card

        url = href if href.startswith("http") else _MYGEWO_BASE + href
        bautraeger = _mygewo_bautraeger(text, href)
        listing = _new_coop_listing(url, bautraeger)
        listing.area_m2 = area
        listing.rooms = rooms
        listing.price_total = rent

        m = re.search(r"Kapital:\s*€?\s*([\d.,]+)", text)
        if m:
            listing.own_funds = _parse_number(m.group(1))

        # Address: mygewo splits it across two <p>s — the street sits in the
        # <p> immediately preceding the "<PLZ> Wien , Wien" line.
        ps = a.find_all("p")
        for i, p in enumerate(ps):
            ptext = p.get_text(" ", strip=True)
            plz_m = re.search(r"(\d{4})\s+Wien", ptext)
            if not plz_m:
                continue
            listing.bezirk = plz_m.group(1)
            city = f"{plz_m.group(1)} Wien"
            street = ps[i - 1].get_text(" ", strip=True) if i > 0 else None
            # guard: preceding <p> must look like a street, not a meta/price line
            if street and not re.search(r"€|m²|Miete|Kapital|Zimmer|gefunden", street):
                listing.address = f"{street}, {city}"
            else:
                listing.address = city
            break

        if re.search(r"Kaufoption|Kaufopt|Kaufmöglichkeit|kaufoption", text, re.I) \
                or re.search(r"kauf", href, re.I):
            listing.special_features = ["Kaufoption"]

        parts = [f"{int(rooms)} Zimmer" if rooms else None,
                 f"{area:.0f} m²" if area else None,
                 bautraeger]
        summary = " · ".join(p for p in parts if p)
        listing.title = (listing.address + (f" – {summary}" if summary else "")) \
            if listing.address else (summary or "Genossenschaftswohnung")
        out.append(listing)
    logger.info(f"🔍 mygewo: {len(out)} listing(s) parsed")
    return out


def resolve_builder_url(offer_url: str) -> Optional[str]:
    """Resolve a mygewo /angebot/ URL to the builder's own reservation page.

    mygewo detail pages (TanStack SSR) carry an "Original-Anzeige" anchor linking
    straight to the Bauträger's listing (wohnen.at, arwag.at, …) — that's where a
    unit is actually reserved. bs4's find(string=…) misses it (the anchor wraps
    nested markup), so scan anchors by visible text. Fall back to the builder's
    homepage ("gefunden auf <domain>.at") when the deep link is absent, else None."""
    try:
        html = fetch(offer_url)
    except Exception as e:
        logger.warning(f"builder-url fetch failed for {offer_url}: {e}")
        return None
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "Original-Anzeige" in a.get_text():
            href = a["href"]
            if href.startswith("http") and "mygewo.at" not in href:
                return href
    m = re.search(r"gefunden auf\s+([\w.\-]+\.at)", html, re.I)
    if m:
        domain = m.group(1)
        domain = domain[4:] if domain.startswith("www.") else domain
        return "https://www." + domain
    return None


def scrape_all() -> List[Listing]:
    out: List[Listing] = []
    for name, cfg in SOURCES.items():
        try:
            html = fetch(cfg["url"])
            out.extend(globals()[cfg["parser"]](html))
        except Exception as e:  # one bad adapter must not kill the rest
            logger.error(f"co-op adapter {name} failed: {e}")
    return out
