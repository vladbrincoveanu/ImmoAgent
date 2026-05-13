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
