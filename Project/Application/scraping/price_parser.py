import re
from typing import Optional


def parse_price_text(price_text: str) -> Optional[float]:
    """Parse common Austrian and English real-estate price formats."""
    if not price_text or not isinstance(price_text, str):
        return None

    if 'anfrage' in price_text.lower():
        return None

    match = re.search(r'(?<!\d)(\d[\d.,]*)(?:\s*([kKmM]))?', price_text)
    if not match:
        return None

    raw = match.group(1)
    suffix = (match.group(2) or '').lower()

    if ',' in raw and '.' in raw:
        if raw.rfind(',') > raw.rfind('.') and len(raw.rsplit(',', 1)[1]) <= 2:
            normalized = raw.replace('.', '').replace(',', '.')
        elif raw.rfind('.') > raw.rfind(',') and len(raw.rsplit('.', 1)[1]) <= 2:
            normalized = raw.replace(',', '')
        else:
            normalized = raw.replace('.', '').replace(',', '')
    elif ',' in raw:
        normalized = raw.replace(',', '') if len(raw.rsplit(',', 1)[1]) == 3 else raw.replace(',', '.')
    elif '.' in raw:
        normalized = raw.replace('.', '') if len(raw.rsplit('.', 1)[1]) == 3 else raw
    else:
        normalized = raw

    try:
        value = float(normalized)
    except ValueError:
        return None

    if suffix == 'k':
        value *= 1000
    elif suffix == 'm':
        value *= 1_000_000

    return value
