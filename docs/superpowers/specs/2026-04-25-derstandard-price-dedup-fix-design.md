# Fix: derStandard Price Parsing Bug + Content Fingerprint Deduplication

**Date:** 2026-04-25
**Status:** Approved

---

## Problem Statement

Two bugs found in derstandard.at scraper:

1. **Price parsing bug**: `extract_property_data_from_json()` grabs `costs.main.value` from JSON, which is **Betriebskosten (€477.08)** for "Preis auf Anfrage" listings, not the actual purchase price. The listing has no actual price, but the code stores the Betriebskosten as `price_total`. This bypasses the existing `extract_price()` "anfrage" check because it only exists in the HTML fallback path, not the JSON path.

2. **Duplicate listings**: Same derstandard listing appears 5 times in the dashboard. Deduplication is purely URL-based (`url` unique index in MongoDB). If derstandard serves the same listing via different URLs (e.g., with query params or short URLs), each variant becomes a separate document.

---

## Fix 1: Price Parsing — Detect "Preis auf Anfrage" in JSON Path

**File:** `Project/Application/scraping/derstandard_scraper.py`
**Method:** `extract_property_data_from_json()` (line 682)

### Change

After extracting `price_total` from JSON (`line 724-727`), check if the listing is "Preis auf Anfrage" by searching the full page text (available as `soup.get_text()` or stored script content). If detected, nullify `price_total`.

```python
# Line 727 - after: property_info['price_total'] = cost_data['value']
# Add check:
if price_total is not None and price_total < 10000:
    page_text = soup.get_text().lower() if soup else ""
    if any(phrase in page_text for phrase in ['preis auf anfrage', 'auf anfrage', 'price on request']):
        property_info['price_total'] = None
        property_info['price_is_on_request'] = True
```

Also update `validate_listing_data()` to reject listings with `price_total is None` before scoring.

---

## Fix 2: Content Fingerprint Deduplication

**File:** `Project/Integration/mongodb_handler.py`

### Changes

1. **Add `content_fingerprint` field computation** in `insert_listing()`:
   ```python
   def _compute_fingerprint(listing: Dict) -> str:
       """Compute a content fingerprint hash for dedup."""
       import hashlib
       key_fields = (
           f"{listing.get('title', '')}"
           f"{listing.get('area_m2', '')}"
           f"{listing.get('rooms', '')}"
           f"{listing.get('bezirk', '')}"
           f"{listing.get('source_enum', '')}"
       )
       return hashlib.md5(key_fields.encode()).hexdigest()
   ```

2. **Check fingerprint before insert** — if a listing with same fingerprint + source already exists, skip insert (return `True` but don't insert).

3. **Add compound index** on `(fingerprint_hash, source_enum)` for efficient lookups.

4. **Update `save_listings_to_mongodb()` in main.py** to compute fingerprint before calling `insert_listing()`.

---

## Fix 3: Cleanup Existing Bad Data

**New file:** `Project/cleanup_derstandard_issues.py`

A standalone cleanup script that:

1. **Find and flag/remove price-on-request listings:**
   - Query: `{source_enum: "derstandard", price_total: {$lt: 10000}}`
   - For each: fetch the listing URL, check if "Preis auf Anfrage" is in page text
   - If yes: delete the document from MongoDB
   - If no (genuinely cheap): keep but log for review

2. **Find and remove duplicate fingerprints:**
   - Aggregate pipeline grouping by `fingerprint_hash` + `source_enum`
   - Keep document with earliest `processed_at`, delete rest
   - Requires fingerprint computation on existing documents

---

## Files to Modify

| File | Change |
|------|--------|
| `Project/Application/scraping/derstandard_scraper.py` | Add "Preis auf Anfrage" check in `extract_property_data_from_json()` after line 727 |
| `Project/Integration/mongodb_handler.py` | Add fingerprint computation + dedup check in `insert_listing()` + add index |
| `Project/Application/main.py` | Compute fingerprint before insert in `save_listings_to_mongodb()` |
| `Project/cleanup_derstandard_issues.py` | New cleanup script |

---

## Testing

1. Run derstandard scraper against the known bad URL (`/detail/15120597`) — it should return `price_total = None` and not store the listing
2. Run cleanup script — verify bad listings are removed
3. Re-scrape — verify only 1 document exists per listing
4. Run existing test suite: `cd Tests && python run_tests.py`
