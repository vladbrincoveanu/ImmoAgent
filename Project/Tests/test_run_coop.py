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


from unittest.mock import MagicMock


def _resp(status=200, text="<html>body</html>", etag=None, last_modified=None):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.headers = {}
    if etag:
        r.headers["ETag"] = etag
    if last_modified:
        r.headers["Last-Modified"] = last_modified
    r.raise_for_status = MagicMock()
    return r


class TestConditionalFetch(unittest.TestCase):
    def test_304_reports_unchanged(self):
        sess = MagicMock()
        sess.get.return_value = _resp(status=304)
        changed, html, meta = run_coop.conditional_fetch(
            "https://x.at", {"etag": "e1"}, session=sess)
        self.assertFalse(changed)
        self.assertIsNone(html)
        # If-None-Match sent
        self.assertEqual(sess.get.call_args.kwargs["headers"]["If-None-Match"], "e1")

    def test_same_hash_reports_unchanged(self):
        sess = MagicMock()
        sess.get.return_value = _resp(text="<html>same</html>")
        prev = {"page_hash": run_coop._page_hash("<html>same</html>")}
        changed, html, meta = run_coop.conditional_fetch("https://x.at", prev, session=sess)
        self.assertFalse(changed)

    def test_new_body_reports_changed_with_new_meta(self):
        sess = MagicMock()
        sess.get.return_value = _resp(text="<html>fresh</html>", etag="e2", last_modified="Mon")
        changed, html, meta = run_coop.conditional_fetch("https://x.at", {}, session=sess)
        self.assertTrue(changed)
        self.assertEqual(html, "<html>fresh</html>")
        self.assertEqual(meta["etag"], "e2")
        self.assertEqual(meta["last_modified"], "Mon")
        self.assertEqual(meta["page_hash"], run_coop._page_hash("<html>fresh</html>"))


if __name__ == '__main__':
    unittest.main()
