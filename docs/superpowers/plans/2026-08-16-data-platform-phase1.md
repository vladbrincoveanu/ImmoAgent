# Data Platform Phase 1: Dedup, Relist Tracking, Private Seller, Geo Precision — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the real production dedup/write path in `main.py` so republished listings are tracked instead of silently skipped, `price_history` actually gets written (currently dead), and add `seller_type` + geo-precision gating so distance-sensitive logic only trusts exact coordinates.

**Architecture:** All fixes land in the existing write path (`Application/main.py:save_listings_to_mongodb`, lines 437-521) and its two helper modules (`Application/helpers/listing_validator.py`, `Integration/mongodb_handler.py`). No new collections in this phase — that's `district_snapshots` (Phase 2, deferred per spec section 5, lower priority per your own answer).

**Tech Stack:** Python, pymongo, unittest + unittest.mock (existing `Project/Tests/` pattern — flat directory, `MongoDBHandler.__new__` + `MagicMock` collection).

**Scope note:** The spec (`docs/superpowers/specs/2026-08-16-data-platform-design.md`) has 5 sub-projects. This plan covers sub-projects 2 and 3 (dedup/relist + private-seller/geo — your stated priorities: duplicates, republish, private sellers, exact location). Sub-projects 4 (extractor coverage audit) and 5 (district_snapshots + external backfill) are analytics/coverage work you deferred ("data is the goal, build other stuff later") — separate follow-up plan, not in this one. **Correction found while planning Task 6:** the code that computes real per-address school/U-Bahn distance (`WillhabenScraper.get_amenities`) is dead — zero callers. Production currently uses a static per-district lookup table for every listing, not real coordinates. This plan adds the `coordinate_precision_m` field so that distinction becomes visible/queryable, but wiring the orphaned real-distance code into the live path is flagged as Task 7, not built here (it's a scraper-control-flow change, not data plumbing — deserves its own reviewed task).

---

### Task 1: Content fingerprint v2 (address/coord-based, cross-source-stable)

**Files:**
- Modify: `Project/Application/helpers/listing_validator.py` (add function near existing `compute_xsrc_fingerprint` at line 96)
- Test: `Project/Tests/test_content_fingerprint_v2.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.helpers.listing_validator import compute_content_fingerprint_v2


class TestContentFingerprintV2(unittest.TestCase):
    def test_stable_across_title_edit(self):
        base = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100",
                "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben",
                "title": "Schöne 3-Zimmer Wohnung"}
        edited = dict(base, title="TOP Schöne 3-Zimmer Wohnung mit Balkon!!")
        self.assertEqual(compute_content_fingerprint_v2(base), compute_content_fingerprint_v2(edited))

    def test_differs_by_address(self):
        a = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100", "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben"}
        b = dict(a, address="Musterstraße 2, 1100 Wien")
        self.assertNotEqual(compute_content_fingerprint_v2(a), compute_content_fingerprint_v2(b))

    def test_falls_back_to_title_when_no_address(self):
        # No address at all -> degrade to title-based key, but must not raise
        d = {"bezirk": "1100", "area_m2": 70.0, "rooms": 3, "source_enum": "willhaben", "title": "Nice flat"}
        fp = compute_content_fingerprint_v2(d)
        self.assertIsInstance(fp, str)
        self.assertEqual(len(fp), 32)  # md5 hex digest

    def test_rounds_area_to_nearest_m2(self):
        a = {"address": "Musterstraße 1, 1100 Wien", "bezirk": "1100", "area_m2": 70.2, "rooms": 3, "source_enum": "willhaben"}
        b = dict(a, area_m2=70.4)
        self.assertEqual(compute_content_fingerprint_v2(a), compute_content_fingerprint_v2(b))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_content_fingerprint_v2.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_content_fingerprint_v2'`

- [ ] **Step 3: Write minimal implementation**

Add to `Project/Application/helpers/listing_validator.py`, directly below `compute_content_fingerprint` (after line 122):

```python
def compute_content_fingerprint_v2(listing: Dict[str, Any]) -> str:
    """
    Cross-source-stable content fingerprint. Prefers address (survives ad-text
    edits, matches the same unit across sources); falls back to the title-based
    key only when address is missing (degraded case — different sources' title
    text for the same unit rarely matches, so this fallback stays per-source-ish).
    """
    address = listing.get('address')
    bezirk = listing.get('bezirk', '')
    area = listing.get('area_m2')
    area_key = str(int(round(area))) if area else ''
    rooms_key = str(listing.get('rooms', '')) if listing.get('rooms') is not None else ''
    source_key = str(listing.get('source_enum', listing.get('source', '')))

    if address:
        raw = f"{_norm(address)}|{bezirk}|{area_key}|{rooms_key}"
    else:
        raw = f"{listing.get('title', '')}{area_key}{rooms_key}{bezirk}{source_key}"

    return hashlib.md5(raw.encode('utf-8')).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_content_fingerprint_v2.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```
git add Project/Application/helpers/listing_validator.py Project/Tests/test_content_fingerprint_v2.py
git commit -m "feat(dedup): add address-based content fingerprint v2, stable across ad-text edits"
```

---

### Task 2: `handle_fingerprint_match` — actually update on fingerprint match instead of silent skip

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (add new function, module-level, near `mark_listing_taken` at line 409)
- Test: `Project/Tests/test_handle_fingerprint_match.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from datetime import datetime, timedelta
from Integration.mongodb_handler import handle_fingerprint_match


class TestHandleFingerprintMatch(unittest.TestCase):
    def test_relist_after_taken(self):
        taken_at = datetime.utcnow() - timedelta(days=5)
        existing = {"_id": 1, "listing_status": "taken", "taken_at": taken_at,
                    "price_total": 250000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 260000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(update["listing_status"], "active")
        self.assertIsNone(update["taken_at"])
        self.assertEqual(update["times_relisted"], 1)
        self.assertEqual(len(update["relist_events"]), 1)
        event = update["relist_events"][0]
        self.assertEqual(event["delisted_at"], taken_at)
        self.assertEqual(event["price_at_relist"], 260000)
        self.assertGreaterEqual(event["days_off_market"], 4)  # ~5 days, allow clock skew

    def test_price_change_while_active_updates_history_no_relist(self):
        existing = {"_id": 2, "listing_status": "active", "taken_at": None,
                     "price_total": 300000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 295000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(len(update["price_history"]), 1)
        self.assertEqual(update["price_history"][0]["price_total"], 300000)
        self.assertNotIn("relist_events", update)  # untouched -> no key emitted
        self.assertEqual(update["price_total"], 295000)

    def test_no_price_change_no_history_entry(self):
        existing = {"_id": 3, "listing_status": "active", "taken_at": None,
                     "price_total": 300000, "price_history": [], "relist_events": [], "times_relisted": 0}
        incoming = {"price_total": 300000}

        update = handle_fingerprint_match(existing, incoming)

        self.assertEqual(update.get("price_history", []), [])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_handle_fingerprint_match.py -v`
Expected: FAIL with `ImportError: cannot import name 'handle_fingerprint_match'`

- [ ] **Step 3: Write minimal implementation**

Add to `Project/Integration/mongodb_handler.py`, as a module-level function near `mark_listing_taken` (after line ~421, same indentation level — module-level, not a class method, matching `compute_content_fingerprint`'s module-level pattern):

```python
def handle_fingerprint_match(existing: Dict, incoming: Dict) -> Dict:
    """
    Build the $set payload for an existing_by_fingerprint match (main.py's
    save loop). Replaces a bare `continue` (silent skip) with an actual update:
    always track price changes; additionally log a relist cycle when the
    matched doc was 'taken'. Returns a dict of fields to $set — does not
    write to Mongo itself (caller does the update_one).
    """
    from datetime import datetime
    now = datetime.utcnow()
    update: Dict[str, Any] = {}

    old_price = existing.get('price_total')
    new_price = incoming.get('price_total')
    if new_price is not None and old_price is not None and new_price != old_price:
        price_history = list(existing.get('price_history', []))
        price_history.append({'price_total': old_price, 'recorded_at': now})
        update['price_history'] = price_history
        update['price_total'] = new_price

    if existing.get('listing_status') == 'taken':
        taken_at = existing.get('taken_at')
        days_off_market = (now - taken_at).days if taken_at else 0
        relist_events = list(existing.get('relist_events', []))
        relist_events.append({
            'delisted_at': taken_at,
            'republished_at': now,
            'days_off_market': days_off_market,
            'price_at_relist': new_price if new_price is not None else old_price,
        })
        update['relist_events'] = relist_events
        update['times_relisted'] = existing.get('times_relisted', 0) + 1
        update['listing_status'] = 'active'
        update['taken_at'] = None

    return update
```

Note: needs `from typing import Dict, Any` already imported at the top of `mongodb_handler.py` — verify with `grep -n "^from typing" Project/Integration/mongodb_handler.py` before adding; add the import if missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_handle_fingerprint_match.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```
git add Project/Integration/mongodb_handler.py Project/Tests/test_handle_fingerprint_match.py
git commit -m "feat(dedup): handle_fingerprint_match tracks relists and price changes instead of silent skip"
```

---

### Task 3: Wire Task 1 + Task 2 into `main.py`'s real write path

**Files:**
- Modify: `Project/Application/main.py:485-521`
- Test: `Project/Tests/test_save_listings_dedup.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock
from Domain.listing import Listing
from Domain.sources import Source


class TestSaveListingsDedup(unittest.TestCase):
    @patch('Application.main.pymongo.MongoClient')
    @patch('Application.main.MongoDBHandler')
    def test_fingerprint_match_reactivates_taken_listing(self, mock_handler_cls, mock_client_cls):
        from Application.main import save_listings_to_mongodb

        mock_collection = MagicMock()
        mock_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = mock_collection
        # url match -> None (not a re-scrape of the same URL)
        # fingerprint match -> a previously-taken doc
        mock_collection.find_one.side_effect = [
            None,  # existing_by_url
            {"_id": "abc", "listing_status": "taken", "taken_at": None,
             "price_total": 200000, "price_history": [], "relist_events": [],
             "times_relisted": 0, "coordinates": {"lat": 48.2, "lon": 16.3}},
        ]

        listing = Listing(url="https://www.willhaben.at/new-url", source=Source.WILLHABEN,
                           title="Test flat", bezirk="1100", address="Musterstraße 1, 1100 Wien",
                           area_m2=70.0, rooms=3, price_total=210000)

        save_listings_to_mongodb([listing], mongo_uri="mongodb://fake/")

        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        set_payload = call_args[0][1]['$set']
        self.assertEqual(set_payload['listing_status'], 'active')
        self.assertEqual(set_payload['times_relisted'], 1)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_save_listings_dedup.py -v`
Expected: FAIL — `update_one` never called (current code just does `continue` after the coordinate backfill check)

- [ ] **Step 3: Write minimal implementation**

Replace `Project/Application/main.py` lines 502-511 (the `existing_by_fingerprint` block) with:

```python
                fingerprint = compute_content_fingerprint_v2(listing_dict)
                listing_dict['content_fingerprint'] = fingerprint
                existing_by_fingerprint = collection.find_one(
                    {"content_fingerprint": fingerprint, "source_enum": source_enum}
                )
                if existing_by_fingerprint:
                    duplicate_count += 1
                    geocoded = geocode_listing(listing_dict)
                    if geocoded.get('coordinate_source') != 'none' and not existing_by_fingerprint.get('coordinates'):
                        mongodb_handler.update_listing_coordinates(listing_dict['url'], geocoded)

                    update_payload = handle_fingerprint_match(existing_by_fingerprint, listing_dict)
                    if update_payload:
                        collection.update_one({"_id": existing_by_fingerprint["_id"]}, {"$set": update_payload})
                    continue
```

And change line 488 (`fingerprint = compute_content_fingerprint(listing_dict)`) to use the v2 function too, so the fingerprint stored on insert matches what's queried on later scrapes:

```python
            fingerprint = compute_content_fingerprint_v2(listing_dict)
```

Add imports at the top of `main.py` (near the existing `from Application.helpers.listing_validator import ...` line — find it with `grep -n "from Application.helpers.listing_validator import" Project/Application/main.py`):

```python
from Application.helpers.listing_validator import compute_content_fingerprint_v2
from Integration.mongodb_handler import handle_fingerprint_match
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_save_listings_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Run full existing suite to check for regressions**

Run: `cd Project/Tests && python run_tests.py`
Expected: all pass, same or higher count than baseline (check `Project/Tests/run_tests.py` output before this task for the baseline number)

- [ ] **Step 6: Commit**

```
git add Project/Application/main.py
git commit -m "fix(dedup): wire fingerprint-match handling into the real save path, was silently skipping"
```

---

### Task 4: Preserve `listing_status`/`taken_at`/`price_history` across `existing_by_url` replace

**Files:**
- Modify: `Project/Application/main.py:492-499`
- Test: `Project/Tests/test_save_listings_url_replace.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock
from Domain.listing import Listing
from Domain.sources import Source


class TestSaveListingsUrlReplace(unittest.TestCase):
    @patch('Application.main.pymongo.MongoClient')
    @patch('Application.main.MongoDBHandler')
    def test_replace_preserves_taken_status_and_pushes_price_history(self, mock_handler_cls, mock_client_cls):
        from Application.main import save_listings_to_mongodb

        mock_collection = MagicMock()
        mock_client_cls.return_value.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_collection.find_one.return_value = {
            "_id": "xyz", "url": "https://www.willhaben.at/same-url",
            "listing_status": "taken", "taken_at": "2026-08-01T00:00:00",
            "price_total": 200000, "price_history": [],
        }

        listing = Listing(url="https://www.willhaben.at/same-url", source=Source.WILLHABEN,
                           title="Test flat", bezirk="1100", area_m2=70.0, rooms=3,
                           price_total=190000)

        save_listings_to_mongodb([listing], mongo_uri="mongodb://fake/")

        mock_collection.replace_one.assert_called_once()
        replaced_doc = mock_collection.replace_one.call_args[0][1]
        self.assertEqual(replaced_doc['listing_status'], 'taken')
        self.assertEqual(replaced_doc['taken_at'], "2026-08-01T00:00:00")
        self.assertEqual(len(replaced_doc['price_history']), 1)
        self.assertEqual(replaced_doc['price_history'][0]['price_total'], 200000)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_save_listings_url_replace.py -v`
Expected: FAIL — `replaced_doc` has no `listing_status` key at all (dropped by blind replace)

- [ ] **Step 3: Write minimal implementation**

Replace `Project/Application/main.py` lines 492-499 (the `existing_by_url` block):

```python
            existing_by_url = collection.find_one({"url": listing.url})

            if existing_by_url:
                listing_dict['_id'] = existing_by_url['_id']
                listing_dict['listing_status'] = existing_by_url.get('listing_status', 'active')
                listing_dict['taken_at'] = existing_by_url.get('taken_at')

                old_price = existing_by_url.get('price_total')
                new_price = listing_dict.get('price_total')
                price_history = list(existing_by_url.get('price_history', []))
                if new_price is not None and old_price is not None and new_price != old_price:
                    from datetime import datetime
                    price_history.append({'price_total': old_price, 'recorded_at': datetime.utcnow()})
                listing_dict['price_history'] = price_history

                collection.replace_one({"_id": existing_by_url['_id']}, listing_dict)
                duplicate_count += 1
                logging.debug(f"🔄 Updated existing listing: {listing.title}")
                _persist_profile_scores(mongodb_handler, listing_dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_save_listings_url_replace.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```
git add Project/Application/main.py Project/Tests/test_save_listings_url_replace.py
git commit -m "fix(dedup): stop replace_one from silently dropping listing_status/taken_at/price_history"
```

---

### Task 5: `seller_type` classification, extracted from `contact_extractor.py`

**Files:**
- Read: `Project/Application/outreach/contact_extractor.py` (lines ~180-260, existing agency/makler regex)
- Modify: `Project/Application/outreach/contact_extractor.py` (add `classify_seller` function)
- Modify: `Project/Domain/listing.py` (add `seller_type: Optional[str] = None` field, after `coop_kind` around line 82)
- Modify: `Project/Application/scraping/willhaben_scraper.py` (call `classify_seller`, near existing `doppelmakler`/`maklerprovision_pct` calls at lines 545-546)
- Test: `Project/Tests/test_classify_seller.py` (new)

- [ ] **Step 1: Read the existing agency-detection regex before writing the test**

Run: `sed -n '180,260p' Project/Application/outreach/contact_extractor.py` and note the exact regex/class patterns used for `agency_name` detection — the test fixtures in Step 2 must use text that actually matches those patterns, not invented text.

- [ ] **Step 2: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.outreach.contact_extractor import classify_seller


class TestClassifySeller(unittest.TestCase):
    def test_private_seller_no_agency_markers(self):
        text = "Verkaufe meine Wohnung, Provisionsfrei, direkt vom Eigentümer."
        self.assertEqual(classify_seller(text, doppelmakler=None), 'private')

    def test_agency_seller(self):
        text = "Ihr Ansprechpartner: Max Mustermann, Immobilienmakler bei ImmoAT GmbH."
        self.assertEqual(classify_seller(text, doppelmakler=None), 'agency')

    def test_doppelmakler_true_forces_agency(self):
        # doppelmakler (dual-agent representation) always implies an agency is involved
        text = "Verkaufe meine Wohnung, Provisionsfrei."
        self.assertEqual(classify_seller(text, doppelmakler=True), 'agency')

    def test_no_signal_returns_unknown(self):
        self.assertEqual(classify_seller("", doppelmakler=None), 'unknown')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_classify_seller.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify_seller'`

- [ ] **Step 4: Write minimal implementation**

Add to `Project/Application/outreach/contact_extractor.py` (reuse the exact regex read in Step 1 — do not invent new patterns; the code block below assumes the existing agency regex is `re.compile(r'agency|makler', re.I)`, adjust to match what Step 1 actually found):

```python
import re


def classify_seller(text: str, doppelmakler: "bool | None" = None) -> str:
    """Classify private / agency / unknown from ad text + the doppelmakler flag.
    doppelmakler=True always implies agency (dual-agent representation requires one).
    Reuses the same agency/makler marker vocabulary as the HTML-scraping path
    above, applied to plain text instead of a BeautifulSoup element."""
    if doppelmakler:
        return 'agency'
    if not text:
        return 'unknown'
    lowered = text.lower()
    if re.search(r'makler|agentur|immobilien\s*gmbh|ansprechpartner', lowered):
        return 'agency'
    if re.search(r'privat|provisionsfrei|vom\s+eigent(ü|u)mer|direkt\s+vom\s+besitzer', lowered):
        return 'private'
    return 'unknown'
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_classify_seller.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Add `seller_type` field to the Listing model**

Modify `Project/Domain/listing.py`, add after the `coop_kind` field (line ~82):

```python
    seller_type:             Optional[str]   = None   # 'private' | 'agency' | 'unknown' — classify_seller()
```

- [ ] **Step 7: Wire into willhaben_scraper.py**

Modify `Project/Application/scraping/willhaben_scraper.py` near lines 545-546 (`listing.doppelmakler = ...` / `listing.maklerprovision_pct = ...`), add directly after:

```python
        from Application.outreach.contact_extractor import classify_seller
        listing.seller_type = classify_seller(_combined, doppelmakler=listing.doppelmakler)
```

- [ ] **Step 8: Run full test suite to check for regressions**

Run: `cd Project/Tests && python run_tests.py`
Expected: all pass, count increased by the 4 new `test_classify_seller.py` tests

- [ ] **Step 9: Commit**

```
git add Project/Application/outreach/contact_extractor.py Project/Domain/listing.py Project/Application/scraping/willhaben_scraper.py Project/Tests/test_classify_seller.py
git commit -m "feat(seller-type): classify private/agency at scrape time, write seller_type to the listing doc"
```

---

### Task 6: `coordinate_precision_m` field

**Files:**
- Modify: `Project/Domain/listing.py` (add `coordinate_precision_m: Optional[int] = None`, after `coordinate_source` at line 46)
- Modify: `Project/Application/helpers/geocoding.py` (set precision in `geocode_listing`, lines 525-563)
- Test: `Project/Tests/test_geocode_precision.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Application.helpers.geocoding import geocode_listing


class TestGeocodePrecision(unittest.TestCase):
    def test_exact_source_sets_10m_precision(self):
        listing = {"coordinates": {"lat": 48.2, "lon": 16.3}, "coordinate_source": "exact"}
        result = geocode_listing(listing)
        self.assertEqual(result['coordinate_precision_m'], 10)

    def test_landmark_source_sets_200m_precision(self):
        listing = {"coordinates": {"lat": 48.2, "lon": 16.3}, "coordinate_source": "landmark"}
        result = geocode_listing(listing)
        self.assertEqual(result['coordinate_precision_m'], 200)

    def test_none_source_sets_null_precision(self):
        listing = {"coordinate_source": "none"}
        result = geocode_listing(listing)
        self.assertIsNone(result['coordinate_precision_m'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_geocode_precision.py -v`
Expected: FAIL — `coordinate_precision_m` key missing from result

- [ ] **Step 3: Write minimal implementation**

Modify `Project/Application/helpers/geocoding.py`, `geocode_listing` function (lines 525-563). The function currently returns early in 3 places (already-geocoded skip, exact match, landmark match, none-found). Add precision at each return point:

```python
def geocode_listing(listing: Dict) -> Dict:
    from .landmark_extractor import extract_landmark_hint

    coordinates = listing.get('coordinates')
    coordinate_source = listing.get('coordinate_source')

    if coordinate_source in ('exact', 'landmark'):
        listing['coordinate_precision_m'] = 10 if coordinate_source == 'exact' else 200
        return listing

    geocoder = ViennaGeocoder()

    address = listing.get('address')
    if address:
        coords = geocoder.geocode_address(address)
        if coords:
            listing['coordinates'] = {'lat': coords.lat, 'lon': coords.lon}
            listing['coordinate_source'] = 'exact'
            listing['coordinate_precision_m'] = 10
            return listing

    title = listing.get('title', '') or ''
    hint = extract_landmark_hint(title)
    if hint:
        coords = geocoder.geocode_address(hint)
        if coords:
            listing['coordinates'] = {'lat': coords.lat, 'lon': coords.lon}
            listing['coordinate_source'] = 'landmark'
            listing['coordinate_precision_m'] = 200
            listing['landmark_hint'] = hint.replace(', Wien, Austria', '')
            return listing

    listing['coordinate_source'] = 'none'
    listing['coordinate_precision_m'] = None
    return listing
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Project && python -m pytest Tests/test_geocode_precision.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Add the field to the Listing model**

Modify `Project/Domain/listing.py`, after `coordinate_source` (line 46):

```python
    coordinate_precision_m: Optional[int] = None  # 10=exact, 200=landmark-guess, None=no coords
```

- [ ] **Step 6: Do NOT gate school/U-Bahn calc here — verified dead code, flagging instead**

Traced the actual call graph: `Application/main.py:normalize_listing_schema` (lines 412-419) is the
*only* live setter of `school_walk_minutes`/`ubahn_walk_minutes`, and it always uses the static
per-district table `get_walking_times()` (`Application/helpers/utils.py:608`) — a hardcoded
district→minutes dict, not a per-coordinate calculation. The methods that DO compute a real
per-address distance from geocoded coordinates — `WillhabenScraper.get_amenities` and
`get_real_ubahn_walk_minutes` (`willhaben_scraper.py:1744`/`1764`), which call
`ViennaGeocoder.get_walking_distance_to_nearest_school`/`_ubahn` — have **zero callers** anywhere in
the codebase (verified via `grep -rn "\.get_amenities(\|\.get_real_ubahn_walk_minutes(" Project --include="*.py"`,
no hits outside the definitions). So today, in production, every listing's school/U-Bahn walk time is
a static per-district guess regardless of `coordinate_source` — there is no real per-listing
calculation to gate on `exact` vs `landmark`.

This is bigger than a gating tweak: wiring the already-written but orphaned `get_amenities`/
`get_real_ubahn_walk_minutes` methods into the live scrape path (replacing the static-table fallback
with a real per-coordinate calc when `coordinate_source == 'exact'`, falling back to the static table
only when precision is worse) is real, valuable work directly matching your original ask — but it
touches the scraper's control flow, not just data plumbing, and deserves its own reviewed task rather
than a rushed addition here. **Not implemented in this plan** — tracked as the first item in Task 7
(follow-up) below.

- [ ] **Step 7: Run full test suite**

Run: `cd Project/Tests && python run_tests.py`
Expected: all pass, no drop from baseline

- [ ] **Step 8: Commit**

```
git add Project/Domain/listing.py Project/Application/helpers/geocoding.py Project/Tests/test_geocode_precision.py
git commit -m "feat(geo): add coordinate_precision_m field (10=exact, 200=landmark-guess, null=none)"
```

---

### Task 7: Follow-up items (not implemented in this plan — flag and stop)

Discovered during Task 6 that are real but out of this plan's bite-sized scope:

1. **Wire real per-address school/U-Bahn distance calc into the live path.** `WillhabenScraper.get_amenities`/`get_real_ubahn_walk_minutes` already implement this correctly using `ViennaGeocoder`, but nothing calls them — replace them, or reuse `get_walking_distance_to_nearest_school`/`_ubahn` from `geocoding.py` directly in `normalize_listing_schema`, gated on `coordinate_source == 'exact'`, falling back to the static per-district table (`get_walking_times`) otherwise. This is the change that actually delivers "distance between schools/U-Bahn and that location" from your original request — Task 6 only added the metadata field to make the current static-guess vs future real-calc distinguishable.
2. Sub-project 3 from the spec (extractor coverage-consistency audit: `doppelmakler`/`maklerprovision_pct`/`sonderumlage_risk` call-site gaps across scrapers).
3. Sub-project 4/5 from the spec (`district_snapshots` monthly rollup + external 10yr backfill) — explicitly deferred per your answer.

---

## Coverage measurement (test_scope: true)

- [ ] **Step 1:** Before Task 1, record baseline: `cd Project && python -m pytest --cov=Application --cov=Integration --cov-report=term-missing Tests/ 2>&1 | tail -5`
- [ ] **Step 2:** After Task 6, re-run the same command and confirm coverage did not drop from baseline.

## Final verification

- [ ] Run `cd Project/Tests && python run_tests.py` — full suite green.
- [ ] Run `cd Project && python -m pytest Tests/ -v 2>&1 | tail -20` — confirm all 6 new test files pass.
- [ ] Manually inspect one real scrape run's log (`Project/log/`) for the new `seller_type`/`coordinate_precision_m` fields appearing in saved documents, or run `python run.py --willhaben-only --quick-scan` against a local/staging Mongo and spot-check a few docs.
