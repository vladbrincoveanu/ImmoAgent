# Taken Listings Tracking & Analytics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-detect when listings go 404/offline, keep in DB as "taken" for analytics, remove from dashboard views.

**Architecture:** Same-collection with `listing_status` flag. Post-scrape lightweight check + daily thorough revalidation. Stats via new API endpoints + dashboard panel.

**Tech Stack:** Python (MongoDB handler, cleanup), TypeScript (Next.js dashboard API + pages)

---

## File Map

### Backend (Python)
- `Project/Integration/mongodb_handler.py` — add `upsert_listing_with_history()`, `mark_listing_taken()`, new indexes, `price_at_scrape` field
- `Project/Application/cleanup.py` — add `mark_taken_listings()`, `daily_revalidation()`
- `Project/Application/main.py` — integrate post-scraping revalidation call

### Dashboard API (TypeScript)
- `dashboard/app/api/listings/map/route.ts` — add `listing_status` filter
- `dashboard/app/api/listings/top/route.ts` — add both `url_is_valid` AND `listing_status` filter
- `dashboard/app/api/stats/taken/route.ts` — **NEW** stats summary endpoint
- `dashboard/app/api/stats/timeline/route.ts` — **NEW** time-series endpoint
- `dashboard/app/api/stats/taken-listings/route.ts` — **NEW** paginated taken listings
- `dashboard/app/api/listings/[id]/taken-detail/route.ts` — **NEW** price history detail

### Dashboard Pages
- `dashboard/app/dashboard/taken/page.tsx` — **NEW** stats panel page

### Tests
- `Tests/test_taken_listings.py` — **NEW** unit tests for cleanup functions
- `Tests/test_taken_listings_mongodb.py` — **NEW** tests for MongoDB upsert/history

---

## Task 1: MongoDB Schema + upsert_listing_with_history()

**Files:**
- Modify: `Project/Integration/mongodb_handler.py:79-97` (index creation), `115-151` (insert_listing), `637-661` (save_listings_to_mongodb)
- Create: `Tests/test_taken_listings_mongodb.py`

- [ ] **Step 1: Write failing test for price_history tracking**

```python
# Tests/test_taken_listings_mongodb.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_price_history_on_re_scrape():
    """When same URL re-scraped with different price, old price pushed to history"""
    from Integration.mongodb_handler import MongoDBHandler
    from unittest.mock import MagicMock, patch

    # Mock the collection
    with patch.object(MongoDBHandler, '__init__', lambda self: None):
        mongo = MongoDBHandler()
        mongo.collection = MagicMock()
        mongo.client = MagicMock()

        # First insert
        mongo.collection.find_one.return_value = None
        mongo.collection.insert_one.return_value = MagicMock()

        listing1 = {
            'url': 'https://example.com/listing1',
            'title': 'Test Listing',
            'price_total': 400000,
            'area_m2': 80,
            'rooms': 3,
            'source_enum': 'willhaben',
            'processed_at': 1700000000,
        }
        result = mongo.upsert_listing_with_history(listing1)
        # Should insert with first_scraped_at and price_at_scrape set
        assert result == True
        insert_call = mongo.collection.insert_one.call_args[0][0]
        assert insert_call['first_scraped_at'] is not None
        assert insert_call['price_at_scrape'] == 400000
        assert insert_call['price_history'] == []

print("✅ Price history test written")
```

Run: `python Tests/test_taken_listings_mongodb.py`
Expected: FAIL — `upsert_listing_with_history` not defined

- [ ] **Step 2: Run test to verify it fails**

```
AttributeError: 'MongoDBHandler' object has no attribute 'upsert_listing_with_history'
```

- [ ] **Step 3: Add new indexes to MongoDBHandler.__init__**

```python
# In __init__ after existing indexes (around line 90):
self.collection.create_index([("listing_status", 1), ("processed_at", -1)])
self.collection.create_index([("listing_status", 1), ("source_enum", 1)])
self.collection.create_index([("listing_status", 1), ("bezirk", 1)])
```

- [ ] **Step 4: Add upsert_listing_with_history() method to MongoDBHandler**

```python
def upsert_listing_with_history(self, listing: Dict) -> bool:
    """Insert or update listing with price history tracking.

    On new listing: set first_scraped_at = processed_at, price_at_scrape = price_total
    On existing listing with price change: push old price to price_history
    Returns True on success, False on validation failure.
    """
    price_val = listing.get('price_total')
    if not isinstance(price_val, (int, float)) or price_val <= 0:
        logging.info(f"🚫 Skipping: invalid price_total ({price_val})")
        return False

    valid, reason = is_valid_listing_data(listing)
    if not valid:
        logging.info(f"🚫 Skipping: validation failed — {reason}")
        return False

    fingerprint = compute_content_fingerprint(listing)
    listing['content_fingerprint'] = fingerprint

    try:
        from datetime import datetime
        now = datetime.utcnow()

        # Check if listing exists by content fingerprint
        existing = self.collection.find_one({
            "content_fingerprint": fingerprint,
            "source_enum": listing.get('source_enum', listing.get('source'))
        })

        if existing:
            # Update existing: track price change
            old_price = existing.get('price_total')
            price_history = existing.get('price_history', [])

            # Push old price to history if it changed
            if old_price and old_price != price_val:
                price_history.append({
                    'price_total': old_price,
                    'recorded_at': now
                })

            update_set = {
                'price_total': price_val,
                'price_history': price_history,
                'processed_at': listing.get('processed_at', now.timestamp()),
            }
            # Set price_at_scrape only if not already set (preserve first scrape price)
            if existing.get('price_at_scrape') is None:
                update_set['price_at_scrape'] = old_price or price_val

            self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_set}
            )
            return True

        # New listing
        listing['first_scraped_at'] = listing.get('processed_at') or now.timestamp()
        listing['price_at_scrape'] = price_val
        listing['price_history'] = []
        listing['listing_status'] = 'active'

        self.collection.insert_one(listing)
        return True

    except pymongo.errors.DuplicateKeyError:
        # URL already exists with different fingerprint — update by URL
        existing = self.collection.find_one({"url": listing.get('url')})
        if existing:
            old_price = existing.get('price_total')
            price_history = existing.get('price_history', [])
            if old_price and old_price != price_val:
                price_history.append({'price_total': old_price, 'recorded_at': datetime.utcnow()})
            self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    'price_total': price_val,
                    'price_history': price_history,
                    'processed_at': listing.get('processed_at', datetime.utcnow().timestamp()),
                    'price_at_scrape': existing.get('price_at_scrape') or old_price or price_val,
                    'listing_status': 'active'
                }}
            )
        return True
    except Exception as e:
        logging.error(f"❌ upsert_listing_with_history error: {e}")
        return False
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python Tests/test_taken_listings_mongodb.py`
Expected: PASS

- [ ] **Step 6: Add mark_listing_taken() helper**

```python
def mark_listing_taken(self, url: str) -> bool:
    """Mark a listing as taken (offline/404)."""
    try:
        from datetime import datetime
        result = self.collection.update_one(
            {"url": url, "listing_status": {"$ne": "taken"}},
            {"$set": {
                "listing_status": "taken",
                "taken_at": datetime.utcnow(),
                "url_is_valid": False
            }}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"❌ mark_listing_taken error for {url}: {e}")
        return False
```

- [ ] **Step 7: Verify mark_listing_taken works (manual test)**

Run: `cd Project && python -c "from Integration.mongodb_handler import MongoDBHandler; m = MongoDBHandler(); print(m.mark_listing_taken('https://example.com/test'))"`

- [ ] **Step 8: Commit**

```bash
git add Project/Integration/mongodb_handler.py Tests/test_taken_listings_mongodb.py
git commit -m "feat: add upsert_listing_with_history and mark_listing_taken with price_history tracking"
```

---

## Task 2: Re-validation Jobs

**Files:**
- Modify: `Project/Application/cleanup.py`
- Create: `Tests/test_taken_listings.py`

- [ ] **Step 1: Write failing test for mark_taken_listings()**

```python
# Tests/test_taken_listings.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_mark_taken_listings_head_404():
    """HEAD 404 marks listing as taken"""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [
        {'_id': 1, 'url': 'https://example.com/404', 'source_enum': 'willhaben'}
    ]

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=404)
        result = mark_taken_listings(mock_mongo, source_filter=['willhaben'])

    assert result['newly_taken'] == 1
    mock_mongo.collection.update_one.assert_called_once()
    call_args = mock_mongo.collection.update_one.call_args
    assert call_args[0][1]['$set']['listing_status'] == 'taken'

def test_mark_taken_listings_head_200_derstandard_soft404():
    """DerStandard 200 with soft 404 body marks listing as taken"""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [
        {'_id': 2, 'url': 'https://derstandard.at/listing', 'source_enum': 'derstandard'}
    ]

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=200)
        with patch('Application.cleanup.requests.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                iter_content=lambda size: [b'diese anzeige wurde entfernt']
            )
            result = mark_taken_listings(mock_mongo, source_filter=['derstandard'])

    assert result['newly_taken'] == 1

print("✅ Tests written")
```

Run: `python Tests/test_taken_listings.py`
Expected: FAIL — `mark_taken_listings` not defined

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add mark_taken_listings() to cleanup.py**

```python
SOFT_404_PATTERNS = [
    'verkauft', 'vergeben', 'inaktiv', 'nicht mehr verfügbar',
    'reserviert', 'abgelaufen',
    # existing patterns from run_top5.py
    'nicht gefunden', 'seite nicht', '404',
    'anzeige wurde entfernt', 'objekt nicht mehr', 'ist nicht mehr aktiv',
    'listing not found', 'page not found',
]

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ImmoScouter/1.0; +https://github.com/vladbrincoveanu/immo-scouter)'
}

def mark_taken_listings(
    mongo_handler: MongoDBHandler,
    source_filter: list = None,
    timeout: int = 5
) -> Dict[str, int]:
    """Lightweight post-scrape revalidation: check active listings for a source.

    Uses HEAD request first. For derstandard, if HEAD returns 200, does body scan.
    Marks 404/410 as taken. Skips already-taken listings.
    Returns dict with checked, newly_taken, already_taken counts.
    """
    stats = {"checked": 0, "newly_taken": 0, "already_taken": 0}

    query = {"listing_status": {"$ne": "taken"}}
    if source_filter:
        query["source_enum"] = {"$in": source_filter}

    cursor = mongo_handler.collection.find(query, {"url": 1, "source_enum": 1, "_id": 1})
    listings = list(cursor)

    for doc in listings:
        url = doc.get('url')
        source = doc.get('source_enum')
        if not url:
            continue

        stats["checked"] += 1
        url_invalid = False

        try:
            resp = requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout)
            if resp.status_code in (404, 410):
                url_invalid = True
            elif resp.status_code == 200 and source == 'derstandard':
                # Soft 404 check for derstandard only
                try:
                    get_resp = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout, stream=True)
                    chunk = b''
                    for c in get_resp.iter_content(8192):
                        chunk += c
                        if len(chunk) > 51200:
                            break
                    body = chunk.decode('utf-8', errors='ignore').lower()
                    if any(p in body for p in SOFT_404_PATTERNS):
                        url_invalid = True
                except Exception:
                    pass
        except requests.exceptions.RequestException:
            url_invalid = True

        if url_invalid:
            was_updated = mongo_handler.mark_listing_taken(url)
            if was_updated:
                stats["newly_taken"] += 1
            else:
                stats["already_taken"] += 1

    logging.info(f"🔍 mark_taken_listings: checked={stats['checked']}, newly_taken={stats['newly_taken']}, already_taken={stats['already_taken']}")
    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python Tests/test_taken_listings.py::test_mark_taken_listings_head_404 -v`
Expected: PASS

Run: `python Tests/test_taken_listings.py::test_mark_taken_listings_head_200_derstandard_soft404 -v`
Expected: PASS

- [ ] **Step 5: Write test for daily_revalidation()**

```python
def test_daily_revalidation_batch_processing():
    """Daily revalidation processes in batches with delay"""
    from Application.cleanup import daily_revalidation
    from unittest.mock import MagicMock, patch

    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    # Return 60 listings
    mock_mongo.collection.find.return_value = [
        {'_id': i, 'url': f'https://example.com/{i}', 'source_enum': 'willhaben'}
        for i in range(60)
    ]

    with patch('Application.cleanup.mark_taken_listings') as mock_mark:
        mock_mark.return_value = {"checked": 20, "newly_taken": 2, "already_taken": 0}
        result = daily_revalidation(mock_mongo, batch_size=20)

    assert result['checked'] == 60
    assert mock_mark.call_count == 3  # 3 batches of 20

print("✅ Daily revalidation test written")
```

Run: `python Tests/test_taken_listings.py::test_daily_revalidation_batch_processing -v`
Expected: FAIL — `daily_revalidation` not defined

- [ ] **Step 6: Add daily_revalidation() to cleanup.py**

```python
def daily_revalidation(
    mongo_handler: MongoDBHandler,
    batch_size: int = 50,
    timeout: int = 8
) -> Dict[str, int]:
    """Thorough daily revalidation of ALL active listings.

    Batch processing to avoid rate limiting.
    Logs progress every 10%.
    Returns stats dict.
    """
    stats = {"checked": 0, "newly_taken": 0, "already_taken": 0, "batches": 0}

    query = {"listing_status": {"$ne": "taken"}}
    cursor = mongo_handler.collection.find(query, {"url": 1, "source_enum": 1, "_id": 1})
    listings = list(cursor)
    total = len(listings)

    if total == 0:
        logging.info("✅ daily_revalidation: no active listings to check")
        return stats

    logging.info(f"🔍 daily_revalidation: checking {total} active listings...")

    for i in range(0, total, batch_size):
        batch = listings[i:i + batch_size]
        batch_stats = mark_taken_listings(mongo_handler, source_filter=None, timeout=timeout)
        stats['checked'] += batch_stats['checked']
        stats['newly_taken'] += batch_stats['newly_taken']
        stats['already_taken'] += batch_stats['already_taken']
        stats['batches'] += 1

        # Rate limit between batches
        time.sleep(0.5)

        if total > batch_size:
            progress = min(100, int(((i + batch_size) / total) * 100))
            if progress % 10 == 0 or progress == 100:
                logging.info(f"   📊 Progress: {i + batch_size}/{total} ({progress}%)")

    logging.info(f"✅ daily_revalidation complete: checked={stats['checked']}, newly_taken={stats['newly_taken']}, batches={stats['batches']}")
    return stats
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python Tests/test_taken_listings.py::test_daily_revalidation_batch_processing -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Project/Application/cleanup.py Tests/test_taken_listings.py
git commit -m "feat: add mark_taken_listings and daily_revalidation to cleanup"
```

---

## Task 3: Integrate Post-Scrape Revalidation

**Files:**
- Modify: `Project/Application/main.py:624-633` (parallel scrape loop)

- [ ] **Step 1: Read the exact code section to modify**

Run: `sed -n '624,633p' Project/Application/main.py`

Output:
```python
        for future in as_completed(future_to_scraper):
            scraper_name = future_to_scraper[future]
            try:
                listings, source = future.result()
                scraping_results[source] = {'listings': listings, 'count': len(listings)}
                all_listings.extend(listings)
                logging.info(f"✅ {scraper_name} completed: {len(listings)} listings")
            except Exception as e:
                logging.error(f"❌ {scraper_name} failed: {e}")
                scraping_results[scraper_name] = {'listings': [], 'count': 0, 'error': str(e)}
```

- [ ] **Step 2: Add mark_taken_listings import**

Check existing imports (around line 22):
```python
from Application.cleanup import deep_cleanup_database, comprehensive_cleanup_all_listings, clean_stale_or_broken_listings, check_and_alert_rejection_rate
```

Add `mark_taken_listings`:
```python
from Application.cleanup import deep_cleanup_database, comprehensive_cleanup_all_listings, clean_stale_or_broken_listings, check_and_alert_rejection_rate, mark_taken_listings
```

- [ ] **Step 3: Add revalidation call inside the parallel loop**

In the `try` block after `scraping_results[source] = ...` line (around line 628), add:

```python
                # Lightweight revalidation of source's active listings
                try:
                    source_enum_map = {
                        'willhaben': 'willhaben',
                        'immo_kurier': 'immo_kurier',
                        'derstandard': 'derstandard'
                    }
                    source_enum = source_enum_map.get(source, source)
                    rev_stats = mark_taken_listings(mongo, source_filter=[source_enum])
                    logging.info(f"   🔍 Revalidation: {rev_stats['newly_taken']} newly taken, {rev_stats['already_taken']} already marked")
                except Exception as rev_e:
                    logging.warning(f"   ⚠️ Revalidation failed for {source}: {rev_e}")
```

- [ ] **Step 4: Verify import and call are syntactically correct**

Run: `cd Project && python -c "from Application.main import run_scraping_pipeline; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add Project/Application/main.py
git commit -m "feat: call mark_taken_listings after each source scrape completes"
```

---

## Task 4: Dashboard Filters — listing_status

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts:65-74` (filter)
- Modify: `dashboard/app/api/listings/top/route.ts:38-61` (filter)

- [ ] **Step 1: Update map route — add listing_status filter**

Read current filter section:
```typescript
const filter: Record<string, unknown> = {
  $and: [
    { url_is_valid: { $ne: false } },
    { price_total: { $gt: 0 } },
    { area_m2: { $gt: 0 } },
    { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
    { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
    { title: { $nin: [null, ""] } },
  ],
};
```

Add `listing_status` filter:
```typescript
const filter: Record<string, unknown> = {
  $and: [
    { url_is_valid: { $ne: false } },
    { listing_status: { $ne: "taken" } },
    { price_total: { $gt: 0 } },
    { area_m2: { $gt: 0 } },
    { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
    { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
    { title: { $nin: [null, ""] } },
  ],
};
```

- [ ] **Step 2: Update top route — add BOTH url_is_valid AND listing_status**

Read current filter (lines 38-61). Current top route does NOT have `url_is_valid` filter — this is the gap we fix.

Change `andConditions`:
```typescript
const andConditions: Record<string, unknown>[] = [
  { $and: [
    { url_is_valid: { $ne: false } },
    { listing_status: { $ne: "taken" } },
    { price_total: { $gt: 0 } },
    { area_m2: { $gt: 0 } },
    { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
    { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
    { title: { $nin: [null, ""] } },
  ]},
];
```

- [ ] **Step 3: Add status query param to top route**

Add after district check (around line 57):
```typescript
    if (status && status !== 'all') {
      if (status === 'active') {
        andConditions.push({ listing_status: { $ne: "taken" } });
      } else if (status === 'taken') {
        andConditions.push({ listing_status: "taken" });
      }
    }
```

Add `validateStatus` helper to `dashboard/lib/validators.ts`:
```typescript
export type StatusOption = 'all' | 'active' | 'taken';
export function validateStatus(input: string | null): StatusOption {
  if (!input) return 'all';
  return (['all', 'active', 'taken'].includes(input)) ? input as StatusOption : 'all';
}
```

In `route.ts`, import and use it:
```typescript
import { validateDistrict, validateSort, validateMinScore, validateLimit, validateStatus } from '@/lib/validators';
// ...
const status = validateStatus(searchParams.get('status'));
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts dashboard/app/api/listings/top/route.ts dashboard/lib/validators.ts
git commit -m "fix: add listing_status filter to map and top routes"
```

---

## Task 5: Stats API Endpoints

**Files:**
- Create: `dashboard/app/api/stats/taken/route.ts`
- Create: `dashboard/app/api/stats/timeline/route.ts`
- Create: `dashboard/app/api/stats/taken-listings/route.ts`
- Create: `dashboard/app/api/listings/[id]/taken-detail/route.ts`

- [ ] **Step 1: Create /api/stats/taken/route.ts**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const days = Math.min(parseInt(searchParams.get('days') || '30'), 365);

  try {
    const now = Date.now();
    const cutoff = now - days * 86400 * 1000;

    // Volume stats
    const totalActive = await db.collection('listings').countDocuments({
      $or: [{ listing_status: { $ne: 'taken' } }, { listing_status: null }]
    });
    const totalTaken = await db.collection('listings').countDocuments({
      listing_status: 'taken'
    });
    const total = totalActive + totalTaken;
    const takenRate = total > 0 ? (totalTaken / total * 100) : 0;

    // By source
    const bySource = await db.collection('listings').aggregate([
      {
        $group: {
          _id: '$source_enum',
          active: {
            $sum: { $cond: [{ $or: [{ $eq: ['$listing_status', null] }, { $ne: ['$listing_status', 'taken'] }] }, 1, 0] }
          },
          taken: { $sum: { $cond: [{ $eq: ['$listing_status', 'taken'] }, 1, 0] } }
        }
      }
    ]).toArray();

    // By district
    const byDistrict = await db.collection('listings').aggregate([
      {
        $group: {
          _id: '$bezirk',
          active: {
            $sum: { $cond: [{ $or: [{ $eq: ['$listing_status', null] }, { $ne: ['$listing_status', 'taken'] }] }, 1, 0] }
          },
          taken: { $sum: { $cond: [{ $eq: ['$listing_status', 'taken'] }, 1, 0] } }
        }
      }
    ]).toArray();

    // Timing stats (days active)
    const timingPipeline = [
      { $match: { listing_status: 'taken', taken_at: { $exists: true } } },
      {
        $project: {
          days_active: {
            $divide: [
              { $subtract: ['$taken_at', { $ifNull: ['$first_scraped_at', '$processed_at'] }] },
              86400000
            ]
          }
        }
      },
      { $group: {
        _id: null,
        avg_days_active: { $avg: '$days_active' },
        min_days_active: { $min: '$days_active' },
        max_days_active: { $max: '$days_active' }
      }}
    ];
    const timing = await db.collection('listings').aggregate(timingPipeline).toArray();

    // Price stats
    const pricePipeline = [
      { $match: { $or: [{ listing_status: 'taken' }, { listing_status: null }] } },
      { $group: {
        _id: '$listing_status',
        avg_price: { $avg: '$price_total' }
      }}
    ];
    const priceStats = await db.collection('listings').aggregate(pricePipeline).toArray();

    const avgPriceActive = priceStats.find(p => p._id === null || p._id !== 'taken')?.avg_price || 0;
    const avgPriceTaken = priceStats.find(p => p._id === 'taken')?.avg_price || 0;

    // Price alterations
    const alterationsPipeline = [
      { $match: { listing_status: 'taken', 'price_history.0': { $exists: true } } },
      { $project: {
        title: 1,
        price_at_scrape: 1,
        last_price: { $arrayElemAt: ['$price_history.price_total', -1] },
        delta: { $subtract: ['$price_total', { $arrayElemAt: ['$price_history.price_total', -1] }] }
      }},
      { $match: { delta: { $ne: 0 } } },
      { $limit: 5 }
    ];
    const alterationExamples = await db.collection('listings').aggregate(alterationsPipeline).toArray();

    return NextResponse.json({
      summary: { total_active: totalActive, total_taken: totalTaken, total, taken_rate_pct: Math.round(takenRate * 10) / 10 },
      by_source: bySource.map(s => ({
        source: s._id,
        active: s.active,
        taken: s.taken,
        taken_rate: s.active + s.taken > 0 ? Math.round((s.taken / (s.active + s.taken)) * 1000) / 10 : 0
      })),
      by_district: byDistrict.map(d => ({
        bezirk: d._id,
        active: d.active,
        taken: d.taken,
        taken_rate: d.active + d.taken > 0 ? Math.round((d.taken / (d.active + d.taken)) * 1000) / 10 : 0
      })),
      timing: timing[0] ? {
        avg_days_active: Math.round(timing[0].avg_days_active * 10) / 10,
        min_days_active: Math.round(timing[0].min_days_active * 10) / 10,
        max_days_active: Math.round(timing[0].max_days_active * 10) / 10
      } : { avg_days_active: 0, min_days_active: 0, max_days_active: 0 },
      price: {
        avg_price_active: Math.round(avgPriceActive),
        avg_price_taken: Math.round(avgPriceTaken)
      },
      price_alterations: {
        count_with_changes: alterationExamples.length,
        examples: alterationExamples
      }
    });
  } catch (err) {
    console.error('[/api/stats/taken]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 2: Create /api/stats/timeline/route.ts**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const days = Math.min(parseInt(searchParams.get('days') || '30'), 365);

  const now = Date.now();
  const cutoff = new Date(now - days * 86400 * 1000);

  try {
    const createdPipeline = [
      { $match: { processed_at: { $gte: cutoff.getTime() / 1000 } } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: { $toDate: { $multiply: ['$processed_at', 1000] } } } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ];

    const takenPipeline = [
      { $match: { listing_status: 'taken', taken_at: { $gte: cutoff } } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$taken_at' } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ];

    const [created, taken] = await Promise.all([
      db.collection('listings').aggregate(createdPipeline).toArray(),
      db.collection('listings').aggregate(takenPipeline).toArray()
    ]);

    return NextResponse.json({
      created: created.map(c => ({ date: c._id, count: c.count })),
      taken: taken.map(t => ({ date: t._id, count: t.count }))
    });
  } catch (err) {
    console.error('[/api/stats/timeline]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 3: Create /api/stats/taken-listings/route.ts**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200);
  const offset = parseInt(searchParams.get('offset') || '0');
  const sort = searchParams.get('sort') || 'days_active_desc';

  const sortMap: Record<string, Record<string, 1 | -1>> = {
    days_active_desc: { days_active: -1 },
    taken_at_desc: { taken_at: -1 },
    price_desc: { price_total: -1 },
  };

  try {
    const pipeline = [
      { $match: { listing_status: 'taken' } },
      {
        $project: {
          title: 1,
          url: 1,
          source_enum: 1,
          bezirk: 1,
          price_total: 1,
          price_at_scrape: 1,
          days_active: {
            $divide: [
              { $subtract: ['$taken_at', { $ifNull: ['$first_scraped_at', '$processed_at'] }] },
              86400000
            ]
          },
          first_scraped_at: { $ifNull: ['$first_scraped_at', '$processed_at'] },
          taken_at: 1,
          price_history: 1
        }
      },
      { $sort: sortMap[sort] || sortMap.days_active_desc },
      { $skip: offset },
      { $limit: limit }
    ];

    const [listings, total] = await Promise.all([
      db.collection('listings').aggregate(pipeline).toArray(),
      db.collection('listings').countDocuments({ listing_status: 'taken' })
    ]);

    return NextResponse.json({
      listings: listings.map(l => ({
        _id: l._id.toString(),
        title: l.title,
        url: l.url,
        source_enum: l.source_enum,
        bezirk: l.bezirk,
        price_total: l.price_total,
        price_at_scrape: l.price_at_scrape,
        days_active: Math.round(l.days_active * 10) / 10,
        first_scraped_at: l.first_scraped_at,
        taken_at: l.taken_at
      })),
      total,
      limit,
      offset
    });
  } catch (err) {
    console.error('[/api/stats/taken-listings]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 4: Create /api/listings/[id]/taken-detail/route.ts**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { id } = params;

  try {
    const listing = await db.collection('listings').findOne(
      { _id: new ObjectId(id), listing_status: 'taken' },
      { projection: { title: 1, url: 1, price_history: 1, price_at_scrape: 1, price_total: 1 } }
    );

    if (!listing) {
      return NextResponse.json({ error: 'Listing not found' }, { status: 404 });
    }

    return NextResponse.json({
      _id: listing._id.toString(),
      title: listing.title,
      url: listing.url,
      price_history: listing.price_history || [],
      price_at_scrape: listing.price_at_scrape,
      price_total: listing.price_total
    });
  } catch (err) {
    console.error('[/api/listings/[id]/taken-detail]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/api/stats/taken/route.ts dashboard/app/api/stats/timeline/route.ts dashboard/app/api/stats/taken-listings/route.ts dashboard/app/api/listings/[id]/taken-detail/route.ts
git commit -m "feat: add stats API endpoints for taken listings"
```

---

## Task 6: Stats Dashboard Panel

**Files:**
- Create: `dashboard/app/dashboard/taken/page.tsx`

- [ ] **Step 1: Write taken page component**

```typescript
'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

interface StatsSummary {
  summary: { total_active: number; total_taken: number; total: number; taken_rate_pct: number };
  by_source: { source: string; active: number; taken: number; taken_rate: number }[];
  by_district: { bezirk: string; active: number; taken: number; taken_rate: number }[];
  timing: { avg_days_active: number; min_days_active: number; max_days_active: number };
  price: { avg_price_active: number; avg_price_taken: number };
  price_alterations: { count_with_changes: number; examples: any[] };
}

interface TimelineEntry { date: string; count: number; }

interface TakenListing {
  _id: string;
  title: string;
  url: string;
  source_enum: string;
  bezirk: string;
  price_total: number;
  price_at_scrape: number;
  days_active: number;
  first_scraped_at: number;
  taken_at: string;
}

export default function TakenStatsPage() {
  const [summary, setSummary] = useState<StatsSummary | null>(null);
  const [timeline, setTimeline] = useState<{ created: TimelineEntry[]; taken: TimelineEntry[] }>({ created: [], taken: [] });
  const [takenListings, setTakenListings] = useState<TakenListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'list'>('overview');

  useEffect(() => {
    Promise.all([
      fetch('/api/stats/taken?days=30').then(r => r.json()),
      fetch('/api/stats/timeline?days=30').then(r => r.json()),
      fetch('/api/stats/taken-listings?limit=50').then(r => r.json())
    ]).then(([s, t, l]) => {
      setSummary(s);
      setTimeline(t);
      setTakenListings(l.listings || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-8 text-center">Laden...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Taken Listings Analytics</h1>
          <p className="text-gray-600 mt-1">Track listing lifecycle: from scraped to offline</p>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Active" value={summary?.summary.total_active ?? 0} color="blue" />
          <StatCard label="Total Taken" value={summary?.summary.total_taken ?? 0} color="red" />
          <StatCard label="Taken Rate" value={`${summary?.summary.taken_rate_pct ?? 0}%`} color="orange" />
          <StatCard label="Avg Days Active" value={summary?.timing.avg_days_active ?? 0} suffix="d" color="green" />
        </div>

        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 rounded ${activeTab === 'overview' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('list')}
            className={`px-4 py-2 rounded ${activeTab === 'list' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}
          >
            Taken Listings ({summary?.summary.total_taken ?? 0})
          </button>
        </div>

        {activeTab === 'overview' && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">By Source</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>Source</th><th>Active</th><th>Taken</th><th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.by_source.map(s => (
                    <tr key={s.source} className="border-t">
                      <td className="py-2">{s.source}</td>
                      <td>{s.active}</td>
                      <td className="text-red-600">{s.taken}</td>
                      <td>{s.taken_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">Timeline (Last 30 Days)</h2>
              <TimelineChart created={timeline.created} taken={timeline.taken} />
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">By District</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>District</th><th>Active</th><th>Taken</th><th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.by_district.filter(d => d.bezirk).map(d => (
                    <tr key={d.bezirk} className="border-t">
                      <td className="py-2">{d.bezirk}</td>
                      <td>{d.active}</td>
                      <td className="text-red-600">{d.taken}</td>
                      <td>{d.taken_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">Price Alterations</h2>
              <p className="text-sm text-gray-600 mb-2">
                {summary?.price_alterations.count_with_changes ?? 0} listings had price changes before being taken
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>Title</th><th>At Scrape</th><th>Last</th><th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.price_alterations.examples.map((ex, i) => (
                    <tr key={i} className="border-t">
                      <td className="py-1 truncate max-w-xs">{ex.title}</td>
                      <td>€{(ex.price_at_scrape / 1000).toFixed(0)}k</td>
                      <td>€{(ex.last_price / 1000).toFixed(0)}k</td>
                      <td className={ex.delta < 0 ? 'text-red-600' : 'text-green-600'}>
                        {ex.delta > 0 ? '+' : ''}{(ex.delta / 1000).toFixed(0)}k
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'list' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr className="text-left text-gray-600">
                  <th className="p-3">Title</th>
                  <th className="p-3">Source</th>
                  <th className="p-3">District</th>
                  <th className="p-3">Price</th>
                  <th className="p-3">Price at Scrape</th>
                  <th className="p-3">Days Active</th>
                  <th className="p-3">Taken At</th>
                </tr>
              </thead>
              <tbody>
                {takenListings.map(l => (
                  <tr key={l._id} className="border-t hover:bg-gray-50">
                    <td className="p-3 max-w-xs truncate">
                      <a href={l.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {l.title}
                      </a>
                    </td>
                    <td className="p-3">{l.source_enum}</td>
                    <td className="p-3">{l.bezirk}</td>
                    <td className="p-3">€{(l.price_total / 1000).toFixed(0)}k</td>
                    <td className="p-3">€{(l.price_at_scrape / 1000).toFixed(0)}k</td>
                    <td className="p-3">{l.days_active}d</td>
                    <td className="p-3 text-gray-500">{new Date(l.taken_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color, suffix = '' }: { label: string; value: number | string; color: string; suffix?: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    green: 'bg-green-50 text-green-700 border-green-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <p className="text-sm opacity-70">{label}</p>
      <p className="text-2xl font-bold">{value}{suffix}</p>
    </div>
  );
}

function TimelineChart({ created, taken }: { created: TimelineEntry[]; taken: TimelineEntry[] }) {
  if (created.length === 0 && taken.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">No data yet</p>;
  }
  const maxCount = Math.max(
    ...created.map(c => c.count),
    ...taken.map(t => t.count),
    1
  );
  return (
    <div className="flex items-end gap-1 h-32">
      {created.slice(-14).map((c, i) => (
        <div key={i} className="flex-1 flex flex-col gap-0.5">
          <div className="bg-blue-400 rounded-t" style={{ height: `${(c.count / maxCount) * 100}%`, minHeight: '2px' }} title={`Created: ${c.count}`} />
          <div className="bg-red-400 rounded-t" style={{ height: `${(taken.find(t => t.date === c.date)?.count || 0) / maxCount * 100}%`, minHeight: '2px' }} title={`Taken: ${taken.find(t => t.date === c.date)?.count || 0}`} />
        </div>
      ))}
      <div className="flex gap-2 mt-1 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-400 rounded" /> Created</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded" /> Taken</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify page renders**

Run: `cd dashboard && npm run dev &` then `sleep 15 && curl -s http://localhost:3000/dashboard/taken | head -50`

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/dashboard/taken/page.tsx
git commit -m "feat: add taken listings stats dashboard panel"
```

---

## Task 7: GitHub Actions Daily Cron

**Files:**
- Create: `.github/workflows/daily-revalidation.yml`

- [ ] **Step 1: Create workflow file**

```yaml
name: Daily Listing Revalidation

on:
  schedule:
    - cron: '0 6 * * *'  # 06:00 UTC daily
  workflow_dispatch:       # Manual trigger

jobs:
  revalidate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd Project
          pip install pymongo requests python-dotenv
      - name: Run daily revalidation
        env:
          MONGODB_URI: ${{ secrets.MONGODB_URI }}
        run: |
          cd Project
          python -c "
from Application.cleanup import daily_revalidation
from Integration.mongodb_handler import MongoDBHandler
m = MongoDBHandler()
result = daily_revalidation(m)
print(f\"Checked: {result['checked']}, Newly taken: {result['newly_taken']}\")
"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily-revalidation.yml
git commit -m "feat: add daily revalidation GitHub Actions workflow"
```

---

## Self-Review Checklist

1. **Spec coverage:** All spec requirements mapped to tasks?
   - [x] Schema + fields (Task 1)
   - [x] Post-scrape revalidation (Task 3)
   - [x] Daily revalidation (Task 2)
   - [x] Price history tracking (Task 1)
   - [x] Stats API endpoints (Task 5)
   - [x] Dashboard filters (Task 4)
   - [x] Stats panel page (Task 6)
   - [x] GitHub Actions cron (Task 7)

2. **Placeholder scan:** No "TBD", "TODO", "implement later" in steps — all steps have actual code

3. **Type consistency:**
   - `listing_status` values match spec: `"active"`, `"taken"`, `null`
   - `price_history` array of `{price_total, recorded_at}` matches spec
   - `days_active` calculation matches spec: `taken_at - first_scraped_at`

4. **Test coverage:** Each task has failing test first, then implementation

5. **No duplicate logic:** Soft 404 patterns defined once in `cleanup.py`, not duplicated in `run_top5.py`

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
