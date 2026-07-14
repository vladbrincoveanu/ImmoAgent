---
title: Genossenschaft coverage vertical — v1 design
date: 2026-07-14
status: design (post-grill, pre-plan)
supersedes_scope_in: 2026-07-14-genossenschaft-aggregator-eval.md
ui_scope: true
graph_scope: false
test_scope: true
---

# Genossenschaft coverage vertical — v1 design

Companion to `2026-07-14-genossenschaft-aggregator-eval.md` (the why). This doc is the **what/how** for v1, after a design grill that changed three locked handoff decisions.

## Wedge (unchanged)
**Widest DEDUPED coverage of Vienna co-op / geförderte first-come units**, broadcast free. Success metric: our unique deduped co-op count ≥ MyGEWO same-day. Speed is table-stakes, not the wedge; coverage + a free channel (vs MyGEWO's paywall) is.

## What the grill changed (vs handoff 2026-07-14-1345)
| Handoff said | Ground truth | v1 decision |
|---|---|---|
| Delivery = per-user saved-search → web push + Telegram; needs deep-link token + per-user `telegram_chat_id` (new infra) | Auth was **deleted** on this branch (no next-auth; only anon cookie `immo_user` + hand-flipped `is_pro`, `dashboard/lib/user.ts:5-24`). Telegram bot is single hardcoded `chat_id` (`telegram_bot.py:104-123`). | **ONE broadcast Telegram channel.** Exact reuse of single-`chat_id` model. No per-user linkage, no deep-link, no web push in v1. Personalization deferred. |
| Dedup = content fingerprint (bautraeger,address,price,rooms,area) + url_hash | Existing fingerprint is `md5(title+area+rooms+bezirk+source)`, index `(content_fingerprint, source_enum)` — **source-scoped** (`listing_validator.py:13-25`, `mongodb_handler.py:86`). Same unit on Willhaben + its Bauträger site would NOT merge. | **Add a second, source-INDEPENDENT fingerprint** for co-op units. Collapses cross-source dupes so the coverage count is honest and the channel doesn't double-post. |
| 1 engine + 11 declarative adapter configs | Codebase convention = copy-per-source monolith (`willhaben_scraper.py` 1928 lines); no base class, no engine. | **Pilot 3 concrete adapters** (ÖVW, Familienwohnbau, BWSG). Extract an abstraction only if their HTML shapes rhyme. No blind engine. |

## Sources (v1)
- **3 pilot Bauträger:** ÖVW, Familienwohnbau, BWSG (all confirmed live public available-units pages, no auth).
- **Willhaben co-op tagging:** tag existing Willhaben listings as co-op when detected (reuses running scraper — near-zero cost).
- **Excluded:** Sozialbau (login-gated — known coverage gap). Remaining 8 Bauträger = post-pilot phase. Wohn-Ticket ranked units = out of scope (speed-irrelevant).

## Deferred to post-v1 (explicitly NOT in this design)
Per-user saved-search push · web push · remaining 8 Bauträger adapters · Wohn-Ticket eligibility check · dossier/register assist · .NET MAUI phone app. These wait on (a) real accounts and (b) proof the free channel pulls demand.

---

## Module Design Blocks (v1)

### M1 — Domain model + co-op source
**Files:** `Project/Domain/listing.py`, `Project/Domain/sources.py`
- Add `Source.GENOSSENSCHAFT = "genossenschaft"` (single source enum; the specific developer goes in `bautraeger`). Willhaben-detected co-op units keep `Source.WILLHABEN` but get `is_genossenschaft=True`.
- Add fields to `Listing`:
  - `is_genossenschaft: Optional[bool] = None`
  - `bautraeger: Optional[str] = None`  # e.g. "ÖVW", "BWSG"
  - `allocation_model: Optional[str] = None`  # 'first_come' | 'wohn_ticket' | None
  - `coop_source: Optional[str] = None`  # 'bautraeger_direct' | 'willhaben'
  - `content_fingerprint_xsrc: Optional[str] = None`  # source-independent (M2)
- No scoring change v1 (co-op uses existing scoring as-is). `allocation_model` defaults to `first_come` for scraped Bauträger direct pages (that's what they publish).

### M2 — Cross-source dedup (source-independent fingerprint)
**Files:** `Project/Application/scraping/listing_validator.py`, `Project/Integration/mongodb_handler.py`, `Project/Application/main.py`
- New `compute_xsrc_fingerprint(listing) -> str` = `md5(norm(bautraeger) + "|" + norm(address) + "|" + round(area_m2) + "|" + rooms)`. NO source, NO price (price varies by portal fee display). `norm()` = lowercased, whitespace-collapsed, umlaut-folded.
- **Only computed for co-op listings** (`is_genossenschaft`). Buy-side listings keep existing source-scoped fingerprint untouched — do not regress current behavior.
- Store on `content_fingerprint_xsrc`. On save, if a co-op listing with the same `content_fingerprint_xsrc` already exists, treat as duplicate → skip insert (but keep the first-seen record; prefer the Bauträger-direct record over Willhaben when both arrive, since direct = canonical apply URL).
- Index: partial index on `content_fingerprint_xsrc` where field exists.
- **Guard:** if `bautraeger` or `address` is missing, fall back to url_hash only (don't collapse on a weak key).

### M3 — Co-op detection / tagging
**Files:** `Project/Application/scraping/field_extractors.py` (+ call site in `willhaben_scraper.py`)
- Add `extract_is_genossenschaft(text) -> Optional[bool]` following the existing two-pass negative/positive pattern in `field_extractors.py`. Positive markers: `genossenschaft`, `gemeinnützig`, `gefördert`, `wgg`, `mietkauf`, `baurechtszins`, `finanzierungsbeitrag`, `eigenmittelanteil`. Negative/exclude: `freifinanziert`, `provisionsfrei` alone (not a co-op signal).
- Wire into `willhaben_scraper.py`'s single-listing extraction so Willhaben co-op units get tagged `is_genossenschaft=True`, `coop_source='willhaben'`.
- Bauträger-direct adapters (M4) set `is_genossenschaft=True`, `coop_source='bautraeger_direct'` unconditionally.

### M4 — Co-op scraper (3 pilot adapters)
**Files:** new `Project/Application/scraping/genossenschaft_scraper.py`; wire into `Project/Application/main.py`
- One module, 3 parser functions (ÖVW, Familienwohnbau, BWSG) — concrete, not config-driven yet. Each returns `List[Listing]` with `source=GENOSSENSCHAFT`, `bautraeger` set, `coop_source='bautraeger_direct'`, `allocation_model='first_come'`.
- Reuse `requests` + BeautifulSoup like the existing scrapers; reuse `field_extractors` where fields overlap.
- Wire per existing convention: `scrape_genossenschaft()` wrapper in `main.py` (mirror `scrape_willhaben()` at `main.py:335`), append `("genossenschaft", scrape_genossenschaft)` to `scrapers_to_run` (`main.py:620-631`), add `--genossenschaft-only` flag to the `sys.argv` block (`main.py:535-537`).
- **Post-pilot decision gate:** after 3 adapters work on live HTML, review variance → decide whether to extract a shared engine/config for the remaining 8. Documented as an open decision, not pre-committed.

### M5 — Telegram co-op channel broadcast
**Files:** `Project/Integration/telegram_bot.py`, `Project/Application/main.py`, `config.json` (channel id via env)
- New channel chat id from env `TELEGRAM_COOP_CHANNEL_ID` (do NOT hardcode; follows CLAUDE.md secret rules). Reuse `TelegramBot` — instantiate a second instance pointed at the co-op channel, OR pass a `chat_id` override to `send_message`. Prefer a second `TelegramBot(bot_token, coop_channel_id)` instance to avoid touching the shared buy-side path.
- On each new deduped co-op listing (post-M2), format + post to the co-op channel. Reuse existing formatting patterns (4096-char limit) and the `sent_to_telegram` flag to prevent re-sends (`Listing.sent_to_telegram`, line 42).
- Post content: bautraeger, bezirk, price/m², rooms, area, allocation_model, direct apply URL. Tag-style hashtags in the message (`#1120 #ÖVW`) so channel users can Telegram-search — this is the v1 "filtering" (per grill: one channel, users self-filter).

### M6 — Scheduled co-op scrape (cron)
**Files:** ops/deploy config (cron), invokes `python run.py --genossenschaft-only --send-to-telegram`
- ~15 min cadence during Bauträger posting window (Mon–Fri 07:00–24:00 per research; off-hours can be slower). First-come speed matters, so cadence is tighter than buy-side.
- Idempotent: dedup (M2) + `sent_to_telegram` guarantee no double-posts across runs.
- Mechanism TBD in plan (system cron vs Vercel cron vs existing pipeline script `run_full_pipeline.sh`).

### M7 — Dashboard co-op filter + map layer
**Files:** `dashboard/lib/filters.ts`, `dashboard/components/MapView.tsx` + filter UI, relevant `dashboard/app/api/listings/*`
- Add a `genossenschaft` toggle/filter (server-side query on `is_genossenschaft=true`) to existing map + grid. Reuse existing filter plumbing.
- Distinct map marker style for co-op units.
- **`ui_scope: true`** → per `.claude/rules/ui-testing.md`: targeted Playwright spec for the co-op filter each iteration; full suite as final gate. Verify on prod data (local Mongo empty — see memory `feedback-verify-on-real-data`).

### M8 — Coverage-measure script
**Files:** new `Project/scripts/measure_coop_coverage.py`
- Counts our unique deduped co-op units (by `content_fingerprint_xsrc`) currently live, broken down by bautraeger + coop_source. This is the success-metric instrument ("≥ MyGEWO same-day").
- v1 = our-side count + manual MyGEWO spot-check (no MyGEWO scraping). Outputs a dated summary to `Project/log/`.

---

## Build order (dependency-sorted)
1. **M1** Domain fields + Source enum (unblocks everything).
2. **M2** Cross-source dedup (before any co-op data lands, so counts are honest from day one).
3. **M3** Co-op detection + Willhaben tagger (first real co-op data, zero new scraper).
4. **M4** 3 pilot Bauträger adapters + main.py wiring.
5. **M7** Dashboard filter + map layer [Playwright gate].
6. **M5** Telegram co-op channel broadcast.
7. **M6** Scrape cron.
8. **M8** Coverage-measure script (validates the wedge).

## Open risks (carried, accepted for v1)
- Coverage moat is copyable (MyGEWO already scrapes) — validate demand via the free channel before investing in down-funnel.
- 3→11 bespoke scrapers are brittle; pilot-first mitigates over-building.
- Source-independent fingerprint may over-merge (two real different units, same bautraeger/address/area/rooms) or under-merge (address formatting differs across portals) — M2 guard + `norm()` reduce but don't eliminate; measure false-merge rate in M8.
- One-channel-no-filter may be too noisy → post-v1 personalization is the escape valve.
- Co-op below-market prices could distort existing scoring if co-op units enter buy-side scoring — v1 keeps them tagged and does not feed buy-side score comparisons.
