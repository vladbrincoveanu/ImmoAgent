# Neubauprojekt Expansion + Belehnungswert Bank Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Belehnungswert bank-scoring model that estimates required equity per listing, store it at scrape time, display it on dashboard cards with a hide-if-unfinanceable toggle, and expand Willhaben scraping to cover Neubauprojekt (new build) listings.

**Architecture:** New pure-function module `bank_scoring.py` computes a Belehnungswert factor from 5 listing fields and derives 80%/90%-LTV equity estimates. All 3 scrapers call this at the end of `scrape_single_listing`. A backfill script patches existing DB records. The dashboard gets a new `EquityBadge` component, max-price input, and show-unfinanceable toggle wired into both desktop and mobile filter surfaces. Neubauprojekt URL is added to config and the scraper loop extended with a URL pagination fix.

**Tech Stack:** Python 3, pymongo, dataclasses / Next.js 15, TypeScript, Tailwind CSS

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `Project/Application/bank_scoring.py` | Create | Pure function: compute Belehnungswert factor + equity estimates |
| `Project/Domain/listing.py` | Modify | +5 Optional bank score fields |
| `Project/Application/scraping/willhaben_scraper.py` | Modify | Wire bank_scoring; fix URL pagination |
| `Project/Application/scraping/immo_kurier_scraper.py` | Modify | Wire bank_scoring |
| `Project/Application/scraping/derstandard_scraper.py` | Modify | Wire bank_scoring |
| `Project/Application/main.py` | Modify | Add `search_url_extra` loop in `scrape_willhaben()` |
| `config.json` | Modify | Add `search_url_extra` with neubauprojekt URL |
| `Project/scripts/backfill_bank_scores.py` | Create | One-time DB backfill script |
| `Tests/test_bank_scoring.py` | Create | Unit tests for bank_scoring module |
| `dashboard/lib/types.ts` | Modify | +bank score fields to `ListingBase` and `ListingDetail` |
| `dashboard/components/EquityBadge.tsx` | Create | Equity display badge component |
| `dashboard/components/ListingCard.tsx` | Modify | Render EquityBadge below price |
| `dashboard/components/FilterBar.tsx` | Modify | Add maxPrice input + showUnfinanceable toggle (desktop) |
| `dashboard/components/FilterDrawer.tsx` | Modify | Add maxPrice input + showUnfinanceable toggle (mobile) |
| `dashboard/app/dashboard/page.tsx` | Modify | maxPrice + showUnfinanceable state, filter logic, pass props |
| `dashboard/components/ListingDetail.tsx` | Modify | Add Financing section to modal |

---

## Task 1: Bank scoring module (TDD)

**Files:**
- Create: `Project/Application/bank_scoring.py`
- Create: `Tests/test_bank_scoring.py`

Run all commands from `Project/` directory.

- [ ] **Step 1: Write the failing tests**

Create `Tests/test_bank_scoring.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock

def make_listing(**kwargs):
    m = MagicMock()
    m.energy_class = kwargs.get('energy_class', None)
    m.year_built = kwargs.get('year_built', None)
    m.facade_renovated = kwargs.get('facade_renovated', None)
    m.roof_renovated = kwargs.get('roof_renovated', None)
    m.window_type = kwargs.get('window_type', None)
    m.price_total = kwargs.get('price_total', None)
    return m

class TestComputeBankScore(unittest.TestCase):

    def test_calibration_altbau_energy_e_1900(self):
        """Bank conversation: Altbau 1900, energy E → 44% equity at 80% LTV."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(energy_class='E', year_built=1900, price_total=560000)
        score = compute_bank_score(listing)
        self.assertAlmostEqual(score.estimated_down_pct, 44.0, places=1)
        self.assertAlmostEqual(score.belehnungswert_factor, 0.70, places=4)

    def test_neubau_energy_b_2023(self):
        """Neubau with energy B, year 2023 → factor capped at 1.0 → 20% standard, 10% KIM-V."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(energy_class='B', year_built=2023, price_total=310000)
        score = compute_bank_score(listing)
        self.assertAlmostEqual(score.belehnungswert_factor, 1.0, places=4)
        self.assertAlmostEqual(score.estimated_down_pct, 20.0, places=1)
        self.assertAlmostEqual(score.estimated_down_pct_kimv, 10.0, places=1)

    def test_no_price_returns_none_equity(self):
        """No price_total → equity fields None, factor still computed."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(energy_class='C', year_built=1990)
        score = compute_bank_score(listing)
        self.assertIsNone(score.estimated_down_pct)
        self.assertIsNone(score.estimated_equity_eur)
        self.assertIsNotNone(score.belehnungswert_factor)

    def test_confidence_all_none_is_low(self):
        """5 None inputs → confidence = 'low'."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing()
        score = compute_bank_score(listing)
        self.assertEqual(score.bank_score_confidence, 'low')

    def test_confidence_all_known_is_high(self):
        """0 None inputs → confidence = 'high'."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(
            energy_class='C', year_built=2000,
            facade_renovated=True, roof_renovated=False,
            window_type='kunststoff', price_total=400000,
        )
        score = compute_bank_score(listing)
        self.assertEqual(score.bank_score_confidence, 'high')

    def test_kastenfenster_penalty(self):
        """kastenfenster window → −0.04 adjustment."""
        from Application.bank_scoring import compute_bank_score
        base = make_listing(energy_class='C', year_built=1990, price_total=300000)
        kast = make_listing(energy_class='C', year_built=1990,
                            window_type='kastenfenster', price_total=300000)
        base_score = compute_bank_score(base)
        kast_score = compute_bank_score(kast)
        self.assertAlmostEqual(
            base_score.belehnungswert_factor - kast_score.belehnungswert_factor, 0.04, places=4
        )

    def test_factor_capped_at_1(self):
        """Factor never exceeds 1.0."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(
            energy_class='A+', year_built=2023,
            facade_renovated=True, roof_renovated=True,
            window_type='isolierverglasung', price_total=400000,
        )
        score = compute_bank_score(listing)
        self.assertLessEqual(score.belehnungswert_factor, 1.0)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```bash
cd Project && python -m pytest Tests/test_bank_scoring.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'Application.bank_scoring'`

- [ ] **Step 3: Create `Project/Application/bank_scoring.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

ENERGY_BASE: dict[str, float] = {
    'A++': 1.00, 'A+': 1.00,
    'A':   0.97, 'B':  0.97,
    'C':   0.92,
    'D':   0.85,
    'E':   0.75,
    'F':   0.65, 'G': 0.65,
}


@dataclass
class BankScore:
    belehnungswert_factor:   float
    estimated_down_pct:      Optional[float]   # 80% LTV (standard)
    estimated_down_pct_kimv: Optional[float]   # 90% LTV (KIM-V program)
    estimated_equity_eur:    Optional[int]
    bank_score_confidence:   str               # "low" | "medium" | "high"


def compute_bank_score(listing) -> BankScore:
    """Estimate Belehnungswert factor and equity requirements from listing fields.

    Uses 80% LTV as base (matches Austrian standard bank practice).
    KIM-V 90% LTV shown as optimistic second value for first-time buyer programs.

    Calibration: energy_class='E', year_built=1900, all others None →
      factor=0.70 → estimated_down_pct=44.0 (matches real bank conversation).
    """
    energy_class    = listing.energy_class
    year_built      = listing.year_built
    facade_renovated = listing.facade_renovated
    roof_renovated  = listing.roof_renovated
    window_type     = listing.window_type
    price_total     = listing.price_total

    # Confidence: count None signals
    none_count = sum(
        1 for v in [energy_class, year_built, facade_renovated, roof_renovated, window_type]
        if v is None
    )
    if none_count <= 1:
        confidence = 'high'
    elif none_count <= 3:
        confidence = 'medium'
    else:
        confidence = 'low'

    # Base factor from energy class
    if energy_class is not None:
        factor = ENERGY_BASE.get(str(energy_class).upper().strip(), 0.82)
    else:
        # year_built fallback — ALSO gets year adjustment below (intentional double-signal:
        # old Altbau with no energy cert is penalized for both missing data AND old age).
        if year_built is not None and year_built >= 2010:
            factor = 0.95
        elif year_built is not None and year_built < 1970:
            factor = 0.72
        else:
            factor = 0.82

    # Year built adjustment (always applied, independent of base selection)
    if year_built is not None:
        if year_built >= 2015:
            factor += 0.05
        elif year_built >= 2000:
            factor += 0.02
        elif year_built < 1970:
            factor -= 0.05

    # Renovation adjustments
    if facade_renovated is True:
        factor += 0.04
    elif facade_renovated is False:
        factor -= 0.03

    if roof_renovated is True:
        factor += 0.02

    # Window type adjustment
    if window_type == 'kastenfenster':
        factor -= 0.04
    elif window_type in ('kunststoff', 'holz-alu', 'isolierverglasung'):
        factor += 0.02

    factor = min(1.0, round(factor, 4))

    if not price_total or price_total <= 0:
        return BankScore(
            belehnungswert_factor=factor,
            estimated_down_pct=None,
            estimated_down_pct_kimv=None,
            estimated_equity_eur=None,
            bank_score_confidence=confidence,
        )

    down_pct      = round((1 - 0.80 * factor) * 100, 1)
    down_pct_kimv = round((1 - 0.90 * factor) * 100, 1)
    equity_eur    = round(price_total * down_pct / 100)

    return BankScore(
        belehnungswert_factor=factor,
        estimated_down_pct=down_pct,
        estimated_down_pct_kimv=down_pct_kimv,
        estimated_equity_eur=equity_eur,
        bank_score_confidence=confidence,
    )
```

- [ ] **Step 4: Run tests — expect all 7 passing**

```bash
cd Project && python -m pytest Tests/test_bank_scoring.py -v
```

Expected output:
```
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_calibration_altbau_energy_e_1900
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_neubau_energy_b_2023
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_no_price_returns_none_equity
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_confidence_all_none_is_low
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_confidence_all_known_is_high
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_kastenfenster_penalty
PASSED Tests/test_bank_scoring.py::TestComputeBankScore::test_factor_capped_at_1
7 passed
```

- [ ] **Step 5: Commit**

```bash
git add Project/Application/bank_scoring.py Tests/test_bank_scoring.py
git commit -m "feat(bank_scoring): add Belehnungswert factor + equity estimate module"
```

---

## Task 2: Add bank score fields to Listing dataclass

**Files:**
- Modify: `Project/Domain/listing.py` (append after `parent_project_id` field, currently last line)

- [ ] **Step 1: Append 5 fields to `Project/Domain/listing.py`**

At the end of the `Listing` dataclass (after `parent_project_id: Optional[int] = None`), add:

```python
    belehnungswert_factor:   Optional[float] = None
    estimated_down_pct:      Optional[float] = None  # 80% LTV standard
    estimated_down_pct_kimv: Optional[float] = None  # 90% LTV KIM-V program
    estimated_equity_eur:    Optional[int]   = None
    bank_score_confidence:   Optional[str]   = None  # "low" | "medium" | "high"
```

- [ ] **Step 2: Verify dataclass still instantiates**

```bash
cd Project && python -c "from Domain.listing import Listing; l = Listing(url='x', source='y'); print('OK', l.estimated_down_pct)"
```

Expected: `OK None`

- [ ] **Step 3: Commit**

```bash
git add Project/Domain/listing.py
git commit -m "feat(listing): add 5 bank score fields to Listing dataclass"
```

---

## Task 3: Wire bank_scoring into all 3 scrapers

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py` (line ~486, before `return listing`)
- Modify: `Project/Application/scraping/immo_kurier_scraper.py` (line ~314, before `return listing`)
- Modify: `Project/Application/scraping/derstandard_scraper.py` (lines ~694 and ~1149, before each `return listing`)

**ADR compliance:** All 3 scrapers MUST be wired. Partial wiring = silent data divergence (see edge-case 2026-05-05-extraction-gap-validation.md).

### 3a: willhaben_scraper.py

- [ ] **Step 1: Add import at top of willhaben_scraper.py**

Find the existing imports block at the top of `willhaben_scraper.py`. Add after the `from Integration.mongodb_handler import MongoDBHandler, is_valid_listing_data` line:

```python
from Application.bank_scoring import compute_bank_score
```

- [ ] **Step 2: Wire bank scoring before `return listing` (line ~486)**

Find the block starting at line ~486:
```python
            # Ensure source fields are strings, not Enum objects
            if hasattr(listing.source, 'value'):
                listing.source = listing.source.value
            if hasattr(listing.source_enum, 'value'):
                listing.source_enum = listing.source_enum.value
        
            return listing
```

Insert before the `# Ensure source fields` comment:

```python
            # Bank scoring — Belehnungswert estimate stored at scrape time
            _bank = compute_bank_score(listing)
            listing.belehnungswert_factor   = _bank.belehnungswert_factor
            listing.estimated_down_pct      = _bank.estimated_down_pct
            listing.estimated_down_pct_kimv = _bank.estimated_down_pct_kimv
            listing.estimated_equity_eur    = _bank.estimated_equity_eur
            listing.bank_score_confidence   = _bank.bank_score_confidence

```

### 3b: immo_kurier_scraper.py

- [ ] **Step 3: Add import to immo_kurier_scraper.py**

Find the existing `from Application.scraping.field_extractors import ...` block at top of `immo_kurier_scraper.py`. Add after it:

```python
from Application.bank_scoring import compute_bank_score
```

- [ ] **Step 4: Wire bank scoring before `return listing` (line ~314)**

Find the block ending `scrape_single_listing` in `immo_kurier_scraper.py`:
```python
            return listing

        except requests.exceptions.RequestException as e:
```

Insert before `return listing`:

```python
            _bank = compute_bank_score(listing)
            listing.belehnungswert_factor   = _bank.belehnungswert_factor
            listing.estimated_down_pct      = _bank.estimated_down_pct
            listing.estimated_down_pct_kimv = _bank.estimated_down_pct_kimv
            listing.estimated_equity_eur    = _bank.estimated_equity_eur
            listing.bank_score_confidence   = _bank.bank_score_confidence

```

### 3c: derstandard_scraper.py

- [ ] **Step 5: Add import to derstandard_scraper.py**

Find the existing `from Application.scraping.field_extractors import ...` block at top of `derstandard_scraper.py`. Add after it:

```python
from Application.bank_scoring import compute_bank_score
```

- [ ] **Step 6: Wire bank scoring before both `return listing` statements (lines ~694 and ~1149)**

`derstandard_scraper.py` has two return paths in `scrape_single_listing`. Find both `return listing` blocks (search for `return listing` in the file) and insert before each:

```python
            _bank = compute_bank_score(listing)
            listing.belehnungswert_factor   = _bank.belehnungswert_factor
            listing.estimated_down_pct      = _bank.estimated_down_pct
            listing.estimated_down_pct_kimv = _bank.estimated_down_pct_kimv
            listing.estimated_equity_eur    = _bank.estimated_equity_eur
            listing.bank_score_confidence   = _bank.bank_score_confidence
```

- [ ] **Step 7: Verify all 3 scrapers import bank_scoring**

```bash
cd Project && grep -l "from Application.bank_scoring import" Application/scraping/*.py
```

Expected: 3 files listed (willhaben_scraper.py, immo_kurier_scraper.py, derstandard_scraper.py)

- [ ] **Step 8: Smoke test import chain**

```bash
cd Project && python -c "
from Application.scraping.willhaben_scraper import WillhabenScraper
from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.scraping.derstandard_scraper import DerStandardScraper
print('All 3 scrapers import cleanly')
"
```

Expected: `All 3 scrapers import cleanly`

- [ ] **Step 9: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py \
        Project/Application/scraping/immo_kurier_scraper.py \
        Project/Application/scraping/derstandard_scraper.py
git commit -m "feat(scrapers): wire compute_bank_score into all 3 scrapers"
```

---

## Task 4: Neubauprojekt search URL + pagination fix

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py` (fix `scrape_search_agent_page` pagination)
- Modify: `Project/Application/main.py` (`scrape_willhaben` function)
- Modify: `config.json` (add `search_url_extra`)

### 4a: Fix URL pagination in scrape_search_agent_page

Currently `scrape_search_agent_page` builds page URLs with:
```python
url = f"{alert_url}&page={page}"
```
This breaks for clean URLs like `/neubauprojekt/wien` (produces `/neubauprojekt/wien&page=2`). Fix with proper URL construction.

- [ ] **Step 1: Add urllib.parse import to willhaben_scraper.py**

At the top of `willhaben_scraper.py`, the file imports `requests`, `json`, `time`, `re`, etc. Add:

```python
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
```

- [ ] **Step 2: Replace the page URL construction in `scrape_search_agent_page`**

Find (around line 1776):
```python
            url = f"{alert_url}&page={page}"
```

Replace with:
```python
            _parsed = urlparse(alert_url)
            _qs = parse_qs(_parsed.query, keep_blank_values=True)
            _qs['page'] = [str(page)]
            url = urlunparse(_parsed._replace(
                query=urlencode({k: v[0] for k, v in _qs.items()})
            ))
```

- [ ] **Step 3: Verify pagination URLs are correct**

```bash
cd Project && python -c "
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

def make_page_url(base, page):
    p = urlparse(base)
    qs = parse_qs(p.query, keep_blank_values=True)
    qs['page'] = [str(page)]
    return urlunparse(p._replace(query=urlencode({k: v[0] for k, v in qs.items()})))

alert = 'https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387'
neubau = 'https://www.willhaben.at/iad/immobilien/neubauprojekt/wien'
print(make_page_url(alert, 2))
print(make_page_url(neubau, 2))
"
```

Expected:
```
https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387&page=2
https://www.willhaben.at/iad/immobilien/neubauprojekt/wien?page=2
```

### 4b: Add search_url_extra to config and wire in main.py

- [ ] **Step 4: Add `search_url_extra` to `config.json`**

Find the `"willhaben"` block in `config.json`. Add `search_url_extra` alongside `search_url`:

```json
"willhaben": {
  "base_url": "https://www.willhaben.at",
  "max_pages": 12,
  "search_url": "https://www.willhaben.at/iad/immobilien/eigentumswohnung/wien",
  "search_url_extra": [
    "https://www.willhaben.at/iad/immobilien/neubauprojekt/wien"
  ],
  "timeout": 30
}
```

- [ ] **Step 5: Update `scrape_willhaben()` in `main.py` to iterate `search_url_extra`**

Find `scrape_willhaben()` in `Project/Application/main.py` (around line 318). The current body:

```python
        alert_url = config.get('alert_url', "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
        listings = scraper.scrape_search_agent_page(alert_url, max_pages=max_pages)
        logging.info(f"✅ Willhaben scraping complete: {len(listings)} matching listings found")
        return listings, "willhaben"
```

Replace with:

```python
        alert_url = config.get('alert_url', "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
        all_listings = scraper.scrape_search_agent_page(alert_url, max_pages=max_pages)

        for extra_url in willhaben_config.get('search_url_extra', []):
            logging.info(f"🏗️  Scraping extra URL: {extra_url}")
            extra_listings = scraper.scrape_search_agent_page(extra_url, max_pages=max_pages)
            all_listings.extend(extra_listings)

        logging.info(f"✅ Willhaben scraping complete: {len(all_listings)} matching listings found")
        return all_listings, "willhaben"
```

- [ ] **Step 6: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py \
        Project/Application/main.py \
        config.json
git commit -m "feat(willhaben): add neubauprojekt search URL + fix pagination for clean URLs"
```

---

## Task 5: Backfill script

**Files:**
- Create: `Project/scripts/backfill_bank_scores.py`

- [ ] **Step 1: Create `Project/scripts/backfill_bank_scores.py`**

```python
#!/usr/bin/env python3
"""Backfill Belehnungswert bank scoring fields for all existing MongoDB listings.

Idempotent: only processes listings where estimated_down_pct does not yet exist.
Run from the Project/ directory:
    python scripts/backfill_bank_scores.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Integration.mongodb_handler import MongoDBHandler
from Application.bank_scoring import compute_bank_score
from Application.helpers.utils import load_config
from Domain.listing import Listing


def main():
    config = load_config()
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    col = mongo.collection

    query = {'estimated_down_pct': {'$exists': False}}
    total = col.count_documents(query)
    print(f"Backfilling {total} listings (estimated_down_pct missing)")

    processed = updated = skipped = 0

    for doc in col.find(query):
        processed += 1
        listing = Listing(
            url=doc.get('url', ''),
            source=doc.get('source', 'unknown'),
            price_total=doc.get('price_total'),
            energy_class=doc.get('energy_class'),
            year_built=doc.get('year_built'),
            facade_renovated=doc.get('facade_renovated'),
            roof_renovated=doc.get('roof_renovated'),
            window_type=doc.get('window_type'),
        )

        bank = compute_bank_score(listing)

        if bank.estimated_down_pct is None:
            skipped += 1
            continue

        col.update_one(
            {'_id': doc['_id']},
            {'$set': {
                'belehnungswert_factor':   bank.belehnungswert_factor,
                'estimated_down_pct':      bank.estimated_down_pct,
                'estimated_down_pct_kimv': bank.estimated_down_pct_kimv,
                'estimated_equity_eur':    bank.estimated_equity_eur,
                'bank_score_confidence':   bank.bank_score_confidence,
            }}
        )
        updated += 1

        if processed % 100 == 0:
            print(f"  {processed}/{total} — {updated} updated, {skipped} skipped")

    print(f"\nDone: {processed} processed | {updated} updated | {skipped} skipped (no price_total)")
    mongo.close()


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify script runs (dry test — check import and query)**

```bash
cd Project && python -c "
import sys, os
sys.path.insert(0, '.')
from Application.bank_scoring import compute_bank_score
from Domain.listing import Listing
l = Listing(url='x', source='y', price_total=400000, energy_class='C', year_built=1990)
s = compute_bank_score(l)
print(f'factor={s.belehnungswert_factor} down={s.estimated_down_pct}% equity=EUR{s.estimated_equity_eur}')
"
```

Expected: `factor=0.92 down=26.4% equity=EUR105600` (approx — C class, 1990 no adjustments)

- [ ] **Step 3: Commit**

```bash
git add Project/scripts/backfill_bank_scores.py
git commit -m "feat(scripts): add backfill_bank_scores.py migration script"
```

---

## Task 6: TypeScript types

**Files:**
- Modify: `dashboard/lib/types.ts`

- [ ] **Step 1: Add bank score fields to `ListingBase` and `ListingDetail`**

Open `dashboard/lib/types.ts`. Add to `ListingBase` (after `price_is_estimated?: boolean;`):

```typescript
  estimated_down_pct?: number | null;
  estimated_equity_eur?: number | null;
  bank_score_confidence?: string | null;
```

Add to `ListingDetail` (after `url_is_valid?: boolean;`):

```typescript
  estimated_down_pct_kimv?: number | null;
  belehnungswert_factor?: number | null;
```

Full updated `ListingBase`:

```typescript
export interface ListingBase {
  _id: string;
  title: string | null;
  url: string;
  source_enum: string;
  bezirk: string | null;
  price_total: number | null;
  area_m2: number | null;
  rooms: number | null;
  score: number | null;
  processed_at: number | null;
  image_url: string | null;
  price_is_estimated?: boolean;
  estimated_down_pct?: number | null;
  estimated_equity_eur?: number | null;
  bank_score_confidence?: string | null;
}
```

Full updated `ListingDetail`:

```typescript
export interface ListingDetail extends ListingBase {
  address: string | null;
  year_built: number | null;
  floor: number | null;
  condition: string | null;
  heating: string | null;
  parking: string | null;
  betriebskosten: number | null;
  energy_class: string | null;
  hwb_value: number | null;
  fgee_value: number | null;
  rooms: number | null;
  calculated_monatsrate: number | null;
  total_monthly_cost: number | null;
  ubahn_walk_minutes: number | null;
  school_walk_minutes: number | null;
  infrastructure_distances: Record<string, unknown>;
  score_breakdown?: Record<string, number>;
  url_is_valid?: boolean;
  coordinate_source?: CoordinateSource;
  landmark_hint?: string | null;
  estimated_down_pct_kimv?: number | null;
  belehnungswert_factor?: number | null;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/types.ts
git commit -m "feat(types): add bank score fields to ListingBase and ListingDetail"
```

---

## Task 7: EquityBadge component

**Files:**
- Create: `dashboard/components/EquityBadge.tsx`

Pattern: follow `ScoreBadge.tsx` structure (same repo, `dashboard/components/ScoreBadge.tsx`).

- [ ] **Step 1: Create `dashboard/components/EquityBadge.tsx`**

```tsx
interface EquityBadgeProps {
  downPct: number | null | undefined;
  equityEur: number | null | undefined;
  confidence: string | null | undefined;
}

export function EquityBadge({ downPct, equityEur, confidence }: EquityBadgeProps) {
  if (confidence === 'low') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-gray-500 bg-gray-100">
        ? equity
      </span>
    );
  }

  if (downPct == null) return null;

  const pctRounded = Math.round(downPct);
  const eurK = equityEur != null ? Math.round(equityEur / 1000) : null;
  const label = eurK != null ? `~${pctRounded}% (~€${eurK}k)` : `~${pctRounded}%`;

  let colorClass: string;
  if (downPct <= 15) {
    colorClass = 'text-green-800 bg-green-100';
  } else if (downPct <= 25) {
    colorClass = 'text-yellow-800 bg-yellow-100';
  } else {
    colorClass = 'text-orange-800 bg-orange-100';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/components/EquityBadge.tsx
git commit -m "feat(dashboard): add EquityBadge component"
```

---

## Task 8: Wire EquityBadge into ListingCard

**Files:**
- Modify: `dashboard/components/ListingCard.tsx`

- [ ] **Step 1: Add EquityBadge import and render below price**

In `ListingCard.tsx`, add import at top:

```tsx
import { EquityBadge } from './EquityBadge';
```

Find the price line:
```tsx
        <p className="font-bold text-heading text-base mb-1">
          {formatPrice(listing.price_total, listing.price_is_estimated)}
        </p>
```

Add EquityBadge immediately after it:

```tsx
        <p className="font-bold text-heading text-base mb-1">
          {formatPrice(listing.price_total, listing.price_is_estimated)}
        </p>
        <div className="mb-1">
          <EquityBadge
            downPct={listing.estimated_down_pct}
            equityEur={listing.estimated_equity_eur}
            confidence={listing.bank_score_confidence}
          />
        </div>
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/ListingCard.tsx
git commit -m "feat(dashboard): show EquityBadge on listing cards"
```

---

## Task 9: Filter state + logic in page.tsx

**Files:**
- Modify: `dashboard/app/dashboard/page.tsx`

- [ ] **Step 1: Add `maxPrice` and `showUnfinanceable` state and client-side filter logic**

In `dashboard/app/dashboard/page.tsx`, add two new state variables after the existing ones:

```tsx
  const [maxPrice, setMaxPrice] = useState('500000');
  const [showUnfinanceable, setShowUnfinanceable] = useState(false);
```

Add a `filteredListings` derived value after `fetchListings` function:

```tsx
  const filteredListings = listings.filter((l) => {
    if (maxPrice && l.price_total != null && l.price_total > Number(maxPrice)) return false;
    if (
      !showUnfinanceable &&
      l.estimated_down_pct != null &&
      l.estimated_down_pct > 30 &&
      l.bank_score_confidence !== 'low'
    ) return false;
    return true;
  });
```

Replace `listings.map(...)` in the grid render with `filteredListings.map(...)`:

```tsx
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredListings.map((l) => (
              <ListingCard key={l._id} listing={l} onClick={setSelectedId} />
            ))}
          </div>
```

Pass the new props to `FilterBar` and `FilterDrawer`:

```tsx
          <FilterBar
            minScore={minScore}
            onMinScoreChange={setMinScore}
            district={district}
            onDistrictChange={setDistrict}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={setSortBy}
            maxPrice={maxPrice}
            onMaxPriceChange={setMaxPrice}
            showUnfinanceable={showUnfinanceable}
            onShowUnfinanceableChange={setShowUnfinanceable}
          />
```

```tsx
      <FilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        district={district}
        onDistrictChange={setDistrict}
        onRefresh={fetchListings}
        sortBy={sortBy}
        onSortChange={setSortBy}
        maxPrice={maxPrice}
        onMaxPriceChange={setMaxPrice}
        showUnfinanceable={showUnfinanceable}
        onShowUnfinanceableChange={setShowUnfinanceable}
      />
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/dashboard/page.tsx
git commit -m "feat(dashboard): add maxPrice + showUnfinanceable filter state"
```

---

## Task 10: FilterBar and FilterDrawer UI controls

**Files:**
- Modify: `dashboard/components/FilterBar.tsx`
- Modify: `dashboard/components/FilterDrawer.tsx`

### 10a: FilterBar (desktop)

- [ ] **Step 1: Update FilterBarProps and add controls to FilterBar.tsx**

Replace the entire `FilterBar.tsx` content:

```tsx
'use client';

import React from 'react';

const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'price_asc', label: 'Price (low to high)' },
  { value: 'price_desc', label: 'Price (high to low)' },
  { value: 'date_desc', label: 'Newest first' },
  { value: 'area_desc', label: 'Largest first' },
] as const;

export type SortOption = typeof SORT_OPTIONS[number]['value'];

interface FilterBarProps {
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy?: SortOption;
  onSortChange?: (sort: SortOption) => void;
  maxPrice: string;
  onMaxPriceChange: (v: string) => void;
  showUnfinanceable: boolean;
  onShowUnfinanceableChange: (v: boolean) => void;
}

export function FilterBar({
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh, sortBy, onSortChange,
  maxPrice, onMaxPriceChange,
  showUnfinanceable, onShowUnfinanceableChange,
}: FilterBarProps) {
  const effectiveSort = sortBy ?? 'score_desc';

  return (
    <div className="hidden md:flex flex-wrap gap-3 mb-6 items-center">
      <div className="flex items-center gap-2 ml-auto">
        <label className="text-sm font-medium text-gray-700">Min Score</label>
        <input
          type="number" min="0" max="100" value={minScore}
          onChange={(e) => onMinScoreChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Max Price €</label>
        <input
          type="number" min="0" step="10000" value={maxPrice}
          onChange={(e) => onMaxPriceChange(e.target.value)}
          className="w-28 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">District</label>
        <input
          type="text" placeholder="e.g. 02" value={district}
          onChange={(e) => onDistrictChange(e.target.value)}
          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <button
        onClick={onRefresh}
        className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
      >
        Refresh
      </button>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Sort</label>
        <select
          value={effectiveSort}
          onChange={(e) => onSortChange?.(e.target.value as SortOption)}
          className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={showUnfinanceable}
          onChange={(e) => onShowUnfinanceableChange(e.target.checked)}
          className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm font-medium text-gray-700">Show unfinanceable</span>
      </label>
    </div>
  );
}
```

### 10b: FilterDrawer (mobile)

- [ ] **Step 2: Update FilterDrawerProps and add controls to FilterDrawer.tsx**

Replace `FilterDrawer.tsx` content:

```tsx
'use client';

import React, { useState, useEffect } from 'react';
import { SortOption } from './FilterBar';

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  minScore: string;
  onMinScoreChange: (v: string) => void;
  district: string;
  onDistrictChange: (v: string) => void;
  onRefresh: () => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
  maxPrice: string;
  onMaxPriceChange: (v: string) => void;
  showUnfinanceable: boolean;
  onShowUnfinanceableChange: (v: boolean) => void;
}

export function FilterDrawer({
  open, onClose,
  minScore, onMinScoreChange,
  district, onDistrictChange,
  onRefresh, sortBy, onSortChange,
  maxPrice, onMaxPriceChange,
  showUnfinanceable, onShowUnfinanceableChange,
}: FilterDrawerProps) {
  const [localMinScore, setLocalMinScore] = useState(minScore);
  const [localDistrict, setLocalDistrict] = useState(district);
  const [localSortBy, setLocalSortBy] = useState(sortBy);
  const [localMaxPrice, setLocalMaxPrice] = useState(maxPrice);
  const [localShowUnfinanceable, setLocalShowUnfinanceable] = useState(showUnfinanceable);

  useEffect(() => {
    setLocalMinScore(minScore);
    setLocalDistrict(district);
    setLocalSortBy(sortBy);
    setLocalMaxPrice(maxPrice);
    setLocalShowUnfinanceable(showUnfinanceable);
  }, [minScore, district, sortBy, maxPrice, showUnfinanceable]);

  if (!open) return null;

  const handleApply = () => {
    onMinScoreChange(localMinScore);
    onDistrictChange(localDistrict);
    onSortChange(localSortBy);
    onMaxPriceChange(localMaxPrice);
    onShowUnfinanceableChange(localShowUnfinanceable);
    onRefresh();
    onClose();
  };

  const handleReset = () => {
    setLocalMinScore('0');
    setLocalDistrict('');
    setLocalSortBy('score_desc');
    setLocalMaxPrice('500000');
    setLocalShowUnfinanceable(false);
  };

  return (
    <div className="fixed inset-0 z-[200] flex flex-col">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative mt-auto bg-white rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.1)] flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-lg font-semibold text-heading">Filters</h2>
          <button
            onClick={onClose}
            className="w-11 h-11 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            aria-label="Close filters"
          >
            <svg className="w-5 h-5 text-text" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Minimum Score</label>
            <input
              type="number" min="0" max="100" value={localMinScore}
              onChange={(e) => setLocalMinScore(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Max Price €</label>
            <input
              type="number" min="0" step="10000" value={localMaxPrice}
              onChange={(e) => setLocalMaxPrice(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">District</label>
            <input
              type="text" placeholder="e.g. 02" value={localDistrict}
              onChange={(e) => setLocalDistrict(e.target.value)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Sort By</label>
            <select
              value={localSortBy}
              onChange={(e) => setLocalSortBy(e.target.value as SortOption)}
              className="w-full rounded-lg border border-border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="score_desc">Score (high to low)</option>
              <option value="price_asc">Price (low to high)</option>
              <option value="price_desc">Price (high to low)</option>
              <option value="date_desc">Newest first</option>
              <option value="area_desc">Largest first</option>
            </select>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={localShowUnfinanceable}
              onChange={(e) => setLocalShowUnfinanceable(e.target.checked)}
              className="w-5 h-5 rounded border-gray-300 text-accent focus:ring-accent"
            />
            <span className="text-sm font-medium text-text">Show unfinanceable listings</span>
          </label>
        </div>

        <div className="flex gap-3 px-5 py-4 border-t border-border shrink-0">
          <button
            onClick={handleReset}
            className="flex-1 h-12 rounded-lg border border-border text-text font-medium hover:bg-gray-50 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            className="flex-1 h-12 rounded-lg bg-accent text-white font-semibold hover:opacity-90 transition-opacity"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/FilterBar.tsx dashboard/components/FilterDrawer.tsx
git commit -m "feat(dashboard): add maxPrice input + showUnfinanceable toggle to FilterBar + FilterDrawer"
```

---

## Task 11: Financing section in ListingDetail modal

**Files:**
- Modify: `dashboard/components/ListingDetail.tsx`

- [ ] **Step 1: Add financing section to the detail grid**

In `ListingDetail.tsx`, find the grid of property details ending with:
```tsx
                {listing.ubahn_walk_minutes != null && <div><span className="font-medium">U-Bahn:</span> {listing.ubahn_walk_minutes} min</div>}
              </div>
```

Add a new section after the closing `</div>` of the grid and before the `infrastructure_distances` block:

```tsx
              {listing.estimated_down_pct != null && (
                <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <h3 className="font-semibold text-gray-800 mb-3">Financing (estimated)</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="font-medium text-gray-600">Standard (80% LTV):</span>
                      <span className="ml-2 font-semibold">
                        ~{Math.round(listing.estimated_down_pct)}%
                        {listing.estimated_equity_eur != null && (
                          <span className="text-gray-500 font-normal">
                            {' '}(~€{Math.round(listing.estimated_equity_eur / 1000)}k equity)
                          </span>
                        )}
                      </span>
                    </div>
                    {listing.estimated_down_pct_kimv != null && (
                      <div>
                        <span className="font-medium text-gray-600">KIM-V (90% LTV):</span>
                        <span className="ml-2 font-semibold">
                          ~{Math.round(listing.estimated_down_pct_kimv)}%
                        </span>
                      </div>
                    )}
                    {listing.belehnungswert_factor != null && (
                      <div>
                        <span className="font-medium text-gray-600">Belehnungswert est.:</span>
                        <span className="ml-2">~{Math.round(listing.belehnungswert_factor * 100)}% of asking</span>
                      </div>
                    )}
                    {listing.bank_score_confidence && (
                      <div>
                        <span className="font-medium text-gray-600">Confidence:</span>
                        <span className={`ml-2 ${
                          listing.bank_score_confidence === 'high' ? 'text-green-700' :
                          listing.bank_score_confidence === 'medium' ? 'text-yellow-700' :
                          'text-gray-500'
                        }`}>
                          {listing.bank_score_confidence}
                        </span>
                      </div>
                    )}
                    {listing.energy_class && (
                      <div className="col-span-2 text-xs text-gray-500 mt-1">
                        Based on: Energy {listing.energy_class}
                        {listing.hwb_value != null ? ` (HWB ${listing.hwb_value})` : ''}
                      </div>
                    )}
                  </div>
                </div>
              )}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/ListingDetail.tsx
git commit -m "feat(dashboard): add Financing section to ListingDetail modal"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `bank_scoring.py` pure function with full formula — Task 1
- ✅ 5 new fields on `Listing` — Task 2
- ✅ All 3 scrapers wired (ADR compliance) — Task 3
- ✅ Willhaben neubauprojekt search URL + pagination fix — Task 4
- ✅ `search_url_extra` in config + `main.py` loop — Task 4
- ✅ Backfill script, idempotent — Task 5
- ✅ TypeScript types — Task 6
- ✅ `EquityBadge` following `ScoreBadge` pattern — Task 7
- ✅ EquityBadge wired into `ListingCard` — Task 8
- ✅ Filter state + `filteredListings` in `page.tsx` — Task 9
- ✅ `FilterBar` + `FilterDrawer` controls — Task 10
- ✅ `ListingDetail` financing section — Task 11
- ✅ Confidence=low always shown (filter logic in Task 9: `bank_score_confidence !== 'low'` guard)
- ✅ Year_built double-penalty documented in `bank_scoring.py` comment

**Type consistency:**
- `BankScore` fields match `Listing` field names exactly: `belehnungswert_factor`, `estimated_down_pct`, `estimated_down_pct_kimv`, `estimated_equity_eur`, `bank_score_confidence`
- TypeScript fields match Python names exactly (snake_case throughout)
- `compute_bank_score` called consistently in all 3 scrapers with same assignment pattern

**Calibration test** (verifiable with Task 1 tests):
`energy_class='E', year_built=1900, price=560000` → `factor=0.70` → `estimated_down_pct=44.0` ✅
