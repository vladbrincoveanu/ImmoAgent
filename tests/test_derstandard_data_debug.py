#!/usr/bin/env python3
"""
Debug derStandard data extraction
See what data is extracted and why listings don't match criteria
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def main():
    """Debug data extraction"""
    print("🔍 DEBUGGING DERSTANDARD DATA EXTRACTION")
    print("=" * 60)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=True)
    print(f"✅ Scraper initialized")
    
    # Test with a few specific URLs
    test_urls = [
        "https://immobilien.derstandard.at/detail/14463580",
        "https://immobilien.derstandard.at/detail/14463407",
        "https://immobilien.derstandard.at/detail/14463404"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n🔍 Testing URL {i}: {url}")
        print("-" * 50)
        
        try:
            listing = scraper.scrape_single_listing(url)
            
            if listing:
                print(f"✅ Data extracted successfully")
                print(f"   Title: {listing.title}")
                print(f"   Price: €{listing.price_total:,}" if listing.price_total else "   Price: N/A")
                print(f"   Area: {listing.area_m2}m²" if listing.area_m2 else "   Area: N/A")
                print(f"   Rooms: {listing.rooms}" if listing.rooms else "   Rooms: N/A")
                print(f"   District: {listing.bezirk}" if listing.bezirk else "   District: N/A")
                print(f"   Year built: {listing.year_built}" if listing.year_built else "   Year built: N/A")
                print(f"   Price per m²: €{listing.price_per_m2:,.0f}" if listing.price_per_m2 else "   Price per m²: N/A")
                
                # Check criteria matching
                matches = scraper.meets_criteria(listing)
                print(f"   Matches criteria: {'✅ YES' if matches else '❌ NO'}")
                
                if not matches:
                    print("   ❌ Criteria check details:")
                    criteria = scraper.criteria
                    
                    # Price checks
                    if listing.price_total:
                        if criteria.get('price_max') and listing.price_total > criteria['price_max']:
                            print(f"     - Price €{listing.price_total:,} > max €{criteria['price_max']:,}")
                        if criteria.get('price_min') and listing.price_total < criteria['price_min']:
                            print(f"     - Price €{listing.price_total:,} < min €{criteria['price_min']:,}")
                    
                    # Price per m² checks
                    if listing.price_per_m2:
                        if criteria.get('price_per_m2_max') and listing.price_per_m2 > criteria['price_per_m2_max']:
                            print(f"     - Price per m² €{listing.price_per_m2:,.0f} > max €{criteria['price_per_m2_max']:,}")
                        if criteria.get('price_per_m2_min') and listing.price_per_m2 < criteria['price_per_m2_min']:
                            print(f"     - Price per m² €{listing.price_per_m2:,.0f} < min €{criteria['price_per_m2_min']:,}")
                    
                    # Area checks
                    if listing.area_m2:
                        if criteria.get('area_m2_min') and listing.area_m2 < criteria['area_m2_min']:
                            print(f"     - Area {listing.area_m2}m² < min {criteria['area_m2_min']}m²")
                        if criteria.get('area_m2_max') and listing.area_m2 > criteria['area_m2_max']:
                            print(f"     - Area {listing.area_m2}m² > max {criteria['area_m2_max']}m²")
                    
                    # Rooms checks
                    if listing.rooms:
                        if criteria.get('rooms_min') and listing.rooms < criteria['rooms_min']:
                            print(f"     - Rooms {listing.rooms} < min {criteria['rooms_min']}")
                        if criteria.get('rooms_max') and listing.rooms > criteria['rooms_max']:
                            print(f"     - Rooms {listing.rooms} > max {criteria['rooms_max']}")
                    
                    # Year built checks
                    if listing.year_built:
                        if criteria.get('year_built_min') and listing.year_built < criteria['year_built_min']:
                            print(f"     - Year built {listing.year_built} < min {criteria['year_built_min']}")
                        if criteria.get('year_built_max') and listing.year_built > criteria['year_built_max']:
                            print(f"     - Year built {listing.year_built} > max {criteria['year_built_max']}")
                
            else:
                print(f"❌ Failed to extract data")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()

if __name__ == "__main__":
    main() 