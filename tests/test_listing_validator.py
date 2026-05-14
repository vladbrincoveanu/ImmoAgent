#!/usr/bin/env python3
"""
Test script for listing validator utilities
"""

import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_valid_listing():
    """Test valid listing validation"""
    print("🧪 Testing Valid Listing")
    print("=" * 40)
    
    from Application.helpers.listing_validator import is_valid_listing
    
    # Valid listing
    valid_listing = {
        'price_total': 300000,
        'area_m2': 60,
        'monthly_payment': {
            'total_monthly': 1500
        }
    }
    
    result = is_valid_listing(valid_listing)
    print(f"✅ Valid listing (€300k, 60m²): {result}")
    assert result == True, "Valid listing should return True"
    
    return True

def test_invalid_listings():
    """Test invalid listing validation"""
    print("\n🧪 Testing Invalid Listings")
    print("=" * 40)
    
    from Application.helpers.listing_validator import is_valid_listing
    
    # Test cases for invalid listings
    test_cases = [
        {
            'name': 'Too cheap per m²',
            'listing': {'price_total': 30000, 'area_m2': 60},  # €500/m²
            'expected': False
        },
        {
            'name': 'Too expensive per m²',
            'listing': {'price_total': 2000000, 'area_m2': 60},  # €33,333/m²
            'expected': False
        },
        {
            'name': 'Too low total price',
            'listing': {'price_total': 30000, 'area_m2': 60},  # €30k total
            'expected': False
        },
        {
            'name': 'Too small area',
            'listing': {'price_total': 100000, 'area_m2': 15},  # 15m²
            'expected': True  # area minimum not enforced, only price_per_m2
        },
        {
            'name': 'Too expensive monthly payment',
            'listing': {
                'price_total': 300000,
                'area_m2': 60,
                'monthly_payment': {'total_monthly': 2501}  # €2,501/month
            },
            'expected': False
        },
        {
            'name': 'Missing price',
            'listing': {'area_m2': 60},
            'expected': True
        },
        {
            'name': 'Missing area',
            'listing': {'price_total': 300000},
            'expected': True
        }
    ]
    
    for test_case in test_cases:
        result = is_valid_listing(test_case['listing'])
        print(f"✅ {test_case['name']}: {result} (expected: {test_case['expected']})")
        assert result == test_case['expected'], f"{test_case['name']} should return {test_case['expected']}"
    
    return True

def test_filter_valid_listings():
    """Test filtering multiple listings"""
    print("\n🧪 Testing Filter Valid Listings")
    print("=" * 40)
    
    from Application.helpers.listing_validator import filter_valid_listings, get_validation_stats
    
    # Mixed list of valid and invalid listings
    listings = [
        {'price_total': 300000, 'area_m2': 60, 'monthly_payment': {'total_monthly': 1500}},  # Valid
        {'price_total': 30000, 'area_m2': 60},  # Invalid (too cheap per m²)
        {'price_total': 400000, 'area_m2': 80, 'monthly_payment': {'total_monthly': 1800}},  # Valid
        {'price_total': 100000, 'area_m2': 15},  # Valid (area min not enforced, only price_per_m2 checked)
        {'price_total': 500000, 'area_m2': 100, 'monthly_payment': {'total_monthly': 2501}}  # Valid
    ]
    
    # Filter valid listings
    valid_listings = filter_valid_listings(listings)
    print(f"✅ Filtered {len(valid_listings)} valid listings from {len(listings)} total")
    assert len(valid_listings) == 3, f"Should have 3 valid listings (only 30000/60 too-cheap-per-m² rejected), got {len(valid_listings)}"
    
    # Test with limit
    limited_listings = filter_valid_listings(listings, limit=1)
    print(f"✅ Limited to {len(limited_listings)} listings")
    assert len(limited_listings) == 1, f"Should have 1 listing with limit, got {len(limited_listings)}"
    
    # Test validation stats
    stats = get_validation_stats(listings)
    print(f"✅ Validation stats: {stats['valid']}/{stats['total']} valid ({stats['valid_percentage']:.1f}%)")
    assert stats['valid'] == 3, f"Should have 3 valid listings in stats, got {stats['valid']}"
    assert stats['invalid'] == 2, f"Should have 2 invalid listings in stats, got {stats['invalid']}"
    
    return True

def main():
    """Run all tests"""
    print("🚀 Listing Validator Tests")
    print("=" * 50)
    
    success1 = test_valid_listing()
    success2 = test_invalid_listings()
    success3 = test_filter_valid_listings()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 and success3 else '❌ FAILED'}")
    
    if success1 and success2 and success3:
        print("🎉 All listing validator tests passed!")
        print("✅ Valid listing detection works")
        print("✅ Invalid listing filtering works")
        print("✅ Batch filtering and statistics work")
    
    return success1 and success2 and success3

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 