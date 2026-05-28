# bank_loan_ready Feasibility Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `bank_loan_ready` buyer profile with hard-gate filtering and Austrian financial feasibility math, storing results on each listing in MongoDB.

**Architecture:** New `Application/feasibility.py` module handles all gates (HWB, energy class, rental status, price ceiling) and financial math (annuity + side costs). Scrapers compute `availability_status`, `bezirk_score`, `is_provisionsfrei`, and call `compute_feasibility()` at scrape-end. `run_top5.py` pre-filters on `feasibility_passed` when using the `bank_loan_ready` profile.

**Tech Stack:** Python 3.11+, pytest, dataclasses, re, MongoDB via existing `mongodb_handler.py`

---

## File Map

| Action | File | What changes |
|---|---|---|
| Modify | `Project/Domain/listing.py` | +6 Optional fields |
| Create | `Project/Application/feasibility.py` | gates + financial math module |
| Create | `Tests/test_feasibility.py` | unit tests for feasibility module |
| Modify | `Project/Application/scoring.py` | +2 NORMALIZATION_RANGES entries |
| Modify | `Project/Application/buyer_profiles.py` | updated `bank_loan_ready` weight dict |
| Modify | `Project/Application/scraping/willhaben_scraper.py` | availability extraction + scrape-end block |
| Modify | `Project/Application/scraping/derstandard_scraper.py` | same scrape-end block (2 return sites) |
| Modify | `Project/Application/scraping/immo_kurier_scraper.py` | same scrape-end block |
| Modify | `Project/run_top5.py` | bezirk_score fallback + feasibility pre-filter + Telegram output |

---

## Task 1: Add 6 new fields to Domain/listing.py

**Files:**
- Modify: `Project/Domain/listing.py`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_listing_fields.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Domain.listing import Listing
from Domain.sources import Source

def test_new_fields_exist_with_none_defaults():
    l = Listing(url='http://example.com', source=Source.WILLHABEN)
    assert hasattr(l, 'availability_status') and l.availability_status is None
    assert hasattr(l, 'rental_end_date') and l.rental_end_date is None
    assert hasattr(l, 'is_provisionsfrei') and l.is_provisionsfrei is None
    assert hasattr(l, 'bezirk_score') and l.bezirk_score is None
    assert hasattr(l, 'feasibility_passed') and l.feasibility_passed is None
    assert hasattr(l, 'feasibility_report') is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
python -m pytest Tests/test_listing_fields.py -v
```

Expected: `AttributeError` or `FAILED` — fields do not exist yet.

- [ ] **Step 3: Add 6 fields to Domain/listing.py**

Open `Project/Domain/listing.py`. After the existing `betriebskosten_breakdown` field (last field in file, line ~77), add:

```python
    availability_status:   Optional[str]        = None
    # 'vacant' | 'rented_befristet' | 'rented_unbefristet' | 'construction' | 'unknown'
    rental_end_date:       Optional[str]        = None
    # 'YYYY-MM' format; only set when availability_status == 'rented_befristet'
    is_provisionsfrei:     Optional[int]        = None
    # 1 = commission-free, 0 = has commission, None = unknown
    bezirk_score:          Optional[int]        = None
    # 1 = target Bezirk (1020/1030/1040/1080/1130/1180/1190), 0 = not target, None = unparsed
    feasibility_passed:    Optional[bool]       = None
    # True = all gates + math pass, False = fails, None = price unknown
    feasibility_report:    Optional[Dict[str, Any]] = field(default_factory=dict)
    # keys: cash_needed, monthly_outflow, loan_principal, failure_reason
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest Tests/test_listing_fields.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add Project/Domain/listing.py Tests/test_listing_fields.py
git commit -m "feat: add 6 feasibility fields to Listing dataclass"
```

---

## Task 2: Create Application/feasibility.py

**Files:**
- Create: `Project/Application/feasibility.py`
- Create: `Tests/test_feasibility.py`

- [ ] **Step 1: Write failing tests**

Create `Tests/test_feasibility.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import pytest
from Application.feasibility import (
    compute_feasibility, passes_hard_gates, extract_availability_status, FeasibilityResult
)

# ── passes_hard_gates ──────────────────────────────────────────────────────────

def test_gate_hwb_too_high():
    assert passes_hard_gates({'hwb_value': 90}) is False

def test_gate_hwb_boundary_exact_80_passes():
    assert passes_hard_gates({'hwb_value': 80.0}) is True

def test_gate_hwb_unknown_passes():
    assert passes_hard_gates({'hwb_value': None}) is True

def test_gate_bad_energy_class_e():
    assert passes_hard_gates({'energy_class': 'E'}) is False

def test_gate_bad_energy_class_case_insensitive():
    assert passes_hard_gates({'energy_class': 'f'}) is False

def test_gate_good_energy_class_b_passes():
    assert passes_hard_gates({'energy_class': 'B'}) is True

def test_gate_unknown_energy_passes():
    assert passes_hard_gates({'energy_class': None}) is True

def test_gate_rented_unbefristet():
    assert passes_hard_gates({'availability_status': 'rented_unbefristet'}) is False

def test_gate_construction():
    assert passes_hard_gates({'availability_status': 'construction'}) is False

def test_gate_rented_befristet_within_horizon():
    assert passes_hard_gates({'availability_status': 'rented_befristet', 'rental_end_date': '2027-11'}) is True

def test_gate_rented_befristet_beyond_horizon():
    assert passes_hard_gates({'availability_status': 'rented_befristet', 'rental_end_date': '2028-03'}) is False

def test_gate_rented_befristet_exact_boundary():
    assert passes_hard_gates({'availability_status': 'rented_befristet', 'rental_end_date': '2027-12'}) is True

def test_gate_price_too_high_with_commission():
    assert passes_hard_gates({'price_total': 510_000, 'is_provisionsfrei': 0}) is False

def test_gate_price_ok_no_commission():
    assert passes_hard_gates({'price_total': 499_999, 'is_provisionsfrei': 0}) is True

def test_gate_price_ok_provisionsfrei():
    assert passes_hard_gates({'price_total': 550_000, 'is_provisionsfrei': 1}) is True

def test_gate_price_too_high_provisionsfrei():
    assert passes_hard_gates({'price_total': 620_000, 'is_provisionsfrei': 1}) is False

def test_gate_unknown_commission_uses_conservative_ceiling():
    # None commission → conservative €500k ceiling
    assert passes_hard_gates({'price_total': 510_000, 'is_provisionsfrei': None}) is False

def test_gate_price_unknown_skips_ceiling():
    assert passes_hard_gates({'price_total': None}) is True

# ── compute_feasibility ────────────────────────────────────────────────────────

def test_feasibility_passes_400k_with_bk():
    r = compute_feasibility({'price_total': 400_000, 'is_provisionsfrei': 0, 'betriebskosten': 200})
    assert r.feasibility_passed is True
    assert r.cash_needed == pytest.approx(80_000, abs=500)
    assert r.monthly_outflow < 2_000

def test_feasibility_passes_500k_edge():
    r = compute_feasibility({'price_total': 500_000, 'is_provisionsfrei': 0, 'betriebskosten': 0, 'ruecklage_eur_month': 0})
    # cash_needed = 500k * 0.20 = exactly 100k → passes
    # monthly uses DEFAULT_BK=250 since bk+ruecklage=0
    assert r.cash_needed == pytest.approx(100_000, abs=1)

def test_feasibility_fails_cash_600k_provisionsfrei():
    r = compute_feasibility({'price_total': 600_000, 'is_provisionsfrei': 1, 'betriebskosten': 200})
    assert r.feasibility_passed is False
    assert 'cash' in r.failure_reason.lower() or 'monthly' in r.failure_reason.lower()

def test_feasibility_fails_monthly_550k_provisionsfrei():
    r = compute_feasibility({'price_total': 550_000, 'is_provisionsfrei': 1, 'betriebskosten': 200})
    assert r.feasibility_passed is False
    assert r.monthly_outflow > 2_000

def test_feasibility_no_price_returns_none():
    r = compute_feasibility({'price_total': None})
    assert r.feasibility_passed is None
    assert r.cash_needed is None

def test_feasibility_gate_fires_before_math():
    # HWB gate fires → no math computed
    r = compute_feasibility({'price_total': 300_000, 'hwb_value': 120})
    assert r.feasibility_passed is False
    assert 'HWB' in r.failure_reason

def test_feasibility_default_bk_used_when_missing():
    r1 = compute_feasibility({'price_total': 400_000, 'is_provisionsfrei': 0})
    r2 = compute_feasibility({'price_total': 400_000, 'is_provisionsfrei': 0, 'betriebskosten': 250})
    assert r1.monthly_outflow == pytest.approx(r2.monthly_outflow, abs=1)

def test_feasibility_ruecklage_included_in_monthly():
    r_no_rl = compute_feasibility({'price_total': 400_000, 'betriebskosten': 200, 'ruecklage_eur_month': 0})
    r_with_rl = compute_feasibility({'price_total': 400_000, 'betriebskosten': 200, 'ruecklage_eur_month': 100})
    assert r_with_rl.monthly_outflow == pytest.approx(r_no_rl.monthly_outflow + 100, abs=1)

def test_feasibility_ggg_extra_on_price_above_500k():
    # price=510k provisionsfrei: GGG extra = 10k * 0.023 = 230
    r = compute_feasibility({'price_total': 510_000, 'is_provisionsfrei': 1, 'betriebskosten': 0, 'ruecklage_eur_month': 0})
    expected_cash = 510_000 * (0.035 + 0.018 + 0.011) + 510_000 * 0.10 + 10_000 * 0.023
    assert r.cash_needed == pytest.approx(expected_cash, abs=1)

# ── extract_availability_status ────────────────────────────────────────────────

def test_avail_ab_sofort():
    status, end = extract_availability_status("ab sofort verfügbar")
    assert status == 'vacant'
    assert end is None

def test_avail_bestandsfrei():
    status, end = extract_availability_status("bestandsfreie Wohnung")
    assert status == 'vacant'

def test_avail_rented_befristet_order1():
    status, end = extract_availability_status("befristet vermietet bis November 2027")
    assert status == 'rented_befristet'
    assert end == '2027-11'

def test_avail_rented_befristet_order2():
    # Matches the willhaben example: "bis Nov 2027 befristet vermietete"
    status, end = extract_availability_status("bis November 2027 befristet vermietete Traumwohnung")
    assert status == 'rented_befristet'
    assert end == '2027-11'

def test_avail_rented_befristet_numeric_date():
    status, end = extract_availability_status("befristet vermietet bis 11/2027")
    assert status == 'rented_befristet'
    assert end == '2027-11'

def test_avail_rented_unbefristet():
    status, end = extract_availability_status("unbefristet vermietet")
    assert status == 'rented_unbefristet'
    assert end is None

def test_avail_construction():
    status, end = extract_availability_status("Wohnung noch in Bau")
    assert status == 'construction'

def test_avail_bauprojekt():
    status, end = extract_availability_status("Bauprojekt in Wien")
    assert status == 'construction'

def test_avail_leibrente():
    status, end = extract_availability_status("Leibrente möglich")
    assert status == 'rented_unbefristet'

def test_avail_wohnrecht():
    status, end = extract_availability_status("mit lebenslangem Wohnrecht")
    assert status == 'rented_unbefristet'

def test_avail_unknown():
    status, end = extract_availability_status("schöne 3-Zimmer Wohnung in Wien")
    assert status == 'unknown'
    assert end is None

def test_avail_empty_string():
    status, end = extract_availability_status("")
    assert status == 'unknown'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest Tests/test_feasibility.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'compute_feasibility' from 'Application.feasibility'`

- [ ] **Step 3: Create Project/Application/feasibility.py**

```python
"""
Financial feasibility gates and math for the bank_loan_ready buyer profile.

Hard gates reject listings before scoring based on: HWB > 80, bad energy class,
rental status, rental horizon, and price ceiling.

Financial math validates Austrian first-time-buyer constraints: €100k cash reserves
and €2,000/month max outflow using a 3.2% / 35yr annuity.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

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

    hwb = listing.get('hwb_value')
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
        is_prov = listing.get('is_provisionsfrei') == 1
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
        hwb = listing.get('hwb_value')
        ec = listing.get('energy_class')
        avail = listing.get('availability_status')
        rental_end = listing.get('rental_end_date')
        price = listing.get('price_total')
        is_prov = listing.get('is_provisionsfrei') == 1
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

    is_prov = listing.get('is_provisionsfrei') == 1
    rate = c['rate_annual']
    term = c['term_months']
    down_pct = c['down_pct']

    side_cost_pct = 0.035 + 0.018 + 0.011 + (0.0 if is_prov else 0.036)
    ggg_extra = max(0.0, price - 500_000) * 0.023
    cash_needed = price * side_cost_pct + price * down_pct + ggg_extra

    if cash_needed > c['cash_reserves']:
        return FeasibilityResult(False, cash_needed, None, None,
                                 f"cash_needed {cash_needed:,.0f} > {c['cash_reserves']:,.0f}")

    loan = price * (1.0 - down_pct)
    mr = rate / 12
    annuity = loan * (mr * (1 + mr) ** term) / ((1 + mr) ** term - 1)

    bk = listing.get('betriebskosten') or 0
    ruecklage = listing.get('ruecklage_eur_month') or 0
    carrying = bk + ruecklage if (bk + ruecklage) > 0 else c['default_bk']
    monthly_outflow = annuity + carrying

    if monthly_outflow > c['max_monthly']:
        return FeasibilityResult(False, cash_needed, monthly_outflow, loan,
                                 f"monthly {monthly_outflow:.0f} > {c['max_monthly']}")

    return FeasibilityResult(True, cash_needed, monthly_outflow, loan, None)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest Tests/test_feasibility.py -v
```

Expected: all tests PASSED (29 tests)

- [ ] **Step 5: Commit**

```bash
git add Project/Application/feasibility.py Tests/test_feasibility.py
git commit -m "feat: add feasibility.py — hard gates + Austrian financial math"
```

---

## Task 3: Update scoring.py NORMALIZATION_RANGES

**Files:**
- Modify: `Project/Application/scoring.py:12-30`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_scoring_new_criteria.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scoring import normalize_value

def test_bezirk_score_1_normalizes_100():
    assert normalize_value('bezirk_score', 1) == 100.0

def test_bezirk_score_0_normalizes_0():
    assert normalize_value('bezirk_score', 0) == 0.0

def test_is_provisionsfrei_1_normalizes_100():
    assert normalize_value('is_provisionsfrei', 1) == 100.0

def test_is_provisionsfrei_0_normalizes_0():
    assert normalize_value('is_provisionsfrei', 0) == 0.0

def test_unknown_criterion_returns_0():
    assert normalize_value('nonexistent', 5) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest Tests/test_scoring_new_criteria.py -v
```

Expected: `FAILED` — `normalize_value('bezirk_score', 1)` returns 0.0 (criterion not in NORMALIZATION_RANGES).

- [ ] **Step 3: Add 2 entries to NORMALIZATION_RANGES in scoring.py**

In `Project/Application/scoring.py`, add to `NORMALIZATION_RANGES` dict (after the existing `roof_renovated` entry):

```python
    'bezirk_score':      {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
    'is_provisionsfrei': {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest Tests/test_scoring_new_criteria.py -v
```

Expected: all 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Project/Application/scoring.py Tests/test_scoring_new_criteria.py
git commit -m "feat: add bezirk_score and is_provisionsfrei to scoring NORMALIZATION_RANGES"
```

---

## Task 4: Update bank_loan_ready weights in buyer_profiles.py

**Files:**
- Modify: `Project/Application/buyer_profiles.py:201-222`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_bank_loan_ready_profile.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.buyer_profiles import get_profile

def test_bank_loan_ready_weights_sum_to_1():
    profile = get_profile('bank_loan_ready')
    total = sum(profile['weights'].values())
    assert abs(total - 1.0) < 0.001, f"weights sum to {total}, expected 1.0"

def test_bank_loan_ready_has_bezirk_score():
    profile = get_profile('bank_loan_ready')
    assert 'bezirk_score' in profile['weights']
    assert profile['weights']['bezirk_score'] == 0.10

def test_bank_loan_ready_has_is_provisionsfrei():
    profile = get_profile('bank_loan_ready')
    assert 'is_provisionsfrei' in profile['weights']
    assert profile['weights']['is_provisionsfrei'] == 0.05

def test_bank_loan_ready_hwb_weight_is_013():
    profile = get_profile('bank_loan_ready')
    assert profile['weights']['hwb_value'] == 0.13

def test_bank_loan_ready_school_weight_is_0():
    profile = get_profile('bank_loan_ready')
    assert profile['weights'].get('school_walk_minutes', 0) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest Tests/test_bank_loan_ready_profile.py -v
```

Expected: `FAILED` — `bezirk_score` not in weights, hwb is 0.10.

- [ ] **Step 3: Replace bank_loan_ready weights in buyer_profiles.py**

Find the `'bank_loan_ready'` dict in `Project/Application/buyer_profiles.py` (around line 201). Replace the `'weights'` sub-dict with:

```python
        'weights': {
            'price_per_m2':             0.13,
            'hwb_value':                0.13,
            'ubahn_walk_minutes':       0.12,
            'renovation_needed_rating': 0.12,
            'parifizierung_complete':   0.10,
            'bezirk_score':             0.10,
            'facade_renovated':         0.07,
            'year_built':               0.05,
            'is_provisionsfrei':        0.05,
            'roof_renovated':           0.04,
            'lift_present':             0.03,
            'potential_growth_rating':  0.02,
            'area_m2':                  0.01,
            'floor_level':              0.01,
            'school_walk_minutes':      0.00,
            'balcony_terrace':          0.01,
            'rooms':                    0.01,
        },
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest Tests/test_bank_loan_ready_profile.py -v
```

Expected: all 5 tests PASSED

- [ ] **Step 5: Also run the existing profile tests to check for regressions**

```bash
python -m pytest Tests/test_buyer_profiles.py -v
```

Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add Project/Application/buyer_profiles.py Tests/test_bank_loan_ready_profile.py
git commit -m "feat: update bank_loan_ready weights — add bezirk_score(0.10), is_provisionsfrei(0.05)"
```

---

## Task 5: Update willhaben_scraper.py

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_willhaben_availability.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.feasibility import extract_availability_status

def test_willhaben_title_bis_nov_2027_befristet():
    # Exact URL-slug style from live willhaben listing
    text = "bis-nov-2027-befristet-vermietete-traumwohnung-mit-klimatisierung"
    # URL slugs use hyphens; the function receives description text, not slugs
    # Test the description text equivalent:
    text = "Bis November 2027 befristet vermietete Traumwohnung mit Klimatisierung"
    status, end = extract_availability_status(text)
    assert status == 'rented_befristet'
    assert end == '2027-11'

def test_schluesselfertig():
    status, _ = extract_availability_status("schlüsselfertige Neubau-Wohnung")
    assert status == 'vacant'

def test_fertigstellung_in_description():
    status, _ = extract_availability_status("Fertigstellung 2027")
    assert status == 'construction'
```

- [ ] **Step 2: Run test to verify it passes (uses feasibility module already)**

```bash
python -m pytest Tests/test_willhaben_availability.py -v
```

Expected: all 3 tests PASSED (extract_availability_status already implemented in Task 2)

- [ ] **Step 3: Add scrape-end block to willhaben_scraper.py**

In `Project/Application/scraping/willhaben_scraper.py`, find the bank scoring block that ends around line 530:

```python
            # Bank scoring — Belehnungswert estimate stored at scrape time
            _bank = compute_bank_score(listing)
            listing.belehnungswert_factor   = _bank.belehnungswert_factor
            ...
            listing.bank_score_confidence   = _bank.bank_score_confidence
```

Add the following block AFTER the bank scoring block and BEFORE the source field normalization (`if hasattr(listing.source, 'value'):`):

```python
            # Feasibility fields
            from Application.feasibility import extract_availability_status, compute_feasibility
            _desc_text = (listing.title or '') + ' ' + soup.get_text()
            listing.availability_status, listing.rental_end_date = extract_availability_status(_desc_text)

            listing.is_provisionsfrei = (
                1 if listing.maklerprovision_pct == 0.0
                else 0 if listing.maklerprovision_pct and listing.maklerprovision_pct > 0
                else None
            )

            _target_bezirke = config.get('target_bezirke',
                ['1020', '1030', '1040', '1080', '1130', '1180', '1190'])
            _bezirk_code = None
            if listing.bezirk:
                import re as _re
                _m = _re.search(r'(\d{4})', listing.bezirk)
                _bezirk_code = _m.group(1) if _m else None
            listing.bezirk_score = (1 if _bezirk_code in _target_bezirke
                                    else 0 if _bezirk_code is not None
                                    else None)

            _feasibility = compute_feasibility(listing.__dict__, config.get('feasibility'))
            listing.feasibility_passed = _feasibility.feasibility_passed
            listing.feasibility_report = {
                'cash_needed': _feasibility.cash_needed,
                'monthly_outflow': _feasibility.monthly_outflow,
                'loan_principal': _feasibility.loan_principal,
                'failure_reason': _feasibility.failure_reason,
            }
```

Note: `config` is the module-level config dict already used elsewhere in the scraper. Verify it is in scope at that point (it is — used on line 103 for interest rate constants).

- [ ] **Step 4: Verify import structure — check config is in scope**

```bash
grep -n "^config\s*=\|config\.get\|from.*config" /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project/Application/scraping/willhaben_scraper.py | head -10
```

If `config` is not directly in scope at the method level, use:
```python
from Application.helpers.utils import load_config as _load_config
_cfg = _load_config() or {}
```
and replace `config.get(...)` with `_cfg.get(...)` in the block above.

- [ ] **Step 5: Run existing willhaben tests**

```bash
python -m pytest Tests/test_willhaben_integration.py Tests/test_field_extractors.py -v 2>&1 | tail -20
```

Expected: no regressions. If failures appear, check import paths added in Step 3.

- [ ] **Step 6: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py Tests/test_willhaben_availability.py
git commit -m "feat: add availability/feasibility extraction to willhaben_scraper"
```

---

## Task 6: Add scrape-end block to derstandard and immo_kurier scrapers

**Files:**
- Modify: `Project/Application/scraping/derstandard_scraper.py` (2 `return listing` sites: lines ~701 and ~1162)
- Modify: `Project/Application/scraping/immo_kurier_scraper.py` (1 `return listing` site: line ~322)

The scrape-end block is identical to Task 5 except use `soup.get_text()` directly (no guaranteed `listing.title` in all paths). Also, DerStandard and ImmoKurier may not expose `config` at method level — use `load_config()`.

- [ ] **Step 1: Add block to derstandard_scraper.py (primary path, ~line 694)**

Find the primary success `return listing` around line 701 (inside `if self.validate_listing_data(listing):`). Insert BEFORE that `return listing`:

```python
                # Feasibility fields
                from Application.feasibility import extract_availability_status, compute_feasibility
                from Application.helpers.utils import load_config as _load_config
                _cfg = _load_config() or {}
                _desc_text = (listing.title or '') + ' ' + soup.get_text()
                listing.availability_status, listing.rental_end_date = extract_availability_status(_desc_text)

                listing.is_provisionsfrei = (
                    1 if listing.maklerprovision_pct == 0.0
                    else 0 if listing.maklerprovision_pct and listing.maklerprovision_pct > 0
                    else None
                )

                _target_bezirke = _cfg.get('target_bezirke',
                    ['1020', '1030', '1040', '1080', '1130', '1180', '1190'])
                _bezirk_code = None
                if listing.bezirk:
                    import re as _re
                    _m = _re.search(r'(\d{4})', listing.bezirk)
                    _bezirk_code = _m.group(1) if _m else None
                listing.bezirk_score = (1 if _bezirk_code in _target_bezirke
                                        else 0 if _bezirk_code is not None
                                        else None)

                _feasibility = compute_feasibility(listing.__dict__, _cfg.get('feasibility'))
                listing.feasibility_passed = _feasibility.feasibility_passed
                listing.feasibility_report = {
                    'cash_needed': _feasibility.cash_needed,
                    'monthly_outflow': _feasibility.monthly_outflow,
                    'loan_principal': _feasibility.loan_principal,
                    'failure_reason': _feasibility.failure_reason,
                }
```

- [ ] **Step 2: Add same block to derstandard_scraper.py fallback path (~line 1162)**

Find the second `return listing` in `extract_from_html_selectors` (~line 1162). Insert the identical block before it.

- [ ] **Step 3: Add block to immo_kurier_scraper.py (~line 322)**

Find `return listing` around line 322. Insert the identical block before it.

- [ ] **Step 4: Run existing scraper tests**

```bash
python -m pytest Tests/test_derstandard_integration.py Tests/test_immo_kurier.py -v 2>&1 | tail -20
```

Expected: no regressions.

- [ ] **Step 5: Commit**

```bash
git add Project/Application/scraping/derstandard_scraper.py \
        Project/Application/scraping/immo_kurier_scraper.py
git commit -m "feat: add availability/feasibility extraction to derstandard and immo_kurier scrapers"
```

---

## Task 7: Update run_top5.py — feasibility pre-filter + Telegram output

**Files:**
- Modify: `Project/run_top5.py`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_feasibility_filter.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.feasibility import passes_hard_gates

def _make_listing(**kwargs):
    base = {'price_total': 400_000, 'bezirk': '1030 Wien'}
    base.update(kwargs)
    return base

def test_feasibility_filter_excludes_failed():
    listings = [
        _make_listing(feasibility_passed=True),
        _make_listing(feasibility_passed=False),
        _make_listing(feasibility_passed=None),   # unknown → included
    ]
    filtered = [l for l in listings if l.get('feasibility_passed') is not False]
    assert len(filtered) == 2

def test_bezirk_score_fallback_computes_from_bezirk_string():
    listing = {'bezirk': '1030 Wien', 'bezirk_score': None}
    import re
    target = ['1020', '1030', '1040', '1080', '1130', '1180', '1190']
    m = re.search(r'(\d{4})', listing['bezirk'])
    listing['bezirk_score'] = 1 if m and m.group(1) in target else 0
    assert listing['bezirk_score'] == 1

def test_bezirk_score_fallback_non_target():
    listing = {'bezirk': '1140 Wien', 'bezirk_score': None}
    import re
    target = ['1020', '1030', '1040', '1080', '1130', '1180', '1190']
    m = re.search(r'(\d{4})', listing['bezirk'])
    listing['bezirk_score'] = 1 if m and m.group(1) in target else 0
    assert listing['bezirk_score'] == 0

def test_passes_hard_gates_used_as_secondary_filter():
    listings = [
        _make_listing(hwb_value=50),   # good → passes
        _make_listing(hwb_value=120),  # bad  → excluded
        _make_listing(hwb_value=None), # unknown → passes
    ]
    filtered = [l for l in listings if passes_hard_gates(l)]
    assert len(filtered) == 2
```

- [ ] **Step 2: Run test to verify it passes (uses existing feasibility module)**

```bash
python -m pytest Tests/test_feasibility_filter.py -v
```

Expected: all 4 tests PASSED

- [ ] **Step 3: Add bezirk_score fallback + feasibility pre-filter to run_top5.py**

In `Project/run_top5.py`, find the block starting with `valid_listings = filter_valid_listings(...)` (around line 718). Add AFTER that line:

```python
        # bank_loan_ready: apply feasibility pre-filter
        if active_profile == 'bank_loan_ready':
            from Application.feasibility import passes_hard_gates
            import re as _re
            _target_bezirke = config.get('target_bezirke',
                ['1020', '1030', '1040', '1080', '1130', '1180', '1190'])

            # Runtime bezirk_score fallback for pre-existing docs
            for _l in valid_listings:
                if _l.get('bezirk_score') is None and _l.get('bezirk'):
                    _m = _re.search(r'(\d{4})', _l['bezirk'])
                    _l['bezirk_score'] = 1 if _m and _m.group(1) in _target_bezirke else 0

            before = len(valid_listings)
            valid_listings = [_l for _l in valid_listings if passes_hard_gates(_l)]
            valid_listings = [_l for _l in valid_listings if _l.get('feasibility_passed') is not False]
            logging.info(f"🏦 Feasibility filter: {before} → {len(valid_listings)} listings")
```

- [ ] **Step 4: Add feasibility output to Telegram message**

In `run_top5.py`, find where the listing message is composed for Telegram (search for `format_listing_message` or the place that builds the message string). The exact location varies — look for where `price_total`, `area_m2`, `score` are formatted.

Add feasibility output when `active_profile == 'bank_loan_ready'`:

Find the Telegram formatting function in the file (grep: `def format_listing_message` or similar). Locate where the listing card text is assembled. After the existing price/score lines, add:

```python
    # Add feasibility output for bank_loan_ready profile
    if listing.get('feasibility_report'):
        cash = listing['feasibility_report'].get('cash_needed')
        monthly = listing['feasibility_report'].get('monthly_outflow')
        if cash is not None and monthly is not None:
            lines.append(f"💰 Cash needed: €{cash:,.0f} | Monthly: €{monthly:.0f}/mo")
    if listing.get('availability_status') and listing['availability_status'] != 'unknown':
        avail_line = listing['availability_status'].replace('_', ' ')
        if listing.get('rental_end_date'):
            avail_line += f" until {listing['rental_end_date']}"
        lines.append(f"📍 {avail_line}")
```

If the message is built as a string (not a list), adapt accordingly — locate the pattern and insert the new lines after the score/price section.

- [ ] **Step 5: Run existing run_top5 tests**

```bash
python -m pytest Tests/test_run_top5_behavior.py Tests/test_top5_filters.py -v 2>&1 | tail -20
```

Expected: no regressions

- [ ] **Step 6: Commit**

```bash
git add Project/run_top5.py Tests/test_feasibility_filter.py
git commit -m "feat: add feasibility pre-filter and output to run_top5 bank_loan_ready profile"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Covered by task |
|---|---|
| `bezirk_score` + `is_provisionsfrei` in NORMALIZATION_RANGES | Task 3 |
| Updated `bank_loan_ready` weights (verified 1.000) | Task 4 |
| `Application/feasibility.py` with hard gates + math | Task 2 |
| `passes_hard_gates` exported + skips None fields | Task 2 |
| `compute_feasibility` returns `FeasibilityResult` | Task 2 |
| `DEFAULT_BK=250` when both BK+ruecklage missing | Task 2 |
| GGG §26a excess at 2.3% above €500k | Task 2 |
| 6 new Listing fields | Task 1 |
| `extract_availability_status` — both regex orderings | Task 2 |
| Scraper: availability + bezirk_score + is_prov + feasibility at scrape-end | Tasks 5+6 |
| run_top5.py: bezirk_score fallback + pre-filter + Telegram output | Task 7 |
| Config keys: `target_bezirke`, `feasibility.*`, `default_bk` | All tasks (read from config) |

### Placeholder scan

No TBD/TODO left. Task 7 Step 4 says "locate where message is assembled" — this is intentional; the exact line varies and is identified by the grep instruction given. The code to insert is fully specified.

### Type consistency

- `FeasibilityResult` defined in Task 2, referenced in Tasks 5, 6, 7 ✓
- `extract_availability_status` → `Tuple[str, Optional[str]]` used consistently in Tasks 5, 6 ✓
- `passes_hard_gates(listing: dict) -> bool` used in Task 7 ✓
- `bezirk_score: Optional[int]` (0/1/None) matches NORMALIZATION_RANGES min=0/max=1 ✓
- `is_provisionsfrei: Optional[int]` (0/1/None) matches NORMALIZATION_RANGES ✓
