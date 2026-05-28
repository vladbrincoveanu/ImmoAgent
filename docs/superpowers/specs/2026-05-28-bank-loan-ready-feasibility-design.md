# bank_loan_ready Profile Update + Financial Feasibility Engine

**Date:** 2026-05-28  
**Status:** Approved  
**Scope:** Scoring profile update, feasibility validation module, new Listing fields, scraper extraction, run_top5.py integration

---

## Problem

The existing `bank_loan_ready` buyer profile scores properties on bank-collateral criteria but does not:
- Reward target Vienna Bezirke (1020, 1030, 1040, 1080, 1130, 1180, 1190)
- Reward commission-free listings (which raise effective price ceiling to €610k)
- Hard-gate properties that fail HWB, energy class, rental status, or price constraints
- Validate whether a specific listing is financially feasible given fixed cash/monthly constraints

---

## Constraints

| Constraint | Value |
|---|---|
| Total cash reserves | €100,000 |
| Max monthly outflow | €2,000 |
| Mortgage rate (fixed) | 3.20% |
| Loan term | 35 years (420 months) |
| Standard price ceiling | €500,000 |
| Provisionsfrei price ceiling | €610,000 |
| Max rental end date (befristet) | 2027-12 |

Side cost structure (Austrian law, May 2026):
- Grunderwerbsteuer: 3.5%
- Treuhandschaft/escrow: 1.8%
- Bank + notary setup: 1.1%
- Broker fee: 0% if provisionsfrei, 3.6% otherwise
- GGG exemption (§26a): ownership + mortgage registration fees = 0% up to €500k

---

## Architecture

```
Scraper
  → extract availability_status + rental_end_date
  → compute is_provisionsfrei from maklerprovision_pct
  → compute bezirk_score from bezirk string

  → feasibility.compute_feasibility()
      → hard gates: HWB, energy_class, rental status, price ceiling
      → financial math: cash gate + monthly gate
      → stores feasibility_passed + feasibility_report on listing

run_top5.py (bank_loan_ready profile)
  → pre-filter: feasibility_passed != False
  → score via updated bank_loan_ready weights
  → Telegram message includes cash_needed + monthly_outflow
```

---

## Section 1: Updated `bank_loan_ready` Profile

### Weight changes

| Criterion | Old | New | Reason |
|---|---|---|---|
| `bezirk_score` | — | 0.10 | NEW: target Bezirke bonus |
| `is_provisionsfrei` | — | 0.05 | NEW: no commission = higher cash headroom |
| `hwb_value` | 0.10 | 0.13 | critical for 90% LTV |
| `school_walk_minutes` | 0.02 | 0.00 | irrelevant for this buyer |
| `rooms` | 0.02 | 0.01 | minor reduction |
| `balcony_terrace` | 0.02 | 0.01 | minor reduction |
| all others | unchanged | unchanged | |

**Total: 1.00**

### New NORMALIZATION_RANGES entries (scoring.py)

```python
'bezirk_score':      {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
'is_provisionsfrei': {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
```

### Module: buyer_profiles.py
- **Responsibility:** Store updated `bank_loan_ready` weight dict
- **Interface:** Called by `get_profile('bank_loan_ready')` → returns weights dict
- **Dependencies:** None
- **Size target:** No new code; edit existing profile dict

### Module: scoring.py
- **Responsibility:** Normalize `bezirk_score` and `is_provisionsfrei` values
- **Interface:** `normalize_value(criterion_name, actual_value)` — no signature change
- **Dependencies:** NORMALIZATION_RANGES dict
- **Size target:** 2-line addition to NORMALIZATION_RANGES

---

## Section 2: New `Application/feasibility.py` Module

### Hard gates

Applied before scoring. Any gate that fires → `feasibility_passed = False`.

| Gate | Condition | Skip if |
|---|---|---|
| HWB | `hwb_value > 80` | `hwb_value is None` |
| Energy class | `energy_class in {'D','E','F','G'}` | `energy_class is None` |
| Unbefristet rented | `availability_status == 'rented_unbefristet'` | — |
| Construction | `availability_status == 'construction'` | — |
| Rental horizon | `rental_end_date > '2027-12'` | `rental_end_date is None` |
| Price ceiling | `price_total > 610k` if provisionsfrei, else `> 500k` | `price_total is None` |

### Financial math

```python
CASH_RESERVES = 100_000
MAX_MONTHLY = 2_000
RATE_ANNUAL = 0.032
TERM_MONTHS = 420
DOWN_PCT = 0.10

side_cost_pct = 0.035 + 0.018 + 0.011 + (0.0 if is_provisionsfrei else 0.036)
cash_needed = price * side_cost_pct + price * DOWN_PCT
# gate: cash_needed > CASH_RESERVES → fail

loan = price * 0.90
monthly_rate = RATE_ANNUAL / 12
annuity = loan * (monthly_rate * (1+monthly_rate)**TERM_MONTHS) / ((1+monthly_rate)**TERM_MONTHS - 1)
monthly_outflow = annuity + (betriebskosten or 0)
# gate: monthly_outflow > MAX_MONTHLY → fail
```

If `price_total is None` → `feasibility_passed = None` (unknown, not excluded).

### Output

```python
@dataclass
class FeasibilityResult:
    feasibility_passed: Optional[bool]   # None = unknown (no price)
    cash_needed: Optional[float]
    monthly_outflow: Optional[float]
    loan_principal: Optional[float]
    failure_reason: Optional[str]        # first gate that fired
```

### Module: feasibility.py
- **Responsibility:** Run hard gates + financial math, return FeasibilityResult
- **Interface:** `compute_feasibility(listing: dict) -> FeasibilityResult`
- **Dependencies:** No external; reads listing dict fields
- **Size target:** ~120 lines, single responsibility

---

## Section 3: New Listing Fields

Add to `Domain/listing.py` (all Optional, all default None for backward compat):

```python
availability_status: Optional[str] = None
# 'vacant' | 'rented_befristet' | 'rented_unbefristet' | 'construction' | 'unknown'

rental_end_date: Optional[str] = None
# 'YYYY-MM' format, populated only when availability_status == 'rented_befristet'

is_provisionsfrei: Optional[int] = None
# 1 = commission-free, 0 = has commission, None = unknown (not set)

bezirk_score: Optional[int] = None
# 1 = target Bezirk, 0 = not target, None = bezirk not parsed

feasibility_passed: Optional[bool] = None
# True = passes all gates + math, False = fails, None = price unknown

feasibility_report: Optional[Dict[str, Any]] = field(default_factory=dict)
# keys: cash_needed, monthly_outflow, loan_principal, failure_reason
```

### Module: Domain/listing.py
- **Responsibility:** Domain model — 6 new fields added
- **Interface:** Dataclass fields, backward-compatible (Optional + default None)
- **Dependencies:** None
- **Size target:** 6-line addition

---

## Section 4: Scraper Changes (willhaben_scraper.py)

### New: `extract_availability_status(text: str) -> tuple[str, Optional[str]]`

Returns `(availability_status, rental_end_date)`.

**Patterns (case-insensitive, searched in listing description + attribute text):**

```python
VACANT_PATTERNS = [
    r'ab sofort', r'bestandsfrei', r'belagsfertig',
    r'schlüsselfertig', r'leerstehend', r'sofort bezugsfertig'
]

RENTED_BEFRISTET_PATTERN = r'befristet\s+vermiet\w*\s+bis\s+(\w+\s+\d{4}|\d{1,2}[./]\d{4})'
RENTED_UNBEFRISTET_PATTERN = r'unbefristet\s+vermiet\w*'

CONSTRUCTION_PATTERNS = [
    r'in\s+bau', r'bauprojekt', r'fertigstellung\s+\d{4}'
]

HARD_DISCARD_PATTERNS = [r'leibrente', r'wohnrecht']
```

Priority order: hard_discard → construction → rented_unbefristet → rented_befristet → vacant → unknown.

For `rented_befristet`: parse date to `'YYYY-MM'`. Map month names (Nov → 11, etc.).

### New: computed fields at scrape-end

```python
# After listing object built:
listing.availability_status, listing.rental_end_date = extract_availability_status(full_text)

listing.is_provisionsfrei = (
    1 if listing.maklerprovision_pct == 0.0
    else 0 if listing.maklerprovision_pct and listing.maklerprovision_pct > 0
    else None  # unknown
)

TARGET_BEZIRKE = config.get('target_bezirke', ['1020','1030','1040','1080','1130','1180','1190'])
bezirk_code = re.search(r'(\d{4})', listing.bezirk or '').group(1) if listing.bezirk else None
listing.bezirk_score = 1 if bezirk_code in TARGET_BEZIRKE else 0 if bezirk_code else None
```

### Run feasibility at scrape-end

```python
from Application.feasibility import compute_feasibility
result = compute_feasibility(listing.__dict__)
listing.feasibility_passed = result.feasibility_passed
listing.feasibility_report = {
    'cash_needed': result.cash_needed,
    'monthly_outflow': result.monthly_outflow,
    'loan_principal': result.loan_principal,
    'failure_reason': result.failure_reason,
}
```

### Module: willhaben_scraper.py
- **Responsibility:** Add availability/rental extraction + computed fields at scrape-end
- **Interface:** `extract_availability_status(text) -> (str, Optional[str])` — new private fn
- **Dependencies:** `Application.feasibility.compute_feasibility`
- **Size target:** ~60 lines added to existing scraper

> Same changes needed in `derstandard_scraper.py` and `immo_kurier_scraper.py` — same scrape-end block.

---

## Section 5: run_top5.py Integration

When `--buyer-profile=bank_loan_ready` is active:

1. **Pre-filter before scoring** (add to existing filter chain):
   ```python
   from Application.feasibility import passes_hard_gates
   listings = [l for l in listings if passes_hard_gates(l)]
   listings = [l for l in listings if l.get('feasibility_passed') is not False]
   ```

2. **Telegram message additions** — include in listing card:
   ```
   💰 Cash needed: €{cash_needed:,.0f} | Monthly: €{monthly_outflow:.0f}/mo
   📍 {availability_status} {rental_end_date or ''}
   ```

3. **`passes_hard_gates(listing: dict) -> bool`** — exported from `feasibility.py` for use at report time (handles listings where feasibility was not computed at scrape time, e.g. older docs).

### Module: run_top5.py
- **Responsibility:** Apply bank_loan_ready pre-filters + add feasibility fields to Telegram output
- **Interface:** `--buyer-profile=bank_loan_ready` triggers extended filter
- **Dependencies:** `Application.feasibility.passes_hard_gates`
- **Size target:** ~20 lines added

---

## Configuration

Add to `config.json` (optional, these are defaults):

```json
{
  "feasibility": {
    "cash_reserves": 100000,
    "max_monthly": 2000,
    "rate_annual": 0.032,
    "term_months": 420,
    "down_pct": 0.10,
    "max_rental_end_date": "2027-12",
    "standard_price_ceiling": 500000,
    "provisionsfrei_price_ceiling": 610000
  },
  "target_bezirke": ["1020", "1030", "1040", "1080", "1130", "1180", "1190"]
}
```

---

## Implementation Order

1. `Domain/listing.py` — add 6 fields (no deps, no risk)
2. `Application/feasibility.py` — new module, pure functions
3. `scoring.py` — add 2 entries to NORMALIZATION_RANGES
4. `buyer_profiles.py` — update `bank_loan_ready` weights
5. `willhaben_scraper.py` — add extraction + scrape-end computation
6. `derstandard_scraper.py` + `immo_kurier_scraper.py` — same scrape-end block
7. `run_top5.py` — add pre-filter + Telegram output

---

## Open Questions

None. All decisions made.
