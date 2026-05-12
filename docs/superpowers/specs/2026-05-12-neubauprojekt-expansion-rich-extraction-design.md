# Design: Neubauprojekt Sub-listing Expansion + Rich HTML Field Extraction

**Date:** 2026-05-12  
**Status:** Approved  
**Scope:** Willhaben scraper enhancements — Phase 2 of bank_loan_ready data pipeline

---

## Problem

Two gaps in the current willhaben scraper:

1. **Neubauprojekt pages return wrong data.** When a search results page links to `/d/neubauprojekt/` URLs, `scrape_single_listing` scrapes the project overview page and gets aggregated/incorrect data (e.g. "ab €280.000" instead of a specific unit's price). Individual unit pages (`/d/eigentumswohnung/`) are never scraped.

2. **Rich structured data in `__NEXT_DATA__` is untapped.** Each individual listing page embeds a comprehensive attribute array in the server-rendered JSON. Fields directly relevant to the Vienna Property Scoring Framework (Rücklage, Betriebskosten, floor type, kitchen, windows, Doppelmakler, outdoor area) are available but not extracted.

---

## Decisions (from grill-me session)

| Decision | Resolution |
|---|---|
| Neubauprojekt pagination | None needed — all unit links in initial DOM load |
| Unit URL selector | Broad: `/iad/immobilien/d/` excluding `/d/neubauprojekt/` itself |
| Re-fetch project pages | Accept one extra HTTP request per project per run; per-unit dedup handles the rest |
| New extractor input | Targeted attribute text (stripped HTML from specific `GENERAL_TEXT_ADVERT/*` keys), not full page text |
| Rücklage source | `GENERAL_TEXT_ADVERT/Preis - Detailinformation` — structured `<li>` list with exact EUR/month value |
| `extract_from_json_data` | Untouched — new `extract_attributes_dict` added as separate method |
| Multi-scraper scope | Boolean text extractors → all 3 scrapers; attributes dict → willhaben only |
| Scoring changes | Phase 2 — extract now, score later |
| Tests | Unit tests only; no new integration tests |
| PDF document URLs | Stored as-is (no parsing) — free add-on via `data-testid` selector |

---

## Module Designs

### Module: `is_project_url` + `expand_project_to_units`
- **Responsibility:** Detect neubauprojekt URLs and expand them to individual unit URLs
- **Interface:** `is_project_url(url: str) -> bool`; `expand_project_to_units(url: str) -> List[str]`
- **Dependencies:** `_fetch_with_retry`, `BeautifulSoup`
- **Size target:** ~30 lines, single responsibility

`is_project_url`: returns `'/d/neubauprojekt/' in url`

`expand_project_to_units`: sleeps 1.0s (same rate as regular listing requests), fetches project page, calls `self.extract_listing_urls(soup)` (reuses existing selector + dedup logic), then filters out any URL containing `/d/neubauprojekt/`. Returns filtered list. If fetch fails, returns empty list (caller logs and skips).

### Module: `scrape_search_agent_page` (modified)
- **Responsibility:** Orchestrate per-page scraping; expand project URLs before scraping units
- **Interface:** unchanged — `(alert_url: str, max_pages: int) -> List[Listing]`
- **Dependencies:** `is_project_url`, `expand_project_to_units`
- **Size target:** ~10 lines added to existing method

When `is_project_url(listing_url)` is True:
1. Call `expand_project_to_units(listing_url)` → unit URLs
2. Add unit URLs to scrape queue (replace project URL with its units)
3. Never call `scrape_single_listing` on the project URL itself

### Module: `extract_attributes_dict`
- **Responsibility:** Parse `__NEXT_DATA__` attributes array into a flat lookup dict
- **Interface:** `extract_attributes_dict(soup: BeautifulSoup) -> Dict[str, List[str]]`
- **Dependencies:** `BeautifulSoup`, `json`
- **Size target:** ~20 lines

Parses `props.pageProps.advertDetails.attributes.attribute` array. Returns `{attr_name: [values]}`. Returns empty dict on any parse failure. Does not raise.

Used by `scrape_single_listing` to extract:

| Listing field | Attribute key |
|---|---|
| `building_condition` | `BUILDING_CONDITION` |
| `floor_surface` | `FLOOR_SURFACE` |
| `free_area_m2` | `FREE_AREA/FREE_AREA_AREA` (first value, parse float) |
| `unit_number` | `UNIT_NUMBER` |
| `parent_project_id` | `parentAdId` — read directly in `scrape_single_listing` via `ad_details.get('parentAdId')` from the same `__NEXT_DATA__` parse, not via `extract_attributes_dict` |

Text blocks passed to field extractors (HTML-stripped via `BeautifulSoup.get_text()`):
- `GENERAL_TEXT_ADVERT/Ausstattung` → `extract_kitchen_included`, `extract_window_type`
- `GENERAL_TEXT_ADVERT/Zusatzinformationen` → full page text supplement
- `GENERAL_TEXT_ADVERT/Preis - Detailinformation` → `extract_ruecklage_eur_month`, `extract_maklerprovision_pct`
- All three joined → `extract_sonderumlage_risk`, `extract_doppelmakler`

### Module: New field extractors in `field_extractors.py`
- **Responsibility:** Extract individual property facts from listing text via two-pass regex
- **Interface:** Each takes a pre-lowercased, HTML-stripped text string; returns typed Optional
- **Dependencies:** `re`
- **Size target:** ~120 lines total for all 6 extractors + `extract_document_urls`

#### `extract_kitchen_included(text) -> Optional[bool]`
- Positive: `einbauküche`, `küche\s+(inkl|vorhanden|inklusive)`, `küche\s+mit\s+geräten`, `möblierte\s+küche`
- Negative: `(ohne|keine)\s+küche`
- None if absent

#### `extract_window_type(text) -> Optional[str]`
Returns one of `"kastenfenster"`, `"kunststoff"`, `"holz-alu"`, `"isolierverglasung"` (first match wins in that priority order).
- `kastenfenster` → `r'kastenfenster'`
- `kunststoff` → `r'kunststofffenster|kunststoff.{0,10}fenster'`
- `holz-alu` → `r'holz-?alu.{0,10}fenster|fenster.{0,20}holz-?alu'`
- `isolierverglasung` → `r'isolierverglasung|3-scheiben|dreifach.{0,10}verglas'`
- Returns `None` if no match

#### `extract_ruecklage_eur_month(text) -> Optional[float]`
Input: stripped `preis_detail` text, e.g. `"monatliche reparaturrücklage (excl. mwst): 81,62 eur"`.
Pattern: `r'reparaturrücklage[^:]*:\s*([\d]{1,3}(?:[.,]\d{3})*[,.]\d{2}|\d+[,.]\d{1,2})'`
Parsing: strip `.` as thousands separator, replace `,` with `.`, cast to float. Handles `81,62` and `1.081,62`.
Returns `None` if absent.

#### `extract_sonderumlage_risk(text) -> Optional[bool]`
- Positive: `sonderumlage`
- Negative: `(keine|kein)\s+sonderumlage`
- Two-pass: negative first. Returns `None` if absent.

#### `extract_doppelmakler(text) -> Optional[bool]`
- Positive: `doppelmakler`
- No negative pattern (disclosing absence is not standard)
- Returns `True` if present, `None` otherwise

#### `extract_maklerprovision_pct(text) -> Optional[float]`
Pattern: `r'(\d+(?:[,.]\d+)?)\s*%\s*(kundenprovision|maklerprovision|provision|käuferprovision)'`
Returns float (e.g. `3.0`). Returns `None` if absent.

#### `extract_document_urls(soup) -> Dict[str, str]`
- **Responsibility:** Extract PDF document links from listing page
- **Interface:** `extract_document_urls(soup: BeautifulSoup) -> Dict[str, str]`
- Selector: `a[data-testid^="documents-item-anchor"]`
- Normalises link text to lowercase ASCII key: `{"expose": url, "preisliste": url, "planmappe": url, "lagereport": url}`
- Returns empty dict if section absent

### Module: `listing.py` (12 new fields)
- **Responsibility:** Data model for a single property listing
- **Interface:** Dataclass, append-only
- **Dependencies:** none
- **Size target:** 12 new `Optional` field lines

```python
building_condition:    Optional[str]        = None  # e.g. "Erstbezug"
floor_surface:         Optional[str]        = None  # e.g. "Parkettboden"
free_area_m2:          Optional[float]      = None  # loggia/balcony/terrace area
unit_number:           Optional[str]        = None  # e.g. "12"
ruecklage_eur_month:   Optional[float]      = None  # monthly repair reserve
kitchen_included:      Optional[bool]       = None
window_type:           Optional[str]        = None  # "kastenfenster"|"kunststoff"|"holz-alu"|"isolierverglasung"
sonderumlage_risk:     Optional[bool]       = None
doppelmakler:          Optional[bool]       = None
maklerprovision_pct:   Optional[float]      = None  # e.g. 3.0
document_urls:         Optional[Dict[str, str]] = None  # keys: expose|preisliste|planmappe|lagereport
parent_project_id:     Optional[int]        = None  # willhaben ad ID of parent project
```

### Module: Multi-scraper wiring
- **Responsibility:** Wire new boolean text extractors into immo_kurier and derstandard
- **Interface:** Adds 6 lines per scraper to the existing field-extraction block
- **Dependencies:** `field_extractors` (existing import)
- **Size target:** ~12 lines total across 2 files

New extractors to wire on `_full_text` in both scrapers: `extract_kitchen_included`, `extract_window_type`, `extract_sonderumlage_risk`, `extract_doppelmakler`. These use full page text in immo_kurier/derstandard (coarser than willhaben's targeted attribute text, but acceptable — false positive rate is low for these patterns).

Also fix missing wiring from the bank_loan_ready session: add `extract_parifizierung_complete` and `extract_roof_renovated` to both immo_kurier and derstandard (currently only lift + facade are wired).

### Module: Tests
- **Responsibility:** Verify extractor correctness with synthetic inputs
- **Interface:** `unittest.TestCase` subclasses, 4 cases each
- **Dependencies:** `field_extractors`, `willhaben_scraper`
- **Size target:** ~160 lines across both test files

**`test_field_extractors.py` additions:**
- `TestExtractKitchenIncluded` — 4 cases
- `TestExtractWindowType` — 5 cases (one per type + absent)
- `TestExtractRuecklageEurMonth` — 3 cases (comma decimal, dot decimal, absent)
- `TestExtractSonderumlageRisk` — 4 cases (positive, negative, variant, absent)
- `TestExtractDoppelmakler` — 3 cases (present, absent, context with percentage)
- `TestExtractMaklerprovisionPct` — 4 cases (integer %, decimal %, variant phrasing, absent)

**`test_willhaben_integration.py` additions:**
- `test_is_project_url` — neubauprojekt URL → True; eigentumswohnung → False; mietwohnung → False
- `test_extract_attributes_dict` — mock `__NEXT_DATA__` HTML with known attributes → verify flat dict keys/values
- `test_extract_document_urls` — mock HTML with `data-testid="documents-item-anchor-0..3"` → verify `{expose: url, preisliste: url, ...}`

---

## Data Flow

```
scrape_search_agent_page(alert_url)
  ├── extract_listing_urls(soup) → [url1, url2, ...]
  │
  ├── for each url:
  │     is_project_url(url)?
  │     ├── YES → expand_project_to_units(url) → [unit_url1, unit_url2, ...]
  │     └── NO  → [url]
  │
  └── for each unit_url:
        listing_exists? → skip
        scrape_single_listing(unit_url)
          ├── extract_from_json_data(soup)        [untouched]
          ├── extract_attributes_dict(soup)        [NEW]
          │     ├── building_condition, floor_surface, free_area_m2, unit_number
          │     ├── parent_project_id
          │     └── text blocks → field extractors
          ├── extract_document_urls(soup)          [NEW]
          └── existing extractors ...             [untouched]
```

---

## Out of Scope (Phase 2)

- Scoring weights for new fields in `buyer_profiles.py`
- `doppelmakler` penalty modifier in `scoring.py`
- PDF parsing (Preisliste, Exposé, Planmappe, Lagereport)
- ImmoKurier / DerStandard neubauprojekt equivalent (different URL structure, different sites)
