"""The co-op CHANNEL must send each unit exactly once, and only units a live
alert actually asks for.

Why this file exists separately from test_run_coop.py: the `_mongo_mock` there is
a MagicMock whose `claim_*`/`mark_sent` always appear to succeed, so it cannot
express a unique index and is structurally blind to the bug class this suite
pins — the channel re-sending the same unit on every minutely poll.

Design: docs/superpowers/specs/2026-08-21-coop-channel-send-once-design.md
"""
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import run_coop  # noqa: E402
from Application.alert_matcher import match  # noqa: E402
from Domain.listing import Listing  # noqa: E402
from Domain.sources import Source  # noqa: E402
from Integration.mongodb_handler import MongoDBHandler  # noqa: E402

MYGEWO_CHAT = "-1001mygewo"
PRIVATE_CHAT = "-1001private"

# One permissive alert: the channel filter is now the union of active alerts, so
# without at least one the feed is silent by design (D6).
OPEN_ALERT = {"_id": "open", "kind": "keyword", "telegram_chat_id": "-100"}


def _l(**kw):
    """A co-op unit with a computable xsrc fingerprint (needs bautraeger+address)."""
    return Listing(
        url=kw.pop('url', 'https://mygewo.at/angebot/1'),
        source=kw.pop('source', Source.GENOSSENSCHAFT),
        is_genossenschaft=kw.pop('is_genossenschaft', True),
        bezirk=kw.pop('bezirk', '1100'),
        rooms=kw.pop('rooms', 3),
        area_m2=kw.pop('area_m2', 70.0),
        bautraeger=kw.pop('bautraeger', 'ÖVW'),
        address=kw.pop('address', 'Musterstraße 1, 1100 Wien'),
        **kw)


class FakeLedger:
    """`coop_channel_sends` with REAL duplicate-key semantics.

    Keyed on (chat_id, dedup_key) exactly like the unique index, so a second
    claim for the same unit in the same channel fails the way Mongo would."""

    def __init__(self, index_ready=True, write_fails=False):
        self.rows = {}
        self.index_ready = index_ready
        self.write_fails = write_fails

    def ensure(self):
        return self.index_ready

    def claim(self, chat_id, dedup_key, url):
        if self.write_fails:            # D5: a write error is a refusal, not a send
            return False
        key = (chat_id, dedup_key)
        if key in self.rows:
            return False
        self.rows[key] = {"url": url, "sent": False}
        return True

    def mark_sent(self, chat_id, dedup_key):
        row = self.rows.get((chat_id, dedup_key))
        if row:
            row["sent"] = True
        return bool(row)

    def release(self, chat_id, dedup_key):
        return self.rows.pop((chat_id, dedup_key), None) is not None


def _handler(ledger, upsert_result="duplicate", alerts=None):
    """A poll handler whose listings collection never yields a doc for the unit.

    `upsert_result="duplicate"` reproduces the production shape: the xsrc-dedup
    path returns without creating a doc at that url, so the old
    `get_listing(url).sent_to_telegram` gate could never latch."""
    h = MagicMock()
    h.collection = object()                       # not None → run() proceeds
    h.get_listing.return_value = None             # no doc at that url, ever
    h.get_listings_by_urls.return_value = {}
    h.upsert_coop_listing.return_value = upsert_result
    h.get_active_alerts.return_value = (
        [OPEN_ALERT] if alerts is None else alerts)
    h.ensure_channel_send_index.side_effect = ledger.ensure
    h.claim_channel_send.side_effect = ledger.claim
    h.mark_channel_send_sent.side_effect = ledger.mark_sent
    h.release_channel_send.side_effect = ledger.release
    return h


def _bot_factory():
    """One bot per chat id, so a per-channel assertion is possible."""
    made = {}

    def factory(token, chat_id):
        bot = made.get(chat_id)
        if bot is None:
            bot = MagicMock()
            bot.send_message.return_value = True
            made[chat_id] = bot
        return bot

    return made, factory


def _route(kind):
    return {"mygewo": MYGEWO_CHAT, "private_transfer": PRIVATE_CHAT}[kind]


def _poll(handler, listings, made_bots_factory, no_send=False):
    made, factory = made_bots_factory
    # A mygewo unit with unresolved builder_url/image_url would otherwise send a
    # live offer-page request from the test suite.
    with patch.object(run_coop.coop, "resolve_offer_details",
                      return_value={"builder_url": "", "image_url": ""}), \
            patch.object(run_coop.coop, "resolve_builder_image", return_value=""), \
            patch("run_coop.MongoDBHandler", return_value=handler), \
            patch("run_coop.poll_source", return_value=list(listings)), \
            patch("run_coop.validate_url", return_value=True), \
            patch("run_coop.route", side_effect=_route), \
            patch("run_coop.TelegramBot", side_effect=factory), \
            patch.object(run_coop, "deliver_user_alerts", return_value=0), \
            patch.dict(run_coop.coop.SOURCES,
                       {"T": {"url": "u", "parser": "p"}}, clear=True), \
            patch.dict(os.environ, {"TELEGRAM_MAIN_BOT_TOKEN": "tok",
                                    "WILLHABEN_PRIVATE_COOP": "0"}):
        return run_coop.run(no_send=no_send)


def _sends(made):
    return sum(bot.send_message.call_count for bot in made.values())


class TestSendOnce(unittest.TestCase):
    """The ledger, exercised through the poll entry point."""

    def test_duplicate_upsert_unit_is_sent_once_across_two_polls(self):
        """THE bug: upsert returns "duplicate" ⇒ no listings doc ⇒ the old
        sent_to_telegram gate passed forever ⇒ one message per minute."""
        ledger = FakeLedger()
        handler = _handler(ledger, upsert_result="duplicate")
        bots = _bot_factory()
        listing = _l(url="https://mygewo.at/angebot/dup")

        self.assertEqual(_poll(handler, [listing], bots), 0)
        self.assertEqual(_poll(handler, [listing], bots), 0)

        self.assertEqual(_sends(bots[0]), 1)

    def test_invalid_upsert_unit_is_sent_once_across_two_polls(self):
        ledger = FakeLedger()
        handler = _handler(ledger, upsert_result="invalid")
        bots = _bot_factory()
        listing = _l(url="https://mygewo.at/angebot/invalid")

        self.assertEqual(_poll(handler, [listing], bots), 0)
        self.assertEqual(_poll(handler, [listing], bots), 0)

        self.assertEqual(_sends(bots[0]), 1)

    def test_same_unit_under_two_urls_is_sent_once(self):
        """Pins the trap: `Listing.content_fingerprint_xsrc` is declared but never
        populated on the object. An implementation that READS it instead of
        COMPUTING it degrades every key to url_hash and this test fails."""
        ledger = FakeLedger()
        handler = _handler(ledger)
        bots = _bot_factory()
        mygewo = _l(url="https://mygewo.at/angebot/7")
        direct = _l(url="https://www.oevw.at/wohnung/7")

        self.assertEqual(_poll(handler, [mygewo, direct], bots), 0)

        self.assertEqual(_sends(bots[0]), 1)

    def test_unit_in_both_feeds_is_sent_once_per_channel(self):
        """D2: the ledger is unique per (chat_id, dedup_key), so a unit that
        legitimately appears in both feeds reaches both channels — once each."""
        ledger = FakeLedger()
        handler = _handler(ledger)
        made, factory = bots = _bot_factory()
        mygewo = _l(url="https://mygewo.at/angebot/9")
        private = _l(url="https://www.willhaben.at/iad/immobilien/d/9/",
                     source=Source.WILLHABEN, coop_kind="private_transfer")

        self.assertEqual(_poll(handler, [mygewo, private], bots), 0)
        self.assertEqual(_poll(handler, [mygewo, private], bots), 0)

        self.assertEqual(made[MYGEWO_CHAT].send_message.call_count, 1)
        self.assertEqual(made[PRIVATE_CHAT].send_message.call_count, 1)

    def test_ledger_write_failure_sends_nothing(self):
        """D5, fail closed: if the claim cannot be recorded, do not send. Spam can
        never recur, even while Mongo is degraded."""
        ledger = FakeLedger(write_fails=True)
        handler = _handler(ledger)
        bots = _bot_factory()

        self.assertEqual(_poll(handler, [_l()], bots), 0)

        self.assertEqual(_sends(bots[0]), 0)

    def test_missing_ledger_index_sends_nothing(self):
        """Without the unique index the claim is not a claim (D5)."""
        ledger = FakeLedger(index_ready=False)
        handler = _handler(ledger)
        bots = _bot_factory()

        self.assertEqual(_poll(handler, [_l()], bots), 0)

        self.assertEqual(_sends(bots[0]), 0)
        handler.claim_channel_send.assert_not_called()

    def test_send_failure_releases_the_claim_so_the_next_poll_retries(self):
        """A transient Telegram failure must not silence the unit forever."""
        ledger = FakeLedger()
        handler = _handler(ledger)
        made, factory = bots = _bot_factory()

        def failing(token, chat_id):
            bot = factory(token, chat_id)
            bot.send_message.return_value = False
            return bot

        listing = _l(url="https://mygewo.at/angebot/flaky")
        self.assertEqual(_poll(handler, [listing], (made, failing)), 0)
        self.assertEqual(ledger.rows, {})          # claim released

        for bot in made.values():
            bot.send_message.return_value = True
        self.assertEqual(_poll(handler, [listing], bots), 0)
        self.assertEqual(made[MYGEWO_CHAT].send_message.call_count, 2)

    def test_successful_send_marks_the_ledger_row_sent(self):
        ledger = FakeLedger()
        handler = _handler(ledger)
        bots = _bot_factory()

        self.assertEqual(_poll(handler, [_l()], bots), 0)

        self.assertEqual([row["sent"] for row in ledger.rows.values()], [True])

    def test_no_send_claims_nothing(self):
        """A dry run must not burn the one send a unit gets."""
        ledger = FakeLedger()
        handler = _handler(ledger)
        bots = _bot_factory()

        self.assertEqual(_poll(handler, [_l()], bots, no_send=True), 0)

        handler.claim_channel_send.assert_not_called()


class TestChannelFilter(unittest.TestCase):
    """D6/D7: the channel carries what live alerts ask for, strictly."""

    def test_zero_active_alerts_sends_nothing_and_warns(self):
        """Behaviour change from "send everything" — it must be loud."""
        ledger = FakeLedger()
        handler = _handler(ledger, alerts=[])
        bots = _bot_factory()

        with self.assertLogs("run_coop", level=logging.WARNING) as captured:
            self.assertEqual(_poll(handler, [_l()], bots), 0)

        self.assertEqual(_sends(bots[0]), 0)
        self.assertTrue(any("alert" in r.getMessage().lower()
                            for r in captured.records))

    def test_listing_no_alert_asks_for_is_not_broadcast(self):
        ledger = FakeLedger()
        handler = _handler(ledger, alerts=[
            {"_id": "a", "kind": "keyword", "keywords": ["Dachterrasse"],
             "telegram_chat_id": "-100"}])
        bots = _bot_factory()
        listing = _l(title="Wohnung ohne Freifläche")

        self.assertEqual(_poll(handler, [listing], bots), 0)

        self.assertEqual(_sends(bots[0]), 0)

    def test_strict_gate_excludes_unknown_area_from_the_channel_only(self):
        """D7: the channel excludes unverified matches; the per-user email path
        keeps delivering them flagged. Proves the strictness did not leak into
        the shared matcher."""
        alert = {"_id": "a", "kind": "keyword", "email": "u@x.at",
                 "confirmed": True, "filters": {"min_area": 50}}
        listing = _l(area_m2=None)

        self.assertFalse(run_coop.channel_match(alert, listing))

        delivered = match([listing], [alert])
        self.assertEqual(len(delivered), 1)
        self.assertTrue(delivered[0][2])            # unverified, still delivered

    def test_an_alert_with_no_deliverable_channel_still_governs_the_feed(self):
        """Filtering is not delivery: an alert with an unconfirmed email has no
        usable channel of its own but must still open the broadcast feed."""
        alert = {"_id": "a", "kind": "keyword", "email": "pending@x.at",
                 "confirmed": False}

        self.assertTrue(run_coop.channel_match(alert, _l()))

    def test_rubric_gate_is_applied(self):
        """A coop_private alert must not open the feed for a mygewo unit."""
        alert = {"_id": "a", "kind": "coop_private", "telegram_chat_id": "-100"}

        self.assertFalse(run_coop.channel_match(alert, _l()))
        self.assertTrue(run_coop.channel_match(
            alert, _l(coop_kind="private_transfer")))


class TestLedgerHandler(unittest.TestCase):
    """The three ledger methods, against a mocked pymongo collection."""

    def _handler_with_db(self):
        handler = MongoDBHandler.__new__(MongoDBHandler)
        handler.db = {"coop_channel_sends": MagicMock()}
        handler.collection = MagicMock()
        return handler

    def test_ensure_index_reports_failure(self):
        import pymongo
        handler = self._handler_with_db()
        handler.db["coop_channel_sends"].create_index.side_effect = (
            pymongo.errors.PyMongoError("no index"))

        self.assertFalse(handler.ensure_channel_send_index())

    def test_ensure_index_is_unique_on_chat_and_key(self):
        handler = self._handler_with_db()

        self.assertTrue(handler.ensure_channel_send_index())

        args, kwargs = handler.db["coop_channel_sends"].create_index.call_args
        self.assertEqual(args[0], [("chat_id", 1), ("dedup_key", 1)])
        self.assertTrue(kwargs["unique"])

    def test_second_claim_for_the_same_key_is_refused(self):
        import pymongo
        handler = self._handler_with_db()
        handler.db["coop_channel_sends"].insert_one.side_effect = (
            pymongo.errors.DuplicateKeyError("dup"))

        self.assertFalse(handler.claim_channel_send("-100", "k", "https://x.at/a"))

    def test_claim_write_error_is_refused_and_logged(self):
        import pymongo
        handler = self._handler_with_db()
        handler.db["coop_channel_sends"].insert_one.side_effect = (
            pymongo.errors.PyMongoError("mongo down"))

        with self.assertLogs("Integration.mongodb_handler",
                             level=logging.ERROR) as captured:
            self.assertFalse(
                handler.claim_channel_send("-100", "k", "https://x.at/a"))

        self.assertTrue(captured.records)

    def test_first_claim_is_granted(self):
        handler = self._handler_with_db()

        self.assertTrue(handler.claim_channel_send("-100", "k", "https://x.at/a"))

        doc = handler.db["coop_channel_sends"].insert_one.call_args[0][0]
        self.assertEqual(doc["chat_id"], "-100")
        self.assertEqual(doc["dedup_key"], "k")
        self.assertFalse(doc["sent"])

    def test_release_deletes_the_claim(self):
        handler = self._handler_with_db()
        handler.db["coop_channel_sends"].delete_one.return_value = MagicMock(
            deleted_count=1)

        self.assertTrue(handler.release_channel_send("-100", "k"))
        handler.db["coop_channel_sends"].delete_one.assert_called_once_with(
            {"chat_id": "-100", "dedup_key": "k"})


class TestMarkSentFailsLoud(unittest.TestCase):
    """`mark_sent` was a bare update_one whose matched_count was never checked —
    it wrote nothing and still logged success, which is how the gate it fed
    could pass forever."""

    def _handler(self):
        handler = MongoDBHandler.__new__(MongoDBHandler)
        handler.collection = MagicMock()
        return handler

    def test_no_matching_document_returns_false_and_logs_error(self):
        handler = self._handler()
        handler.collection.update_one.return_value = MagicMock(matched_count=0)

        with self.assertLogs(level=logging.ERROR) as captured:
            self.assertFalse(handler.mark_sent("https://x.at/missing"))

        self.assertTrue(captured.records)

    def test_matching_document_returns_true(self):
        handler = self._handler()
        handler.collection.update_one.return_value = MagicMock(matched_count=1)

        self.assertTrue(handler.mark_sent("https://x.at/present"))


if __name__ == '__main__':
    unittest.main()
