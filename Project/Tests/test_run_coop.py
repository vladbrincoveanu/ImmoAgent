import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Domain.listing import Listing
from Domain.sources import Source
import run_coop


def _l(**kw):
    return Listing(url=kw.pop('url', 'https://x.at/a'), source=Source.GENOSSENSCHAFT,
                   is_genossenschaft=True, bezirk=kw.pop('bezirk', '1100'),
                   rooms=kw.pop('rooms', 3), area_m2=kw.pop('area_m2', 70.0),
                   price_total=kw.pop('price_total', None), **kw)


class TestMatchesCoopAlerts(unittest.TestCase):
    def test_empty_filter_sends_all(self):
        self.assertTrue(run_coop.matches_coop_alerts(_l(), {}))

    def test_bezirk_include_and_exclude(self):
        self.assertTrue(run_coop.matches_coop_alerts(_l(bezirk='1100'), {"bezirke": ["1100", "1200"]}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(bezirk='1010'), {"bezirke": ["1100"]}))

    def test_missing_listing_field_is_permissive(self):
        # filter wants min_rooms=3 but listing has unknown rooms -> included
        self.assertTrue(run_coop.matches_coop_alerts(_l(rooms=None), {"min_rooms": 3}))
        # filter wants a bezirk but listing has none -> included
        self.assertTrue(run_coop.matches_coop_alerts(_l(bezirk=None), {"bezirke": ["1100"]}))

    def test_min_rooms_min_area_max_cost(self):
        self.assertFalse(run_coop.matches_coop_alerts(_l(rooms=2), {"min_rooms": 3}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(area_m2=40), {"min_area": 50}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(price_total=500), {"max_cost": 400}))
        self.assertTrue(run_coop.matches_coop_alerts(_l(rooms=3, area_m2=70, price_total=300),
                                                     {"min_rooms": 3, "min_area": 50, "max_cost": 400}))


class TestLoadCoopAlerts(unittest.TestCase):
    def test_env_override_wins(self):
        os.environ["COOP_ALERTS"] = '{"min_rooms": 2}'
        try:
            self.assertEqual(run_coop.load_coop_alerts().get("min_rooms"), 2)
        finally:
            del os.environ["COOP_ALERTS"]

    def test_bad_env_falls_through_to_dict(self):
        os.environ["COOP_ALERTS"] = 'not-json'
        try:
            self.assertIsInstance(run_coop.load_coop_alerts(), dict)  # no crash
        finally:
            del os.environ["COOP_ALERTS"]


if __name__ == '__main__':
    unittest.main()
