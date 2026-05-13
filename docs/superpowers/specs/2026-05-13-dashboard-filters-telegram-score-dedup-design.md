# Dashboard Filters + Telegram Score + Telegram Dedup

**Date:** 2026-05-13  
**Status:** Approved

---

## Problem

1. Dashboard shows garbage listings (price_per_m2 < 2500, empty titles) that slip through between daily cleanup runs.
2. Telegram notifications don't show the listing score — users can't tell quality at a glance.
3. High-scoring listings get re-sent every scrape cycle. Users receive the same property repeatedly until it's sold.

---

## Decision

Three independent changes, each touching a distinct layer.

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

**New check** at the `high_score_listings.append` site (`main.py:657`):

```python
SEVEN_DAYS = 7 * 86400

# Before appending to high_score_listings:
doc = mongo.collection.find_one({"url": listing.url}, {"sent_to_telegram_at": 1})
last_sent = doc.get("sent_to_telegram_at") if doc else None
if last_sent and (time.time() - last_sent) < SEVEN_DAYS:
    logging.info(f"⏭️  Skipping Telegram for '{listing.title}' — sent {int((time.time()-last_sent)/86400)}d ago")
    continue
high_score_listings.append(listing)
```

**Why in main.py, not TelegramBot:**
- `mark_sent` is already called from main.py — ownership is already there
- TelegramBot has no MongoDB dependency; adding one for a check that main.py already owns is unnecessary coupling
- Listing objects at this point are dataclass instances, not MongoDB documents — `sent_to_telegram_at` is not on the dataclass

**Cooldown:** 7 days hardcoded. Not configurable — YAGNI, this is a product constant not an ops knob.

### Module Design Block

### Module: main.py Telegram dispatch loop
- **Responsibility:** Filter scraped listings by score + cooldown, send Telegram, mark sent
- **Interface:** `high_score_listings: List[Listing]`, `mongo: MongoDBHandler`, `telegram_bot: TelegramBot`
- **Dependencies:** MongoDBHandler, TelegramBot
- **Size target:** ~20-line loop, no structural change

---

## Non-changes

- `send_top_listings` (run_top5.py daily report) — dedup does NOT apply. Top5 is a deliberate batch report, not a real-time alert.
- `TelegramBot` constructor — no new params. MongoDB stays out of TelegramBot.
- `sent_to_telegram_at` field name — unchanged (already in DB via `mark_sent`).

---

## Test coverage

- Dashboard filter: verify `price_per_m2 = 2000` excluded, `= 3000` included; empty title excluded
- Score display: smoke-check message contains `🔥 Score:`
- Dedup: listing with `sent_to_telegram_at = now - 3 days` → skipped; `now - 8 days` → sent; missing field → sent
