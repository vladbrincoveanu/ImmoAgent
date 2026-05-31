# Taken Listings Tracking & Analytics — Design Spec

**Date:** 2026-05-31
**Status:** Approved
**Approach:** A (Minimal flag)

---

## Context

DerStandard listings go 404 randomly. No distinction between "taken" (sold/rented) and "offline" (broken link). No lifecycle statistics. Dashboard shows broken URLs until manually cleaned.

Goal: Auto-detect when listings go offline, keep in DB for stats panel, remove from dashboard views.

---

## 1. MongoDB Schema Changes

### New Fields on `listings` Collection

| Field | Type | Description |
|-------|------|-------------|
| `listing_status` | `string` | `"active"` \| `"taken"` \| `null` (null = active for backwards compat) |
| `taken_at` | `datetime` | When first detected as offline (HTTP 404/410) |
| `price_history` | `array` | `[{price_total: float, recorded_at: datetime}]` — snapshots on price changes |
| `first_scraped_at` | `datetime` | From `processed_at` on first insert (set once) |

### Indexes

- `listing_status: 1, processed_at: -1` — stats queries by status over time
- `listing_status: 1, source_enum: 1` — source breakdown
- `listing_status: 1, bezirk: 1` — district turnover

### Backwards Compatibility

All existing listings: `listing_status: null` treated as active. No migration needed. All existing queries continue to work.

---

## 2. Re-validation Jobs

### 2a. Lightweight Post-Scrape Check

**Function:** `mark_taken_listings(mongo_handler, source_filter=None)` in `cleanup.py`

**Trigger:** After each scraper run completes (called from `Application/main.py`)

**Behavior:**
1. Query all `listing_status != "taken"` listings for given source(s)
2. For each URL: `HEAD` request with 5s timeout
3. If HTTP 404 or 410 → set `listing_status: "taken"`, `taken_at: datetime.utcnow()`
4. Skip if already `listing_status: "taken"`
5. Log count of newly taken

**Rate limit:** sequential, 1 req/s, single source per run

### 2b. Thorough Daily Revalidation

**Function:** `daily_revalidation(mongo_handler, batch_size=50)` in `cleanup.py`

**Trigger:** GitHub Actions cron, daily at 06:00 UTC

**Behavior:**
1. Query ALL active listings (any source)
2. Batch processing (50 per batch, 0.5s between batches)
3. HEAD request → 404/410 → mark taken
4. Additionally: for HTTP 200 responses, scan body for soft 404 patterns:
   - `"verkauft"`, `"vergeben"`, `"inaktiv"`, `"nicht mehr verfügbar"`
   - If found → mark taken
5. Log progress every 10%
6. Return stats: checked, newly_taken, already_taken

### 2c. First-Scrape Timestamp

On `insert_listing()` in `mongodb_handler.py`:
- If `first_scraped_at` not set → set to `processed_at`
- Existing listings remain `null` (acceptable)

---

## 3. Price History Tracking

### On Listing Update (existing listing re-scraped)

In `MongoDBHandler.insert_listing()` or a new `update_listing()`:

1. Fetch existing document
2. Compare `price_total` with existing
3. If different AND existing price not null:
   - Push `{price_total: old_price, recorded_at: datetime.utcnow()}` to `price_history` array
4. Proceed with normal update

### Price Alteration Detection

- `price_history.length > 1` = price was altered at least once
- `price_history[-1]` = most recent recorded price before current

---

## 4. Stats API Endpoints

### 4a. `GET /api/stats/taken`

**Returns:**
```json
{
  "summary": {
    "total_active": 120,
    "total_taken": 45,
    "total": 165,
    "taken_rate_pct": 27.3
  },
  "by_source": [
    {"source": "willhaben", "active": 80, "taken": 20, "taken_rate": 20.0},
    {"source": "derstandard", "active": 30, "taken": 25, "taken_rate": 45.5}
  ],
  "by_district": [
    {"bezirk": "1010", "active": 10, "taken": 5, "taken_rate": 33.3}
  ],
  "timing": {
    "avg_days_active": 14.3,
    "median_days_active": 7.0,
    "min_days_active": 1,
    "max_days_active": 90
  },
  "price": {
    "avg_price_active": 450000,
    "avg_price_taken": 380000,
    "avg_price_at_scrape_taken": 385000
  },
  "price_alterations": {
    "count_with_changes": 12,
    "total_taken": 45,
    "alteration_rate_pct": 26.7,
    "examples": [
      {"title": "...", "price_at_scrape": 400000, "last_price": 385000, "delta": -15000}
    ]
  }
}
```

### 4b. `GET /api/stats/timeline`

**Query params:** `?days=30` (default 30)

**Returns:**
```json
{
  "created": [
    {"date": "2026-05-01", "count": 5},
    {"date": "2026-05-02", "count": 8}
  ],
  "taken": [
    {"date": "2026-05-03", "count": 2},
    {"date": "2026-05-05", "count": 1}
  ]
}
```

### 4c. `GET /api/stats/taken-listings`

**Query params:** `?limit=50&offset=0&sort=days_active_desc`

**Returns:** Paginated list of taken listings:
```json
{
  "listings": [
    {
      "title": "...",
      "url": "https://...",
      "source": "derstandard",
      "bezirk": "1010",
      "price_total": 385000,
      "price_at_scrape": 400000,
      "days_active": 12,
      "first_scraped_at": "2026-05-01T10:00:00Z",
      "taken_at": "2026-05-13T14:30:00Z",
      "price_history": [{"price_total": 400000, "recorded_at": "..."}]
    }
  ],
  "total": 45,
  "limit": 50,
  "offset": 0
}
```

---

## 5. Dashboard Changes

### 5a. Map Route (`/api/listings/map`)

Add filter: `listing_status: {$ne: "taken"}` (default)

Existing behavior: `url_is_valid !== false` already filters broken URLs. Add `listing_status !== "taken"` to same filter.

### 5b. Top Route (`/api/listings/top`)

Add `status` query param: `?status=active|taken|all` (default: `active`)

### 5c. New Stats Panel (`/dashboard/taken`)

New page showing:
- Summary cards: total active, total taken, taken rate %, avg days active
- Timeline chart: listings created vs taken over time
- Source breakdown table
- District heatmap (taken rate by district)
- Full table of taken listings with:
  - Days alive
  - Price at scrape vs last known price
  - Price alteration indicator (↑↓)
  - Link to original URL (may be 404, but archive.org fallback link)
  - `first_scraped_at` → `taken_at`

---

## 6. GitHub Actions Integration

### Daily Revalidation Workflow

```yaml
name: Daily Listing Revalidation
on:
  schedule:
    - cron: '0 6 * * *'  # 06:00 UTC daily
  workflow_dispatch:       # Manual trigger
```

```bash
cd Project && python -c "from Application.cleanup import daily_revalidation; from Integration.mongodb_handler import MongoDBHandler; m = MongoDBHandler(); print(daily_revalidation(m))"
```

### Post-Scrape Integration

In `Application/main.py` after each source scrape completes:
```python
mark_taken_listings(mongo, source_filter=[source_enum])
```

---

## 7. Implementation Order

**Prerequisite:** Current `insert_listing` does NOT update existing listings on re-scrape (URL unique index + content fingerprint dedup means re-scrapes are silently skipped or fail). Implementation MUST add `upsert_listing_with_history()` that:
- On new URL → insert with `first_scraped_at = processed_at`
- On existing URL → push price to `price_history` if price changed, then `$set` other fields
- This is a prerequisite for price history to work at all

1. **Schema + price history** — `mongodb_handler.py` changes, first_scraped_at, price_history, `upsert_listing_with_history()`
2. **Re-validation jobs** — `cleanup.py` functions (mark_taken_listings, daily_revalidation)
3. **Stats API** — `/api/stats/taken`, `/api/stats/timeline`, `/api/stats/taken-listings`
4. **Dashboard filters** — map + top route status filter
5. **Stats panel** — `/dashboard/taken` page
6. **GitHub Actions** — cron + post-scrape integration

---

## Open Questions (Resolved)

- **Distinguish taken vs offline?** No — single `taken` status sufficient
- **Separate collection?** No — same collection with `listing_status` flag
- **Re-validation frequency?** Both — lightweight post-scrape + thorough daily
- **Stats needed?** Volume, timing, price, price alterations, timeline
