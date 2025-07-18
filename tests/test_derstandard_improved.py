#!/usr/bin/env python3
"""
Test script for improved derStandard scraper
Tests image extraction and complete field population
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import json
import time

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def test_derstandard_scraper():
    """Test the improved derStandard scraper"""
    print("🧪 TESTING IMPROVED DERSTANDARD SCRAPER")
    print("=" * 60)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ No configuration found")
        return
    
    # Initialize scraper
    scraper = DerStandardScraper(config=config, use_selenium=False)  # Use requests for testing
    
    # First, get a fresh URL from search results
    print("🔍 Getting fresh URLs from search results...")
    search_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    
    try:
        urls = scraper.extract_listing_urls(search_url, max_pages=1)
        if not urls:
            print("❌ No URLs found in search results")
            return
        
        test_url = urls[0]  # Use the first URL
        print(f"✅ Found {len(urls)} URLs, testing: {test_url}")
        
    except Exception as e:
        print(f"❌ Error getting URLs: {e}")
        return
    
    print(f"🔍 Testing URL: {test_url}")
    
    try:
        # Scrape the listing
        start_time = time.time()
        listing = scraper.scrape_single_listing(test_url)
        extraction_time = time.time() - start_time
        
        if not listing:
            print("❌ Failed to extract listing data")
            return
        
        print(f"✅ Extracted in {extraction_time:.2f}s")
        
        # Print all extracted data
        print("\n📊 EXTRACTED DATA:")
        print("=" * 40)
        
        # Basic info
        print(f"Title: {listing.title}")
        print(f"URL: {listing.url}")
        print(f"Source: {listing.source}")
        print(f"Source Enum: {listing.source_enum}")
        
        # Location
        print(f"Address: {listing.address}")
        print(f"Bezirk: {listing.bezirk}")
        
        # Financial
        print(f"Price Total: €{listing.price_total:,}" if listing.price_total else "Price Total: None")
        print(f"Price per m²: €{listing.price_per_m2:,.2f}" if listing.price_per_m2 else "Price per m²: None")
        print(f"Betriebskosten: €{listing.betriebskosten:,.2f}" if listing.betriebskosten else "Betriebskosten: None")
        
        # Property details
        print(f"Area: {listing.area_m2}m²" if listing.area_m2 else "Area: None")
        print(f"Rooms: {listing.rooms}" if listing.rooms else "Rooms: None")
        print(f"Year Built: {listing.year_built}" if listing.year_built else "Year Built: None")
        print(f"Floor: {listing.floor}" if listing.floor else "Floor: None")
        print(f"Condition: {listing.condition}" if listing.condition else "Condition: None")
        
        # Energy and heating
        print(f"Heating: {listing.heating}" if listing.heating else "Heating: None")
        print(f"Heating Type: {listing.heating_type}" if listing.heating_type else "Heating Type: None")
        print(f"Energy Carrier: {listing.energy_carrier}" if listing.energy_carrier else "Energy Carrier: None")
        print(f"Energy Class: {listing.energy_class}" if listing.energy_class else "Energy Class: None")
        print(f"HWB Value: {listing.hwb_value}" if listing.hwb_value else "HWB Value: None")
        print(f"FGEE Value: {listing.fgee_value}" if listing.fgee_value else "FGEE Value: None")
        
        # Other details
        print(f"Parking: {listing.parking}" if listing.parking else "Parking: None")
        print(f"Available From: {listing.available_from}" if listing.available_from else "Available From: None")
        print(f"Special Features: {listing.special_features}" if listing.special_features else "Special Features: []")
        
        # Infrastructure
        print(f"U-Bahn Walk: {listing.ubahn_walk_minutes} min" if listing.ubahn_walk_minutes else "U-Bahn Walk: None")
        print(f"School Walk: {listing.school_walk_minutes} min" if listing.school_walk_minutes else "School Walk: None")
        
        # Financial calculations
        print(f"Calculated Monatsrate: €{listing.calculated_monatsrate:,.2f}" if listing.calculated_monatsrate else "Calculated Monatsrate: None")
        print(f"Total Monthly Cost: €{listing.total_monthly_cost:,.2f}" if listing.total_monthly_cost else "Total Monthly Cost: None")
        
        # Image
        print(f"Image URL: {listing.image_url}" if listing.image_url else "Image URL: None")
        
        # Metadata
        print(f"Processed At: {listing.processed_at}")
        print(f"Sent to Telegram: {listing.sent_to_telegram}")
        print(f"Score: {listing.score}")
        
        # Check for null values in critical fields
        print("\n🔍 NULL VALUE CHECK:")
        print("=" * 30)
        
        critical_fields = [
            'title', 'price_total', 'area_m2', 'rooms', 'bezirk', 'address'
        ]
        
        null_count = 0
        for field in critical_fields:
            value = getattr(listing, field, None)
            if value is None or value == "":
                print(f"❌ {field}: NULL/EMPTY")
                null_count += 1
            else:
                print(f"✅ {field}: {value}")
        
        print(f"\n📈 SUMMARY:")
        print(f"Critical fields with data: {len(critical_fields) - null_count}/{len(critical_fields)}")
        print(f"Image extracted: {'✅' if listing.image_url else '❌'}")
        print(f"Price per m² calculated: {'✅' if listing.price_per_m2 else '❌'}")
        print(f"Betriebskosten estimated: {'✅' if listing.betriebskosten else '❌'}")
        print(f"Mortgage details calculated: {'✅' if listing.calculated_monatsrate else '❌'}")
        
        if null_count == 0:
            print("\n🎉 All critical fields have data!")
        else:
            print(f"\n⚠️ {null_count} critical fields are missing data")
        
    except Exception as e:
        print(f"❌ Error testing scraper: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_derstandard_scraper() 