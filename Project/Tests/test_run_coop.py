import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
import unittest
from Domain.listing import Listing
from Domain.sources import Source
import run_coop


def _l(**kw):
    return Listing(url=kw.pop('url', 'https://x.at/a'), source=Source.GENOSSENSCHAFT,
                   is_genossenschaft=True, bezirk=kw.pop('bezirk', '1100'),
                   rooms=kw.pop('rooms', 3), area_m2=kw.pop('area_m2', 70.0),
                   price_total=kw.pop('price_total', None), **kw)


# The static `coop_alerts.json` filter is gone: every field in it was null in
# CI, so it matched everything and the channel was a firehose. The channel filter
# is now the union of active alerts — see Tests/test_coop_channel_ledger.py.

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


def _mongo_mock(get_listing_ret=None, alerts=None):
    h = MagicMock()
    h.collection = object()          # not None → run() proceeds
    h.get_listing.return_value = get_listing_ret
    h.get_listings_by_urls.return_value = {}
    # One key-less alert = "everything on this feed", which is what these tests
    # assumed before the channel filter existed. Zero alerts now means silence.
    h.get_alert_subscriptions.return_value = (
        [{"_id": "t", "kind": "keyword", "telegram_chat_id": "-100"}]
        if alerts is None else alerts)
    return h


def test_get_listings_by_urls_returns_url_map():
    handler = run_coop.MongoDBHandler.__new__(run_coop.MongoDBHandler)
    handler.collection = MagicMock()
    first = {"url": "https://mygewo.at/angebot/1", "_id": "one"}
    second = {"url": "https://mygewo.at/angebot/2", "_id": "two"}
    handler.collection.find.return_value = [first, second]

    assert handler.get_listings_by_urls(
        [first["url"], first["url"], "", second["url"]]
    ) == {first["url"]: first, second["url"]: second}
    handler.collection.find.assert_called_once_with(
        {"url": {"$in": [first["url"], second["url"]]}}
    )


def test_get_listings_by_urls_returns_none_on_query_failure():
    handler = run_coop.MongoDBHandler.__new__(run_coop.MongoDBHandler)
    handler.collection = MagicMock()
    handler.collection.find.side_effect = RuntimeError("mongo down")

    assert handler.get_listings_by_urls(["https://mygewo.at/angebot/1"]) is None


def test_new_mygewo_listing_is_a_user_alert_candidate():
    handler = MagicMock()
    handler.get_listings_by_urls.return_value = {}
    listing = _l(url="https://mygewo.at/angebot/new")

    assert run_coop.new_alert_candidates(handler, [listing], []) == [listing]
    handler.get_listings_by_urls.assert_called_once_with([listing.url])
    handler.get_listing.assert_not_called()


def test_existing_mygewo_listing_is_not_a_new_user_alert_candidate():
    handler = MagicMock()
    listing = _l(url="https://mygewo.at/angebot/existing")
    handler.get_listings_by_urls.return_value = {
        listing.url: {"_id": "existing"}
    }

    assert run_coop.new_alert_candidates(handler, [listing], []) == []


def test_willhaben_candidates_are_included_and_duplicate_urls_are_removed():
    handler = MagicMock()
    handler.get_listings_by_urls.return_value = {}
    mygewo = _l(url="https://mygewo.at/angebot/new")
    willhaben = _l(url="https://www.willhaben.at/iad/immobilien/d/new/")
    duplicate_mygewo = _l(url=mygewo.url)
    duplicate_willhaben = _l(url=willhaben.url)

    candidates = run_coop.new_alert_candidates(
        handler, [mygewo, duplicate_mygewo], [willhaben, duplicate_willhaben])

    assert candidates == [willhaben, mygewo]
    assert handler.get_listings_by_urls.call_args_list == [call([mygewo.url])]


def test_batch_lookup_failure_excludes_mygewo_but_keeps_willhaben_candidates():
    handler = MagicMock()
    handler.get_listings_by_urls.return_value = None
    mygewo = _l(url="https://mygewo.at/angebot/unknown")
    willhaben = _l(url="https://www.willhaben.at/iad/immobilien/d/new/")

    assert run_coop.new_alert_candidates(handler, [mygewo], [willhaben]) == [willhaben]
    handler.get_listings_by_urls.assert_called_once_with([mygewo.url])
    handler.get_listing.assert_not_called()


@patch("run_coop.validate_url", return_value=True)
@patch("run_coop.poll_source")
@patch("run_coop.MongoDBHandler")
def test_user_alerts_run_before_mygewo_upsert(mongo, poll, validate):
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


def test_batch_existing_docs_are_reused_during_mygewo_detail_processing():
    handler = _mongo_mock(get_listing_ret=None)
    new_listing = _l(url="https://mygewo.at/angebot/new")
    new_listing.builder_url = ""
    new_listing.image_url = ""
    existing_listing = _l(url="https://mygewo.at/angebot/existing")
    existing_doc = {
        "builder_url": "https://builder.at/offer/existing",
        "image_url": "https://cdn.builder.at/existing.jpg",
        "image_probe_v": run_coop.IMAGE_PROBE_V,
    }
    handler.get_listings_by_urls.return_value = {
        existing_listing.url: existing_doc
    }
    events = []

    with patch.object(
        run_coop, "deliver_user_alerts",
        side_effect=lambda h, candidates: events.append(("deliver", candidates)),
    ), patch.object(run_coop.coop, "resolve_offer_details") as resolve_details, \
            patch.object(run_coop.coop, "resolve_builder_image") as resolve_image, \
            patch.dict(run_coop.coop.SOURCES,
                       {"MYGEWO": {"url": "u", "fetcher": "fetch_all_mygewo"}},
                       clear=True), patch.dict(os.environ,
                                               {"WILLHABEN_PRIVATE_COOP": "0"}):
        handler.upsert_coop_listing.side_effect = (
            lambda doc: events.append(("upsert", doc["url"]))
        )
        with patch("run_coop.MongoDBHandler", return_value=handler), \
                patch("run_coop.poll_source", return_value=[new_listing,
                                                            existing_listing]):
            assert run_coop.run(no_send=False) == 0

    assert events[0] == ("deliver", [new_listing])
    assert events[1:] == [
        ("upsert", new_listing.url), ("upsert", existing_listing.url)
    ]
    handler.get_listings_by_urls.assert_called_once_with(
        [new_listing.url, existing_listing.url]
    )
    resolve_details.assert_not_called()
    resolve_image.assert_not_called()


def test_mygewo_lookup_failure_defers_mygewo_but_keeps_willhaben_processing():
    handler = _mongo_mock(get_listing_ret=None)
    handler.get_listings_by_urls.return_value = None
    mygewo = _l(url="https://mygewo.at/angebot/deferred")
    willhaben = Listing(
        url="https://www.willhaben.at/iad/immobilien/d/transfer-1/",
        source=Source.WILLHABEN,
        bezirk="1100",
        rooms=3,
        area_m2=70.0,
        is_genossenschaft=False,
    )
    willhaben.coop_kind = "private_transfer"
    bot = MagicMock()
    bot.send_message.return_value = True
    events = []

    with patch.object(
        run_coop, "deliver_user_alerts",
        side_effect=lambda h, candidates: events.append(("deliver", candidates)),
    ), patch.object(run_coop.coop, "resolve_offer_details",
                    side_effect=AssertionError("mygewo details must be deferred")), \
            patch("run_coop.MongoDBHandler", return_value=handler), \
            patch("run_coop.poll_source", return_value=[mygewo]), \
            patch("run_coop.crawl_newest", return_value=[willhaben]), \
            patch("run_coop.WillhabenScraper"), \
            patch("run_coop.validate_url", return_value=True) as validate, \
            patch("run_coop.route", return_value="-100"), \
            patch("run_coop.TelegramBot", return_value=bot), \
            patch.dict(run_coop.coop.SOURCES,
                       {"MYGEWO": {"url": "u", "fetcher": "fetch_all_mygewo"}},
                       clear=True), patch.dict(os.environ, {
                           "WILLHABEN_PRIVATE_COOP": "1",
                           "TELEGRAM_MAIN_BOT_TOKEN": "tok",
                       }):
        handler.upsert_coop_listing.side_effect = (
            lambda doc: events.append(("upsert", doc["url"]))
        )
        assert run_coop.run(no_send=False) == 0

    assert events[0] == ("deliver", [willhaben])
    assert events[1:] == [("upsert", willhaben.url)]
    bot.send_message.assert_called_once()
    validate.assert_called_once_with(willhaben.url)
    handler.upsert_coop_listing.assert_called_once()


def test_no_send_skips_candidate_lookup_and_user_delivery():
    handler = _mongo_mock(get_listing_ret=None)
    listing = _l(url="https://mygewo.at/angebot/dry-run")
    listing.builder_url = ""
    listing.image_url = ""

    with patch.object(run_coop, "new_alert_candidates") as candidates, \
            patch.object(run_coop, "deliver_user_alerts") as deliver, \
            patch("run_coop.MongoDBHandler", return_value=handler), \
            patch("run_coop.poll_source", return_value=[listing]), \
            patch.dict(run_coop.coop.SOURCES,
                       {"MYGEWO": {"url": "u", "fetcher": "fetch_all_mygewo"}},
                       clear=True), patch.dict(os.environ,
                                               {"WILLHABEN_PRIVATE_COOP": "0"}):
        assert run_coop.run(no_send=True) == 0

    candidates.assert_not_called()
    deliver.assert_not_called()
    handler.get_listings_by_urls.assert_not_called()


class TestRun(unittest.TestCase):
    @patch("run_coop.poll_source", return_value=[])
    @patch("run_coop.MongoDBHandler")
    def test_missing_optional_telegram_channels_are_warnings(self, MH, poll):
        MH.return_value = _mongo_mock()
        with patch.dict(os.environ, {
            "TELEGRAM_COOP_CHANNEL_ID": "",
            "TELEGRAM_PRIVATE_COOP_CHANNEL_ID": "",
            "WILLHABEN_PRIVATE_COOP": "0",
        }, clear=False), self.assertLogs("run_coop", level=logging.WARNING) as captured:
            with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                            clear=True):
                self.assertEqual(run_coop.run(no_send=True), 0)

        channel_records = [
            record for record in captured.records
            if "TELEGRAM_" in record.getMessage()
        ]
        self.assertEqual(len(channel_records), 2)
        self.assertTrue(all(record.levelno == logging.WARNING for record in channel_records))

    @patch("run_coop.MongoDBHandler")
    def test_aborts_when_no_mongo(self, MH):
        MH.return_value.collection = None
        self.assertEqual(run_coop.run(), 1)

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_no_send_upserts_and_counts_without_sending(self, MH, poll, vurl):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://x.at/new")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.upsert_coop_listing.assert_called_once()
        MH.return_value.mark_sent.assert_not_called()   # no-send never sends

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.TelegramBot")
    @patch("run_coop.MongoDBHandler")
    def test_sends_via_bot_and_marks_sent(self, MH, TB, poll, vurl):
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

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.TelegramBot")
    @patch("run_coop.MongoDBHandler")
    def test_send_failure_does_not_mark_sent(self, MH, TB, poll, vurl):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        TB.return_value.send_message.return_value = False    # send failed
        poll.return_value = [_l(url="https://x.at/f")]
        with patch.dict(os.environ,
                        {"TELEGRAM_MAIN_BOT_TOKEN": "t", "TELEGRAM_COOP_CHANNEL_ID": "c"}):
            with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
                rc = run_coop.run(no_send=False)
        self.assertEqual(rc, 0)
        MH.return_value.mark_sent.assert_not_called()

    # Send-once is no longer the `sent_to_telegram` flag's job — that gate read a
    # document the duplicate/invalid upsert paths never create. The ledger owns
    # it now: Tests/test_coop_channel_ledger.py.

    @patch("run_coop.validate_url", return_value=False)   # broken URL
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_broken_url_marked_invalid(self, MH, poll, vurl):
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://x.at/broken")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.mark_url_invalid.assert_called_once_with("https://x.at/broken")

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_filtered_out_listing_not_alerted(self, MH, poll, vurl):
        """No alert asks for this unit → it never reaches the send checks."""
        MH.return_value = _mongo_mock(
            get_listing_ret=None,
            alerts=[{"_id": "a", "kind": "keyword", "keywords": ["Dachterrasse"],
                     "telegram_chat_id": "-100"}])
        poll.return_value = [_l(url="https://x.at/other",
                                title="Wohnung ohne Freifläche")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        vurl.assert_not_called()          # filtered before the send checks

    @patch("run_coop.poll_source", side_effect=RuntimeError("boom"))
    @patch("run_coop.MongoDBHandler")
    def test_all_adapters_fail_returns_1(self, MH, poll):
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

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_transfers_are_tagged_and_upserted(self, MH, poll, WS, crawl, vurl):
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

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_an_ordinary_rental_is_never_tagged_as_a_transfer(self, MH, poll, WS,
                                                              crawl, vurl):
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

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_ordinary_rentals_never_reach_the_coop_channel(self, MH, poll, WS,
                                                           crawl, vurl):
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

    @patch("run_coop.validate_url", return_value=True)
    @patch("run_coop.crawl_newest", side_effect=RuntimeError("blocked"))
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source")
    @patch("run_coop.MongoDBHandler")
    def test_willhaben_failure_does_not_fail_the_poll(self, MH, poll, WS, crawl,
                                                      vurl):
        """A Willhaben block must leave the mygewo half of the poll running."""
        MH.return_value = _mongo_mock(get_listing_ret=None)
        poll.return_value = [_l(url="https://mygewo.at/angebot/1")]
        with patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}},
                        clear=True):
            rc = run_coop.run(no_send=True)
        self.assertEqual(rc, 0)
        MH.return_value.upsert_coop_listing.assert_called_once()

    @patch("run_coop.crawl_newest")
    @patch("run_coop.WillhabenScraper")
    @patch("run_coop.poll_source", side_effect=RuntimeError("mygewo down"))
    @patch("run_coop.MongoDBHandler")
    def test_willhaben_cannot_mask_a_total_mygewo_outage(self, MH, poll, WS, crawl):
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
    def test_legacy_listings_alert_created_by_dashboard_is_delivered(self, TB):
        """The legacy dashboard modal stores kind='listings'; keep polling it."""
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        alert = {"_id": "a", "kind": "listings", "keyword": "1100",
                 "telegram_chat_id": "-100", "confirmed": True}
        handler = self._handler([])
        handler.get_active_alerts.side_effect = (
            lambda kinds: [alert] if "listings" in kinds else [])
        listing = _l(url="https://willhaben.at/x")
        listing.title = "Wohnung 1100 Wien"

        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        handler.get_active_alerts.assert_called_once_with(
            ["listings", "coop_private", "keyword"])
        TB.assert_called_once_with("tok", "-100")

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
    @patch("Application.alert_email.send_alert_email")
    def test_unconfirmed_email_does_not_block_telegram(self, mail, TB):
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        handler = self._handler([{
            "_id": "a", "keyword": "1100", "telegram_chat_id": "-100",
            "email": "pending@x.at", "confirmed": False,
        }])
        listing = _l(url="https://willhaben.at/x")
        listing.title = "Weitergabe 1100 Wien"

        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        TB.assert_called_once_with("tok", "-100")
        mail.assert_not_called()

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
