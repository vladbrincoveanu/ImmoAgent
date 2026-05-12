# Neubauprojekt Expansion + Rich HTML Field Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand willhaben neubauprojekt project-page URLs into individual unit listings, and extract 12 new structured fields from `__NEXT_DATA__` attributes covering Rücklage, kitchen, windows, Doppelmakler, document URLs, and building condition.

**Architecture:** `scrape_search_agent_page` detects project URLs, expands them via `expand_project_to_units`, and processes each unit individually. `scrape_single_listing` is extended with `extract_attributes_dict` (parses `__NEXT_DATA__` attribute array) and 6 new text extractors in `field_extractors.py`. Boolean extractors are also wired into all three scrapers.

**Tech Stack:** Python 3, `re`, `BeautifulSoup`, `requests` (all already in use)

**Spec:** `docs/superpowers/specs/2026-05-12-neubauprojekt-expansion-rich-extraction-design.md`

---

## File Map

| File | Action | What changes |
|---|---|---|
| `Project/Domain/listing.py` | Modify | Add 12 new Optional fields |
| `Project/Application/scraping/field_extractors.py` | Modify | Add 6 extractors + `extract_document_urls` |
| `Project/Application/scraping/willhaben_scraper.py` | Modify | Add `is_project_url`, `expand_project_to_units`, `extract_attributes_dict`; wire new fields in `scrape_single_listing`; expand logic in `scrape_search_agent_page` |
| `Project/Application/scraping/immo_kurier_scraper.py` | Modify | Wire 4 new + 2 previously missing boolean extractors |
| `Project/Application/scraping/derstandard_scraper.py` | Modify | Wire 4 new + 2 previously missing boolean extractors |
| `Tests/test_field_extractors.py` | Modify | Add 6 new TestCase classes |
| `Tests/test_willhaben_integration.py` | Modify | Add 3 new test functions |

---

## Task 1: Add 12 new fields to Listing dataclass

**Files:**
- Modify: `Project/Domain/listing.py:59` (append after last field `roof_renovated`)

- [ ] **Step 1: Add fields to listing.py**

Open `Project/Domain/listing.py`. After line 58 (`roof_renovated: Optional[bool] = None`), append:

```python
    building_condition:    Optional[str]        = None
    floor_surface:         Optional[str]        = None
    free_area_m2:          Optional[float]      = None
    unit_number:           Optional[str]        = None
    ruecklage_eur_month:   Optional[float]      = None
    kitchen_included:      Optional[bool]       = None
    window_type:           Optional[str]        = None
    sonderumlage_risk:     Optional[bool]       = None
    doppelmakler:          Optional[bool]       = None
    maklerprovision_pct:   Optional[float]      = None
    document_urls:         Optional[Dict[str, str]] = None
    parent_project_id:     Optional[int]        = None
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Tests
python run_tests.py 2>&1 | tail -5
```

Expected: no new failures. If `test_field_extractors.py` fails with import errors for functions not yet defined, that's expected — continue.

- [ ] **Step 3: Commit**

```bash
git add Project/Domain/listing.py
git commit -m "feat(listing): add 12 new fields for neubauprojekt expansion and rich HTML extraction"
```

---

## Task 2: Write + implement `extract_kitchen_included` and `extract_window_type`

**Files:**
- Modify: `Tests/test_field_extractors.py` (add 2 test classes at end of file)
- Modify: `Project/Application/scraping/field_extractors.py` (add 2 functions at end of file)

- [ ] **Step 1: Add failing tests to `test_field_extractors.py`**

Append to `Tests/test_field_extractors.py`:

```python
class TestExtractKitchenIncluded(unittest.TestCase):
    def test_positive_einbaukueche(self):
        self.assertTrue(extract_kitchen_included("wohnung mit einbauküche und parkett"))

    def test_positive_moeblierte_kueche(self):
        self.assertTrue(extract_kitchen_included("möblierte küche inklusive aller geräte"))

    def test_negative_ohne_kueche(self):
        self.assertFalse(extract_kitchen_included("ohne küche, selbst einzurichten"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_kitchen_included("schöne 3-zimmer-wohnung mit parkett"))


class TestExtractWindowType(unittest.TestCase):
    def test_kastenfenster(self):
        self.assertEqual(extract_window_type("originale kastenfenster aus dem baujahr"), "kastenfenster")

    def test_kunststoff(self):
        self.assertEqual(extract_window_type("neue kunststofffenster eingebaut"), "kunststoff")

    def test_holz_alu(self):
        self.assertEqual(extract_window_type("holz-alu-fenster dreifach verglast"), "holz-alu")

    def test_isolierverglasung(self):
        self.assertEqual(extract_window_type("3-scheiben-isolierverglasung"), "isolierverglasung")

    def test_absent_returns_none(self):
        self.assertIsNone(extract_window_type("schöne 3-zimmer-wohnung mit parkett"))
```

Also update the import at the top of `test_field_extractors.py` to include the new functions:

```python
from Application.scraping.field_extractors import (
    extract_lift_present,
    extract_facade_renovated,
    extract_parifizierung_complete,
    extract_roof_renovated,
    extract_kitchen_included,
    extract_window_type,
)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractKitchenIncluded test_field_extractors.py::TestExtractWindowType -v
```

Expected: `ImportError: cannot import name 'extract_kitchen_included'`

- [ ] **Step 3: Implement in `field_extractors.py`**

Append to `Project/Application/scraping/field_extractors.py`:

```python

def extract_kitchen_included(text: str) -> Optional[bool]:
    """True if furnished kitchen mentioned, False if explicitly absent, None if not mentioned."""
    negative = [r'(ohne|keine)\s+küche']
    positive = [
        r'einbauküche',
        r'küche\s+(inkl|vorhanden|inklusive)',
        r'küche\s+mit\s+geräten',
        r'möblierte\s+küche',
    ]
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_window_type(text: str) -> Optional[str]:
    """Returns window type: 'kastenfenster'|'kunststoff'|'holz-alu'|'isolierverglasung'|None.
    Priority order: kastenfenster > kunststoff > holz-alu > isolierverglasung."""
    checks = [
        ('kastenfenster', [r'kastenfenster']),
        ('kunststoff', [r'kunststofffenster', r'kunststoff.{0,10}fenster']),
        ('holz-alu', [r'holz-?alu.{0,10}fenster', r'fenster.{0,20}holz-?alu']),
        ('isolierverglasung', [r'isolierverglasung', r'3-scheiben', r'dreifach.{0,10}verglas']),
    ]
    for label, patterns in checks:
        if _any_match(text, patterns):
            return label
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractKitchenIncluded test_field_extractors.py::TestExtractWindowType -v
```

Expected: 9 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Tests/test_field_extractors.py Project/Application/scraping/field_extractors.py
git commit -m "feat(extractors): add extract_kitchen_included and extract_window_type"
```

---

## Task 3: Write + implement `extract_ruecklage_eur_month` and `extract_maklerprovision_pct`

**Files:**
- Modify: `Tests/test_field_extractors.py` (add 2 test classes)
- Modify: `Project/Application/scraping/field_extractors.py` (add 2 functions)

- [ ] **Step 1: Add failing tests**

Append to `Tests/test_field_extractors.py`:

```python
class TestExtractRuecklageEurMonth(unittest.TestCase):
    def test_comma_decimal(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("monatliche reparaturrücklage (excl. mwst): 81,62 eur"),
            81.62, places=2
        )

    def test_dot_decimal(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("reparaturrücklage: 81.62 eur"),
            81.62, places=2
        )

    def test_thousands_separator(self):
        self.assertAlmostEqual(
            extract_ruecklage_eur_month("monatliche reparaturrücklage: 1.081,62 eur"),
            1081.62, places=2
        )

    def test_absent_returns_none(self):
        self.assertIsNone(extract_ruecklage_eur_month("monatliche betriebskosten: 281,75 eur"))


class TestExtractMaklerprovisionPct(unittest.TestCase):
    def test_integer_percent(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("3% kundenprovision zzgl. mwst"),
            3.0, places=1
        )

    def test_decimal_percent_comma(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("3,6% maklerprovision"),
            3.6, places=1
        )

    def test_provision_variant(self):
        self.assertAlmostEqual(
            extract_maklerprovision_pct("käuferprovision: 2% zzgl. mwst"),
            2.0, places=1
        )

    def test_absent_returns_none(self):
        self.assertIsNone(extract_maklerprovision_pct("keine provision für käufer"))
```

Also extend the import at the top of `test_field_extractors.py`:

```python
from Application.scraping.field_extractors import (
    extract_lift_present,
    extract_facade_renovated,
    extract_parifizierung_complete,
    extract_roof_renovated,
    extract_kitchen_included,
    extract_window_type,
    extract_ruecklage_eur_month,
    extract_maklerprovision_pct,
)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractRuecklageEurMonth test_field_extractors.py::TestExtractMaklerprovisionPct -v
```

Expected: `ImportError: cannot import name 'extract_ruecklage_eur_month'`

- [ ] **Step 3: Implement in `field_extractors.py`**

Append to `Project/Application/scraping/field_extractors.py`:

```python

def extract_ruecklage_eur_month(text: str) -> Optional[float]:
    """Extract monthly Reparaturrücklage in EUR from preis_detail text. Handles thousands separators."""
    m = re.search(
        r'reparaturrücklage[^:]*:\s*([\d]{1,3}(?:[.,]\d{3})*[,.]\d{2}|\d+[,.]\d{1,2})',
        text
    )
    if not m:
        return None
    raw = m.group(1)
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    return float(raw)


def extract_maklerprovision_pct(text: str) -> Optional[float]:
    """Extract broker commission percentage. Returns float e.g. 3.0 for '3% Kundenprovision'."""
    m = re.search(
        r'(\d+(?:[,.]\d+)?)\s*%\s*(kundenprovision|maklerprovision|provision|käuferprovision)',
        text
    )
    if not m:
        return None
    return float(m.group(1).replace(',', '.'))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractRuecklageEurMonth test_field_extractors.py::TestExtractMaklerprovisionPct -v
```

Expected: 8 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Tests/test_field_extractors.py Project/Application/scraping/field_extractors.py
git commit -m "feat(extractors): add extract_ruecklage_eur_month and extract_maklerprovision_pct"
```

---

## Task 4: Write + implement `extract_sonderumlage_risk` and `extract_doppelmakler`

**Files:**
- Modify: `Tests/test_field_extractors.py` (add 2 test classes)
- Modify: `Project/Application/scraping/field_extractors.py` (add 2 functions)

- [ ] **Step 1: Add failing tests**

Append to `Tests/test_field_extractors.py`:

```python
class TestExtractSonderumlageRisk(unittest.TestCase):
    def test_positive(self):
        self.assertTrue(extract_sonderumlage_risk("eine sonderumlage für fassadensanierung ist geplant"))

    def test_negative_keine(self):
        self.assertFalse(extract_sonderumlage_risk("keine sonderumlage bekannt"))

    def test_negative_kein(self):
        self.assertFalse(extract_sonderumlage_risk("kein sonderumlage erwartet"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_sonderumlage_risk("schöne wohnung mit parkett und balkon"))


class TestExtractDoppelmakler(unittest.TestCase):
    def test_present(self):
        self.assertTrue(extract_doppelmakler("der vermittler ist als doppelmakler tätig"))

    def test_with_provision_context(self):
        self.assertTrue(extract_doppelmakler("doppelmakler tätig. 3% kundenprovision zzgl. mwst"))

    def test_absent_returns_none(self):
        self.assertIsNone(extract_doppelmakler("3% kundenprovision, keine weiteren kosten"))
```

Extend the import:

```python
from Application.scraping.field_extractors import (
    extract_lift_present,
    extract_facade_renovated,
    extract_parifizierung_complete,
    extract_roof_renovated,
    extract_kitchen_included,
    extract_window_type,
    extract_ruecklage_eur_month,
    extract_maklerprovision_pct,
    extract_sonderumlage_risk,
    extract_doppelmakler,
)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractSonderumlageRisk test_field_extractors.py::TestExtractDoppelmakler -v
```

Expected: `ImportError: cannot import name 'extract_sonderumlage_risk'`

- [ ] **Step 3: Implement in `field_extractors.py`**

Append to `Project/Application/scraping/field_extractors.py`:

```python

def extract_sonderumlage_risk(text: str) -> Optional[bool]:
    """True if Sonderumlage mentioned, False if explicitly absent, None if not mentioned."""
    negative = [r'(keine|kein)\s+sonderumlage']
    positive = [r'sonderumlage']
    if _any_match(text, negative):
        return False
    if _any_match(text, positive):
        return True
    return None


def extract_doppelmakler(text: str) -> Optional[bool]:
    """True if Doppelmakler disclosed, None otherwise (absence not explicitly stated)."""
    if re.search(r'doppelmakler', text):
        return True
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractSonderumlageRisk test_field_extractors.py::TestExtractDoppelmakler -v
```

Expected: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Tests/test_field_extractors.py Project/Application/scraping/field_extractors.py
git commit -m "feat(extractors): add extract_sonderumlage_risk and extract_doppelmakler"
```

---

## Task 5: Write + implement `extract_document_urls`

**Files:**
- Modify: `Project/Application/scraping/field_extractors.py` (add import + function)
- Modify: `Tests/test_field_extractors.py` (add test class)

- [ ] **Step 1: Add failing test**

Append to `Tests/test_field_extractors.py`:

```python
class TestExtractDocumentUrls(unittest.TestCase):
    def _make_soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'html.parser')

    def test_all_four_documents(self):
        soup = self._make_soup("""
        <html><body>
        <a data-testid="documents-item-anchor-0" href="https://storage.justimmo.at/file/abc.pdf">Exposé</a>
        <a data-testid="documents-item-anchor-1" href="https://storage.justimmo.at/file/def.pdf">Preisliste</a>
        <a data-testid="documents-item-anchor-2" href="https://storage.justimmo.at/file/ghi.pdf">Planmappe</a>
        <a data-testid="documents-item-anchor-3" href="https://storage.justimmo.at/file/jkl.pdf">Lagereport</a>
        </body></html>
        """)
        docs = extract_document_urls(soup)
        self.assertEqual(docs.get('expose'), 'https://storage.justimmo.at/file/abc.pdf')
        self.assertEqual(docs.get('preisliste'), 'https://storage.justimmo.at/file/def.pdf')
        self.assertEqual(docs.get('planmappe'), 'https://storage.justimmo.at/file/ghi.pdf')
        self.assertEqual(docs.get('lagereport'), 'https://storage.justimmo.at/file/jkl.pdf')

    def test_empty_when_no_documents(self):
        soup = self._make_soup("<html><body><p>no documents here</p></body></html>")
        docs = extract_document_urls(soup)
        self.assertEqual(docs, {})

    def test_partial_documents(self):
        soup = self._make_soup("""
        <html><body>
        <a data-testid="documents-item-anchor-0" href="https://storage.justimmo.at/file/abc.pdf">Exposé</a>
        </body></html>
        """)
        docs = extract_document_urls(soup)
        self.assertEqual(docs.get('expose'), 'https://storage.justimmo.at/file/abc.pdf')
        self.assertIsNone(docs.get('preisliste'))
```

Also add `extract_document_urls` to the import at the top of `test_field_extractors.py`:

```python
from Application.scraping.field_extractors import (
    extract_lift_present,
    extract_facade_renovated,
    extract_parifizierung_complete,
    extract_roof_renovated,
    extract_kitchen_included,
    extract_window_type,
    extract_ruecklage_eur_month,
    extract_maklerprovision_pct,
    extract_sonderumlage_risk,
    extract_doppelmakler,
    extract_document_urls,
)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractDocumentUrls -v
```

Expected: `ImportError: cannot import name 'extract_document_urls'`

- [ ] **Step 3: Implement in `field_extractors.py`**

Add `BeautifulSoup` import at the top of `field_extractors.py` (after existing imports):

```python
from typing import Dict, Optional
from bs4 import BeautifulSoup
```

Note: the existing file has `from typing import Optional`. Change it to `from typing import Dict, Optional`.

Then append the function:

```python

def extract_document_urls(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract PDF document links from listing page documents box.
    Returns dict with keys: expose|preisliste|planmappe|lagereport."""
    label_map = {
        'exposé': 'expose',
        'expose': 'expose',
        'preisliste': 'preisliste',
        'planmappe': 'planmappe',
        'lagereport': 'lagereport',
    }
    result = {}
    for anchor in soup.select('a[data-testid^="documents-item-anchor"]'):
        text = anchor.get_text(strip=True).lower()
        href = anchor.get('href', '')
        if text in label_map and href:
            result[label_map[text]] = href
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Tests && python -m pytest test_field_extractors.py::TestExtractDocumentUrls -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Run all extractor tests to confirm nothing broken**

```bash
cd Tests && python -m pytest test_field_extractors.py -v
```

Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add Tests/test_field_extractors.py Project/Application/scraping/field_extractors.py
git commit -m "feat(extractors): add extract_document_urls with data-testid selector"
```

---

## Task 6: Write + implement `is_project_url` and `extract_attributes_dict`

**Files:**
- Modify: `Tests/test_willhaben_integration.py` (add 2 test functions + BeautifulSoup import)
- Modify: `Project/Application/scraping/willhaben_scraper.py` (add 2 methods)

- [ ] **Step 1: Add failing tests to `test_willhaben_integration.py`**

Add `from bs4 import BeautifulSoup` to the imports at the top of `Tests/test_willhaben_integration.py`.

Then append:

```python
def test_is_project_url():
    scraper = WillhabenScraper()
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/neubauprojekt/wien/wien-1220/am-bienefeld-1475846939/"
    ) is True
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220/some-listing-1334111902/"
    ) is False
    assert scraper.is_project_url(
        "https://www.willhaben.at/iad/immobilien/d/mietwohnung/wien/wien-1220/some-listing-1234567890/"
    ) is False


def test_extract_attributes_dict():
    scraper = WillhabenScraper()
    mock_html = """<html><head></head><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"advertDetails":{"attributes":{"attribute":[
        {"name":"BUILDING_CONDITION","values":["Erstbezug"]},
        {"name":"FLOOR_SURFACE","values":["Parkettboden"]},
        {"name":"UNIT_NUMBER","values":["12"]},
        {"name":"FREE_AREA/FREE_AREA_AREA","values":["10,96"]}
    ]}}}}}
    </script>
    </body></html>"""
    soup = BeautifulSoup(mock_html, 'html.parser')
    attrs = scraper.extract_attributes_dict(soup)
    assert attrs.get('BUILDING_CONDITION') == ['Erstbezug']
    assert attrs.get('FLOOR_SURFACE') == ['Parkettboden']
    assert attrs.get('UNIT_NUMBER') == ['12']
    assert attrs.get('FREE_AREA/FREE_AREA_AREA') == ['10,96']
    assert attrs.get('NONEXISTENT') is None


def test_extract_attributes_dict_empty_on_bad_html():
    scraper = WillhabenScraper()
    soup = BeautifulSoup("<html><body>no next data here</body></html>", 'html.parser')
    attrs = scraper.extract_attributes_dict(soup)
    assert attrs == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd Tests && python -m pytest test_willhaben_integration.py::test_is_project_url test_willhaben_integration.py::test_extract_attributes_dict -v
```

Expected: `AttributeError: 'WillhabenScraper' object has no attribute 'is_project_url'`

- [ ] **Step 3: Add methods to `willhaben_scraper.py`**

Find the method `extract_special_features` (line 187) in `willhaben_scraper.py`. Add the two new methods just before it (after `extract_listing_urls`):

```python
    def is_project_url(self, url: str) -> bool:
        """Return True if the URL is a Neubauprojekt project page (not an individual unit)."""
        return '/d/neubauprojekt/' in url

    def expand_project_to_units(self, url: str) -> List[str]:
        """Fetch a Neubauprojekt page and return individual unit listing URLs."""
        time.sleep(1.0)
        response = self._fetch_with_retry(url)
        if not response:
            logging.warning(f"⚠️  Failed to expand project page: {url}")
            return []
        soup = BeautifulSoup(response.content, 'html.parser')
        all_urls = self.extract_listing_urls(soup)
        return [u for u in all_urls if '/d/neubauprojekt/' not in u]

    def extract_attributes_dict(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Parse __NEXT_DATA__ attributes array into a flat {name: [values]} dict."""
        try:
            script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
            if not script_tag or not script_tag.string:
                return {}
            json_data = json.loads(str(script_tag.string))
            attrs = (json_data.get('props', {})
                              .get('pageProps', {})
                              .get('advertDetails', {})
                              .get('attributes', {})
                              .get('attribute', []))
            return {a['name']: a.get('values', []) for a in attrs if 'name' in a}
        except Exception:
            return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Tests && python -m pytest test_willhaben_integration.py::test_is_project_url test_willhaben_integration.py::test_extract_attributes_dict test_willhaben_integration.py::test_extract_attributes_dict_empty_on_bad_html -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add Tests/test_willhaben_integration.py Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(willhaben): add is_project_url, expand_project_to_units, extract_attributes_dict"
```

---

## Task 7: Wire new field extractors into `scrape_single_listing`

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py`

This task has no new tests — the extractor unit tests already cover correctness. Integration is verified by running existing tests and a manual smoke test.

- [ ] **Step 1: Update the import at top of `willhaben_scraper.py`**

Find the existing import block for field_extractors (search for `from Application.scraping.field_extractors import`). Extend it to include all new extractors:

```python
from Application.scraping.field_extractors import (
    extract_lift_present,
    extract_facade_renovated,
    extract_parifizierung_complete,
    extract_roof_renovated,
    extract_kitchen_included,
    extract_window_type,
    extract_ruecklage_eur_month,
    extract_sonderumlage_risk,
    extract_doppelmakler,
    extract_maklerprovision_pct,
    extract_document_urls,
)
```

- [ ] **Step 2: Add new field extraction block in `scrape_single_listing`**

In `scrape_single_listing`, find the bank_loan_ready block (around line 371–375):

```python
            # New fields for bank_loan_ready profile
            _full_text = soup.get_text().lower()
            listing.lift_present = extract_lift_present(_full_text)
            listing.facade_renovated = extract_facade_renovated(_full_text)
            listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
            listing.roof_renovated = extract_roof_renovated(_full_text)
```

Immediately after `listing.roof_renovated = ...`, add:

```python
            # Rich attribute extraction from __NEXT_DATA__
            _attrs = self.extract_attributes_dict(soup)
            def _strip_html(val: str) -> str:
                from bs4 import BeautifulSoup as _BS
                return _BS(val, 'html.parser').get_text(' ', strip=True).lower() if val else ''

            _ausstattung = _strip_html((_attrs.get('GENERAL_TEXT_ADVERT/Ausstattung') or [''])[0])
            _preis_detail = _strip_html((_attrs.get('GENERAL_TEXT_ADVERT/Preis - Detailinformation') or [''])[0])
            _zusatz = _strip_html((_attrs.get('GENERAL_TEXT_ADVERT/Zusatzinformationen') or [''])[0])
            _combined = ' '.join([_ausstattung, _zusatz, _preis_detail])

            # Direct attribute fields
            _bc = (_attrs.get('BUILDING_CONDITION') or [None])[0]
            listing.building_condition = _bc
            _fs = (_attrs.get('FLOOR_SURFACE') or [None])[0]
            listing.floor_surface = _fs
            _unit = (_attrs.get('UNIT_NUMBER') or [None])[0]
            listing.unit_number = _unit
            _raw_area = (_attrs.get('FREE_AREA/FREE_AREA_AREA') or [None])[0]
            if _raw_area:
                try:
                    listing.free_area_m2 = float(str(_raw_area).replace(',', '.'))
                except (ValueError, TypeError):
                    pass

            # Text-mined fields from attribute blocks
            listing.kitchen_included = extract_kitchen_included(_ausstattung)
            listing.window_type = extract_window_type(_ausstattung)
            listing.ruecklage_eur_month = extract_ruecklage_eur_month(_preis_detail)
            listing.sonderumlage_risk = extract_sonderumlage_risk(_combined)
            listing.doppelmakler = extract_doppelmakler(_combined)
            listing.maklerprovision_pct = extract_maklerprovision_pct(_combined)

            # Document URLs (PDF links)
            _doc_urls = extract_document_urls(soup)
            listing.document_urls = _doc_urls if _doc_urls else None

            # parent_project_id from top-level advertDetails (not in attributes array)
            try:
                _script = soup.find('script', {'id': '__NEXT_DATA__'})
                if _script and _script.string:
                    _jd = json.loads(str(_script.string))
                    _ad = _jd.get('props', {}).get('pageProps', {}).get('advertDetails', {})
                    listing.parent_project_id = _ad.get('parentAdId')
            except Exception:
                pass
```

- [ ] **Step 3: Run existing willhaben tests**

```bash
cd Tests && python -m pytest test_willhaben_integration.py -v
```

Expected: all existing tests PASSED (no regressions)

- [ ] **Step 4: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(willhaben): wire 12 new fields into scrape_single_listing via extract_attributes_dict"
```

---

## Task 8: Expand neubauprojekt URLs in `scrape_search_agent_page`

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py` (lines ~1713–1720)

- [ ] **Step 1: Locate the inner scrape loop in `scrape_search_agent_page`**

In `willhaben_scraper.py`, find `scrape_search_agent_page` (line 1691). The listing URL loop starts around line 1713:

```python
                listing_urls = self.extract_listing_urls(soup)
                if not listing_urls:
                    print("No more listings found on this page.")
                    break

                for listing_url in listing_urls:
                    if self.mongo.listing_exists(listing_url):
```

- [ ] **Step 2: Add project expansion pre-pass**

Replace the section from `listing_urls = self.extract_listing_urls(soup)` through the start of the `for listing_url in listing_urls:` loop with:

```python
                listing_urls = self.extract_listing_urls(soup)
                if not listing_urls:
                    print("No more listings found on this page.")
                    break

                # Expand neubauprojekt project pages into individual unit URLs
                expanded_urls: List[str] = []
                for listing_url in listing_urls:
                    if self.is_project_url(listing_url):
                        unit_urls = self.expand_project_to_units(listing_url)
                        print(f"🏗️  Expanding project {listing_url} → {len(unit_urls)} units")
                        expanded_urls.extend(unit_urls)
                    else:
                        expanded_urls.append(listing_url)

                for listing_url in expanded_urls:
                    if self.mongo.listing_exists(listing_url):
```

The rest of the inner loop body (from `if self.mongo.listing_exists` onwards) stays completely unchanged.

- [ ] **Step 3: Run full test suite**

```bash
cd Tests && python run_tests.py 2>&1 | tail -10
```

Expected: no new failures

- [ ] **Step 4: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(willhaben): expand neubauprojekt project URLs into individual unit listings"
```

---

## Task 9: Wire new boolean extractors into `immo_kurier_scraper.py`

**Files:**
- Modify: `Project/Application/scraping/immo_kurier_scraper.py` (lines 15–16 import, lines 269–270 wiring)

- [ ] **Step 1: Extend the field_extractors import (lines 15–16)**

Find this block in `immo_kurier_scraper.py`:

```python
from Application.scraping.field_extractors import (
    extract_lift_present, extract_facade_renovated,
)
```

Replace with:

```python
from Application.scraping.field_extractors import (
    extract_lift_present, extract_facade_renovated,
    extract_parifizierung_complete, extract_roof_renovated,
    extract_kitchen_included, extract_window_type,
    extract_sonderumlage_risk, extract_doppelmakler,
)
```

- [ ] **Step 2: Add wiring after line 270**

Find this block in `immo_kurier_scraper.py` (around line 269):

```python
            listing.lift_present = extract_lift_present(_full_text)
            listing.facade_renovated = extract_facade_renovated(_full_text)
```

Add immediately after:

```python
            listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
            listing.roof_renovated = extract_roof_renovated(_full_text)
            listing.kitchen_included = extract_kitchen_included(_full_text)
            listing.window_type = extract_window_type(_full_text)
            listing.sonderumlage_risk = extract_sonderumlage_risk(_full_text)
            listing.doppelmakler = extract_doppelmakler(_full_text)
```

- [ ] **Step 3: Run tests**

```bash
cd Tests && python run_tests.py 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -5
```

Expected: no new failures

- [ ] **Step 4: Commit**

```bash
git add Project/Application/scraping/immo_kurier_scraper.py
git commit -m "feat(immo_kurier): wire 4 new + 2 missing boolean field extractors"
```

---

## Task 10: Wire new boolean extractors into `derstandard_scraper.py`

**Files:**
- Modify: `Project/Application/scraping/derstandard_scraper.py` (lines 23–24 import, lines 680–681 wiring)

- [ ] **Step 1: Extend the field_extractors import (lines 23–24)**

Find this block in `derstandard_scraper.py`:

```python
from Application.scraping.field_extractors import (
    extract_lift_present, extract_facade_renovated,
)
```

Replace with:

```python
from Application.scraping.field_extractors import (
    extract_lift_present, extract_facade_renovated,
    extract_parifizierung_complete, extract_roof_renovated,
    extract_kitchen_included, extract_window_type,
    extract_sonderumlage_risk, extract_doppelmakler,
)
```

- [ ] **Step 2: Add wiring after line 681**

Find this block in `derstandard_scraper.py` (around line 680):

```python
            listing.lift_present = extract_lift_present(_full_text)
            listing.facade_renovated = extract_facade_renovated(_full_text)
```

Add immediately after:

```python
            listing.parifizierung_complete = extract_parifizierung_complete(_full_text)
            listing.roof_renovated = extract_roof_renovated(_full_text)
            listing.kitchen_included = extract_kitchen_included(_full_text)
            listing.window_type = extract_window_type(_full_text)
            listing.sonderumlage_risk = extract_sonderumlage_risk(_full_text)
            listing.doppelmakler = extract_doppelmakler(_full_text)
```

- [ ] **Step 3: Run full test suite**

```bash
cd Tests && python run_tests.py 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -5
```

Expected: no new failures

- [ ] **Step 4: Commit**

```bash
git add Project/Application/scraping/derstandard_scraper.py
git commit -m "feat(derstandard): wire 4 new + 2 missing boolean field extractors"
```

---

## Task 11: Final verification

- [ ] **Step 1: Run the complete test suite**

```bash
cd Tests && python run_tests.py 2>&1 | tail -15
```

Expected: all tests PASS, no regressions in `test_field_extractors.py`, `test_buyer_profiles.py`, `test_score_calculation.py`

- [ ] **Step 2: Smoke test willhaben scraper on a single unit listing**

```bash
cd Project && python -c "
from Application.scraping.willhaben_scraper import WillhabenScraper
s = WillhabenScraper()
listing = s.scrape_single_listing('https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220-donaustadt/wohnen-mit-stil-geniessen-sie-modernes-design-und-erstklassige-annehmlichkeiten-1334111902/')
if listing:
    print('ruecklage_eur_month:', listing.ruecklage_eur_month)
    print('doppelmakler:', listing.doppelmakler)
    print('document_urls:', listing.document_urls)
    print('parent_project_id:', listing.parent_project_id)
    print('unit_number:', listing.unit_number)
    print('building_condition:', listing.building_condition)
else:
    print('ERROR: listing is None')
"
```

Expected output (approximate):
```
ruecklage_eur_month: 81.62
doppelmakler: True
document_urls: {'expose': 'https://storage...', 'preisliste': '...', ...}
parent_project_id: 1475846939
unit_number: 12
building_condition: Erstbezug
```

- [ ] **Step 3: Smoke test neubauprojekt expansion**

```bash
cd Project && python -c "
from Application.scraping.willhaben_scraper import WillhabenScraper
s = WillhabenScraper()
project_url = 'https://www.willhaben.at/iad/immobilien/d/neubauprojekt/wien/wien-1220-donaustadt/am-bienefeld-exklusives-wohnen-in-donaustadt-1475846939/'
print('is_project_url:', s.is_project_url(project_url))
units = s.expand_project_to_units(project_url)
print(f'Found {len(units)} unit URLs')
print('First 3:', units[:3])
assert len(units) > 0, 'No units found!'
assert all('/d/neubauprojekt/' not in u for u in units), 'Project URL leaked into units!'
print('OK')
"
```

Expected:
```
is_project_url: True
Found 28 unit URLs
First 3: ['https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/...', ...]
OK
```

- [ ] **Step 4: Final commit if any fixups needed, then summarise**

If smoke tests revealed any issues, fix them and commit. Otherwise the feature is complete.
