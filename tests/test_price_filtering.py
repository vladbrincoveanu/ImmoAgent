#!/usr/bin/env python3
"""
Test script to verify "Preis auf Anfrage" filtering in Immo Kurier scraper
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.helpers.utils import load_config
from bs4 import BeautifulSoup

def test_price_filtering():
    """Test that 'Preis auf Anfrage' is properly filtered out"""
    print("🧪 Testing 'Preis auf Anfrage' filtering")
    print("=" * 50)
    
    # Load config
    config = load_config()
    scraper = ImmoKurierScraper(config=config)
    
    # Test cases with different price formats
    test_cases = [
        # Valid prices
        ("€599.000,00", 599000.0),
        ("599.000 EUR", 599000.0),
        ("Kaufpreis: 450.000", 450000.0),
        ("Preis: 350.000€", 350000.0),
        
        # Invalid prices (should return None)
        ("Preis auf Anfrage", None),
        ("Kaufpreis auf Anfrage", None),
        ("€ auf Anfrage", None),
        ("Preis: Auf Anfrage", None),
        ("Kaufpreis: auf anfrage", None),
        ("Preis: ANFRAGE", None),
    ]
    
    print("🔍 Testing price extraction...")
    for test_text, expected in test_cases:
        # Create a simple HTML structure for testing
        html = f'<div class="price">{test_text}</div>'
        soup = BeautifulSoup(html, 'html.parser')
        
        # Test the extract_price method
        result = scraper.extract_price(soup)
        
        if result == expected:
            print(f"   ✅ '{test_text}' -> {result}")
        else:
            print(f"   ❌ '{test_text}' -> {result} (expected: {expected})")
    
    print("\n🔍 Testing criteria filtering...")
    
    # Test with a sample listing that should be filtered out
    from Domain.listing import Listing
    from Domain.sources import Source
    
    # Test listing with 2 rooms (should be filtered out)
    test_listing_2rooms = Listing(
        url="https://test.com",
        source=Source.IMMO_KURIER,
        title="Test 2-room apartment",
        price_total=500000,
        area_m2=50,
        rooms=2.0,  # Below minimum of 3
        bezirk="1010",
        year_built=1990,
        processed_at=1234567890
    )
    
    # Test listing with old year (should be filtered out)
    test_listing_old = Listing(
        url="https://test.com",
        source=Source.IMMO_KURIER,
        title="Test old apartment",
        price_total=500000,
        area_m2=80,
        rooms=3.0,
        bezirk="1010",
        year_built=1960,  # Below minimum of 1970
        processed_at=1234567890
    )
    
    # Test listing that should pass
    test_listing_good = Listing(
        url="https://test.com",
        source=Source.IMMO_KURIER,
        title="Test good apartment",
        price_total=500000,
        area_m2=80,
        rooms=3.0,
        bezirk="1010",
        year_built=1990,  # Above minimum of 1970
        processed_at=1234567890
    )
    
    # Test criteria matching
    print(f"   2-room apartment (rooms=2): {'❌ REJECTED' if not scraper.meets_criteria(test_listing_2rooms) else '✅ ACCEPTED'}")
    print(f"   Old apartment (year=1960): {'❌ REJECTED' if not scraper.meets_criteria(test_listing_old) else '✅ ACCEPTED'}")
    print(f"   Good apartment (3 rooms, 1990): {'✅ ACCEPTED' if scraper.meets_criteria(test_listing_good) else '❌ REJECTED'}")
    
    print("\n✅ Price filtering tests completed!")

if __name__ == "__main__":
    test_price_filtering() 