# MyGEWO Parity — Phase A: Fast Poll + Instant Alerts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A lightweight GitHub Actions cron (`*/5`) that polls the Genossenschaft Bauträger adapters, upserts new units, and DMs matches to Telegram within ≤15 min of appearing — no Selenium, no scoring, no geocoding.

**Architecture:** New `Project/run_coop.py` runner iterates the existing coop adapter registry with conditional-GET politeness (ETag/Last-Modified/page-hash from a new `source_meta` collection), upserts via a new price-less `MongoDBHandler.upsert_coop_listing()` (co-op listings often have no purchase price), then alerts on units that are unsent AND pass an optional `coop_alerts` filter. The daily full-scrape workflow (`scrapeJob.yml`) is untouched; the existing `coop-scrape.yml` is **replaced** by the new `coop-fast-poll.yml`.

**Tech Stack:** Python 3.11, `requests` + `beautifulsoup4` (already deps), `pymongo`, GitHub Actions cron. Tests: `unittest` + `unittest.mock`, run via `pytest`.

---

## Decisions locked (from spec + pre-flight grill)

| Topic | Decision |
|---|---|
| Existing `coop-scrape.yml` | **Replace** with `coop-fast-poll.yml` (user-confirmed). Single coop poll path → no double-send races. |
| Poll schedule | `*/5 6-20 * * 1-6` (user-confirmed) — every 5 min, ~8–22 Vienna, Mon–Sat. |
| Alert gating | Config filter only (`coop_alerts`), NO score gate. Missing/empty filter field = no constraint. Missing **listing** field = permissive (never excludes). |
| Send target | `TELEGRAM_COOP_CHANNEL_ID`, fallback `TELEGRAM_MAIN_CHAT_ID`. |
| Persistence | Lean upsert only (validation + xsrc dedup + url upsert). No geocoding/scoring in fast path — the daily job enriches; map uses bezirk-centroid fallback (pre-existing behavior). |

## Assumptions / deviations from the spec (flagged)

1. **`coop_alerts` lives in a tracked `Project/coop_alerts.json`, not `config.json`.** `config.json` is gitignored and absent in CI (GH Actions), so a `coop_alerts` key there would never apply to the CI poll. The filter contains no secrets (bezirke/price/rooms/area), so a tracked file is the correct CI-visible source. Precedence in `load_coop_alerts()`: `COOP_ALERTS` env (JSON) > `config.json` `coop_alerts` key > `Project/coop_alerts.json` > `{}` (send all).
2. **`format_coop_message` is extracted from `Application/main.py` into a new light module** so `run_coop.py` never imports the heavy `main.py`. `main.py` keeps identical behavior via an import.
3. **`upsert_coop_listing` preserves `sent_to_telegram` / `sent_to_telegram_at` on re-poll.** A `*/5` poll re-sees the same listing constantly; a naive `replace_one` (as in `save_listings_to_mongodb`) would reset the sent flag and re-spam every 5 minutes. This is a latent bug in the existing daily path; the coop method fixes it for the coop path.
4. **`source` (a plain `Enum`) is stringified before upsert** — verified `asdict(coop_listing)['source']` is a `Source` enum that raises `InvalidDocument` under BSON encoding.
5. **`ui_scope: true` from the spec applies to Phase C** (dashboard filters) — not this plan. This plan honors `test_scope: true` (Task 8, coverage).

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `Project/Application/coop_format.py` | **Create** | `format_coop_message(l: Listing) -> str` (moved from main.py). |
| `Project/Application/main.py` | Modify (`406-422`, `21-25`) | Delete the local `format_coop_message` def; import it from `coop_format`. |
| `Project/Integration/mongodb_handler.py` | Modify (add methods) | `get_source_meta`, `set_source_meta`, `upsert_coop_listing`. |
| `Project/coop_alerts.json` | **Create** (tracked) | Default filter `{}`-equivalent (send all). |
| `Project/run_coop.py` | **Create** | Runner: poll → upsert → filter → notify. `--dry-run`. ≤200 lines. |
| `.github/workflows/coop-fast-poll.yml` | **Create** | cron `*/5 6-20 * * 1-6` → `python run_coop.py`. |
| `.github/workflows/coop-scrape.yml` | **Delete** (`git rm`) | Replaced by fast-poll (user-authorized). |
| `Project/Tests/test_coop_format.py` | **Create** | Message formatting test. |
| `Project/Tests/test_source_meta.py` | **Create** | source_meta round-trip (mocked collection). |
| `Project/Tests/test_upsert_coop.py` | **Create** | upsert validation / dedup / send-state preservation (mocked collection). |
| `Project/Tests/test_run_coop.py` | **Create** | `matches_coop_alerts`, `load_coop_alerts`, `conditional_fetch` (mocked). |
| `docs/CLAUDE-full-reference.md` | Modify (append) | Document `coop_alerts` schema + `run_coop.py` + workflow change. |

---

## Task 1: Extract `format_coop_message` into a light module

**Files:**
- Create: `Project/Application/coop_format.py`
- Modify: `Project/Application/main.py` (delete def at `406-422`, add import near `21-25`)
- Test: `Project/Tests/test_coop_format.py`

- [ ] **Step 1: Write the failing test**

Create `Project/Tests/test_coop_format.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Domain.listing import Listing
from Domain.sources import Source
from Application.coop_format import format_coop_message


def _coop(**kw):
    return Listing(url=kw.pop('url', 'https://www.oevw.at/x'),
                   source=Source.GENOSSENSCHAFT, is_genossenschaft=True,
                   bautraeger=kw.pop('bautraeger', 'ÖVW'), **kw)


class TestFormatCoopMessage(unittest.TestCase):
    def test_html_bold_and_ppm2(self):
        msg = format_coop_message(_coop(bezirk='1100', rooms=3, area_m2=70, price_total=350))
        self.assertIn('<b>ÖVW</b>', msg)
        self.assertIn('5.0€/m²', msg)          # 350/70
        self.assertIn('#1100', msg)
        self.assertIn('https://www.oevw.at/x', msg)

    def test_escapes_html_in_free_text(self):
        msg = format_coop_message(_coop(bautraeger='A & B <Bau>'))
        self.assertIn('A &amp; B', msg)
        self.assertNotIn('<Bau>', msg)

    def test_missing_fields_use_placeholders(self):
        msg = format_coop_message(_coop(bautraeger=None, bezirk=None))
        self.assertIn('Genossenschaft', msg)
        self.assertIn('? Zi', msg)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_coop_format.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'Application.coop_format'`

- [ ] **Step 3: Create the module (move the function verbatim)**

Create `Project/Application/coop_format.py`:

```python
"""Formatting for co-op (Genossenschaft) Telegram alerts. Kept separate from
Application.main so lightweight runners (run_coop.py) don't import the heavy
scrape orchestration just to format a message."""
import html
from Domain.listing import Listing


def format_coop_message(l: Listing) -> str:
    """Format a co-op (Genossenschaft) listing as an HTML Telegram message.

    parse_mode defaults to "HTML" in TelegramBot.send_message, so tags are
    <b>...</b> here (not Markdown *...*) to actually render as intended.
    Scraped free-text fields (bautraeger, bezirk) are HTML-escaped since
    Telegram's HTML parser rejects unescaped &/</> in the message body."""
    bautraeger = html.escape(l.bautraeger) if l.bautraeger else None
    bezirk = html.escape(l.bezirk) if l.bezirk else None
    url = html.escape(l.url, quote=False) if l.url else ''
    ppm2 = f"{l.price_total / l.area_m2:.1f}€/m²" if (l.price_total and l.area_m2) else "–"
    tags = " ".join(t for t in [f"#{bezirk}" if bezirk else None,
                                f"#{bautraeger}" if bautraeger else None] if t)
    return (f"🏢 <b>{bautraeger or 'Genossenschaft'}</b> — {bezirk or ''}\n"
            f"{l.rooms or '?'} Zi · {l.area_m2 or '?'} m² · {ppm2}\n"
            f"Vergabe: {l.allocation_model or 'first_come'}\n"
            f"{url}\n{tags}")
```

- [ ] **Step 4: Update `main.py` to import instead of defining**

In `Project/Application/main.py`, delete the whole `def format_coop_message(l: Listing) -> str:` block (currently lines `406-422`, ending at the `f"{url}\n{tags}")` return).

Then add this import next to the other `Application.*` imports near line 25 (after `from Application.feasibility import derive_profile_fields`):

```python
from Application.coop_format import format_coop_message
```

Leave every existing call site (`format_coop_message(listing)` around line 853) unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_coop_format.py -q`
Expected: PASS (3 passed)

Run (regression — main still imports cleanly):
`cd Project && python -c "import Application.main"` → **NOTE: `python -c` is denied in this environment.** Instead run:
`cd Project && python -m pytest Tests/test_coop_format.py Tests/test_bank_scoring.py -q`
Expected: PASS (imports resolve; no `ImportError` for `format_coop_message`).

- [ ] **Step 6: Commit**

```bash
git add Project/Application/coop_format.py Project/Application/main.py Project/Tests/test_coop_format.py
git commit -m "refactor(coop): extract format_coop_message into light module"
```

---

## Task 2: `source_meta` handler methods (conditional-GET storage)

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (add two methods to `MongoDBHandler`)
- Test: `Project/Tests/test_source_meta.py`

- [ ] **Step 1: Write the failing test**

Create `Project/Tests/test_source_meta.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler_with_fake_meta():
    h = MongoDBHandler.__new__(MongoDBHandler)   # bypass __init__ (no DB)
    h.client = MagicMock()
    h.db = MagicMock()
    h.source_meta_collection = MagicMock()
    return h


class TestSourceMeta(unittest.TestCase):
    def test_get_returns_empty_when_absent(self):
        h = _handler_with_fake_meta()
        h.source_meta_collection.find_one.return_value = None
        self.assertEqual(h.get_source_meta("ÖVW"), {})

    def test_get_strips_mongo_internals(self):
        h = _handler_with_fake_meta()
        h.source_meta_collection.find_one.return_value = {
            "_id": 1, "source": "ÖVW", "etag": "abc",
            "last_modified": "Mon", "page_hash": "h1"}
        self.assertEqual(h.get_source_meta("ÖVW"),
                         {"etag": "abc", "last_modified": "Mon", "page_hash": "h1"})

    def test_set_upserts_by_source(self):
        h = _handler_with_fake_meta()
        h.set_source_meta("ÖVW", etag="abc", last_modified="Mon", page_hash="h1")
        args, kwargs = h.source_meta_collection.update_one.call_args
        self.assertEqual(args[0], {"source": "ÖVW"})
        self.assertEqual(args[1]["$set"],
                         {"etag": "abc", "last_modified": "Mon", "page_hash": "h1"})
        self.assertTrue(kwargs.get("upsert"))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_source_meta.py -q`
Expected: FAIL — `AttributeError: 'MongoDBHandler' object has no attribute 'source_meta_collection'` / `get_source_meta`.

- [ ] **Step 3: Add the `source_meta_collection` and two methods**

In `Project/Integration/mongodb_handler.py`, inside `__init__`, next to the other collection assignments (after `self.outreach_collection = self.db["outreach_jobs"]`, ~line 72), add:

```python
            self.source_meta_collection = self.db["source_meta"]
```

Then add these two methods to the `MongoDBHandler` class (place them right after `mark_url_invalid`, ~line 435):

```python
    def get_source_meta(self, source: str) -> Dict:
        """Conditional-GET metadata for a coop adapter: {etag, last_modified, page_hash}.
        Returns {} when unknown or on error (caller then does an unconditional GET)."""
        try:
            doc = self.source_meta_collection.find_one({"source": source})
            if not doc:
                return {}
            return {k: doc.get(k) for k in ("etag", "last_modified", "page_hash")
                    if doc.get(k) is not None}
        except Exception as e:
            logging.warning(f"get_source_meta({source}) failed: {e}")
            return {}

    def set_source_meta(self, source: str, etag: Optional[str] = None,
                        last_modified: Optional[str] = None,
                        page_hash: Optional[str] = None) -> None:
        """Upsert conditional-GET metadata for a coop adapter. Only non-None
        fields are written, so a 304 (no new headers) never clobbers a good ETag."""
        try:
            update = {k: v for k, v in
                      (("etag", etag), ("last_modified", last_modified),
                       ("page_hash", page_hash)) if v is not None}
            if not update:
                return
            self.source_meta_collection.update_one(
                {"source": source}, {"$set": update}, upsert=True)
        except Exception as e:
            logging.warning(f"set_source_meta({source}) failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_source_meta.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add Project/Integration/mongodb_handler.py Project/Tests/test_source_meta.py
git commit -m "feat(coop): source_meta collection + get/set for conditional GET"
```

---

## Task 3: `upsert_coop_listing` handler method (price-less coop upsert)

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` (add method)
- Test: `Project/Tests/test_upsert_coop.py`

Rationale: `insert_listing()` hard-rejects `price_total <= 0` (line 140), but co-op units often have no purchase price. This method mirrors the proven co-op branch in `save_listings_to_mongodb` (validation → xsrc dedup → url upsert → fingerprint dedup → insert) **minus** geocoding/profile-scoring, and **preserves send-state on update** so a `*/5` re-poll never resets `sent_to_telegram`.

- [ ] **Step 1: Write the failing test**

Create `Project/Tests/test_upsert_coop.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock
from Integration.mongodb_handler import MongoDBHandler


def _handler():
    h = MongoDBHandler.__new__(MongoDBHandler)
    h.client = MagicMock()
    h.collection = MagicMock()
    return h


def _doc(**kw):
    d = {"url": "https://www.oevw.at/a", "source": "genossenschaft",
         "source_enum": "genossenschaft", "is_genossenschaft": True,
         "bezirk": "1100", "rooms": 3, "area_m2": 70.0,
         "price_total": None, "coop_source": "bautraeger_direct",
         "bautraeger": "ÖVW"}
    d.update(kw)
    return d


class TestUpsertCoopListing(unittest.TestCase):
    def test_inserts_new_listing_without_price(self):
        h = _handler()
        h.collection.find_one.return_value = None       # no xsrc, no url, no fp match
        status = h.upsert_coop_listing(_doc())
        self.assertEqual(status, "inserted")
        h.collection.insert_one.assert_called_once()

    def test_update_preserves_send_state(self):
        h = _handler()
        # first find_one (xsrc) -> None; second (by url) -> existing sent doc
        h.collection.find_one.side_effect = [
            None,
            {"_id": 42, "url": "https://www.oevw.at/a",
             "sent_to_telegram": True, "sent_to_telegram_at": 111.0},
        ]
        status = h.upsert_coop_listing(_doc())
        self.assertEqual(status, "updated")
        replaced = h.collection.replace_one.call_args[0][1]
        self.assertTrue(replaced["sent_to_telegram"])           # not reset!
        self.assertEqual(replaced["sent_to_telegram_at"], 111.0)
        self.assertEqual(replaced["_id"], 42)

    def test_rejects_invalid_by_price_per_m2(self):
        h = _handler()
        # price_per_m2 = 10,000,000 — above any realistic GLOBAL_VALIDATION
        # max (robust regardless of the exact min, which could be 0).
        status = h.upsert_coop_listing(_doc(price_total=10_000_000.0, area_m2=1.0))
        self.assertEqual(status, "invalid")
        h.collection.insert_one.assert_not_called()


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_upsert_coop.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'upsert_coop_listing'`

- [ ] **Step 3: Add the method**

In `Project/Integration/mongodb_handler.py`, add this method to `MongoDBHandler` right after `insert_listing` (~line 209). `is_valid_listing_data`, `compute_xsrc_fingerprint`, `compute_content_fingerprint`, and `SimpleNamespace` are already imported at module top.

```python
    def upsert_coop_listing(self, listing: Dict) -> str:
        """Upsert a co-op listing WITHOUT the price>0 gate (co-op units often
        have no purchase price). Mirrors the co-op branch of
        save_listings_to_mongodb (validation → xsrc dedup → url upsert →
        fingerprint dedup → insert) minus geocoding/scoring.

        Preserves send-state on update so a */5 re-poll never resets
        sent_to_telegram and re-spams. Returns one of:
        "inserted" | "updated" | "duplicate" | "invalid" | "error"."""
        if self.collection is None:
            return "error"
        valid, reason = is_valid_listing_data(listing)
        if not valid:
            logging.info(f"🚫 coop upsert skipped — {reason}")
            return "invalid"
        try:
            # Cross-source dedup (Willhaben ↔ Bauträger-direct for one unit).
            if listing.get('is_genossenschaft'):
                xfp = compute_xsrc_fingerprint(SimpleNamespace(**listing))
                if xfp:
                    listing['content_fingerprint_xsrc'] = xfp
                    existing = self.collection.find_one({"content_fingerprint_xsrc": xfp})
                    if existing and existing.get('url') != listing.get('url'):
                        if (listing.get('coop_source') == 'bautraeger_direct'
                                and existing.get('coop_source') == 'willhaben'):
                            self.collection.update_one(
                                {"_id": existing["_id"]},
                                {"$set": {
                                    "url": listing.get('url'),
                                    "coop_source": 'bautraeger_direct',
                                    "bautraeger": listing.get('bautraeger'),
                                }})
                        logging.info(f"🚫 coop xsrc duplicate: {xfp}")
                        return "duplicate"

            listing['content_fingerprint'] = compute_content_fingerprint(listing)

            existing_by_url = self.collection.find_one({"url": listing.get('url')})
            if existing_by_url:
                listing['_id'] = existing_by_url['_id']
                # NEVER reset send-state on re-poll → no 5-minute re-spam.
                for k in ("sent_to_telegram", "sent_to_telegram_at", "url_is_valid"):
                    if k in existing_by_url:
                        listing[k] = existing_by_url[k]
                self.collection.replace_one({"_id": existing_by_url['_id']}, listing)
                return "updated"

            source_enum = listing.get('source_enum', listing.get('source', ''))
            existing_by_fp = self.collection.find_one(
                {"content_fingerprint": listing['content_fingerprint'],
                 "source_enum": source_enum})
            if existing_by_fp:
                logging.info(f"🚫 coop fingerprint duplicate: {listing.get('url')}")
                return "duplicate"

            self.collection.insert_one(listing)
            return "inserted"
        except Exception as e:
            logging.error(f"upsert_coop_listing error: {e}")
            return "error"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_upsert_coop.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add Project/Integration/mongodb_handler.py Project/Tests/test_upsert_coop.py
git commit -m "feat(coop): price-less upsert_coop_listing preserving send-state"
```

---

## Task 4: `coop_alerts` filter (tracked file + load + match)

**Files:**
- Create: `Project/coop_alerts.json`
- Create (partial): `Project/run_coop.py` — the pure `load_coop_alerts()` + `matches_coop_alerts()` functions only (orchestration added in Task 6)
- Test: `Project/Tests/test_run_coop.py` (filter cases)

- [ ] **Step 1: Write the failing test**

Create `Project/Tests/test_run_coop.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Domain.listing import Listing
from Domain.sources import Source
import run_coop


def _l(**kw):
    return Listing(url=kw.pop('url', 'https://x.at/a'), source=Source.GENOSSENSCHAFT,
                   is_genossenschaft=True, bezirk=kw.pop('bezirk', '1100'),
                   rooms=kw.pop('rooms', 3), area_m2=kw.pop('area_m2', 70.0),
                   price_total=kw.pop('price_total', None), **kw)


class TestMatchesCoopAlerts(unittest.TestCase):
    def test_empty_filter_sends_all(self):
        self.assertTrue(run_coop.matches_coop_alerts(_l(), {}))

    def test_bezirk_include_and_exclude(self):
        self.assertTrue(run_coop.matches_coop_alerts(_l(bezirk='1100'), {"bezirke": ["1100", "1200"]}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(bezirk='1010'), {"bezirke": ["1100"]}))

    def test_missing_listing_field_is_permissive(self):
        # filter wants min_rooms=3 but listing has unknown rooms -> included
        self.assertTrue(run_coop.matches_coop_alerts(_l(rooms=None), {"min_rooms": 3}))
        # filter wants a bezirk but listing has none -> included
        self.assertTrue(run_coop.matches_coop_alerts(_l(bezirk=None), {"bezirke": ["1100"]}))

    def test_min_rooms_min_area_max_cost(self):
        self.assertFalse(run_coop.matches_coop_alerts(_l(rooms=2), {"min_rooms": 3}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(area_m2=40), {"min_area": 50}))
        self.assertFalse(run_coop.matches_coop_alerts(_l(price_total=500), {"max_cost": 400}))
        self.assertTrue(run_coop.matches_coop_alerts(_l(rooms=3, area_m2=70, price_total=300),
                                                     {"min_rooms": 3, "min_area": 50, "max_cost": 400}))


class TestLoadCoopAlerts(unittest.TestCase):
    def test_env_override_wins(self):
        os.environ["COOP_ALERTS"] = '{"min_rooms": 2}'
        try:
            self.assertEqual(run_coop.load_coop_alerts().get("min_rooms"), 2)
        finally:
            del os.environ["COOP_ALERTS"]

    def test_bad_env_falls_through_to_dict(self):
        os.environ["COOP_ALERTS"] = 'not-json'
        try:
            self.assertIsInstance(run_coop.load_coop_alerts(), dict)  # no crash
        finally:
            del os.environ["COOP_ALERTS"]


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_run_coop.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'run_coop'`

- [ ] **Step 3: Create the tracked default filter**

Create `Project/coop_alerts.json` (empty = send everything; the owner tunes by committing edits):

```json
{
  "bezirke": [],
  "max_cost": null,
  "min_rooms": null,
  "min_area": null
}
```

- [ ] **Step 4: Create `run_coop.py` with the pure functions only**

Create `Project/run_coop.py` (orchestration is added in Task 6 — this step introduces only the importable module + the two pure functions so the Task-4 tests pass):

```python
#!/usr/bin/env python3
"""Fast co-op poll → instant Telegram alerts.

Lightweight (requests + bs4, no Selenium, no scoring/geocoding): polls the
Genossenschaft Bauträger adapters, upserts new units, and DMs matches that
pass the coop_alerts filter. Built for GitHub Actions cron */5.

Run from Project/:  python run_coop.py [--dry-run]
"""
import json
import logging
import os

from Domain.listing import Listing
from Application.helpers.utils import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_coop")


def load_coop_alerts() -> dict:
    """Alert filter. Precedence: COOP_ALERTS env (JSON) > config.json coop_alerts
    > Project/coop_alerts.json > {} (send all). config.json is gitignored/absent
    in CI, so the tracked coop_alerts.json is the CI-visible source."""
    env = os.environ.get("COOP_ALERTS")
    if env:
        try:
            data = json.loads(env)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            logger.warning("COOP_ALERTS env is not valid JSON; ignoring")
    cfg = load_config() or {}
    if isinstance(cfg.get("coop_alerts"), dict):
        return cfg["coop_alerts"]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coop_alerts.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def matches_coop_alerts(listing: Listing, alerts: dict) -> bool:
    """True if the listing passes the (optional) alert filter. Empty/missing
    filter field = no constraint. Missing LISTING field = permissive (never
    excludes) — for a single power-user, speed/coverage beats precision."""
    bezirke = alerts.get("bezirke") or []
    if bezirke and listing.bezirk and listing.bezirk not in bezirke:
        return False
    max_cost = alerts.get("max_cost")
    if max_cost is not None and listing.price_total is not None and listing.price_total > max_cost:
        return False
    min_rooms = alerts.get("min_rooms")
    if min_rooms is not None and listing.rooms is not None and listing.rooms < min_rooms:
        return False
    min_area = alerts.get("min_area")
    if min_area is not None and listing.area_m2 is not None and listing.area_m2 < min_area:
        return False
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_run_coop.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add Project/coop_alerts.json Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "feat(coop): coop_alerts filter (tracked file + load + match)"
```

---

## Task 5: Conditional-GET fetch helper

**Files:**
- Modify: `Project/run_coop.py` (add `_page_hash`, `conditional_fetch`)
- Test: `Project/Tests/test_run_coop.py` (append conditional-GET cases)

- [ ] **Step 1: Write the failing test (append to `test_run_coop.py`)**

Add this class to `Project/Tests/test_run_coop.py` (above the `if __name__` guard):

```python
from unittest.mock import MagicMock


def _resp(status=200, text="<html>body</html>", etag=None, last_modified=None):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.headers = {}
    if etag:
        r.headers["ETag"] = etag
    if last_modified:
        r.headers["Last-Modified"] = last_modified
    r.raise_for_status = MagicMock()
    return r


class TestConditionalFetch(unittest.TestCase):
    def test_304_reports_unchanged(self):
        sess = MagicMock()
        sess.get.return_value = _resp(status=304)
        changed, html, meta = run_coop.conditional_fetch(
            "https://x.at", {"etag": "e1"}, session=sess)
        self.assertFalse(changed)
        self.assertIsNone(html)
        # If-None-Match sent
        self.assertEqual(sess.get.call_args.kwargs["headers"]["If-None-Match"], "e1")

    def test_same_hash_reports_unchanged(self):
        sess = MagicMock()
        sess.get.return_value = _resp(text="<html>same</html>")
        prev = {"page_hash": run_coop._page_hash("<html>same</html>")}
        changed, html, meta = run_coop.conditional_fetch("https://x.at", prev, session=sess)
        self.assertFalse(changed)

    def test_new_body_reports_changed_with_new_meta(self):
        sess = MagicMock()
        sess.get.return_value = _resp(text="<html>fresh</html>", etag="e2", last_modified="Mon")
        changed, html, meta = run_coop.conditional_fetch("https://x.at", {}, session=sess)
        self.assertTrue(changed)
        self.assertEqual(html, "<html>fresh</html>")
        self.assertEqual(meta["etag"], "e2")
        self.assertEqual(meta["last_modified"], "Mon")
        self.assertEqual(meta["page_hash"], run_coop._page_hash("<html>fresh</html>"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_run_coop.py::TestConditionalFetch -q`
Expected: FAIL — `AttributeError: module 'run_coop' has no attribute 'conditional_fetch'`

- [ ] **Step 3: Add the helpers to `run_coop.py`**

Add `import hashlib` and `import requests` and `from typing import Optional, Tuple, List` to the imports of `Project/run_coop.py`, then add:

```python
_UA = {"User-Agent": "Mozilla/5.0 (compatible; immo-scouter-coop/1.0; +alerts)"}


def _page_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def conditional_fetch(url: str, meta: dict, session=requests) -> Tuple[bool, Optional[str], dict]:
    """Conditional GET. Returns (changed, html, new_meta).

    changed=False when the server returns 304 OR the body hash matches the
    stored one — caller then skips parsing. new_meta carries etag/last_modified/
    page_hash to persist (empty on 304 so a good stored ETag isn't clobbered)."""
    headers = dict(_UA)
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    resp = session.get(url, headers=headers, timeout=20)
    if resp.status_code == 304:
        return False, None, {}
    resp.raise_for_status()
    new_hash = _page_hash(resp.text)
    new_meta = {
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "page_hash": new_hash,
    }
    if meta.get("page_hash") and new_hash == meta["page_hash"]:
        return False, None, new_meta
    return True, resp.text, new_meta
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_run_coop.py -q`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "feat(coop): conditional-GET fetch (ETag/Last-Modified/page-hash)"
```

---

## Task 6: `run_coop.py` orchestration + CLI

**Files:**
- Modify: `Project/run_coop.py` (add `_to_doc`, `poll_source`, `run`, `main`/CLI)
- Test: `Project/Tests/test_run_coop.py` (append `poll_source` skip-on-unchanged test); live smoke via `--dry-run`

- [ ] **Step 1: Write the failing test (append to `test_run_coop.py`)**

Add this class:

```python
class TestPollSource(unittest.TestCase):
    def test_skips_parse_when_unchanged(self):
        handler = MagicMock()
        handler.get_source_meta.return_value = {"etag": "e1"}
        sess = MagicMock()
        sess.get.return_value = _resp(status=304)
        cfg = {"url": "https://x.at", "parser": "parse_oevw"}
        out = run_coop.poll_source("ÖVW", cfg, handler, session=sess)
        self.assertEqual(out, [])
        # A pure 304 carries no new headers → conditional_fetch returns {} →
        # existing stored meta is kept, so set_source_meta is NOT called.
        handler.set_source_meta.assert_not_called()

    def test_to_doc_stringifies_source_enum(self):
        from Domain.sources import Source
        d = run_coop._to_doc(_l(area_m2=70.0, price_total=350.0))
        self.assertEqual(d["source"], "genossenschaft")       # not the Enum
        self.assertEqual(d["source_enum"], "genossenschaft")
        self.assertAlmostEqual(d["price_per_m2"], 5.0)        # 350/70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Project && python -m pytest Tests/test_run_coop.py::TestPollSource -q`
Expected: FAIL — `AttributeError: module 'run_coop' has no attribute 'poll_source'`

- [ ] **Step 3: Add orchestration to `run_coop.py`**

Add these imports at the top of `Project/run_coop.py`:

```python
import argparse
from dataclasses import asdict

from Domain.sources import Source
from Application.scraping import genossenschaft_scraper as coop
from Application.coop_format import format_coop_message
from Application.helpers.listing_validator import validate_url
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot
```

Then append:

```python
def _to_doc(listing: Listing) -> dict:
    """Listing → BSON-safe dict. Source is a plain Enum (verified not
    BSON-encodable), so stringify it. price_per_m2 filled when derivable."""
    d = asdict(listing)
    d["source"] = listing.source.value if hasattr(listing.source, "value") else listing.source
    d["source_enum"] = Source.GENOSSENSCHAFT.value
    if listing.price_total and listing.area_m2 and not d.get("price_per_m2"):
        d["price_per_m2"] = listing.price_total / listing.area_m2
    return d


def poll_source(name: str, cfg: dict, handler, session=requests) -> List[Listing]:
    """Fetch one adapter with conditional GET; parse only when the page changed."""
    meta = handler.get_source_meta(name) or {}
    changed, html_text, new_meta = conditional_fetch(cfg["url"], meta, session=session)
    if new_meta:
        handler.set_source_meta(name, **new_meta)
    if not changed:
        logger.info(f"↔️  {name}: unchanged, skipping parse")
        return []
    parser = getattr(coop, cfg["parser"])
    listings = parser(html_text)
    logger.info(f"🔍 {name}: {len(listings)} listing(s) parsed")
    return listings


def run(dry_run: bool = False) -> int:
    """Poll → upsert → alert. Exit 0 unless MongoDB is down or ALL adapters fail."""
    alerts = load_coop_alerts()
    handler = MongoDBHandler()
    if handler.collection is None:
        logger.error("❌ No MongoDB connection; aborting")
        return 1

    bot = None
    if not dry_run:
        token = os.environ.get("TELEGRAM_MAIN_BOT_TOKEN")
        chat_id = (os.environ.get("TELEGRAM_COOP_CHANNEL_ID")
                   or os.environ.get("TELEGRAM_MAIN_CHAT_ID"))
        if token and chat_id:
            bot = TelegramBot(token, chat_id)
        else:
            logger.warning("⚠️  Telegram not configured; running in no-send mode")

    seen: List[Listing] = []
    ok_adapters = 0
    for name, cfg in coop.SOURCES.items():
        try:
            seen.extend(poll_source(name, cfg, handler, session=requests))
            ok_adapters += 1
        except Exception as e:
            logger.error(f"❌ adapter {name} failed: {e}")

    if ok_adapters == 0:
        logger.error("❌ All adapters failed")
        handler.close()
        return 1

    for listing in seen:
        handler.upsert_coop_listing(_to_doc(listing))

    sent = 0
    for listing in seen:
        if not matches_coop_alerts(listing, alerts):
            continue
        doc = handler.get_listing(listing.url)
        if doc and doc.get("sent_to_telegram"):
            continue
        if not validate_url(listing.url):            # CLAUDE.md hard rule 2
            logger.warning(f"🚫 broken URL, skipping: {listing.url}")
            handler.mark_url_invalid(listing.url)
            continue
        if dry_run:
            logger.info(f"[dry-run] would alert: {listing.url}")
            sent += 1
            continue
        if bot and bot.send_message(format_coop_message(listing)):
            handler.mark_sent(listing.url)
            sent += 1
        elif bot:
            logger.error(f"❌ send failed (retry next run): {listing.url}")

    logger.info(f"📱 coop: {sent} alerted/queued from {len(seen)} seen "
                f"across {ok_adapters}/{len(coop.SOURCES)} adapters")
    handler.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Fast co-op poll → Telegram alerts")
    parser.add_argument("--dry-run", action="store_true", help="skip Telegram sends")
    args = parser.parse_args()
    raise SystemExit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `cd Project && python -m pytest Tests/test_run_coop.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Live smoke test (`--dry-run`, real adapters, no sends)**

Requires a real `MONGODB_URI` (see project memory: `vercel env pull` or local Atlas URI in env). Run:

```bash
cd Project && MONGODB_URI="<atlas-uri>" python run_coop.py --dry-run
```

Expected output includes, per adapter, either `🔍 <name>: N listing(s) parsed` or `↔️ <name>: unchanged`, and a final line `📱 coop: <n> alerted/queued from <m> seen across 3/3 adapters`. Exit code 0. No Telegram messages are sent (dry-run). If a live site changed its HTML and a parser yields 0, that is acceptable for the smoke (adapters are failure-isolated) — note it but do not block.

- [ ] **Step 6: Commit**

```bash
git add Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "feat(coop): run_coop.py orchestration — poll, upsert, alert, --dry-run"
```

---

## Task 7: Workflow swap — delete `coop-scrape.yml`, add `coop-fast-poll.yml`

**Files:**
- Create: `.github/workflows/coop-fast-poll.yml`
- Delete: `.github/workflows/coop-scrape.yml`

- [ ] **Step 1: Create the new workflow**

Create `.github/workflows/coop-fast-poll.yml`:

```yaml
name: coop-fast-poll
on:
  schedule:
    - cron: "*/5 6-20 * * 1-6"   # every 5 min, ~08:00–22:00 Vienna, Mon–Sat
  workflow_dispatch: {}
concurrency:
  group: coop-fast-poll
  cancel-in-progress: true       # a slow run must not stack on the next tick
jobs:
  poll:
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r Project/requirements.txt
      - name: Fast co-op poll → Telegram
        working-directory: Project
        env:
          MONGODB_URI: ${{ secrets.MONGODB_URI }}
          TELEGRAM_MAIN_BOT_TOKEN: ${{ secrets.TELEGRAM_MAIN_BOT_TOKEN }}
          TELEGRAM_MAIN_CHAT_ID: ${{ secrets.TELEGRAM_MAIN_CHAT_ID }}
          TELEGRAM_COOP_CHANNEL_ID: ${{ secrets.TELEGRAM_COOP_CHANNEL_ID }}
        run: python run_coop.py
```

- [ ] **Step 2: Delete the replaced workflow**

```bash
git rm .github/workflows/coop-scrape.yml
```

- [ ] **Step 3: Validate YAML parses**

Run: `cd Project && python -m pytest Tests/test_run_coop.py -q` (sanity that nothing broke), and validate the workflow YAML:

```bash
python - <<'PY'
import yaml, pathlib
for p in [".github/workflows/coop-fast-poll.yml"]:
    yaml.safe_load(pathlib.Path(p).read_text())
    print("OK", p)
PY
```

**NOTE:** if a heredoc/`python -` invocation is denied in this environment, instead write a one-line check script to `Project/scratchpad/_yaml_check.py` and run it. Expected: `OK .github/workflows/coop-fast-poll.yml`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/coop-fast-poll.yml
git commit -m "ci(coop): replace coop-scrape (*/15) with coop-fast-poll (*/5)"
```

---

## Task 8: Coverage measurement (honors `test_scope: true`)

**Files:** none created — measurement only.

- [ ] **Step 1: Install coverage tooling (not currently in requirements)**

```bash
cd Project && pip install pytest-cov
```

- [ ] **Step 2: Measure coverage of the new/changed code**

```bash
cd Project && python -m pytest Tests/test_run_coop.py Tests/test_coop_format.py \
  Tests/test_source_meta.py Tests/test_upsert_coop.py \
  --cov=run_coop --cov=Application.coop_format \
  --cov-report=term-missing -q
```

Expected: all tests PASS. Record the reported coverage %. **Gate:** `run_coop.py` and `Application/coop_format.py` line coverage ≥ 85%. If below, add a targeted test for the uncovered lines (the `--cov-report=term-missing` output lists them) and re-run. Do not lower the gate.

Note: `upsert_coop_listing` / `get_source_meta` / `set_source_meta` live in the large `mongodb_handler.py`; they are covered by `test_upsert_coop.py` / `test_source_meta.py` but a whole-file `--cov=Integration.mongodb_handler` number would be noise — measure those methods’ coverage by inspection of `term-missing` if needed, not as a file gate.

- [ ] **Step 3: Record the number in the status file**

Append the coverage % and pass count to `.claude/relentless-status-<session>.md` under a "Phase A coverage" line. (No commit — measurement artifact only.)

---

## Task 9: Document the `coop_alerts` schema + workflow change

**Files:**
- Modify: `docs/CLAUDE-full-reference.md` (append a section)

- [ ] **Step 1: Append documentation**

Add to `docs/CLAUDE-full-reference.md`:

```markdown
## Co-op fast-poll (Phase A)

`Project/run_coop.py` — lightweight coop poller for GitHub Actions cron `*/5`
(`.github/workflows/coop-fast-poll.yml`, ~08:00–22:00 Vienna Mon–Sat). Replaces
the old `coop-scrape.yml` (*/15). Polls the Genossenschaft adapters with
conditional GET (ETag/Last-Modified/page-hash stored in the `source_meta`
Mongo collection), upserts via `MongoDBHandler.upsert_coop_listing()` (price-less;
preserves `sent_to_telegram` on re-poll), and DMs matches to
`TELEGRAM_COOP_CHANNEL_ID` (fallback `TELEGRAM_MAIN_CHAT_ID`).

Run locally: `cd Project && python run_coop.py [--dry-run]`.

### Alert filter — `Project/coop_alerts.json` (tracked; not a secret)

    { "bezirke": [], "max_cost": null, "min_rooms": null, "min_area": null }

Empty/`null` field = no constraint (send all). A missing **listing** field is
permissive (never excludes). Precedence: `COOP_ALERTS` env (JSON) >
`config.json` `coop_alerts` key > `Project/coop_alerts.json` > send-all.
(`config.json` is gitignored/absent in CI, so the tracked file is the
CI-visible source. Tune by editing + committing `coop_alerts.json`.)
```

- [ ] **Step 2: Commit**

```bash
git add docs/CLAUDE-full-reference.md
git commit -m "docs(coop): document run_coop, coop_alerts schema, workflow swap"
```

---

## Final gate (before declaring Phase A done)

- [ ] **Full backend test suite green:** `cd Project && python -m pytest Tests/ -q` — 0 failures.
- [ ] **Live smoke re-run:** `cd Project && MONGODB_URI="<atlas>" python run_coop.py --dry-run` exits 0 with a sane summary line.
- [ ] **No secret committed:** `git diff --stat main` shows only the files in this plan; `config.json` absent; no tokens in `coop_alerts.json`.
- [ ] **Workflow swap verified:** `coop-scrape.yml` deleted, `coop-fast-poll.yml` present and YAML-valid.

## Out of scope (this plan)

Phase B (adapter scale-out to ~14 Bauträger, `coop/` package refactor) and Phase C
(dashboard filters ×4, `ui_scope` Playwright verification) — separate plans.
Geocoding/scoring of fast-poll listings (daily job enriches; map uses bezirk centroid).
```