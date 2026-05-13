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
    price_total      = listing.price_total

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
