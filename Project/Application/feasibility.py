"""
Financial feasibility gates and math for the bank_loan_ready buyer profile.

Hard gates reject listings before scoring based on: HWB > 80, bad energy class,
rental status, rental horizon, and price ceiling.

Financial math validates Austrian first-time-buyer constraints: €100k cash reserves
and €2,000/month max outflow using a 3.2% / 35yr annuity.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

DEFAULT_CONFIG = {
    'cash_reserves': 100_000,
    'max_monthly': 2_000,
    'rate_annual': 0.032,
    'term_months': 420,
    'down_pct': 0.10,
    'default_bk': 250,
    'max_rental_end_date': '2027-12',
    'standard_price_ceiling': 500_000,
    'provisionsfrei_price_ceiling': 610_000,
}

BAD_ENERGY_CLASSES = {'D', 'E', 'F', 'G'}


def derive_profile_fields(listing: dict) -> dict:
    """
    Compute is_provisionsfrei and bezirk_score from existing listing fields
    if not already set. Mutates and returns the listing dict.
    """
    if listing.get('is_provisionsfrei') is None:
        prov_pct = listing.get('maklerprovision_pct')
        if prov_pct is not None:
            listing['is_provisionsfrei'] = prov_pct == 0
        else:
            listing['is_provisionsfrei'] = False
    if listing.get('bezirk_score') is None:
        bezirk = listing.get('bezirk')
        if bezirk is not None:
            try:
                district_num = int(str(bezirk).strip().split()[0])
                if 1 <= district_num <= 23:
                    listing['bezirk_score'] = max(0.0, 1.0 - abs(district_num - 1) / 22.0)
                else:
                    listing['bezirk_score'] = 0.0
            except (ValueError, IndexError):
                listing['bezirk_score'] = 0.0
        else:
            listing['bezirk_score'] = 0.0
    return listing


def is_provisionsfrei(listing: dict) -> bool:
    """True iff listing is commission-free. Handles bool, int 0/1, and missing."""
    val = listing.get('is_provisionsfrei')
    if val is None:
        prov_pct = listing.get('maklerprovision_pct')
        if prov_pct is None:
            return False
        return prov_pct == 0
    if isinstance(val, bool):
        return val
    return val == 1

MONTH_MAP = {
    'jan': '01', 'jän': '01', 'jänner': '01', 'januar': '01',
    'feb': '02', 'februar': '02',
    'mär': '03', 'mar': '03', 'märz': '03',
    'apr': '04', 'april': '04',
    'mai': '05',
    'jun': '06', 'juni': '06',
    'jul': '07', 'juli': '07',
    'aug': '08', 'august': '08',
    'sep': '09', 'sept': '09', 'september': '09',
    'okt': '10', 'oktober': '10',
    'nov': '11', 'november': '11',
    'dez': '12', 'dezember': '12',
}

VACANT_PATTERNS = [
    r'ab\s+sofort', r'bestandsfrei', r'belagsfertig',
    r'schlüsselfertig', r'leerstehend', r'sofort\s+bezugsfertig',
]
RENTED_BEFRISTET_PATTERNS = [
    r'befristet\s+vermiet\w*\s+bis\s+(\w+\s+\d{4}|\d{1,2}[./]\d{4})',
    r'bis\s+(\w+\s+\d{4}|\d{1,2}[./]\d{4})\s+befristet\s+vermiet\w*',
]
RENTED_UNBEFRISTET_PATTERN = r'unbefristet\s+vermiet\w*'
CONSTRUCTION_PATTERNS = [r'in\s+bau', r'bauprojekt', r'fertigstellung\s+\d{4}']
HARD_DISCARD_PATTERNS = [r'leibrente', r'wohnrecht']


@dataclass
class FeasibilityResult:
    feasibility_passed: Optional[bool]   # None = unknown (price missing)
    cash_needed: Optional[float]
    monthly_outflow: Optional[float]
    loan_principal: Optional[float]
    failure_reason: Optional[str]


def calculate_monthly_payment(loan_amount: float, annual_rate: float, term_months: int) -> float:
    """
    Calculate monthly mortgage payment (annuity) using standard amortization formula.
    Supports rates as percentages (e.g. 3.2) or fractions (e.g. 0.032).
    """
    if loan_amount <= 0 or term_months <= 0:
        return 0.0
    
    rate = float(annual_rate)
    if rate > 1.0:
        rate = rate / 100.0
        
    mr = rate / 12.0
    if mr == 0:
        return round(loan_amount / term_months, 2)
        
    payment = loan_amount * (mr * (1 + mr) ** term_months) / ((1 + mr) ** term_months - 1)
    return round(payment, 2)


def normalize_hwb_value(hwb_val: Any) -> Optional[float]:
    """
    Normalize HWB value to float.
    Convert MJ/m²a to kWh/m²a if specified (divide by 3.6).
    """
    if hwb_val is None:
        return None
    if isinstance(hwb_val, (int, float)):
        return float(hwb_val)
    
    s = str(hwb_val).strip().lower()
    m = re.search(r'([\d.,]+)', s)
    if not m:
        return None
    
    val_str = m.group(1).replace('.', '').replace(',', '.')
    try:
        val = float(val_str)
    except ValueError:
        return None
    
    # Convert MJ/m²a to kWh/m²a
    if 'mj' in s:
        val = val / 3.6
        
    return round(val, 2)


def _parse_rental_date(date_str: str) -> Optional[str]:
    """Convert German date string ('November 2027' or '11/2027') to 'YYYY-MM'."""
    s = date_str.strip().lower()
    m = re.match(r'(\d{1,2})[./](\d{4})', s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.match(r'(\w+)\s+(\d{4})', s)
    if m:
        word = m.group(1)
        year = m.group(2)
        for prefix, num in MONTH_MAP.items():
            if word.startswith(prefix):
                return f"{year}-{num}"
    return None


def extract_availability_status(text: str) -> Tuple[str, Optional[str]]:
    """
    Parse occupancy status from listing description text.

    Returns (availability_status, rental_end_date):
      availability_status: 'vacant' | 'rented_befristet' | 'rented_unbefristet'
                           | 'construction' | 'unknown'
      rental_end_date: 'YYYY-MM' or None
    """
    t = text or ''

    for pat in HARD_DISCARD_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return 'rented_unbefristet', None

    for pat in CONSTRUCTION_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return 'construction', None

    if re.search(RENTED_UNBEFRISTET_PATTERN, t, re.IGNORECASE):
        return 'rented_unbefristet', None

    for pat in RENTED_BEFRISTET_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return 'rented_befristet', _parse_rental_date(m.group(1))

    for pat in VACANT_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return 'vacant', None

    return 'unknown', None


def passes_hard_gates(listing: dict, cfg: Optional[dict] = None) -> bool:
    """
    Return False if any hard exclusion gate fires.
    Gates for fields that are None are skipped (unknowns are not excluded).
    """
    c = {**DEFAULT_CONFIG, **(cfg or {})}

    hwb = normalize_hwb_value(listing.get('hwb_value'))
    if hwb is not None and hwb > 80:
        return False

    ec = listing.get('energy_class')
    if ec is not None and str(ec).upper() in BAD_ENERGY_CLASSES:
        return False

    avail = listing.get('availability_status')
    if avail in ('rented_unbefristet', 'construction'):
        return False

    rental_end = listing.get('rental_end_date')
    if rental_end is not None and rental_end > c['max_rental_end_date']:
        return False

    price = listing.get('price_total')
    if price is not None:
        is_prov = is_provisionsfrei(listing)
        ceiling = c['provisionsfrei_price_ceiling'] if is_prov else c['standard_price_ceiling']
        if price > ceiling:
            return False

    return True


def compute_feasibility(listing: dict, cfg: Optional[dict] = None) -> FeasibilityResult:
    """
    Run hard gates then Austrian financial math.

    Side costs (Austrian law, 2026):
      Grunderwerbsteuer 3.5% + escrow 1.8% + bank/notary 1.1% + broker (0% if prov, 3.6% otherwise)
    GGG §26a: ownership+mortgage registration = 0% up to €500k; 2.3% on excess.
    Annuity: 3.2% fixed / 35yr / 10% down.
    """
    c = {**DEFAULT_CONFIG, **(cfg or {})}

    if not passes_hard_gates(listing, c):
        hwb = normalize_hwb_value(listing.get('hwb_value'))
        ec = listing.get('energy_class')
        avail = listing.get('availability_status')
        rental_end = listing.get('rental_end_date')
        price = listing.get('price_total')
        is_prov = is_provisionsfrei(listing)
        ceiling = c['provisionsfrei_price_ceiling'] if is_prov else c['standard_price_ceiling']

        if hwb is not None and hwb > 80:
            reason = f"HWB {hwb} > 80"
        elif ec is not None and str(ec).upper() in BAD_ENERGY_CLASSES:
            reason = f"energy_class {ec}"
        elif avail in ('rented_unbefristet', 'construction'):
            reason = f"availability_status {avail}"
        elif rental_end is not None and rental_end > c['max_rental_end_date']:
            reason = f"rental_end_date {rental_end} > {c['max_rental_end_date']}"
        else:
            reason = f"price {price:,.0f} > ceiling {ceiling:,.0f}"
        return FeasibilityResult(False, None, None, None, reason)

    price = listing.get('price_total')
    if price is None:
        return FeasibilityResult(None, None, None, None, None)

    is_prov = is_provisionsfrei(listing)
    
    rate = float(c['rate_annual'])
    if rate > 1.0:
        rate = rate / 100.0
        
    term = int(c['term_months'])
    
    down_pct = float(c['down_pct'])
    if down_pct > 1.0:
        down_pct = down_pct / 100.0

    side_cost_pct = 0.035 + 0.018 + 0.011 + (0.0 if is_prov else 0.036)
    ggg_extra = max(0.0, price - 500_000) * 0.023
    cash_needed = price * side_cost_pct + price * down_pct + ggg_extra

    if cash_needed > c['cash_reserves']:
        return FeasibilityResult(False, cash_needed, None, None,
                                 f"cash_needed {cash_needed:,.0f} > {c['cash_reserves']:,.0f}")

    loan = price * (1.0 - down_pct)
    annuity = calculate_monthly_payment(loan, rate, term)

    bk = listing.get('betriebskosten') or 0
    ruecklage = listing.get('ruecklage_eur_month') or 0
    carrying = bk + ruecklage if (bk + ruecklage) > 0 else c['default_bk']
    monthly_outflow = annuity + carrying

    if monthly_outflow > c['max_monthly']:
        return FeasibilityResult(False, cash_needed, monthly_outflow, loan,
                                 f"monthly {monthly_outflow:.0f} > {c['max_monthly']}")

    return FeasibilityResult(True, cash_needed, monthly_outflow, loan, None)
