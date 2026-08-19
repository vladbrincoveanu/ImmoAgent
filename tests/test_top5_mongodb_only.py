#!/usr/bin/env python3
"""
Test script to verify top5 MongoDB functionality only (no Telegram required)
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config
from test_utils import load_test_config, setup_test_environment, cleanup_test_environment

pytestmark = pytest.mark.smoke

def test_top5_mongodb():
    """Test fetching top listings from MongoDB"""
    print("🧪 Testing Top5 MongoDB Functionality")
    print("=" * 50)
    
    try:
        # Set up test environment
        setup_test_environment()
        
        # Load config (will use test config if in test mode)
        try:
            config = load_test_config()
            print("✅ Using test configuration")
        except FileNotFoundError:
            config = load_config()
            print("✅ Using production configuration")
        
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Initialize MongoDB
        mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
        mongo = MongoDBHandler(uri=mongo_uri)
        
        if not mongo.client:
            print("❌ Failed to connect to MongoDB")
            return False
        
        print("✅ Connected to MongoDB")
        
        # Get parameters from config
        limit = config.get('top5', {}).get('limit', 5)
        min_score = config.get('top5', {}).get('min_score', 40.0)
        days_old = config.get('top5', {}).get('days_old', 7)
        
        print(f"📊 Fetching top {limit} listings...")
        print(f"🎯 Minimum score: {min_score}")
        print(f"📅 Last {days_old} days")
        
        # Test fetching top listings
        listings = mongo.get_top_listings(
            limit=limit,
            min_score=min_score,
            days_old=days_old
        )
        
        print(f"✅ Found {len(listings)} listings")
        
        if listings:
            print("\n🏆 Top Properties:")
            for i, listing in enumerate(listings, 1):
                score = listing.get('score', 0)
                price = listing.get('price_total', 0)
                area = listing.get('area_m2', 0)
                rooms = listing.get('rooms', 0)
                bezirk = listing.get('bezirk', 'N/A')
                source = listing.get('source', 'Unknown')
                title = listing.get('title', 'No title')[:50] + "..." if len(listing.get('title', '')) > 50 else listing.get('title', 'No title')
                
                ranking_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                
                print(f"  {ranking_emoji} Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk} | {source}")
                print(f"     📝 {title}")
                print()
        else:
            print("⚠️ No listings found matching criteria")
        
        # Test with different parameters
        print("\n🧪 Testing with different parameters:")
        
        # Test with no score filter
        all_listings = mongo.get_top_listings(limit=3, min_score=0.0, days_old=30)
        print(f"  All listings (last 30 days): {len(all_listings)} found")
        
        # Test with higher score threshold
        high_score_listings = mongo.get_top_listings(limit=3, min_score=50.0, days_old=30)
        print(f"  High score listings (≥50): {len(high_score_listings)} found")
        
        # Test with recent listings only
        recent_listings = mongo.get_top_listings(limit=3, min_score=0.0, days_old=1)
        print(f"  Recent listings (last 1 day): {len(recent_listings)} found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing MongoDB: {e}")
        return False
    finally:
        # Clean up test environment
        cleanup_test_environment()

def main():
    """Run the test"""
    success = test_top5_mongodb()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
