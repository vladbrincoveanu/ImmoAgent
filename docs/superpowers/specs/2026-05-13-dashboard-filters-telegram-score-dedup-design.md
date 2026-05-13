# Dashboard Filters + Telegram Score + Telegram Dedup + Data Cleanup

**Date:** 2026-05-13
**Status:** Approved

---

## Problem

1. Dashboard shows garbage listings (price_per_m2 < 2500, empty titles) that slip through between daily cleanup runs.
2. Telegram notifications don't show the listing score — users can't tell quality at a glance.
3. High-scoring listings get re-sent every scrape cycle. Users receive the same property repeatedly until it's sold.
4. GLOBAL_VALIDATION min_price_per_m2 is €1,000 — too low; allows Neubauprojekt aggregate pages.
5. Willhaben scraper hits Neubauprojekt aggregate pages → wrong data (€/m² instead of €/unit).

---

## Decision

Four independent changes.

---

## Section 1: Dashboard Quality Filters

### What changes

Both API routes raise the `price_per_m2` floor and add a title guard.

**Files:** `dashboard/app/api/listings/map/route.ts`, `dashboard/app/api/listings/top/route.ts`

**map/route.ts** — existing `$and` filter:
```typescript
// Before
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 1000] } },

// After
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
```

Add to both routes' `$and` array:
```typescript
{ title: { $nin: [null, ""] } },
```

**Why `$nin` not `$ne`:** `{ title: { $ne: null, $ne: "" } }` is invalid — JS object drops the first `$ne`. `$nin: [null, ""]` handles null, empty string, and missing field in one operator.

### Module Design Block

### Module: Dashboard API routes (map + top)
- **Responsibility:** Filter and return listing documents for UI consumption
- **Interface:** GET query params → JSON listing array
- **Dependencies:** MongoDB `listings` collection
- **Size target:** Both routes ~100 lines, no change to size

---

## Section 2: Telegram Score Display

### What changes

Score was deliberately removed from `_format_property_message` (lines 395–397). Restore it, move to position 2 (immediately after address+price).

**File:** `Project/Integration/telegram_bot.py`

Message order after change:
```
🏠 <b>address</b> - €price
🔥 Score: 82
🏗️ Year of Construction: 2019
💰 Initial Investment: ...
...
```

**Implementation:**
```python
# After address+price block, before year_built block:
if score is not None:
    message_parts.append(f"🔥 Score: {score:.0f}")
```

Format: integer (`{score:.0f}`). `score_apartment_simple` returns float — confirmed safe.

### Module Design Block

### Module: TelegramBot._format_property_message
- **Responsibility:** Format a listing dict as an HTML Telegram message
- **Interface:** `listing: Dict` → `str`
- **Dependencies:** None (pure formatting)
- **Size target:** ~270 lines, no structural change

---

## Section 3: Telegram 7-Day Dedup

### What changes

Before queueing a listing for Telegram in `main.py`, check `sent_to_telegram_at`. Skip if sent within 7 days. Existing `mark_sent` call after send is unchanged.

**File:** `Project/Application/main.py`

**Existing infrastructure (no new fields needed):**
- `MongoDBHandler.mark_sent(url)` — sets `sent_to_telegram: True, sent_to_telegram_at: timestamp`
- Called at `main.py:710` after each successful send — already in place

**New check** at the top of the scoring loop (before score calculation, `main.py:649`):

```python
SEVEN_DAYS = 7 * 86400

# Cooldown check BEFORE scoring (skip CPU for recently-sent listings)
if mongo.collection:
    doc = mongo.collection.find_one({"url": listing.url}, {"sent_to_telegram_at": 1})
    last_sent = doc.get("sent_to_telegram_at") if doc else None
    if last_sent and (time.time() - last_sent) < SEVEN_DAYS:
        logging.info(f"⏭️  Skipping '{listing.title}' — sent {int((time.time()-last_sent)/86400)}d ago")
        # Still calculate score for MongoDB storage, but skip Telegram send
        if telegram_bot:
            score = telegram_bot.calculate_listing_score(listing.__dict__)
            listing.score = score
        continue

# Score calculation continues normally...
```

**Why in main.py, not TelegramBot:**
- `mark_sent` is already called from main.py — ownership is already there
- TelegramBot has no MongoDB dependency; adding one for a check that main.py already owns is unnecessary coupling
- Listing objects at this point are dataclass instances, not MongoDB documents — `sent_to_telegram_at` is not on the dataclass

**Cooldown behavior:** On cooldown → skip Telegram send, BUT still calculate score (needed for MongoDB storage). Score is stored even for cooldown-listed listings so the dashboard shows current scores.

**Cooldown:** 7 days hardcoded. Not configurable — YAGNI, this is a product constant not an ops knob.

**MongoDB guard:** `if mongo.collection:` check prevents crash if MongoDB is unavailable.

### Module Design Block

### Module: main.py Telegram dispatch loop
- **Responsibility:** Filter scraped listings by score + cooldown, send Telegram, mark sent
- **Interface:** `high_score_listings: List[Listing]`, `mongo: MongoDBHandler`, `telegram_bot: TelegramBot`
- **Dependencies:** MongoDBHandler, TelegramBot
- **Size target:** ~20-line loop, no structural change

---

## Section 4: GLOBAL_VALIDATION min_price_per_m2 Update

### What changes

Raise `GLOBAL_VALIDATION['min_price_per_m2']` from €1,000 → €2,500.

**File:** `Project/Application/buyer_profiles.py`

```python
# Before
GLOBAL_VALIDATION = {
    "min_price_per_m2": 1000,
    "max_price_per_m2": 20000,
}

# After
GLOBAL_VALIDATION = {
    "min_price_per_m2": 2500,
    "max_price_per_m2": 20000,
}
```

**Rationale:** Neubauprojekt aggregate pages show project totals (€/m²) instead of unit prices. €2,500/m² is below any realistic Vienna new-build unit price, catching these aggregate pages without rejecting legitimate older properties.

**Cascade effect:** `listing_validator.py` uses this threshold — no other changes needed.

---

## Section 5: Cleanup Migration Script

### What changes

One-shot migration script to purge bad data from MongoDB.

**File:** `Project/scripts/cleanup_empty_titles.py`

**Step 1 — Query candidates**
```python
{ $or: [
    { title: "" }, { title: null }, { title: { $exists: false } },
    { price_per_m2: { $lt: 2500 } },
    { url: { $regex: "/neubauprojekt/" } }
] }
```

**Step 2 — Parallel health check (5 workers)**
Each listing:
- HTTP head → ≠200 → mark `url_is_valid=false` → delete
- HTTP 200 → re-scrape using source-specific scraper (matching `listing.source_enum`)
  - Re-scrape has valid title AND `price_per_m2 >= 2500` → update MongoDB, keep
  - Re-scrape still bad → delete

**Step 3 — Pre-delete audit log**
Write affected URLs + reason to `log/cleanup_empty_titles_{timestamp}.log`

**Step 4 — Modes**
```bash
python scripts/cleanup_empty_titles.py       # dry-run
python scripts/cleanup_empty_titles.py --confirm  # real delete
```

### Module Design Block

### Module: cleanup_empty_titles.py
- **Responsibility:** Find and delete listings with empty titles or sub-threshold price/m²
- **Interface:** CLI with `--confirm` flag
- **Dependencies:** MongoDBHandler, WillhabenScraper, HTTP client, ThreadPoolExecutor
- **Size target:** ~150 lines

---

## Section 6: Willhaben Scraper Neubauprojekt Fix

### What changes

Skip URLs containing `/neubauprojekt/` in the Willhaben scraper.

**File:** `Project/Application/scraping/willhaben_scraper.py`

In the main scrape loop (where individual listing URLs are queued for scraping), check:
```python
if '/neubauprojekt/' in url:
    logging.info(f"⏭️  Skipping Neubauprojekt aggregate page: {url}")
    continue
```

**Rationale:** Neubauprojekt pages show project-level data (aggregate price, total area, unit count) not unit-level data. These pages cannot be scraped into valid listings.

---

## Non-changes

- `send_top_listings` (run_top5.py daily report) — dedup does NOT apply. Top5 is a deliberate batch report, not a real-time alert.
- `TelegramBot` constructor — no new params. MongoDB stays out of TelegramBot.
- `sent_to_telegram_at` field name — unchanged (already in DB via `mark_sent`).
- `GLOBAL_VALIDATION['max_price_per_m2']` — unchanged at €20,000.

---

## Test coverage

- Dashboard filter: verify `price_per_m2 = 2000` excluded, `= 3000` included; empty title excluded
- Score display: smoke-check message contains `🔥 Score:`
- Dedup: listing with `sent_to_telegram_at = now - 3 days` → skipped; `now - 8 days` → sent; missing field → sent
- GLOBAL_VALIDATION: `python -c "from Application.buyer_profiles import GLOBAL_VALIDATION; print(GLOBAL_VALIDATION['min_price_per_m2'])"` → `2500`
- Cleanup script dry-run: prints count without deleting
- Cleanup script confirm: deletes and logs
- Scraper skip: `python -c "if '/neubauprojekt/' in 'https://willhaben.at/iad/immobilien/d/neubauprojekt/foo': print('skip')"` → `skip`