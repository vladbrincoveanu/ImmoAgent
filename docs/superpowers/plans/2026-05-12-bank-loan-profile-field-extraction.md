# Bank Loan Ready Profile + Field Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bank_loan_ready` buyer profile scoring Vienna listings against Austrian bank Belehnungswert criteria, plus extract 4 new bool fields (lift, facade, parifizierung, roof) from listing description text in all 3 scrapers.

**Architecture:** New `field_extractors.py` module provides pure-text regex extraction (two-pass: negatives first, then positives). Four new `Optional[bool]` fields added to `Listing` dataclass. New buyer profile uses existing scoring engine with reweighted criteria. All 3 scrapers wired to call extractors after existing field population.

**Tech Stack:** Python, `re`, existing `BeautifulSoup` soup objects (all 3 scrapers already have `soup` available), `unittest`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `Project/Domain/listing.py` | Modify | +4 `Optional[bool]` fields |
| `Project/Application/scoring.py` | Modify | +4 normalization range entries |
| `Project/Application/buyer_profiles.py` | Modify | +profile dict + `BANK_LOAN_READY` enum |
| `Project/Application/scraping/field_extractors.py` | **Create** | 4 extraction functions, two-pass negation |
| `Tests/test_field_extractors.py` | **Create** | 16 unit tests (4 per function) |
| `Project/Application/scraping/willhaben_scraper.py` | Modify | Wire field_extractors after line 365 |
| `Project/Application/scraping/immo_kurier_scraper.py` | Modify | Wire field_extractors after line 261 |
| `Project/Application/scraping/derstandard_scraper.py` | Modify | Wire field_extractors after line 672 (main path only) |

---

## Task 1: Add 4 fields to Listing dataclass

**Files:**
- Modify: `Project/Domain/listing.py`

- [ ] **Step 1: Read current end of listing.py to confirm anchor**

  ```bash
  tail -10 Project/Domain/listing.py
  ```
  Expected: last 2 lines are `street_view: Optional[int] = None` and `orientation: Optional[int] = None`

- [ ] **Step 2: Add 4 new fields after `orientation`**

  Append to end of `Listing` dataclass (after `orientation: Optional[int] = None`):
  ```python
      lift_present: Optional[bool] = None
      facade_renovated: Optional[bool] = None
      parifizierung_complete: Optional[bool] = None
      roof_renovated: Optional[bool] = None
  ```

- [ ] **Step 3: Verify no import error**

  ```bash
  cd Project && python -c "from Domain.listing import Listing; l = Listing(url='x', source='test'); print(l.lift_present, l.facade_renovated, l.parifizierung_complete, l.roof_renovated)"
  ```
  Expected: `None None None None`

- [ ] **Step 4: Commit**

  ```bash
  git add Project/Domain/listing.py
  git commit -m "feat(listing): add lift_present, facade_renovated, parifizierung_complete, roof_renovated fields"
  ```

---

## Task 2: Add normalization ranges to scoring engine

**Files:**
- Modify: `Project/Application/scoring.py`

- [ ] **Step 1: Find insertion point in NORMALIZATION_RANGES**

  ```bash
  grep -n "orientation\|NORMALIZATION_RANGES" Project/Application/scoring.py | head -10
  ```
  Expected: `'orientation': {'min_val': 0, 'max_val': 100, 'direction': 'higher_is_better'},` is the last entry.

- [ ] **Step 2: Add 4 entries after the `orientation` entry**

  Insert after `'orientation': {'min_val': 0, 'max_val': 100, 'direction': 'higher_is_better'},`:
  ```python
      'lift_present':           {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
      'facade_renovated':       {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
      'parifizierung_complete': {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
      'roof_renovated':         {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
  ```

- [ ] **Step 3: Verify normalization works for bool inputs**

  ```bash
  cd Project && python -c "
  from Application.scoring import normalize_value
  print(normalize_value('lift_present', True))   # expect 100.0
  print(normalize_value('lift_present', False))  # expect 0.0
  print(normalize_value('lift_present', None))   # expect 0.0
  print(normalize_value('facade_renovated', True)) # expect 100.0
  "
  ```
  Expected: `100.0`, `0.0`, `0.0`, `100.0`

- [ ] **Step 4: Commit**

  ```bash
  git add Project/Application/scoring.py
  git commit -m "feat(scoring): add normalization ranges for bank_loan_ready fields"
  ```

---

## Task 3: Write failing tests for field_extractors

**Files:**
- Create: `Tests/test_field_extractors.py`

- [ ] **Step 1: Create test file**

  Create `Tests/test_field_extractors.py`:
  ```python
  #!/usr/bin/env python3
  import sys
  import os
  sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

  import unittest
  from Application.scraping.field_extractors import (
      extract_lift_present,
      extract_facade_renovated,
      extract_parifizierung_complete,
      extract_roof_renovated,
  )


  class TestExtractLiftPresent(unittest.TestCase):
      def test_positive_aufzug(self):
          self.assertTrue(extract_lift_present("aufzug vorhanden im haus"))

      def test_positive_fahrstuhl(self):
          self.assertTrue(extract_lift_present("fahrstuhl im gebäude"))

      def test_negative_kein_aufzug(self):
          self.assertFalse(extract_lift_present("kein aufzug vorhanden"))

      def test_absent_returns_none(self):
          self.assertIsNone(extract_lift_present("schöne 3-zimmer-wohnung mit parkett"))


  class TestExtractFacadeRenovated(unittest.TestCase):
      def test_positive_fassadensanierung(self):
          self.assertTrue(extract_facade_renovated("fassadensanierung 2019 abgeschlossen"))

      def test_positive_sanierte_fassade(self):
          self.assertTrue(extract_facade_renovated("sanierte fassade und neue fenster"))

      def test_negative_keine_fassadensanierung(self):
          self.assertFalse(extract_facade_renovated("keine fassadensanierung erfolgt"))

      def test_absent_returns_none(self):
          self.assertIsNone(extract_facade_renovated("günstige wohnung in wien kaufen"))


  class TestExtractParifizierungComplete(unittest.TestCase):
      def test_positive_abgeschlossen(self):
          self.assertTrue(extract_parifizierung_complete("parifizierung abgeschlossen"))

      def test_positive_bereits_parifiziert(self):
          self.assertTrue(extract_parifizierung_complete("bereits parifiziert"))

      def test_negative_ausstehend(self):
          self.assertFalse(extract_parifizierung_complete("parifizierung ausstehend"))

      def test_negative_nicht_parifiziert(self):
          self.assertFalse(extract_parifizierung_complete("nicht parifiziert"))

      def test_absent_returns_none(self):
          self.assertIsNone(extract_parifizierung_complete("moderne wohnung mit balkon"))


  class TestExtractRoofRenovated(unittest.TestCase):
      def test_positive_dachsanierung(self):
          self.assertTrue(extract_roof_renovated("dachsanierung 2020 durchgeführt"))

      def test_positive_saniertes_dach(self):
          self.assertTrue(extract_roof_renovated("saniertes dach und neue fenster"))

      def test_negative_keine_dachsanierung(self):
          self.assertFalse(extract_roof_renovated("keine dachsanierung erfolgt"))

      def test_absent_returns_none(self):
          self.assertIsNone(extract_roof_renovated("ruhige lage, u-bahn nähe"))


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run tests — verify they fail**

  ```bash
  cd Tests && python test_field_extractors.py 2>&1 | head -20
  ```
  Expected: `ModuleNotFoundError: No module named 'Application.scraping.field_extractors'`

---

## Task 4: Implement field_extractors.py

**Files:**
- Create: `Project/Application/scraping/field_extractors.py`

- [ ] **Step 1: Create the module**

  Create `Project/Application/scraping/field_extractors.py`:
  ```python
  """
  Extract boolean property features from listing full-page text.
  Two-pass approach: check negative patterns first, then positive.
  Input: soup.get_text().lower() — full page text, pre-lowercased.
  """
  import re
  from typing import Optional


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
  ```

- [ ] **Step 2: Run tests — verify all pass**

  ```bash
  cd Tests && python test_field_extractors.py -v 2>&1
  ```
  Expected: `16 tests, 0 failures, 0 errors` — all pass.

- [ ] **Step 3: Commit**

  ```bash
  git add Project/Application/scraping/field_extractors.py Tests/test_field_extractors.py
  git commit -m "feat(extraction): add field_extractors module with 16 tests — lift, facade, parifizierung, roof"
  ```

---

## Task 5: Add bank_loan_ready profile and enum

**Files:**
- Modify: `Project/Application/buyer_profiles.py`

- [ ] **Step 1: Add BANK_LOAN_READY to BuyerPersona enum**

  In `BuyerPersona` enum, add after `PRIME_NEW_BUILD = 'prime_new_build'`:
  ```python
      BANK_LOAN_READY = 'bank_loan_ready'
  ```

- [ ] **Step 2: Add profile dict entry**

  In `BUYER_PROFILES` dict, add after the `'prime_new_build'` entry:
  ```python
      'bank_loan_ready': {
          'name': 'Bank Loan Ready 🏦',
          'description': 'Scores based on Austrian bank Belehnungswert criteria. Missing fields score 0 — transparency rewarded.',
          'weights': {
              'price_per_m2':           0.13,
              'ubahn_walk_minutes':     0.12,
              'renovation_needed_rating': 0.12,
              'hwb_value':              0.10,
              'parifizierung_complete': 0.10,
              'potential_growth_rating': 0.08,
              'facade_renovated':       0.07,
              'year_built':             0.09,
              'roof_renovated':         0.04,
              'lift_present':           0.03,
              'area_m2':                0.03,
              'floor_level':            0.03,
              'school_walk_minutes':    0.02,
              'balcony_terrace':        0.02,
              'rooms':                  0.02,
          }
      },
  ```

- [ ] **Step 3: Verify weights sum to 1.0**

  ```bash
  cd Project && python -c "
  from Application.buyer_profiles import BUYER_PROFILES, validate_profile_weights
  p = BUYER_PROFILES['bank_loan_ready']
  ok = validate_profile_weights(p['weights'])
  total = sum(p['weights'].values())
  print(f'Sum={total:.2f}, valid={ok}')
  "
  ```
  Expected: `Sum=1.00, valid=True`

- [ ] **Step 4: Verify enum works**

  ```bash
  cd Project && python -c "
  from Application.buyer_profiles import BuyerPersona
  p = BuyerPersona.from_value('bank_loan_ready')
  print(p)
  "
  ```
  Expected: `BuyerPersona.BANK_LOAN_READY`

- [ ] **Step 5: Commit**

  ```bash
  git add Project/Application/buyer_profiles.py
  git commit -m "feat(profiles): add bank_loan_ready buyer profile and BuyerPersona enum member"
  ```

---

## Task 6: Wire extractors into willhaben_scraper.py

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py`

- [ ] **Step 1: Add import at top of file**

  After the existing imports (around line 17), add:
  ```python
  from Application.scraping.field_extractors import (
      extract_lift_present, extract_facade_renovated,
      extract_parifizierung_complete, extract_roof_renovated,
  )
  ```

- [ ] **Step 2: Add extraction calls after the prime_new_build block**

  Find this block (around line 361–365):
  ```python
          # New fields for prime_new_build profile
          listing.street_view = self.extract_street_view(soup)
          listing.orientation = self.extract_orientation(soup)
          listing.floor_level = self.extract_floor_level(soup)
          listing.balcony_terrace = self.extract_balcony_terrace(soup)
  ```
  Insert immediately after:
  ```python

          # New fields for bank_loan_ready profile
          _full_text = soup.get_text().lower()
          listing.lift_present = extract_lift_present(_full_text)
          listing.facade_renovated = extract_facade_renovated(_full_text)
          listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
          listing.roof_renovated = extract_roof_renovated(_full_text)
  ```

- [ ] **Step 3: Verify no import error**

  ```bash
  cd Project && python -c "from Application.scraping.willhaben_scraper import WillhabenScraper; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 4: Commit**

  ```bash
  git add Project/Application/scraping/willhaben_scraper.py
  git commit -m "feat(willhaben): wire field_extractors for bank_loan_ready fields"
  ```

---

## Task 7: Wire extractors into immo_kurier_scraper.py

**Files:**
- Modify: `Project/Application/scraping/immo_kurier_scraper.py`

- [ ] **Step 1: Add import at top of file**

  After existing imports (around line 14), add:
  ```python
  from Application.scraping.field_extractors import (
      extract_lift_present, extract_facade_renovated,
      extract_parifizierung_complete, extract_roof_renovated,
  )
  ```

- [ ] **Step 2: Add extraction calls after the prime_new_build block**

  Find this block (around line 258–261):
  ```python
          # New fields for prime_new_build profile
          listing.street_view = self.extract_street_view(soup)
          listing.orientation = self.extract_orientation(soup)
          listing.floor_level = self.extract_floor_level(soup)
          listing.balcony_terrace = self.extract_balcony_terrace(soup)
  ```
  Insert immediately after:
  ```python

          # New fields for bank_loan_ready profile
          _full_text = soup.get_text().lower()
          listing.lift_present = extract_lift_present(_full_text)
          listing.facade_renovated = extract_facade_renovated(_full_text)
          listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
          listing.roof_renovated = extract_roof_renovated(_full_text)
  ```

- [ ] **Step 3: Verify no import error**

  ```bash
  cd Project && python -c "from Application.scraping.immo_kurier_scraper import ImmoKurierScraper; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 4: Commit**

  ```bash
  git add Project/Application/scraping/immo_kurier_scraper.py
  git commit -m "feat(immo_kurier): wire field_extractors for bank_loan_ready fields"
  ```

---

## Task 8: Wire extractors into derstandard_scraper.py

**Files:**
- Modify: `Project/Application/scraping/derstandard_scraper.py`

Note: DerStandard has two `return listing` paths. Add extraction to the **main JSON path only** (around line 672), consistent with how `prime_new_build` fields are handled. The fallback HTML path already omits those fields.

- [ ] **Step 1: Add import at top of file**

  After existing imports (around line 18), add:
  ```python
  from Application.scraping.field_extractors import (
      extract_lift_present, extract_facade_renovated,
      extract_parifizierung_complete, extract_roof_renovated,
  )
  ```

- [ ] **Step 2: Find exact anchor in main JSON path**

  ```bash
  grep -n "balcony_terrace\|validate_listing_data" Project/Application/scraping/derstandard_scraper.py | head -10
  ```
  Expected: lines showing `listing.balcony_terrace = self.extract_balcony_terrace(soup)` around 672, followed shortly by `if self.validate_listing_data(listing):`

- [ ] **Step 3: Add extraction calls between balcony_terrace and validate_listing_data**

  Find this block:
  ```python
              # New fields for prime_new_build profile
              listing.street_view = self.extract_street_view(soup)
              listing.orientation = self.extract_orientation(soup)
              listing.floor_level = self.extract_floor_level(soup)
              listing.balcony_terrace = self.extract_balcony_terrace(soup)

              # Validate that we have essential data
              if self.validate_listing_data(listing):
  ```
  Insert between them:
  ```python

              # New fields for bank_loan_ready profile
              _full_text = soup.get_text().lower()
              listing.lift_present = extract_lift_present(_full_text)
              listing.facade_renovated = extract_facade_renovated(_full_text)
              listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
              listing.roof_renovated = extract_roof_renovated(_full_text)

  ```

- [ ] **Step 4: Verify no import error**

  ```bash
  cd Project && python -c "from Application.scraping.derstandard_scraper import DerStandardScraper; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 5: Commit**

  ```bash
  git add Project/Application/scraping/derstandard_scraper.py
  git commit -m "feat(derstandard): wire field_extractors for bank_loan_ready fields"
  ```

---

## Task 9: ADR compliance check + integration test

**Files:** None

- [ ] **Step 1: Verify all 3 scrapers call field_extractors**

  ```bash
  grep -l "extract_lift_present" Project/Application/scraping/*.py
  ```
  Expected: 3 files listed — `derstandard_scraper.py`, `immo_kurier_scraper.py`, `willhaben_scraper.py`. If fewer than 3, stop — a scraper was missed.

- [ ] **Step 2: Run all field extractor tests**

  ```bash
  cd Tests && python test_field_extractors.py -v
  ```
  Expected: `16 tests, 0 failures`

- [ ] **Step 3: Smoke test — profile loads and scores**

  ```bash
  cd Project && python -c "
  from Application.scoring import set_buyer_profile, score_apartment
  set_buyer_profile('bank_loan_ready')
  listing = {
      'price_per_m2': 5500,
      'ubahn_walk_minutes': 4,
      'hwb_value': 80,
      'year_built': 1970,
      'renovation_needed_rating': 2,
      'potential_growth_rating': 3,
      'facade_renovated': True,
      'parifizierung_complete': True,
      'lift_present': None,
      'roof_renovated': None,
      'area_m2': 75,
      'floor_level': 2,
      'balcony_terrace': False,
      'rooms': 3,
      'school_walk_minutes': 8,
  }
  score, breakdown = score_apartment(listing)
  print(f'Score: {score:.1f}')
  assert score > 0, 'Score must be positive'
  listing_no_extras = {k: v for k, v in listing.items() if k not in ('facade_renovated', 'parifizierung_complete')}
  score2, _ = score_apartment(listing_no_extras)
  print(f'Score without facade/parifizierung: {score2:.1f}')
  assert score > score2, 'facade_renovated+parifizierung_complete must increase score'
  print('All assertions pass')
  "
  ```
  Expected: Two scores printed, first > second, `All assertions pass`.

- [ ] **Step 4: Verify run_top5.py accepts the new profile**

  `run_top5.py` has no `--dry-run` flag. Test profile loading separately:

  ```bash
  cd Project && python -c "
  from Application.buyer_profiles import BuyerPersona, get_profile
  from Application.scoring import set_buyer_profile
  p = BuyerPersona.from_value('bank_loan_ready')
  profile = get_profile(p)
  set_buyer_profile('bank_loan_ready')
  print(f'Profile loaded: {profile[\"name\"]}')
  print(f'Criteria count: {len(profile[\"weights\"])}')
  "
  ```
  Expected: `Profile loaded: Bank Loan Ready 🏦`, `Criteria count: 15`

  If MongoDB is available locally, full end-to-end:
  ```bash
  cd Project && python run_top5.py --buyer-profile=bank_loan_ready --limit=3 2>&1 | tail -30
  ```

- [ ] **Step 5: Final commit if any cleanup needed**

  If no changes needed, skip. Otherwise:
  ```bash
  git add -p
  git commit -m "fix: cleanup after integration test"
  ```

---

## Success Criteria Checklist

- [ ] `python -c "from Domain.listing import Listing; l=Listing(url='x',source='t'); print(l.lift_present)"` → `None`
- [ ] `python -c "from Application.scoring import normalize_value; print(normalize_value('facade_renovated', True))"` → `100.0`
- [ ] `python -c "from Application.buyer_profiles import BUYER_PROFILES; print(sum(BUYER_PROFILES['bank_loan_ready']['weights'].values()))"` → `1.0`
- [ ] `cd Tests && python test_field_extractors.py` → `16 tests, 0 failures`
- [ ] `grep -l "extract_lift_present" Project/Application/scraping/*.py | wc -l` → `3`
- [ ] Score with facade_renovated=True > score without it (smoke test Step 3)
