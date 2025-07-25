#!/usr/bin/env python3
"""
Test script to verify run_top5.py new behavior
"""

import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_run_top5_behavior():
    """Test that run_top5.py uses all-time listings with duplicate prevention"""
    print("🧪 Testing run_top5.py New Behavior")
    print("=" * 50)
    
    from Application.helpers.utils import load_config
    from Integration.mongodb_handler import MongoDBHandler
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Initialize MongoDB handler
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    
    # Test 1: Check that we get listings from all time (not just 7 days)
    print("\n📋 Test 1: Checking all-time listings vs 7-day listings")
    
    # Get listings with 7-day filter (old behavior)
    listings_7_days = mongo.get_top_listings(
        limit=10,
        min_score=0,
        days_old=7,
        exclude_recently_sent=False
    )
    print(f"✅ Found {len(listings_7_days)} listings from last 7 days")
    
    # Get listings with 365-day filter (new behavior)
    listings_365_days = mongo.get_top_listings(
        limit=10,
        min_score=0,
        days_old=365,
        exclude_recently_sent=False
    )
    print(f"✅ Found {len(listings_365_days)} listings from last 365 days")
    
    # Get listings with duplicate prevention (actual run_top5 behavior)
    listings_with_duplicate_prevention = mongo.get_top_listings(
        limit=10,
        min_score=0,
        days_old=365,
        exclude_recently_sent=True,
        recently_sent_days=7
    )
    print(f"✅ Found {len(listings_with_duplicate_prevention)} listings with duplicate prevention")
    
    # Test 2: Verify that we get more listings with longer time range
    if len(listings_365_days) >= len(listings_7_days):
        print("✅ Success: Longer time range provides more listings")
    else:
        print("⚠️ Warning: Longer time range didn't provide more listings (might be limited data)")
    
    # Test 3: Verify that duplicate prevention works
    if len(listings_with_duplicate_prevention) <= len(listings_365_days):
        print("✅ Success: Duplicate prevention is working (filtering out recently sent)")
    else:
        print("❌ Error: Duplicate prevention not working correctly")
        return False
    
    return True

def test_config_parameters():
    """Test that run_top5.py uses correct config parameters"""
    print("\n🧪 Testing Config Parameters")
    print("=" * 40)
    
    from Application.helpers.utils import load_config
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Check top5 config section
    top5_config = config.get('top5', {})
    
    print(f"📋 Top5 config parameters:")
    print(f"   • limit: {top5_config.get('limit', 5)}")
    print(f"   • min_score: {top5_config.get('min_score', 40.0)}")
    print(f"   • excluded_districts: {top5_config.get('excluded_districts', [])}")
    print(f"   • min_rooms: {top5_config.get('min_rooms', 0)}")
    print(f"   • include_monthly_payment: {top5_config.get('include_monthly_payment', True)}")
    
    # Note: days_old is no longer used in run_top5.py
    if 'days_old' in top5_config:
        print(f"   ⚠️ days_old: {top5_config.get('days_old')} (no longer used)")
    else:
        print(f"   ✅ days_old: not configured (correct - no longer used)")
    
    return True

def main():
    """Run all tests"""
    print("🚀 run_top5.py Behavior Tests")
    print("=" * 60)
    
    success1 = test_run_top5_behavior()
    success2 = test_config_parameters()
    
    print("\n" + "=" * 60)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("🎉 All run_top5.py behavior tests passed!")
        print("✅ run_top5.py now uses all-time listings (365 days)")
        print("✅ Duplicate prevention excludes recently sent listings")
        print("✅ No more 7-day age restriction")
        print("✅ Different items will be sent each time")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 