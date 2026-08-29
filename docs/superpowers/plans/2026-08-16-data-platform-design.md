# Data Platform Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Mongo data platform with cross-source dedup, relist-cycle tracking, private-seller classification, coordinate-precision-aware distance recompute, capture-coverage fixes, and district-level drift analytics.

**Architecture:** Five phases matching the spec's sub-projects. Phases 1-4 are fully specified TDD tasks; Phase 5 is a single research spike (data-shape/licensing verification), not a full implementation, per the design doc's flagged risk. Phases are ordered by dependency: Phase 1 (fingerprint/relist) and Phase 2 (seller/geo) are independent of each other; Phase 3 (capture coverage) is independent; Phase 4 (district_snapshots) has no hard dependency on 1-3 but is more useful once `seller_type` exists; Phase 5 depends on Phase 4's collection shape.

**Tech Stack:** Python 3.13, pytest, MongoDB (pymongo), existing `Domain.listing.Listing` dataclass, existing `Application/scraping/field_extractors.py` regex-marker pattern.

**Spec:** `docs/superpowers/specs/2026-08-16-data-platform-design.md`

---

## Phase 1: Cross-source dedup + relist-cycle tracking

### Task 1.1: Extend `content_fingerprint_xsrc`-style fingerprint to a general cross-source `unit_fingerprint`

**Files:**
- Modify: `Project/Application/helpers/listing_validator.py:96-107` (add new function after `compute_xsrc_fingerprint`)
- Modify: `Project/Domain/listing.py:91` (add new field after `first_seen_at`)
- Test: `Tests/test_unit_fingerprint.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_unit_fingerprint.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.helpers.listing_validator import compute_unit_fingerprint
from Domain.listing import Listing
from Domain.sources import Source
from Domain.location import Coordinates


def _listing(lat, lon, coord_source, area, rooms, bezirk, source=Source.WILLHABEN):
    return Listing(
        url="u", source=source, bezirk=bezirk, area_m2=area, rooms=rooms,
        coordinates=Coordinates(lat=lat, lon=lon) if lat is not None else None,
        coordinate_source=coord_source,
    )


def test_same_unit_exact_coords_two_sources_same_fingerprint():
    a = _listing(48.21091, 16.37372, "exact", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.21093, 16.37369, "landmark", 62.4, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) == compute_unit_fingerprint(b)


def test_both_landmark_precision_does_not_merge_on_coords():
    # Two different landmark-precision docs must NOT collapse just because
    # rounded coords/area/rooms happen to match - false-positive risk for
    # adjacent units in the same building.
    a = _listing(48.21091, 16.37372, "landmark", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.21093, 16.37369, "landmark", 62.4, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) is None


def test_different_coords_different_fingerprint():
    a = _listing(48.21091, 16.37372, "exact", 62.0, 3.0, "1010", Source.WILLHABEN)
    b = _listing(48.19500, 16.33000, "exact", 62.0, 3.0, "1010", Source.IMMO_KURIER)
    assert compute_unit_fingerprint(a) != compute_unit_fingerprint(b)


def test_no_coords_falls_back_to_bezirk_street_key():
    a = Listing(url="u1", source=Source.WILLHABEN, bezirk="1010",
                address="Musterstraße 5, 1010 Wien", area_m2=62.0, rooms=3.0,
                coordinate_source="none")
    b = Listing(url="u2", source=Source.DERSTANDARD, bezirk="1010",
                address="musterstrasse  5, 1010 wien", area_m2=62.0, rooms=3.0,
                coordinate_source="none")
    assert compute_unit_fingerprint(a) == compute_unit_fingerprint(b)
    assert compute_unit_fingerprint(a) is not None


def test_no_coords_and_no_address_returns_none():
    a = Listing(url="u1", source=Source.WILLHABEN, bezirk="1010",
                area_m2=62.0, rooms=3.0, coordinate_source="none")
    assert compute_unit_fingerprint(a) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_unit_fingerprint.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_unit_fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# Project/Application/helpers/listing_validator.py
# Add after compute_xsrc_fingerprint (line 107), before compute_content_fingerprint

def compute_unit_fingerprint(listing) -> "str | None":
    """Cross-source fingerprint for 'same physical unit', extending the co-op
    xsrc pattern to all verticals. Key = md5(coord_key|area|rooms|bezirk).

    Coord key uses round(lat,4)/round(lon,4) (~11m) - NOT round(...,3) (~111m,
    too coarse to distinguish adjacent units in the same building).

    Merge guard: only usable across sources when coordinate_source == 'exact'
    for at least one side. Two 'landmark'-precision docs must not collapse on
    coordinates alone (false-positive risk), so this returns None for
    landmark-only listings with no address fallback - callers should not treat
    None as "no unit", just "no safe cross-source key available".

    Falls back to bezirk+normalized-street when no exact-precision coords
    exist at all but an address string is present. Returns None when neither
    a safe coordinate key nor an address is available (weak key -> don't
    collapse, matches compute_xsrc_fingerprint's convention).
    """
    area = listing.area_m2
    rooms = listing.rooms
    bezirk = listing.bezirk
    if area is None or rooms is None or not bezirk:
        return None

    area_key = str(int(round(area)))
    rooms_key = str(rooms)

    coord_source = getattr(listing, "coordinate_source", None)
    coords = getattr(listing, "coordinates", None)
    if coord_source == "exact" and coords is not None:
        coord_key = f"{round(coords.lat, 4)}:{round(coords.lon, 4)}"
        raw = f"{coord_key}|{area_key}|{rooms_key}|{bezirk}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    address = getattr(listing, "address", None)
    if address:
        raw = f"{_norm(address)}|{area_key}|{rooms_key}|{bezirk}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    return None
```

Note: this function only produces a merge key when it's driven by an `exact`-precision coordinate OR a real address string — never by two `landmark`-precision coordinate pairs alone, per the merge guard in the spec. `test_both_landmark_precision_does_not_merge_on_coords` is expected to return `None` here since neither listing has an `address` set and `coord_source != 'exact'`.

Add the field to `Domain/listing.py` after line 91:

```python
    unit_fingerprint:        Optional[str]   = None   # cross-source dedup key; see compute_unit_fingerprint
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_unit_fingerprint.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```
git add Project/Application/helpers/listing_validator.py Project/Domain/listing.py Tests/test_unit_fingerprint.py
git commit -m "feat(dedup): add cross-source unit_fingerprint with coord-precision merge guard"
```

### Task 1.2: Write `unit_fingerprint` on every upsert without changing existing per-source dedup behavior

**Files:**
- Modify: `Project/Integration/mongodb_handler.py:326-407` (`upsert_listing_with_history`)
- Test: `Tests/test_scraper_mongodb.py` (extend) or new `Tests/test_upsert_unit_fingerprint.py`

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_upsert_unit_fingerprint.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def test_upsert_sets_unit_fingerprint_on_new_doc(monkeypatch):
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.collection = MagicMock()
    handler.collection.find_one.return_value = None

    listing = {
        "url": "https://example.com/1", "price_total": 300000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
        "coordinate_source": "none",
    }
    ok = handler.upsert_listing_with_history(listing)
    assert ok is True
    inserted = handler.collection.insert_one.call_args[0][0]
    assert "unit_fingerprint" in inserted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_upsert_unit_fingerprint.py -v`
Expected: FAIL — `unit_fingerprint` not in inserted dict (KeyError/AssertionError)

- [ ] **Step 3: Write minimal implementation**

In `Project/Integration/mongodb_handler.py`, `upsert_listing_with_history`, right after the existing fingerprint line (`listing['content_fingerprint'] = fingerprint`, around line 343):

```python
        from Application.helpers.listing_validator import compute_unit_fingerprint as _compute_unit_fp
        from Domain.listing import Listing as _Listing
        try:
            _tmp = _Listing(url=listing.get('url', ''), source=listing.get('source_enum', listing.get('source')))
            for _f in ("area_m2", "rooms", "bezirk", "address", "coordinates", "coordinate_source"):
                if _f in listing:
                    setattr(_tmp, _f, listing[_f])
            listing['unit_fingerprint'] = _compute_unit_fp(_tmp)
        except Exception as e:
            logging.warning(f"unit_fingerprint computation failed: {e}")
            listing['unit_fingerprint'] = None
```

This does not change the existing dedup match key (`content_fingerprint` + `source_enum` at line 348-351) — `unit_fingerprint` is written alongside for display-layer merging only, never used to find `existing`.

Also add `unit_fingerprint` to the `update_set` dict in the existing-doc branch (around line 363-367) so it gets refreshed on price updates too:

```python
                update_set = {
                    'price_total': price_val,
                    'price_history': price_history,
                    'processed_at': listing.get('processed_at', now.timestamp()),
                    'unit_fingerprint': listing.get('unit_fingerprint'),
                }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_upsert_unit_fingerprint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```
git add Project/Integration/mongodb_handler.py Tests/test_upsert_unit_fingerprint.py
git commit -m "feat(dedup): write unit_fingerprint on every listing upsert"
```

### Task 1.3: `record_relist_event` — same-source relist detection with cross-source disambiguation

**Files:**
- Modify: `Project/Integration/mongodb_handler.py:326-407`
- Test: `Tests/test_relist_events.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_relist_events.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler_with_existing(existing_doc):
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.collection = MagicMock()
    handler.collection.find_one.return_value = existing_doc
    return handler


def test_relist_event_recorded_when_same_source_doc_was_taken():
    existing = {
        "_id": "abc", "price_total": 290000.0, "price_history": [],
        "listing_status": "taken", "taken_at": "2026-06-01T00:00:00",
        "source_enum": "willhaben", "content_fingerprint": "fp1",
    }
    handler = _handler_with_existing(existing)
    listing = {
        "url": "https://example.com/1", "price_total": 295000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
    }
    handler.upsert_listing_with_history(listing)

    update_call = handler.collection.update_one.call_args[0][1]["$set"]
    assert update_call["listing_status"] == "active"
    assert update_call["times_relisted"] == 1
    assert len(update_call["relist_events"]) == 1
    assert update_call["relist_events"][0]["price_at_relist"] == 295000.0


def test_no_relist_event_when_existing_doc_still_active():
    existing = {
        "_id": "abc", "price_total": 290000.0, "price_history": [],
        "listing_status": "active", "source_enum": "willhaben",
        "content_fingerprint": "fp1",
    }
    handler = _handler_with_existing(existing)
    listing = {
        "url": "https://example.com/1", "price_total": 295000.0,
        "title": "Nice flat", "area_m2": 62.0, "rooms": 3.0,
        "bezirk": "1010", "source_enum": "willhaben",
    }
    handler.upsert_listing_with_history(listing)

    update_call = handler.collection.update_one.call_args[0][1]["$set"]
    assert "relist_events" not in update_call
    assert "times_relisted" not in update_call
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_relist_events.py -v`
Expected: FAIL — `KeyError: 'times_relisted'` (first test), second test passes trivially (no regression yet)

- [ ] **Step 3: Write minimal implementation**

In `Project/Integration/mongodb_handler.py`, inside the `if existing:` branch of `upsert_listing_with_history` (currently lines 353-372), right after computing `price_history` and before building `update_set`:

```python
            if existing:
                old_price = existing.get('price_total')
                price_history = existing.get('price_history', [])

                if old_price and old_price != price_val:
                    price_history.append({
                        'price_total': old_price,
                        'recorded_at': now
                    })

                update_set = {
                    'price_total': price_val,
                    'price_history': price_history,
                    'processed_at': listing.get('processed_at', now.timestamp()),
                    'unit_fingerprint': listing.get('unit_fingerprint'),
                }
                if existing.get('price_at_scrape') is None:
                    update_set['price_at_scrape'] = old_price or price_val

                # Relist detection: only fires for a same-source match on a
                # previously-taken doc. A cross-source fingerprint match on an
                # *active* doc from a different source is a plain new insert
                # elsewhere in this function, never a relist event here -
                # matching only happens by (content_fingerprint, source_enum),
                # so `existing` is always same-source by construction.
                if existing.get('listing_status') == 'taken':
                    taken_at = existing.get('taken_at')
                    days_off_market = None
                    if taken_at:
                        try:
                            delta = now - taken_at
                            days_off_market = delta.days
                        except TypeError:
                            days_off_market = None
                    relist_events = existing.get('relist_events', [])
                    relist_events.append({
                        'delisted_at': taken_at,
                        'republished_at': now,
                        'days_off_market': days_off_market,
                        'price_at_relist': price_val,
                    })
                    update_set['relist_events'] = relist_events
                    update_set['times_relisted'] = existing.get('times_relisted', 0) + 1
                    update_set['listing_status'] = 'active'

                self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": update_set}
                )
                return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_relist_events.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```
git add Project/Integration/mongodb_handler.py Tests/test_relist_events.py
git commit -m "feat(dedup): record relist_events when a taken listing reappears on the same source"
```

### Task 1.4: `pick_canonical_doc` — most-complete-data-wins selection for cross-source display dedup

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (add function; used by dashboard/top-5 query layer in a future integration task, not wired into any endpoint here — this task delivers the pure selection function per the spec's "Resolved decisions" table so it exists and is tested, per-endpoint wiring is separate follow-up work outside this plan's file list)
- Test: `Tests/test_canonical_doc_selection.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_canonical_doc_selection.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Integration.mongodb_handler import pick_canonical_doc


def test_most_complete_doc_wins():
    docs = [
        {"_id": "a", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 100.0},
        {"_id": "b", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "area_m2": 62, "rooms": 3, "bezirk": "1010", "first_scraped_at": 200.0},
    ]
    assert pick_canonical_doc(docs)["_id"] == "b"


def test_tie_break_on_earliest_first_scraped_at():
    docs = [
        {"_id": "a", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 200.0},
        {"_id": "b", "unit_fingerprint": "fp1", "title": "Flat", "price_total": 300000,
         "first_scraped_at": 100.0},
    ]
    assert pick_canonical_doc(docs)["_id"] == "b"


def test_single_doc_returns_itself():
    docs = [{"_id": "a", "unit_fingerprint": "fp1", "title": "Flat"}]
    assert pick_canonical_doc(docs)["_id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_canonical_doc_selection.py -v`
Expected: FAIL — `ImportError: cannot import name 'pick_canonical_doc'`

- [ ] **Step 3: Write minimal implementation**

Add to `Project/Integration/mongodb_handler.py`, near `compute_content_fingerprint`'s usage (module-level function, not a method — mirrors `is_valid_listing_data`'s module-level placement):

```python
def _completeness_score(doc: Dict) -> int:
    """Count of non-null fields, excluding Mongo/bookkeeping keys that are
    always present and don't reflect scrape data quality."""
    _EXCLUDE = {"_id", "content_fingerprint", "unit_fingerprint", "source_enum",
                "url", "processed_at", "sent_to_telegram", "sent_to_telegram_at"}
    return sum(1 for k, v in doc.items() if k not in _EXCLUDE and v not in (None, "", []))


def pick_canonical_doc(docs: List[Dict]) -> Dict:
    """Given multiple docs sharing a unit_fingerprint, pick the display
    canonical one: most non-null fields wins; tie-break on earliest
    first_scraped_at. Per spec 'Resolved decisions' table."""
    return sorted(
        docs,
        key=lambda d: (-_completeness_score(d), d.get("first_scraped_at") or float("inf")),
    )[0]
```

Add `from typing import List, Dict` to the existing imports if not already present (file already imports `Tuple` from `typing` per `is_valid_listing_data`'s signature — extend that import line).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_canonical_doc_selection.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```
git add Project/Integration/mongodb_handler.py Tests/test_canonical_doc_selection.py
git commit -m "feat(dedup): add pick_canonical_doc for cross-source display selection"
```

### Task 1.5: Regression check — existing upsert/mongodb tests still pass

**Files:**
- No new files.

- [ ] **Step 1: Run the full existing Mongo/dedup test suite**

Run: `cd Tests && python -m pytest test_scraper_mongodb.py test_taken_listings_mongodb.py test_coop_fingerprint.py test_listing_validator.py -v`
Expected: PASS, 0 failures (Tasks 1.1-1.4 must not have changed the per-source dedup match key or the co-op xsrc fingerprint behavior)

- [ ] **Step 2: If any failure, fix root cause (not the test)**

If `test_scraper_mongodb.py` fails on a missing `unit_fingerprint`/`times_relisted` key in an assertion, that means the change altered externally-observed upsert behavior beyond what the spec allows — re-check Task 1.2/1.3/1.4 for scope creep before touching the pre-existing test.

- [ ] **Step 3: Commit (only if a fix was needed)**

```
git add -A
git commit -m "fix(dedup): resolve regression from unit_fingerprint/relist_events changes"
```

---

## Phase 2: Private-seller classification + coordinate-precision-aware distance recompute

### Task 2.1: `extract_seller_type` text-marker classifier

**Files:**
- Modify: `Project/Application/scraping/field_extractors.py` (add function)
- Modify: `Project/Domain/listing.py:75` (add `seller_type` field near `is_provisionsfrei`)
- Test: `Tests/test_field_extractors_seller_type.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_field_extractors_seller_type.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping.field_extractors import extract_seller_type


def test_private_marker_detected():
    text = "provisionsfrei, direkt vom eigentümer, keine käuferprovision"
    assert extract_seller_type(text) == "private"


def test_agency_marker_detected():
    text = "wir als immobilienbüro freuen uns, maklerprovision 3%"
    assert extract_seller_type(text) == "agency"


def test_bautraeger_from_genossenschaft_flag():
    text = "geförderte wohnung, warme miete"
    assert extract_seller_type(text, is_genossenschaft=True) == "bautraeger"


def test_unknown_when_no_marker():
    text = "schöne 3-zimmer wohnung mit balkon"
    assert extract_seller_type(text) == "unknown"


def test_agency_wins_over_bautraeger_when_both_present():
    text = "geförderte wohnung, vermittelt durch unser immobilienbüro"
    assert extract_seller_type(text, is_genossenschaft=True) == "agency"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_field_extractors_seller_type.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_seller_type'`

- [ ] **Step 3: Write minimal implementation**

```python
# Project/Application/scraping/field_extractors.py
# Add near the end, after extract_is_genossenschaft

_PRIVATE_MARKERS = [
    r'provisionsfrei', r'privatverkauf', r'von\s+privat', r'direkt\s+vom\s+eigent',
]
_AGENCY_MARKERS = [
    r'makler(?!provision)', r'immobilienb(ü|ue)ro', r'maklerprovision',
]


def extract_seller_type(text: str, is_genossenschaft: Optional[bool] = None) -> str:
    """Classify seller as 'private' | 'agency' | 'bautraeger' | 'unknown' from
    already-scraped listing text (title + description). Does NOT fetch the
    contact page - that regex lives in Application/outreach/contact_extractor.py
    and is intentionally not reused here (it requires a separate network
    request per listing, made only during outreach, too expensive at scrape
    time for every listing).

    Agency markers take priority over the bautraeger co-op signal: a builder's
    unit can still be listed for them by an agency."""
    if _any_match(text, _AGENCY_MARKERS):
        return "agency"
    if _any_match(text, _PRIVATE_MARKERS):
        return "private"
    if is_genossenschaft:
        return "bautraeger"
    return "unknown"
```

Add to `Domain/listing.py` near line 75 (`is_provisionsfrei` field):

```python
    seller_type:             Optional[str]  = None   # 'private' | 'agency' | 'bautraeger' | 'unknown'; see extract_seller_type
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_field_extractors_seller_type.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```
git add Project/Application/scraping/field_extractors.py Project/Domain/listing.py Tests/test_field_extractors_seller_type.py
git commit -m "feat(seller-type): add text-marker seller classification, no extra network fetch"
```

### Task 2.2: Wire `extract_seller_type` into `willhaben_scraper.py`

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py:23-29` (import), `:544-546` (call site)
- Test: extend `Tests/test_field_extractors_seller_type.py` is unit-level only; add a scraper-level smoke assertion to existing willhaben scraper test if one exists, else skip (scraper tests hit live HTML fixtures — out of scope for this task; unit coverage on the extractor is sufficient per Task 2.1).

- [ ] **Step 1: Add the import**

In `Project/Application/scraping/willhaben_scraper.py`, extend the existing `from Application.scraping.field_extractors import (...)` block (lines 23-29) to include `extract_seller_type`.

- [ ] **Step 2: Call it at the existing `_combined` call site**

Right after line 546 (`listing.maklerprovision_pct = extract_maklerprovision_pct(_combined)`):

```python
            listing.seller_type = extract_seller_type(_combined, is_genossenschaft=listing.is_genossenschaft)
```

- [ ] **Step 3: Run the willhaben scraper's existing unit tests (no live network)**

Run: `cd Tests && python -m pytest test_listing_validator.py -k willhaben -v` (or the closest existing offline willhaben test file — confirm exact filename with `ls Tests/ | grep -i willhaben` before running; do not add a new network-dependent test)
Expected: PASS, no regressions

- [ ] **Step 4: Commit**

```
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(seller-type): wire extract_seller_type into willhaben_scraper"
```

### Task 2.3: `coordinate_precision_m` field + distance recompute trigger on precision upgrade

**Files:**
- Modify: `Project/Domain/listing.py:46` (add field near `coordinate_source`)
- Modify: `Project/Application/main.py:505-520` (both geocode call sites)
- Test: `Tests/test_coordinate_precision.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_coordinate_precision.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.main import compute_coordinate_precision_m


def test_exact_precision():
    assert compute_coordinate_precision_m("exact") == 10


def test_landmark_precision():
    assert compute_coordinate_precision_m("landmark") == 200


def test_none_precision():
    assert compute_coordinate_precision_m("none") is None
    assert compute_coordinate_precision_m(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_coordinate_precision.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_coordinate_precision_m'`

- [ ] **Step 3: Write minimal implementation**

Add a module-level helper near the top of `Project/Application/main.py` (before the geocode call sites at lines ~508/518). Named `compute_coordinate_precision_m` (verb prefix) rather than `coordinate_precision_m`, to avoid grep confusion with the `Listing.coordinate_precision_m` field of the same conceptual name:

```python
def compute_coordinate_precision_m(coordinate_source):
    """Confidence radius in meters for a given coordinate_source tier."""
    return {"exact": 10, "landmark": 200}.get(coordinate_source)
```

At both call sites (around line 508-509 and 518-519), extend the existing pattern:

```python
            geocoded = geocode_listing(listing_dict)
            if geocoded.get('coordinate_source') != 'none':
                prior_precision = compute_coordinate_precision_m(listing_dict.get('coordinate_source'))
                new_precision = compute_coordinate_precision_m(geocoded.get('coordinate_source'))
                listing_dict['coordinate_precision_m'] = new_precision
                mongodb_handler.update_listing_coordinates(...)  # existing call, unchanged
                if new_precision is not None and (prior_precision is None or new_precision < prior_precision):
                    # Precision improved (e.g. landmark -> exact): recompute
                    # walk-distance calcs that were based on the coarser fix.
                    coords = geocoded.get('coordinates')
                    if coords:
                        listing_dict['school_walk_minutes'] = geocoding_handler.get_school_walk_minutes(coords)
                        listing_dict['ubahn_walk_minutes'] = geocoding_handler.get_walking_distance_to_nearest_ubahn(coords)
```

Add the field to `Domain/listing.py` right after `coordinate_source` (line 46):

```python
    coordinate_precision_m: Optional[int] = None  # 10 | 200 | None; see compute_coordinate_precision_m()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_coordinate_precision.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```
git add Project/Domain/listing.py Project/Application/main.py Tests/test_coordinate_precision.py
git commit -m "feat(geo): add coordinate_precision_m and recompute walk-distances on precision upgrade"
```

---

## Phase 3: Richer capture — coverage-consistency fix (no new fields)

### Task 3.1: Audit co-op scrapers for missing `field_extractors` calls, then wire what has text available

**Files:**
- Modify: `Project/Application/scraping/genossenschaft_scraper.py` (import + call sites found in Step 1)
- Modify: `Project/Application/scraping/willhaben_private_coop.py` (same)
- Test: `Tests/test_coop_scraper_field_coverage.py` (new)

- [ ] **Step 1: Run the audit command and record findings as inline comments**

Run: `grep -n "def parse\|def _parse\|description\|_text(\|get_text" Project/Application/scraping/genossenschaft_scraper.py Project/Application/scraping/willhaben_private_coop.py`

`genossenschaft_scraper.py` parses multiple Bauträger sources (mygewo, wiensued, sozialbau, etc.) from **list-view HTML blocks**, not always a fetched detail-page description — some blocks may only have title + price, no free text. For each `def parse*`/`def _parse*` function the grep surfaces, open it and check whether it assigns a `description`-like free-text variable (e.g. the `_text(block, ...)` calls already used for `listing.address` at lines 144/169/193 show which blocks have text-bearing selectors available). Add a one-line comment directly above each such function: `# field_extractors coverage: <variable-name> available` or `# field_extractors coverage: no free-text field, skip`. This is the map for Step 3 below — do this even though the comment-only part produces a small diff, it prevents wiring extractors against text that doesn't exist.

- [ ] **Step 2: Write the failing test**

```python
# Tests/test_coop_scraper_field_coverage.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from Application.scraping import genossenschaft_scraper as gs


def test_module_imports_field_extractors():
    # genossenschaft_scraper must call the same coverage-fields extraction
    # helpers the other scrapers use, wherever description text is available.
    import inspect
    src = inspect.getsource(gs)
    assert "extract_doppelmakler" in src or "extract_maklerprovision_pct" in src
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_coop_scraper_field_coverage.py -v`
Expected: FAIL — assertion error, neither extractor referenced yet

- [ ] **Step 4: Write minimal implementation**

For each parser block flagged in Step 1's comments as having a text field (e.g. a `description` or combined attribute-text variable), add:

```python
from Application.scraping.field_extractors import (
    extract_doppelmakler, extract_maklerprovision_pct, extract_sonderumlage_risk,
    extract_seller_type,
)
```

and, at the point where that block's listing object is populated, call:

```python
    listing.doppelmakler = extract_doppelmakler(description_text)
    listing.maklerprovision_pct = extract_maklerprovision_pct(description_text)
    listing.sonderumlage_risk = extract_sonderumlage_risk(description_text)
    listing.seller_type = extract_seller_type(description_text, is_genossenschaft=listing.is_genossenschaft)
```

using whatever variable name Step 1 identified as that block's text source. Blocks flagged "no free-text field, skip" are left unchanged (fields stay `None`, which is correct — not a bug).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_coop_scraper_field_coverage.py -v`
Expected: PASS

- [ ] **Step 6: Run co-op regression suite**

Run: `cd Tests && python -m pytest test_coop_fingerprint.py -v`
Expected: PASS, 0 failures (co-op fingerprint logic untouched by this task)

- [ ] **Step 7: Commit**

```
git add Project/Application/scraping/genossenschaft_scraper.py Project/Application/scraping/willhaben_private_coop.py Tests/test_coop_scraper_field_coverage.py
git commit -m "fix(capture): wire doppelmakler/maklerprovision/sonderumlage/seller_type extraction into co-op scrapers"
```

---

## Phase 4: District drift analytics

### Task 4.1: `district_snapshot.py` monthly aggregation job

**Files:**
- Create: `Project/Application/analytics/__init__.py` (if the `analytics/` dir doesn't exist yet)
- Create: `Project/Application/analytics/district_snapshot.py`
- Test: `Tests/test_district_snapshot.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# Tests/test_district_snapshot.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Project"))
from unittest.mock import MagicMock
from Application.analytics.district_snapshot import build_district_snapshot


def test_build_snapshot_computes_avg_and_median():
    from datetime import datetime
    listings = [
        {"bezirk": "1010", "price_total": 300000, "area_m2": 60, "listing_status": "active",
         "first_scraped_at": datetime(2026, 7, 1).timestamp()},
        {"bezirk": "1010", "price_total": 400000, "area_m2": 80, "listing_status": "active",
         "first_scraped_at": datetime(2026, 7, 1).timestamp()},
        {"bezirk": "1010", "price_total": 200000, "area_m2": 50, "listing_status": "taken",
         "first_scraped_at": datetime(2026, 7, 1).timestamp(), "taken_at": datetime(2026, 7, 11)},
    ]
    snap = build_district_snapshot("1010", "2026-07", listings, source="scraped")
    assert snap["bezirk"] == "1010"
    assert snap["period"] == "2026-07"
    assert snap["listing_count"] == 3
    assert snap["active_count"] == 2
    assert round(snap["avg_price_m2"], 1) == round((300000/60 + 400000/80 + 200000/50) / 3, 1)
    assert snap["source"] == "scraped"
    assert snap["avg_days_on_market"] == 10.0  # only the taken listing has a resolvable window


def test_build_snapshot_handles_empty_list():
    snap = build_district_snapshot("1010", "2026-07", [], source="scraped")
    assert snap["listing_count"] == 0
    assert snap["avg_price_m2"] is None
    assert snap["median_price_m2"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_district_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'Application.analytics'`

- [ ] **Step 3: Write minimal implementation**

```python
# Project/Application/analytics/__init__.py
```

```python
# Project/Application/analytics/district_snapshot.py
"""Monthly district (bezirk) rollup: price/m², volume, days-on-market.
Written to the district_snapshots collection for dashboard drift charts."""
import statistics
from typing import Dict, List, Any, Optional


def _days_on_market(listing: Dict[str, Any]) -> Optional[float]:
    """Days between first_scraped_at and taken_at, for COMPLETED cycles only
    (listing_status == 'taken'). Still-active listings are excluded rather
    than measured against "now" - that would make avg_days_on_market drift
    every time the job reruns for the same historical period, which defeats
    the point of a monthly snapshot. first_scraped_at is epoch-seconds
    (per upsert_listing_with_history), taken_at is a datetime (per
    mark_listing_taken). Returns None if the cycle isn't complete or either
    endpoint is missing/malformed."""
    from datetime import datetime
    if listing.get("listing_status") != "taken":
        return None
    first = listing.get("first_scraped_at")
    taken_at = listing.get("taken_at")
    if not first or not isinstance(taken_at, datetime):
        return None
    first_dt = datetime.utcfromtimestamp(first) if isinstance(first, (int, float)) else first
    if not isinstance(first_dt, datetime):
        return None
    return (taken_at - first_dt).total_seconds() / 86400.0


def build_district_snapshot(bezirk: str, period: str, listings: List[Dict[str, Any]],
                             source: str = "scraped") -> Dict[str, Any]:
    prices_per_m2 = []
    active_count = 0
    relisted_count = 0
    days_on_market = []

    for l in listings:
        price = l.get("price_total")
        area = l.get("area_m2")
        if price and area:
            prices_per_m2.append(price / area)
        if l.get("listing_status") == "active":
            active_count += 1
        if l.get("times_relisted"):
            relisted_count += 1
        dom = _days_on_market(l)
        if dom is not None:
            days_on_market.append(dom)

    listing_count = len(listings)
    avg_price_m2 = statistics.fmean(prices_per_m2) if prices_per_m2 else None
    median_price_m2 = statistics.median(prices_per_m2) if prices_per_m2 else None
    avg_days_on_market = statistics.fmean(days_on_market) if days_on_market else None
    relisted_pct = (relisted_count / listing_count * 100) if listing_count else None

    return {
        "bezirk": bezirk,
        "period": period,
        "avg_price_m2": avg_price_m2,
        "median_price_m2": median_price_m2,
        "listing_count": listing_count,
        "active_count": active_count,
        "avg_days_on_market": avg_days_on_market,
        "relisted_pct": relisted_pct,
        "source": source,
    }


def run_monthly_aggregation(mongo_handler, period: str) -> int:
    """Query listings for the given YYYY-MM period, grouped by bezirk, and
    upsert one district_snapshots doc per bezirk. Returns count of docs written."""
    from datetime import datetime
    year, month = (int(x) for x in period.split("-"))
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), (month % 12) + 1, 1)

    cursor = mongo_handler.collection.find({
        "processed_at": {"$gte": start.timestamp(), "$lt": end.timestamp()},
    })
    by_bezirk: Dict[str, List[Dict[str, Any]]] = {}
    for doc in cursor:
        bezirk = doc.get("bezirk")
        if not bezirk:
            continue
        by_bezirk.setdefault(bezirk, []).append(doc)

    written = 0
    for bezirk, docs in by_bezirk.items():
        snap = build_district_snapshot(bezirk, period, docs, source="scraped")
        mongo_handler.db["district_snapshots"].update_one(
            {"bezirk": bezirk, "period": period, "source": "scraped"},
            {"$set": snap},
            upsert=True,
        )
        written += 1
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_district_snapshot.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```
git add Project/Application/analytics/__init__.py Project/Application/analytics/district_snapshot.py Tests/test_district_snapshot.py
git commit -m "feat(analytics): add district_snapshot monthly rollup builder"
```

### Task 4.2: `run_monthly_aggregation` integration test against a fake collection

**Files:**
- Test: extend `Tests/test_district_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to Tests/test_district_snapshot.py
from unittest.mock import MagicMock
from Application.analytics.district_snapshot import run_monthly_aggregation


def test_run_monthly_aggregation_writes_one_doc_per_bezirk():
    handler = MagicMock()
    handler.collection.find.return_value = [
        {"bezirk": "1010", "price_total": 300000, "area_m2": 60, "listing_status": "active",
         "processed_at": 1751328000.0},
        {"bezirk": "1020", "price_total": 250000, "area_m2": 55, "listing_status": "active",
         "processed_at": 1751328000.0},
    ]
    handler.db = {"district_snapshots": MagicMock()}

    written = run_monthly_aggregation(handler, "2026-07")
    assert written == 2
    assert handler.db["district_snapshots"].update_one.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Tests && python -m pytest test_district_snapshot.py -k run_monthly_aggregation -v`
Expected: FAIL if `handler.db["district_snapshots"]` access pattern doesn't match `MongoDBHandler`'s actual `self.db` attribute — verify `self.db` exists on `MongoDBHandler.__init__` (grep confirms `self.collection = self.db[collection_name]`, so `self.db` is the pymongo `Database` object; a plain dict mock as above satisfies subscript access `handler.db["district_snapshots"]` in the test).

- [ ] **Step 3: Implementation already written in Task 4.1** — no change needed if Step 2 passes; if it fails on `db` access shape, adjust `run_monthly_aggregation` to use `mongo_handler.db["district_snapshots"]` consistently (already does).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Tests && python -m pytest test_district_snapshot.py -v`
Expected: PASS (3 tests total)

- [ ] **Step 5: Commit**

```
git add Tests/test_district_snapshot.py
git commit -m "test(analytics): cover run_monthly_aggregation writes one snapshot per bezirk"
```

---

## Phase 5: External historical backfill — spike only

**Per the spec's flagged risk:** Statistik Austria/Immobilienpreisspiegel's data shape and licensing have not been verified (no `WebFetch` done — host not previously on the sandbox allowlist). Do not write `district_snapshot_backfill.py` against unverified assumptions about field names, granularity, or update cadence.

### Task 5.1: Spike — verify external data source shape before implementing

**Files:**
- No code changes. Output is a decision, recorded as a short section appended to the spec.

- [ ] **Step 1: Fetch and inspect the source**

Use `WebFetch` against the Statistik Austria / Immobilienpreisspiegel open-data publication (confirm exact URL with the user or via a `WebSearch` for "Statistik Austria Immobilienpreisspiegel open data Bezirk" if not already known — do not guess a URL). Determine: (a) actual field names / CSV or API schema, (b) granularity (confirm yearly vs semi-annual per spec's assumption), (c) license terms (confirm free/open re-use, no attribution blocker for this project's private dashboard use).

- [ ] **Step 2: Record findings**

Append a "Sub-project 5 — spike findings" section to `docs/superpowers/specs/2026-08-16-data-platform-design.md` with: confirmed schema, confirmed granularity, license confirmation, and either (a) a go-ahead to write `district_snapshot_backfill.py` matching the confirmed shape, or (b) a documented blocker if the source isn't usable as assumed.

- [ ] **Step 3: Do NOT write `district_snapshot_backfill.py` in this plan**

That implementation is scoped to a follow-up plan once Step 2's findings are in, per "Size target: ~150 lines... Run once manually" in the spec — building it now against unverified assumptions would violate the No Placeholders rule (the field mappings would be guesses).

---

## Phase 6: Cross-cutting scope-flag tasks

### Task 6.1: Graph rebuild (`graph_scope: true`)

**Files:** none — operates on `graphify-out/graph.json`.

- [ ] **Step 1: Run graphify update**

Run: `graphify update .`

- [ ] **Step 2: Validate new nodes/edges exist**

Run: `graphify query "unit_fingerprint dedup"` and confirm the query surfaces `compute_unit_fingerprint`, `record_relist_event`, `extract_seller_type`, and `district_snapshot.py` as nodes connected to `mongodb_handler.py` / `field_extractors.py` / `listing_validator.py`.

- [ ] **Step 3: Write a rationale_for edge for the fingerprint precision correction**

If the graph tool supports manual edge annotation, record that `compute_unit_fingerprint`'s 4-decimal coordinate rounding exists *because* 3-decimal rounding was measured as ~111m (too coarse) during plan review — this is the kind of non-obvious "why" that should survive in the graph, not just in this plan file.

- [ ] **Step 4: Commit graph artifacts if tracked**

Run: `git status graphify-out/` — if `graphify-out/graph.json` is git-tracked, commit it; if gitignored, skip.

### Task 6.2: Coverage measurement (`test_scope: true`)

**Files:** none — measurement only.

- [ ] **Step 1: Record baseline coverage before this plan's changes**

Run (on the commit prior to Task 1.1, or via `git stash` if still mid-plan): `cd Tests && python -m pytest --cov=../Project --cov-report=term-missing | tail -5`
Record the total `%` line.

- [ ] **Step 2: Record coverage after all phases**

Run: `cd Tests && python -m pytest --cov=../Project --cov-report=term-missing | tail -5`

- [ ] **Step 3: Compare**

If the new total is lower than the baseline, add missing test coverage for whichever new module dragged it down (most likely `district_snapshot.py`'s `run_monthly_aggregation`, since Task 4.2 only covers the happy path) before declaring the plan done. Do not merge with a coverage regression.

---

## Final verification (all phases)

- [ ] Run the complete relevant test suite: `cd Tests && python -m pytest test_unit_fingerprint.py test_upsert_unit_fingerprint.py test_relist_events.py test_canonical_doc_selection.py test_field_extractors_seller_type.py test_coordinate_precision.py test_coop_scraper_field_coverage.py test_district_snapshot.py test_scraper_mongodb.py test_taken_listings_mongodb.py test_coop_fingerprint.py test_listing_validator.py -v`
- [ ] All new tests pass, all pre-existing tests still pass (0 regressions)
- [ ] `git log --oneline` on the feature branch shows one commit per task, each with a clear message
- [ ] Coverage did not regress (Task 6.2)
- [ ] Graph updated and validated (Task 6.1)
