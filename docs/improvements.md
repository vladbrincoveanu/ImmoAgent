# immo-scouter — Comprehensive Improvements List
Generated: 2026-05-14 | Priority: [H]igh [M]edium [L]ow

> **Status:** Items marked [ALREADY FIXED] were addressed in the 2026-05-14 audit session.
> **Status:** Items marked [STALE REF] have incorrect info that was corrected during audit.

---

## 0. Already Fixed During 2026-05-14 Audit

| # | Item | Status |
|---|------|--------|
| - | 6 bare `except:` blocks fixed (willhaben_scraper x3, derstandard_scraper, app.py, telegram_bot) | [ALREADY FIXED] |
| - | `min_price_per_m2` raised from 2500→1000 (per CLAUDE.md "ONLY source of truth") | [ALREADY FIXED] |
| - | Tests updated to match actual `is_valid_listing_data()` behavior | [ALREADY FIXED] |
| - | `hashlib.md5` → `hashlib.sha256` for fingerprinting | [ALREADY FIXED] |
| - | `app_broken.py` duplicate deleted | [ALREADY FIXED] |
| - | Token benchmark API keys now from env vars | [ALREADY FIXED] |
| - | `OutlinesAnalyzer` dead code (~160 lines) deleted from analyzer.py | [ALREADY FIXED] |
| - | Domain/constants.py created as shared home for keyword lists | [ALREADY FIXED] |
| - | BeautifulSoup `string=` → `text=` fix | [ALREADY FIXED] |
| - | `while True` in utils.py clarified (exits via `return`, not `break`) | [ALREADY FIXED] |
| - | All 53 Python files pass `python -m py_compile` | [ALREADY FIXED] |
| - | 21 core unit tests passing | [ALREADY FIXED] |
| - | Next.js dashboard builds clean | [ALREADY FIXED] |

---

## 1. Architecture & Code Quality

### 1.1 Memory Issue — Score Sort Loads ALL Docs Into RAM
**File:** `Api/app.py:241-276`
**Priority:** [H]
**Problem:** When sorting by score, all matching documents are fetched from MongoDB, scored in Python, sorted, then paginated. With 1000+ listings this exhausts memory.
**Fix:** Use MongoDB aggregation pipeline with `$addFields` + `$sort` + `$skip` + `$limit` on the server side.

### 1.2 Hardcoded Vienna Walking Times
**File:** `Application/helpers/utils.py:56-101`
**Priority:** [M]
**Problem:** ~12 districts have hardcoded estimates (e.g., "15 min" for 1110, 1120, 1130, 1140). Other 23 districts have real data from OpenRouteService.
**Fix:** Either fetch real walking times for all 23 districts, or clearly label all as estimates in UI.

### 1.3 print() Statements — 2,549 Occurrences
**Priority:** [L]
**Problem:** Heavy `print()` usage throughout codebase instead of `logging` module. Pollutes stdout, no log levels, can't suppress.
**Fix:** Replace with `logging.getLogger(__name__).info()` etc. Would require ~6h across all files.

### 1.4 No Type Hints on Most Functions
**Priority:** [L]
**Problem:** Scorers, helpers, and scrapers lack return type annotations. Makes IDE support and refactoring harder.
**Fix:** Add `from __future__ import annotations` and annotate all public functions.

---

## 2. Scraping & Data Quality

### 2.1 Willhaben Deduplication Fails for Same-Agent Listings
**File:** `Integration/mongodb_handler.py`
**Priority:** [H]
**Problem:** Listings from same agent with identical `bezirk + price + area + rooms + image_url` get different `_id` but identical content fingerprints.
**Fix:** Add content fingerprint hash (`sha256(bezirk + price_total + area_m2 + rooms + image_url)`) as dedup key alongside URL.

### 2.2 No Schema Validation on Listing Inserts
**Priority:** [H]
**Problem:** Listings are inserted into MongoDB without schema validation. Malformed data (wrong types, missing required fields) can enter the DB.
**Fix:** Use MongoDB JSON Schema validation or pydantic models for insert/update operations.

### 2.3 No Rate Limiting on Scrapers
**Priority:** [M]
**Problem:** Scrapers make requests as fast as possible. May trigger anti-bot protections.
**Fix:** Add `backoff` or `ratelimit` library with per-domain throttling (e.g., 1 req/sec per domain).

### 2.4 No Proxy Rotation
**Priority:** [M]
**Problem:** Single IP scraping. Willhaben/ImmoKurier can IP-ban.
**Fix:** Integrate residential proxy pool (e.g., BrightData, ScraperAPI) with automatic rotation on 403/429.

### 2.5 No Asyncio for Concurrent Scraping
**Priority:** [M]
**Problem:** ThreadPoolExecutor used for parallel scraping, but blocking I/O in thread pool. Python `asyncio` + `aiohttp` would be more efficient.
**Fix:** Refactor scrapers to use `asyncio` with `aiohttp` for HTTP, keeping Selenium only for JS-heavy pages.

### 2.6 No Incremental Scraper State
**Priority:** [M]
**Problem:** Each scrape starts from scratch. No tracking of "seen listings" across runs to detect new vs. old.
**Fix:** Store `last_scraped_at` + `listing_hash` in Redis or MongoDB to diff between runs.

### 2.7 DerStandard Scraper Uses Deprecated `string=` Parameter
**File:** `Application/scraping/derstandard_scraper.py`
**Priority:** [L] — [STALE REF: Already fixed in willhaben_scraper; need to verify derstandard uses `text=`]
**Fix:** Confirm `BeautifulSoup(..., string=...)` → `text=` replacement in derstandard.
**Problem:** Each scrape starts from scratch. No tracking of "seen listings" across runs to detect new vs. old.
**Fix:** Store `last_scraped_at` + `listing_hash` in Redis or MongoDB to diff between runs.

### 2.7 DerStandard Scraper Uses Deprecated `string=` Parameter
**File:** `Application/scraping/derstandard_scraper.py`
**Priority:** [L] — Already fixed in willhaben_scraper, not verified in derstandard
**Fix:** Confirm `BeautifulSoup(..., string=...)` → `text=` replacement.

---

## 3. Scoring & Business Logic

### 3.1 Mortgage Calculator Hardcoded Ratio
**File:** `Application/scraping/immo_kurier_scraper.py:45`
**Priority:** [M]
**Problem:** `new_ratio = 0.00383` is a simplified approximation, not a proper amortization formula.
**Fix:** Use standard amortization formula: `M = P * [r(1+r)^n] / [(1+r)^n - 1]` where r = monthly rate, n = total payments.

### 3.2 No Price Index / Market Trend Data
**Priority:** [L]
**Problem:** Scoring is absolute. No comparison to district average prices or market trends.
**Fix:** Enrich listings with `district_avg_price_per_m2`, `price_vs_district_avg_pct`, `market_trend` from Wiener Mieterverein or City Council data.

### 3.3 Buyer Profile Weights Not Persisted
**Priority:** [L]
**Problem:** Profiles are static dicts. No UI to customize weights per user.
**Fix:** Store user weight preferences in MongoDB, allow profile switching via dashboard.

### 3.4 No Historical Price Tracking
**Priority:** [L]
**Problem:** Price changes on existing listings (reduction, increase) are not tracked.
**Fix:** Store `price_history: [{date, price}]` array. Alert on significant reductions.

---

## 4. Infrastructure & DevOps

### 4.1 No CI/CD Test Coverage
**Priority:** [H]
**Problem:** 60+ test files exist, but no automated CI running them. GitHub Actions only runs scraper + top5.
**Fix:** Add `pytest Tests/` step to GitHub Actions workflow. Target: 21 core tests passing.

### 4.2 No Docker Container
**Priority:** [M]
**Problem:** No Dockerfile for reproducible deployments.
**Fix:** Multi-stage Dockerfile: Python 3.11 + Selenium + Chrome headless + project code.

### 4.3 Secrets in Environment Variables Only
**Priority:** [M]
**Problem:** No secret management (AWS Secrets Manager, HashiCorp Vault). If env vars lost, system fails.
**Fix:** Integrate AWS Secrets Manager or similar for prod. Keep env vars for dev only.

### 4.4 No Health Check Endpoint
**Priority:** [L]
**Problem:** No `/health` or `/ready` endpoint for Kubernetes/load balancer health probes.
**Fix:** Add `/api/health` returning `{"status": "ok", "mongodb": bool, "telegram": bool}`.

### 4.5 Log Rotation Missing
**Priority:** [L]
**Problem:** `log/immo-scouter.log` grows unbounded.
**Fix:** Use `logging.handlers.RotatingFileHandler` with 10MB max, 5 backup files.

---

## 5. Dashboard (Next.js)

### 5.1 No Server-Side Pagination on Map
**File:** `dashboard/app/api/listings/map/route.ts`
**Priority:** [H]
**Problem:** All listings loaded at once for map view. With 500+ listings, map becomes slow.
**Fix:** Tile-based loading (load listings in viewport bounds only). Use `react-leaflet` cluster.

### 5.2 No Listing Detail Page
**Priority:** [M]
**Problem:** Users can see listings in sidebar but can't click for full detail.
**Fix:** Create `/dashboard/listings/[id]` page with full listing data, score breakdown, contact button.

### 5.3 No User Authentication
**Priority:** [H]
**Problem:** Dashboard has auth code (`Api/auth_api.py`) but no login UI, no session management.
**Fix:** Add NextAuth.js or similar. Protect API routes with JWT middleware.

### 5.4 No Real-time Updates
**Priority:** [M]
**Problem:** Dashboard shows stale data until manual refresh.
**Fix:** Server-Sent Events (SSE) or WebSocket for live listing updates after scrape completes.

### 5.5 Filter State Not Persisted
**Priority:** [L]
**Problem:** Selected filters reset on page reload.
**Fix:** Store filter state in URL query params or localStorage.

### 5.6 No Dark Mode
**Priority:** [L]
**Problem:** Dashboard only has light theme.
**Fix:** Use `next-themes` for theme switching.

### 5.7 No Mobile Responsive Map
**Priority:** [M]
**Problem:** Map view broken on mobile screens due to sidebar overlap.
**Fix:** Bottom sheet pattern for mobile (already partially implemented in `BottomSheet.tsx` but not fully wired).

### 5.8 Dashboard Build Uses Old Node.js
**File:** `dashboard/package.json`
**Priority:** [L]
**Problem:** Next.js 14.2.0 is latest but dashboard may have dependencies out of date.
**Fix:** `npm outdated` + `npm update`.

---

## 6. Outreach System

### 6.1 No Unsubscribe Link in Emails
**Priority:** [H]
**Problem:** Outreach emails have no opt-out mechanism. GDPR risk.
**Fix:** Add `mailto:unsubscribe@immo-scouter?subject=unsubscribe` or use mailing list service with unsubscribe.

### 6.2 No Email Open/Click Tracking
**Priority:** [M]
**Problem:** No way to know if outreach emails are actually read.
**Fix:** Add tracking pixel + unique click IDs. Use services like Mailtrack or self-host with PostgreSQL.

### 6.3 Outreach Templates Not Localized
**Priority:** [M]
**Problem:** All emails in German only. No English templates for non-German speakers.
**Fix:** Add i18n for email templates. Support `de` + `en` based on listing agent's language.

### 6.4 No Retry Queue for Failed Sends
**Priority:** [M]
**Problem:** If SMTP fails mid-batch, failed emails are lost.
**Fix:** Store outreach jobs in MongoDB with `status: pending|sent|failed|retry`. Retry with exponential backoff.

### 6.5 Email Content Similarity Not Checked
**Priority:** [L]
**Problem:** Same template sent to all agents. No A/B testing or variation.
**Fix:** Generate 3-5 email variants and rotate, or use AI to personalize based on listing features.

---

## 7. Monitoring & Observability

### 7.1 No Metrics Dashboard
**Priority:** [M]
**Problem:** No Grafana/Prometheus metrics. Scrape success rate, API latency, DB query times unknown.
**Fix:** Add `prometheus_client` metrics. Export via `/metrics` endpoint. Import pre-built Grafana dashboard.

### 7.2 No Alerting on Scrape Failures
**Priority:** [M]
**Problem:** If scraper crashes or returns 0 listings, no alert is sent.
**Fix:** Alert if `listings_count == 0` or `scrape_duration > 2h`. Use PagerDuty, email, or Telegram bot alert.

### 7.3 No Structured Logging (JSON)
**Priority:** [L]
**Problem:** Human-readable logs, not machine-parseable. Makes log aggregation hard.
**Fix:** Use `python-json-logger` or `structlog` for JSON logs in production.

---

## 8. Data Enrichment Gaps

### 8.1 No Noise Score — Identify "Too Good to Be True" Listings
**Priority:** [M]
**Problem:** Fraudulent listings (fake cheap prices) can score high.
**Fix:** Add fraud signals: price_vs_district_avg (flag if <60% of district avg), same agent with 5+ active listings, placeholder images.

### 8.2 No Energy Certificate Parsing Standardization
**Priority:** [L]
**Problem:** HWB values parsed differently across sources. Some in kWh/m²a, some in MJ/m²a.
**Fix:** Normalize all to kWh/m²a. Add `energy_certificate_standard` field.

### 8.3 No Public Transport Score
**Priority:** [L]
**Problem:** Only walking time to U-Bahn stored. No tram/bus proximity score.
**Fix:** Use Wiener Linien API or GTFS data to compute composite transit score per listing.

### 8.4 No School Quality Data
**Priority:** [L]
**Problem:** Only walking distance to schools, not school quality/ratings.
**Fix:** Integrate with BMBF school data or Google Places ratings for nearby schools.

### 8.5 No Demographic Data Per District
**Priority:** [L]
**Problem:** No population density, age distribution, income levels per district for investment analysis.
**Fix:** Add STATISTIK AUSTRIA data per postal code.

---

## 9. Security

### 9.1 No Input Sanitization on API Filters
**File:** `Api/app.py:179-231`
**Priority:** [H]
**Problem:** Query parameters directly interpolated into MongoDB queries. Potential query injection.
**Fix:** Use pydantic schemas for all API inputs. Validate types before query building.

### 9.2 Telegram Bot Token in Logs
**Priority:** [M]
**Problem:** If `logging.DEBUG` enabled, Telegram tokens may leak in logs.
**Fix:** Redact tokens in log formatter.

### 9.3 No Rate Limiting on API Endpoints
**Priority:** [M]
**Problem:** Public API endpoints vulnerable to brute force / DoS.
**Fix:** Add `slowapi` or API gateway with rate limits (e.g., 100 req/min per IP).

### 9.4 Selenium WebDriver Headless Mode
**File:** `Application/helpers/selenium_fetcher.py`
**Priority:** [L]
**Problem:** Some scrapers may be detected because Chrome not in headless mode properly.
**Fix:** Ensure `--headless=new` flag + disable `webgl` + fake user agent.

---

## 10. Missing Features (Competitive Gap)

### 10.1 No ImmoScout24 Scraper
**Priority:** [M]
**Problem:** Austria's largest real estate portal (ImmoScout24.at) not scraped.
**Fix:** Add ImmoScout24 scraper. Note: has strong anti-bot, may need residential proxies.

### 10.2 No Price History / Reduction Alerts
**Priority:** [M]
**Problem:** No alerts when a listing's price drops.
**Fix:** Track `last_price` and alert on `price_total < last_price * 0.95`.

### 10.3 No Comparative Market Analysis (CMA)
**Priority:** [L]
**Problem:** No automatic CMA report generation for a given property vs. comps.
**Fix:** Generate PDF CMA using `reportlab` with comps from same district, same size ±20%.

### 10.4 No WhatsApp Integration
**Priority:** [L]
**Problem:** Telegram only for alerts. WhatsApp has higher open rates.
**Fix:** Add Twilio WhatsApp API or similar.

### 10.5 No WhatsFound/Feature Comparison Across Listings
**Priority:** [L]
**Problem:** Users can't compare multiple listings side-by-side.
**Fix:** Add `/compare?ids=id1,id2,id3` page with feature matrix.

### 10.6 No Mobile App
**Priority:** [L]
**Problem:** No React Native or PWA for mobile.
**Fix:** Build PWA with service worker + offline listing cache.

---

## 11. Additional Code Pattern Issues Found by Scan

### 11.1 Fixed time.sleep() Without Jitter
**Priority:** [M]
**Problem:** All sleep calls use fixed delays (1s, 2s, 3s). Predictable timing makes scraping easier to detect/throttle.
**Locations:**
- `willhaben_scraper.py:204` — `time.sleep(1.0)`
- `willhaben_scraper.py:1797` — `time.sleep(2.0)`
- `derstandard_scraper.py:463` — `time.sleep(3)`
- `derstandard_scraper.py:1866` — `time.sleep(1)`
- `immo_kurier_scraper.py:1351` — `time.sleep(0.5)`
- `telegram_bot.py:542` — `time.sleep(1)`
- `contact_extractor.py:122` — `time.sleep(2)`
- `geocoding.py:189` — `time.sleep(1)`
- `run_outreach.py:347` — `time.sleep(1)`
**Fix:** Use `random.uniform(0.8, 1.5) * base_delay` or `asyncio.sleep` with jitter.

### 11.2 requests.get() Without timeout
**Priority:** [H]
**Problem:** HTTP requests without timeout hang indefinitely on network issues.
**Locations:**
- `setup_vienna_channel.py:53,74,97` — All Telegram API calls lack `timeout=`
**Fix:** Add `timeout=10` to all `requests.get/post()` calls.

### 11.3 Large find() Result Sets Without .limit()
**Priority:** [H]
**Problem:** Loading massive result sets into memory. Combined with score sort issue.
**Locations:**
- `Api/app.py:244` — `cursor = self.collection.find(query)` (all docs loaded for score sort)
- `Application/cleanup.py:43,59,175` — `list(mongo_handler.collection.find(...))` loads ALL into memory
- `mongodb_handler.py:262` — `list(self.collection.find({"sent_to_telegram": {"$ne": True}}))` loads ALL unsent
**Fix:** Always chain `.limit()` or use aggregation pipelines with `$limit`.

### 11.4 datetime.utcnow() Deprecated in Python 3.12+
**Priority:** [L]
**Problem:** Uses deprecated `datetime.utcnow()` which gives naive datetime in local time.
**Locations:**
- `Api/app.py:120,134,155`
- `Api/auth_api.py:51,52,112,151,219,262`
**Fix:** Use `datetime.now(timezone.utc)` from Python 3.11+.

### 11.5 MongoClient Not Thread-Safe (Global Instances)
**Priority:** [M]
**Problem:** Global MongoClient instances shared across threads without proper locking.
**Locations:**
- `Application/main.py:156,405` — Two separate `pymongo.MongoClient()` instantiations
- `Api/auth_api.py:38` — Global `MongoClient`
**Fix:** Use connection pooling with `MongoClient(..., maxPoolSize=50)` and share single client instance.

### 11.6 API Routes Without Input Validation
**Priority:** [H]
**Problem:** Filter parameters passed directly to MongoDB queries without type coercion or pydantic validation.
**Locations:**
- `Api/app.py:508` — `/` route accepts 15+ filter params with no validation
- `Api/app.py:584` — `/api/properties` passes raw `filters = request.args.to_dict()` to DB
**Fix:** Use pydantic `BaseModel` for all query params. Validate types before MongoDB query.

### 11.7 No Retry Logic on HTTP Requests
**Priority:** [M]
**Problem:** Single attempt on network requests. Transient failures cause hard failures.
**Locations:**
- `setup_vienna_channel.py:53,74,97` — No retry on Telegram API calls
- `Application/helpers/fetch_vienna_schools.py:18` — No retry (has `timeout=60`)
**Fix:** Use `urllib3.util.retry.Retry` or `requests.adapters.HTTPAdapter(max_retries=3)`.

### 11.8 No @lru_cache on Expensive Pure Functions
**Priority:** [L]
**Problem:** Repeated calls to pure functions recompute every time.
**Example:** `ViennaDistrictHelper.get_district_centroid()` called repeatedly for same district.
**Fix:** Add `@functools.lru_cache(maxsize=128)` to pure data functions.

### 11.9 Hardcoded Credentials in Script Files
**Priority:** [H]
**Problem:** `setup_vienna_channel.py` uses hardcoded bot token patterns.
**Fix:** Ensure all scripts read from env vars or `load_config()`.

### 11.10 Selenium Wait Strategies
**File:** `Application/helpers/selenium_fetcher.py:25`
**Priority:** [L]
**Problem:** Uses fixed `time.sleep(wait_time)` instead of WebDriverWait with condition.
**Fix:** Use `WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "...")))`.

---

## 12. Research Findings — External Analysis

### 12.1 Willhaben Anti-Bot Detection
**URL:** https://www.willhaben.at/robots.txt
**Priority:** [H]
**Problem:** robots.txt explicitly forbids automated scraping. Uses Radware Bot Manager + hCaptcha.
**Fix:**
- Add TLS fingerprint masking via `tls-client` or `undetected-chromedriver`
- Reduce request rate to <1 req/sec
- Consider using sitemap (`/sitemap/sitemapindex-immobilien-liste.xml`) for listing discovery instead of direct search
- Rotate user agents and use stealth Chrome arguments (`--disable-blink-features=AutomationControlled`)

### 12.2 No Official Willhaben API
**URL:** https://developers.willhaben.at (does not exist)
**Problem:** No public API available. Only internal SPA APIs (`/rest/`, `/webapi/`) which are blocked.
**Fix:** No change possible — continue with Selenium approach. Focus on minimizing detectability.

### 12.3 Austrian Mortgage Standards
**URL:** https://www.immobilienscout24.at/pp/kaufpreisrechner.html
**Priority:** [M]
**Problem:** Mortgage calculator uses hardcoded `new_ratio = 0.00383` approximation. Doesn't reflect actual Austrian lending rules.
**Current Rules (since Aug 2022):**
- Minimum equity: **20%** of purchase price (incl. ancillary costs ~10%)
- Max loan term: **35 years**
- Affordability: Monthly payment ≤ **40% of household net income**
- Renovation exception: Up to **€50,000** without 20% rule
- Euribor-based (3-month or 6-month reference rate + margin 0.8%–1.5%)
- Current 3-month Euribor: ~3.2%–3.4% (check ECB rates)

**Current broken implementation locations:**
- `immo_kurier_scraper.py:46` — `new_ratio = 0.00383` (line 47: `loan_amount * new_ratio`)
- `immo_kurier_scraper.py:76` — Same hardcoded ratio in `get_payment_breakdown()`
- `immo_kurier_scraper.py:72` — Hardcoded 0.85/0.15 split, not real amortization

**Fix:** Replace with proper amortization formula:
```python
def calculate_monthly_payment(loan_amount: float, annual_rate: float, years: int) -> float:
    monthly_rate = annual_rate / 12 / 100
    num_payments = years * 12
    if monthly_rate == 0:
        return round(loan_amount / num_payments, 2)
    payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
    return round(payment, 2)
```
Also add affordability check: alert if `monthly_payment > 0.4 * household_monthly_net_income`.

### 12.4 Wiener Linien Open Data for Transit Score
**URL:** https://data.wienerlinien.at/
**Priority:** [L]
**Problem:** No transit score beyond U-Bahn walking time. Tram/bus accessibility not scored.
**Fix:** Use GTFS feed to compute weighted transit score:
- All stops (U-Bahn, tram, bus) with pedestrian routing
- Score = walking_time_to_nearest_stop * stop_frequency_multiplier
- License: CC BY 4.0 ( attribution required in UI)

### 12.5 ImmoScout24 Austria Also Has No API
**Problem:** Both Willhaben AND ImmoScout24 block automated access. Only ImmoKurier might be scrapable.
**Fix:** No change — current strategy (Selenium + Willhaben/ImmoKurier/DerStandard) is the correct approach given market constraints.

---

## 13. Additional Code Quality Issues Found

### 13.1 JSON Parsing Without Specific Exception Handling
**Priority:** [L]
**Problem:** `json.loads()` wrapped in broad `except Exception:` instead of `json.JSONDecodeError`. Hides real parsing errors.
**Locations:**
- `willhaben_scraper.py:1581` — `json.loads(script.string)` caught by generic `except Exception`
- `derstandard_scraper.py:746` — `json.loads(json_str)` completely unguarded
- `derstandard_scraper.py:126,134` — `json.load(f)` caught by `except Exception`
- `immo_kurier_scraper.py:145` — `json.load(f)` caught by `except Exception`
- `utils.py:184,222,371,396` — `json.load(f)` caught by `except Exception`
**Fix:** Catch `json.JSONDecodeError` specifically. Already done correctly in `derstandard_scraper.py:380` and `immo_kurier_scraper.py:1138`.

### 13.2 Global State Mutations
**Priority:** [M]
**Problem:** Global variables mutated at runtime, creating hidden coupling and thread-safety issues.
**Locations:**
- `Application/helpers/utils.py:92` — `global _project_root` → `_project_root = path` (line 150, 158)
- `Application/helpers/utils.py:171` — `global _config` → `_config = loaded_json` (line 186)
- `Application/scoring.py:83` — `global CRITERIA_WEIGHTS` → `CRITERIA_WEIGHTS = weights` (line 84)
**Fix:** Replace globals with:
- `_project_root` → module-level constant or `dataclasses.frozendict`
- `_config` → singleton pattern with thread-safe lazy init
- `CRITERIA_WEIGHTS` → `contextvars` (already used elsewhere in scoring, but weights are also global)

### 13.3 Hardcoded Relative File Paths
**Priority:** [L]
**Problem:** Data files hardcoded as relative paths. Breaks if working directory changes.
**Locations:**
- `willhaben_scraper.py:95` — `criteria_path: str = "criteria.json"`
- `immo_kurier_scraper.py:87` — `criteria_path: str = "criteria.json"`
- `utils.py:369` — `'ubahn_coordinates.json'`
- `utils.py:394` — `'vienna_schools.json'`
- `fetch_vienna_schools.py:37` — `"immo-scouter/vienna_schools.json"` (absolute-looking path)
**Fix:** Resolve relative to `os.path.dirname(__file__)` or project root via `utils.find_project_root()`.

### 13.4 Explicit `except Exception: pass` Empty Handlers
**Priority:** [L]
**Problem:** Silent failure on JSON parsing and data extraction errors. Hides data quality issues.
**Locations:**
- `willhaben_scraper.py:223` — `except Exception:` → `return {}`
- `willhaben_scraper.py:159` — `except Exception as e:` → `print`, `return {}`
- `willhaben_scraper.py:254,308` — `except Exception as e:` → `print`, `return None`
- `derstandard_scraper.py:140` — `except Exception as e:` → `logging.warning`, `return {}`
- `immo_kurier_scraper.py:146,213` — `except Exception as e:` → `print`, `return {}`/`return None`
- `utils.py:196,231` — `except Exception` → `print`/`continue`
- `Api/app.py:43` — `except Exception as e:` → `print`, `return {}`
**Fix:** Log at WARNING level with specific error message. Don't silently swallow errors.

### 13.5 Hardcoded Vienna Schools Path
**File:** `Application/helpers/fetch_vienna_schools.py:37`
**Priority:** [L]
**Problem:** `"immo-scouter/vienna_schools.json"` is hardcoded as relative path, not resolved from project root.
**Fix:** Use `Path(__file__).parent.parent.parent / 'data' / 'vienna_schools.json'` or similar.

### 13.6 No Dead Code Elimination
**Priority:** [L]
**Problem:** `app_broken.py` was deleted (good), but many scrapers may have unused helper methods.
**Fix:** Run `vulture` or `pyflakes` to find truly unused code across the project.

### 13.7 Regex Compiled Inside Loop (landmark_extractor.py)
**File:** `Application/helpers/landmark_extractor.py:35,45,57,64`
**Priority:** [H]
**Problem:** `extract_landmark_hint()` recompiles 4 regex patterns on every invocation (per listing).
```python
Line 35: ubahn_nahe_pattern = re.compile(...)
Line 45: ubahn_standalone_pattern = re.compile(...)
Line 57: strassenbahn_pattern1 = re.compile(...)
Line 64: strassenbahn_pattern2 = re.compile(...)
```
**Fix:** Move to module-level constants: `_UBAHN_NAHE_PATTERN = re.compile(...)`

### 13.8 requests Without User-Agent Headers
**Priority:** [M]
**Problem:** HTTP requests without User-Agent may get blocked.
**Locations:**
- `cleanup.py:73,227,308` — `requests.head()` with no headers (URL validation)
- `minio_handler.py:47` — `requests.get(image_url)` downloading content
- `analyzer.py:455` — `requests.get(url)` downloading content
- `run_top5.py:274` — `requests.get(url)` no headers
**Fix:** Add `headers={'User-Agent': 'Mozilla/5.0...'}` to all requests calls.

### 13.9 @staticmethod Creating Internal Instance (mongodb_handler.py)
**File:** `Integration/mongodb_handler.py:614`
**Priority:** [L]
**Problem:** `save_listings_to_mongodb()` is a `@staticmethod` but internally creates `MongoDBHandler()` instance — should be a module-level function.
**Fix:** Move to module level or refactor as class method.

### 13.10 Mutable Class State in Static/Utility Classes
**File:** `Application/helpers/utils.py:359-424`
**Priority:** [L]
**Problem:** `DataLoader` and `ViennaDistrictHelper` exist only as namespace for static methods — anti-pattern.
**Fix:** Convert to plain module-level functions.

### 13.11 Missing Database Indexes on Hot Query Fields
**File:** `Integration/mongodb_handler.py:78-79`
**Priority:** [M]
**Problem:** Only `url` and `content_fingerprint+source_enum` indexes exist. Hot query fields lack indexes.
**Missing indexes on:**
- `source_enum` alone (WHERE source filtering)
- `bezirk` (district filtering)
- `price_total` (sorting/filtering)
- `score` (top 5 queries)
- `sent_to_telegram` (already has query pattern)
- `processed_at` (time-based cleanup)
- `url_is_valid` (dashboard filtering)
**Fix:** Add compound indexes:
```python
collection.create_index([('source_enum', 1), ('score', -1)])
collection.create_index([('bezirk', 1), ('price_per_m2', 1)])
collection.create_index([('url_is_valid', 1), ('processed_at', -1)])
```

### 13.12 ObjectId Injection / DoS on /api/listings/[id]
**File:** `Api/app.py:360`
**Priority:** [H]
**Problem:** `property_id` passed directly to `ObjectId()` without validation. Invalid IDs cause `bson.errors.InvalidId` exceptions.
```python
doc = self.collection.find_one({'_id': ObjectId(property_id)})
```
**Fix:** Wrap in try/except, return 400 for invalid IDs:
```python
try:
    doc = self.collection.find_one({'_id': ObjectId(property_id)})
except bson.errors.InvalidId:
    return jsonify({"error": "Invalid listing ID"}), 400
```

### 13.13 Session Fixation on Login
**File:** `Api/app.py:454`
**Priority:** [M]
**Problem:** `login_user(user, remember=True)` doesn't regenerate session ID, enabling session fixation attacks.
**Fix:** Call `session.regenerate()` before `login_user()`.

### 13.14 MongoClient Never Closed (Resource Leak)
**File:** `Api/app.py:96`
**Priority:** [M]
**Problem:** `PropertyDatabase.__init__` stores `MongoClient` that lives for process lifetime. Only cleaned up via `__del__` (non-deterministic).
```python
class PropertyDatabase:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
```
**Fix:** Register atexit handler:
```python
import atexit
atexit.register(lambda: self.client.close())
```

### 13.15 Undefined `logger` Variable (mongodb_handler.py)
**File:** `Integration/mongodb_handler.py:650`
**Priority:** [H]
**Problem:** `increment_validation_failure` uses `logger.warning()` but `logger` is never defined in this module. Will raise `NameError`.
```python
except Exception as e:
    logger.warning(f"Failed to increment metrics: {e}")
```
**Fix:** Add `logger = logging.getLogger(__name__)` at module level.

### 13.16 Email Header Injection Vulnerability
**File:** `Application/outreach/email_sender.py:242`
**Priority:** [H]
**Problem:** `sender_name` used directly in `From:` header. Newline injection could add arbitrary headers.
```python
msg['From'] = f"{self.sender_name} <{self.sender_email}>"
```
If `sender_name = "Test\nBcc: victim@evil.com"` → header injection.
**Fix:** Strip newlines and validate:
```python
safe_name = self.sender_name.replace('\n', '').replace('\r', '')
msg['From'] = f"{safe_name} <{self.sender_email}>"
```

### 13.17 Weak Email Validation Regex
**File:** `Application/outreach/email_sender.py:330`
**Priority:** [M]
**Problem:** Simple regex doesn't handle IDN domains, quoted strings.
```python
if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', contact_email):
```
**Fix:** Use `email.utils.parseaddr()` or `email_validator` library.

### 13.18 SMTP Without TLS Context (MITM Vulnerability)
**File:** `Application/outreach/email_sender.py:258-261`
**Priority:** [M]
**Problem:** `starttls()` without SSL context check vulnerable to MITM.
```python
server.starttls()  # Context not verified
```
**Fix:** Use `ssl.create_default_context()`:
```python
context = ssl.create_default_context()
with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
    server.starttls(context=context)
```

### 13.19 Wildcard CORS Without Origin Restriction
**File:** `Api/auth_api.py:25`
**Priority:** [M]
**Problem:** `CORS(app)` allows all origins. Enables CSRF and unauthorized cross-origin access.
**Fix:** Specify explicit origins:
```python
CORS(app, origins=['https://your-domain.com'], supports_credentials=True)
```

### 13.20 Default MongoDB URIs Throughout Codebase
**Priority:** [H]
**Problem:** Multiple files default to `mongodb://localhost:27017/` if env var unset. App silently connects to local MongoDB instead of failing fast.
**Locations:** `app.py:89`, `mongodb_handler.py:37`, `main.py:151`, `willhaben_scraper.py:132,148`, `derstandard_scraper.py:107`, `immo_kurier_scraper.py:125,137`, `run_top5.py:596`, `run_outreach.py:261`, `auth_api.py:32`, `production.py:35,101`, `utils.py:240`
**Fix:** Remove defaults. Require `MONGODB_URI` env var explicitly. Fail fast if missing.

### 13.21 OpenRouteService API Called Without API Key
**File:** `Application/helpers/geocoding.py:457-471`
**Priority:** [H]
**Problem:** API call succeeds with 403 because headers are commented out:
```python
# 'Authorization': 'YOUR_FREE_API_KEY'  # Commented out!
```
Walking distance calculations silently fall back to straight-line.
**Fix:** Add `ORS_API_KEY` env var with required status and warning if missing.

### 13.22 Hardcoded Secret Keys in production.py
**Priority:** [H]
**Locations:**
- `production.py:13` — `SECRET_KEY = 'your-secret-key-change-this-in-production'`
- `production.py:39` — `ADMIN_PASSWORD = 'admin123'`
- `production.py:88` — `SECRET_KEY = 'dev-secret-key-change-in-production'`
- `production.py:105` — `ADMIN_PASSWORD = 'admin123'`
- `auth_api.py:28` — `SECRET_KEY = 'your-super-secret-key-change-this-in-production'`
**Fix:** All must come from env vars. Fail if not set in production.

### 13.23 Invalid Jest Version in package.json
**File:** `dashboard/package.json:22,30`
**Priority:** [H]
**Problem:** Jest ^30.3.0 does not exist. Latest is 29.x. `npm install` will fail.
```json
"@jest/globals": "^30.3.0",
"jest": "^30.3.0"
```
**Fix:** Change to `"jest": "^29.7.0"` and `"@jest/globals": "^29.7.0"`.

### 13.24 No Rate Limiting on Any Flask Endpoint
**Priority:** [H]
**Problem:** All API routes vulnerable to brute-force and DoS. No `flask-limiter` or similar.
**Fix:** Add `flask-limiter` with Redis backend:
```python
from flask_limiter import Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
```

### 13.25 Input Validation on Filter Parameters Can Crash Server
**File:** `Api/app.py:179-221`
**Priority:** [H]
**Problem:** `int(filters['price_min'])` raises `ValueError` on non-numeric input → 500 error.
```python
if filters.get('price_min'):
    query['price_total'] = {'$gte': int(filters['price_min'])}  # Crashes if 'abc'
```
**Fix:** Use pydantic validation or safe conversion:
```python
try:
    query['price_total'] = {'$gte': int(filters['price_min'])}
except (ValueError, TypeError):
    pass  # Skip invalid filter
```

### 13.26 PropertyDatabase Init Failure Crashes Entire Flask App
**File:** `Api/app.py:104`
**Priority:** [M]
**Problem:** `_init_admin_user()` raises exception if MongoDB down → Flask app won't start.
**Fix:** Wrap in try/except with graceful degradation.

### 13.27 CORS Configured But Not Applied to Main App
**File:** `Api/auth_api.py:25`, `production.py:55`
**Priority:** [L]
**Problem:** `CORS_ORIGINS` defined in `ProductionConfig` but never applied to main `app.py` Flask instance.
**Fix:** Either integrate or remove dead config.

### 13.28 Requests Security: Known CVEs in requests Library
**Priority:** [M]
**Problem:** `requests` library has known CVEs (see https://github.com/psf/requests/security/advisories):
- GHSA-gc5v-m9x4-r6x2 (Mar 2026): Insecure Temp File Reuse
- GHSA-9hjg-9r4m-mvj7 (Jun 2025): .netrc credentials leak
- GHSA-j8r2-6x86-q33q (May 2023): Proxy-Authorization header leak
- GHSA-9wx4-h78v-vm56 (May 2024): verify=False doesn't verify
**Fix:** Run `pip-audit` in CI, update `requests` to latest. Avoid `verify=False`.

### 13.29 No pip-audit / Safety Check in CI
**Priority:** [M]
**Problem:** No automated scanning for known CVE vulnerabilities in dependencies.
**Fix:** Add to GitHub Actions:
```yaml
- name: Security audit
  run: pip install pip-audit && pip-audit
```

### 13.30 Nominatim Rate Limit Not Handled
**File:** `Application/helpers/geocoding.py:88`
**Priority:** [M]
**Problem:** Nominatim strict rate limit (1 req/sec). No `Retry-After` header handling. Could get IP banned.
**Fix:** Add delay and respect `Retry-After`:
```python
if 'Retry-After' in response.headers:
    time.sleep(int(response.headers['Retry-After']))
else:
    time.sleep(1.1)
```

### 13.31 No Health Check Endpoint
**Priority:** [H]
**Problem:** No `/health` or `/ready` endpoint for Kubernetes probes.
**Fix:** Add:
```python
@app.route('/health')
def health():
    mongodb_ok = check_mongo_connection()
    return {"status": "ok" if mongodb_ok else "degraded", "mongodb": mongodb_ok}
```

### 13.32 Geocoding Session Never Closed
**File:** `Application/helpers/geocoding.py:11`
**Priority:** [L]
**Problem:** `ViennaGeocoder` creates `requests.Session` never explicitly closed.
**Fix:** Add `self.session.close()` in `__del__` or use context manager.

### 13.33 `cleanup.py` Deletes Listing on Any HEAD Request Failure
**File:** `Application/cleanup.py:77-78`
**Priority:** [M]
**Problem:** Any exception (timeout, DNS) during `requests.head()` deletes listing — too aggressive.
```python
except Exception:
    mongo_handler.collection.delete_one(...)  # Deletes on network timeout!
```
**Fix:** Only delete on actual 404/410, not on network errors.

### 13.34 No pip-compile / Lock File for Dependencies
**Priority:** [M]
**Problem:** No `requirements.txt` lock file. `pip install -r requirements.txt` could install different versions over time.
**Fix:** Use `pip-compile` or `pip-tools` to generate `requirements.txt.lock` with pinned versions.

### 13.35 No Docker Healthcheck in Dockerfile
**File:** `Dockerfile`
**Priority:** [L]
**Problem:** No `HEALTHCHECK` instruction. Docker doesn't know if container is healthy.
**Fix:** Add:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:5001/health || exit 1
```

### 13.36 Selenium WebDriverWait Not Used (Polling Instead)
**File:** `Application/helpers/selenium_fetcher.py:25`
**Priority:** [L]
**Problem:** Uses `time.sleep(wait_time)` instead of WebDriverWait.
**Fix:**
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
```

### 13.37 No Dataclass `__slots__` (Memory Waste)
**Priority:** [L]
**Problem:** All dataclasses lack `__slots__`, wasting memory per instance.
**Affected:** `Listing`, `Coordinates`, `ContactInfo`, `OutreachEmail`, `BankScoringResult`
**Fix:** Add `__slots__ = (...)` to each dataclass.

---

## 14. Business Logic & Scoring Issues

### 14.1 Division by Zero in Scoring Normalization
**File:** `Application/scoring.py:147,154`
**Priority:** [H]
**Problem:** `max_val == min_val` produces NaN:
```python
scoring.py:147: return 100.0 * (max_val - actual_value) / (max_val - min_val)
scoring.py:154: return 100.0 * (actual_value - min_val) / (max_val - min_val)
```
**Fix:** Add guard:
```python
if max_val == min_val:
    return 50.0  # neutral score
```

### 14.2 NaN/Inf Risk with Extreme Values
**File:** `Application/scoring.py:141-154`
**Priority:** [H]
**Problem:** No check for `math.isnan()` or `math.isinf()` on actual_value.
**Fix:** Add after extracting value:
```python
if not isinstance(actual_value, (int, float)) or math.isnan(actual_value) or math.isinf(actual_value):
    return 0.0
```

### 14.3 `prime_new_build` Profile Weights Sum to 0.92, Not 1.0
**File:** `Application/buyer_profiles.py:184-198`
**Priority:** [H]
**Problem:** Weights: 0.20+0.15+0.15+0.12+0.12+0.10+0.08+0.05+0.03 = 0.92 (missing 0.08).
**Fix:** Normalize to sum to 1.0.

### 14.4 `bank_loan_ready` Profile Weights Sum to 1.01
**File:** `Application/buyer_profiles.py:204-220`
**Priority:** [M]
**Problem:** Weights sum slightly over 1.0: 0.13+0.12+0.12+0.10+0.10+0.08+0.07+0.09+0.04+0.03+0.03+0.03+0.02+0.02+0.02 = 1.01.
**Fix:** Adjust weights to sum to exactly 1.0.

### 14.5 Race Condition in Check-Then-Insert
**File:** `Integration/mongodb_handler.py:110-120`
**Priority:** [H]
**Problem:** `listing_exists()` then `insert_listing()` is TOCTOU. Two concurrent scrapers can insert duplicates before unique index catches it.
**Fix:** Use `insert_one()` with `ordered=False` and catch `DuplicateKeyError`.

### 14.6 `mark_listings_sent` Silent Failure
**File:** `Integration/mongodb_handler.py:203`
**Priority:** [M]
**Problem:** `update_many` result not checked. If some URLs don't exist, `modified_count < len(listings)` silently fails.
**Fix:** Check `modified_count` matches expected and warn if mismatch.

### 14.7 Buyer Profile Weight Tolerance Inconsistency
**File:** `buyer_profiles.py:267` vs `scoring.py:59`
**Priority:** [L]
**Problem:** Profile uses `abs(total_weight - 1.0) < 0.001` tolerance but scoring uses `> 0.001` — contradictory.
**Fix:** Use consistent tolerance across both files.

### 14.8 No Telegram Message Length Check
**File:** `run_top5.py` (around line 825)
**Priority:** [M]
**Problem:** No check against 4096 char Telegram limit before send. Long messages get truncated silently.
**Fix:** Calculate message length before send, split if > 4096 chars.

---

## 15. Outreaach System Issues

### 15.1 HTML Injection in Email Templates
**File:** `Application/outreach/email_sender.py:225`
**Priority:** [H]
**Problem:** User-controlled fields (`{address}`, `{title}`, `{sender_name}`) interpolated into HTML without sanitization.
```python
body_html = body_text.replace('\n', '<br>\n')
```
**Fix:** Sanitize user input before HTML interpolation. Use `bleach` or `html.escape()`.

### 15.2 No Reply-To / Threading Headers
**File:** `Application/outreach/email_sender.py:241-243`
**Priority:** [H]
**Problem:** Missing `Reply-To`, `In-Reply-To`, `References` headers. Emails don't thread in Gmail/Outlook.
**Fix:** Add:
```python
msg['Reply-To'] = self.sender_email
msg['References'] = f"<{listing.get('url', '').split('/')[-1]}>"
```

### 15.3 SMTP Connection Not Reused (Performance)
**File:** `Application/outreach/email_sender.py:258`
**Priority:** [H]
**Problem:** Each email creates new SMTP connection. For 10 emails = 10 handshakes.
**Fix:** Use single persistent connection for batch sends.

### 15.4 No Bounce Handling
**Priority:** [M]
**Problem:** No Return-Path tracking, no failed email audit trail.
**Fix:** Use webhooks or parse bounces from SMTP logs.

### 15.5 Contact Emails Logged at INFO Level (PII)
**File:** `Application/outreach/email_sender.py:334`
**Priority:** [M]
**Problem:** `logging.info(f"📧 Sending offer to {contact_email}...")` exposes PII.
**Fix:** Use `logging.debug()` or hash the email in logs.

---

## 16. Scraping & Pagination Issues

### 16.1 No Session Cookie Refresh
**File:** `Application/scraping/willhaben_scraper.py:96-100`
**Priority:** [M]
**Problem:** Session cookies never refreshed. If server issues rate-limit cookie, scraper uses stale ones.
**Fix:** Periodically refresh session: `self.session = requests.Session()` every N pages.

### 16.2 No Captcha Detection
**File:** `Application/scraping/willhaben_scraper.py` (throughout)
**Priority:** [H]
**Problem:** No detection for Cloudflare/Imperva challenge pages (403, challenge screens).
**Fix:** Check response body for challenge indicators and alert/stop scraping.

### 16.3 Pagination Continues Even on Empty Pages
**File:** `Application/scraping/willhaben_scraper.py:1785`
**Priority:** [L]
**Problem:** `for page in range(1, max_pages + 1)` doesn't check if page has results.
**Fix:** Check listing count before continuing to next page.

### 16.4 No Dry-Run Mode in Cleanup
**File:** `Application/cleanup.py` (throughout)
**Priority:** [M]
**Problem:** All cleanup operations are destructive (delete). No preview mode.
**Fix:** Add `--dry-run` flag that only reports what would be deleted.

---

## 17. Auth & Password Issues

### 17.1 werkzeug vs bcrypt Inconsistency
**File:** `Api/app.py:9` vs `Api/auth_api.py:9`
**Priority:** [L]
**Problem:** `app.py` uses werkzeug `generate_password_hash` (pbkdf2:sha256) while `auth_api.py` uses bcrypt. Inconsistent.
**Fix:** Pick one algorithm (bcrypt is more secure) and use consistently.

### 17.2 Default Admin Password in Comments
**File:** `run_outreach.py:16,159`
**Priority:** [L]
**Problem:** `"smtp_password": "your-app-password"` placeholder in comments.
**Fix:** Remove default values from comments.

---

## Priority Summary

### [H] — Do Now
1. Score sort memory fix (aggregation pipeline)
2. Willhaben deduplication (content fingerprint)
3. CI/CD test coverage
4. API input sanitization / injection prevention
5. Dashboard auth (no login UI)
6. Unsubscribe link in outreach emails (GDPR)
7. `requests.get()` without timeout (setup_vienna_channel.py)
8. Large find() without .limit() (cleanup.py, app.py)
9. Hardcoded credentials in scripts (setup_vienna_channel.py)

### [M] — Next Sprint
7. No proxy rotation (IP bans)
8. No rate limiting on scrapers
9. No incremental scraper state
10. No alerting on scrape failures
11. Health check endpoint
12. Mobile responsive map
13. ImmoScout24 scraper
14. Price reduction alerts
15. Secrets management (prod)

### [L] — Backlog
16. print() → logging migration
17. Type hints
18. Log rotation
19. Email open tracking
20. Dark mode
21. School quality data
22. Public transport score
23. Docker container
24. Metrics dashboard
25. CMA report generation
26. WhatsApp integration
27. Comparative market analysis
28. PWA / mobile app