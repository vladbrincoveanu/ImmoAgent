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


from unittest.mock import MagicMock, call


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


class TestPollSource(unittest.TestCase):
    def test_skips_parse_when_unchanged(self):
        handler = MagicMock()
        handler.get_source_meta.return_value = {"etag": "e1"}
        sess = MagicMock()
        sess.get.return_value = _resp(status=304)
        cfg = {"url": "https://x.at", "parser": "parse_oevw"}
        out = run_coop.poll_source("ÖVW", cfg, handler, session=sess)
        self.assertEqual(out, [])
        # A pure 304 carries no new headers → conditional_fetch returns {} →
        # existing stored meta is kept, so set_source_meta is NOT called.
        handler.set_source_meta.assert_not_called()

    def test_to_doc_stringifies_source_enum(self):
        from Domain.sources import Source
        d = run_coop._to_doc(_l(area_m2=70.0, price_total=350.0))
        self.assertEqual(d["source"], "genossenschaft")       # not the Enum
        self.assertEqual(d["source_enum"], "genossenschaft")
        self.assertAlmostEqual(d["price_per_m2"], 5.0)        # 350/70


from unittest.mock import patch


class TestPollSourceParse(unittest.TestCase):
    def test_parses_when_changed(self):
        handler = MagicMock()
        handler.get_source_meta.return_value = {}
        sess = MagicMock()
        sess.get.return_value = _resp(text="<html>new</html>", etag="e9")
        listing = _l()
        with patch.object(run_coop.coop, "parse_oevw", return_value=[listing], create=True):
            out = run_coop.poll_source(
                "ÖVW", {"url": "u", "parser": "parse_oevw"}, handler, session=sess)
        self.assertEqual(out, [listing])
        handler.set_source_meta.assert_called_once()   # new_meta present → persisted

    def test_fetcher_source_bypasses_the_change_gate(self):
        # The gate only hashes SSR page 0; a unit added on page 3 leaves it
        # byte-identical. A self-crawling fetcher must run regardless — and must
        # not spend a request on the gate at all.
        handler = MagicMock()
        handler.get_source_meta.return_value = {"page_hash": "same", "etag": "e1"}
        sess = MagicMock()
        listing = _l()
        with patch.object(run_coop.coop, "fetch_all_mygewo",
                          return_value=[listing], create=True) as fetcher:
            out = run_coop.poll_source(
                "mygewo", {"url": "u", "fetcher": "fetch_all_mygewo", "states": "28_"},
                handler, session=sess)
        self.assertEqual(out, [listing])
        fetcher.assert_called_once_with("28_")
        sess.get.assert_not_called()


def _mongo_mock(get_listing_ret=None):
    h = MagicMock()
    h.collection = object()          # not None → run() proceeds
    h.get_listing.return_value = get_listing_ret
    return h


def test_new_mygewo_listing_is_a_user_alert_candidate():
    handler = MagicMock()
    handler.get_listing.return_value = None
    listing = _l(url="https://mygewo.at/angebot/new")

    assert run_coop.new_alert_candidates(handler, [listing], []) == [listing]
    handler.get_listing.assert_called_once_with(listing.url)


def test_existing_mygewo_listing_is_not_a_new_user_alert_candidate():
    handler = MagicMock()
    handler.get_listing.return_value = {"_id": "existing"}
    listing = _l(url="https://mygewo.at/angebot/existing")

    assert run_coop.new_alert_candidates(handler, [listing], []) == []


def test_willhaben_candidates_are_included_and_duplicate_urls_are_removed():
    handler = MagicMock()
    handler.get_listing.return_value = None
    mygewo = _l(url="https://mygewo.at/angebot/new")
    willhaben = _l(url="https://www.willhaben.at/iad/immobilien/d/new/")
    duplicate_mygewo = _l(url=mygewo.url)
    duplicate_willhaben = _l(url=willhaben.url)

    candidates = run_coop.new_alert_candidates(
        handler, [mygewo, duplicate_mygewo], [willhaben, duplicate_willhaben])

    assert candidates == [mygewo, willhaben]
    assert handler.get_listing.call_args_list == [call(mygewo.url)]


@patch("run_coop.load_coop_alerts", return_value={})
@patch("run_coop.validate_url", return_value=True)
@patch("run_coop.poll_source")
@patch("run_coop.MongoDBHandler")
def test_user_alerts_run_before_mygewo_upsert(mongo, poll, validate, alerts):
    handler = _mongo_mock(get_listing_ret=None)
    events = []
    listing = _l(url="https://mygewo.at/angebot/new")
    listing.builder_url = ""
    listing.image_url = ""
    handler.upsert_coop_listing.side_effect = lambda doc: events.append("upsert")
    mongo.return_value = handler
    poll.return_value = [listing]

    with patch.object(
        run_coop, "deliver_user_alerts",
        side_effect=lambda h, candidates: events.append(("deliver", candidates)),
    ), patch.dict(run_coop.coop.SOURCES,
                  {"MYGEWO": {"url": "u", "fetcher": "fetch_all_mygewo"}},
                  clear=True), patch.dict(os.environ,
                                          {"WILLHABEN_PRIVATE_COOP": "0"}):
        assert run_coop.run(no_send=False) == 0

    assert events[0] == ("deliver", [listing])
    assert events[1] == "upsert"


class TestRun(unittest.TestCase):
    @patch("run_coop.MongoDBHandler")
    def test_aborts_when_no_mongo(self, MH):
        MH.return_value.collection = None
        self.assertEqual(run_coop.run(), 1)

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_no_send_upserts_and_counts_without_sending(self, MH, poll, vurl, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://x.at/new")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.upsert_coop_listing.assert_called_once()
        MH.return_value.mark_sent.assert_not_called()   # no-send never sends

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.TelegramBot")
    @patch("run_coop.MongoDBHandler")
    def test_sends_via_bot_and_marks_sent(self, MH, TB, poll, vurl, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        TB.return_value.send_message.return_value = True
        poll.return_value = [_l(url="https://x.at/s")]
        with patch.dict(os.environ,
                        {"TELEGRAM_MAIN_BOT_TOKEN": "t", "TELEGRAM_COOP_CHANNEL_ID": "c"}):
            with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
                rc = run_coop.run(no_send=False)
        self.assertEqual(rc, 0)
        TB.return_value.send_message.assert_called_once()
        MH.return_value.mark_sent.assert_called_once_with("https://x.at/s")

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.TelegramBot")
    @patch("run_coop.MongoDBHandler")
    def test_send_failure_does_not_mark_sent(self, MH, TB, poll, vurl, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        TB.return_value.send_message.return_value = False    # send failed
        poll.return_value = [_l(url="https://x.at/f")]
        with patch.dict(os.environ,
                        {"TELEGRAM_MAIN_BOT_TOKEN": "t", "TELEGRAM_COOP_CHANNEL_ID": "c"}):
            with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
                rc = run_coop.run(no_send=False)
        self.assertEqual(rc, 0)
        MH.return_value.mark_sent.assert_not_called()

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_skips_already_sent(self, MH, poll, alerts):
        MH.return_value = _mongo_mock(get_listing_ret={"sent_to_telegram": True})
        poll.return_value = [_l(url="https://x.at/dup")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.mark_sent.assert_not_called()

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=False)   # broken URL
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_broken_url_marked_invalid(self, MH, poll, vurl, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://x.at/broken")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.mark_url_invalid.assert_called_once_with("https://x.at/broken")

    @patch("run_coop.load_coop_alerts", return_value={"bezirke": ["9999"]})
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_filtered_out_listing_not_alerted(self, MH, poll, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://x.at/other", bezirk="1100")]  # not in 9999
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.get_listing.assert_not_called()   # filtered before send checks

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.poll_source", side_effect=RuntimeError("boom"))
    @patch("run_coop.MongoDBHandler")
    def test_all_adapters_fail_returns_1(self, MH, poll, alerts):
        MH.return_value = _mongo_mock()
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 1)
        MH.return_value.close.assert_called_once()


class TestMain(unittest.TestCase):
    @patch("run_coop.run", return_value=0)
    def test_main_exits_with_run_code(self, run_fn):
        with patch.object(sys, "argv", ["run_coop.py", "--dry-run"]):  # deprecated alias
            with self.assertRaises(SystemExit) as ctx:
                run_coop.main()
        self.assertEqual(ctx.exception.code, 0)
        run_fn.assert_called_once_with(no_send=True)


if __name__ == '__main__':
    unittest.main()


# --- photo re-probe versioning ------------------------------------------------
# v1 read og:image off the mygewo offer page, which carries none, so every unit
# stored the terminal "" and /coop showed a placeholder on every row. v2 hops to
# the builder page. The version marker is what keeps the retry to exactly once.

from run_coop import IMAGE_PROBE_V, maybe_reprobe_image  # noqa: E402


def test_unit_with_old_probe_version_is_reprobed_once():
    calls = []

    def fake_resolve(url):
        calls.append(url)
        return "https://cdn.builder.at/a.jpg"

    got = maybe_reprobe_image(
        {"builder_url": "https://www.gesiba.at/x", "image_url": "",
         "image_probe_v": 1}, fake_resolve)
    assert got["image_url"] == "https://cdn.builder.at/a.jpg"
    assert got["image_probe_v"] == IMAGE_PROBE_V
    assert len(calls) == 1


def test_unit_missing_probe_version_is_treated_as_v1():
    """Every unit already in Mongo predates the field entirely."""
    got = maybe_reprobe_image(
        {"builder_url": "https://www.gesiba.at/x", "image_url": ""},
        lambda url: "https://cdn.builder.at/b.jpg")
    assert got["image_url"] == "https://cdn.builder.at/b.jpg"
    assert got["image_probe_v"] == IMAGE_PROBE_V


def test_unit_at_current_probe_version_is_not_refetched():
    """Terminal within a version: no photo stays no photo, and costs no request."""
    calls = []
    got = maybe_reprobe_image(
        {"builder_url": "https://www.nhg.at/x", "image_url": "",
         "image_probe_v": IMAGE_PROBE_V}, lambda url: calls.append(url))
    assert got["image_url"] == ""
    assert calls == []


def test_reprobe_miss_is_terminal_at_new_version():
    """A v2 miss records "" and bumps the version, so it never retries again."""
    got = maybe_reprobe_image(
        {"builder_url": "https://www.nhg.at/x", "image_url": "",
         "image_probe_v": 1}, lambda url: None)
    assert got["image_url"] == ""
    assert got["image_probe_v"] == IMAGE_PROBE_V


def test_reprobe_skipped_without_builder_url():
    """No builder page to hop to — no request, and no version bump, so the unit
    stays eligible once its builder_url does resolve."""
    calls = []
    got = maybe_reprobe_image(
        {"builder_url": None, "image_url": "", "image_probe_v": 1},
        lambda url: calls.append(url))
    assert calls == []
    assert got.get("image_probe_v") == 1


# --- Willhaben private-coop adapter wiring ------------------------------------
# run() now polls Willhaben as well as mygewo. These tests must never touch the
# network, so the adapter is disabled by default for the whole module and
# enabled explicitly, with the crawl patched, where the wiring is under test.

def setUpModule():
    os.environ["WILLHABEN_PRIVATE_COOP"] = "0"


def tearDownModule():
    os.environ.pop("WILLHABEN_PRIVATE_COOP", None)


class TestWillhabenPrivateCoopWiring(unittest.TestCase):
    def setUp(self):
        os.environ["WILLHABEN_PRIVATE_COOP"] = "1"

    def tearDown(self):
        os.environ["WILLHABEN_PRIVATE_COOP"] = "0"

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_transfers_are_tagged_and_upserted(self, MH, poll, WS, crawl, vurl, alerts):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = []
        # The scraper is what classifies an ad; the poll only re-affirms the tag.
        transfer = _l(url="https://www.willhaben.at/iad/immobilien/d/x-1/")
        transfer.coop_kind = "private_transfer"
        crawl.return_value = [transfer]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        self.assertEqual(transfer.coop_kind, "private_transfer")
        MH.return_value.upsert_coop_listing.assert_called_once()

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_an_ordinary_rental_is_never_tagged_as_a_transfer(self, MH, poll, WS,
                                                              crawl, vurl, alerts):
        """The feed is now the whole newest-first rental list. Blanket-tagging it
        would route ordinary rentals into the private-Ablöse channel and corrupt
        /coop/private."""
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = []
        rental = _l(url="https://www.willhaben.at/iad/immobilien/d/y-2/")
        crawl.return_value = [rental]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        self.assertIsNone(rental.coop_kind)

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_ordinary_rentals_never_reach_the_coop_channel(self, MH, poll, WS,
                                                           crawl, vurl, alerts):
        """Without the co-op guard the mygewo channel would receive the entire
        Wien rental market, since `seen` now carries every new ad."""
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = []
        # A plain rental: the `_l` helper defaults is_genossenschaft=True, which
        # is exactly what this guard must NOT rely on being false by accident.
        rental = Listing(url="https://www.willhaben.at/iad/immobilien/d/y-2/",
                         source=Source.WILLHABEN, bezirk="1100", rooms=3,
                         area_m2=70.0, is_genossenschaft=False)
        crawl.return_value = [rental]
        bot = MagicMock()
        bot.send_message.return_value = True
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True), \
                patch("run_coop.route", return_value="-100"), \
                patch("run_coop.TelegramBot", return_value=bot), \
                patch.dict(os.environ, {"TELEGRAM_MAIN_BOT_TOKEN": "tok"}):
            rc = run_coop.run(no_send=False)
        self.assertEqual(rc, 0)
        bot.send_message.assert_not_called()

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest", side_effect=RuntimeError("blocked"))
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_willhaben_failure_does_not_fail_the_poll(self, MH, poll, WS, crawl,
                                                      vurl, alerts):
        """A Willhaben block must leave the mygewo half of the poll running."""
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://mygewo.at/angebot/1")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.upsert_coop_listing.assert_called_once()

    @patch("run_coop.load_coop_alerts", return_value={})
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source", side_effect=RuntimeError("mygewo down"))
    @patch("run_coop.MongoDBHandler")
    def test_willhaben_cannot_mask_a_total_mygewo_outage(self, MH, poll, WS, crawl,
                                                         alerts):
        """Every mygewo adapter failing is still exit 1, even if Willhaben works —
        otherwise a dead poll looks half-alive."""
        MH.return_value = _mongo_mock(get_listing_ret=None)
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 1)
        crawl.assert_not_called()


class TestDeliverUserAlerts(unittest.TestCase):
    """Alerts users create on /alerts, delivered from the poll."""

    def _handler(self, alerts):
        """A handler whose ledger is empty and whose claims always succeed —
        i.e. every pair is being delivered for the first time."""
        h = MagicMock()
        h.get_active_alerts.return_value = alerts
        h.claim_delivery.return_value = True
        h.stale_pending_deliveries.return_value = []
        return h

    @patch("Integration.telegram_bot.TelegramBot")
    def test_telegram_alert_is_delivered(self, TB):
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{"_id": "a", "keyword": "1100",
                                  "telegram_chat_id": "-100", "confirmed": True}])
        listing = _l(url="https://willhaben.at/x")
        listing.title = "Weitergabe 1100 Wien"
        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        TB.assert_called_once_with("tok", "-100")

    @patch("Integration.telegram_bot.TelegramBot")
    def test_non_matching_keyword_delivers_nothing(self, TB):
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{"_id": "a", "keyword": "garten",
                                  "telegram_chat_id": "-100", "confirmed": True}])
        listing = _l(url="https://willhaben.at/x")
        listing.title = "Weitergabe ohne Freiflaeche"
        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 0)
        TB.return_value.send_message.assert_not_called()

    @patch("Application.alert_email.send_alert_email", return_value=True)
    def test_confirmed_email_alert_is_delivered(self, mail):
        handler = self._handler([{"_id": "a", "keyword": "", "email": "u@x.at",
                                  "telegram_chat_id": None, "confirmed": True}])
        listing = _l(url="https://willhaben.at/x")
        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        mail.assert_called_once()

    @patch("Application.alert_email.send_alert_email")
    def test_unconfirmed_email_is_never_mailed(self, mail):
        """Anyone can type someone else's address into the form."""
        handler = self._handler([{"_id": "a", "keyword": "", "email": "victim@x.at",
                                  "telegram_chat_id": None, "confirmed": False}])
        self.assertEqual(
            run_coop.deliver_user_alerts(handler, [_l(url="https://willhaben.at/x")]), 0)
        mail.assert_not_called()

    def test_alert_load_failure_does_not_raise(self):
        """A broken alert lookup must not fail the poll that feeds the website."""
        h = MagicMock()
        h.get_active_alerts.side_effect = RuntimeError("mongo down")
        self.assertEqual(
            run_coop.deliver_user_alerts(h, [_l(url="https://willhaben.at/x")]), 0)

    @patch("Integration.telegram_bot.TelegramBot", side_effect=RuntimeError("telegram down"))
    def test_send_failure_is_swallowed(self, TB):
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{"_id": "a", "keyword": "",
                                  "telegram_chat_id": "-100", "confirmed": True}])
        self.assertEqual(
            run_coop.deliver_user_alerts(handler, [_l(url="https://willhaben.at/x")]), 0)

    @patch("Integration.telegram_bot.TelegramBot")
    def test_an_already_claimed_pair_is_not_sent_again(self, TB):
        """The ledger, from the poll's point of view: a pair another poll already
        owns must produce no second message."""
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{"_id": "a", "keyword": "",
                                  "telegram_chat_id": "-100", "confirmed": True}])
        handler.claim_delivery.return_value = False
        self.assertEqual(
            run_coop.deliver_user_alerts(handler, [_l(url="https://willhaben.at/x")]), 0)
        TB.return_value.send_message.assert_not_called()

    @patch("Integration.telegram_bot.TelegramBot")
    def test_a_pending_row_from_a_dead_poll_is_retried(self, TB):
        """The at-least-once guarantee, exercised through the poll entry point."""
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{"_id": "a", "keyword": "",
                                  "telegram_chat_id": "-100", "confirmed": True}])
        handler.stale_pending_deliveries.return_value = [
            {"alert_id": "a", "url_hash": "h1", "chat_id": "-100",
             "message": "verlorene Anzeige"},
        ]
        # No new listings at all — the only delivery possible is the recovered one.
        self.assertEqual(run_coop.deliver_user_alerts(handler, []), 1)
        handler.mark_delivery_sent.assert_called_once_with("a", "h1")
