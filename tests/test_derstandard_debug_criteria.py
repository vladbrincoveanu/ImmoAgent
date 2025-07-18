#!/usr/bin/env python3
"""
Debug derStandard criteria matching
See what data is extracted and why listings don't match criteria
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def main():
    """Debug criteria matching"""
    print("🔍 DEBUGGING DERSTANDARD CRITERIA MATCHING")
    print("=" * 60)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    print(f"📋 Criteria loaded: {len(config.get('criteria', {}))} rules")
    
    # Print criteria limits
    criteria = config.get('criteria', {})
    print(f"\n📊 CRITERIA LIMITS:")
    print(f"   Price max: €{criteria.get('price_max', 'N/A'):,}")
    print(f"   Price per m² max: €{criteria.get('price_per_m2_max', 'N/A'):,}")
    print(f"   Area min: {criteria.get('area_m2_min', 'N/A')}m²")
    print(f"   Rooms min: {criteria.get('rooms_min', 'N/A')}")
    print(f"   Year built min: {criteria.get('year_built_min', 'N/A')}")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=True)
    print(f"✅ Scraper initialized")
    
    # Test URL extraction
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    print(f"\n🔍 Testing URL extraction from: {test_url}")
    
    try:
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            # Test first 5 URLs to see what data is extracted
            for i, url in enumerate(urls[:5], 1):
                print(f"\n🔍 [{i}/5] Testing: {url}")
                
                listing = scraper.scrape_single_listing(url)
                
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
                    
                    # Check criteria manually
                    print(f"\n🔍 MANUAL CRITERIA CHECK:")
                    
                    # Price check
                    if listing.price_total:
                        price_max = criteria.get('price_max', float('inf'))
                        price_ok = listing.price_total <= price_max
                        print(f"   Price €{listing.price_total:,} vs max €{price_max:,}: {'✅ PASS' if price_ok else '❌ FAIL'}")
                    
                    # Area check
                    if listing.area_m2:
                        area_min = criteria.get('area_m2_min', 0)
                        area_ok = listing.area_m2 >= area_min
                        print(f"   Area {listing.area_m2}m² vs min {area_min}m²: {'✅ PASS' if area_ok else '❌ FAIL'}")
                    
                    # Rooms check
                    if listing.rooms:
                        rooms_min = criteria.get('rooms_min', 0)
                        rooms_ok = listing.rooms >= rooms_min
                        print(f"   Rooms {listing.rooms} vs min {rooms_min}: {'✅ PASS' if rooms_ok else '❌ FAIL'}")
                    
                    # Price per m² check
                    if listing.price_total and listing.area_m2:
                        price_per_m2 = listing.price_total / listing.area_m2
                        price_per_m2_max = criteria.get('price_per_m2_max', float('inf'))
                        price_per_m2_ok = price_per_m2 <= price_per_m2_max
                        print(f"   Price per m² €{price_per_m2:,.0f} vs max €{price_per_m2_max:,}: {'✅ PASS' if price_per_m2_ok else '❌ FAIL'}")
                    
                    # Year built check
                    if listing.year_built:
                        year_min = criteria.get('year_built_min', 0)
                        year_ok = listing.year_built >= year_min
                        print(f"   Year built {listing.year_built} vs min {year_min}: {'✅ PASS' if year_ok else '❌ FAIL'}")
                    
                    # Final result
                    matches = scraper.meets_criteria(listing)
                    print(f"\n🎯 FINAL RESULT: {'✅ MATCHES' if matches else '❌ DOES NOT MATCH'}")
                    
                    if not matches:
                        print(f"   💡 SUGGESTION: Consider adjusting criteria limits if these are good listings")
                else:
                    print(f"   ❌ Failed to scrape listing")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()
            print("🧹 Selenium driver closed")

if __name__ == "__main__":
    main() 