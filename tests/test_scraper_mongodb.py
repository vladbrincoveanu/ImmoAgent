#!/usr/bin/env python3
"""
Test derStandard scraper MongoDB connection
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper

pytestmark = pytest.mark.smoke

def test_scraper_mongodb():
    """Test scraper MongoDB connection"""
    print("🧪 TESTING SCRAPER MONGODB CONNECTION")
    print("=" * 50)
    
    try:
        # Initialize scraper
        print("🔧 Initializing scraper...")
        scraper = DerStandardScraper(use_selenium=False)  # Don't use Selenium for this test
        print("✅ Scraper initialized")
        
        # Test MongoDB connection
        print("🔌 Testing MongoDB connection...")
        
        # Test listing_exists
        test_url = "https://test.com"
        exists = scraper.mongo.listing_exists(test_url)
        print(f"✅ listing_exists test: {exists}")
        
        # Test insert
        print("📝 Testing insert...")
        test_doc = {
            "url": "https://test-scraper.com",
            "title": "Test Scraper Listing",
            "source": "test",
            "price_total": 100000
        }
        
        success = scraper.mongo.insert_listing(test_doc)
        print(f"✅ Insert test: {success}")
        
        # Test count
        print("📊 Testing count...")
        try:
            count = scraper.mongo.collection.count_documents({"source": "test"})
            print(f"✅ Count test: {count}")
        except Exception as e:
            print(f"❌ Count test failed: {e}")
        
        # Clean up test document
        try:
            scraper.mongo.collection.delete_one({"url": "https://test-scraper.com"})
            print("🧹 Test document cleaned up")
        except Exception as e:
            print(f"⚠️  Cleanup failed: {e}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scraper_mongodb() 
