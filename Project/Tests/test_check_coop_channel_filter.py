"""The channel-filter diagnostic must report the REAL filter, not a re-derivation.

Its whole value is answering "will my Telegram carry only the alert I set?"
against production data, so anything it computes itself is a chance to disagree
with `run_coop` and reassure the owner about a channel that then misbehaves.
These tests pin the two places it could drift: how a stored Mongo doc becomes
something the matcher can read, and the verdict it prints per alert.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_coop_channel_filter import (  # noqa: E402
    describe_alert, doc_to_unit, preview)


def _doc(**kw):
    doc = {"url": "https://mygewo.at/angebot/1", "bezirk": "1100",
           "rooms": 3, "area_m2": 70.0, "title": "Schöne Wohnung",
           "address": "Musterstraße 1, 1100 Wien"}
    doc.update(kw)
    return doc


class TestDocToUnit(unittest.TestCase):

    def test_description_is_carried_so_body_keywords_match(self):
        """The body is where "Nachmieter gesucht" and the district actually live;
        a unit built without it silently under-reports every keyword alert."""
        unit = doc_to_unit(_doc(description="Nachmieter gesucht, Ablöse VB"))

        self.assertIn("nachmieter", (unit.description or "").lower())

    def test_absent_fields_become_none_not_attribute_errors(self):
        """Mongo omits absent fields entirely. `SimpleNamespace(**doc)` would
        raise on exactly the sparse units whose gates most need evaluating."""
        unit = doc_to_unit({"url": "https://mygewo.at/x"})

        self.assertIsNone(unit.area_m2)
        self.assertIsNone(unit.rooms)
        self.assertIsNone(unit.coop_kind)

    def test_coop_kind_is_carried_so_the_rubric_gate_works(self):
        unit = doc_to_unit(_doc(coop_kind="private_transfer"))

        self.assertEqual(unit.coop_kind, "private_transfer")


class TestDescribeAlert(unittest.TestCase):

    def test_an_unconstrained_alert_is_reported_as_not_governing(self):
        """The headline the owner needs: this row does NOT filter the channel."""
        row = describe_alert({"_id": "a", "kind": "keyword"})

        self.assertFalse(row["governs"])

    def test_null_gates_are_not_listed_as_gates(self):
        """`{"min_area": None}` is the old all-null firehose, not a filter, and
        printing it as one would tell the owner the channel is narrowed when it
        is not."""
        row = describe_alert({"_id": "a", "kind": "keyword",
                              "keywords": ["dachterrasse"],
                              "filters": {"min_area": None, "max_price": 900}})

        self.assertEqual(row["gates"], {"max_price": 900})

    def test_a_constrained_alert_governs(self):
        row = describe_alert({"_id": "a", "kind": "keyword",
                              "keywords": ["Dachterrasse"]})

        self.assertTrue(row["governs"])
        self.assertEqual(row["keywords"], ["dachterrasse"])

    def test_a_coop_private_alert_governs_without_keywords(self):
        row = describe_alert({"_id": "a", "kind": "coop_private"})

        self.assertTrue(row["governs"])


class TestPreview(unittest.TestCase):

    def test_a_unit_is_attributed_to_every_alert_that_admits_it(self):
        """Attribution, not a bare count: "which of my alerts pulled this in" is
        the question asked when an unexpected unit shows up on the channel."""
        alerts = [{"_id": "wanted", "kind": "keyword", "keywords": ["wien"]},
                  {"_id": "other", "kind": "keyword", "keywords": ["graz"]}]

        rows = preview([_doc()], alerts)

        self.assertEqual([r["matched_by"] for r in rows], [["wanted"]])

    def test_a_unit_no_alert_admits_is_reported_with_no_match(self):
        """Excluded units must still appear, or the report cannot distinguish
        "correctly filtered out" from "never scraped"."""
        alerts = [{"_id": "other", "kind": "keyword", "keywords": ["graz"]}]

        rows = preview([_doc()], alerts)

        self.assertEqual(rows[0]["matched_by"], [])
        self.assertFalse(rows[0]["would_send"])

    def test_an_unconstrained_alert_admits_nothing_in_the_preview(self):
        """The preview must agree with `run_coop.channel_match`, which refuses a
        catch-all alert. If it disagreed, the report would predict a flood that
        the poller will not produce — or worse, the reverse."""
        rows = preview([_doc()], [{"_id": "catchall", "kind": "keyword"}])

        self.assertEqual(rows[0]["matched_by"], [])

    def test_a_gate_the_unit_cannot_verify_is_excluded_from_the_channel(self):
        """The channel takes `passes and not unverified`. A unit with unknown
        area must show as NOT broadcast even though the per-user path would
        deliver it flagged."""
        alerts = [{"_id": "a", "kind": "keyword", "filters": {"min_area": 50}}]

        rows = preview([_doc(area_m2=None)], alerts)

        self.assertFalse(rows[0]["would_send"])


if __name__ == '__main__':
    unittest.main()
