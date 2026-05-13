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
    extract_kitchen_included,
    extract_window_type,
    extract_ruecklage_eur_month,
    extract_maklerprovision_pct,
    extract_sonderumlage_risk,
    extract_doppelmakler,
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


class TestExtractSonderumlageRisk(unittest.TestCase):
    def test_positive(self):
        self.assertTrue(extract_sonderumlage_risk("eine sonderumlage für fassadensanierung ist geplant"))

    def test_negative_keine(self):
        self.assertFalse(extract_sonderumlage_risk("keine sonderumlage bekannt"))

    def test_negative_kein(self):
        self.assertFalse(extract_sonderumlage_risk("kein sonderumlage erwartet"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_sonderumlage_risk("schöne wohnung mit parkett und balkon"))


class TestExtractDoppelmakler(unittest.TestCase):
    def test_present(self):
        self.assertTrue(extract_doppelmakler("der vermittler ist als doppelmakler tätig"))

    def test_with_provision_context(self):
        self.assertTrue(extract_doppelmakler("doppelmakler tätig. 3% kundenprovision zzgl. mwst"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_doppelmakler("3% kundenprovision, keine weiteren kosten"))


class TestExtractRuecklageEurMonth(unittest.TestCase):
    def test_comma_decimal(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("monatliche reparaturrücklage (excl. mwst): 81,62 eur"),
            81.62, places=2
        )

    def test_dot_decimal(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("reparaturrücklage: 81.62 eur"),
            81.62, places=2
        )

    def test_thousands_separator(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("monatliche reparaturrücklage: 1.081,62 eur"),
            1081.62, places=2
        )

    def test_absent_returns_none(self):
        self.assertIsNone(extract_ruecklage_eur_month("monatliche betriebskosten: 281,75 eur"))


class TestExtractMaklerprovisionPct(unittest.TestCase):
    def test_integer_percent(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("3% kundenprovision zzgl. mwst"),
            3.0, places=1
        )

    def test_decimal_percent_comma(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("3,6% maklerprovision"),
            3.6, places=1
        )

    def test_provision_variant(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("käuferprovision: 2% zzgl. mwst"),
            2.0, places=1
        )

    def test_absent_returns_none(self):
        self.assertIsNone(extract_maklerprovision_pct("keine provision für käufer"))


class TestExtractKitchenIncluded(unittest.TestCase):
    def test_positive_einbaukueche(self):
        self.assertTrue(extract_kitchen_included("wohnung mit einbauküche und parkett"))

    def test_positive_moeblierte_kueche(self):
        self.assertTrue(extract_kitchen_included("möblierte küche inklusive aller geräte"))

    def test_negative_ohne_kueche(self):
        self.assertFalse(extract_kitchen_included("ohne küche, selbst einzurichten"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_kitchen_included("schöne 3-zimmer-wohnung mit parkett"))


class TestExtractWindowType(unittest.TestCase):
    def test_kastenfenster(self):
        self.assertEqual(extract_window_type("originale kastenfenster aus dem baujahr"), "kastenfenster")

    def test_kunststoff(self):
        self.assertEqual(extract_window_type("neue kunststofffenster eingebaut"), "kunststoff")

    def test_holz_alu(self):
        self.assertEqual(extract_window_type("holz-alu-fenster dreifach verglast"), "holz-alu")

    def test_isolierverglasung(self):
        self.assertEqual(extract_window_type("3-scheiben-isolierverglasung"), "isolierverglasung")

    def test_absent_returns_none(self):
        self.assertIsNone(extract_window_type("schöne 3-zimmer-wohnung mit parkett"))


if __name__ == '__main__':
    unittest.main()
