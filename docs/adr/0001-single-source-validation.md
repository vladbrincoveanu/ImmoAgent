# ADR-0001: Single Source of Truth for Validation

**Date:** 2026-05-03
**Status:** Accepted
**Updated:** 2026-05-05

## Context

Listing validation had duplicate logic in three places with different thresholds:
- `listing_validator.py`: min_price_per_m2=€1,000, max=€25,000, min_area=20
- `mongodb_handler.is_valid_listing_data()`: used GLOBAL_VALIDATION (min_price_per_m2=€2,000, max=€20,000, min_area=30)
- Inline checks in `main.py`

This caused inconsistent filtering and bugs where listings passed one validator but failed another.

## Decision

1. `GLOBAL_VALIDATION` in `buyer_profiles.py` is the **single source of truth** for numeric thresholds.
2. `listing_validator.is_valid_listing()` uses `GLOBAL_VALIDATION` instead of hardcoded values.
3. `mongodb_handler.is_valid_listing_data()` delegates to `listing_validator.is_valid_listing()` for full validation.
4. Missing price/area passes validation (price-on-request listings exist).

## Current Thresholds (2026-05-05)

Only price_per_m2 validation is used:
- `min_price_per_m2`: €1,000
- `max_price_per_m2`: €20,000

min_price_total and min_area_m2 have been removed.

## Consequences

- **Positive:** One place to change thresholds. Consistent validation everywhere.
- **Positive:** Keyword filtering (rental, price-on-request) now applies to all validation paths.
- **Positive:** Validation stats are consistent.
