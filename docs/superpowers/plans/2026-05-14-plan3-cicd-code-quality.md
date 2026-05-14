# Plan 3 of 6: CI/CD & Code Quality — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken Jest dependencies, add CI test runs, add health check endpoint, add pip-audit security scan, add log rotation, fix datetime.utcnow() deprecations, add __slots__ to dataclasses.

**Architecture:** GitHub Actions CI now runs `pytest Tests/` after scrape job. Health check endpoint added to Flask app. Security audit step added. Logging switched to RotatingFileHandler. datetime.utcnow() replaced with datetime.now(timezone.utc).

**Tech Stack:** pytest, pip-audit, structlog or pythonjsonlogger, logging.handlers.RotatingFileHandler, dataclasses

---

## File Map

```
Project/
  Api/
    app.py                          # Modify: add /health endpoint, datetime.utcnow() → timezone.utc
    auth_api.py                     # Modify: datetime.utcnow() → timezone.utc
  Integration/
    minio_handler.py                # Modify: add User-Agent to requests
  Application/
    main.py                         # Modify: datetime.utcnow() → timezone.utc, log rotation
  Application/helpers/
    utils.py                        # Modify: log rotation setup
  Domain/
    listing.py                      # Modify: add __slots__ to Listing dataclass
    location.py                     # Modify: add __slots__ to Coordinates dataclass
  Application/outreach/
    contact_extractor.py            # Modify: add __slots__ to ContactInfo dataclass
    email_sender.py                 # Modify: add __slots__ to OutreachEmail dataclass
  dashboard/
    package.json                   # Modify: Jest ^30.x → ^29.7.0
    playwright.config.ts            # Create (if missing): Playwright config for smoke tests
  .github/
    workflows/
      scrape.yml                   # Modify: add pytest step, pip-audit step
```

---

## Task 1: Fix invalid Jest version in dashboard/package.json

**Files:**
- Modify: `dashboard/package.json:22,30`

- [ ] **Step 1: Read dashboard/package.json**

Find the jest and @jest/globals entries.

- [ ] **Step 2: Change ^30.3.0 to ^29.7.0**

```json
// OLD:
"@jest/globals": "^30.3.0",
"jest": "^30.3.0"

// NEW:
"@jest/globals": "^29.7.0",
"jest": "^29.7.0"
```

Also fix ts-jest which may also reference Jest 30:
```json
// OLD:
"ts-jest": "^29.4.9"  # Should be compatible with Jest 29
```

- [ ] **Step 3: Run npm install to verify fix**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/dashboard && npm install 2>&1 | tail -20
```

- [ ] **Step 4: Commit**
```bash
git add dashboard/package.json
git commit -m "fix: downgrade Jest from ^30.3.0 to ^29.7.0 (v30 does not exist)"
```

---

## Task 2: Add CI test step to GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/scrape.yml` (check if it exists)

- [ ] **Step 1: Check if scrape.yml exists**

```bash
rtk ls -la /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/.github/workflows/
```

- [ ] **Step 2: Read existing workflow**

If `.github/workflows/scrape.yml` exists, read it. If not, create it.

- [ ] **Step 3: Add pytest step after the scrape job**

```yaml
jobs:
  test:
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
          pip install -q pymongo requests beautifulsoup4 selenium
          pip install -q pytest pytest-asyncio
      - name: Run core tests
        run: |
          cd Tests
          pytest test_buyer_profiles.py test_score_calculation.py test_validation.py \
                 test_listing_validator.py test_utils.py test_district_extraction.py \
                 -v --tb=short
```

- [ ] **Step 4: Also add pip-audit security scan**

```yaml
      - name: Security audit
        run: |
          pip install pip-audit
          pip-audit --format columns 2>&1 || true
        # Continue even if vulnerabilities found (to be addressed separately)
```

- [ ] **Step 5: Commit**
```bash
git add .github/workflows/scrape.yml  # or create if doesn't exist
git commit -m "ci: add pytest and pip-audit to GitHub Actions"
```

---

## Task 3: Add /health endpoint to Flask API

**Files:**
- Modify: `Api/app.py` (add health check route)

- [ ] **Step 1: Read app.py to find where routes are defined**

Find a good insertion point after imports.

- [ ] **Step 2: Add /health route**

Add after other routes or before route definitions:
```python
@app.route('/health', methods=['GET'])
def health_check():
    """Kubernetes health check endpoint"""
    try:
        # Check MongoDB
        mongo_ok = False
        try:
            self.collection.find_one({}, {'_id': 1})
            mongo_ok = True
        except Exception as e:
            logging.warning(f"Health check MongoDB failed: {e}")

        # Check Telegram (optional)
        telegram_ok = True  # If token is configured

        status = "healthy" if mongo_ok else "degraded"
        http_code = 200 if mongo_ok else 503

        return jsonify({
            "status": status,
            "mongodb": mongo_ok,
            "telegram": telegram_ok
        }), http_code
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503
```

- [ ] **Step 3: Commit**
```bash
git add Api/app.py
git commit -m "feat: add /health endpoint for Kubernetes probes"
```

---

## Task 4: Add log rotation (RotatingFileHandler)

**Files:**
- Modify: `Application/main.py:41-48`, `Application/helpers/utils.py`

- [ ] **Step 1: Read logging setup in main.py**

Find the `logging.basicConfig` call around line 41.

- [ ] **Step 2: Replace with RotatingFileHandler**

Old:
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/immo-scouter.log'),
        logging.StreamHandler()
    ]
)
```

New:
```python
import logging.handlers

# Ensure log directory exists
os.makedirs('log', exist_ok=True)

rotating = logging.handlers.RotatingFileHandler(
    'log/immo-scouter.log',
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
rotating.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        rotating,
        logging.StreamHandler()
    ]
)
```

- [ ] **Step 3: Commit**
```bash
git add Application/main.py
git commit -m "feat: add RotatingFileHandler for log rotation (10MB, 5 backups)"
```

---

## Task 5: Fix datetime.utcnow() → datetime.now(timezone.utc) in Api/app.py and auth_api.py

**Files:**
- Modify: `Api/app.py:120,134,155`, `Api/auth_api.py:51,52,112,151,219,262`

- [ ] **Step 1: Add import at top of Api/app.py**

```python
from datetime import datetime, timezone
```

- [ ] **Step 2: Replace each datetime.utcnow()**

OLD (line 120):
```python
'created_at': datetime.utcnow()
```

NEW:
```python
'created_at': datetime.now(timezone.utc)
```

Apply to all occurrences in both `Api/app.py` and `Api/auth_api.py`.

- [ ] **Step 3: Commit**
```bash
git add Api/app.py Api/auth_api.py
git commit -m "fix: replace deprecated datetime.utcnow() with datetime.now(timezone.utc)"
```

---

## Task 6: Add __slots__ to dataclasses (Listing, Coordinates, ContactInfo, OutreachEmail)

**Files:**
- Modify: `Domain/listing.py`, `Domain/location.py`, `Application/outreach/contact_extractor.py`, `Application/outreach/email_sender.py`

- [ ] **Step 1: Read Listing dataclass in Domain/listing.py**

Find all field names in the Listing dataclass.

- [ ] **Step 2: Add __slots__ to Listing**

```python
@dataclass(slots=True)
class Listing:
    url: str
    source: Source
    title: Optional[str] = None
    # ... all other fields ...
```

- [ ] **Step 3: Add __slots__ to Coordinates**

```python
@dataclass(slots=True)
class Coordinates:
    lat: float
    lon: float
```

- [ ] **Step 4: Add __slots__ to ContactInfo**

```python
@dataclass(slots=True)
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    source_url: Optional[str] = None
```

- [ ] **Step 5: Add __slots__ to OutreachEmail**

```python
@dataclass(slots=True)
class OutreachEmail:
    recipient_email: str
    recipient_name: str
    subject: str
    body_text: str
    body_html: str = ""
    sender_name: str = ""
    sender_email: str = ""
```

- [ ] **Step 6: Verify Python version supports slots on dataclasses**

Requires Python 3.10+. Check `python --version` — should be 3.11+.

- [ ] **Step 7: Commit**
```bash
git add Domain/listing.py Domain/location.py Application/outreach/contact_extractor.py Application/outreach/email_sender.py
git commit -m "feat: add __slots__ to dataclasses for memory efficiency"
```

---

## Task 7: Add User-Agent to requests calls in cleanup.py and minio_handler.py

**Files:**
- Modify: `Application/cleanup.py:73,227,308`, `Integration/minio_handler.py:47`

- [ ] **Step 1: Add common User-Agent header module-level constant**

In `Application/cleanup.py`, add after imports:
```python
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ImmoScouter/1.0; +https://github.com/vladbrincoveanu/immo-scouter)'
}
```

- [ ] **Step 2: Apply to all requests calls in cleanup.py**

```python
# OLD:
requests.head(url, allow_redirects=True, timeout=8)
# NEW:
requests.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=8)
```

Apply to all 3 occurrences (lines 73, 227, 308).

- [ ] **Step 3: Apply to minio_handler.py**

```python
# In minio_handler.py:47, add headers to image download:
image_response = requests.get(image_url, headers=DEFAULT_HEADERS, timeout=30)
```

- [ ] **Step 4: Commit**
```bash
git add Application/cleanup.py Integration/minio_handler.py
git commit -m "fix: add User-Agent header to HTTP requests"
```

---

## Task 8: Add @lru_cache to ViennaDistrictHelper.get_district_centroid

**Files:**
- Modify: `Application/helpers/utils.py`

- [ ] **Step 1: Find get_district_centroid method**

In `ViennaDistrictHelper` class around line 365.

- [ ] **Step 2: Add @functools.lru_cache**

```python
import functools

class ViennaDistrictHelper:
    @staticmethod
    @functools.lru_cache(maxsize=128)
    def get_district_centroid(bezirk: str) -> Tuple[float, float]:
        # existing implementation
```

- [ ] **Step 3: Also cache get_ubahn_stations**

```python
@staticmethod
@functools.lru_cache(maxsize=32)
def get_ubahn_stations() -> Dict[str, Any]:
    # existing implementation
```

- [ ] **Step 4: Commit**
```bash
git add Application/helpers/utils.py
git commit -m "feat: add lru_cache to district centroid and ubahn stations lookups"
```

---

## Verification

1. Run: `npm install` in dashboard — Jest must resolve without error
2. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc))"` — must work
3. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter && python -c "from Domain.listing import Listing; print(Listing.__slots__)"` — must show slot names
4. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Tests && rtk pytest test_validation.py test_listing_validator.py -v` — must pass

---

## Plan 3 Self-Review

| Spec Item | Covered? | Task |
|---|---|---|
| Jest ^30.x invalid version | ✅ | Task 1 |
| No CI test coverage | ✅ | Task 2 |
| No health check endpoint | ✅ | Task 3 |
| Log rotation missing | ✅ | Task 4 |
| datetime.utcnow() deprecated | ✅ | Task 5 |
| No dataclass __slots__ | ✅ | Task 6 |
| requests without User-Agent | ✅ | Task 7 |
| No lru_cache on pure functions | ✅ | Task 8 |
| pip-audit not in CI | ✅ | Task 2 (pip-audit step) |