#!/usr/bin/env python3
"""
Per-profile scoring for dashboard precalculation.

Scores one listing against all buyer profiles and returns a dict
mapping profile key -> normalized score (0-100).
"""
import logging
from typing import Any

from Application.buyer_profiles import BUYER_PROFILES
from Application.scoring import score_apartment_simple

logger = logging.getLogger(__name__)


def score_all_profiles(listing_dict: dict[str, Any]) -> dict[str, float]:
    """Score a single listing against every buyer profile.

    Skips profiles whose scoring raises; logs a warning.
    Returns dict with all profile keys (missing ones omitted on failure).
    """
    scores: dict[str, float] = {}
    for profile_key, profile in BUYER_PROFILES.items():
        try:
            weights = profile['weights']
            score = score_apartment_simple(listing_dict, weights=weights)
            scores[profile_key] = round(float(score), 2)
        except Exception as e:
            logger.warning(
                "profile_scoring: failed to score profile=%s listing=%s err=%s",
                profile_key,
                listing_dict.get('_id', '<no-id>'),
                e,
            )
    return scores
