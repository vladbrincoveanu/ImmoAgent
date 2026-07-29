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
        self.assertEqual(status, "updated")
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertIs(replaced["buyable"], False)
        self.assertEqual(replaced["coop_source"], "bautraeger_direct")
        self.assertEqual(replaced["_id"], 7)

    def test_xsrc_migration_refreshes_all_fields_and_keeps_send_state(self):
        # The migration used to $set only 4 fields, so rent/area/features stayed
        # frozen at the Willhaben values forever. It must replace wholesale —
        # while still carrying send-state so no re-spam.
        h = _handler()
        h.collection.find_one.return_value = {
            "_id": 7, "url": "https://willhaben.at/x", "coop_source": "willhaben",
            "area_m2": 55.0, "price_total": 999.0, "sent_to_telegram": True,
            "sent_to_telegram_at": 111.0, "builder_url": "https://oevw.at/old"}
        status = h.upsert_coop_listing(_doc(area_m2=70.0, buyable=False))
        self.assertEqual(status, "updated")
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertEqual(replaced["area_m2"], 70.0)             # fresh, not 55
        self.assertEqual(replaced["url"], "https://www.oevw.at/a")
        self.assertTrue(replaced["sent_to_telegram"])            # not reset!
        self.assertEqual(replaced["sent_to_telegram_at"], 111.0)
        self.assertEqual(replaced["builder_url"], "https://oevw.at/old")  # kept

    def test_xsrc_match_from_willhaben_never_downgrades_a_direct_row(self):
        h = _handler()
        h.collection.find_one.return_value = {
            "_id": 8, "url": "https://oevw.at/a", "coop_source": "bautraeger_direct"}
        status = h.upsert_coop_listing(
            _doc(url="https://willhaben.at/y", coop_source="willhaben"))
        self.assertEqual(status, "duplicate")
        h.collection.replace_one.assert_not_called()

    def test_coop_uid_match_updates_in_place_even_when_the_url_changed(self):
        # A unit's url flips between the mygewo /angebot/ page and the builder's
        # project page as it moves across result pages. Identity must survive
        # that, or every page shuffle forks a duplicate document.
        h = _handler()
        h.collection.find_one.return_value = {
            "_id": 5, "url": "https://mygewo.at/angebot/old", "coop_uid": "mygewo:u1",
            "sent_to_telegram": True}
        status = h.upsert_coop_listing(_doc(coop_uid="mygewo:u1"))
        self.assertEqual(status, "updated")
        h.collection.find_one.assert_called_once_with({"coop_uid": "mygewo:u1"})
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertEqual(replaced["_id"], 5)
        self.assertTrue(replaced["sent_to_telegram"])            # no re-spam

    def test_sibling_unit_is_not_swallowed_by_its_neighbours_fingerprint(self):
        # THE regression: two flats in one project share address/area/rooms and
        # the project reservation url. The xsrc key cannot tell them apart, so
        # coop_uid must — otherwise the second is logged as a duplicate and lost.
        h = _handler()
        neighbour = {"_id": 9, "url": "https://www.oevw.at/projekt#mygewo-u1",
                     "coop_uid": "mygewo:u1", "coop_source": "bautraeger_direct"}
        h.collection.find_one.side_effect = [
            None,        # by coop_uid: this unit is new
            neighbour,   # by xsrc fingerprint: its identical neighbour
            None,        # by url
            neighbour,   # by content fingerprint: the neighbour again
        ]
        status = h.upsert_coop_listing(
            _doc(coop_uid="mygewo:u2", url="https://www.oevw.at/projekt#mygewo-u2"))
        self.assertEqual(status, "inserted")
        h.collection.insert_one.assert_called_once()
        h.collection.replace_one.assert_not_called()

    def test_legacy_row_without_a_uid_is_adopted_not_duplicated(self):
        # Rows stored before coop_uid existed must be taken over on the next
        # poll — dropping them as duplicates would strand their send-state.
        h = _handler()
        h.collection.find_one.side_effect = [
            None,
            {"_id": 11, "url": "https://www.oevw.at/legacy",
             "coop_source": "bautraeger_direct", "sent_to_telegram": True},
        ]
        status = h.upsert_coop_listing(_doc(coop_uid="mygewo:u3"))
        self.assertEqual(status, "updated")
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertEqual(replaced["_id"], 11)
        self.assertEqual(replaced["coop_uid"], "mygewo:u3")
        self.assertTrue(replaced["sent_to_telegram"])

    def test_shared_project_url_does_not_overwrite_a_sibling(self):
        # Even if two units end up on one url, a row already claimed by another
        # uid must not be replaced — that was the silent overwrite.
        h = _handler()
        h.collection.find_one.side_effect = [
            None,                                            # by coop_uid
            None,                                            # by xsrc
            {"_id": 12, "url": "https://www.oevw.at/a", "coop_uid": "mygewo:other"},
            None,                                            # by content fp
        ]
        status = h.upsert_coop_listing(_doc(coop_uid="mygewo:u4"))
        self.assertEqual(status, "inserted")
        h.collection.replace_one.assert_not_called()

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
