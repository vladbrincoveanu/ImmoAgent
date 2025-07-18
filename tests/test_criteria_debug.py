#!/usr/bin/env python3
"""
Debug criteria matching
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def main():
    """Debug criteria matching"""
    print("🔍 DEBUGGING CRITERIA MATCHING")
    print("=" * 50)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    print(f"📋 Criteria: {config.get('criteria', {})}")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=True)
    print(f"🔧 Scraper criteria: {scraper.criteria}")
    
    # Test one specific listing
    test_url = "https://immobilien.derstandard.at/immobiliensuche/neubau/detail/14692813"
    print(f"\n🔍 Testing specific listing: {test_url}")
    
    listing = scraper.scrape_single_listing(test_url)
    
    if listing:
        print(f"📊 EXTRACTED DATA:")
        print(f"   Title: {listing.title}")
        print(f"   Price: €{listing.price_total:,}" if listing.price_total else "   Price: None")
        print(f"   Area: {listing.area_m2}m²" if listing.area_m2 else "   Area: None")
        print(f"   Rooms: {listing.rooms}" if listing.rooms else "   Rooms: None")
        print(f"   District: {listing.bezirk}" if listing.bezirk else "   District: None")
        print(f"   Year built: {listing.year_built}" if listing.year_built else "   Year built: None")
        
        if listing.price_total and listing.area_m2:
            price_per_m2 = listing.price_total / listing.area_m2
            print(f"   Price per m²: €{price_per_m2:,.0f}")
        
        # Manual criteria check
        print(f"\n🔍 MANUAL CRITERIA CHECK:")
        
        # Price check
        if listing.price_total:
            price_max = scraper.criteria.get('price_max', float('inf'))
            print(f"   Price €{listing.price_total:,} vs max €{price_max:,}: {'❌ FAIL' if listing.price_total > price_max else '✅ PASS'}")
        
        # Area check
        if listing.area_m2:
            area_min = scraper.criteria.get('area_m2_min', 0)
            print(f"   Area {listing.area_m2}m² vs min {area_min}m²: {'❌ FAIL' if listing.area_m2 < area_min else '✅ PASS'}")
        
        # Rooms check
        if listing.rooms:
            rooms_min = scraper.criteria.get('rooms_min', 0)
            print(f"   Rooms {listing.rooms} vs min {rooms_min}: {'❌ FAIL' if listing.rooms < rooms_min else '✅ PASS'}")
        
        # Price per m² check
        if listing.price_total and listing.area_m2:
            price_per_m2 = listing.price_total / listing.area_m2
            price_per_m2_max = scraper.criteria.get('price_per_m2_max', float('inf'))
            print(f"   Price per m² €{price_per_m2:,.0f} vs max €{price_per_m2_max:,}: {'❌ FAIL' if price_per_m2 > price_per_m2_max else '✅ PASS'}")
        
        # Year built check
        if listing.year_built:
            year_min = scraper.criteria.get('year_built_min', 0)
            print(f"   Year built {listing.year_built} vs min {year_min}: {'❌ FAIL' if listing.year_built < year_min else '✅ PASS'}")
        
        # Final result
        matches = scraper.meets_criteria(listing)
        print(f"\n🎯 FINAL RESULT: {'✅ MATCHES' if matches else '❌ DOES NOT MATCH'}")
        
    else:
        print("❌ Failed to scrape listing")
    
    # Clean up
    if hasattr(scraper, 'driver') and scraper.driver:
        scraper.driver.quit()
        print("🧹 Selenium driver closed")

if __name__ == "__main__":
    main() 