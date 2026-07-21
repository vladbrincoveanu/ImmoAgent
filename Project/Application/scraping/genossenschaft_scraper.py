"""Genossenschaft (co-op) Bauträger scrapers — v1 pilot: ÖVW, Familienwohnbau, BWSG.
Concrete parsers (no shared engine yet). Each parse_<x>(html) -> List[Listing].
Post-pilot: review HTML variance to decide whether to extract a shared engine."""
import json
import logging
import os
import re
import requests
from typing import List, Optional, Tuple
from urllib.parse import quote
from bs4 import BeautifulSoup
from Domain.listing import Listing
from Domain.sources import Source

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter/1.0)"}

# mygewo.at is itself the aggregator of ~30 Vienna Bauträger (ÖVW, ARWAG, BWSG,
# Neues Leben, …) — one server-rendered search page carries every developer's
# units, so a single adapter gives full parity (and stays in sync) instead of N
# brittle scrapers. We therefore rely on mygewo ALONE: the standalone ÖVW/
# Familienwohnbau/BWSG adapters were a v1 pilot and are now redundant with mygewo
# *and* had no rent/buy filter, so they leaked for-sale (Kauf) units. Disabled
# below; their parse_* functions are kept for reference only.
#
# states=28_ is Wien (verified: the region filter returns Wien-only). We deliberately
# apply NO room/size/rent narrowing in the URL — the user's own thresholds live in
# coop_alerts.json (Telegram) and the dashboard — so we ingest the full Wien
# inventory "newest first". Buy-option units are dropped in the parser (buyable flag),
# NOT via the URL, so nothing for-sale ever reaches the DB.
#
# CRITICAL: mygewo server-renders only the FIRST page (~25 units) into the SSR
# HTML; the rest of the inventory (Wien had 75 units / 58 rentals when this was
# written) lives behind a paginated TanStack "server function". Parsing the SSR
# page alone silently drops ~2/3 of every builder's listings. `fetch_all_mygewo`
# pages through that RPC so we ingest EVERY unit, not just the first screen.
MYGEWO_DEFAULT_URL = "https://mygewo.at/genossenschaftswohnungen/suche?states=28_"


def _mygewo_states(url: str) -> str:
    """The `states` region token from a mygewo search URL (Wien = 28_)."""
    m = re.search(r"[?&]states=([^&]+)", url or "")
    return m.group(1) if m else "28_"


_MYGEWO_CFG_URL = os.environ.get("MYGEWO_SEARCH_URL") or MYGEWO_DEFAULT_URL

SOURCES = {
    # `fetcher` (full-inventory RPC pagination) supersedes the single-page `parser`.
    # `url` is kept only as the conditional-GET change gate (skip the RPC crawl when
    # page 0 is byte-for-byte unchanged). `states` drives the RPC region filter.
    "MYGEWO": {"url": _MYGEWO_CFG_URL, "fetcher": "fetch_all_mygewo",
               "states": _mygewo_states(_MYGEWO_CFG_URL)},
    # Redundant with mygewo (which aggregates these builders) and unfiltered for
    # buy-vs-rent — disabled to keep the co-op feed Wien-rentals-only. Re-enable
    # only if a builder is found missing from mygewo AND its parser filters Kauf.
    # "ÖVW":             {"url": "https://www.oevw.at/suche/wohnen", "parser": "parse_oevw"},
    # "Familienwohnbau": {"url": "https://www.familienwohnbau.at/de/immobilien", "parser": "parse_familienwohnbau"},
    # "BWSG":            {"url": "https://www.bwsg.at/immobilien/immobilie-suchen/", "parser": "parse_bwsg"},
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _new_coop_listing(url: str, bautraeger: str) -> Listing:
    return Listing(
        url=url, source=Source.GENOSSENSCHAFT,
        is_genossenschaft=True, bautraeger=bautraeger,
        coop_source="bautraeger_direct", allocation_model="first_come",
    )


def _text(block, sel: str) -> Optional[str]:
    el = block.select_one(sel)
    return el.get_text(" ", strip=True) if el else None


def _parse_number(text: str) -> Optional[float]:
    m = re.search(r"\d+(?:[.,]\d+)*", text)
    if not m:
        return None
    raw = m.group()
    if "," in raw:  # European format, e.g. "1.432,73" -> 1432.73
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:  # "1.234.567" -> 1234567 (multiple dot-groups are always thousands seps)
        raw = raw.replace(".", "")
    elif "." in raw:
        int_part, frac_part = raw.split(".")
        if len(frac_part) == 3:  # "350.000" -> 350000 (dot-thousands, no decimal comma)
            raw = int_part + frac_part
        # else a 1-2 digit tail is a real decimal point, e.g. "77.5" -> 77.5
    return float(raw)


def _num(block, sel: str) -> Optional[float]:
    el = block.select_one(sel)
    return _parse_number(el.get_text(" ")) if el else None


def _num_by_keyword(block, sel: str, keyword: str) -> Optional[float]:
    for el in block.select(sel):
        text = el.get_text(" ")
        if keyword in text:
            return _parse_number(text)
    return None


def _num_before_keyword(text: str, keyword: str) -> Optional[float]:
    """Number immediately preceding keyword, e.g. "3" from "3 Zimmer" inside
    "77,29 m² | 3 Zimmer" — anchoring to the keyword (not just "first number
    in the string") avoids picking up an unrelated figure from elsewhere in
    the same text when multiple keyword/number pairs share one text node."""
    m = re.search(r"([\d.,]+)\s*" + re.escape(keyword), text)
    return _parse_number(m.group(1)) if m else None


def _bezirk_from(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(\d{4})\s+Wien", text)  # same convention as willhaben_scraper.extract_bezirk
    return m.group(1) if m else None


def parse_oevw(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select(".thumb--unit"):
        a = block.select_one(".thumb__link a[href]")
        if not a:
            continue
        href = a.get("href", "")
        url = href if href.startswith("http") else "https://www.oevw.at" + href
        listing = _new_coop_listing(url, "ÖVW")
        street = _text(block, ".thumb__heading")
        info = _text(block, ".thumb__info")  # e.g. "Wohnung – Miete – 1100 Wien"
        listing.address = f"{street}, {info}" if street and info else (street or info)
        listing.bezirk = _bezirk_from(info)
        listing.area_m2 = _num(block, ".thumb__subheading__list li:nth-of-type(1)")
        listing.price_total = _num(block, ".thumb__subheading__list li:nth-of-type(2)")
        listing.rooms = _num(block, ".thumb__text__list li:nth-of-type(1)")
        out.append(listing)
    return out


def parse_familienwohnbau(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select('a[href^="/de/objekt/"]'):
        href = block.get("href", "")
        if not href:
            continue
        title = _text(block, "p.uppercase")
        if title and "garage" in title.lower():  # parking spots, not housing units
            continue
        rooms = _num_by_keyword(block, "div.flex-1 p", "Zimmer")
        area = _num_by_keyword(block, "div.flex-1 p", "m²")
        if rooms is None and area is None:  # multi-unit project overview, no single-unit data
            continue
        url = href if href.startswith("http") else "https://www.familienwohnbau.at" + href
        listing = _new_coop_listing(url, "Familienwohnbau")
        listing.address = _text(block, "p.text-gray-700.pt-1") or title
        listing.bezirk = _bezirk_from(listing.address)
        listing.area_m2 = area
        listing.rooms = rooms
        listing.price_total = _num(block, "p.text-primary")
        out.append(listing)
    return out


def parse_bwsg(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select(".res_immobiliensuche__immobilien__item"):
        href = block.get("href", "")
        if not href:
            continue
        row1 = _text(block, ".res_immobiliensuche__immobilien__item__content__meta__row_1") or ""
        rooms = _num_before_keyword(row1, "Zimmer")
        area = _num_before_keyword(row1, "m²")
        if rooms is None and area is None:  # project overview card, no single-unit data
            continue
        url = href if href.startswith("http") else "https://www.bwsg.at" + href
        listing = _new_coop_listing(url, "BWSG")
        title = _text(block, ".res_immobiliensuche__immobilien__item__content__title")
        listing.address = _text(block, ".res_immobiliensuche__immobilien__item__content__meta__location") or title
        listing.bezirk = _bezirk_from(listing.address)
        listing.area_m2 = area
        listing.rooms = rooms
        listing.price_total = _num(block, ".res_immobiliensuche__immobilien__item__content__meta__preis")
        out.append(listing)
    return out


_MYGEWO_BASE = "https://mygewo.at"


def _seroval_ref_bodies(html: str) -> dict:
    """Map seroval ref id -> its object body text, for the `$R[NN]={…}` blocks
    mygewo dehydrates into the page. company/city objects are deduplicated: the
    first unit that references one inlines it as `$R[NN]={…}`, later units carry a
    bare `$R[NN]`. Building this map lets us resolve either form uniformly.

    Braces inside string values are skipped so nested objects (a city holds a
    `state:$R[..]={…}`) balance correctly."""
    bodies: dict = {}
    for m in re.finditer(r"\$R\[(\d+)\]=\{", html):
        i = m.end() - 1  # index of the opening brace
        depth, j, n = 0, m.end() - 1, len(html)
        while j < n:
            c = html[j]
            if c == '"':
                j += 1
                while j < n and html[j] != '"':
                    j += 2 if html[j] == "\\" else 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        bodies[m.group(1)] = html[i:j + 1]
    return bodies


def _mygewo_units(html: str) -> List[dict]:
    """Extract structured unit dicts from mygewo's SSR-dehydrated data.

    mygewo (TanStack Start) server-renders the search results as a serialized
    object graph in an inline script. Each unit is a `{id:…,manualData:…,…}`
    literal carrying clean fields we can't get from the visible card text:
    `buyable` (the authoritative rent-vs-buy flag), the builder's own `url`
    (direct reservation page), zipcode, coordinates and amenity flags. We parse
    that graph rather than the rendered cards so the rent/buy split is exact and
    every builder link is captured without a per-detail fetch."""
    bodies = _seroval_ref_bodies(html)
    ref_company = {rid: mm.group(1) for rid, b in bodies.items()
                   if "readable_url:" in b and (mm := re.search(r'\bname:"([^"]*)"', b))}
    ref_zip = {rid: mm.group(1) for rid, b in bodies.items()
               if (mm := re.search(r'zipcode:"(\d+)"', b))}

    starts = [m.start() for m in re.finditer(r"\{id:\d+,manualData:", html)]
    starts.append(len(html))
    units: List[dict] = []
    for k in range(len(starts) - 1):
        seg = html[starts[k]:starts[k + 1]]
        if "external_unit_id:" not in seg:
            continue

        def s(pat: str) -> Optional[str]:
            mm = re.search(pat, seg)
            return mm.group(1) if mm else None

        city_ref = s(r"\bcity:\$R\[(\d+)\]")
        company_ref = s(r"\bcompany:\$R\[(\d+)\]")
        units.append({
            "uuid": s(r'\buuid:"([0-9a-f-]{36})"'),
            "url": s(r'\burl:"([^"]*)"'),
            "buyable": s(r"\bbuyable:(!0|!1|true|false|null)") in ("!0", "true"),
            "rooms": s(r'\brooms:"([\d.]+)"'),
            "rent": s(r'\brent:"([\d.]+)"'),
            "capital": s(r'\bcapital:"([\d.]+)"'),
            "area": s(r'\barea:"([\d.]+)"'),
            "street": s(r'\bstreet:"([^"]*)"'),
            "zipcode": ref_zip.get(city_ref or ""),
            "company": ref_company.get(company_ref or ""),
            "has_balcony": s(r"\bhas_balcony:(!0|!1|null)") == "!0",
            "has_terrace": s(r"\bhas_terrace:(!0|!1|null)") == "!0",
            "has_garden": s(r"\bhas_garden:(!0|!1|null)") == "!0",
            "has_loggia": s(r"\bhas_loggia:(!0|!1|null)") == "!0",
        })
    return units


def _to_float(v: Optional[str]) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _offer_url_map(html: str) -> dict:
    """uuid -> mygewo /angebot/ URL, recovered from the rendered result cards.

    Only page 0's ~25 cards are server-rendered, so this map covers the first
    page; units from later (RPC) pages fall back to their builder URL as the key."""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for a in soup.select('a[href^="/genossenschaftswohnungen/angebot/"]'):
        href = a.get("href", "")
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", href)
        if m:
            out[m.group(1)] = _MYGEWO_BASE + href
    return out


def _units_to_listings(units: List[dict], uuid_to_offer: dict) -> List[Listing]:
    """Map extracted mygewo unit dicts → Wien RENTAL Listings.

    Buy-option units (`buyable`, e.g. "…miete-mit-eo") are dropped — the user
    wants Genossenschaft rentals, never for-sale. Non-Wien rows (should already be
    excluded by states=28_) are dropped defensively via zipcode.

    `url` stays the mygewo /angebot/ page when a rendered card exists for the
    unit's uuid — the SAME key earlier records used — so a re-poll updates in
    place instead of forking a duplicate; otherwise it falls back to the builder's
    own reservation page. That builder page always goes to `builder_url`, which the
    dashboard and Telegram link to directly."""
    out: List[Listing] = []
    dropped_buy = dropped_nonwien = 0
    for u in units:
        builder_url = u["url"]
        if not builder_url:
            continue
        if u["buyable"]:                       # for-sale / rent-with-buy-option → not a rental
            dropped_buy += 1
            continue
        zipcode = u["zipcode"]
        if not (zipcode and re.match(r"^1\d{3}$", zipcode)):  # Wien PLZ are 1xxx
            dropped_nonwien += 1
            continue

        url = uuid_to_offer.get(u["uuid"] or "", builder_url)
        listing = _new_coop_listing(url, u["company"])
        listing.builder_url = builder_url      # the builder's own reservation page
        listing.buyable = False                # every emitted unit is a rental
        listing.area_m2 = _to_float(u["area"])
        listing.rooms = _to_float(u["rooms"])
        listing.price_total = _to_float(u["rent"])
        listing.own_funds = _to_float(u["capital"])
        listing.bezirk = zipcode
        street = u["street"]
        city = f"{zipcode} Wien"
        listing.address = f"{street}, {city}" if street else city
        listing.balcony_terrace = u["has_balcony"] or u["has_terrace"]
        feats = [name for flag, name in (
            (u["has_balcony"], "Balkon"), (u["has_terrace"], "Terrasse"),
            (u["has_loggia"], "Loggia"), (u["has_garden"], "Garten")) if flag]
        listing.special_features = feats

        rooms, area = listing.rooms, listing.area_m2
        summary = " · ".join(p for p in (
            f"{int(rooms)} Zimmer" if rooms else None,
            f"{area:.0f} m²" if area else None,
            u["company"]) if p)
        listing.title = f"{listing.address} – {summary}" if summary else listing.address
        out.append(listing)
    logger.info(f"🔍 mygewo: {len(out)} rental(s) parsed "
                f"(dropped {dropped_buy} buy-option, {dropped_nonwien} non-Wien)")
    return out


def parse_mygewo(html: str) -> List[Listing]:
    """Parse ONE server-rendered mygewo search page (page 0) into Wien rentals.

    Kept for the change-detection path and unit tests; the production crawl uses
    `fetch_all_mygewo`, which pages through every result via the RPC."""
    return _units_to_listings(_mygewo_units(html), _offer_url_map(html))


# --- Full-inventory pagination via mygewo's TanStack "server function" ---------
#
# mygewo's SSR HTML only carries page 0. The "Weiter" button calls this server
# function (reverse-engineered from the live site) with a seroval-encoded
# {search:{states}, page} payload and returns a seroval-JSON graph of the same
# unit objects — plus `total`/`hasNextPage` for paging. We replicate that exact
# request (headers + payload envelope) to fetch pages 1..N.
_MYGEWO_SERVERFN = (_MYGEWO_BASE +
    "/_serverFn/0bd589189b0d5f0ef7b3cef8396d61c095f0ec654c167c01db5d05fca34b86db")
_MYGEWO_RPC_HEADERS = {**_HEADERS,
    "accept": "application/x-tss-framed, application/x-ndjson, application/json",
    "x-tsr-serverfn": "true"}
_MYGEWO_MAX_PAGES = 20  # safety cap (~500 units) so a server bug can't loop forever


def _seroval_json_decode(node, refs: dict):
    """Decode seroval's JSON node form ({"t":<type>,"s"/"a"/"p":…}) into plain
    Python. Handles the types this API emits: number(0), string(1), constant(2:
    0=Null 1=Undefined 2=True 3=False), array(9), object(10), back-reference(3).
    `refs` maps a node's index `i` to the already-built value so repeated
    (deduplicated) company/city objects resolve on later references."""
    if not isinstance(node, dict):
        return None
    t = node.get("t")
    if t in (0, 1):
        return node.get("s")
    if t == 2:
        return {2: True, 3: False}.get(node.get("s"))  # 0/1 → None
    if t == 9:
        arr = []
        if "i" in node:
            refs[node["i"]] = arr
        for it in node.get("a", []):
            arr.append(_seroval_json_decode(it, refs))
        return arr
    if t == 10:
        obj = {}
        if "i" in node:
            refs[node["i"]] = obj
        p = node.get("p") or {}
        for k, v in zip(p.get("k", []), p.get("v", [])):
            obj[k] = _seroval_json_decode(v, refs)
        return obj
    if t == 3:
        return refs.get(node.get("i"))
    return None


def _find_units_payload(d):
    """Locate the {units, total, …} dict anywhere in the decoded response tree."""
    if isinstance(d, dict):
        if "units" in d and "total" in d:
            return d
        for v in d.values():
            found = _find_units_payload(v)
            if found:
                return found
    return None


def _mygewo_rpc_payload(states: str, page: int) -> dict:
    """The seroval-encoded {data:{search:{states}, page}} argument envelope."""
    return {"t": {"t": 10, "i": 0, "p": {"k": ["data"], "v": [
        {"t": 10, "i": 1, "p": {"k": ["search", "page"], "v": [
            {"t": 10, "i": 2, "p": {"k": ["states"], "v": [{"t": 1, "s": states}]}, "o": 0},
            {"t": 0, "s": page}]}, "o": 0}]}, "o": 0}, "f": 63, "m": []}


def _fetch_mygewo_page(states: str, page: int) -> Tuple[List[dict], int, bool]:
    """GET one RPC page. Returns (raw unit dicts, total, has_next_page)."""
    url = _MYGEWO_SERVERFN + "?payload=" + quote(
        json.dumps(_mygewo_rpc_payload(states, page), separators=(",", ":")))
    resp = requests.get(url, headers=_MYGEWO_RPC_HEADERS, timeout=20)
    resp.raise_for_status()
    try:
        root = json.loads(resp.text)
    except ValueError:  # framed/ndjson transport → first frame holds the graph
        root = json.loads(resp.text.splitlines()[0])
    pd = _find_units_payload(_seroval_json_decode(root, {}))
    if not pd:
        return [], 0, False
    return pd.get("units") or [], pd.get("total") or 0, bool(pd.get("hasNextPage"))


def _mygewo_units_from_rpc(units_json: List[dict]) -> List[dict]:
    """RPC unit objects → the same dict shape `_mygewo_units` produces from SSR,
    so both feed one mapping path (`_units_to_listings`)."""
    out: List[dict] = []
    for u in units_json:
        if not isinstance(u, dict):
            continue
        company = u.get("company") if isinstance(u.get("company"), dict) else {}
        city = u.get("city") if isinstance(u.get("city"), dict) else {}
        out.append({
            "uuid": u.get("uuid"),
            "url": u.get("url"),
            "buyable": u.get("buyable") is True,
            "rooms": u.get("rooms"),
            "rent": u.get("rent"),
            "capital": u.get("capital"),
            "area": u.get("area"),
            "street": u.get("street"),
            "zipcode": city.get("zipcode"),
            "company": company.get("name"),
            "has_balcony": u.get("has_balcony") is True,
            "has_terrace": u.get("has_terrace") is True,
            "has_garden": u.get("has_garden") is True,
            "has_loggia": u.get("has_loggia") is True,
        })
    return out


def _mygewo_ssr_url(states: str) -> str:
    return f"{_MYGEWO_BASE}/genossenschaftswohnungen/suche?states={states}"


def fetch_all_mygewo(states: str = "28_") -> List[Listing]:
    """Fetch the COMPLETE Wien co-op rental inventory from mygewo across all pages.

    Page 0's SSR cards give the stable mygewo /angebot/ URL per uuid (kept as the
    dedup key for continuity with existing DB rows); every unit (page 0..N) is
    pulled authoritatively from the paginated RPC so nothing past the first screen
    is dropped. Buy-option and non-Wien units are filtered in `_units_to_listings`."""
    try:
        uuid_to_offer = _offer_url_map(fetch(_mygewo_ssr_url(states)))
    except Exception as e:  # SSR page optional — only supplies nicer /angebot/ keys
        logger.warning(f"mygewo SSR page fetch failed ({e}); offer-url map empty")
        uuid_to_offer = {}

    units: List[dict] = []
    seen: set = set()
    page, total = 0, 0
    while page < _MYGEWO_MAX_PAGES:
        page_units, total, has_next = _fetch_mygewo_page(states, page)
        for u in page_units:
            uid = u.get("uuid")
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            units.append(u)
        if not page_units or not has_next or (total and len(units) >= total):
            break
        page += 1

    listings = _units_to_listings(_mygewo_units_from_rpc(units), uuid_to_offer)
    logger.info(f"🔍 mygewo: {len(units)} unit(s) across {page + 1} page(s) "
                f"(total={total}) → {len(listings)} Wien rental(s)")
    return listings


def resolve_builder_url(offer_url: str) -> Optional[str]:
    """Resolve a mygewo /angebot/ URL to the builder's own reservation page.

    mygewo detail pages (TanStack SSR) carry an "Original-Anzeige" anchor linking
    straight to the Bauträger's listing (wohnen.at, arwag.at, …) — that's where a
    unit is actually reserved. bs4's find(string=…) misses it (the anchor wraps
    nested markup), so scan anchors by visible text. Fall back to the builder's
    homepage ("gefunden auf <domain>.at") when the deep link is absent, else None."""
    try:
        html = fetch(offer_url)
    except Exception as e:
        logger.warning(f"builder-url fetch failed for {offer_url}: {e}")
        return None
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "Original-Anzeige" in a.get_text():
            href = a["href"]
            if href.startswith("http") and "mygewo.at" not in href:
                return href
    m = re.search(r"gefunden auf\s+([\w.\-]+\.at)", html, re.I)
    if m:
        domain = m.group(1)
        domain = domain[4:] if domain.startswith("www.") else domain
        return "https://www." + domain
    return None


def scrape_all() -> List[Listing]:
    out: List[Listing] = []
    for name, cfg in SOURCES.items():
        try:
            if cfg.get("fetcher"):  # self-contained multi-request crawl (mygewo RPC)
                out.extend(globals()[cfg["fetcher"]](cfg.get("states", "28_")))
            else:
                out.extend(globals()[cfg["parser"]](fetch(cfg["url"])))
        except Exception as e:  # one bad adapter must not kill the rest
            logger.error(f"co-op adapter {name} failed: {e}")
    return out
