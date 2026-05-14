# Bank Scoring Altbau Fix — Design Spec

**Date:** 2026-05-14  
**Status:** Approved  
**Trigger:** Altbau listings with missing `year_built` receive unrealistically low equity requirements because the age penalty never fires and condition/HWB signals are ignored.

---

## Problem Statement

### Bug 1: Altbau properties are over-scored

Example: DerStandard listing 15139047 — "Großzügige Altbauwohnung mit großem Ausbaupotential", energy C, HWB 84.4, year_built unknown.

Current output: factor = 0.92 → **26.4% down payment required**  
Real bank expectation: factor ~0.75 → **~39% down payment required**

Root cause: `year_built` is not provided by DerStandard for this listing, so the age penalty (−0.05 for pre-1970) never fires. The formula only sees energy class C (base 0.92) and nothing else. The condition ("Altbau", "Ausbaupotential") and HWB (84.4 — high for a C-class property) are ignored entirely.

### Bug 2: Green badge threshold is mathematically unreachable

`EquityBadge.tsx` shows green when `downPct ≤ 15`. But the formula minimum is:
```
factor capped at 1.0 → down_pct = (1 − 0.80 × 1.0) × 100 = 20%
```
No listing can ever show green. The threshold is dead code.

---

## Design Decisions

| # | Question | Decision |
|---|---|---|
| 1 | How to add new signals? | Use raw fields from Listing at scrape time — no sequencing change |
| 2 | HWB + energy_class interaction | Sub-class penalty only (−0.03 if HWB in top 30% of class band) |
| 3 | Condition penalty magnitudes | Three tiers, cap at −0.15 |
| 4 | Green badge fix | Switch green tier to KIM-V (90% LTV) ≤15% |
| 5 | Text fields to scan | `condition` + `title` combined |
| 6 | Confidence calculation | Add `hwb_value` as 6th signal; adjust thresholds |

---

## Module Design

### Module: `bank_scoring.py` (modify)

- **Responsibility:** Compute Belehnungswert factor and equity estimates from listing fields
- **Interface:** `compute_bank_score(listing) → BankScore` — listing must expose `.hwb_value`, `.condition`, `.title` in addition to existing fields
- **Dependencies:** None (pure function)
- **Size target:** ~150 lines, single responsibility

**New inputs consumed:**

| Field | Type | Source |
|---|---|---|
| `hwb_value` | `Optional[float]` | Already on Listing, extracted by all 3 scrapers |
| `condition` | `Optional[str]` | Already on Listing |
| `title` | `Optional[str]` | Already on Listing |

**HWB sub-class penalty (`−0.03`):**

Fires when `hwb_value > class_upper_bound × 0.70`:

| Energy class | Upper bound | Penalty fires when HWB > |
|---|---|---|
| A++, A+, A | 25 | 17.5 |
| B | 50 | 35 |
| C | 75 | 52.5 |
| D | 100 | 70 |
| E | 150 | 105 |
| F, G | — | never (already worst-class) |

Penalty only applies when `energy_class` is declared (HWB as override path is separate).

**Condition keyword tiers** (scan `f"{condition or ''} {title or ''}".lower()`):

| Keyword(s) | Penalty |
|---|---|
| `sanierungsbedürftig` or `renovierungsbedürftig` | −0.12 |
| `ausbaupotential` or `ausbaumöglichkeit` | −0.09 |
| `altbau` (without `renoviert` within 30 chars) | −0.04 |

Total condition penalty capped at **−0.15**.

**Updated confidence (6 signals):**

Signals: `[energy_class, year_built, facade_renovated, roof_renovated, window_type, hwb_value]`

| None count | Confidence |
|---|---|
| ≤ 2 | `high` |
| ≤ 4 | `medium` |
| > 4 | `low` |

---

### Module: `EquityBadge.tsx` (modify)

- **Responsibility:** Display equity badge with color tier
- **Interface:** Props unchanged (`downPct`, `equityEur`, `confidence`, add `downPctKimv`)
- **Dependencies:** None
- **Size target:** ~40 lines

**New color logic:**

```
green  → downPctKimv != null && downPctKimv ≤ 15   (KIM-V eligible: factor ≥ 0.944)
yellow → downPct ≤ 25                               (standard 80% LTV, reasonable equity)
orange → downPct > 25                               (significant equity required)
```

Green is now physically achievable: energy A/B + year ≥ 2015 → factor hits 1.0 → `estimated_down_pct_kimv = (1 − 0.90 × 1.0) × 100 = 10%`.

Label shows standard `downPct` in all cases (KIM-V only drives the color).

---

### Scrapers: willhaben, immo_kurier, derstandard (no change needed)

`compute_bank_score(listing)` already receives the full listing object. The function will access `.hwb_value`, `.condition`, `.title` directly — no call-site changes required.

---

### Backfill script (update)

The existing `Project/scripts/backfill_bank_scores.py` builds a minimal `Listing` object from MongoDB document fields. It must be updated to also pass `hwb_value`, `condition`, and `title` when constructing the listing for re-scoring.

---

## Calibration Verification

After changes, the triggering listing must score as follows:

| Input | Value |
|---|---|
| `energy_class` | C |
| `hwb_value` | 84.4 |
| `title` | "Großzügige Altbauwohnung mit großem Ausbaupotential" |
| `condition` | None |
| `year_built` | None |

Expected output:
- HWB penalty: 84.4 > 52.5 → −0.03
- Condition keywords: `altbau` (−0.04) + `ausbaupotential` (−0.09) = −0.13
- Total: 0.92 − 0.03 − 0.13 = **0.76**
- `estimated_down_pct` = (1 − 0.80 × 0.76) × 100 = **39.2%** ✓
- `confidence`: [energy_class=C ✓, hwb_value=84.4 ✓, year_built=None, facade=None, roof=None, window=None] → 4 Nones → `medium` ✓
- Badge: `estimated_down_pct = 39.2%` (orange, visible) ✓

---

## Files Changed

| File | Change |
|---|---|
| `Project/Application/bank_scoring.py` | Add HWB + condition/title signals; update confidence |
| `dashboard/components/EquityBadge.tsx` | Switch green to KIM-V ≤15%; add `downPctKimv` prop |
| `dashboard/components/ListingCard.tsx` | Pass `estimated_down_pct_kimv` to EquityBadge |
| `Project/scripts/backfill_bank_scores.py` | Pass `hwb_value`, `condition`, `title` during re-score |
| `Tests/test_bank_scoring.py` | Add tests for HWB penalty, keyword tiers, cap, new confidence |

No scraper changes required — `compute_bank_score(listing)` already receives the full object.
