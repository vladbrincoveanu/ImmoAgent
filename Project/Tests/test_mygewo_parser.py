"""Deterministic parse_mygewo tests (fixture-based, no network).

The fixture mirrors mygewo.at's SSR-dehydrated (TanStack/seroval) data graph: a
`units:$R[..]=[…]` array of `{id:…,manualData:…,…}` unit literals, each carrying
`buyable` (rent-vs-buy flag), the builder's own `url`, and `company`/`city`
objects expressed as deduplicated `$R[NN]={…}` refs (inlined on first use, bare
`$R[NN]` when repeated). Rentals in Wien are kept; buy-option and non-Wien units
are dropped.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping.genossenschaft_scraper import parse_mygewo  # noqa: E402

_TS = '"2026-07-20T12:08:02.203Z"'


def _uuid(uid):
    return f"aaaaaaaa-aaaa-aaaa-aaaa-{str(uid).zfill(12)}"


def _card(uid, slug):
    """A rendered result card — parse_mygewo recovers the /angebot/ url from it
    by the uuid it shares with the structured unit."""
    return (f'<a href="/genossenschaftswohnungen/angebot/{slug}-{_uuid(uid)}">'
            f'{slug}</a>')


def _company(ref, cid, domain, name):
    return (f'$R[{ref}]={{id:{cid},url:"https://www.{domain}",code:"{name.lower()}",'
            f'name:"{name}",created_at:{_TS},deleted_at:null,updated_at:{_TS},'
            f'public_slug:"{name.lower()}",readable_url:"{domain}"}}')


def _city(ref, cid, zipcode, state_ref):
    return (f'$R[{ref}]={{id:{cid},name:"Wien",state:$R[{state_ref}]={{id:28,code:"9",'
            f'name:"Wien",position:0,created_at:{_TS},deleted_at:null,updated_at:{_TS},'
            f'public_slug:"wien"}},zipcode:"{zipcode}",state_id:28,region_id:347,'
            f'created_at:{_TS},deleted_at:null,updated_at:{_TS},gemeindecode:"92201",'
            f'gemeindekennziffer:"90001"}}')


def _unit(ref, uid, url, rooms, rent, capital, area, street, *, buyable="null",
          balcony="null", terrace="null", company="", city=""):
    return (f'$R[{ref}]={{id:{uid},manualData:!1,manualAvailable:!1,uuid:"{_uuid(uid)}",'
            f'external_unit_id:"{url}",url:"{url}",online:!0,available:!0,'
            f'first_seen:{_TS},last_seen:{_TS},unavailable_timestamp:null,city_id:28,'
            f'street:"{street}",rooms:"{rooms}",rent:"{rent}",capital:"{capital}",'
            f'area:"{area}",company_id:13,coordinates:"00",created_at:{_TS},'
            f'updated_at:{_TS},deleted_at:null,buyable:{buyable},has_garden:null,'
            f'garden_area:null,has_loggia:null,loggia_area:null,has_balcony:{balcony},'
            f'balcony_area:null,has_terrace:{terrace},terrace_area:null,'
            f'company:{company},city:{city}}}')


# Unit A: plain Wien rental (inlines company $R[37] + city $R[38]).
# Unit B: Wien rental with a buy option (buyable:!0) -> must be dropped.
# Unit C: Wien rental reusing A's company as a BARE ref -> tests ref resolution.
# Unit D: non-Wien (zipcode 3100) rental -> must be dropped.
FIXTURE = "<script>window.x={pages:[{payload:{units:$R[35]=[" + ",".join([
    _unit(36, 22755, "https://www.siedlungsunion.at/wohnen/sofort/1220-wien-saikogasse",
          "1.00", "478.27", "9239.18", "44.60", "Saikogasse", terrace="!0",
          company=_company(37, 13, "siedlungsunion.at", "Siedlungsunion"),
          city=_city(38, 28, "1220", 39)),
    _unit(40, 22448, "https://www.wohnen.at/immobilienangebot/1220-wien-miete-mit-eo",
          "1.00", "778.33", "0.00", "40.00", "Dueckegasse", buyable="!0",
          company=_company(41, 20, "wohnen.at", "NeuesLeben"),
          city=_city(42, 17, "1220", 43)),
    _unit(44, 22701, "https://www.siedlungsunion.at/wohnen/sofort/1210-wien-lebnergasse",
          "2.00", "520.00", "7690.16", "60.00", "Lebnergasse", balcony="!0",
          company="$R[37]", city=_city(49, 29, "1210", 50)),
    _unit(45, 22999, "https://www.gedesag.at/objekt/3100-st-poelten",
          "3.00", "700.00", "5000.00", "75.00", "Hauptstrasse",
          company=_company(46, 99, "gedesag.at", "Gedesag"),
          city=_city(47, 90, "3100", 48)),
]) + "]}}]}</script>" + (
    # rendered cards carrying the /angebot/ links (uuid-matched to the units above)
    _card(22755, "gw-wien-1-zimmer-saikogasse-oesw")
    + _card(22701, "gw-wien-2-zimmer-lebnergasse-siedlungsunion"))


def _by_bezirk():
    return {l.bezirk: l for l in parse_mygewo(FIXTURE)}


def test_keeps_only_wien_rentals():
    ls = parse_mygewo(FIXTURE)
    # Unit B (buy option) and Unit D (non-Wien) dropped -> only A and C remain.
    assert len(ls) == 2
    assert {l.bezirk for l in ls} == {"1220", "1210"}


def test_drops_buy_option_units():
    urls = [l.builder_url for l in parse_mygewo(FIXTURE)]
    assert not any("miete-mit-eo" in u for u in urls)


def test_drops_non_wien():
    assert all(l.bezirk.startswith("1") for l in parse_mygewo(FIXTURE))


def test_extracts_core_fields_and_builder_url():
    a = _by_bezirk()["1220"]
    assert a.rooms == 1.0 and abs(a.area_m2 - 44.60) < 1e-6
    assert a.price_total == 478.27 and a.own_funds == 9239.18
    assert a.bautraeger == "Siedlungsunion"
    # builder_url = the builder's own reservation page (what the dashboard links to)
    assert a.builder_url == "https://www.siedlungsunion.at/wohnen/sofort/1220-wien-saikogasse"
    # url = the stable mygewo /angebot/ page recovered from the rendered card
    assert a.url == ("https://mygewo.at/genossenschaftswohnungen/angebot/"
                     "gw-wien-1-zimmer-saikogasse-oesw-" + _uuid(22755))
    assert a.buyable is False                 # emitted units are rentals
    assert a.is_genossenschaft is True
    assert a.address == "Saikogasse, 1220 Wien"
    assert "Terrasse" in (a.special_features or []) and a.balcony_terrace is True


def test_url_falls_back_to_builder_when_no_card():
    # A structured unit with no matching rendered card falls back to the builder url.
    no_card = ("<script>window.x={units:$R[35]=[" + _unit(
        36, 99999, "https://www.example-bt.at/objekt/1200-wien-x",
        "2.00", "600.00", "3000.00", "55.00", "Beispielgasse",
        company=_company(37, 13, "example-bt.at", "ExampleBT"),
        city=_city(38, 28, "1200", 39)) + "]}</script>")
    ls = parse_mygewo(no_card)
    assert len(ls) == 1
    assert ls[0].url == "https://www.example-bt.at/objekt/1200-wien-x"
    assert ls[0].builder_url == ls[0].url


def test_resolves_bare_company_and_city_refs():
    # Unit C carries a bare $R[37] company ref first defined on Unit A.
    c = _by_bezirk()["1210"]
    assert c.bautraeger == "Siedlungsunion"   # company ref resolved
    assert c.bezirk == "1210"                 # city ref resolved
    assert "Balkon" in (c.special_features or [])
    assert c.buyable is False
