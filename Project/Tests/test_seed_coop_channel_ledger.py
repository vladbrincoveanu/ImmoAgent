"""Seeding the co-op channel ledger from units already in Mongo.

Without it, switching the channel to the ledger would treat the entire existing
inventory as never-sent and flood both channels on the first poll after deploy.

The one assertion that matters more than the rest combined: a seeded key must be
byte-identical to the key the send loop computes for the same unit. If it drifts,
seeding suppresses nothing and the flood happens anyway — silently.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

import run_coop  # noqa: E402
from Domain.listing import Listing  # noqa: E402
from Domain.sources import Source  # noqa: E402
from scripts.seed_coop_channel_ledger import seed, seed_dedup_key  # noqa: E402
from test_coop_channel_ledger import (  # noqa: E402
    MYGEWO_CHAT, PRIVATE_CHAT, FakeLedger, _bot_factory, _handler, _poll)

UNIT = {
    "url": "https://mygewo.at/angebot/42",
    "bautraeger": "ÖVW",
    "address": "Musterstraße 1, 1100 Wien",
    "area_m2": 70.0,
    "rooms": 3,
    "is_genossenschaft": True,
}


def _listing(**kw):
    doc = dict(UNIT, **kw)
    return Listing(url=doc["url"], source=Source.GENOSSENSCHAFT,
                   is_genossenschaft=True, bezirk="1100",
                   rooms=doc["rooms"], area_m2=doc["area_m2"],
                   bautraeger=doc["bautraeger"], address=doc["address"])


class FakeSeedLedger(FakeLedger):
    """Adds the seed insert — same (chat_id, dedup_key) uniqueness."""

    def seed_row(self, chat_id, dedup_key, url):
        key = (chat_id, dedup_key)
        if key in self.rows:
            return False
        self.rows[key] = {"url": url, "sent": True}
        return True


def _seed_handler(ledger, docs):
    handler = _handler(ledger)
    handler.get_coop_listings_for_seed.return_value = docs
    handler.seed_channel_send.side_effect = ledger.seed_row
    return handler


class TestSeedKey(unittest.TestCase):
    def test_seed_key_equals_the_key_the_send_loop_computes(self):
        self.assertEqual(seed_dedup_key(UNIT),
                         run_coop.channel_dedup_key(_listing()))

    def test_stored_fingerprint_is_used_when_present(self):
        """The stored field is only written for is_genossenschaft units, so the
        computed fallback below is load-bearing, not decoration."""
        doc = dict(UNIT, content_fingerprint_xsrc="stored-key")
        self.assertEqual(seed_dedup_key(doc), "stored-key")

    def test_a_sparse_doc_does_not_raise(self):
        """Mongo omits absent fields entirely, so a doc need not carry area or
        rooms at all — and those sparse units are exactly the ones that depend on
        the url_hash fallback working."""
        doc = {"url": UNIT["url"], "is_genossenschaft": True}
        listing = _listing()
        listing.bautraeger = None
        listing.address = None
        self.assertEqual(seed_dedup_key(doc),
                         run_coop.channel_dedup_key(listing))

    def test_weak_key_falls_back_to_url_hash_on_both_sides(self):
        """No bautraeger ⇒ no fingerprint. Both sides must degrade identically."""
        doc = dict(UNIT, bautraeger=None)
        listing = _listing()
        listing.bautraeger = None
        self.assertEqual(seed_dedup_key(doc),
                         run_coop.channel_dedup_key(listing))


class TestSeed(unittest.TestCase):
    def test_every_unit_is_seeded_as_already_sent_on_both_channels(self):
        """Seeding one channel only would let the other flood."""
        ledger = FakeSeedLedger()
        handler = _seed_handler(ledger, [UNIT])

        with patch("scripts.seed_coop_channel_ledger.route",
                   side_effect=lambda kind: {"mygewo": MYGEWO_CHAT,
                                             "private_transfer": PRIVATE_CHAT}[kind]):
            self.assertEqual(seed(handler), 2)

        key = seed_dedup_key(UNIT)
        self.assertEqual(sorted(ledger.rows), sorted([(MYGEWO_CHAT, key),
                                                      (PRIVATE_CHAT, key)]))
        self.assertTrue(all(row["sent"] for row in ledger.rows.values()))

    def test_re_running_is_a_no_op(self):
        ledger = FakeSeedLedger()
        handler = _seed_handler(ledger, [UNIT])

        with patch("scripts.seed_coop_channel_ledger.route",
                   side_effect=lambda kind: {"mygewo": MYGEWO_CHAT,
                                             "private_transfer": PRIVATE_CHAT}[kind]):
            self.assertEqual(seed(handler), 2)
            self.assertEqual(seed(handler), 0)

        self.assertEqual(len(ledger.rows), 2)

    def test_missing_ledger_index_seeds_nothing(self):
        """Seeding without the unique index would insert duplicate rows that the
        send path then cannot rely on."""
        ledger = FakeSeedLedger(index_ready=False)
        handler = _seed_handler(ledger, [UNIT])

        self.assertEqual(seed(handler), 0)
        self.assertEqual(ledger.rows, {})

    def test_a_seeded_unit_is_not_re_sent_by_the_next_poll(self):
        """The whole point: no flood on deploy."""
        ledger = FakeSeedLedger()
        handler = _seed_handler(ledger, [UNIT])
        with patch("scripts.seed_coop_channel_ledger.route",
                   side_effect=lambda kind: {"mygewo": MYGEWO_CHAT,
                                             "private_transfer": PRIVATE_CHAT}[kind]):
            seed(handler)

        bots = _bot_factory()
        self.assertEqual(_poll(handler, [_listing()], bots), 0)

        self.assertEqual(
            sum(bot.send_message.call_count for bot in bots[0].values()), 0)

    def test_an_unseeded_unit_still_goes_out(self):
        """Seeding must suppress the backlog, not the feed."""
        ledger = FakeSeedLedger()
        handler = _seed_handler(ledger, [UNIT])
        with patch("scripts.seed_coop_channel_ledger.route",
                   side_effect=lambda kind: {"mygewo": MYGEWO_CHAT,
                                             "private_transfer": PRIVATE_CHAT}[kind]):
            seed(handler)

        fresh = _listing()
        fresh.url = "https://mygewo.at/angebot/43"
        fresh.address = "Andere Gasse 2, 1100 Wien"
        bots = _bot_factory()
        self.assertEqual(_poll(handler, [fresh], bots), 0)

        self.assertEqual(
            sum(bot.send_message.call_count for bot in bots[0].values()), 1)


class TestSeedHandlerQuery(unittest.TestCase):
    def test_seed_row_is_inserted_as_sent(self):
        from Integration.mongodb_handler import MongoDBHandler
        handler = MongoDBHandler.__new__(MongoDBHandler)
        handler.db = {"coop_channel_sends": MagicMock()}

        self.assertTrue(
            handler.seed_channel_send("-100", "k", "https://mygewo.at/angebot/1"))

        doc = handler.db["coop_channel_sends"].insert_one.call_args[0][0]
        self.assertTrue(doc["sent"])
        self.assertEqual(doc["dedup_key"], "k")

    def test_an_already_present_row_is_left_alone(self):
        import pymongo
        from Integration.mongodb_handler import MongoDBHandler
        handler = MongoDBHandler.__new__(MongoDBHandler)
        handler.db = {"coop_channel_sends": MagicMock()}
        handler.db["coop_channel_sends"].insert_one.side_effect = (
            pymongo.errors.DuplicateKeyError("dup"))

        self.assertFalse(handler.seed_channel_send("-100", "k", "https://x.at/a"))


if __name__ == '__main__':
    unittest.main()
