#!/usr/bin/env python3
"""
Test criteria loading and application in derStandard scraper
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config
from Domain.listing import Listing

def main():
    """Test criteria loading and application"""
    print("🧪 TESTING CRITERIA LOADING AND APPLICATION")
    print("=" * 60)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded with {len(config.get('criteria', {}))} criteria")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=False)  # Don't use Selenium for this test
    print(f"✅ Scraper initialized")
    print(f"🔧 Scraper criteria count: {len(scraper.criteria)}")
    
    # Test with a sample listing that should match criteria
    test_listing = Listing(
        url="https://test.com",
        source="derstandard",
        source_enum="derstandard",
        title="Test Listing",
        price_total=500000,  # Within €1M limit
        area_m2=80,  # Within 20-500m² range
        rooms=3,  # Within 1-10 range
        bezirk="1010",  # Valid Vienna district
        address="Test Address, 1010 Wien",
        year_built=1990,  # After 1960
        price_per_m2=6250,  # Within €1K-20K range
        processed_at=1234567890
    )
    
    print(f"\n🔍 Testing criteria matching with sample listing:")
    print(f"   Price: €{test_listing.price_total:,}")
    print(f"   Area: {test_listing.area_m2}m²")
    print(f"   Rooms: {test_listing.rooms}")
    print(f"   District: {test_listing.bezirk}")
    print(f"   Year built: {test_listing.year_built}")
    print(f"   Price per m²: €{test_listing.price_per_m2:,.0f}")
    
    # Test criteria matching
    matches = scraper.meets_criteria(test_listing)
    print(f"   Matches criteria: {'✅ YES' if matches else '❌ NO'}")
    
    if not matches:
        print("   ❌ Criteria check details:")
        criteria = scraper.criteria
        
        # Price checks
        if test_listing.price_total:
            if criteria.get('price_max') and test_listing.price_total > criteria['price_max']:
                print(f"     - Price €{test_listing.price_total:,} > max €{criteria['price_max']:,}")
            if criteria.get('price_min') and test_listing.price_total < criteria['price_min']:
                print(f"     - Price €{test_listing.price_total:,} < min €{criteria['price_min']:,}")
        
        # Price per m² checks
        if test_listing.price_per_m2:
            if criteria.get('price_per_m2_max') and test_listing.price_per_m2 > criteria['price_per_m2_max']:
                print(f"     - Price per m² €{test_listing.price_per_m2:,.0f} > max €{criteria['price_per_m2_max']:,}")
            if criteria.get('price_per_m2_min') and test_listing.price_per_m2 < criteria['price_per_m2_min']:
                print(f"     - Price per m² €{test_listing.price_per_m2:,.0f} < min €{criteria['price_per_m2_min']:,}")
        
        # Area checks
        if test_listing.area_m2:
            if criteria.get('area_m2_min') and test_listing.area_m2 < criteria['area_m2_min']:
                print(f"     - Area {test_listing.area_m2}m² < min {criteria['area_m2_min']}m²")
            if criteria.get('area_m2_max') and test_listing.area_m2 > criteria['area_m2_max']:
                print(f"     - Area {test_listing.area_m2}m² > max {criteria['area_m2_max']}m²")
        
        # Rooms checks
        if test_listing.rooms:
            if criteria.get('rooms_min') and test_listing.rooms < criteria['rooms_min']:
                print(f"     - Rooms {test_listing.rooms} < min {criteria['rooms_min']}")
            if criteria.get('rooms_max') and test_listing.rooms > criteria['rooms_max']:
                print(f"     - Rooms {test_listing.rooms} > max {criteria['rooms_max']}")
        
        # Year built checks
        if test_listing.year_built:
            if criteria.get('year_built_min') and test_listing.year_built < criteria['year_built_min']:
                print(f"     - Year built {test_listing.year_built} < min {criteria['year_built_min']}")
            if criteria.get('year_built_max') and test_listing.year_built > criteria['year_built_max']:
                print(f"     - Year built {test_listing.year_built} > max {criteria['year_built_max']}")
    
    print(f"\n📋 Current criteria:")
    for key, value in scraper.criteria.items():
        print(f"   {key}: {value}")

if __name__ == "__main__":
    main() 