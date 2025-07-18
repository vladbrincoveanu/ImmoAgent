#!/usr/bin/env python3
"""
Debug script to test DerStandard scraper and see what fields are being extracted
"""

import logging
import sys
import os

# Add the Project directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Project'))

from Project.Application.scraping.derstandard_scraper import DerStandardScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def debug_derstandard_scraper():
    """Debug DerStandard scraper to see what fields are extracted"""
    print("🔍 Debugging DerStandard Scraper...")
    
    try:
        scraper = DerStandardScraper(use_selenium=True)  # Enable Selenium for dynamic content
        
        # Get just one listing URL to test
        listing_urls = scraper.extract_listing_urls(scraper.search_url, max_pages=1)
        
        if not listing_urls:
            print("❌ No listing URLs found")
            return
        
        # Test the first listing
        test_url = listing_urls[0]
        print(f"🔍 Testing URL: {test_url}")
        
        # Temporarily disable validation to see what's extracted
        original_validate = scraper.validate_listing_data
        
        def always_true(data):
            return True
        
        scraper.validate_listing_data = always_true
        
        listing = scraper.scrape_single_listing(test_url)
        
        if listing:
            print("\n✅ Listing extracted successfully!")
            print("--- Extracted Fields ---")
            
            # Check all required fields
            required_fields = ['url', 'price_total', 'area_m2', 'rooms', 'bezirk', 'address']
            
            for field in required_fields:
                value = getattr(listing, field, None)
                status = "✅" if value else "❌"
                print(f"{status} {field}: {value}")
            
            print("\n--- All Fields ---")
            for attr in dir(listing):
                if not attr.startswith('_'):
                    value = getattr(listing, attr)
                    if not callable(value):
                        print(f"{attr}: {value}")
            
            # Test validation
            is_valid = scraper.validate_listing_data(listing)
            print(f"\nValidation result: {'✅ Valid' if is_valid else '❌ Invalid'}")
            
        else:
            print("❌ Failed to extract listing")
            
    except Exception as e:
        print(f"❌ Error debugging DerStandard scraper: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_derstandard_scraper() 