# ADR-0003: Cleanup Functions Extracted to cleanup.py Module

**Date:** 2026-05-03
**Status:** Accepted

## Context

`main.py` was 1113 lines. Functions for cleanup, scraping, saving, Telegram were all mixed in one "god function" (`main()`). This made the code:
- Hard to test in isolation
- Risky to modify — change one thing, break another
- Difficult to understand the pipeline flow

## Decision

1. Extracted cleanup functions to `Application/cleanup.py`:
   - `deep_cleanup_database()`
   - `comprehensive_cleanup_all_listings()`
   - `clean_stale_or_broken_listings()`
   - `check_and_alert_rejection_rate()`

2. `main.py` imports these from `Application.cleanup`.

3. `main()` becomes orchestrator — calls `cleanup.*`, `scraping.*`, `mongodb.*` with clear separation.

## Consequences

- **Positive:** `main.py` reduced from 1113 to 796 lines.
- **Positive:** Cleanup testable in isolation.
- **Positive:** Locality: cleanup changes don't touch orchestration.
- **Positive:** Clearer pipeline: scrape → save → cleanup.

## Notes

- Cleanup runs on every scrape (not just morning) since 2026-05-03.
