"""User-created alerts on the private-transfer feed.

The two invariants worth guarding: a keyword must match the ad BODY (not just the
title, where it usually isn't), and an unconfirmed email must never be delivered
to — anyone can type someone else's address into the form.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.alert_matcher import (  # noqa: E402
    alert_matches, channels_for, match, searchable_text,
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
