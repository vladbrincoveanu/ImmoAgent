import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.outreach.contact_extractor import classify_seller


class TestClassifySeller(unittest.TestCase):
    def test_private_seller_no_agency_markers(self):
        text = "Verkaufe meine Wohnung, Provisionsfrei, direkt vom Eigentümer."
        self.assertEqual(classify_seller(text, doppelmakler=None), 'private')

    def test_agency_seller(self):
        text = "Ihr Ansprechpartner: Max Mustermann, Immobilienmakler bei ImmoAT GmbH."
        self.assertEqual(classify_seller(text, doppelmakler=None), 'agency')

    def test_doppelmakler_true_forces_agency(self):
        # doppelmakler (dual-agent representation) always implies an agency is involved
        text = "Verkaufe meine Wohnung, Provisionsfrei."
        self.assertEqual(classify_seller(text, doppelmakler=True), 'agency')

    def test_no_signal_returns_unknown(self):
        self.assertEqual(classify_seller("", doppelmakler=None), 'unknown')


if __name__ == '__main__':
    unittest.main()
