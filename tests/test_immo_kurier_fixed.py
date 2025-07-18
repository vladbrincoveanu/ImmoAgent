#!/usr/bin/env python3
"""
Test script to verify the fixed Immo Kurier scraper
Tests data extraction improvements and null value handling
"""

import sys
import os
import json
import time
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add Project directory to path for imports
project_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project')
sys.path.insert(0, project_path)

from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.main import load_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_immo_kurier_scraper():
    """Test the fixed Immo Kurier scraper"""
    print("🧪 Testing Fixed Immo Kurier Scraper")
    print("=" * 50)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Initialize scraper
    try:
        scraper = ImmoKurierScraper(config=config)
        print("✅ Immo Kurier scraper initialized")
    except Exception as e:
        print(f"❌ Failed to initialize scraper: {e}")
        return False
    
    # Test URLs from Immo Kurier
    test_urls = [
        "https://immo.kurier.at/immobilien/4-zimmer-gartenwohnung-direkt-am-park-luftwaermepumpe-zum-heizen-und-kuehlen-1210-wien-687917641a021222de455e59",
        "https://immo.kurier.at/immobilien/3-zimmer-wohnung-mit-balkon-und-garage-1010-wien",
        "https://immo.kurier.at/immobilien/2-zimmer-wohnung-mit-terrasse-1020-wien"
    ]
    
    successful_extractions = 0
    total_tests = len(test_urls)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n🔍 Testing URL {i}/{total_tests}: {url}")
        
        try:
            # Scrape the listing
            listing = scraper.scrape_single_listing(url)
            
            if listing:
                print(f"✅ Successfully scraped listing")
                
                # Check for null values and report
                null_fields = []
                important_fields = [
                    'title', 'price_total', 'area_m2', 'rooms', 'bezirk', 
                    'address', 'year_built', 'energy_class', 'hwb_value',
                    'image_url', 'calculated_monatsrate', 'betriebskosten'
                ]
                
                for field in important_fields:
                    value = getattr(listing, field, None)
                    if value is None:
                        null_fields.append(field)
                
                if null_fields:
                    print(f"⚠️  Null fields: {', '.join(null_fields)}")
                else:
                    print("✅ All important fields extracted successfully")
                
                # Print key data
                print(f"   📝 Title: {listing.title}")
                print(f"   💰 Price: €{listing.price_total:,.0f}" if listing.price_total else "   💰 Price: N/A")
                print(f"   📐 Area: {listing.area_m2}m²" if listing.area_m2 else "   📐 Area: N/A")
                print(f"   🏠 Rooms: {listing.rooms}" if listing.rooms else "   🏠 Rooms: N/A")
                print(f"   📍 District: {listing.bezirk}" if listing.bezirk else "   📍 District: N/A")
                print(f"   🏗️ Year: {listing.year_built}" if listing.year_built else "   🏗️ Year: N/A")
                print(f"   ⚡ Energy: {listing.energy_class}" if listing.energy_class else "   ⚡ Energy: N/A")
                print(f"   🔥 HWB: {listing.hwb_value}" if listing.hwb_value else "   🔥 HWB: N/A")
                print(f"   🖼️ Image: {'✅' if listing.image_url else '❌'}")
                print(f"   💳 Monthly: €{listing.calculated_monatsrate:,.0f}" if listing.calculated_monatsrate else "   💳 Monthly: N/A")
                print(f"   📄 Betriebskosten: €{listing.betriebskosten:,.0f}" if listing.betriebskosten else "   📄 Betriebskosten: N/A")
                
                successful_extractions += 1
                
            else:
                print(f"❌ Failed to scrape listing")
                
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
        
        # Be nice to the server
        time.sleep(2)
    
    print(f"\n📊 Test Results:")
    print(f"   ✅ Successful extractions: {successful_extractions}/{total_tests}")
    print(f"   📈 Success rate: {(successful_extractions/total_tests)*100:.1f}%")
    
    if successful_extractions > 0:
        print("\n✅ Immo Kurier scraper improvements are working!")
        return True
    else:
        print("\n❌ Immo Kurier scraper still has issues")
        return False

def test_search_results():
    """Test scraping search results"""
    print("\n🔍 Testing Search Results Scraping")
    print("=" * 40)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Initialize scraper
    try:
        scraper = ImmoKurierScraper(config=config)
        print("✅ Immo Kurier scraper initialized for search")
    except Exception as e:
        print(f"❌ Failed to initialize scraper: {e}")
        return False
    
    # Get search URL from config
    search_url = config.get('immo_kurier', {}).get('search_url')
    if not search_url:
        print("❌ No search URL found in config")
        return False
    
    print(f"🔍 Testing search URL: {search_url}")
    
    try:
        # Test with limited pages to avoid overwhelming the server
        listings = scraper.scrape_search_results(search_url, max_pages=1)
        
        if listings:
            print(f"✅ Found {len(listings)} listings from search")
            
            # Analyze the first few listings
            for i, listing in enumerate(listings[:3], 1):
                print(f"\n📋 Listing {i}:")
                print(f"   📝 Title: {listing.title}")
                print(f"   💰 Price: €{listing.price_total:,.0f}" if listing.price_total else "   💰 Price: N/A")
                print(f"   📐 Area: {listing.area_m2}m²" if listing.area_m2 else "   📐 Area: N/A")
                print(f"   🏠 Rooms: {listing.rooms}" if listing.rooms else "   🏠 Rooms: N/A")
                print(f"   📍 District: {listing.bezirk}" if listing.bezirk else "   📍 District: N/A")
                print(f"   🖼️ Image: {'✅' if listing.image_url else '❌'}")
            
            return True
        else:
            print("❌ No listings found from search")
            return False
            
    except Exception as e:
        print(f"❌ Error testing search results: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Immo Kurier Scraper Tests")
    print("=" * 60)
    
    # Test individual listing scraping
    individual_success = test_immo_kurier_scraper()
    
    # Test search results scraping
    search_success = test_search_results()
    
    print("\n🎉 Test Summary:")
    print("=" * 30)
    print(f"   Individual scraping: {'✅' if individual_success else '❌'}")
    print(f"   Search results: {'✅' if search_success else '❌'}")
    
    if individual_success and search_success:
        print("\n🎉 All tests passed! Immo Kurier scraper is working properly.")
        return True
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 