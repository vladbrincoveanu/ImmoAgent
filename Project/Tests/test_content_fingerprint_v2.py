import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.helpers.listing_validator import compute_content_fingerprint_v2


class TestContentFingerprintV2(unittest.TestCase):
    def test_stable_across_title_edit(self):
        base = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100",
                "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben",
                "title": "Schöne 3-Zimmer Wohnung"}
        edited = dict(base, title="TOP Schöne 3-Zimmer Wohnung mit Balkon!!")
        self.assertEqual(compute_content_fingerprint_v2(base), compute_content_fingerprint_v2(edited))

    def test_differs_by_address(self):
        a = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100", "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben"}
        b = dict(a, address="Musterstraße 2, 1100 Wien")
        self.assertNotEqual(compute_content_fingerprint_v2(a), compute_content_fingerprint_v2(b))

    def test_falls_back_to_title_when_no_address(self):
        d = {"bezirk": "1100", "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben", "title": "Nice flat"}
        fp = compute_content_fingerprint_v2(d)
        self.assertIsInstance(fp, str)
        self.assertEqual(len(fp), 32)  # md5 hex digest

    def test_rounds_area_to_nearest_m2(self):
        a = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100", "area_m2": 70.2, "rooms": 3, "source_enum": "willhaben"}
        b = dict(a, area_m2=70.4)
        self.assertEqual(compute_content_fingerprint_v2(a), compute_content_fingerprint_v2(b))


if __name__ == '__main__':
    unittest.main()
