"""Genossenschaft (co-op) Bauträger scrapers — v1 pilot: ÖVW, Familienwohnbau, BWSG.
Concrete parsers (no shared engine yet). Each parse_<x>(html) -> List[Listing].
Post-pilot: review HTML variance to decide whether to extract a shared engine."""
import logging
import requests
from typing import List
from bs4 import BeautifulSoup
from Domain.listing import Listing
from Domain.sources import Source

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter/1.0)"}

# Filled in per adapter task from live inspection.
SOURCES = {
    "ÖVW":             {"url": "TBD_FROM_STEP1", "parser": "parse_oevw"},
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


def scrape_all() -> List[Listing]:
    out: List[Listing] = []
    for name, cfg in SOURCES.items():
        try:
            html = fetch(cfg["url"])
            out.extend(globals()[cfg["parser"]](html))
        except Exception as e:  # one bad adapter must not kill the rest
            logger.error(f"co-op adapter {name} failed: {e}")
    return out
