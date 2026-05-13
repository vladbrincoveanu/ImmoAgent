# Design: Neubauprojekt Search Expansion + Belehnungswert Bank Scoring

**Date:** 2026-05-13
**Status:** Approved
**Builds on:** `2026-05-12-bank-loan-profile-field-extraction-design.md` (fields already extracted), `2026-05-12-neubauprojekt-expansion-rich-extraction-design.md` (expansion loop already implemented)

---

## Problem

Current dashboard shows listings scored on property quality but gives no signal on bank financing feasibility. A real bank conversation showed that an Altbau 1900 with energy class E required 44% equity — not the ~10% expected. Dashboard shows no way to distinguish listings the bank would finance at ≤15% equity from those requiring 35–50%.

Additionally, the Willhaben scraper only searches `eigentumswohnung` listings. Neubauprojekt pages (new builds, energy class A/B, most bank-friendly) live at a separate Willhaben endpoint and are never found by search — only expanded if encountered incidentally.

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| LTV base | 80% (standard) | Bank conversation confirmed: energy E Altbau → 44% equity at 80% LTV exactly. KIM-V 90% shown as second line in modal. |
| Bank scoring location | Scrape time, stored in MongoDB | Dashboard stays dumb (reads stored values). Enables DB-level filtering. |
| Config schema change | Add `search_url_extra` list | Non-breaking. Existing `search_url` string untouched. |
| Hidden threshold | >30% estimated_down_pct | Listings needing >€90k equity on a €300k apartment are not actionable. Toggle reveals them. |
| Confidence field | "low/medium/high" based on None count | Prevents hiding listings where estimate is unreliable due to missing data. |
| rooms_min | Keep at 3 | Accept Neubau inventory limited to 3-room units in budget. |
| Price cap | Dashboard filter (default €500k) | Keeps DB complete; scraper price_max unchanged. |

---

## Module Designs

### Module: `bank_scoring.py`
- **Responsibility:** Compute Belehnungswert factor and equity estimates from listing fields
- **Interface:** `compute_bank_score(listing) -> BankScore` where `BankScore` is a dataclass with 5 fields
- **Dependencies:** `Domain/listing.py` (read-only), `dataclasses`
- **Size target:** ~80 lines

**Belehnungswert factor formula:**

Base factor from energy class:

| energy_class | base_factor |
|---|---|
| A++, A+ | 1.00 |
| A, B | 0.97 |
| C | 0.92 |
| D | 0.85 |
| E | 0.75 |
| F, G | 0.65 |
| None + year_built ≥ 2010 | 0.95 |
| None + year_built < 1970 | 0.72 |
| None + other | 0.82 |

Adjustments (additive, capped at 1.0 total):

| Signal | Delta |
|---|---|
| year_built ≥ 2015 | +0.05 |
| year_built 2000–2014 | +0.02 |
| year_built < 1970 | −0.05 |
| facade_renovated = True | +0.04 |
| facade_renovated = False | −0.03 |
| roof_renovated = True | +0.02 |
| window_type = 'kastenfenster' | −0.04 |
| window_type = 'kunststoff'/'holz-alu'/'isolierverglasung' | +0.02 |

Confidence scoring (count of None inputs from the 5 adjustment signals: energy_class, year_built, facade_renovated, roof_renovated, window_type):
- 0–1 None → `"high"`
- 2–3 None → `"medium"`
- 4–5 None → `"low"`

Derived values (None guard: return all None if `price_total` is None):
```
loan_80 = 0.80 × factor × price_total
loan_90 = 0.90 × factor × price_total
estimated_down_pct      = (1 − loan_80 / price_total) × 100   # standard LTV
estimated_down_pct_kimv = (1 − loan_90 / price_total) × 100   # KIM-V best case
estimated_equity_eur    = round(price_total × estimated_down_pct / 100)
```

Output dataclass:
```python
@dataclass
class BankScore:
    belehnungswert_factor:   float
    estimated_down_pct:      Optional[float]  # 80% LTV
    estimated_down_pct_kimv: Optional[float]  # 90% LTV (KIM-V)
    estimated_equity_eur:    Optional[int]
    bank_score_confidence:   str              # "low" | "medium" | "high"
```

Calibration check: Altbau 1900 energy E, no renovation, no windows info → factor = 0.75 − 0.05 = 0.70 → estimated_down_pct = (1 − 0.80 × 0.70) × 100 = 44%. Matches bank conversation exactly.

---

### Module: `Domain/listing.py` additions
- **Responsibility:** Store bank scoring output fields
- **Interface:** 5 new Optional fields appended to Listing dataclass
- **Dependencies:** None
- **Size target:** +5 lines

```python
belehnungswert_factor:   Optional[float] = None
estimated_down_pct:      Optional[float] = None  # 80% LTV
estimated_down_pct_kimv: Optional[float] = None  # 90% LTV KIM-V
estimated_equity_eur:    Optional[int]   = None
bank_score_confidence:   Optional[str]   = None  # "low"|"medium"|"high"
```

---

### Module: Scraper wiring (all 3 scrapers)
- **Responsibility:** Call `compute_bank_score` at end of `scrape_single_listing`
- **Interface:** Add ~5 lines to each scraper after all field extraction is complete
- **Dependencies:** `bank_scoring.compute_bank_score`
- **Size target:** +5 lines × 3 files

Pattern (identical in all 3 scrapers, after existing field extractions):
```python
from Application.bank_scoring import compute_bank_score

score = compute_bank_score(listing)
listing.belehnungswert_factor   = score.belehnungswert_factor
listing.estimated_down_pct      = score.estimated_down_pct
listing.estimated_down_pct_kimv = score.estimated_down_pct_kimv
listing.estimated_equity_eur    = score.estimated_equity_eur
listing.bank_score_confidence   = score.bank_score_confidence
```

ADR compliance: all 3 scrapers must be updated or bank scores diverge (same failure mode as field_extractors gap — see edge-case 2026-05-05).

---

### Module: `config.json` change
- **Responsibility:** Feed neubauprojekt search URL into Willhaben scraper
- **Interface:** Add `search_url_extra` list alongside existing `search_url`
- **Dependencies:** Willhaben scraper loop (reads both keys)
- **Size target:** +3 lines in config.json, +5 lines in willhaben_scraper.py

Config addition:
```json
"willhaben": {
  "search_url": "https://www.willhaben.at/iad/immobilien/eigentumswohnung/wien",
  "search_url_extra": [
    "https://www.willhaben.at/iad/immobilien/neubauprojekt/wien"
  ]
}
```

Scraper loop change: before iterating pages, collect all search URLs:
```python
search_urls = [config['willhaben']['search_url']]
search_urls += config['willhaben'].get('search_url_extra', [])
for search_url in search_urls:
    # existing page iteration loop
```

---

### Module: `scripts/backfill_bank_scores.py`
- **Responsibility:** One-time backfill of bank scoring fields for all existing DB listings
- **Interface:** CLI script, reads all listings from MongoDB, writes 5 fields per listing
- **Dependencies:** `MongoDBHandler`, `bank_scoring.compute_bank_score`, `Domain/listing.py`
- **Size target:** ~50 lines

Behavior:
1. Query all listings where `estimated_down_pct` is null
2. For each: reconstruct minimal Listing from DB dict (only the 5 input fields needed)
3. Call `compute_bank_score(listing)`
4. `update_one({_id: id}, {$set: {bank score fields}})`
5. Print progress (N processed, N updated, N skipped due to missing price_total)

Safe: reads and writes single fields only, never deletes. Idempotent: `estimated_down_pct` null guard means re-running is a no-op.

---

### Module: Dashboard card equity badge
- **Responsibility:** Show estimated equity on each listing card
- **Interface:** New `EquityBadge` component, rendered below price
- **Dependencies:** `estimated_down_pct`, `estimated_equity_eur`, `bank_score_confidence` fields
- **Size target:** ~30 lines (component + styles)

Display logic:
```
confidence = "low"  → show "? equity" (grey badge, not hidden)
down_pct ≤ 15%      → "~15% (~€45k)"  green badge
down_pct 15–25%     → "~20% (~€60k)"  yellow badge
down_pct 25–30%     → "~28% (~€84k)"  orange badge
down_pct > 30%      → hidden by default (show-unfinanceable toggle)
```

Format: `~{round to nearest 1%}% (~€{round to nearest 1k}k equity)`

---

### Module: Dashboard filters
- **Responsibility:** Max price slider + show-unfinanceable toggle
- **Interface:** Two new controls in the existing filter bar (alongside Min Score / District)
- **Dependencies:** Existing filter state; `estimated_down_pct` and `price_total` fields
- **Size target:** ~40 lines (state + filter logic)

Max price: slider or input, default 500000, applies client-side to `listing.price_total`.

Show-unfinanceable toggle: default OFF. When OFF: hide listings where `estimated_down_pct > 30` AND `bank_score_confidence != "low"`. When ON: show all. (Low confidence listings always shown — they're hidden from the rule because the estimate isn't reliable enough to justify hiding them.)

---

### Module: ListingDetail modal financing section
- **Responsibility:** Show full bank scoring breakdown in listing detail view
- **Interface:** New "Financing" accordion/section in existing ListingDetail modal
- **Dependencies:** All 5 bank score fields + `energy_class`, `hwb_value`
- **Size target:** ~40 lines

Display:
```
Financing (estimated)
────────────────────────────────
Standard (80% LTV):   ~22%  (~€66k equity)
KIM-V program (90%):  ~16%  (~€48k equity)
Belehnungswert est.:  ~91% of asking price
Confidence:           medium

Based on: Energy class B, HWB 40.3, facade unknown, roof unknown
```

---

## Data Flow

```
scrape_single_listing(url)
  ├── extract all existing fields (energy_class, hwb_value, facade_renovated, etc.)
  ├── compute_bank_score(listing)          [NEW]
  │     ├── base factor from energy_class/year_built
  │     ├── adjustments from facade/roof/window
  │     ├── confidence from None count
  │     └── → 5 bank fields written to listing
  └── mongo.save(listing)                  → all 5 bank fields persisted

scrape loop (willhaben)
  ├── search_url (eigentumswohnung)        [EXISTING]
  └── search_url_extra (neubauprojekt)     [NEW]
        └── expand_project_to_units()      [EXISTING logic]
              └── individual unit URLs → scrape_single_listing()

Dashboard /api/listings
  └── returns all fields including bank score fields (no API changes)

Dashboard card
  └── EquityBadge(estimated_down_pct, estimated_equity_eur, bank_score_confidence)

Dashboard filters
  └── maxPrice filter + showUnfinanceable toggle → client-side
```

---

## Out of Scope

- immo.at / wohnnet.at scrapers (Phase 2 per prior spec)
- immo.kurier / derstandard neubauprojekt expansion (different site structure; verify manually first)
- PDF document parsing (Exposé, Preisliste)
- Bank score as a scoring profile weight (existing `bank_loan_ready` profile covers this)
- UI for confidence explanation tooltip (future)

---

## Files Changed

| File | Change | Lines |
|---|---|---|
| `config.json` | Add `search_url_extra` | +3 |
| `Project/Application/bank_scoring.py` | New module | ~80 |
| `Project/Domain/listing.py` | +5 Optional fields | +5 |
| `Project/Application/scraping/willhaben_scraper.py` | Wire bank_scoring + search_url_extra loop | +10 |
| `Project/Application/scraping/immo_kurier_scraper.py` | Wire bank_scoring | +5 |
| `Project/Application/scraping/derstandard_scraper.py` | Wire bank_scoring | +5 |
| `Project/scripts/backfill_bank_scores.py` | New migration script | ~50 |
| `dashboard/components/EquityBadge.tsx` | New component | ~30 |
| `dashboard/components/ListingDetail.tsx` | Add financing section | ~40 |
| `dashboard/app/page.tsx` (or listings component) | Max price filter + toggle | ~40 |

---

## Success Criteria

1. `python Project/scripts/backfill_bank_scores.py` completes without error; at least 50% of DB listings get non-null `estimated_down_pct`
2. Willhaben scraper processes at least one neubauprojekt unit per run (log: `🏗️ Expanding project...`)
3. A Neubau listing (energy B/A, year ≥ 2015) shows green badge ≤15% in dashboard
4. An Altbau energy E listing shows orange/red badge or is hidden by default
5. `bank_score_confidence = "low"` listings are always shown (never hidden by toggle)
6. `compute_bank_score` returns exactly 44% for: price=560000, energy_class='E', year_built=1900, all other fields None
7. Dashboard max price filter defaults to 500000 and applies without page reload
