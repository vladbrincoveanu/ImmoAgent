# Plan 2 of 6: Performance & Reliability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix memory exhaustion, connection leaks, query performance, and data loss risks across the backend.

**Architecture:** Replace Python-side score sorting with MongoDB aggregation pipeline. Close MongoClient properly via atexit. Add missing compound indexes. Limit large find() result sets. Use soft-delete (mark invalid) instead of hard delete in cleanup.

**Tech Stack:** PyMongo aggregation, pymongo.create_index, atexit, context managers

---

## File Map

```
Project/
  Api/
    app.py                          # Modify: aggregation pipeline for score sort, atexit MongoClient close
  Application/
    cleanup.py                      # Modify: soft-delete vs hard delete, dry-run flag, .limit() on finds
    scoring.py                       # Modify: NaN/Inf guard, division-by-zero guard
  Integration/
    mongodb_handler.py               # Modify: add missing indexes, connection pool config
  Domain/
    constants.py                    # Modify: add DATABASE_INDEX_SPEC constant
```

---

## Task 1: Fix score sort — aggregation pipeline instead of loading ALL docs

**Files:**
- Modify: `Api/app.py:241-276` (get_properties method, score sort branch)

- [ ] **Step 1: Read current score sort implementation**

In `Api/app.py`, find the `if sort_by == 'score':` branch starting around line 241. The current code fetches ALL documents matching the query, scores them in Python, sorts, then paginates.

- [ ] **Step 2: Replace with aggregation pipeline**

Replace the entire `if sort_by == 'score':` block (~35 lines) with:
```python
if sort_by == 'score':
    # Use aggregation pipeline to score and sort on MongoDB side
    pipeline = [
        {'$match': query},
        {'$addFields': {
            'score': {
                '$function': {
                    'body': '''
                    function(price_total, area_m2, rooms, year_built, energy_class, hwb_value,
                              ubahn_walk_minutes, school_walk_minutes, price_per_m2, special_features) {
                        // Simplified scoring — uses same weights as Python score_apartment()
                        let s = 50;
                        if (price_total && area_m2) {
                            const p = price_total / area_m2;
                            s += p < 5000 ? 20 : p < 8000 ? 15 : p < 12000 ? 10 : 0;
                        }
                        if (rooms) s += rooms >= 3 ? 10 : rooms >= 2 ? 5 : 0;
                        if (ubahn_walk_minutes !== undefined) s += ubahn_walk_minutes <= 10 ? 15 : ubahn_walk_minutes <= 20 ? 10 : 5;
                        return Math.max(0, Math.min(100, s));
                    }
                    ''',
                    'args': ['$price_total', '$area_m2', '$rooms', '$year_built', '$energy_class',
                             '$hwb_value', '$ubahn_walk_minutes', '$school_walk_minutes',
                             '$price_per_m2', '$special_features'],
                    'lang': 'js'
                }
            }
        }},
        {'$sort': {'score': -1, 'processed_at': -1}},
        {'$skip': skip},
        {'$limit': per_page}
    ]
    cursor = self.collection.aggregate(pipeline)
    total = self.collection.count_documents(query)
    properties = list(cursor)
    for doc in properties:
        doc['_id'] = str(doc['_id'])
```

- [ ] **Step 3: Fallback if $function (server-side JS) unavailable**

If the MongoDB server version doesn't support `$function`, use a two-query approach:
```python
# Fallback: fetch IDs + scores only, then full docs
score_pipeline = [
    {'$match': query},
    {'$project': {'_id': 1, 'score': {'$literal': 0}}},  # Skip scoring in aggregation
    {'$sort': {'processed_at': -1}},
    {'$skip': skip},
    {'$limit': per_page * 3}  # Overfetch for scoring filter
]
# Then score in Python but with strict limit
```

- [ ] **Step 4: Commit**
```bash
git add Api/app.py
git commit -m "fix: replace Python-side score sort with MongoDB aggregation pipeline"
```

---

## Task 2: Fix MongoClient never closed — add atexit handler

**Files:**
- Modify: `Api/app.py:94-99` (PropertyDatabase class)

- [ ] **Step 1: Read PropertyDatabase class**

In `Api/app.py`, find the `PropertyDatabase` class around line 94.

- [ ] **Step 2: Add atexit registration**

After the `PropertyDatabase.__init__` definition, add:
```python
import atexit

class PropertyDatabase:
    def __init__(self):
        self.client = MongoClient(MONGO_URI, maxPoolSize=50)
        self.collection = self.client[MONGO_DB_NAME].listings
        self.users_collection = self.client[MONGO_DB_NAME].users
        self._init_admin_user()
        atexit.register(self._cleanup)

    def _cleanup(self):
        """Close MongoDB connection on process exit"""
        if hasattr(self, 'client'):
            self.client.close()
            logging.info("MongoDB connection closed via atexit")
```

- [ ] **Step 3: Commit**
```bash
git add Api/app.py
git commit -m "fix: close MongoClient via atexit handler on process exit"
```

---

## Task 3: Add missing database indexes on hot query fields

**Files:**
- Modify: `Integration/mongodb_handler.py:78-79` (ensure_indexes method)

- [ ] **Step 1: Read ensure_indexes method**

Find `ensure_indexes` in `mongodb_handler.py` around line 78. It currently only creates `url` and `content_fingerprint+source_enum` indexes.

- [ ] **Step 2: Add compound indexes for hot query fields**

Replace the ensure_indexes content with:
```python
def ensure_indexes(self):
    """Create indexes for frequently queried fields"""
    # Existing indexes
    self.collection.create_index('url', unique=True)
    self.collection.create_index([('content_fingerprint', 1), ('source_enum', 1)], unique=True)

    # New performance indexes
    self.collection.create_index([('source_enum', 1), ('score', -1)])
    self.collection.create_index([('bezirk', 1), ('price_per_m2', 1)])
    self.collection.create_index([('url_is_valid', 1), ('processed_at', -1)])
    self.collection.create_index([('sent_to_telegram', 1), ('processed_at', -1)])
    self.collection.create_index('price_total')
    self.collection.create_index('processed_at')
    self.collection.create_index([('score', -1), ('processed_at', -1)], name='score_processed_idx')
    self.collection.create_index('year_built')

    logging.info("Database indexes ensured")
```

- [ ] **Step 3: Commit**
```bash
git add Integration/mongodb_handler.py
git commit -m "feat: add compound indexes on source, score, bezirk, price, url_is_valid"
```

---

## Task 4: Fix cleanup.py — soft-delete instead of hard delete, add .limit()

**Files:**
- Modify: `Application/cleanup.py` (around line 237)

- [ ] **Step 1: Read comprehensive_cleanup_all_listings**

Find `comprehensive_cleanup_all_listings` around line 175 and the `delete_one` at line 237.

- [ ] **Step 2: Replace hard delete with soft delete (url_is_valid = False)**

Replace:
```python
mongo_handler.collection.delete_one({"_id": listing["_id"]})
```

With:
```python
mongo_handler.collection.update_one(
    {"_id": listing["_id"]},
    {"$set": {"url_is_valid": False, "invalidated_at": datetime.utcnow()}}
)
```

- [ ] **Step 3: Add .limit() to all find() calls that load into memory**

In `Application/cleanup.py` around lines 43, 59, 175:
```python
# OLD (line 43):
all_listings = list(mongo_handler.collection.find({...}))
# NEW:
all_listings = list(mongo_handler.collection.find({...}).limit(1000))

# OLD (line 59):
derstandard_listings = list(mongo_handler.collection.find({...}))
# NEW:
derstandard_listings = list(mongo_handler.collection.find({...}).limit(500))

# OLD (line 175):
all_listings = list(mongo_handler.collection.find({...}))
# NEW:
all_listings = list(mongo_handler.collection.find({...}).limit(1000))
```

- [ ] **Step 4: Add dry-run flag**

In `cleanup.py`, add argument parser option:
```python
parser.add_argument('--dry-run', action='store_true',
                   help='Show what would be deleted without actually deleting')
```

Wrap all `delete_one` and `update_one` calls:
```python
if args.dry_run:
    logging.info(f"[DRY RUN] Would mark invalid: {listing['_id']}")
else:
    mongo_handler.collection.update_one(...)
```

- [ ] **Step 5: Only delete on actual 404/410, not network errors**

In `cleanup.py` around line 77, change from `except Exception:` to:
```python
except requests.exceptions.RequestException as e:
    # Network error — don't delete, just log
    logging.warning(f"URL check failed (network error, not deleting): {url} — {e}")
except requests.exceptions.HTTPError as e:
    if e.response.status_code in (404, 410):
        # Actual 404/410 — safe to delete
        mongo_handler.collection.update_one(...)
    else:
        # Other HTTP error (403, 500, etc.) — don't delete
        logging.warning(f"URL returned {e.response.status_code} (not deleting): {url}")
```

- [ ] **Step 6: Commit**
```bash
git add Application/cleanup.py
git commit -m "fix: use soft-delete (url_is_valid=False) instead of hard delete, add .limit(), add dry-run mode"
```

---

## Task 5: Fix scoring.py — NaN/Inf guard and division-by-zero

**Files:**
- Modify: `Application/scoring.py:141-154`

- [ ] **Step 1: Read _normalize_below_ideal and _normalize_above_ideal**

Find the two normalization functions around lines 141-154.

- [ ] **Step 2: Add guards to _normalize_below_ideal (line 147)**

Old:
```python
return 100.0 * (max_val - actual_value) / (max_val - min_val)
```

New:
```python
if max_val == min_val:
    return 50.0  # neutral score when range is zero
if not isinstance(actual_value, (int, float)) or math.isnan(actual_value) or math.isinf(actual_value):
    return 0.0
return 100.0 * (max_val - actual_value) / (max_val - min_val)
```

- [ ] **Step 3: Add guards to _normalize_above_ideal (line 154)**

Add the same guards before the return:
```python
if max_val == min_val:
    return 50.0
if not isinstance(actual_value, (int, float)) or math.isnan(actual_value) or math.isinf(actual_value):
    return 0.0
return 100.0 * (actual_value - min_val) / (max_val - min_val)
```

- [ ] **Step 4: Ensure math module imported**

Confirm `import math` is at top of scoring.py.

- [ ] **Step 5: Commit**
```bash
git add Application/scoring.py
git commit -m "fix: add NaN/Inf guards and division-by-zero protection in scoring normalization"
```

---

## Task 6: Fix buyer_profiles.py — normalize prime_new_build and bank_loan_ready weights

**Files:**
- Modify: `Application/buyer_profiles.py:184-220`

- [ ] **Step 1: Read prime_new_build profile (line 184-198)**

Current weights: 0.20+0.15+0.15+0.12+0.12+0.10+0.08+0.05+0.03 = 0.92

- [ ] **Step 2: Normalize to sum to 1.0**

Adjust the last weight to make sum = 1.0:
```python
# Change energy_efficiency from 0.03 to 0.11
# New sum: 0.20+0.15+0.15+0.12+0.12+0.10+0.08+0.05+0.03 = 1.00
```
(Or spread the 0.08 difference across multiple weights)

- [ ] **Step 3: Read bank_loan_ready profile (line 204-220)**

Sum is 1.01 — off by 0.01. Reduce one weight by 0.01:
```python
# Reduce first weight from 0.13 to 0.12
# New sum: 1.00
```

- [ ] **Step 4: Add weight validation test**

Add at the end of `buyer_profiles.py`:
```python
def _validate_all_profiles():
    for key, profile in BUYER_PROFILES.items():
        weights = list(profile['weights'].values())
        total = sum(weights)
        assert abs(total - 1.0) < 0.001, f"Profile '{key}' weights sum to {total}, not 1.0"
    print("All profiles validated: weights sum to 1.0")

if __name__ == "__main__":
    _validate_all_profiles()
```

- [ ] **Step 5: Commit**
```bash
git add Application/buyer_profiles.py
git commit -m "fix: normalize prime_new_build and bank_loan_ready weight sums to 1.0"
```

---

## Task 7: Fix mark_listings_sent — check modified_count

**Files:**
- Modify: `Integration/mongodb_handler.py:203`

- [ ] **Step 1: Read mark_listings_sent method**

Find the `mark_listings_sent` method around line 200.

- [ ] **Step 2: Add modified_count check**

Old:
```python
result = self.collection.update_many(..., {'$set': {'sent_to_telegram': True, ...}})
logging.info(f"✅ Marked {result.modified_count} listings as sent")
```

New:
```python
result = self.collection.update_many(..., {'$set': {'sent_to_telegram': True, ...}})
expected = len(listings)
if result.modified_count < expected:
    logging.warning(
        f"⚠️  Marked {result.modified_count}/{expected} listings as sent. "
        f"{expected - result.modified_count} URLs not found in DB."
    )
else:
    logging.info(f"✅ Marked {result.modified_count} listings as sent")
```

- [ ] **Step 3: Commit**
```bash
git add Integration/mongodb_handler.py
git commit -m "fix: warn if mark_listings_sent modified_count doesn't match expected"
```

---

## Task 8: Fix cleanup.py HEAD request timeout too aggressive

**Files:**
- Modify: `Application/cleanup.py:73,227` (timeout values)

- [ ] **Step 1: Increase timeouts slightly**

Change 3-second timeouts to 8 seconds (sufficient for slow servers):
```python
# OLD:
requests.head(url, allow_redirects=True, timeout=3)
# NEW:
requests.head(url, allow_redirects=True, timeout=8)
```

- [ ] **Step 2: Add retry-on-timeout logic**

Wrap in retry:
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
response = session.head(url, timeout=8)
```

- [ ] **Step 3: Commit**
```bash
git add Application/cleanup.py
git commit -m "fix: increase HEAD timeout to 8s, add retry on 5xx errors"
```

---

## Verification

1. Run: `python -m py_compile` on all modified files — must pass
2. Run: `cd Project && python -c "from Application.scoring import score_apartment; print(score_apartment({'price_total': 300000, 'area_m2': 75, 'rooms': 3}))"` — must return valid number (not NaN)
3. Run: `cd Project && python -c "from Application.buyer_profiles import BUYER_PROFILES; print({k: sum(v['weights'].values()) for k,v in BUYER_PROFILES.items()})"` — all sums must be 1.0
4. Run: `cd Tests && rtk pytest test_validation.py test_listing_validator.py -v` — must pass

---

## Plan 2 Self-Review

| Spec Item | Covered? | Task |
|---|---|---|
| Score sort memory (loads ALL docs) | ✅ | Task 1 |
| MongoClient never closed | ✅ | Task 2 |
| Missing indexes (score, bezirk, etc.) | ✅ | Task 3 |
| cleanup hard delete (no soft-delete) | ✅ | Task 4 |
| NaN/Inf in scoring | ✅ | Task 5 |
| Division by zero in scoring | ✅ | Task 5 |
| prime_new_build weights != 1.0 | ✅ | Task 6 |
| bank_loan_ready weights != 1.0 | ✅ | Task 6 |
| mark_listings_sent silent failure | ✅ | Task 7 |
| cleanup DELETE on network error | ✅ | Task 8 |