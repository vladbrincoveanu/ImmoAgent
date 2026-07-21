"""Tests for resolve_builder_url — mygewo /angebot/ → builder reservation URL.

No network: monkeypatches genossenschaft_scraper.fetch to return fixture HTML that
mirrors the real mygewo detail DOM (the "Original-Anzeige" anchor wraps nested
markup, so bs4.find(string=…) misses it; decoy similar-offer links are present to
prove we pick the right anchor).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping import genossenschaft_scraper as coop  # noqa: E402

BUILDER = "https://www.wohnen.at/immobilienangebot/bestandseinheiten/1210-wien-donaufelder-str/"

# "Original-Anzeige" text sits inside a nested <span>, and two decoy similar-offer
# builder links precede it — the resolver must return the Original-Anzeige href only.
DETAIL_WITH_LINK = f"""<html><body>
  <p>gefunden auf wohnen.at · vor 3 Tagen</p>
  <section class="similar">
    <a href="https://www.arwag.at/immobilien/decoy-1/">Ähnliches Angebot</a>
    <a href="https://www.gesiba.at/immobilien/decoy-2/">Ähnliches Angebot</a>
  </section>
  <a href="{BUILDER}" class="cta" target="_blank">
    <span class="icon"></span><span>Original-Anzeige</span>
  </a>
</body></html>"""

DETAIL_NO_LINK = """<html><body>
  <p>gefunden auf oesw.at · vor 1 Tag</p>
  <section class="similar">
    <a href="https://www.arwag.at/immobilien/decoy/">Ähnliches Angebot</a>
  </section>
</body></html>"""

DETAIL_NOTHING = """<html><body><p>vor 1 Tag</p></body></html>"""

# Guard: an Original-Anzeige anchor that points back at mygewo must be ignored.
DETAIL_MYGEWO_SELF = """<html><body>
  <a href="https://mygewo.at/x"><span>Original-Anzeige</span></a>
  <p>gefunden auf gesiba.at</p>
</body></html>"""


def _patch(monkeypatch, html):
    monkeypatch.setattr(coop, "fetch", lambda url: html)


def test_extracts_original_anzeige_deep_link(monkeypatch):
    _patch(monkeypatch, DETAIL_WITH_LINK)
    assert coop.resolve_builder_url("https://mygewo.at/genossenschaftswohnungen/angebot/x") == BUILDER


def test_falls_back_to_builder_homepage(monkeypatch):
    _patch(monkeypatch, DETAIL_NO_LINK)
    assert coop.resolve_builder_url("https://mygewo.at/genossenschaftswohnungen/angebot/x") == "https://www.oesw.at"


def test_returns_none_when_no_signal(monkeypatch):
    _patch(monkeypatch, DETAIL_NOTHING)
    assert coop.resolve_builder_url("https://mygewo.at/genossenschaftswohnungen/angebot/x") is None


def test_ignores_mygewo_self_link_uses_homepage_fallback(monkeypatch):
    _patch(monkeypatch, DETAIL_MYGEWO_SELF)
    # Original-Anzeige points to mygewo → rejected → homepage fallback from "gefunden auf".
    assert coop.resolve_builder_url("https://mygewo.at/genossenschaftswohnungen/angebot/x") == "https://www.gesiba.at"


def test_none_on_fetch_failure(monkeypatch):
    def _boom(url):
        raise RuntimeError("network down")
    monkeypatch.setattr(coop, "fetch", _boom)
    assert coop.resolve_builder_url("https://mygewo.at/genossenschaftswohnungen/angebot/x") is None
