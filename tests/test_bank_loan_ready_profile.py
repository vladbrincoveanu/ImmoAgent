"""bank_loan_ready was consolidated into urban_professional on 2026-07-06
(docs/product/value-review-2026-07-06.md) — its ranking was 0.98-correlated.
These tests now pin the legacy-alias behavior that replaced it."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import pytest

from Application.buyer_profiles import get_profile, BuyerPersona, BUYER_PROFILES, LEGACY_PROFILE_ALIASES

def test_bank_loan_ready_aliases_to_urban_professional():
    assert get_profile('bank_loan_ready') is BUYER_PROFILES['urban_professional']

def test_all_legacy_aliases_resolve_to_kept_profiles():
    for legacy, kept in LEGACY_PROFILE_ALIASES.items():
        assert legacy not in BUYER_PROFILES
        assert kept in BUYER_PROFILES
        assert get_profile(legacy) is BUYER_PROFILES[kept]

def test_persona_enum_accepts_legacy_values():
    assert BuyerPersona.from_value('owner_occupier') is BuyerPersona.DEFAULT
    assert BuyerPersona.from_value('retiree') is BuyerPersona.DEFAULT
    assert BuyerPersona.from_value('eco_conscious') is BuyerPersona.URBAN_PROFESSIONAL
    assert BuyerPersona.from_value('prime_new_build') is BuyerPersona.URBAN_PROFESSIONAL
    assert BuyerPersona.from_value('bank_loan_ready') is BuyerPersona.URBAN_PROFESSIONAL

def test_unknown_persona_still_raises():
    with pytest.raises(ValueError):
        BuyerPersona.from_value('garbage_profile')
