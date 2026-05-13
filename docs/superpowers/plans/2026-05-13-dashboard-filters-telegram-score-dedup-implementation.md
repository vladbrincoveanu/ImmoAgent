# Dashboard Filters + Telegram Score + Telegram Dedup + Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 4 independent changes: (1) dashboard filters, (2) telegram score display, (3) telegram dedup cooldown, (4) data cleanup migration + scraper fix.

**Architecture:** Changes are in 3 layers: dashboard API routes (TypeScript), main.py Telegram loop (Python), GLOBAL_VALIDATION (Python), cleanup script (Python), Willhaben scraper (Python). All are independent — no cross-layer coupling.

**Tech Stack:** TypeScript (Next.js API routes), Python (main.py, buyer_profiles.py, telegram_bot.py, willhaben_scraper.py, cleanup script), MongoDB.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard/app/api/listings/map/route.ts` | Modify | Raise price floor to 2500, add title guard |
| `dashboard/app/api/listings/top/route.ts` | Modify | Raise price floor to 2500, add title guard |
| `Project/Integration/telegram_bot.py` | Modify | Restore score display after address+price |
| `Project/Application/main.py` | Modify | Add 7-day dedup cooldown check before scoring |
| `Project/Application/buyer_profiles.py` | Modify | Change min_price_per_m2: 1000 → 2500 |
| `Project/scripts/cleanup_empty_titles.py` | Create | Migration cleanup script |
| `Project/Application/scraping/willhaben_scraper.py` | Modify | Skip /neubauprojekt/ URLs |
| `Tests/test_cleanup.py` | Create | Unit tests for cleanup script |

---

## Task 1: Dashboard map/route.ts — Raise price floor + title guard

**Files:**
- Modify: `dashboard/app/api/listings/map/route.ts:70`

- [ ] **Step 1: Change 1000 → 2500 in $expr filter**

Change line 70:
```typescript
// Before
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 1000] } },

// After
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
```

- [ ] **Step 2: Add title guard to $and array**

Add after the price filter (after line 71):
```typescript
{ title: { $nin: [null, ""] } },
```

- [ ] **Step 3: Verify no TypeScript errors**

```bash
cd dashboard && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/api/listings/map/route.ts
git commit -m "feat(dashboard): raise price floor to 2500, filter empty titles in map route"
```

---

## Task 2: Dashboard top/route.ts — Raise price floor + title guard

**Files:**
- Modify: `dashboard/app/api/listings/top/route.ts:46`

- [ ] **Step 1: Change 1000 → 2500 in $expr filter**

Change line 46:
```typescript
// Before
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 1000] } },

// After
{ $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
```

- [ ] **Step 2: Add title guard to $and array**

Add after the price filter (after line 48):
```typescript
{ title: { $nin: [null, ""] } },
```

- [ ] **Step 3: Verify no TypeScript errors**

```bash
cd dashboard && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/api/listings/top/route.ts
git commit -m "feat(dashboard): raise price floor to 2500, filter empty titles in top route"
```

---

## Task 3: GLOBAL_VALIDATION min_price_per_m2 Update

**Files:**
- Modify: `Project/Application/buyer_profiles.py:315`

- [ ] **Step 1: Change min_price_per_m2 from 1000 to 2500**

Change line 315:
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

- [ ] **Step 2: Verify the change**

```bash
cd Project && python -c "from Application.buyer_profiles import GLOBAL_VALIDATION; print(GLOBAL_VALIDATION['min_price_per_m2'])"
```
Expected: `2500`

- [ ] **Step 3: Commit**

```bash
git add Project/Application/buyer_profiles.py
git commit -m "feat(validation): raise min_price_per_m2 from 1000 to 2500 to filter Neubauprojekt aggregate pages"
```

---

## Task 4: Telegram Score Display

**Files:**
- Modify: `Project/Integration/telegram_bot.py:395-397`

- [ ] **Step 1: Uncomment and move score line after address+price block**

Find lines 395-397 (commented out):
```python
        # Score (REMOVED - no longer displayed in Telegram messages)
        # if score is not None:
        #     message_parts.append(f"🔥 <b>Score:</b> <b>{score}</b>")
```

Remove those lines and add after the address+price block (after line 350, before year_built block around line 352):
```python

        # 🔥 Score (after address+price, per approved design)
        if score is not None:
            message_parts.append(f"🔥 Score: {score:.0f}")
```

- [ ] **Step 2: Verify formatting**

```bash
cd Project && python -c "
from Integration.telegram_bot import TelegramBot
bot = TelegramBot('fake_token', 'fake_chat')
msg = bot._format_property_message({'address': 'Teststr 1', 'price_total': 500000, 'score': 82})
assert '🔥 Score: 82' in msg, f'Score not found in: {msg}'
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add Project/Integration/telegram_bot.py
git commit -m "feat(telegram): restore score display after address+price"
```

---

## Task 5: Telegram 7-Day Dedup Cooldown

**Files:**
- Modify: `Project/Application/main.py:649` (at top of scoring loop)

- [ ] **Step 1: Read current loop structure**

```bash
grep -n "for listing in all_listings" Project/Application/main.py
```
Expected: line 649

- [ ] **Step 2: Add dedup check before scoring**

Add this block at the top of the `for listing in all_listings:` loop (after line 649):
```python

            # 7-day Telegram dedup cooldown — check BEFORE scoring to skip CPU for recently-sent listings
            SEVEN_DAYS = 7 * 86400
            if mongo.collection:
                doc = mongo.collection.find_one({"url": listing.url}, {"sent_to_telegram_at": 1})
                last_sent = doc.get("sent_to_telegram_at") if doc else None
                if last_sent and (time.time() - last_sent) < SEVEN_DAYS:
                    logging.info(f"⏭️  Skipping '{listing.title}' — sent {int((time.time()-last_sent)/86400)}d ago")
                    # Still calculate score for MongoDB storage
                    if telegram_bot:
                        score = telegram_bot.calculate_listing_score(listing.__dict__)
                        listing.score = score
                    continue
```

- [ ] **Step 3: Verify import time is available (already imported)**

```bash
grep -n "^import time\|from time import" Project/Application/main.py | head -3
```
Expected: `import time` somewhere (check line ~15)

- [ ] **Step 4: Commit**

```bash
git add Project/Application/main.py
git commit -m "feat(telegram): add 7-day dedup cooldown check before scoring"
```

---

## Task 6: Cleanup Migration Script

**Files:**
- Create: `Project/scripts/cleanup_empty_titles.py`
- Create: `Tests/test_cleanup.py`

- [ ] **Step 1: Create the cleanup script**

Create `Project/scripts/cleanup_empty_titles.py`:
```python
#!/usr/bin/env python3
"""
Cleanup migration script: remove listings with empty titles or sub-threshold price/m².
Also re-scrapes candidates to recover from transient failures.

Usage:
    python scripts/cleanup_empty_titles.py       # dry-run (print count only)
    python scripts/cleanup_empty_titles.py --confirm  # actual delete
"""
import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Integration.mongodb_handler import MongoDBHandler
from Application.scraping.willhaben_scraper import WillhabenScraper
from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

CLEANUP_QUERY = {
    '$or': [
        { 'title': '' },
        { 'title': None },
        { 'title': { '$exists': False } },
        { 'price_per_m2': { '$lt': 2500 } },
        { 'url': { '$regex': '/neubauprojekt/' } },
    ]
}


def rescrape_listing(url: str, source_enum: str) -> Optional[Dict]:
    """Try to re-scrape a listing using source-specific scraper. Returns listing dict or None."""
    config = load_config()
    scrapers = {
        'willhaben': WillhabenScraper(config),
        'immo_kurier': ImmoKurierScraper(config),
        'derstandard': DerStandardScraper(config),
    }
    scraper = scrapers.get(source_enum, scrapers.get('willhaben'))
    if not scraper:
        return None
    try:
        listing = scraper.scrape_single_listing(url)
        if listing and listing.title and listing.price_per_m2 and listing.price_per_m2 >= 2500:
            return listing.__dict__
        return None
    except Exception as e:
        logger.debug(f"Re-scrape failed for {url}: {e}")
        return None


def process_listing(listing: Dict, dry_run: bool, scrapers: dict) -> Optional[str]:
    """Process one listing. Returns reason string if deleted, None if kept."""
    url = listing.get('url', '')
    title = listing.get('title', '')
    price_per_m2 = listing.get('price_per_m2')
    source_enum = listing.get('source_enum', 'willhaben')

    # Try re-scrape if source_enum is known
    if source_enum in scrapers and url:
        scraped = rescrape_listing(url, source_enum)
        if scraped:
            logger.info(f"✅ Re-scraped successfully, updating: {url}")
            return None  # Keep

    # Delete reasons
    if not title or title in ('', None):
        return "empty title"
    if price_per_m2 is not None and price_per_m2 < 2500:
        return f"price_per_m2 {price_per_m2:.0f} < 2500"
    if '/neubauprojekt/' in url:
        return "neubauprojekt aggregate page"
    return None


def main():
    parser = argparse.ArgumentParser(description='Cleanup listings with empty titles or bad price data')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default is dry-run)')
    parser.add_argument('--workers', type=int, default=5, help='Parallel workers (default 5)')
    args = parser.parse_args()

    config = load_config()
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))

    if not mongo.collection:
        logger.error("MongoDB not available")
        return

    logger.info(f"Finding cleanup candidates...")
    candidates = list(mongo.collection.find(CLEANUP_QUERY))
    logger.info(f"Found {len(candidates)} candidates")

    if not candidates:
        logger.info("Nothing to clean up")
        return

    if dry_run := not args.confirm:
        logger.info(f"[DRY RUN] Would process {len(candidates)} listings")

    # Init scrapers for re-scrape
    scrapers = {}
    for name, cls in [('willhaben', WillhabenScraper), ('immo_kurier', ImmoKurierScraper), ('derstandard', DerStandardScraper)]:
        try:
            scrapers[name] = cls(config)
        except Exception as e:
            logger.debug(f"Could not init {name} scraper: {e}")

    to_delete: List[str] = []
    to_update: List[Dict] = []
    audit_entries: List[str] = []

    def process_one(candidate: Dict) -> tuple:
        reason = process_listing(candidate, dry_run, scrapers)
        if reason:
            return (candidate.get('url', 'unknown'), reason)
        return None

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, c): c for c in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result:
                url, reason = result
                to_delete.append(url)
                audit_entries.append(f"{url} — {reason}")

    # Audit log
    if audit_entries:
        ts = time.strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(os.path.dirname(__file__), '..', 'log', f'cleanup_empty_titles_{ts}.log')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'w') as f:
            f.write('\n'.join(audit_entries))
        logger.info(f"Audit log: {log_path}")

    if not args.confirm:
        logger.info(f"[DRY RUN] Would delete {len(to_delete)} listings")
        return

    if to_delete:
        result = mongo.collection.delete_many({'url': {'$in': to_delete}})
        logger.info(f"Deleted {result.deleted_count}/{len(to_delete)} listings")

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run dry-run to verify it finds candidates**

```bash
cd Project && python scripts/cleanup_empty_titles.py 2>&1 | head -10
```
Expected: Finds N candidates (or 0 if DB is clean)

- [ ] **Step 3: Commit**

```bash
git add Project/scripts/cleanup_empty_titles.py
git commit -m "feat(cleanup): add cleanup_empty_titles migration script"
```

---

## Task 7: Willhaben Scraper Neubauprojekt Skip

**Files:**
- Modify: `Project/Application/scraping/willhaben_scraper.py`

- [ ] **Step 1: Find where to add skip check**

The skip should be in `scrape_single_listing` at the top of the method, right after the `_fetch_with_retry` check:
```python
if '/neubauprojekt/' in url:
    logger.info(f"⏭️  Skipping Neubauprojekt aggregate page: {url}")
    return None
```

Insert after line 362 (after `if not response: return None`):
```python

            # Skip Neubauprojekt aggregate pages — these show project-level data, not unit data
            if '/neubauprojekt/' in url:
                logger.info(f"⏭️  Skipping Neubauprojekt aggregate page: {url}")
                return None
```

- [ ] **Step 2: Verify no import error**

```bash
cd Project && python -c "from Application.scraping.willhaben_scraper import WillhabenScraper; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add Project/Application/scraping/willhaben_scraper.py
git commit -m "feat(willhaben): skip neubauprojekt aggregate pages in scrape_single_listing"
```

---

## Task 8: Dashboard UI Testing

**Files:** Dashboard project

- [ ] **Step 1: Start dev server**

```bash
cd dashboard && npm run dev &
sleep 15
```

- [ ] **Step 2: Run smoke tests**

```bash
cd dashboard && npx playwright test tests/smoke.spec.ts --reporter=list 2>&1 | tail -20
```
Expected: all tests pass with 0 console errors

- [ ] **Step 3: Stop dev server**

```bash
pkill -f "next dev"
```

---

## Success Criteria

- [ ] `dashboard/app/api/listings/map/route.ts` — price floor is 2500, title guard added
- [ ] `dashboard/app/api/listings/top/route.ts` — price floor is 2500, title guard added
- [ ] `telegram_bot.py` — score appears in Telegram messages after address+price
- [ ] `main.py` — cooldown check runs before scoring, skips recently-sent listings
- [ ] `buyer_profiles.py` — `min_price_per_m2` is 2500
- [ ] `cleanup_empty_titles.py` — dry-run prints count without deleting
- [ ] `willhaben_scraper.py` — `scrape_single_listing` returns None for `/neubauprojekt/` URLs
- [ ] Playwright smoke tests: all pass with 0 console errors