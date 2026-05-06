# Prime New Build Scraper Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `street_view`, `orientation`, and `floor_level` extraction to all three scrapers (Willhaben, ImmoKurier, DerStandard) and wire into `scrape_single_listing()`.

**Architecture:** Three independent extraction methods per scraper, following existing scraper patterns. Each method parses HTML soup and returns a typed value. Values are wired into the Listing object during `scrape_single_listing()`.

**Tech Stack:** Python 3, BeautifulSoup, regex

---

## File Map

| File | Responsibility |
|------|----------------|
| `Project/Application/scraping/willhaben_scraper.py` | Add 3 extraction methods, wire into `scrape_single_listing` |
| `Project/Application/scraping/immo_kurier_scraper.py` | Same |
| `Project/Application/scraping/derstandard_scraper.py` | Same |
| `Project/Domain/listing.py` | Already has `street_view`, `orientation`, `floor_level` fields |
| `Project/Application/scoring.py` | Already has normalization ranges for new fields |

---

## Extraction Logic Reference

### `extract_street_view(soup)` → `int`
- Address contains "Straße" but NOT "Hof" → `1` (main street)
- Address contains "Hof" or "Ruhelage" → `0` (quiet/inner court)
- Look in text/address elements for patterns: `Straße`, `gasse`, `platz`, `weg`, `allee`, `ring`

### `extract_orientation(soup)` → `int`
Ordinal scale from page text (keywords: Süd, Nord, Ost, West):
- N/NNE/NNW = `0`
- NE/NW = `30`
- E/W = `50`
- SE/SW = `70`
- S = `100`

Search in text for: `Süd`, `Nord`, `Ost`, `West`, `Südosten`, `Südwesten`, `Nordosten`, `Nordwesten`

### `extract_floor_level(soup)` → `int`
Convert floor string to integer:
- "Erdgeschoss" / "Hochparterre" → `0`
- "Dachgeschoss" → `4` (top floor estimate)
- "1. Stock" / "1. Etage" → `1`
- "2. Stock" → `2`, etc.
- "3rd floor" → `3`

---

## Task 1: Willhaben Scraper

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py:311-406`

- [ ] **Step 1: Add `extract_street_view` method**

Add after `extract_available_from()` (~line 1371):

```python
def extract_street_view(self, soup: BeautifulSoup) -> Optional[int]:
    """Extract street view: 1 = main street, 0 = quiet/inner court"""
    try:
        all_text = soup.get_text()
        address_text = ''
        # Try address selectors
        address_selectors = ['[data-testid="object-location-address"]', '.address-line', '.location-address']
        for selector in address_selectors:
            elem = soup.select_one(selector)
            if elem:
                address_text = elem.get_text()
                break
        if not address_text:
            address_text = all_text

        # Main street indicators: Straße, gasse, platz, weg, allee, ring
        # Quiet/inner court: Hof, Ruhelage
        main_street_patterns = [
            r'Straße', r'gasse', r'platz', r'weg', r'allee', r'ring'
        ]
        quiet_patterns = [
            r'Hof', r'Ruhelage', r'innenliegend'
        ]

        has_main_street = any(re.search(p, address_text, re.IGNORECASE) for p in main_street_patterns)
        has_quiet = any(re.search(p, address_text, re.IGNORECASE) for p in quiet_patterns)

        if has_quiet:
            return 0
        if has_main_street:
            return 1
        return None  # Unknown
    except Exception as e:
        return None
```

- [ ] **Step 2: Add `extract_orientation` method**

Add after `extract_street_view()`:

```python
def extract_orientation(self, soup: BeautifulSoup) -> Optional[int]:
    """Extract orientation as ordinal: N=0, NE/NW=30, E/W=50, SE/SW=70, S=100"""
    try:
        all_text = soup.get_text()

        orientation_patterns = [
            (r'Südosten|SO| southeast', 70),
            (r'Südwesten|SW|southwest', 70),
            (r'Nordosten|NO|northeast', 30),
            (r'Nordwesten|NW|northwest', 30),
            (r'\bSüd\b|\bS\b.*\bseite\b|south', 100),
            (r'\bNord\b|\bN\b.*\bseite\b|north', 0),
            (r'\bOst\b|\bO\b.*\bseite\b|east', 50),
            (r'\bWest\b|\bW\b.*\bseite\b|west', 50),
        ]

        for pattern, score in orientation_patterns:
            if re.search(pattern, all_text, re.IGNORECASE):
                return score

        return None
    except Exception as e:
        return None
```

- [ ] **Step 3: Add `extract_floor_level` method**

Add after `extract_orientation()`:

```python
def extract_floor_level(self, soup: BeautifulSoup) -> Optional[int]:
    """Extract floor level as integer: 0=ground, 1+=floors"""
    try:
        all_text = soup.get_text()

        floor_patterns = [
            (r'hochparterre', 0),
            (r'erdgeschoss|ground\s*floor', 0),
            (r'dachgeschoss|attic', 4),
            (r'(\d+)\.\s*[Ss]tock|(\d+)\.\s*[Ee]tage|(\d+)\s*[Ss]tock', None),
        ]

        for pattern, level in floor_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                if level is not None:
                    return level
                # Extract numeric floor
                for group in match.groups():
                    if group:
                        return int(group)
        return None
    except Exception as e:
        return None
```

- [ ] **Step 4: Wire into `scrape_single_listing`**

In `scrape_single_listing()` around line 311, after the existing field extractions, add:

```python
# New fields
listing.street_view = self.extract_street_view(soup)
listing.orientation = self.extract_orientation(soup)
listing.floor_level = self.extract_floor_level(soup)
```

Place after line ~358 (after `get_walking_times` block) and before `monatsrate` extraction.

- [ ] **Step 5: Verify no existing `street_view`/`orientation`/`floor_level` in Listing construction**

Check around line 324-348 where Listing object is created. The new fields should be set as attributes after construction (not in constructor), so no change needed to constructor call.

- [ ] **Step 6: Commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(willhaben): add street_view, orientation, floor_level extraction"
```

---

## Task 2: ImmoKurier Scraper

**Files:**
- Modify: `Project/Application/scraping/immo_kurier_scraper.py`

- [ ] **Step 1: Add three extraction methods**

Add after `extract_available_from()` (~line 990) — same methods as Willhaben (copy from Task 1 Steps 1-3). Methods are identical; only class name changes (`self.extract_street_view` → same code).

- [ ] **Step 2: Wire into `scrape_single_listing`**

In `scrape_single_listing()` around line 210, after the `get_walking_times` block (~line 255) and before `betriebskosten` handling, add:

```python
# New fields
listing.street_view = self.extract_street_view(soup)
listing.orientation = self.extract_orientation(soup)
listing.floor_level = self.extract_floor_level(soup)
```

- [ ] **Step 3: Commit**

```bash
git add Project/Application/scraping/immo_kurier_scraper.py
git commit -m "feat(immo_kurier): add street_view, orientation, floor_level extraction"
```

---

## Task 3: DerStandard Scraper

**Files:**
- Modify: `Project/Application/scraping/derstandard_scraper.py`

- [ ] **Step 1: Add three extraction methods**

Add after `extract_available_from()` method (around line 1047 in the capped output). Same methods as Willhaben.

- [ ] **Step 2: Wire into `scrape_single_listing`**

In `scrape_single_listing()` after the property data extraction block (~line 630-665 in JSON extraction area, or in the HTML fallback `extract_from_html_selectors`). The Listing is constructed at line 569 with all fields, then populated via `property_data` dict. Add after the existing field population:

```python
# New fields
listing.street_view = self.extract_street_view(soup)
listing.orientation = self.extract_orientation(soup)
listing.floor_level = self.extract_floor_level(soup)
```

Place after line 665 (after `listing.total_monthly_cost = total_monthly`).

- [ ] **Step 3: Commit**

```bash
git add Project/Application/scraping/derstandard_scraper.py
git commit -m "feat(derstandard): add street_view, orientation, floor_level extraction"
```

---

## Validation

- [ ] **Step: Run buyer_profiles module to verify profile**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project
python -c "from Application.buyer_profiles import print_profile_summary; print_profile_summary('prime_new_build')"
```

Expected: Shows 9 criteria with weights summing to 1.00

- [ ] **Step: Run scoring module to verify normalization**

```bash
python -c "
from Application.scoring import NORMALIZATION_RANGES
print('street_view:', NORMALIZATION_RANGES.get('street_view'))
print('orientation:', NORMALIZATION_RANGES.get('orientation'))
"
```

Expected: Both ranges present with correct min/max/direction

---

## Self-Review Checklist

1. **Spec coverage:** All 3 scrapers get all 3 extraction methods. All wired into `scrape_single_listing`. ✅
2. **Placeholder scan:** No TBD/TODO. All methods have full implementation. ✅
3. **Type consistency:** `street_view` → `int` (0/1), `orientation` → `int` (0-100), `floor_level` → `int`. All match Listing dataclass types. ✅
4. **No duplicate logic:** Each scraper gets identical extraction methods (follows existing pattern of duplicating across scrapers rather than sharing in a base class). ✅
5. **Orientation ordinal scale matches profile:** N=0, NE/NW=30, E/W=50, SE/SW=70, S=100 — matches `prime_new_build` design. ✅
