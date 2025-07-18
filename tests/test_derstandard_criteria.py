#!/usr/bin/env python3
"""
Test derStandard criteria matching
See what data is extracted and why listings don't match criteria
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def main():
    """Test criteria matching"""
    print("🔍 TESTING DERSTANDARD CRITERIA MATCHING")
    print("=" * 50)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=True)
    print("✅ Scraper initialized")
    
    # Test URL extraction
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    print(f"🔍 Testing URL extraction from: {test_url}")
    
    try:
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            # Test first 5 URLs
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
                    
                    # Check criteria
                    matches = scraper.meets_criteria(listing)
                    print(f"   Matches criteria: {'✅ YES' if matches else '❌ NO'}")
                    
                    if not matches:
                        print(f"   ❌ REJECTION REASONS:")
                        
                        # Check each criterion
                        if listing.price_total and listing.price_total > config['criteria']['price_max']:
                            print(f"      - Price €{listing.price_total:,} > €{config['criteria']['price_max']:,}")
                        
                        if listing.area_m2 and listing.area_m2 < config['criteria']['area_m2_min']:
                            print(f"      - Area {listing.area_m2}m² < {config['criteria']['area_m2_min']}m²")
                        
                        if listing.rooms and listing.rooms < config['criteria']['rooms_min']:
                            print(f"      - Rooms {listing.rooms} < {config['criteria']['rooms_min']}")
                        
                        if listing.price_total and listing.area_m2:
                            price_per_m2 = listing.price_total / listing.area_m2
                            if price_per_m2 > config['criteria']['price_per_m2_max']:
                                print(f"      - Price per m² €{price_per_m2:,.0f} > €{config['criteria']['price_per_m2_max']:,}")
                        
                        if listing.year_built and listing.year_built < config['criteria']['year_built_min']:
                            print(f"      - Year built {listing.year_built} < {config['criteria']['year_built_min']}")
                else:
                    print(f"   ❌ Failed to scrape")
                    
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