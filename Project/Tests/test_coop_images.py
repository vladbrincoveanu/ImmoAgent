"""Co-op photo extraction (fixture-based, no network).

Covers the three tiers the dashboard depends on:
  T1 — an image key in mygewo's own unit payload (SSR literal or RPC dict),
  T2 — og:image / a content <img> on the offer page `run_coop` already fetches,
  T3 — nothing usable, which must yield None (the UI renders a placeholder)
       rather than a bad src that would show as a broken image.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.genossenschaft_scraper import (  # noqa: E402
    _image_from_unit,
    _mygewo_units_from_rpc,
    _normalize_image_url,
    _og_image,
    parse_mygewo,
)

_IMG = "https://cdn.example-bt.at/objekte/1200-wien/hero.jpg"


# --- URL normalisation --------------------------------------------------------

def test_absolute_url_kept():
    assert _normalize_image_url(_IMG) == _IMG


def test_protocol_relative_and_root_relative_absolutised():
    assert _normalize_image_url("//cdn.x.at/a.jpg") == "https://cdn.x.at/a.jpg"
    assert _normalize_image_url("/media/a.jpg") == "https://mygewo.at/media/a.jpg"


def test_unusable_values_rejected():
    # A bare storage key is NOT guessed at — a broken <img> src is worse than
    # the placeholder tile the dashboard shows for None.
    for bad in (None, "", "   ", "abc123-storage-key", 42, {}, []):
        assert _normalize_image_url(bad) is None


def test_first_usable_entry_of_a_list_wins():
    assert _normalize_image_url(["not-a-url", {"url": _IMG}]) == _IMG


def test_dict_shapes_unwrapped():
    assert _normalize_image_url({"src": _IMG}) == _IMG


# --- T1: image key in the unit payload ---------------------------------------

def test_image_read_from_any_candidate_key():
    for key in ("image", "images", "main_image", "photo", "thumbnail"):
        assert _image_from_unit({key: _IMG}) == _IMG, key


def test_unit_without_any_image_key_yields_none():
    assert _image_from_unit({"uuid": "x", "rent": "500"}) is None


def test_rpc_mapping_carries_the_image_through():
    mapped = _mygewo_units_from_rpc([{"uuid": "u1", "url": "https://b.at/x",
                                      "images": [{"url": _IMG}]}])
    assert mapped[0]["image"] == _IMG


def test_ssr_literal_image_reaches_the_listing():
    ts = '"2026-07-20T12:08:02.203Z"'
    html = (
        "<script>window.x={units:$R[1]=[{id:1,manualData:!1,"
        'uuid:"aaaaaaaa-aaaa-aaaa-aaaa-000000000001",'
        'external_unit_id:"https://www.example-bt.at/objekt/1200-wien-x",'
        'url:"https://www.example-bt.at/objekt/1200-wien-x",'
        'street:"Beispielgasse",rooms:"2.00",rent:"600.00",capital:"3000.00",'
        f'area:"55.00",coordinates:"00",buyable:null,image:"{_IMG}",'
        f'first_seen:{ts},'
        'company:$R[2]={id:13,name:"ExampleBT",readable_url:"example-bt.at"},'
        'city:$R[3]={id:28,name:"Wien",zipcode:"1200"}}]}</script>'
    )
    listings = parse_mygewo(html)
    assert len(listings) == 1
    assert listings[0].image_url == _IMG


def test_listing_image_is_none_when_payload_has_no_image():
    ts = '"2026-07-20T12:08:02.203Z"'
    html = (
        "<script>window.x={units:$R[1]=[{id:1,manualData:!1,"
        'uuid:"aaaaaaaa-aaaa-aaaa-aaaa-000000000002",'
        'external_unit_id:"https://www.example-bt.at/objekt/1200-wien-y",'
        'url:"https://www.example-bt.at/objekt/1200-wien-y",'
        'street:"Beispielgasse",rooms:"2.00",rent:"600.00",capital:"3000.00",'
        f'area:"55.00",coordinates:"00",buyable:null,first_seen:{ts},'
        'company:$R[2]={id:13,name:"ExampleBT",readable_url:"example-bt.at"},'
        'city:$R[3]={id:28,name:"Wien",zipcode:"1200"}}]}</script>'
    )
    listings = parse_mygewo(html)
    assert len(listings) == 1
    assert listings[0].image_url is None


# --- T2: the offer page ------------------------------------------------------

def test_og_image_preferred():
    html = f'<html><head><meta property="og:image" content="{_IMG}"></head></html>'
    assert _og_image(html) == _IMG


def test_twitter_image_used_when_og_absent():
    html = f'<html><head><meta name="twitter:image" content="{_IMG}"></head></html>'
    assert _og_image(html) == _IMG


def test_falls_back_to_a_content_img_skipping_chrome():
    html = ('<html><body><img src="/assets/logo.svg">'
            '<img src="/static/icon-menu.png">'
            f'<img src="{_IMG}"></body></html>')
    assert _og_image(html) == _IMG


def test_offer_page_without_any_photo_yields_none():
    html = '<html><body><img src="/assets/logo.svg"><p>kein Bild</p></body></html>'
    assert _og_image(html) is None


# --- T4: a resolved-but-empty result is terminal ------------------------------
# The offer page is fetched at most once per unit. That only holds if "fetched,
# and there was no photo" is stored distinguishably from "not fetched yet" —
# otherwise every unit whose page has no og:image is re-fetched on every */5
# poll, forever, and nothing surfaces it because a missing photo is a
# placeholder tile rather than an error. "" is that terminal marker.

class _FakeCollection:
    def __init__(self):
        self.replaced = None

    def replace_one(self, _filter, doc):
        self.replaced = doc


def _preserving(existing: dict, incoming: dict) -> dict:
    from Integration.mongodb_handler import MongoDBHandler
    handler = MongoDBHandler.__new__(MongoDBHandler)  # no connection needed
    handler.collection = _FakeCollection()
    MongoDBHandler._replace_preserving_state(handler, existing, incoming)
    return handler.collection.replaced


def test_empty_sentinel_survives_a_re_scrape():
    """The whole point: a re-poll must not wipe "" back to None."""
    out = _preserving(
        {"_id": 1, "builder_url": "", "image_url": ""},
        {"builder_url": None, "image_url": None},
    )
    assert out["image_url"] == "", "'' wiped to None → offer page re-fetched every poll"
    assert out["builder_url"] == ""


def test_a_real_resolved_value_is_still_carried_over():
    out = _preserving({"_id": 1, "image_url": _IMG}, {"image_url": None})
    assert out["image_url"] == _IMG


def test_a_freshly_scraped_value_beats_the_stored_one():
    out = _preserving({"_id": 1, "image_url": ""}, {"image_url": _IMG})
    assert out["image_url"] == _IMG


# --- T4: builder-page hop -----------------------------------------------------
# mygewo offer pages carry no unit photo, so `resolve_offer_details` stored "" for
# every unit and /coop rendered a placeholder on every row. The photo lives on the
# builder's own page instead. Shapes below are real, sampled 2026-07-30.

from unittest.mock import patch  # noqa: E402

from Application.scraping.genossenschaft_scraper import (  # noqa: E402
    resolve_builder_image,
)

_LEBENSWERT = (
    '<html><head><meta property="og:image" '
    'content="https://storage.justimmo.at/thumb/abc/fc_h1080/XezxUq.jpg"/>'
    '</head><body></body></html>'
)
_FRIEDEN = (
    '<html><head><meta data-react-helmet="true" property="og:image" '
    'content="https://portego.frieden.at/PublicFile/jVjKAN5jy5"/>'
    '</head><body></body></html>'
)
_GESIBA = (
    '<html><head></head><body>'
    '<img src="/assets/logo.svg"/>'
    '<img src="/media/objekte/010001418110016/wohnzimmer.jpg"/>'
    '</body></html>'
)
_NO_PHOTO = '<html><head></head><body><img src="/assets/icon-menu.svg"/></body></html>'


def test_builder_image_from_og_image():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_LEBENSWERT):
        assert resolve_builder_image("https://www.lebenswert-wohnen.at/objekt/7769786") == \
            "https://storage.justimmo.at/thumb/abc/fc_h1080/XezxUq.jpg"


def test_builder_image_from_helmet_og_image():
    """frieden.at renders og:image through react-helmet, so the tag carries an
    extra data attribute — the lookup must key on property, not exact markup."""
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_FRIEDEN):
        assert resolve_builder_image("https://www.frieden.at/immobiliensuche/1840") == \
            "https://portego.frieden.at/PublicFile/jVjKAN5jy5"


def test_builder_image_falls_back_to_content_img_when_no_og():
    """gesiba/nhg publish no og:image; half the inventory depends on this path."""
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_GESIBA):
        got = resolve_builder_image("https://www.gesiba.at/immobilien/wohnungen/detail")
    assert got is not None and got.endswith("/wohnzimmer.jpg")
    assert "logo" not in got


def test_builder_image_none_when_only_icons():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_NO_PHOTO):
        assert resolve_builder_image("https://www.nhg.at/Projekte/Details/?id=610") is None


def test_builder_image_none_on_fetch_failure():
    """One dead builder site must not abort a poll."""
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               side_effect=Exception("boom")):
        assert resolve_builder_image("https://dead.example.at/x") is None


def test_builder_image_none_for_empty_url():
    assert resolve_builder_image("") is None
    assert resolve_builder_image(None) is None
