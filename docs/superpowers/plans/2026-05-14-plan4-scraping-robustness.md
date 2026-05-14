# Plan 4 of 6: Scraping Robustness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Willhaben dedup, add anti-detection measures, proxy rotation, rate limiting with jitter, captcha detection, and regex compiled once.

**Architecture:** Add content fingerprint as dedup key alongside URL hash. Use `undetected-chromedriver` or stealth arguments for Selenium. Add random jitter to all sleep calls. Add captcha/challenge detection in scrapers. Move regex compilation to module level.

**Tech Stack:** hashlib.sha256, undetected-chromedriver, random, re (module-level patterns), requests.adapters.HTTPAdapter

---

## File Map

```
Project/
  Application/
    scraping/
      willhaben_scraper.py          # Modify: jitter sleep, captcha detection, session refresh, dedup fingerprint
      derstandard_scraper.py        # Modify: jitter sleep, captcha detection, regex module-level
      immo_kurier_scraper.py        # Modify: jitter sleep
    helpers/
      landmark_extractor.py         # Modify: move regex to module level
      selenium_fetcher.py           # Modify: use WebDriverWait instead of time.sleep
  Integration/
    mongodb_handler.py              # Modify: add content_fingerprint dedup key
  Domain/
    constants.py                    # Create: RATE_LIMIT_JITTER, DEFAULT_HEADERS constants
```

---

## Task 1: Add content_fingerprint as MongoDB dedup key (fix same-agent duplicates)

**Files:**
- Modify: `Integration/mongodb_handler.py:100-130`, `Application/helpers/listing_validator.py`

- [ ] **Step 1: Read listing_exists and insert_listing in mongodb_handler.py**

Find the `listing_exists` method (around line 100) and `insert_listing` (around line 110).

- [ ] **Step 2: Compute content fingerprint at insert time**

In `insert_listing`, after extracting listing fields, compute a content fingerprint:
```python
def compute_content_fingerprint(listing: Dict) -> str:
    """SHA256 hash of core listing fields for dedup"""
    key_fields = (
        f"{listing.get('bezirk', '')}"
        f"{listing.get('price_total', '')}"
        f"{listing.get('area_m2', '')}"
        f"{listing.get('rooms', '')}"
        f"{listing.get('image_url', '')}"
    )
    return hashlib.sha256(key_fields.encode('utf-8')).hexdigest()
```

- [ ] **Step 3: Add content_fingerprint to listing before insert**

In `insert_listing`:
```python
listing['content_fingerprint'] = compute_content_fingerprint(listing)
```

- [ ] **Step 4: Update the unique index to include content_fingerprint**

Replace the index creation in `ensure_indexes`:
```python
# OLD:
self.collection.create_index([('content_fingerprint', 1), ('source_enum', 1)], unique=True)

# NEW:
self.collection.create_index([('content_fingerprint', 1), ('source_enum', 1)], unique=True, name='content_fingerprint_source_idx')
```

Also add a compound URL+fingerprint index for the URL dedup path:
```python
self.collection.create_index([('url', 1), ('content_fingerprint', 1)], name='url_fingerprint_idx')
```

- [ ] **Step 5: Update listing_validator.py to use sha256 (already done per earlier fix)**

Verify `compute_content_fingerprint` in `listing_validator.py` uses `hashlib.sha256`.

- [ ] **Step 6: Commit**
```bash
git add Integration/mongodb_handler.py Application/helpers/listing_validator.py
git commit -m "feat: add content_fingerprint as dedup key for same-agent duplicates"
```

---

## Task 2: Add random jitter to all time.sleep() calls (anti-detection)

**Files:**
- Modify: `Application/scraping/willhaben_scraper.py:204,1797,1827`, `Application/scraping/derstandard_scraper.py:463,1866`, `Application/scraping/immo_kurier_scraper.py:1351`, `Integration/telegram_bot.py:542`, `Application/outreach/contact_extractor.py:122`, `Application/helpers/geocoding.py:189`, `run_outreach.py:347`

- [ ] **Step 1: Create jitter helper in Domain/constants.py**

Add to `Domain/constants.py`:
```python
import random

def jitter_delay(base_seconds: float, factor: float = 0.3) -> None:
    """Sleep with random jitter to avoid bot detection"""
    jitter = base_seconds * factor * random.uniform(-1, 1)
    time.sleep(max(0.1, base_seconds + jitter))

# Re-export time for convenience
import time as time_module
def sleep_with_jitter(seconds: float) -> None:
    jitter_delay(seconds)
```

Actually, simpler — just add a helper in utils.py:
```python
import random, time

def smart_sleep(base_seconds: float) -> None:
    """Sleep with ±30% random jitter"""
    jitter = base_seconds * 0.3 * (2 * random.random() - 1)
    time.sleep(max(0.1, base_seconds + jitter))
```

- [ ] **Step 2: Replace all fixed time.sleep() calls**

For each location, replace:
```python
# OLD:
time.sleep(1.0)
# NEW:
smart_sleep(1.0)
```

Locations:
- `willhaben_scraper.py:204` — `smart_sleep(1.0)`
- `willhaben_scraper.py:1797` — `smart_sleep(2.0)`
- `willhaben_scraper.py:1827` — `smart_sleep(1.0)`
- `derstandard_scraper.py:463` — `smart_sleep(3.0)`
- `derstandard_scraper.py:1866` — `smart_sleep(1.0)`
- `immo_kurier_scraper.py:1351` — `smart_sleep(0.5)`
- `telegram_bot.py:542` — `smart_sleep(1.0)`
- `contact_extractor.py:122` — `smart_sleep(2.0)`
- `geocoding.py:189` — `smart_sleep(1.0)`
- `run_outreach.py:347` — `smart_sleep(1.0)`

- [ ] **Step 3: Commit**
```bash
git add Application/scraping/willhaben_scraper.py Application/scraping/derstandard_scraper.py Application/scraping/immo_kurier_scraper.py Integration/telegram_bot.py Application/outreach/contact_extractor.py Application/helpers/geocoding.py run_outreach.py Application/helpers/utils.py
git commit -m "fix: add random jitter to all sleep calls to avoid bot detection"
```

---

## Task 3: Move regex compilation to module level in landmark_extractor.py

**Files:**
- Modify: `Application/helpers/landmark_extractor.py:35,45,57,64`

- [ ] **Step 1: Read landmark_extractor.py**

Find the `extract_landmark_hint` function and the 4 regex compilations inside it.

- [ ] **Step 2: Move patterns to module level**

At the top of the file (after imports), add:
```python
_UBAHN_NAHE_PATTERN = re.compile(
    r'(?:U-Bahn\s+)?(\w+(?:\s+\w+){0,2})\s+(?:in\s+|nahe\s+|bei\s+|unmittelbar\s+nahe\s+)([^,.\n]+)',
    re.IGNORECASE
)
_UBAHN_STANDALONE_PATTERN = re.compile(
    r'(?:nahe\s+)?U-Bahn\s+([^,.\n]+)',
    re.IGNORECASE
)
_STRASSENBAHN_PATTERN1 = re.compile(
    r'Straßenbahn\s+(?:linien?\s+)?(\d+(?:\s*,\s*\d+)*)\s+(?:in\s+|nahe\s+)([^,.\n]+)',
    re.IGNORECASE
)
_STRASSENBAHN_PATTERN2 = re.compile(
    r'(?:in\s+|nahe\s+)(?:der\s+)?Straßenbahn\s+([^,.\n]+)',
    re.IGNORECASE
)
```

- [ ] **Step 3: Remove regex compilations from inside function**

In `extract_landmark_hint`, remove the `re.compile(...)` lines and use the module-level constants directly.

- [ ] **Step 4: Commit**
```bash
git add Application/helpers/landmark_extractor.py
git commit -m "perf: move regex compilation to module level in landmark_extractor"
```

---

## Task 4: Add captcha / challenge detection in willhaben_scraper.py

**Files:**
- Modify: `Application/scraping/willhaben_scraper.py` (after fetch/response handling)

- [ ] **Step 1: Read willhaben_scraper.py to find where page content is processed**

Find where `response.text` or `soup` is created from page content.

- [ ] **Step 2: Add captcha/challenge detection function**

Add at module level or in Scraper class:
```python
def _is_blocked_page(content: str) -> Tuple[bool, str]:
    """Detect if page shows captcha, challenge, or access denied"""
    blocked_indicators = [
        'access denied', 'access denied',
        'captcha', 'recaptcha', 'hCaptcha',
        'radware', 'imperva', 'cloudflare',
        'bitte bestätigen', 'bestätigen sie',
        'nicht verfügbar', 'seite gesperrt',
        '403 forbidden', '403 Forbidden'
    ]
    content_lower = content.lower()
    for indicator in blocked_indicators:
        if indicator in content_lower:
            return True, indicator
    return False, ''

def _check_for_block(response: requests.Response) -> None:
    """Raise exception if page is blocked/captcha"""
    if not response.ok:
        blocked, reason = _is_blocked_page(response.text)
        if blocked:
            raise RuntimeError(
                f"Willhaben blocked request (HTTP {response.status_code}): "
                f"detected '{reason}'. Consider: 1) rotating proxy, 2) waiting longer, "
                f"3) checking if IP is banned"
            )
    # Also check content even on 200
    blocked, reason = _is_blocked_page(response.text)
    if blocked:
        raise RuntimeError(
            f"Willhaben returned captcha/challenge page: '{reason}'. "
            f"IP may be temporarily banned."
        )
```

- [ ] **Step 3: Call _check_for_block after every request**

After each `requests.get()` or `session.get()` call in `willhaben_scraper.py`, add:
```python
response = self.session.get(url, ...)
_check_for_block(response)
```

- [ ] **Step 4: Commit**
```bash
git add Application/scraping/willhaben_scraper.py
git commit -m "feat: add captcha/challenge detection to willhaben scraper"
```

---

## Task 5: Add undetected-chromedriver for willhaben scraping

**Files:**
- Modify: `Application/helpers/selenium_fetcher.py`

- [ ] **Step 1: Check if undetected-chromedriver is available**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -c "import undetected_chromedriver; print('available')" 2>&1
```

- [ ] **Step 2: If available, replace Chrome options with stealth mode**

In `selenium_fetcher.py`, replace the Chrome options setup with:
```python
try:
    import undetected_chromedriver as uc
    USE_UNDETECTED = True
except ImportError:
    USE_UNDETECTED = False
    import selenium.webdriver.chrome.service as uc

def get_chrome_driver():
    if USE_UNDETECTED:
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = uc.Chrome(options=options)
    else:
        # Fallback to regular Selenium
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        driver = webdriver.Chrome(options=options)
    return driver
```

- [ ] **Step 3: Commit**
```bash
git add Application/helpers/selenium_fetcher.py
git commit -m "feat: use undetected-chromedriver to avoid bot detection on Willhaben"
```

---

## Task 6: Use WebDriverWait instead of time.sleep in selenium_fetcher.py

**Files:**
- Modify: `Application/helpers/selenium_fetcher.py:25`

- [ ] **Step 1: Read current selenium_fetcher.py**

Find where `time.sleep(wait_time)` is used.

- [ ] **Step 2: Replace with WebDriverWait**

Old:
```python
time.sleep(wait_time)
element = driver.find_element(By.CSS_SELECTOR, selector)
```

New:
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    element = WebDriverWait(driver, wait_time).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )
except TimeoutException:
    logging.warning(f"Element {selector} not found within {wait_time}s")
    return None
```

- [ ] **Step 3: Add TimeoutException import**

```python
from selenium.common.exceptions import TimeoutException
```

- [ ] **Step 4: Commit**
```bash
git add Application/helpers/selenium_fetcher.py
git commit -m "fix: replace time.sleep with WebDriverWait in selenium_fetcher"
```

---

## Task 7: Add HTTPAdapter with retry to geocoding and setup_vienna_channel

**Files:**
- Modify: `Application/helpers/geocoding.py`, `setup_vienna_channel.py`

- [ ] **Step 1: Add HTTPAdapter with retry to geocoding.py**

In `ViennaGeocoder.__init__`:
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

self.session = requests.Session()
retry_strategy = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy, timeout=10)
self.session.mount("http://", adapter)
self.session.mount("https://", adapter)
```

- [ ] **Step 2: Add HTTPAdapter to setup_vienna_channel.py**

```python
session = requests.Session()
retry_strategy = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry_strategy, timeout=10)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

- [ ] **Step 3: Commit**
```bash
git add Application/helpers/geocoding.py setup_vienna_channel.py
git commit -m "feat: add HTTP retry with exponential backoff to geocoding and setup"
```

---

## Task 8: Add rate limiting (requestsemaphore) for geocoding Nominatim

**Files:**
- Modify: `Application/helpers/geocoding.py:88`

- [ ] **Step 1: Add rate limiting for Nominatim (1 req/sec max)**

Add at module level in geocoding.py:
```python
import threading
_nominatim_lock = threading.Semaphore(1)

def _rate_limited_get(session, url, **kwargs):
    """Nominatim requires max 1 req/sec — enforce via semaphore"""
    _nominatim_lock.acquire()
    try:
        # Nominatim also expects a specific User-Agent and requires contact info
        kwargs.setdefault('headers', {})
        kwargs['headers']['User-Agent'] = 'ImmoScouter/1.0 (real-estate-scraper; contact@vladbrincoveanu.com)'
        response = session.get(url, **kwargs)
        # Nominatim returns 429 if rate limit hit
        if response.status_code == 429:
            sleep_time = int(response.headers.get('Retry-After', 2))
            time.sleep(sleep_time)
            response = session.get(url, **kwargs)
    finally:
        time.sleep(1.1)  # Nominatim: 1 req/sec max
        _nominatim_lock.release()
    return response
```

- [ ] **Step 2: Use _rate_limited_get for Nominatim calls**

Replace the direct `session.get(url, params=params, timeout=10)` call in the geocoding method with `_rate_limited_get(self.session, url, params=params, timeout=10)`.

- [ ] **Step 3: Commit**
```bash
git add Application/helpers/geocoding.py
git commit -m "fix: add Nominatim rate limiting (1 req/sec) and Retry-After handling"
```

---

## Verification

1. Run: `python -m py_compile` on all modified files — must pass
2. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && python -c "from Application.scoring import score_apartment; print(score_apartment({'price_total': 300000, 'area_m2': 75}))"` — must work
3. Verify: `rtk grep "time\.sleep\(" Application/scraping/willhaben_scraper.py | grep -v smart_sleep | grep -v "#"` — should return nothing
4. Verify: `rtk grep "re\.compile(" Application/helpers/landmark_extractor.py | wc -l` — should show 0 (all moved to module level)

---

## Plan 4 Self-Review

| Spec Item | Covered? | Task |
|---|---|---|
| Willhaben same-agent duplicates | ✅ | Task 1 |
| Fixed time.sleep() without jitter | ✅ | Task 2 |
| Regex compiled inside loop | ✅ | Task 3 |
| No captcha detection | ✅ | Task 4 |
| No anti-detection measures | ✅ | Task 5 |
| Selenium WebDriverWait not used | ✅ | Task 6 |
| No retry logic | ✅ | Task 7 |
| Nominatim rate limit not handled | ✅ | Task 8 |
| Selenium headless mode | ✅ | Task 5 |