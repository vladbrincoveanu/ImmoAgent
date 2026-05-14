# Bank Scoring Altbau Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs: (1) Altbau properties with missing `year_built` receive unrealistically low equity requirements because HWB and condition/title signals are ignored; (2) the EquityBadge green tier (`≤15%`) is mathematically unreachable under 80% LTV.

**Architecture:** Add `hwb_value`, `condition`, and `title` as inputs to `compute_bank_score` (all already on the Listing at scrape time — no sequencing change). Add HWB sub-class penalty (−0.03) and condition keyword tiers (cap −0.15). Expand confidence to 6 signals. Fix EquityBadge green tier to use KIM-V (90% LTV) which CAN reach ≤15% for A/B-class Neubau properties.

**Tech Stack:** Python 3, dataclasses / Next.js 15, TypeScript, Tailwind CSS

---

## File Map

| File | Action | What changes |
|---|---|---|
| `Tests/test_bank_scoring.py` | Modify | Update `make_listing` helper; add 8 new test cases |
| `Project/Application/bank_scoring.py` | Modify | Add HWB + condition/title signals; update confidence |
| `dashboard/lib/types.ts` | Modify | Move `estimated_down_pct_kimv` from `ListingDetail` to `ListingBase` |
| `dashboard/components/EquityBadge.tsx` | Modify | Add `downPctKimv` prop; new color logic using KIM-V for green |
| `dashboard/components/ListingCard.tsx` | Modify | Pass `estimated_down_pct_kimv` to EquityBadge |
| `Project/scripts/backfill_bank_scores.py` | Modify | Pass `hwb_value`, `condition`, `title` when re-scoring |

No scraper changes — `compute_bank_score(listing)` already receives the full Listing object.

---

## Task 1: Failing tests for bank_scoring changes (TDD)

**Files:**
- Modify: `Tests/test_bank_scoring.py`

Run all commands from `Project/` directory.

- [ ] **Step 1: Update `make_listing` helper and add 8 new failing tests**

Open `Tests/test_bank_scoring.py`. Replace the `make_listing` function with this updated version (adds `hwb_value`, `condition`, `title` — all default to `None`):

```python
def make_listing(**kwargs):
    m = MagicMock()
    m.energy_class      = kwargs.get('energy_class', None)
    m.year_built        = kwargs.get('year_built', None)
    m.facade_renovated  = kwargs.get('facade_renovated', None)
    m.roof_renovated    = kwargs.get('roof_renovated', None)
    m.window_type       = kwargs.get('window_type', None)
    m.hwb_value         = kwargs.get('hwb_value', None)
    m.condition         = kwargs.get('condition', None)
    m.title             = kwargs.get('title', None)
    m.price_total       = kwargs.get('price_total', None)
    return m
```

Then append these 8 test methods to `TestComputeBankScore`:

```python
    def test_hwb_subclass_penalty_fires_for_energy_c_high_hwb(self):
        """Energy C + HWB 84 → penalty -0.03 (84 > 75*0.70=52.5)."""
        from Application.bank_scoring import compute_bank_score
        no_hwb = make_listing(energy_class='C', price_total=400000)
        with_hwb = make_listing(energy_class='C', hwb_value=84.0, price_total=400000)
        self.assertAlmostEqual(
            compute_bank_score(no_hwb).belehnungswert_factor -
            compute_bank_score(with_hwb).belehnungswert_factor,
            0.03, places=4
        )

    def test_hwb_subclass_penalty_does_not_fire_for_low_hwb(self):
        """Energy C + HWB 50 → no penalty (50 <= 52.5)."""
        from Application.bank_scoring import compute_bank_score
        no_hwb = make_listing(energy_class='C', price_total=400000)
        low_hwb = make_listing(energy_class='C', hwb_value=50.0, price_total=400000)
        self.assertAlmostEqual(
            compute_bank_score(no_hwb).belehnungswert_factor,
            compute_bank_score(low_hwb).belehnungswert_factor,
            places=4
        )

    def test_ausbaupotential_in_title_applies_penalty(self):
        """'ausbaupotential' in title → -0.09 adjustment."""
        from Application.bank_scoring import compute_bank_score
        base = make_listing(energy_class='C', price_total=400000)
        titled = make_listing(energy_class='C', title='Altbauwohnung mit Ausbaupotential', price_total=400000)
        diff = compute_bank_score(base).belehnungswert_factor - compute_bank_score(titled).belehnungswert_factor
        # titled has altbau(-0.04) + ausbaupotential(-0.09) = -0.13
        self.assertAlmostEqual(diff, 0.13, places=4)

    def test_sanierungsbeduerftig_applies_largest_penalty(self):
        """'sanierungsbedürftig' → -0.12 penalty."""
        from Application.bank_scoring import compute_bank_score
        base = make_listing(energy_class='C', price_total=400000)
        saniert = make_listing(energy_class='C', condition='sanierungsbedürftig', price_total=400000)
        diff = compute_bank_score(base).belehnungswert_factor - compute_bank_score(saniert).belehnungswert_factor
        self.assertAlmostEqual(diff, 0.12, places=4)

    def test_altbau_with_renoviert_skips_altbau_penalty(self):
        """'altbau' + 'renoviert' in same text → no altbau penalty fires."""
        from Application.bank_scoring import compute_bank_score
        base = make_listing(energy_class='C', price_total=400000)
        renovated = make_listing(energy_class='C', condition='Altbau vollständig renoviert', price_total=400000)
        self.assertAlmostEqual(
            compute_bank_score(base).belehnungswert_factor,
            compute_bank_score(renovated).belehnungswert_factor,
            places=4
        )

    def test_condition_penalty_capped_at_015(self):
        """All three keyword tiers fire (0.12+0.09+0.04=0.25) → capped at 0.15."""
        from Application.bank_scoring import compute_bank_score
        base = make_listing(energy_class='C', price_total=400000)
        worst = make_listing(
            energy_class='C',
            condition='sanierungsbedürftig Altbau mit Ausbaupotential',
            price_total=400000
        )
        diff = compute_bank_score(base).belehnungswert_factor - compute_bank_score(worst).belehnungswert_factor
        self.assertAlmostEqual(diff, 0.15, places=4)

    def test_calibration_triggering_listing(self):
        """The listing that triggered this fix: energy C, HWB 84.4, altbau+ausbaupotential → factor=0.76, down=39.2%."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(
            energy_class='C',
            hwb_value=84.4,
            title='Großzügige Altbauwohnung mit großem Ausbaupotential',
            price_total=399000,
        )
        score = compute_bank_score(listing)
        self.assertAlmostEqual(score.belehnungswert_factor, 0.76, places=4)
        self.assertAlmostEqual(score.estimated_down_pct, 39.2, places=1)

    def test_confidence_hwb_as_sixth_signal(self):
        """hwb_value counts as 6th signal. energy+hwb known, rest None → 4 Nones → medium."""
        from Application.bank_scoring import compute_bank_score
        listing = make_listing(energy_class='C', hwb_value=60.0, price_total=300000)
        score = compute_bank_score(listing)
        self.assertEqual(score.bank_score_confidence, 'medium')
```

- [ ] **Step 2: Run the new tests — expect failures**

```bash
cd Project && python -m pytest Tests/test_bank_scoring.py -v -k "hwb or ausbaupotential or sanierung or altbau_with or capped or calibration_triggering or sixth" 2>&1 | tail -20
```

Expected: all 8 new tests FAIL (current `compute_bank_score` ignores hwb_value/condition/title).

- [ ] **Step 3: Verify existing 7 tests still pass before touching implementation**

```bash
cd Project && python -m pytest Tests/test_bank_scoring.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: original 7 pass, 8 new fail. If any original test breaks now, fix `make_listing` — the mock must return `None` for all unspecified fields, not MagicMock objects.

- [ ] **Step 4: Commit failing tests**

```bash
git add Tests/test_bank_scoring.py
git commit -m "test(bank_scoring): add failing tests for HWB + condition keyword signals"
```

---

## Task 2: Update bank_scoring.py

**Files:**
- Modify: `Project/Application/bank_scoring.py`

- [ ] **Step 1: Add HWB class upper bounds constant and update compute_bank_score**

Replace the full contents of `Project/Application/bank_scoring.py` with:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

ENERGY_BASE: dict[str, float] = {
    'A++': 1.00, 'A+': 1.00,
    'A':   0.97, 'B':  0.97,
    'C':   0.92,
    'D':   0.85,
    'E':   0.75,
    'F':   0.65, 'G':  0.65,
}

# Upper HWB bound per energy class (OIB Richtlinie 6).
# Penalty fires when HWB > upper * 0.70 (top 30% of class band).
HWB_CLASS_UPPER: dict[str, float] = {
    'A++': 25.0, 'A+': 25.0, 'A': 25.0,
    'B':   50.0,
    'C':   75.0,
    'D':  100.0,
    'E':  150.0,
    # F and G already carry the lowest base factor; no sub-class penalty.
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
    energy_class     = listing.energy_class
    year_built       = listing.year_built
    facade_renovated = listing.facade_renovated
    roof_renovated   = listing.roof_renovated
    window_type      = listing.window_type
    hwb_value        = listing.hwb_value
    condition        = listing.condition
    title            = listing.title
    price_total      = listing.price_total

    # Confidence: 6 signals. ≤2 None → high, ≤4 None → medium, >4 → low.
    none_count = sum(
        1 for v in [energy_class, year_built, facade_renovated, roof_renovated, window_type, hwb_value]
        if v is None
    )
    if none_count <= 2:
        confidence = 'high'
    elif none_count <= 4:
        confidence = 'medium'
    else:
        confidence = 'low'

    # Base factor from energy class
    if energy_class is not None:
        factor = ENERGY_BASE.get(str(energy_class).upper().strip(), 0.82)
    else:
        # year_built fallback — ALSO gets year adjustment below (intentional double-signal:
        # old Altbau with no energy cert is penalized for both missing cert AND old age).
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

    # HWB sub-class penalty: fires when HWB is in the top 30% of the declared class band.
    if energy_class is not None and hwb_value is not None:
        upper = HWB_CLASS_UPPER.get(str(energy_class).upper().strip())
        if upper is not None and hwb_value > upper * 0.70:
            factor -= 0.03

    # Condition keyword penalty (scan condition field + title).
    # Tiers are additive; total capped at 0.15.
    text = f"{condition or ''} {title or ''}".lower()
    cond_penalty = 0.0
    if 'sanierungsbedürftig' in text or 'renovierungsbedürftig' in text:
        cond_penalty += 0.12
    if 'ausbaupotential' in text or 'ausbaumöglichkeit' in text:
        cond_penalty += 0.09
    if 'altbau' in text and 'renoviert' not in text:
        cond_penalty += 0.04
    factor -= min(cond_penalty, 0.15)

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

- [ ] **Step 2: Run all bank_scoring tests — expect all 15 passing**

```bash
cd Project && python -m pytest Tests/test_bank_scoring.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"
```

Expected: `15 passed`. If `test_calibration_triggering_listing` fails, verify: energy C (0.92) − HWB penalty (0.03) − altbau (0.04) − ausbaupotential (0.09) = 0.76. `min(0.13, 0.15)` = 0.13 total condition. `down_pct = (1 − 0.80 × 0.76) × 100 = 39.2`. ✓

- [ ] **Step 3: Smoke-test import chain**

```bash
cd Project && python -c "
from Application.bank_scoring import compute_bank_score
from unittest.mock import MagicMock
m = MagicMock()
m.energy_class = 'C'; m.hwb_value = 84.4
m.title = 'Altbauwohnung mit Ausbaupotential'
m.condition = None; m.year_built = None
m.facade_renovated = None; m.roof_renovated = None
m.window_type = None; m.price_total = 399000
s = compute_bank_score(m)
print(f'factor={s.belehnungswert_factor} down={s.estimated_down_pct}% conf={s.bank_score_confidence}')
assert s.belehnungswert_factor == 0.76, s.belehnungswert_factor
assert s.estimated_down_pct == 39.2, s.estimated_down_pct
assert s.bank_score_confidence == 'medium', s.bank_score_confidence
print('OK')
"
```

Expected: `factor=0.76 down=39.2% conf=medium` then `OK`.

- [ ] **Step 4: Commit**

```bash
git add Project/Application/bank_scoring.py
git commit -m "feat(bank_scoring): add HWB sub-class penalty + condition keyword tiers + 6-signal confidence"
```

---

## Task 3: Move KIM-V field to ListingBase + update EquityBadge

**Files:**
- Modify: `dashboard/lib/types.ts`
- Modify: `dashboard/components/EquityBadge.tsx`

- [ ] **Step 1: Move `estimated_down_pct_kimv` from `ListingDetail` to `ListingBase`**

In `dashboard/lib/types.ts`, add `estimated_down_pct_kimv` to `ListingBase` (after `bank_score_confidence`):

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
  estimated_down_pct_kimv?: number | null;
}
```

Then remove `estimated_down_pct_kimv` from `ListingDetail` (it's now inherited). Find and delete this line in `ListingDetail`:

```typescript
  estimated_down_pct_kimv?: number | null;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 3: Replace EquityBadge.tsx with new color logic**

Replace the full contents of `dashboard/components/EquityBadge.tsx`:

```tsx
interface EquityBadgeProps {
  downPct: number | null | undefined;
  downPctKimv: number | null | undefined;
  equityEur: number | null | undefined;
  confidence: string | null | undefined;
}

export function EquityBadge({ downPct, downPctKimv, equityEur, confidence }: EquityBadgeProps) {
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
  if (downPctKimv != null && downPctKimv <= 15) {
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

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd dashboard && npx tsc --noEmit 2>&1
```

Expected: no errors. (ListingCard.tsx will error until Task 4 adds the new prop — fix ListingCard first if tsc fails there.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib/types.ts dashboard/components/EquityBadge.tsx
git commit -m "feat(dashboard): KIM-V green tier in EquityBadge; promote estimated_down_pct_kimv to ListingBase"
```

---

## Task 4: Update ListingCard + UI smoke test

**Files:**
- Modify: `dashboard/components/ListingCard.tsx`

- [ ] **Step 1: Add `downPctKimv` prop to EquityBadge call site**

In `dashboard/components/ListingCard.tsx`, find (around line 63):

```tsx
          <EquityBadge
            downPct={listing.estimated_down_pct}
            equityEur={listing.estimated_equity_eur}
            confidence={listing.bank_score_confidence}
          />
```

Replace with:

```tsx
          <EquityBadge
            downPct={listing.estimated_down_pct}
            downPctKimv={listing.estimated_down_pct_kimv}
            equityEur={listing.estimated_equity_eur}
            confidence={listing.bank_score_confidence}
          />
```

- [ ] **Step 2: Verify TypeScript compiles clean**

```bash
cd dashboard && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 3: Start dev server and run Playwright smoke tests**

```bash
cd dashboard && npm run dev &
sleep 15
npx playwright test --reporter=list 2>&1
```

Expected: all 5 smoke tests pass, 0 console errors. If tests fail, read the error output and fix the code. Re-run until clean.

- [ ] **Step 4: Stop dev server**

```bash
pkill -f "next dev" 2>/dev/null; true
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/ListingCard.tsx
git commit -m "feat(dashboard): pass estimated_down_pct_kimv to EquityBadge"
```

---

## Task 5: Update backfill script

**Files:**
- Modify: `Project/scripts/backfill_bank_scores.py`

- [ ] **Step 1: Add `hwb_value`, `condition`, `title` to Listing construction in backfill**

In `Project/scripts/backfill_bank_scores.py`, find the Listing construction inside the `for doc in col.find(query):` loop:

```python
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
```

Replace with:

```python
        listing = Listing(
            url=doc.get('url', ''),
            source=doc.get('source', 'unknown'),
            price_total=doc.get('price_total'),
            energy_class=doc.get('energy_class'),
            year_built=doc.get('year_built'),
            facade_renovated=doc.get('facade_renovated'),
            roof_renovated=doc.get('roof_renovated'),
            window_type=doc.get('window_type'),
            hwb_value=doc.get('hwb_value'),
            condition=doc.get('condition'),
            title=doc.get('title'),
        )
```

- [ ] **Step 2: Verify dry-run import**

```bash
cd Project && python -c "
import sys, os
sys.path.insert(0, '.')
from Application.bank_scoring import compute_bank_score
from Domain.listing import Listing
l = Listing(
    url='x', source='y',
    price_total=399000, energy_class='C', hwb_value=84.4,
    title='Altbauwohnung mit Ausbaupotential',
)
s = compute_bank_score(l)
print(f'factor={s.belehnungswert_factor} down={s.estimated_down_pct}% conf={s.bank_score_confidence}')
assert s.estimated_down_pct == 39.2
print('OK')
"
```

Expected: `factor=0.76 down=39.2% conf=medium` then `OK`.

- [ ] **Step 3: Commit**

```bash
git add Project/scripts/backfill_bank_scores.py
git commit -m "feat(scripts): pass hwb_value, condition, title to bank_scoring in backfill"
```

---

## Self-Review

**Spec coverage:**
- ✅ HWB sub-class penalty (−0.03 when HWB > upper × 0.70) — Task 2
- ✅ Condition keyword tiers (-0.12 / -0.09 / -0.04), cap at -0.15 — Task 2
- ✅ Scan `condition` + `title` combined — Task 2
- ✅ Confidence: 6 signals; ≤2→high, ≤4→medium, >4→low — Task 2
- ✅ No scraper changes needed (listing object already passed) — verified in File Map
- ✅ Green badge uses KIM-V ≤15% — Task 3
- ✅ `estimated_down_pct_kimv` promoted to `ListingBase` — Task 3
- ✅ ListingCard passes `downPctKimv` prop — Task 4
- ✅ Playwright smoke tests run after dashboard change — Task 4
- ✅ Backfill passes `hwb_value`, `condition`, `title` — Task 5
- ✅ Calibration: triggering listing → factor=0.76, down=39.2% — Task 1 + Task 2

**Calibration check (end-to-end):**
Energy C (0.92) − HWB 84.4 penalty (0.03) − altbau (0.04) − ausbaupotential (0.09) = **0.76**  
`down_pct = (1 − 0.80 × 0.76) × 100 = 39.2%` ✓  
`confidence`: [C ✓, None, None, None, None, 84.4 ✓] = 4 Nones → **medium** ✓  
Badge: orange (39.2% > 25%), shows percentage (not "? equity" since medium ≠ low) ✓
