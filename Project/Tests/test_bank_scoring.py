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
    m.hwb_value = kwargs.get('hwb_value', None)
    m.condition = kwargs.get('condition', None)
    m.title = kwargs.get('title', None)
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


if __name__ == '__main__':
    unittest.main()
