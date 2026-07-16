"""Genossenschaft (co-op) Bauträger scrapers — v1 pilot: ÖVW, Familienwohnbau, BWSG.
Concrete parsers (no shared engine yet). Each parse_<x>(html) -> List[Listing].
Post-pilot: review HTML variance to decide whether to extract a shared engine."""
import logging
import re
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
from Domain.listing import Listing
from Domain.sources import Source

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter/1.0)"}

# Filled in per adapter task from live inspection.
SOURCES = {
    "ÖVW":             {"url": "https://www.oevw.at/suche/wohnen", "parser": "parse_oevw"},
    "Familienwohnbau": {"url": "TBD_FROM_STEP1", "parser": "parse_familienwohnbau"},
    "BWSG":            {"url": "TBD_FROM_STEP1", "parser": "parse_bwsg"},
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
    return el.get_text(strip=True) if el else None


def _num(block, sel: str) -> Optional[float]:
    el = block.select_one(sel)
    if not el:
        return None
    m = re.search(r"\d+(?:[.,]\d+)*", el.get_text())
    if not m:
        return None
    raw = m.group()
    if "," in raw:  # European format, e.g. "1.432,73" -> 1432.73
        raw = raw.replace(".", "").replace(",", ".")
    return float(raw)


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


def scrape_all() -> List[Listing]:
    out: List[Listing] = []
    for name, cfg in SOURCES.items():
        try:
            html = fetch(cfg["url"])
            out.extend(globals()[cfg["parser"]](html))
        except Exception as e:  # one bad adapter must not kill the rest
            logger.error(f"co-op adapter {name} failed: {e}")
    return out
