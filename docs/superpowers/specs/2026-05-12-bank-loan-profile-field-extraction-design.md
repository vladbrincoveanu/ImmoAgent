# Design: Bank Loan Ready Profile + Field Extraction

**Date:** 2026-05-12  
**Status:** Approved  
**Phase:** 1 of 2 (Phase 2 = new scrapers for immo.at / wohnnet.at — separate session)

---

## Goal

Add a `bank_loan_ready` buyer profile that scores Vienna listings against Austrian bank Belehnungswert criteria. Extend the Listing domain model with 4 new extractable fields and wire extraction into all 3 existing scrapers.

---

## Background

Austrian banks score properties on a ~100-point internal model before setting LTV. A listing scoring ~54/100 triggers 50% equity demands instead of standard 20%. The 7 scoring categories are: Location, Building Substance, Apartment Condition, Energy, Features, Legal/Financial, Pricing. The current scoring engine covers Location, Energy, Condition, and Pricing via existing fields. This spec adds Building Substance (facade, roof) and Legal (parifizierung, lift) coverage.

---

## Decisions Made (Grill-Me)

| Decision | Choice | Reason |
|---|---|---|
| New fields vs. proxy weights | New fields + extraction | 40% of bank score uncovered by existing fields |
| Missing field behavior | Penalize (score 0) | Banks penalize missing documentation |
| Hard filters on bank profile | No — soft weighting only | Hard filters belong in CLI flags, not profile definitions |
| New scrapers (immo.at, wohnnet.at) | Deferred to Phase 2 | 1–2 week scope; Phase 1 delivers value immediately |
| facade/roof weight vs. bias risk | Reduced weights | 21% on potentially-silent fields creates systematic bias; redistributed |

---

## New Fields

### Module: Domain/listing.py additions

- **Responsibility:** 4 new Optional[bool] fields on the Listing dataclass
- **Interface:** Added alongside existing bool fields (balcony_terrace, street_view)
- **Dependencies:** None
- **Size target:** +4 lines

```python
lift_present: Optional[bool] = None          # Aufzug vorhanden im Haus
facade_renovated: Optional[bool] = None      # Fassadensanierung nachweislich erfolgt
parifizierung_complete: Optional[bool] = None # Parifizierung abgeschlossen
roof_renovated: Optional[bool] = None        # Dachsanierung abgeschlossen
```

Scoring behavior: `True` → 1 → 100 pts, `False` → 0 → 0 pts, `None` → 0 → 0 pts.  
This is identical to existing `balcony_terrace` normalization.

---

## Scoring Changes

### Module: Application/scoring.py — NORMALIZATION_RANGES additions

- **Responsibility:** Add normalization config for 4 new bool fields
- **Interface:** Same pattern as `balcony_terrace` entry
- **Dependencies:** None
- **Size target:** +4 entries

```python
'lift_present':            {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
'facade_renovated':        {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
'parifizierung_complete':  {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
'roof_renovated':          {'min_val': 0, 'max_val': 1, 'direction': 'higher_is_better'},
```

---

## Bank Loan Ready Profile

### Module: Application/buyer_profiles.py additions

- **Responsibility:** New `bank_loan_ready` profile + enum member
- **Interface:** Follows existing BUYER_PROFILES dict pattern
- **Dependencies:** New fields in scoring.py NORMALIZATION_RANGES
- **Size target:** +20 lines

**Weight distribution** (sums to 1.0):

| Criterion | Weight | Bank Category |
|---|---|---|
| `price_per_m2` | 0.13 | Pricing / Niederstwertprinzip |
| `ubahn_walk_minutes` | 0.12 | Location |
| `facade_renovated` | 0.07 | Building Substance |
| `hwb_value` | 0.10 | Energy |
| `parifizierung_complete` | 0.10 | Legal / Financial |
| `potential_growth_rating` | 0.08 | Location / district trajectory |
| `renovation_needed_rating` | 0.12 | Apartment Condition (boosted from 8%) |
| `roof_renovated` | 0.04 | Building Substance |
| `year_built` | 0.09 | Building Substance (boosted from 6%) |
| `lift_present` | 0.03 | Apartment Features |
| `area_m2` | 0.03 | Apartment Features |
| `floor_level` | 0.03 | Apartment Features |
| `school_walk_minutes` | 0.02 | Location / infrastructure |
| `balcony_terrace` | 0.02 | Apartment Features |
| `rooms` | 0.02 | Apartment Features |

Weight rationale: facade (7%), roof (4%), lift (3%) reduced from original 10%/6%/5% to limit systematic bias from sparse listing descriptions. Redistributed to renovation_needed_rating (+4%) and year_built (+3%) — always-present proxies for building quality.

**Enum addition:**
```python
BANK_LOAN_READY = 'bank_loan_ready'
```

---

## Field Extraction

### Module: Application/scraping/field_extractors.py (new)

- **Responsibility:** Extract 4 bool fields from listing description text using German regex patterns with negation handling
- **Interface:** `extract_lift_present(text: str) -> Optional[bool]` × 4 functions. Input: `soup.get_text().lower()`. Output: `True` / `False` / `None`
- **Dependencies:** `re`, `typing.Optional`
- **Size target:** <100 lines

**Negation rule (two-pass — Python `re` does not support variable-length look-behinds):**
1. Check negative patterns first. If match → return `False`.
2. Else check positive patterns. If match → return `True`.
3. No match either → return `None`.

**Patterns per field:**

```
lift_present:
  negative: r'(kein|keine|keinen|ohne)\s+\w*\s*(aufzug|lift)'
  positive: r'aufzug|fahrstuhl|lift\s+im\s+haus|aufzug\s+vorhanden'

facade_renovated:
  negative: r'(keine|nicht)\s+\w*\s*fassaden?(sanierung|renovierung|dämmung)'
  positive: r'fassaden?(sanierung|renovierung|dämmung)|sanierte\s+fassade|fassade\s+(saniert|renoviert|gedämmt)|wärmedämmfassade|neue\s+fassade'

parifizierung_complete:
  negative: r'parifizierung\s+(ausstehend|noch\s+nicht|nicht\s+abgeschlossen)|nicht\s+parifiziert'
  positive: r'parifizierung\s+abgeschlossen|bereits\s+parifiziert|parifiziert'

roof_renovated:
  negative: r'(keine|nicht)\s+\w*\s*dach(sanierung|renovierung)'
  positive: r'dach(sanierung|renovierung)|saniertes?\s+dach|dach\s+(saniert|renoviert)|neues?\s+dach'
```

**Text scope:** `soup.get_text().lower()` — full page text. Risk: nav/footer false positives (acceptable for v1; tune per-scraper selectors in Phase 2 if precision is poor).

### Wiring: All 3 existing scrapers

**Affected files** (all must be updated — ADR lesson: no partial wiring):
- `Application/scraping/willhaben_scraper.py`
- `Application/scraping/immo_kurier_scraper.py`
- `Application/scraping/derstandard_scraper.py`

**Wiring pattern** (identical in all 3, at end of `scrape_single_listing()`):

```python
from Application.scraping.field_extractors import (
    extract_lift_present, extract_facade_renovated,
    extract_parifizierung_complete, extract_roof_renovated
)

# Near end of scrape_single_listing, after existing field extractions:
full_text = soup.get_text().lower()
listing.lift_present = extract_lift_present(full_text)
listing.facade_renovated = extract_facade_renovated(full_text)
listing.parifizierung_complete = extract_parifizierung_complete(full_text)
listing.roof_renovated = extract_roof_renovated(full_text)
```

**Verification per scraper:** After wiring, confirm that at least one test listing returns non-None for at least one field. If all fields are always None, the pattern is wrong.

---

## Scope Boundaries (What This Spec Does NOT Include)

- New scrapers for immo.at or wohnnet.at → Phase 2
- Dashboard display of new fields → future work
- Hard floor filters on bank profile → CLI `--min-score` flag handles this
- Hausverwaltung / Rücklage extraction → not reliably present in listing text

---

## Known Constraints

- **Backwards compatibility:** Existing MongoDB listings have no new fields → `None` → 0 pts on 4 criteria. Max achievable score for old listings on `bank_loan_ready` = ~76/100 (new fields at 0, weight 24%). New listings can score up to 100. Not a bug — penalizing unknowns is the intent.
- **GitHub Actions:** No changes to CI/CD. New profile is a CLI flag only.
- **ADR compliance:** `field_extractors.py` must be called in ALL 3 scrapers or extraction diverges (see edge-case: 2026-05-05-extraction-gap-validation.md).

---

## Files Changed

| File | Change Type | Description |
|---|---|---|
| `Project/Domain/listing.py` | Modify | +4 Optional[bool] fields |
| `Project/Application/scoring.py` | Modify | +4 NORMALIZATION_RANGES entries |
| `Project/Application/buyer_profiles.py` | Modify | +profile dict + enum member |
| `Project/Application/scraping/field_extractors.py` | Create | 4 extraction functions (two-pass negation) |
| `Project/Application/scraping/willhaben_scraper.py` | Modify | Wire field_extractors |
| `Project/Application/scraping/immo_kurier_scraper.py` | Modify | Wire field_extractors |
| `Project/Application/scraping/derstandard_scraper.py` | Modify | Wire field_extractors |
| `Tests/test_field_extractors.py` | Create | 3–5 cases per function: positive, negative, absent |

---

## Success Criteria

1. `python run_top5.py --buyer-profile=bank_loan_ready` executes without error
2. At least one scraped listing has non-None value for at least one new field
3. Profile weights sum to 1.0 (validated by `validate_profile_weights()`)
4. All 3 scrapers call `field_extractors` (grep check)
5. Score for a listing with facade_renovated=True, parifizierung_complete=True is measurably higher than same listing without those fields
6. `Tests/test_field_extractors.py` passes: positive match, negative match, absent → None for each of 4 functions
