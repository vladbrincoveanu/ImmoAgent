# CLAUDE.md

Vienna real-estate scraper/scorer (Willhaben, ImmoKurier, DerStandard) + Telegram notify + Next.js dashboard. Bias: caution over speed on non-trivial work.

## Rules
Follow `~/.claude/rules/12-rule-template.md`.

## Commands (run from Project/)
- Scrape: `python run.py` [--send-to-telegram | --deep-scan | --quick-scan | --willhaben-only | --buyer-profile=X]
- Top-5: `python run_top5.py` [--limit=N | --weekly | --min-score=X | --exclude-district NNNN ...]
- Outreach: `python run_outreach.py` [--test-smtp | --dry-run --limit=N | --discount=N]
- Pipeline: `bash Project/run_full_pipeline.sh [--max-pages 1 --willhaben-only]`
- Tests: `cd Tests && python run_tests.py`
- Full command/architecture reference: docs/CLAUDE-full-reference.md (read on demand, not by default)

## Architecture
- `Project/Application/` — main.py (orchestration), scoring.py, buyer_profiles.py, analyzer.py, scraping/, outreach/
- `Project/Integration/` — mongodb_handler.py, telegram_bot.py, minio_handler.py
- `Project/Domain/` — listing.py, location.py, sources.py
- `Project/UI/` (Flask), `dashboard/` (Next.js), `Tests/`
- Buyer profiles: default, owner_occupier, diy_renovator, growing_family, urban_professional, eco_conscious, retiree, budget_buyer. Weights in buyer_profiles.py must sum to 1.0 (`validate_weights()`); ranges in scoring.py NORMALIZATION_RANGES.

## Config & security
- Priority: config.json > env vars > defaults. Required in CI: MONGODB_URI, TELEGRAM_MAIN_BOT_TOKEN, TELEGRAM_MAIN_CHAT_ID.
- NEVER commit secrets: .env, config.json, secrets.json are gitignored. SMTP password only via SMTP_PASSWORD env var (Gmail app passwords: Project/SETUP_GMAIL.md).

## Hard rules (never violate)
1. GLOBAL_VALIDATION is the ONLY source of truth for listing-validation thresholds.
2. URL validation (listing_validator.py) is mandatory before display/send.
3. Use `is_valid_listing_data()` from mongodb_handler.py — never inline `> 0` checks.
4. MongoDB access via mongodb_handler.py methods only — no raw queries.
5. Dedup via `url`/`url_hash`; `sent_to_telegram` flag prevents re-sends.
6. Telegram formatting: follow telegram_bot.py patterns (4096-char limit). Outreach templates are German (outreach/email_sender.py).

## Workflow notes
- New scraper: Application/scraping/<src>_scraper.py → wire into Application/main.py → add --<src>-only flag.
- Dashboard changes: `.claude/rules/ui-testing.md` applies (targeted spec per iteration, full suite as final gate).
- Logs: Project/log/. Temp files: scratchpad, not /tmp. Data: Project/data/.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
