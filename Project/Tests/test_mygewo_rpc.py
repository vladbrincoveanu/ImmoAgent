"""Offline tests for mygewo's paginated RPC path (JSON-seroval decode + full crawl).

The production crawl no longer parses only the server-rendered first page — it
pages through mygewo's TanStack "server function", which returns a seroval-JSON
graph. These tests pin the decoder, the RPC-unit → Listing mapping, and the
pagination loop (dedup + stop condition) WITHOUT any network.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.scraping import genossenschaft_scraper as g  # noqa: E402


# --- seroval JSON node builders (mirror the live wire format) ------------------
def _str(s):  return {"t": 1, "s": s}
def _num(n):  return {"t": 0, "s": n}
_TRUE = {"t": 2, "s": 2}
_NULL = {"t": 2, "s": 0}


def _obj(i, fields):
    return {"t": 10, "i": i, "p": {"k": list(fields.keys()), "v": list(fields.values())}, "o": 0}


def _ref(i):
    return {"t": 3, "i": i}


def _unit(i, uuid, url, rooms, rent, area, zip_node, company_node, *,
          buyable=_NULL, capital="1000.00", street="Teststrasse 1",
          balcony=_NULL, terrace=_NULL):
    return _obj(i, {
        "uuid": _str(uuid), "url": _str(url), "buyable": buyable,
        "rooms": _str(rooms), "rent": _str(rent), "capital": _str(capital),
        "area": _str(area), "street": _str(street),
        "has_balcony": balcony, "has_terrace": terrace,
        "has_garden": _NULL, "has_loggia": _NULL,
        "company": company_node, "city": zip_node,
    })


def _city(i, zipcode):
    return _obj(i, {"id": _num(27), "name": _str("Wien"), "zipcode": _str(zipcode)})


def _company(i, name):
    return _obj(i, {"id": _num(13), "name": _str(name), "readable_url": _str("x.at")})


def _response(units, total, has_next):
    """Wrap units the way the live endpoint does: result.payload.{units,total,…}."""
    payload = _obj(2, {
        "units": {"t": 9, "i": 3, "a": units},
        "total": _num(total), "page": _num(0),
        "hasNextPage": _TRUE if has_next else _NULL,
    })
    result = _obj(1, {"payload": payload})
    return _obj(0, {"result": result, "error": _NULL, "context": _NULL})


def test_seroval_decode_resolves_back_references():
    # company defined once (i=50), reused by a bare back-ref on the second unit.
    comp = _company(50, "ÖVW")
    resp = _response([
        _unit(10, "u1", "https://oevw.at/a", "2.00", "600.00", "60.00", _city(60, "1210"), comp),
        _unit(11, "u2", "https://oevw.at/b", "3.00", "700.00", "70.00", _city(61, "1220"), _ref(50)),
    ], total=2, has_next=False)
    decoded = g._find_units_payload(g._seroval_json_decode(resp, {}))
    assert decoded["total"] == 2 and decoded["hasNextPage"] is None
    units = g._mygewo_units_from_rpc(decoded["units"])
    assert [u["company"] for u in units] == ["ÖVW", "ÖVW"]   # bare ref resolved
    assert [u["zipcode"] for u in units] == ["1210", "1220"]


def test_rpc_units_map_to_wien_rentals_and_drop_buy_and_nonwien():
    resp = _response([
        _unit(10, "u1", "https://oevw.at/rental", "2.00", "600.00", "60.00",
              _city(60, "1210"), _company(50, "ÖVW"), terrace=_TRUE),
        _unit(11, "u2", "https://wohnen.at/buy", "2.00", "800.00", "55.00",
              _city(61, "1220"), _company(51, "Neues Leben"), buyable=_TRUE),
        _unit(12, "u3", "https://gedesag.at/nö", "3.00", "700.00", "75.00",
              _city(62, "3100"), _company(52, "Gedesag")),
    ], total=3, has_next=False)
    decoded = g._find_units_payload(g._seroval_json_decode(resp, {}))
    listings = g._units_to_listings(g._mygewo_units_from_rpc(decoded["units"]), {})
    assert len(listings) == 1                         # buy + non-Wien dropped
    l = listings[0]
    assert l.bezirk == "1210" and l.bautraeger == "ÖVW"
    assert l.rooms == 2.0 and l.area_m2 == 60.0 and l.price_total == 600.0
    assert l.buyable is False and l.is_genossenschaft is True
    assert l.builder_url == "https://oevw.at/rental"
    assert "Terrasse" in (l.special_features or []) and l.balcony_terrace is True


def test_fetch_all_mygewo_pages_until_complete_and_dedups(monkeypatch):
    # 3 pages of 2 units each; last page repeats a uuid (dedup) and flips has_next.
    pages = {
        0: ([{"uuid": "a", "url": "https://b.at/a", "buyable": False, "rooms": "2.0",
              "rent": "500", "capital": "0", "area": "50", "street": "S1", "zipcode": "1100",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False},
             {"uuid": "b", "url": "https://b.at/b", "buyable": False, "rooms": "3.0",
              "rent": "600", "capital": "0", "area": "60", "street": "S2", "zipcode": "1110",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False}], 5, True),
        1: ([{"uuid": "c", "url": "https://b.at/c", "buyable": False, "rooms": "2.0",
              "rent": "700", "capital": "0", "area": "70", "street": "S3", "zipcode": "1120",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False},
             {"uuid": "d", "url": "https://b.at/d", "buyable": False, "rooms": "1.0",
              "rent": "400", "capital": "0", "area": "40", "street": "S4", "zipcode": "1130",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False}], 5, True),
        2: ([{"uuid": "d", "url": "https://b.at/d", "buyable": False, "rooms": "1.0",
              "rent": "400", "capital": "0", "area": "40", "street": "S4", "zipcode": "1130",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False},
             {"uuid": "e", "url": "https://b.at/e", "buyable": False, "rooms": "2.0",
              "rent": "550", "capital": "0", "area": "55", "street": "S5", "zipcode": "1200",
              "company": "B", "has_balcony": False, "has_terrace": False,
              "has_garden": False, "has_loggia": False}], 5, False),
    }
    calls = []

    def fake_page(states, page):
        calls.append(page)
        # already in _mygewo_units shape; map to the raw-json shape fetch expects
        raw, total, nxt = pages[page]
        return [{**u} for u in raw], total, nxt

    monkeypatch.setattr(g, "_fetch_mygewo_page", fake_page)
    monkeypatch.setattr(g, "_mygewo_units_from_rpc", lambda units: list(units))  # already shaped
    monkeypatch.setattr(g, "fetch", lambda url: "<html></html>")  # no SSR network

    listings = g.fetch_all_mygewo("28_")
    assert calls == [0, 1, 2]                    # paged through all
    bez = sorted(l.bezirk for l in listings)
    assert bez == ["1100", "1110", "1120", "1130", "1200"]  # 5 unique, 'd' deduped


def test_fetch_all_mygewo_stops_on_max_pages(monkeypatch):
    # has_next never flips False and total never reached → must stop at the cap.
    def fake_page(states, page):
        return ([{"uuid": f"u{page}", "url": f"https://b.at/{page}", "buyable": False,
                  "rooms": "2.0", "rent": "500", "capital": "0", "area": "50", "street": "S",
                  "zipcode": "1100", "company": "B", "has_balcony": False,
                  "has_terrace": False, "has_garden": False, "has_loggia": False}], 9999, True)
    monkeypatch.setattr(g, "_fetch_mygewo_page", fake_page)
    monkeypatch.setattr(g, "_mygewo_units_from_rpc", lambda units: list(units))
    monkeypatch.setattr(g, "fetch", lambda url: "<html></html>")
    listings = g.fetch_all_mygewo("28_")
    assert len(listings) == g._MYGEWO_MAX_PAGES     # capped, no infinite loop
