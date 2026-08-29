"""User-created alerts on the private-transfer feed.

The two invariants worth guarding: a keyword must match the ad BODY (not just the
title, where it usually isn't), and an unconfirmed email must never be delivered
to — anyone can type someone else's address into the form.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.alert_matcher import (  # noqa: E402
    alert_keywords, alert_matches, channels_for, gate_result, keyword_hit,
    match, searchable_text,
)


class _L:
    def __init__(self, title=None, address=None, bezirk=None, description=None):
        self.title = title
        self.address = address
        self.bezirk = bezirk
        self.description = description


_TG = {"_id": "a1", "keyword": "", "telegram_chat_id": "-100123456", "email": None,
       "confirmed": True}


# --- matching -----------------------------------------------------------------

def test_keyword_matches_the_ad_body():
    """The whole point: "Nachmieter" lives in the description, not the title."""
    listing = _L(title="3 Zimmer Wohnung", description="Nachmieter gesucht, Ablöse VB")
    assert alert_matches({"keyword": "nachmieter"}, listing) is True


def test_keyword_matches_the_district():
    listing = _L(title="Wohnung", bezirk="1100")
    assert alert_matches({"keyword": "1100"}, listing) is True


def test_keyword_is_case_insensitive():
    listing = _L(description="Grosse TERRASSE")
    assert alert_matches({"keyword": "terrasse"}, listing) is True


def test_non_matching_keyword():
    listing = _L(title="Wohnung", description="ohne Balkon")
    assert alert_matches({"keyword": "garten"}, listing) is False


def test_empty_keyword_matches_everything():
    """Watching the whole feed is a legitimate choice, not a misconfiguration."""
    assert alert_matches({"keyword": ""}, _L(title="irgendwas")) is True
    assert alert_matches({}, _L(title="irgendwas")) is True


def test_searchable_text_skips_missing_fields():
    assert searchable_text(_L(title="Nur Titel")) == "nur titel"


# --- channels -----------------------------------------------------------------

def test_confirmed_email_is_usable():
    chat, email = channels_for({"email": "a@b.at", "confirmed": True})
    assert (chat, email) == (None, "a@b.at")


def test_unconfirmed_email_is_never_delivered_to():
    chat, email = channels_for({"email": "victim@example.at", "confirmed": False})
    assert email is None


def test_telegram_survives_an_unconfirmed_email_on_the_same_alert():
    chat, email = channels_for({
        "telegram_chat_id": "-100999", "email": "pending@x.at", "confirmed": False})
    assert chat == "-100999"
    assert email is None


# --- pairing ------------------------------------------------------------------

def test_match_pairs_alert_with_listing():
    listing = _L(title="Weitergabe 1100")
    pairs = match([listing], [_TG])
    assert len(pairs) == 1
    assert pairs[0][0] is _TG and pairs[0][1] is listing


def test_alert_without_any_channel_is_skipped():
    dead = {"_id": "dead", "keyword": "", "telegram_chat_id": None,
            "email": "x@y.at", "confirmed": False}
    assert match([_L(title="x")], [dead]) == []


def test_no_alerts_means_no_pairs():
    assert match([_L(title="x")], []) == []


def test_each_alert_sees_every_matching_listing():
    listings = [_L(title="a 1100"), _L(title="b 1100"), _L(title="c 1210")]
    pairs = match(listings, [{"_id": "k", "keyword": "1100",
                              "telegram_chat_id": "-1", "confirmed": True}])
    assert len(pairs) == 2


# --- multi-key OR semantics + numeric gates -----------------------------------

class _LN:
    """Listing stub carrying the numeric fields the gates read."""

    def __init__(self, title=None, description=None,
                 area_m2=None, rooms=None, price_total=None, coop_kind=None,
                 coop_source=None):
        self.title = title
        self.address = None
        self.bezirk = None
        self.description = description
        self.area_m2 = area_m2
        self.rooms = rooms
        self.price_total = price_total
        # What the scraper concluded about the ad. None is the common case: most
        # of the newest-first feed is ordinary free-market rentals.
        self.coop_kind = coop_kind
        self.coop_source = coop_source


def _alert(**kw):
    base = {"_id": "k1", "telegram_chat_id": "-100123456", "email": None,
            "confirmed": True, "keywords": [], "filters": {}}
    base.update(kw)
    return base


def test_any_key_hits_matches():
    a = _alert(keywords=["ablöse", "nachmieter"])
    assert keyword_hit(a, _LN(title="Nachmieter gesucht"))


def test_no_key_hits_does_not_match():
    a = _alert(keywords=["ablöse", "nachmieter"])
    assert not keyword_hit(a, _LN(title="Schöne Altbauwohnung"))


def test_key_matches_body_not_only_title():
    a = _alert(keywords=["nachmieter"])
    assert keyword_hit(a, _LN(title="Wohnung 1100", description="Nachmieter gesucht"))


def test_empty_keyword_list_matches_everything():
    assert keyword_hit(_alert(keywords=[]), _LN(title="irgendwas"))


def test_legacy_scalar_keyword_still_matches():
    a = _alert(keywords=None, keyword="ablöse")
    assert keyword_hit(a, _LN(title="ABLÖSE für Küche"))


def test_keywords_are_case_insensitive():
    assert keyword_hit(_alert(keywords=["ABLÖSE"]), _LN(title="ablöse"))


def test_alert_keywords_drops_blanks_and_lowercases():
    assert alert_keywords(_alert(keywords=[" Ablöse ", "", "  "])) == ["ablöse"]


def test_area_gate_accepts_value_in_range():
    a = _alert(filters={"min_area": 50, "max_area": 80})
    assert gate_result(a, _LN(area_m2=65)) == (True, False)


def test_area_gate_rejects_value_below_min():
    a = _alert(filters={"min_area": 50})
    assert gate_result(a, _LN(area_m2=40)) == (False, False)


def test_area_gate_rejects_value_above_max():
    a = _alert(filters={"max_area": 80})
    assert gate_result(a, _LN(area_m2=95)) == (False, False)


def test_rooms_gate_rejects_value_below_min():
    a = _alert(filters={"min_rooms": 3})
    assert gate_result(a, _LN(rooms=2)) == (False, False)


def test_price_gate_rejects_value_above_max():
    a = _alert(filters={"max_price": 900})
    assert gate_result(a, _LN(price_total=1200)) == (False, False)


def test_price_gate_accepts_value_at_max():
    a = _alert(filters={"max_price": 900})
    assert gate_result(a, _LN(price_total=900)) == (True, False)


def test_null_value_passes_a_set_gate_and_flags_unverified():
    """Unknown never fails a gate — newest-first list pages routinely omit
    size, and dropping those would lose exactly the freshest ads."""
    a = _alert(filters={"min_area": 60})
    assert gate_result(a, _LN(area_m2=None)) == (True, True)


def test_null_value_with_no_gates_set_is_not_unverified():
    assert gate_result(_alert(filters={}), _LN(area_m2=None)) == (True, False)


def test_unverified_only_when_the_missing_field_has_a_gate():
    a = _alert(filters={"min_area": 60})
    assert gate_result(a, _LN(area_m2=70, rooms=None)) == (True, False)


def test_match_returns_alert_listing_unverified_triples():
    a = _alert(keywords=["nachmieter"], filters={"min_area": 60})
    pairs = match([_LN(title="Nachmieter", area_m2=None)], [a])
    assert len(pairs) == 1
    alert, listing, unverified = pairs[0]
    assert alert is a and unverified is True


def test_match_drops_listings_failing_a_gate():
    a = _alert(keywords=[], filters={"max_price": 800})
    assert match([_LN(title="x", price_total=1500)], [a]) == []


def test_match_skips_alerts_with_no_usable_channel():
    a = _alert(telegram_chat_id=None, email="x@y.at", confirmed=False)
    assert match([_LN(title="x")], [a]) == []


# --- the coop_private rubric --------------------------------------------------
#
# "A co-op flat being passed on by its tenant" is an AND of two markers, and the
# keys are OR-ed, so it cannot be written as a keyword list — an alert for
# "Ablöse" matches every kitchen buyout on the feed. The scraper answers it per
# ad via `coop_kind`, and a coop_private alert reuses that verdict.

def test_coop_private_requires_the_scrapers_verdict():
    a = _alert(kind="coop_private", keywords=["genossenschaft"])
    hit = _LN(title="Genossenschaftswohnung", coop_kind="private_transfer")
    assert alert_matches(a, hit) is True


def test_coop_private_rejects_an_ad_the_rubric_did_not_tag():
    """The failure this exists to prevent: an ordinary free-financed rental that
    happens to say "Ablöse" for the fitted kitchen reaching a co-op alert."""
    a = _alert(kind="coop_private", keywords=["ablöse"])
    miss = _LN(title="Ablöse für Küche", description="freifinanziert")
    assert alert_matches(a, miss) is False
    assert match([miss], [a]) == []


def test_coop_private_still_applies_its_keywords():
    """The rubric is an extra AND term, not a replacement for the keys."""
    a = _alert(kind="coop_private", keywords=["1100"])
    other = _LN(title="Wohnung", coop_kind="private_transfer")
    assert alert_matches(a, other) is False


def test_other_kinds_see_the_whole_feed():
    """'keyword' and the legacy default must not inherit the rubric, or every
    pre-existing alert silently narrows to co-op transfers."""
    plain = _LN(title="Dachgeschoss mit Terrasse")
    assert alert_matches(_alert(kind="keyword", keywords=["terrasse"]), plain) is True
    assert alert_matches(_alert(keywords=["terrasse"]), plain) is True


def test_mygewo_matches_builder_direct_listing_without_keywords():
    alert = _alert(kind="mygewo", keywords=[])
    listing = _LN(
        title="1100 Wien - 3 Zimmer",
        coop_source="bautraeger_direct",
    )

    assert alert_matches(alert, listing) is True


def test_mygewo_rejects_non_builder_direct_listing():
    alert = _alert(kind="mygewo", keywords=[])

    assert alert_matches(alert, _LN(coop_source="willhaben")) is False
    assert alert_matches(alert, _LN(coop_source=None)) is False
