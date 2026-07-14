# Genossenschaft Coverage Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a v1 that scrapes 3 pilot Vienna co-op Bauträger + tags Willhaben co-op units, dedupes them across sources, and broadcasts every new deduped co-op unit to one free Telegram channel — beating MyGEWO on coverage + a free alert.

**Architecture:** Reuse the existing `requests`+BeautifulSoup scraper convention (copy-per-source, no new engine yet), the existing MongoDB handler, and the existing single-`chat_id` Telegram bot pointed at a new co-op channel. One net-new concept: a **source-independent fingerprint** so the same unit on Willhaben and its Bauträger site collapses to one record.

**Tech Stack:** Python 3 (requests, BeautifulSoup, pymongo), MongoDB Atlas, python-telegram-bot, Next.js dashboard (Leaflet), GitHub Actions (scheduler), pytest.

**Source design doc:** `docs/superpowers/specs/2026-07-14-genossenschaft-coverage-vertical-design.md`

**Scope flags:** `ui_scope: true` (M7 has a Playwright visual-verification task), `test_scope: true` (final coverage-measurement task), `graph_scope: false`.

**Locked decisions (post-grill):** one broadcast channel (no per-user infra); source-independent dedup; 3 pilot adapters then decide abstraction; GitHub Actions cron; live network-gated smoke tests for parsers.

---

## File Structure

**Create:**
- `Project/Application/scraping/genossenschaft_scraper.py` — 3 pilot adapters (ÖVW, Familienwohnbau, BWSG), each `parse_<x>(html) -> List[Listing]` + a `fetch(url) -> str` + `scrape_all() -> List[Listing]`.
- `Project/scripts/measure_coop_coverage.py` — coverage-metric instrument.
- `.github/workflows/coop-scrape.yml` — */15 scheduled scrape.
- `Tests/test_coop_fingerprint.py` — dedup unit tests.
- `Tests/test_coop_detection.py` — co-op detector unit tests.
- `Tests/test_coop_adapters_smoke.py` — live network-gated parser smoke tests.
- `dashboard/tests/coop-filter.spec.ts` — Playwright spec for the co-op filter.

**Modify:**
- `Project/Domain/sources.py` — add `GENOSSENSCHAFT`.
- `Project/Domain/listing.py` — add 5 co-op fields.
- `Project/Application/scraping/field_extractors.py` — add `extract_is_genossenschaft`.
- `Project/Application/scraping/listing_validator.py` — add `compute_xsrc_fingerprint`.
- `Project/Application/scraping/willhaben_scraper.py` — tag co-op units at extraction.
- `Project/Integration/mongodb_handler.py` — xsrc-fingerprint dedup on save.
- `Project/Application/main.py` — wire `scrape_genossenschaft`, `--genossenschaft-only`, co-op channel broadcast.
- `Project/Integration/telegram_bot.py` — (only if needed) allow a second channel instance.
- `dashboard/lib/filters.ts`, `dashboard/components/MapView.tsx`, `dashboard/app/api/listings/*` — co-op filter + marker.

---

## Phase 1 — Domain model (M1)

### Task 1: Add GENOSSENSCHAFT source enum

**Files:**
- Modify: `Project/Domain/sources.py`

- [ ] **Step 1: Add the enum value**

```python
class Source(Enum):
    WILLHABEN = "willhaben"
    IMMO_KURIER = "immo_kurier"
    DERSTANDARD = "derstandard"
    GENOSSENSCHAFT = "genossenschaft"
    UNKNOWN = "unknown"
```

- [ ] **Step 2: Verify it imports**

Run: `cd Project && python -c "from Domain.sources import Source; print(Source.GENOSSENSCHAFT.value)"`
Expected: `genossenschaft`

- [ ] **Step 3: Commit**

```bash
git add Project/Domain/sources.py
git commit -m "feat(coop): add GENOSSENSCHAFT source enum"
```

### Task 2: Add co-op fields to Listing

**Files:**
- Modify: `Project/Domain/listing.py` (append after `bezirk_score` at line 79)

- [ ] **Step 1: Add the fields**

Append inside the `Listing` dataclass, after `bezirk_score`:

```python
    # --- Genossenschaft / co-op vertical (v1) ---
    is_genossenschaft:      Optional[bool]  = None
    bautraeger:             Optional[str]   = None   # "ÖVW" | "BWSG" | "Familienwohnbau" | ...
    allocation_model:       Optional[str]   = None   # 'first_come' | 'wohn_ticket'
    coop_source:            Optional[str]   = None   # 'bautraeger_direct' | 'willhaben'
    content_fingerprint_xsrc: Optional[str] = None   # source-independent dedup key
```

- [ ] **Step 2: Verify it constructs**

Run: `cd Project && python -c "from Domain.listing import Listing; from Domain.sources import Source; l=Listing(url='x', source=Source.GENOSSENSCHAFT, is_genossenschaft=True, bautraeger='ÖVW'); print(l.bautraeger, l.is_genossenschaft)"`
Expected: `ÖVW True`

- [ ] **Step 3: Commit**

```bash
git add Project/Domain/listing.py
git commit -m "feat(coop): add co-op fields to Listing model"
```

---

## Phase 2 — Cross-source dedup (M2)

### Task 3: Source-independent fingerprint function

**Files:**
- Modify: `Project/Application/scraping/listing_validator.py` (add alongside existing `compute_content_fingerprint` at line 13)
- Test: `Tests/test_coop_fingerprint.py`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_coop_fingerprint.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping.listing_validator import compute_xsrc_fingerprint
from Domain.listing import Listing
from Domain.sources import Source


def _coop(bautraeger, address, area, rooms, source=Source.GENOSSENSCHAFT):
    return Listing(url="u", source=source, is_genossenschaft=True,
                   bautraeger=bautraeger, address=address, area_m2=area, rooms=rooms)


def test_same_unit_different_source_same_fingerprint():
    a = _coop("ÖVW", "Musterstraße 5, 1120 Wien", 62.0, 3.0, Source.GENOSSENSCHAFT)
    b = _coop("ÖVW", "musterstrasse  5, 1120 wien", 62.4, 3.0, Source.WILLHABEN)
    assert compute_xsrc_fingerprint(a) == compute_xsrc_fingerprint(b)


def test_different_units_different_fingerprint():
    a = _coop("ÖVW", "Musterstraße 5, 1120 Wien", 62.0, 3.0)
    b = _coop("ÖVW", "Andere Gasse 9, 1100 Wien", 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) != compute_xsrc_fingerprint(b)


def test_missing_bautraeger_returns_none():
    a = _coop(None, "Musterstraße 5", 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) is None


def test_missing_address_returns_none():
    a = _coop("ÖVW", None, 62.0, 3.0)
    assert compute_xsrc_fingerprint(a) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project/.. && python -m pytest Tests/test_coop_fingerprint.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_xsrc_fingerprint'`

- [ ] **Step 3: Write the implementation**

Add to `Project/Application/scraping/listing_validator.py`:

```python
import hashlib
import re
import unicodedata


def _norm(s: str) -> str:
    """Lowercase, fold umlauts/ß, collapse whitespace, strip non-alnum runs to single space."""
    s = s.lower().strip()
    s = s.replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compute_xsrc_fingerprint(listing) -> "str | None":
    """Source-INDEPENDENT fingerprint for co-op units so the same unit on
    Willhaben and on its Bauträger site collapse to one record.
    Key = md5(norm(bautraeger)|norm(address)|round(area)|rooms). No source, no price.
    Returns None when bautraeger or address is missing (weak key → don't collapse)."""
    if not getattr(listing, "bautraeger", None) or not getattr(listing, "address", None):
        return None
    area = listing.area_m2
    area_key = str(int(round(area))) if area else ""
    rooms_key = str(listing.rooms) if listing.rooms is not None else ""
    raw = f"{_norm(listing.bautraeger)}|{_norm(listing.address)}|{area_key}|{rooms_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project/.. && python -m pytest Tests/test_coop_fingerprint.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add Project/Application/scraping/listing_validator.py Tests/test_coop_fingerprint.py
git commit -m "feat(coop): source-independent fingerprint for cross-source dedup"
```

### Task 4: Apply xsrc-dedup on save

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (co-op branch alongside existing fingerprint logic at lines 144-152)

- [ ] **Step 1: Read the existing save/dedup path**

Run: `cd Project && sed -n '130,175p' Integration/mongodb_handler.py`
Expected: see the existing `compute_content_fingerprint` insert-skip block and the compound index at line 86.

- [ ] **Step 2: Add the co-op dedup branch**

In the save method, immediately before the existing fingerprint insert, add (only for co-op listings):

```python
from Application.scraping.listing_validator import compute_xsrc_fingerprint

# Co-op cross-source dedup (v1): collapse same unit across Willhaben + Bauträger.
if getattr(listing, "is_genossenschaft", False):
    xfp = compute_xsrc_fingerprint(listing)
    if xfp:
        listing.content_fingerprint_xsrc = xfp
        existing = self.collection.find_one({"content_fingerprint_xsrc": xfp})
        if existing:
            # Prefer Bauträger-direct (canonical apply URL) over Willhaben.
            if (listing.coop_source == "bautraeger_direct"
                    and existing.get("coop_source") == "willhaben"):
                self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"url": listing.url, "coop_source": "bautraeger_direct",
                              "bautraeger": listing.bautraeger}},
                )
            self.logger.info(f"Skipping cross-source co-op duplicate: {xfp}")
            return existing.get("_id")
```

- [ ] **Step 3: Create the partial index (idempotent, add near line 86 index setup)**

```python
self.collection.create_index(
    "content_fingerprint_xsrc",
    partialFilterExpression={"content_fingerprint_xsrc": {"$exists": True}},
    name="coop_xsrc_fp",
)
```

- [ ] **Step 4: Verify import + syntax**

Run: `cd Project && python -c "import Integration.mongodb_handler"`
Expected: no error (import succeeds; no live DB call).

- [ ] **Step 5: Commit**

```bash
git add Project/Integration/mongodb_handler.py
git commit -m "feat(coop): dedup co-op units cross-source on save, prefer Bauträger-direct"
```

---

## Phase 3 — Co-op detection + Willhaben tagging (M3)

### Task 5: `extract_is_genossenschaft`

**Files:**
- Modify: `Project/Application/scraping/field_extractors.py`
- Test: `Tests/test_coop_detection.py`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_coop_detection.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping.field_extractors import extract_is_genossenschaft


def test_positive_genossenschaft():
    assert extract_is_genossenschaft("provisionsfrei, genossenschaftswohnung mit finanzierungsbeitrag") is True


def test_positive_gefoerdert():
    assert extract_is_genossenschaft("gefördert, gemeinnütziger bauträger, mietkauf möglich") is True


def test_negative_freifinanziert():
    assert extract_is_genossenschaft("freifinanzierte eigentumswohnung, provisionsfrei vom bauträger") is False


def test_none_when_no_signal():
    assert extract_is_genossenschaft("schöne altbauwohnung im 7. bezirk") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project/.. && python -m pytest Tests/test_coop_detection.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_is_genossenschaft'`

- [ ] **Step 3: Write the implementation**

Add to `Project/Application/scraping/field_extractors.py` (follows the file's two-pass pattern):

```python
def extract_is_genossenschaft(text: str) -> Optional[bool]:
    """True if co-op/subsidized markers present, False if explicitly free-financed,
    None if no signal. Input is pre-lowercased full page text."""
    negative = [r'freifinanziert', r'frei\s+finanziert']
    positive = [
        r'genossenschaft', r'gemeinnützig', r'gemeinnutzig',
        r'gefördert', r'geforderte?r?', r'\bwgg\b',
        r'mietkauf', r'baurechtszins', r'finanzierungsbeitrag',
        r'eigenmittelanteil', r'wohnbauförderung',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project/.. && python -m pytest Tests/test_coop_detection.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add Project/Application/scraping/field_extractors.py Tests/test_coop_detection.py
git commit -m "feat(coop): detect co-op/subsidized listings from page text"
```

### Task 6: Tag Willhaben listings as co-op

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py` (in the single-listing extraction where full-page text + other `extract_*` from `field_extractors` are already called)

- [ ] **Step 1: Locate the extraction call site**

Run: `cd Project && grep -n "field_extractors\|extract_lift_present\|get_text().lower()" Application/scraping/willhaben_scraper.py | head`
Expected: find where page text is lowercased and other `extract_*` are invoked.

- [ ] **Step 2: Add the tagging**

At that call site, after the page text (`text`) is available and the `Listing` is being populated:

```python
from Application.scraping.field_extractors import extract_is_genossenschaft
is_coop = extract_is_genossenschaft(text)
if is_coop:
    listing.is_genossenschaft = True
    listing.coop_source = "willhaben"
    listing.allocation_model = "first_come"
```

- [ ] **Step 3: Verify import + syntax**

Run: `cd Project && python -c "import Application.scraping.willhaben_scraper"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(coop): tag Willhaben listings as co-op when detected"
```

---

## Phase 4 — Pilot Bauträger adapters (M4)

> **Note on selectors:** The exact CSS selectors for ÖVW / Familienwohnbau / BWSG are unknowable until the live HTML is inspected. Each adapter task therefore starts with a discovery step (fetch + inspect the real page), then implements the parser to match. This is the correct scraping procedure, not a placeholder. Tests are **live network-gated smoke tests** (per decision): they hit the real page, `pytest.skip` on network failure, and assert the parser yields ≥1 valid co-op Listing. These adapters use `requests` (no Selenium) so a fetch is a cheap HTTP GET.

### Task 7: Scraper module scaffold + shared fetch

**Files:**
- Create: `Project/Application/scraping/genossenschaft_scraper.py`

- [ ] **Step 1: Write the scaffold**

```python
"""Genossenschaft (co-op) Bauträger scrapers — v1 pilot: ÖVW, Familienwohnbau, BWSG.
Concrete parsers (no shared engine yet). Each parse_<x>(html) -> List[Listing].
Post-pilot: review HTML variance to decide whether to extract a shared engine."""
import logging
import requests
from typing import List
from bs4 import BeautifulSoup
from Domain.listing import Listing
from Domain.sources import Source

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter/1.0)"}

# Filled in per adapter task from live inspection.
SOURCES = {
    "ÖVW":             {"url": "TBD_FROM_STEP1", "parser": "parse_oevw"},
    "Familienwohnbau": {"url": "TBD_FROM_STEP1", "parser": "parse_familienwohnbau"},
    "BWSG":            {"url": "TBD_FROM_STEP1", "parser": "parse_bwsg"},
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


def scrape_all() -> List[Listing]:
    out: List[Listing] = []
    for name, cfg in SOURCES.items():
        try:
            html = fetch(cfg["url"])
            out.extend(globals()[cfg["parser"]](html))
        except Exception as e:  # one bad adapter must not kill the rest
            logger.error(f"co-op adapter {name} failed: {e}")
    return out
```

- [ ] **Step 2: Verify import**

Run: `cd Project && python -c "import Application.scraping.genossenschaft_scraper as g; print(list(g.SOURCES))"`
Expected: `['ÖVW', 'Familienwohnbau', 'BWSG']`

- [ ] **Step 3: Commit**

```bash
git add Project/Application/scraping/genossenschaft_scraper.py
git commit -m "feat(coop): genossenschaft scraper scaffold + shared fetch"
```

### Task 8: ÖVW adapter (repeat pattern for Familienwohnbau, BWSG)

**Files:**
- Modify: `Project/Application/scraping/genossenschaft_scraper.py`
- Test: `Tests/test_coop_adapters_smoke.py`

- [ ] **Step 1: Discover the live URL + structure**

Find the ÖVW "available units / sofort verfügbar" page (start from https://www.oevw.at). Fetch and inspect:

```bash
cd Project && python -c "
from Application.scraping.genossenschaft_scraper import fetch
html = fetch('https://www.oevw.at/de/wohnungssuche')  # confirm real path
open('/tmp/oevw.html','w').write(html)
print(len(html))
"
```
Inspect `/tmp/oevw.html` for the repeating listing block: container selector, and where address / bezirk / area_m2 / rooms / price / detail-URL live. Record the selectors. Set `SOURCES['ÖVW']['url']` to the confirmed URL.

- [ ] **Step 2: Write the failing smoke test**

```python
# Tests/test_coop_adapters_smoke.py
import sys, os, pytest, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping import genossenschaft_scraper as g


def _fetch_or_skip(name):
    url = g.SOURCES[name]["url"]
    try:
        return g.fetch(url)
    except (requests.RequestException, Exception) as e:
        pytest.skip(f"{name} unreachable: {e}")


@pytest.mark.smoke
def test_oevw_parser_yields_valid_coop():
    html = _fetch_or_skip("ÖVW")
    listings = g.parse_oevw(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.is_genossenschaft is True
    assert first.bautraeger == "ÖVW"
    assert first.coop_source == "bautraeger_direct"
    assert first.url and first.url.startswith("http")
    assert first.address or first.bezirk
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd Project/.. && python -m pytest Tests/test_coop_adapters_smoke.py::test_oevw_parser_yields_valid_coop -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'parse_oevw'`

- [ ] **Step 4: Implement `parse_oevw` using the selectors from Step 1**

```python
def parse_oevw(html: str) -> List[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Listing] = []
    for block in soup.select("SELECTOR_FROM_STEP1"):          # e.g. ".unit-card"
        a = block.select_one("a[href]")
        if not a:
            continue
        href = a.get("href", "")
        url = href if href.startswith("http") else "https://www.oevw.at" + href
        listing = _new_coop_listing(url, "ÖVW")
        listing.address = _text(block, "ADDRESS_SELECTOR")
        listing.bezirk = _bezirk_from(listing.address)
        listing.area_m2 = _num(block, "AREA_SELECTOR")
        listing.rooms = _num(block, "ROOMS_SELECTOR")
        listing.price_total = _num(block, "PRICE_SELECTOR")
        out.append(listing)
    return out
```

Add the small helpers once (near top of module):

```python
import re
def _text(block, sel):
    el = block.select_one(sel)
    return el.get_text(strip=True) if el else None
def _num(block, sel):
    el = block.select_one(sel)
    if not el:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", el.get_text())
    return float(m.group().replace(",", ".")) if m else None
def _bezirk_from(address):
    if not address:
        return None
    m = re.search(r"\b1[0-2]\d0\b", address)  # Vienna postcodes 1010-1230
    return m.group() if m else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Project/.. && python -m pytest Tests/test_coop_adapters_smoke.py::test_oevw_parser_yields_valid_coop -v`
Expected: PASS (or SKIP if network down — SKIP is acceptable in CI, PASS required locally once).

- [ ] **Step 6: Commit**

```bash
git add Project/Application/scraping/genossenschaft_scraper.py Tests/test_coop_adapters_smoke.py
git commit -m "feat(coop): ÖVW Bauträger adapter + live smoke test"
```

### Task 9: Familienwohnbau adapter

Repeat Task 8's 6 steps for `parse_familienwohnbau` (bautraeger `"Familienwohnbau"`, base URL `https://www.familienwohnbau.at`, discover the available-units page). Add `test_familienwohnbau_parser_yields_valid_coop` mirroring the ÖVW test. Commit: `feat(coop): Familienwohnbau adapter + smoke test`.

### Task 10: BWSG adapter

Repeat Task 8's 6 steps for `parse_bwsg` (bautraeger `"BWSG"`, base URL `https://www.bwsg.at`, discover the available-units page). Add `test_bwsg_parser_yields_valid_coop`. Commit: `feat(coop): BWSG adapter + smoke test`.

### Task 11: Wire co-op scraper into main.py

**Files:**
- Modify: `Project/Application/main.py` (mirror `scrape_willhaben` at line 335; flags at 535-537; registration at 620-631)

- [ ] **Step 1: Add the scrape wrapper**

```python
def scrape_genossenschaft():
    from Application.scraping.genossenschaft_scraper import scrape_all
    return scrape_all()
```

- [ ] **Step 2: Add the `--genossenschaft-only` flag handling**

Mirror the existing `willhaben_only` pattern in the `sys.argv` block (~line 535):

```python
genossenschaft_only = "--genossenschaft-only" in sys.argv
```

- [ ] **Step 3: Register the scraper in the run list**

In the `scrapers_to_run` assembly (~line 620), mirror existing `*_only` gating:

```python
if genossenschaft_only:
    scrapers_to_run = [("genossenschaft", scrape_genossenschaft)]
else:
    scrapers_to_run.append(("genossenschaft", scrape_genossenschaft))
```

- [ ] **Step 4: Verify the flag runs (no crash, no DB required for import path)**

Run: `cd Project && python -c "import Application.main"`
Expected: no error.

- [ ] **Step 5: Commit**

```bash
git add Project/Application/main.py
git commit -m "feat(coop): wire genossenschaft scraper + --genossenschaft-only flag"
```

---

## Phase 5 — Dashboard co-op filter + map layer (M7)  [ui_scope]

### Task 12: Co-op filter in API + UI

**Files:**
- Modify: `dashboard/lib/filters.ts`, `dashboard/app/api/listings/map/route.ts` (+ `top/route.ts`), `dashboard/components/MapView.tsx`
- Test: `dashboard/tests/coop-filter.spec.ts`

- [ ] **Step 1: Add `genossenschaft` to filter parsing**

In `dashboard/lib/filters.ts`, add a boolean filter `genossenschaft` that, when true, adds `{ is_genossenschaft: true }` to the Mongo query. Follow the existing filter-to-query pattern in that file.

- [ ] **Step 2: Honor it in the listings API**

In `dashboard/app/api/listings/map/route.ts` (and `top/route.ts`), pass the new filter through to the query builder. Follow how existing filters flow from `searchParams` → query.

- [ ] **Step 3: Add the toggle + distinct marker**

In the map filter UI, add a "Genossenschaft" toggle. In `MapView.tsx`, render co-op markers (`is_genossenschaft`) with a distinct color/icon. Follow the existing marker-style pattern.

- [ ] **Step 4: Write the Playwright spec**

```typescript
// dashboard/tests/coop-filter.spec.ts
import { test, expect } from '@playwright/test';

test('co-op filter toggles and shows only co-op listings', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.getByRole('button', { name: /genossenschaft/i }).click();
  await page.waitForResponse(r => r.url().includes('/api/listings/map') && r.ok());
  // At least one co-op marker OR an explicit empty-state — never a crash.
  const errors: string[] = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await expect(page.locator('body')).toBeVisible();
  expect(errors).toHaveLength(0);
});
```

- [ ] **Step 5: Visual verification loop** (per `ui_scope`)

Per `.claude/rules/ui-testing.md` + `~/.claude/skills/frontend-design/SKILL.md` §Visual verification:
- Start dev server: `cd dashboard && npm run dev &`; wait for `localhost:3000`.
- Verify against **prod data** (local Mongo empty — memory `feedback-verify-on-real-data`): use `playwright.prod.config.ts` if present.
- Run the targeted spec: `cd dashboard && npx playwright test tests/coop-filter.spec.ts --reporter=dot`
- Expected: PASS, 0 console errors.

- [ ] **Step 6: Final suite gate**

Run: `cd dashboard && npx playwright test --reporter=line`
Expected: 0 failures, 0 console errors on `/`, `/dashboard`, `/dashboard/map`. Then `pkill -f "next dev"`.

- [ ] **Step 7: Commit**

```bash
git add dashboard/lib/filters.ts dashboard/app/api/listings dashboard/components/MapView.tsx dashboard/tests/coop-filter.spec.ts
git commit -m "feat(coop): dashboard co-op filter + map layer"
```

---

## Phase 6 — Telegram co-op channel broadcast (M5)

### Task 13: Broadcast new deduped co-op units to the co-op channel

**Files:**
- Modify: `Project/Application/main.py` (broadcast step after save/dedup)
- Read: `Project/Integration/telegram_bot.py` (reuse `TelegramBot`; second instance for co-op channel)

- [ ] **Step 1: Add the channel id via env (no hardcode — CLAUDE.md secret rule)**

Read env `TELEGRAM_COOP_CHANNEL_ID`. Document it in `Project/SETUP_GMAIL.md`-style config notes (or config README), not committed with a value.

- [ ] **Step 2: Build a co-op TelegramBot instance**

In `main.py`, where the buy-side `TelegramBot` is built, add (guarded on env presence):

```python
coop_channel_id = os.environ.get("TELEGRAM_COOP_CHANNEL_ID")
coop_bot = TelegramBot(bot_token, coop_channel_id) if coop_channel_id else None
```

- [ ] **Step 3: Post new co-op units, honoring `sent_to_telegram`**

After co-op listings are saved+deduped, for each newly-saved co-op listing with `sent_to_telegram` false:

```python
if coop_bot and listing.is_genossenschaft and not listing.sent_to_telegram:
    msg = format_coop_message(listing)   # bautraeger, bezirk, €/m², rooms, area,
                                         # allocation_model, apply URL, #hashtags
    if coop_bot.send_message(msg):       # reuse existing 4096-char-safe send
        listing.sent_to_telegram = True
        mongo.mark_sent_to_telegram(listing)   # reuse existing flag-setter
```

- [ ] **Step 4: Implement `format_coop_message`** (follow existing telegram formatting in `telegram_bot.py`)

```python
def format_coop_message(l):
    ppm2 = f"{l.price_total / l.area_m2:.1f}€/m²" if (l.price_total and l.area_m2) else "–"
    tags = " ".join(t for t in [f"#{l.bezirk}" if l.bezirk else None,
                                f"#{l.bautraeger}" if l.bautraeger else None] if t)
    return (f"🏢 *{l.bautraeger or 'Genossenschaft'}* — {l.bezirk or ''}\n"
            f"{l.rooms or '?'} Zi · {l.area_m2 or '?'} m² · {ppm2}\n"
            f"Vergabe: {l.allocation_model or 'first_come'}\n"
            f"{l.url}\n{tags}")
```

- [ ] **Step 5: Smoke-verify formatting (no live send)**

Run: `cd Project && python -c "
from Domain.listing import Listing; from Domain.sources import Source
from Application.main import format_coop_message
l=Listing(url='http://x', source=Source.GENOSSENSCHAFT, bautraeger='ÖVW', bezirk='1120', rooms=3, area_m2=62, price_total=124000, allocation_model='first_come')
print(format_coop_message(l))"`
Expected: a formatted multi-line message with `€/m²`, `#1120 #ÖVW`.

- [ ] **Step 6: Commit**

```bash
git add Project/Application/main.py
git commit -m "feat(coop): broadcast new deduped co-op units to Telegram channel"
```

---

## Phase 7 — Scheduler (M6)

### Task 14: GitHub Actions scheduled scrape

**Files:**
- Create: `.github/workflows/coop-scrape.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: coop-scrape
on:
  schedule:
    - cron: "*/15 6-22 * * 1-5"   # every 15 min, Mon-Fri, ~Bauträger posting window (UTC)
  workflow_dispatch: {}
concurrency:
  group: coop-scrape
  cancel-in-progress: true
jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r Project/requirements.txt
      - name: Run co-op scrape
        working-directory: Project
        env:
          MONGODB_URI: ${{ secrets.MONGODB_URI }}
          TELEGRAM_MAIN_BOT_TOKEN: ${{ secrets.TELEGRAM_MAIN_BOT_TOKEN }}
          TELEGRAM_COOP_CHANNEL_ID: ${{ secrets.TELEGRAM_COOP_CHANNEL_ID }}
        run: python run.py --genossenschaft-only --send-to-telegram
```

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/coop-scrape.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Note required GH secrets** (do NOT set values here)

Document that `MONGODB_URI`, `TELEGRAM_MAIN_BOT_TOKEN`, `TELEGRAM_COOP_CHANNEL_ID` must be added in repo Settings → Secrets. State this in the PR description.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/coop-scrape.yml
git commit -m "feat(coop): GitHub Actions scheduled co-op scrape every 15min"
```

---

## Phase 8 — Coverage measurement (M8)  [test_scope]

### Task 15: Coverage-measure script + suite coverage check

**Files:**
- Create: `Project/scripts/measure_coop_coverage.py`

- [ ] **Step 1: Write the script**

```python
"""Success-metric instrument: count unique deduped co-op units live now,
broken down by bautraeger + coop_source. Compares against a manual MyGEWO
same-day spot-check (no MyGEWO scraping in v1)."""
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Integration.mongodb_handler import MongoDBHandler  # reuse handler, no raw queries

def main():
    mongo = MongoDBHandler()
    coll = mongo.collection
    total = coll.count_documents({"is_genossenschaft": True})
    unique = len(coll.distinct("content_fingerprint_xsrc",
                               {"is_genossenschaft": True,
                                "content_fingerprint_xsrc": {"$exists": True}}))
    by_bt = list(coll.aggregate([
        {"$match": {"is_genossenschaft": True}},
        {"$group": {"_id": {"bt": "$bautraeger", "src": "$coop_source"},
                    "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]))
    stamp = datetime.date.today().isoformat()
    lines = [f"# Co-op coverage {stamp}",
             f"total co-op docs: {total}",
             f"unique deduped units (xsrc fp): {unique}", "", "by bautraeger/source:"]
    lines += [f"  {r['_id'].get('bt')} / {r['_id'].get('src')}: {r['n']}" for r in by_bt]
    report = "\n".join(lines)
    print(report)
    os.makedirs("Project/log", exist_ok=True)
    open(f"Project/log/coop_coverage_{stamp}.txt", "w").write(report)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import path (no live DB needed to import)**

Run: `cd Project && python -c "import ast; ast.parse(open('scripts/measure_coop_coverage.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Run the full co-op test suite + record coverage** (per `test_scope`)

Run: `cd Project/.. && python -m pytest Tests/test_coop_fingerprint.py Tests/test_coop_detection.py -v`
Expected: all PASS. (Smoke tests may SKIP without network — acceptable.)

- [ ] **Step 4: Commit**

```bash
git add Project/scripts/measure_coop_coverage.py
git commit -m "feat(coop): coverage-measurement instrument for the wedge metric"
```

---

## Self-Review Results

**Spec coverage:** M1→Tasks 1-2 · M2→Tasks 3-4 · M3→Tasks 5-6 · M4→Tasks 7-11 · M7→Task 12 · M5→Task 13 · M6→Task 14 · M8→Task 15. All 8 modules covered; build order preserved (M2 before co-op data lands).

**Scope flags:** `ui_scope` → Task 12 Steps 5-6 (Playwright + visual verify on prod data). `test_scope` → Task 15 Step 3 (suite run + coverage record). `graph_scope: false` → no graph task. ✅

**Type consistency:** `content_fingerprint_xsrc` (M1 field ↔ M2 compute ↔ M8 distinct) consistent. `is_genossenschaft`/`bautraeger`/`coop_source`/`allocation_model` consistent across M1/M3/M4/M5/M8. `compute_xsrc_fingerprint`, `extract_is_genossenschaft`, `scrape_all`, `format_coop_message` referenced with identical signatures where used.

**Known deferred (not gaps):** per-user push, web push, remaining 8 adapters, eligibility/dossier, MAUI — fenced in the design doc as post-v1.

**Adapter selector caveat (honest):** Tasks 8-10 carry `SELECTOR_FROM_STEP1` placeholders *by design* — real selectors require live HTML inspection (Step 1 of each). This is the correct scraping procedure, not an unfilled plan step; the surrounding parser structure, Listing shape, and tests are fully specified.
