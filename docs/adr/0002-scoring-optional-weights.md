# ADR-0002: Scoring Function Accepts Optional Weights Parameter

**Date:** 2026-05-03
**Status:** Accepted

## Context

`score_apartment()` and `score_apartment_simple()` read from global `CRITERIA_WEIGHTS` dict, which is modified by `set_buyer_profile()` using `global` keyword. This caused:
- Not thread-safe
- Hidden dependency on call order
- Hard to test in isolation
- Can't score with different weights in same process

## Decision

1. `score_apartment(apartment_data, weights=None)` accepts optional `weights` parameter.
2. If `weights=None`, falls back to global `CRITERIA_WEIGHTS` (backward compatible).
3. Explicit weights allow thread-safe, isolated scoring with any profile.
4. `score_multiple_apartments(apartments_list, weights=None)` also updated.

## Consequences

- **Positive:** Thread-safe when passing weights explicitly.
- **Positive:** Testable in isolation — pass any weights dict.
- **Positive:** Backward compatible — existing call sites unchanged.
- **Positive:** No more call-order dependency.
