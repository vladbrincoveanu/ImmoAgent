import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import pytest
from Application.feasibility import (
    compute_feasibility, passes_hard_gates, extract_availability_status, FeasibilityResult, normalize_hwb_value
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
    assert end is None

# ── HWB unit normalization ──────────────────────────────────────────────────

def test_normalize_hwb_float():
    assert normalize_hwb_value(75.5) == 75.5

def test_normalize_hwb_string_numeric():
    assert normalize_hwb_value(" 75,5 ") == 75.5

def test_normalize_hwb_mj():
    # 270 MJ/m²a should be converted to 75.0 kWh/m²a (270 / 3.6 = 75.0)
    assert normalize_hwb_value("270 MJ/m²a") == 75.0

def test_normalize_hwb_none():
    assert normalize_hwb_value(None) is None
