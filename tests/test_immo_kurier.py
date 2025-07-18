#!/usr/bin/env python3
"""
Quick test script for Immo Kurier scraper
"""

import sys
import os
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Project.Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from dataclasses import asdict

def test_immo_kurier():
    """Test the Immo Kurier scraper"""
    print("🧪 Testing Immo Kurier Scraper")
    print("=" * 50)
    
    # Create scraper
    scraper = ImmoKurierScraper()
    
    # Test URL extraction
    print("🔍 Testing URL extraction...")
    test_html = """
    <html>
        <body>
            <a href="/immobilien/test-1" data-href="/immobilien/test-1?params">Test 1</a>
            <a href="/immobilien/test-2" data-href="/immobilien/test-2?params">Test 2</a>
            <a href="/other-link">Other</a>
        </body>
    </html>
    """
    
    urls = scraper.extract_listing_urls(test_html)
    print(f"✅ Found {len(urls)} URLs: {urls}")
    
    # Test single listing scraping (with mock data)
    print("\n🔍 Testing single listing scraping...")
    test_listing_html = """
    <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body>
            <h1>Test Apartment - Beautiful Penthouse</h1>
            <div class="address">
                Teststraße 1, 1010 Wien
            </div>
            <div class="price">
                € 300.000,00
            </div>
            <div class="area">
                60,5 m²
            </div>
            <div class="rooms">
                2 Zi.
            </div>
            <div class="year-built">
                Baujahr: 1995
            </div>
            <div class="condition">
                Zustand: Renoviert
            </div>
            <div class="heating">
                Heizung: Fernwärme
            </div>
            <div class="energy-class">
                Energieklasse: B
            </div>
        </body>
    </html>
    """
    
    # Mock the request
    import requests
    from unittest.mock import patch
    
    with patch('requests.Session.get') as mock_get:
        mock_response = type('MockResponse', (), {
            'content': test_listing_html.encode('utf-8'),
            'raise_for_status': lambda self: None
        })()
        mock_get.return_value = mock_response
        
        result = scraper.scrape_single_listing("https://immo.kurier.at/immobilien/test")
        result_dict = asdict(result) if result else None
        if result_dict:
            print("✅ Successfully scraped listing:")
            print(f"   Title: {result_dict.get('title')}")
            print(f"   Price: €{result_dict.get('price_total'):,.0f}")
            print(f"   Area: {result_dict.get('area_m2')}m²")
            print(f"   Rooms: {result_dict.get('rooms')}")
            print(f"   Address: {result_dict.get('address')}")
            print(f"   District: {result_dict.get('bezirk')}")
            print(f"   Year Built: {result_dict.get('year_built')}")
            print(f"   Condition: {result_dict.get('condition')}")
            print(f"   Heating: {result_dict.get('heating')}")
            print(f"   Energy Class: {result_dict.get('energy_class')}")
            print(f"   Price per m²: €{result_dict.get('price_per_m2'):,.0f}")
            print(f"   Image: {result_dict.get('image_url')}")
            # Validate extracted data
            assert result_dict.get('title') == 'Test Apartment - Beautiful Penthouse', f"Title mismatch: {result_dict.get('title')}"
            assert result_dict.get('price_total') == 300000, f"Price mismatch: {result_dict.get('price_total')}"
            assert result_dict.get('area_m2') == 60.5, f"Area mismatch: {result_dict.get('area_m2')}"
            assert result_dict.get('rooms') == 2.0, f"Rooms mismatch: {result_dict.get('rooms')}"
            assert result_dict.get('bezirk') == '1010', f"District mismatch: {result_dict.get('bezirk')}"
            assert result_dict.get('year_built') == 1995, f"Year built mismatch: {result_dict.get('year_built')}"
            assert result_dict.get('condition') == 'Renoviert', f"Condition mismatch: {result_dict.get('condition')}"
            assert result_dict.get('heating') == 'Fernwärme', f"Heating mismatch: {result_dict.get('heating')}"
            assert result_dict.get('energy_class') == 'B', f"Energy class mismatch: {result_dict.get('energy_class')}"
            assert abs(result_dict.get('price_per_m2') - 4958.68) < 0.1, f"Price per m² mismatch: {result_dict.get('price_per_m2')}"
            print("✅ All data validation passed!")
        else:
            print("❌ Failed to scrape listing")
    
    print("\n✅ Immo Kurier scraper test completed!")

if __name__ == "__main__":
    test_immo_kurier() 