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
    if _any_match(text, [r'doppelmakler']):
        return True
    return None


_TRANSFER_MARKERS = [
    r'ablöse', r'abloese',
    r'weitergabe', r'weiterzugeben', r'weiter\s?zu\s?geben',
    r'nachmieter(?:in)?',
    r'abzugeben',
    r'wohnungstausch',
    r'übergabe\s+der\s+genossenschaftswohnung',
]

# "Ablöse" on its own is the dominant false positive: ordinary free-financed
# rentals routinely ask one for a fitted kitchen or furniture. A co-op marker has
# to be present too, or the feed fills with kitchen buyouts. Reuses the same
# vocabulary as extract_is_genossenschaft so the two agree on what "co-op" means.
_COOP_CONTEXT_MARKERS = [
    r'genossenschaft', r'gemeinnützig', r'gemeinnutzig',
    r'gefördert', r'geforderte?r?', r'\bwgg\b',
    r'finanzierungsbeitrag', r'eigenmittelanteil', r'wohnbauförderung',
    r'baurechtszins', r'mietkauf',
]


def extract_is_private_coop_transfer(text: str) -> Optional[bool]:
    """True when an ad is a private tenant passing on a co-op flat.

    These are the first-come-first-served ones: no waiting list, no Bauträger
    allocation, whoever reaches the current tenant first gets it. That is a
    different thing from a builder listing a co-op unit, which is what
    `extract_is_genossenschaft` catches, so both markers are required.

    False when the ad is explicitly free-financed — a `freifinanziert` flat with an
    Ablöse is a kitchen buyout, not a co-op transfer. None when there is no signal.
    Input is pre-lowercased full page text (title + description + body)."""
    if _any_match(text, [r'freifinanziert', r'frei\s+finanziert']):
        return False
    if _any_match(text, _TRANSFER_MARKERS) and _any_match(text, _COOP_CONTEXT_MARKERS):
        return True
    return None


def extract_is_genossenschaft(text: str) -> Optional[bool]:
    """True if co-op/subsidized markers present, False if explicitly free-financed,
    None if no signal. Input is pre-lowercased full page text."""
    negative = [r'freifinanziert', r'frei\s+finanziert']
    positive = [
        r'genossenschaft', r'gemeinnützig', r'gemeinnutzig',
        r'gefördert', r'geforderte?r?', r'\bwgg\b',
        r'mietkauf', r'baurechtszins', r'finanzierungsbeitrag',
        r'eigenmittelanteil', r'wohnbauförderung',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


_KNOWN_BAUTRAEGER = [
    # Must match the bautraeger names genossenschaft_scraper.py's direct-scrape
    # adapters use, so the same unit collapses across sources by name.
    (r'\bövw\b|\boevw\b', 'ÖVW'),
    (r'familienwohnbau', 'Familienwohnbau'),
    (r'\bbwsg\b', 'BWSG'),
]


def extract_bautraeger(text: str) -> Optional[str]:
    """Name of the co-op Bauträger if one of the known pilot builders is
    mentioned, else None. Input is pre-lowercased full page text."""
    for pattern, name in _KNOWN_BAUTRAEGER:
        if re.search(pattern, text):
            return name
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