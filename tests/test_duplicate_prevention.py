#!/usr/bin/env python3
"""
Test script for duplicate prevention system
"""

import sys
import os
import time

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_duplicate_prevention():
    """Test that listings sent to Telegram are tracked and not sent again"""
    print("🧪 Testing Duplicate Prevention System")
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
    
    # Test 1: Check if we can get recently sent listings
    print("\n📋 Test 1: Getting recently sent listings")
    recently_sent = mongo.get_recently_sent_listings(days=7)
    print(f"✅ Found {len(recently_sent)} recently sent listings")
    
    # Test 2: Check if get_top_listings excludes recently sent
    print("\n📋 Test 2: Testing exclusion of recently sent listings")
    
    # First, get listings without exclusion
    listings_without_exclusion = mongo.get_top_listings(
        limit=10, 
        min_score=0, 
        days_old=30,
        exclude_recently_sent=False
    )
    print(f"✅ Found {len(listings_without_exclusion)} listings without exclusion")
    
    # Then, get listings with exclusion
    listings_with_exclusion = mongo.get_top_listings(
        limit=10, 
        min_score=0, 
        days_old=30,
        exclude_recently_sent=True,
        recently_sent_days=7
    )
    print(f"✅ Found {len(listings_with_exclusion)} listings with exclusion")
    
    # Test 3: Mark some listings as sent and verify they're excluded
    print("\n📋 Test 3: Marking listings as sent and verifying exclusion")
    
    if listings_without_exclusion:
        # Mark first 3 listings as sent
        test_listings = listings_without_exclusion[:3]
        mongo.mark_listings_sent(test_listings)
        print(f"✅ Marked {len(test_listings)} listings as sent")
        
        # Wait a moment for the database to update
        time.sleep(1)
        
        # Check if they're now in recently sent
        recently_sent_after = mongo.get_recently_sent_listings(days=7)
        print(f"✅ Found {len(recently_sent_after)} recently sent listings after marking")
        
        # Get listings again with exclusion
        listings_after_exclusion = mongo.get_top_listings(
            limit=10, 
            min_score=0, 
            days_old=30,
            exclude_recently_sent=True,
            recently_sent_days=7
        )
        print(f"✅ Found {len(listings_after_exclusion)} listings after exclusion")
        
        # Verify the marked listings are not in the results
        marked_urls = [listing.get('url') for listing in test_listings if listing.get('url')]
        excluded_urls = [listing.get('url') for listing in listings_after_exclusion if listing.get('url')]
        
        overlap = set(marked_urls) & set(excluded_urls)
        if not overlap:
            print("✅ Success: Marked listings are properly excluded")
            return True
        else:
            print(f"❌ Error: {len(overlap)} marked listings still appear in results")
            return False
    else:
        print("⚠️ No listings found to test with")
        return True

def test_mark_sent_functionality():
    """Test the mark_sent functionality"""
    print("\n🧪 Testing Mark Sent Functionality")
    print("=" * 40)
    
    from Application.helpers.utils import load_config
    from Integration.mongodb_handler import MongoDBHandler
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Initialize MongoDB handler
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    
    # Get a test listing
    test_listings = mongo.get_top_listings(limit=1, min_score=0, days_old=30, exclude_recently_sent=False)
    
    if not test_listings:
        print("⚠️ No listings found to test with")
        return True
    
    test_listing = test_listings[0]
    test_url = test_listing.get('url')
    
    if not test_url:
        print("⚠️ Test listing has no URL")
        return True
    
    print(f"📋 Testing with listing: {test_url[:50]}...")
    
    # Test individual mark_sent
    mongo.mark_sent(test_url)
    print("✅ Marked individual listing as sent")
    
    # Test batch mark_listings_sent
    mongo.mark_listings_sent([test_listing])
    print("✅ Marked listing as sent via batch method")
    
    # Verify it's in recently sent
    recently_sent = mongo.get_recently_sent_listings(days=7)
    if test_url in recently_sent:
        print("✅ Listing properly tracked in recently sent")
        return True
    else:
        print("❌ Listing not found in recently sent")
        return False

def main():
    """Run all tests"""
    print("🚀 Duplicate Prevention System Tests")
    print("=" * 60)
    
    success1 = test_duplicate_prevention()
    success2 = test_mark_sent_functionality()
    
    print("\n" + "=" * 60)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("🎉 All duplicate prevention tests passed!")
        print("✅ Recently sent listings are properly tracked")
        print("✅ Duplicate listings are excluded from results")
        print("✅ Mark sent functionality works correctly")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 