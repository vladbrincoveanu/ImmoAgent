"""
Extract boolean property features from listing full-page text.
Two-pass approach: check negative patterns first, then positive.
Input: soup.get_text().lower() — full page text, pre-lowercased.
"""
import re
from typing import Dict, Optional
from bs4 import BeautifulSoup


def _any_match(text: str, patterns: list) -> bool:
    return any(re.search(p, text) for p in patterns)


def extract_lift_present(text: str) -> Optional[bool]:
    """True if lift mentioned, False if explicitly absent, None if not mentioned."""
    negative = [r'(kein|keine|keinen|ohne)\s+\w*\s*(aufzug|lift)']
    positive = [r'aufzug|fahrstuhl|lift\s+im\s+haus|aufzug\s+vorhanden']
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_facade_renovated(text: str) -> Optional[bool]:
    """True if facade renovation mentioned, False if explicitly negated, None if absent."""
    negative = [r'(keine|nicht)\s+\w*\s*fassaden?(sanierung|renovierung|dämmung)']
    positive = [
        r'fassaden?(sanierung|renovierung|dämmung)',
        r'sanierte\s+fassade',
        r'fassade\s+(saniert|renoviert|gedämmt)',
        r'wärmedämmfassade',
        r'neue\s+fassade',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_parifizierung_complete(text: str) -> Optional[bool]:
    """True if parifizierung complete, False if pending/incomplete, None if not mentioned."""
    negative = [
        r'parifizierung\s+(ausstehend|noch\s+nicht|nicht\s+abgeschlossen)',
        r'nicht\s+parifiziert',
    ]
    positive = [
        r'parifizierung\s+abgeschlossen',
        r'bereits\s+parifiziert',
        r'parifiziert',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_roof_renovated(text: str) -> Optional[bool]:
    """True if roof renovation mentioned, False if explicitly negated, None if absent."""
    negative = [r'(keine|nicht)\s+\w*\s*dach(sanierung|renovierung)']
    positive = [
        r'dach(sanierung|renovierung)',
        r'saniertes?\s+dach',
        r'dach\s+(saniert|renoviert)',
        r'neues?\s+dach',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_kitchen_included(text: str) -> Optional[bool]:
    """True if furnished kitchen mentioned, False if explicitly absent, None if not mentioned."""
    negative = [r'(ohne|keine)\s+küche']
    positive = [
        r'einbauküche',
        r'küche\s+(inkl|vorhanden|inklusive)',
        r'küche\s+mit\s+geräten',
        r'möblierte\s+küche',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_window_type(text: str) -> Optional[str]:
    """Returns window type: 'kastenfenster'|'kunststoff'|'holz-alu'|'isolierverglasung'|None."""
    checks = [
        ('kastenfenster', [r'kastenfenster']),
        ('kunststoff', [r'kunststofffenster', r'kunststoff.{0,10}fenster']),
        ('holz-alu', [r'holz-?alu.{0,10}fenster', r'fenster.{0,20}holz-?alu']),
        ('isolierverglasung', [r'isolierverglasung', r'3-scheiben', r'dreifach.{0,10}verglas']),
    ]
    for label, patterns in checks:
        if _any_match(text, patterns):
            return label
    return None


def extract_ruecklage_eur_month(text: str) -> Optional[float]:
    """Extract monthly Reparaturrücklage in EUR. Handles German thousands separators."""
    m = re.search(
        r'reparaturrücklage[^:]*:\s*([\d]{1,3}(?:[.,]\d{3})*[,.]\d{2}|\d+[,.]\d{1,2})',
        text
    )
    if not m:
        return None
    raw = m.group(1)
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    return float(raw)


def extract_maklerprovision_pct(text: str) -> Optional[float]:
    """Extract broker commission percentage. Returns float e.g. 3.0 for '3% Kundenprovision'."""
    # "3% kundenprovision" — number before keyword
    m = re.search(
        r'(\d+(?:[,.]\d+)?)\s*%\s*(kundenprovision|maklerprovision|provision|käuferprovision)',
        text
    )
    if m:
        return float(m.group(1).replace(',', '.'))
    # "käuferprovision: 2%" — keyword before number
    m = re.search(
        r'(kundenprovision|maklerprovision|provision|käuferprovision)[^%\d]{0,20}(\d+(?:[,.]\d+)?)\s*%',
        text
    )
    if m:
        return float(m.group(2).replace(',', '.'))
    return None


def extract_sonderumlage_risk(text: str) -> Optional[bool]:
    """True if Sonderumlage mentioned, False if explicitly absent, None if not mentioned."""
    negative = [r'(keine|kein)\s+sonderumlage']
    positive = [r'sonderumlage']
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_doppelmakler(text: str) -> Optional[bool]:
    """True if Doppelmakler disclosed, None otherwise."""
    if re.search(r'doppelmakler', text):
        return True
    return None


def extract_document_urls(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract PDF document links from listing page documents box.
    Returns dict with keys: expose|preisliste|planmappe|lagereport."""
    label_map = {
        'exposé': 'expose',
        'expose': 'expose',
        'preisliste': 'preisliste',
        'planmappe': 'planmappe',
        'lagereport': 'lagereport',
    }
    result = {}
    for anchor in soup.select('a[data-testid^="documents-item-anchor"]'):
        text = anchor.get_text(strip=True).lower()
        href = anchor.get('href', '')
        if text in label_map and href:
            result[label_map[text]] = href
    return result