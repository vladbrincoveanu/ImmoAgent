---
title: MyGEWO parity — fast coop alerts, Vienna adapter scale-out, dashboard filters
date: 2026-07-18
status: approved
ui_scope: true
graph_scope: false
test_scope: true
---

# MyGEWO Parity — Design Spec

## Goal

Match MyGEWO's core value for a single client (the project owner): fastest-possible,
accurate Telegram alerts for new Genossenschaft listings across Vienna's major
Bauträger, plus MyGEWO-level dashboard filters.

**End state (success criteria):**
1. New coop listing → Telegram DM within ≤15 min of appearing on the source site.
2. ≥14 Vienna Bauträger covered by adapters (existing 3 + ~11 new).
3. Dashboard filters: min rooms, min m², Bauträger, address search — Playwright green.

## Decisions (from brainstorming, locked)

| Topic | Decision |
|---|---|
| Scope | Core 4: coverage, fast polling, alerts, filters. No native app, no community. |
| Client model | Single user. No per-user subscription system (YAGNI). |
| Polling infra | GitHub Actions cron `*/5` (repo is public → free minutes). No local Mac, no VPS. |
| Coverage | Vienna-first phased. Phase 1: ~14 Bauträger. Phase 2 (~30, later spec): rest of Vienna + NÖ. |
| Alert gating | Config filter only (`coop_alerts` in config.json). NO score gate — first-come demands speed. |
| Dashboard | All four filters incl. address search. |
| Build order | A (poll+alerts) → B (adapters) → C (dashboard filters). |

## Phase A — Fast poll + instant alerts

New GitHub Actions workflow polls only the lightweight coop adapters (requests +
BeautifulSoup, no Selenium) every 5 minutes and DMs matches immediately. The
existing daily full-scrape workflow is untouched.

Data flow:
```
coop-fast-poll.yml (cron */5)
  → run_coop.py
    → for each adapter in registry (failure-isolated):
        conditional GET (ETag/Last-Modified from source_meta) → page-hash skip if unchanged
        → parse → Listing objects
    → is_valid_listing_data() gate
    → upsert via mongodb_handler (dedup url_hash)
    → new listings: match vs config.coop_alerts {bezirke, max_cost, min_rooms, min_area}
      (missing/empty config = send all)
    → validate_url() per listing (hard rule 2)
    → format_coop_message → send to TELEGRAM_COOP_CHANNEL_ID (fallback: main chat)
    → mark sent_to_telegram
```

### Module: `Project/run_coop.py` (new)
- **Responsibility:** Thin runner — orchestrate poll → validate → upsert → filter → notify.
- **Interface:** CLI, no args required; `--dry-run` flag skips Telegram sends. Exit 0 unless ALL adapters fail.
- **Dependencies:** coop adapter registry, mongodb_handler, telegram_bot, listing_validator, config loader.
- **Size target:** ≤200 lines.

### Module: `.github/workflows/coop-fast-poll.yml` (new)
- **Responsibility:** cron `*/5` → `python Project/run_coop.py`.
- **Interface:** repo secrets MONGODB_URI, TELEGRAM_MAIN_BOT_TOKEN, TELEGRAM_MAIN_CHAT_ID, TELEGRAM_COOP_CHANNEL_ID (optional).
- **Dependencies:** requirements install (cached pip); no browser install.
- **Size target:** minimal — single job, ≤60 lines.

### Module: `mongodb_handler.py` — source-meta methods (extend)
- **Responsibility:** `get_source_meta(source)` / `set_source_meta(source, etag, last_modified, page_hash)` on a `source_meta` collection. Keeps hard rule 4 (all Mongo access via handler).
- **Interface:** plain dict in/out.
- **Dependencies:** existing client/db plumbing.
- **Size target:** ~30 lines added.

### Module: `config.json` — `coop_alerts` block (extend)
- **Responsibility:** user's alert filter: `{"bezirke": [], "max_cost": null, "min_rooms": null, "min_area": null}`. Empty/absent field = no constraint.
- **Interface:** read by run_coop.py via existing config loader precedence (config.json > env > defaults).

Notes:
- Coop send path does NOT reuse `send_property_notification` (it score-gates). It uses
  the existing `format_coop_message` + a direct send.
- Send failure → `sent_to_telegram` stays unset → retried on next 5-min run.
- Politeness: custom UA, conditional GET, page-hash skip → unchanged pages are one
  cheap request, no parse.

## Phase B — Adapter scale-out (Vienna phase 1)

New Bauträger (11): Sozialbau, Wien-Süd, GEWOG, Gesiba, WBV-GPA, ÖSW, EGW,
Neues Leben, Heimbau, Frieden, Altmannsdorf-Hetzendorf.

⚠️ INVESTIGATIVE per adapter: trace first — sniff for JSON/XHR backend (preferred:
stable + exact fields), fall back to HTML parsing. Effort per adapter unknown until
traced; plan must budget a trace step before each parse step.

### Module: `Project/Application/scraping/coop/` (new package, refactor)
- **Responsibility:** One module per Bauträger adapter; registry replaces the
  `COOP_SOURCES` dict currently in `genossenschaft_scraper.py` (5.8K, 3 parsers —
  would break the 200-line rule at 14).
- **Interface:** each module exposes `fetch()` (returns raw payload, honors
  conditional-GET meta) and `parse(payload) -> List[Listing]`; `coop/__init__.py`
  exposes `ADAPTERS: dict[name, module]`.
- **Dependencies:** requests, bs4, Domain/listing.py, field_extractors.
- **Size target:** ≤120 lines per adapter module.
- **Migration:** existing 3 parsers (ÖVW, Familienwohnbau, BWSG) move into the
  package unchanged in behavior; `genossenschaft_scraper.py` becomes a thin shim or
  is removed with call sites updated (extraction-gap checklist applies: update ALL
  call sites, run existing smoke tests).

### Testing (Phase B)
- Per adapter: pytest smoke test on a **recorded HTML/JSON fixture** (no live
  network in CI) asserting: ≥1 listing, valid URL, address or bezirk present,
  coop metadata set. Live smoke stays available behind a marker for local runs.
- European number formats via existing `_parse_number` (already verified).

## Phase C — Dashboard filters ×4

Add to `FilterState` → URL params → map + top API routes → UI → MongoDB queries:

1. **Min rooms** (`min_rooms`)
2. **Min m²** (`min_area`)
3. **Bauträger** (`bautraeger`) — dropdown fed by distinct `coop_source` values (new small API or reuse existing endpoint)
4. **Address search** (`q`) — case-insensitive regex on `address` (collection is small;
   add index only if measurably slow)

- Follows the exact wiring pattern of the existing `genossenschaft` toggle (Task 12).
- `ui_scope: true`: every cycle verified with Playwright DOM assertions (real
  selectors/text, not screenshots), against **production build on :3010 with Atlas
  URI** per project memory; full suite as final gate.

### Module: dashboard filter wiring (extend)
- **Responsibility:** thread 4 new params through `lib/filters.ts`, API routes, filter UI, Mongo query builders.
- **Interface:** URL search params ↔ FilterState ↔ Mongo query fragments.
- **Dependencies:** existing filters infrastructure.
- **Size target:** no new files >200 lines; follow existing per-file pattern.

## Error handling

- Adapter failure: log + continue others; workflow exit-code red only when ALL fail.
- Telegram send failure: retried next run via unset `sent_to_telegram`.
- Atlas free tier: no `no_cursor_timeout` cursors (known constraint); short-lived
  connections at 288 runs/day are fine.
- GH cron jitter: accepted — effective latency 5–15 min meets the ≤15 min criterion.

## Out of scope

Native/mobile app, PWA, community features, per-user subscriptions, Austria-wide
coverage (phase 2 spec), rent-oriented scoring.
