import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.helpers.geocoding import geocode_listing


class TestGeocodePrecision(unittest.TestCase):
    def test_exact_source_sets_10m_precision(self):
        listing = {"coordinates": {"lat": 48.2, "lon": 16.3}, "coordinate_source": "exact"}
        result = geocode_listing(listing)
        self.assertEqual(result['coordinate_precision_m'], 10)

    def test_landmark_source_sets_200m_precision(self):
        listing = {"coordinates": {"lat": 48.2, "lon": 16.3}, "coordinate_source": "landmark"}
        result = geocode_listing(listing)
        self.assertEqual(result['coordinate_precision_m'], 200)

    def test_none_source_sets_null_precision(self):
        listing = {"coordinate_source": "none"}
        result = geocode_listing(listing)
        self.assertIsNone(result['coordinate_precision_m'])


if __name__ == '__main__':
    unittest.main()
