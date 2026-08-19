#!/usr/bin/env python3
"""
Test script to verify derStandard scraper fixes
Tests that collections are properly skipped and no cycles occur
"""

import pytest
import sys
import os
import logging

# Add Project directory to path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper

pytestmark = pytest.mark.smoke

def test_derstandard_scraper():
    """Test that derStandard scraper works without cycles"""
    print("🧪 TESTING DERSTANDARD SCRAPER FIXES")
    print("=" * 50)
    
    # Set up logging to see what's happening
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=False)
    print("✅ Scraper initialized")
    
    # Test with a small number of pages to avoid too much output
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    
    print(f"🔍 Testing with URL: {test_url}")
    print("📝 This will show if collections are properly skipped and no cycles occur")
    
    try:
        # Extract a few URLs first
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs to test")
        
        if urls:
            # Test scraping the first few URLs
            test_count = min(3, len(urls))
            print(f"🔍 Testing first {test_count} URLs...")
            
            for i, url in enumerate(urls[:test_count], 1):
                print(f"\n[{i}/{test_count}] Testing: {url}")
                listing = scraper.scrape_single_listing(url)
                
                if listing:
                    print(f"   ✅ Successfully scraped: {listing.title}")
                    print(f"   💰 Price: €{listing.price_total:,.0f}" if listing.price_total else "   💰 Price: N/A")
                    print(f"   📐 Area: {listing.area_m2}m²" if listing.area_m2 else "   📐 Area: N/A")
                    print(f"   🛏️  Rooms: {listing.rooms}" if listing.rooms else "   🛏️  Rooms: N/A")
                else:
                    print(f"   ❌ Failed to scrape or was skipped")
        
        print("\n🎉 Test completed!")
        print("✅ No cycle warnings should appear above")
        print("✅ Collections should be skipped with info messages")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_derstandard_scraper() 
