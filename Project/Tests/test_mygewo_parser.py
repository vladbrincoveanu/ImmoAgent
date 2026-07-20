"""Deterministic parse_mygewo tests (fixture-based, no network).

Fixture mirrors the real mygewo.at card DOM: an <a> to /genossenschaftswohnungen/
angebot/<slug>-<uuid> with a "gefunden auf <dev>.at" line, a "Miete: €… • … m² •
… Zimmer • Kapital: €…" line, a street <p>, and a "<PLZ> Wien , Wien" <p>.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.genossenschaft_scraper import parse_mygewo  # noqa: E402


def _card(href, dev, rent, area, rooms, kapital, street, plz, extra=""):
    return f"""
    <a href="{href}" class="block rounded-lg border">
      <p class="truncate">gefunden auf {dev}</p>
      <p>vor 3 Tagen</p>
      <p class="hidden">Miete: €{rent} • {area} m² • {rooms} Zimmer • Kapital: €{kapital}{extra}</p>
      <p class="mt-2 text-base leading-6">{street}</p>
      <p class="text-base leading-5">{plz} Wien , Wien</p>
    </a>"""


FIXTURE = f"""<html><body><div class="results">
  {_card("/genossenschaftswohnungen/angebot/gw-wien-3-zimmer-70-09-m2-oesw-e34fe1a4-5ecc-48cd-8378-a4958f5b7be8",
         "oesw.at", "945", "70,09", "3", "2.922", "Erzherzog-Karl-Straße 140", "1220")}
  {_card("/genossenschaftswohnungen/angebot/gw-wien-3-zimmer-63-m2-oevw-85a5472f-3ed9-42f4-8b4f-633571cec0d9",
         "oevw.at", "550", "63", "3", "2.702", "Thomas-Morus-Gasse 2-12", "1130",
         extra=" • mit Kaufoption")}
  <a href="/genossenschaftswohnungen/suche">back to search</a>
</div></body></html>"""


def test_parses_all_unit_cards_ignoring_nav():
    ls = parse_mygewo(FIXTURE)
    assert len(ls) == 2  # the /suche nav link is not a unit card


def test_extracts_core_fields_and_full_address():
    ls = {l.bezirk: l for l in parse_mygewo(FIXTURE)}
    a = ls["1220"]
    assert a.rooms == 3 and abs(a.area_m2 - 70.09) < 0.001 and a.price_total == 945
    assert a.own_funds == 2922
    assert a.address == "Erzherzog-Karl-Straße 140, 1220 Wien"
    assert a.bautraeger == "OESW"
    assert a.url.startswith("https://mygewo.at/genossenschaftswohnungen/angebot/")
    assert a.is_genossenschaft is True
    assert a.title and "Erzherzog-Karl" in a.title


def test_buy_option_flagged_in_special_features():
    ls = {l.bezirk: l for l in parse_mygewo(FIXTURE)}
    assert "Kaufoption" in (ls["1130"].special_features or [])
    assert "Kaufoption" not in (ls["1220"].special_features or [])


def test_european_number_parsing():
    a = {l.bezirk: l for l in parse_mygewo(FIXTURE)}["1220"]
    # "2.922" is 2922 (thousands dot), "70,09" is 70.09 (decimal comma)
    assert a.own_funds == 2922.0
    assert a.area_m2 == 70.09
