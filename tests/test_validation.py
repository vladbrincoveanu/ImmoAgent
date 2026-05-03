#!/usr/bin/env python3
"""Tests for validation logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.mongodb_handler import is_valid_listing_data
from Application.buyer_profiles import GLOBAL_VALIDATION

def test_valid_listing():
    """A normal valid listing should pass."""
    listing = {
        "price_total": 250000,
        "area_m2": 75,
        "title": "Test apartment"
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Valid listing failed: {reason}"

def test_price_too_low():
    """Price below 50k should fail."""
    listing = {
        "price_total": 40000,
        "area_m2": 80,
    }
    valid, reason = is_valid_listing_data(listing)
    assert not valid, "Should have failed"
    assert "price_total" in reason.lower()

def test_area_too_small():
    """Area below 30sqm should fail."""
    listing = {
        "price_total": 200000,
        "area_m2": 25,
    }
    valid, reason = is_valid_listing_data(listing)
    assert not valid, "Should have failed"
    assert "area_m2" in reason.lower()

def test_per_m2_too_low():
    """Per-m2 below 2000 should fail."""
    listing = {
        "price_total": 100000,
        "area_m2": 80,  # 1250/m2 - too low
    }
    valid, reason = is_valid_listing_data(listing)
    assert not valid, "Should have failed"
    assert "per_m2" in reason.lower()

def test_per_m2_too_high():
    """Per-m2 above 20000 should fail."""
    listing = {
        "price_total": 2000000,
        "area_m2": 80,  # 25000/m2 - too high
    }
    valid, reason = is_valid_listing_data(listing)
    assert not valid, "Should have failed"
    assert "per_m2" in reason.lower()

def test_missing_price():
    """Listing with no price should pass (price is on request case)."""
    listing = {
        "price_total": None,
        "area_m2": 75,
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Listing without price should be valid: {reason}"

def test_missing_area():
    """Listing with no area should pass."""
    listing = {
        "price_total": 250000,
        "area_m2": None,
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Listing without area should be valid: {reason}"

def test_both_missing():
    """Listing with neither price nor area should pass (skip validation)."""
    listing = {
        "price_total": None,
        "area_m2": None,
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Listing without price or area should be valid: {reason}"

def test_boundary_price():
    """Exact boundary price should pass."""
    listing = {
        "price_total": 400000,
        "area_m2": 75,
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Boundary price should pass: {reason}"

def test_boundary_area():
    """Exact boundary area should pass."""
    listing = {
        "price_total": 250000,
        "area_m2": 30,
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Boundary area should pass: {reason}"

def test_boundary_per_m2_low():
    """Exact boundary per-m2 (2000) should pass."""
    listing = {
        "price_total": 150000,
        "area_m2": 75,  # 2000/m2 - exactly at boundary
    }
    valid, reason = is_valid_listing_data(listing)
    assert valid, f"Boundary per-m2 should pass: {reason}"

def test_betriebskosten_bug():
    """The original bug: price_total=162 with area=85 should fail (per-m2=1906 < 2000)."""
    listing = {
        "price_total": 162,
        "area_m2": 85,
    }
    valid, reason = is_valid_listing_data(listing)
    assert not valid, "Should have failed - Betriebskosten bug"
    assert "price_total" in reason.lower() or "per_m2" in reason.lower()

if __name__ == "__main__":
    test_valid_listing()
    test_price_too_low()
    test_area_too_small()
    test_per_m2_too_low()
    test_per_m2_too_high()
    test_missing_price()
    test_missing_area()
    test_both_missing()
    test_boundary_price()
    test_boundary_area()
    test_boundary_per_m2_low()
    test_betriebskosten_bug()
    print("All tests passed!")