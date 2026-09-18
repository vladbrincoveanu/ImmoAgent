import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from datetime import datetime, timedelta
from Integration.mongodb_handler import handle_fingerprint_match


class TestHandleFingerprintMatch(unittest.TestCase):
    def test_relist_after_taken(self):
        taken_at = datetime.utcnow() - timedelta(days=5)
        existing = {"_id": 1, "listing_status": "taken", "taken_at": taken_at,
                    "price_total": 250000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 260000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(update["listing_status"], "active")
        self.assertIsNone(update["taken_at"])
        self.assertEqual(update["times_relisted"], 1)
        self.assertEqual(len(update["relist_events"]), 1)
        event = update["relist_events"][0]
        self.assertEqual(event["delisted_at"], taken_at)
        self.assertEqual(event["price_at_relist"], 260000)
        self.assertGreaterEqual(event["days_off_market"], 4)  # ~5 days, allow clock skew

    def test_price_change_while_active_updates_history_no_relist(self):
        existing = {"_id": 2, "listing_status": "active", "taken_at": None,
                     "price_total": 300000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 295000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(len(update["price_history"]), 1)
        self.assertEqual(update["price_history"][0]["price_total"], 300000)
        self.assertNotIn("relist_events", update)  # untouched -> no key emitted
        self.assertEqual(update["price_total"], 295000)

    def test_no_price_change_no_history_entry(self):
        existing = {"_id": 3, "listing_status": "active", "taken_at": None,
                     "price_total": 300000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 300000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(update.get("price_history", []), [])


if __name__ == '__main__':
    unittest.main()
