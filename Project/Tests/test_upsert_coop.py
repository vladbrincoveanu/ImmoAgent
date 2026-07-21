import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler():
    h = MongoDBHandler.__new__(MongoDBHandler)
    h.client = MagicMock()
    h.collection = MagicMock()
    return h


def _doc(**kw):
    d = {"url": "https://www.oevw.at/a", "source": "genossenschaft",
         "source_enum": "genossenschaft", "is_genossenschaft": True,
         "bezirk": "1100", "rooms": 3, "area_m2": 70.0,
         "price_total": None, "coop_source": "bautraeger_direct",
         "bautraeger": "ÖVW",
         # address required for compute_xsrc_fingerprint() to produce a key
         # (returns None without it) so the xsrc find_one is exercised.
         "address": "Musterstraße 1, 1100 Wien"}
    d.update(kw)
    return d


class TestUpsertCoopListing(unittest.TestCase):
    def test_inserts_new_listing_without_price(self):
        h = _handler()
        h.collection.find_one.return_value = None       # no xsrc, no url, no fp match
        status = h.upsert_coop_listing(_doc())
        self.assertEqual(status, "inserted")
        h.collection.insert_one.assert_called_once()

    def test_update_preserves_send_state(self):
        h = _handler()
        # first find_one (xsrc) -> None; second (by url) -> existing sent doc
        h.collection.find_one.side_effect = [
            None,
            {"_id": 42, "url": "https://www.oevw.at/a",
             "sent_to_telegram": True, "sent_to_telegram_at": 111.0},
        ]
        status = h.upsert_coop_listing(_doc())
        self.assertEqual(status, "updated")
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertTrue(replaced["sent_to_telegram"])           # not reset!
        self.assertEqual(replaced["sent_to_telegram_at"], 111.0)
        self.assertEqual(replaced["_id"], 42)

    def test_buyable_flag_persists_on_insert(self):
        # The dashboard's rentals-only view requires buyable:false to be stored.
        h = _handler()
        h.collection.find_one.return_value = None
        h.upsert_coop_listing(_doc(buyable=False))
        inserted = h.collection.insert_one.call_args[0][0]
        self.assertIs(inserted["buyable"], False)

    def test_buyable_flag_persists_on_xsrc_migration(self):
        # A mygewo rental (buyable:false) that matches an existing Willhaben row must
        # carry the rental flag onto it, else the buyable:false filter would hide it.
        h = _handler()
        h.collection.find_one.return_value = {
            "_id": 7, "url": "https://willhaben.at/x", "coop_source": "willhaben"}
        status = h.upsert_coop_listing(_doc(buyable=False))
        self.assertEqual(status, "duplicate")
        set_doc = h.collection.update_one.call_args[0][1]["$set"]
        self.assertIs(set_doc["buyable"], False)
        self.assertEqual(set_doc["coop_source"], "bautraeger_direct")

    def test_rejects_invalid_by_price_per_m2(self):
        h = _handler()
        # Co-op RENTALS are exempt from the purchase €/m² floor (see
        # is_valid_listing_data), so this must be a buyable unit — an actual
        # purchase — to still exercise the floor.
        # price_per_m2 = 10,000,000 — above any realistic GLOBAL_VALIDATION
        # max (robust regardless of the exact min, which could be 0).
        status = h.upsert_coop_listing(_doc(price_total=10_000_000.0, area_m2=1.0, buyable=True))
        self.assertEqual(status, "invalid")
        h.collection.insert_one.assert_not_called()


if __name__ == '__main__':
    unittest.main()
