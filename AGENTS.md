# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Vienna real-estate scraper/scorer (Willhaben, ImmoKurier, DerStandard) + Telegram notify + Next.js dashboard. Bias: caution over speed on non-trivial work.

## Rules (condensed)
1. Think first: state assumptions; ask, don't guess; push back if simpler exists.
2. Simplicity: minimum code, no speculative features/abstractions.
3. Surgical: touch only what you must; match existing style; no drive-by refactors.
4. Goal-driven: define success criteria, loop until verified.
5. LLM only for judgment (classify/draft/summarize); code for deterministic work.
6. Token budgets: 4k/task, 30k/session. At ~80%: write handoff summary, /clear, fresh session. Surface breaches.
7. Conflicting patterns: pick one (newer/tested), explain, flag the other.
8. Read exports/callers/shared utils before writing.
9. Tests encode WHY, not just WHAT.
10. Checkpoint after each significant step.
11. Codebase conventions > personal taste; surface disagreement, don't fork.
12. Fail loud. Never report "done"/"tests pass" if anything was skipped.

## Commands

### Python scraper (run from `Project/`)
```bash
python run.py                                    # Standard scrape (~12 pages/source)
python run.py --send-to-telegram                 # Scrape + notify
python run.py --deep-scan / --quick-scan         # ~20 or ~4 pages/source
python run.py --willhaben-only                   # Single source; also --immo-kurier-only, --derstandard-only
python run.py --buyer-profile=owner_occupier     # Profile-weighted scoring
python run_top5.py [--limit=N] [--weekly] [--min-score=X] [--exclude-district 1100]
python run_outreach.py [--test-smtp | --dry-run --limit=2 | --discount=25]
bash run_full_pipeline.sh [--max-pages 1 --willhaben-only]
cd ../Tests && python run_tests.py               # Full Python test suite
```

### Next.js dashboard (run from `dashboard/`)
```bash
npm run dev          # Dev server on port 3000
npm run build        # Production build (run before Playwright tests)
npm run start        # Serve production build (default port 3000; use PORT=3060 for local Playwright)
npm run lint         # ESLint
```

### Dashboard testing
```bash
# Playwright — local (expects prod build running on port 3060)
cd dashboard
PORT=3060 npm run start &
npx playwright test --config playwright.local.config.ts <spec>   # single spec
npx playwright test --config playwright.local.config.ts          # full suite

# Playwright — production Vercel
npx playwright test --config playwright.prod.config.ts
```
Run only the spec(s) covering changed code during iteration; run the full suite as the final gate before committing. Do NOT take screenshots into context — assert on DOM selectors. See `.claude/rules/ui-testing.md` for the full loop.

## Architecture

### Data flow
```
Scrapers (Willhaben / ImmoKurier / DerStandard)
  → Listing (Domain/listing.py dataclass)
  → geocode_listing() [helpers/geocoding.py, Nominatim]
  → score_apartment_simple() [Application/scoring.py]
  → MongoDBHandler.save() [Integration/mongodb_handler.py]
  → TelegramBot.send() [Integration/telegram_bot.py]
  → Next.js dashboard [reads same MongoDB via dashboard/lib/mongodb.ts]
```

### Python backend (`Project/`)
- **Domain/** — `listing.py` (core dataclass), `location.py` (`Coordinates`, `UBahnStation`, `Amenity`), `sources.py`.
- **Application/scraping/** — one class per source (`WillhabenScraper`, `ImmoKurierScraper`, `DerStandardScraper`), all ~50–90 KB; share `field_extractors.py` for common field parsing and `helpers/geocoding.py` for Nominatim geocoding + U-Bahn walk times.
- **Application/helpers/** — `geocoding.py` (`ViennaGeocoder`, `geocode_listing()`), `utils.py` (`ViennaDistrictHelper`, `UBahnProximityCalculator`, `DataLoader`, `smart_sleep()`), `listing_validator.py`, `mortgage.py`, `selenium_fetcher.py`.
- **Application/** — `main.py` (orchestration), `scoring.py` (`score_apartment_simple()`, `NORMALIZATION_RANGES`), `buyer_profiles.py` (8 profiles, weights must sum to 1.0 via `validate_weights()`), `analyzer.py` (`StructuredAnalyzer`), `bank_scoring.py`.
- **Integration/** — `mongodb_handler.py` (all DB access; never use raw queries), `telegram_bot.py` (4096-char limit), `minio_handler.py` (image storage).
- **Config priority:** `config.json` → env vars → defaults. Required env vars: `MONGODB_URI`, `TELEGRAM_MAIN_BOT_TOKEN`, `TELEGRAM_MAIN_CHAT_ID`.

### Next.js dashboard (`dashboard/`)
- **App Router** under `dashboard/app/`. Pages: `/dashboard` (listing grid), `/dashboard/map` (Leaflet map).
- **API routes** under `dashboard/app/api/`: `listings/` (list + `[id]` + `map/` + `stream/` + `top/`), `district-heatmap/`, `district-trend/`, `commute/`, `destinations/`, `geo/`, `insights/`, `rent-estimate/`, `saved-searches/`, `stats/`, `admin/`.
- **`dashboard/lib/`** — shared server-side utilities: `mongodb.ts` (singleton `MongoClient`; DB name `immo`), `types.ts` (`ListingBase`, `MapListing`, `CoordinateSource`), `filters.ts`, `profile.ts`, `validators.ts`, `heatmap-color.ts`, `sse.ts`, `rate-limiter.ts`.
- **Components of note:** `MapView.tsx` (Leaflet map, dynamically imported, dual desktop+mobile instances; `flyTo` on pin select, `BoundsTracker` for viewport filtering), `MapLayersPopover.tsx` (choropleth toggle), `ListingDetail.tsx` (full detail panel), `FilterBar/FilterDrawer.tsx` (shared filter state), `DistrictTrendChart.tsx`, `BankFinancingPanel.tsx`, `CommuteAndRentPanel.tsx`.
- **MapView dual-map trap:** the map page renders two `MapView` instances (desktop + mobile). Always guard `map.getSize()` before calling `flyTo` — the hidden instance has zero size and will throw.
- **`dashboard/public/vienna-districts.geojson`** — 23 Bezirk polygons used by the choropleth layer (generated by `scripts/fetch-vienna-districts.mjs`; simplified with Ramer-Douglas-Peucker).

## Config & security
- `config.json` and `secrets.json` are gitignored. Copy `config.json.default` to get started.
- SMTP password only via `SMTP_PASSWORD` env var (see `Project/SETUP_GMAIL.md`).
- Dashboard reads `MONGODB_URI` from env; no other secrets needed for the Next.js app.

## Hard rules (never violate)
1. `GLOBAL_VALIDATION` is the ONLY source of truth for listing-validation thresholds.
2. URL validation (`listing_validator.py`) is mandatory before display/send.
3. Use `is_valid_listing_data()` from `mongodb_handler.py` — never inline `> 0` checks.
4. MongoDB access via `mongodb_handler.py` methods only (Python) / `dashboard/lib/mongodb.ts` (Next.js) — no raw queries.
5. Dedup via `url`/`url_hash`; `sent_to_telegram` flag prevents re-sends.
6. Telegram formatting: follow `telegram_bot.py` patterns (4096-char limit). Outreach templates are German (`outreach/email_sender.py`).
7. Map listings with `coordinate_source === 'none'` must not be rendered as pins — they have no real location.

## Workflow notes
- New scraper: `Application/scraping/<src>_scraper.py` → wire into `Application/main.py` → add `--<src>-only` flag.
- New buyer profile: add to `buyer_profiles.py`, ensure `validate_weights()` passes, add range to `scoring.py NORMALIZATION_RANGES`.
- Dashboard changes: run the targeted spec during iteration, full Playwright suite as final gate. Local tests need a production build on port 3060.
- Verify dashboard against real data using `playwright.prod.config.ts` — local MongoDB is empty.
- Logs: `Project/log/`. Temp files: `scratchpad/`, not `/tmp`. Data: `Project/data/`.

## graphify (default search tool — token-efficient)

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships. **Always search the graph first — it is far more token-efficient than grepping or reading files one by one.**

- **ALWAYS** answer codebase questions (what calls X, how does Y work, trace data flow, find usages/definitions/tests) by running `graphify query "<question>"` FIRST. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
- Only fall back to grep/read when: the graph is stale/missing, an exact string/regex/symbol match is needed, or the query returns nothing after re-wording. Surface the fallback reason.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review when query/path/explain are insufficient.
- **Keep the graph current: after every code change, run `graphify update .`** (AST-only, no API cost). A stale graph gives wrong answers — treat updating it as part of finishing any edit.
