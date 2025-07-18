#!/usr/bin/env python3
"""
Test script to run DerStandard and Immo Kurier scrapers only
to identify and fix UTF-8 encoding issues
"""

import logging
import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Project.Application.scraping.derstandard_scraper import DerStandardScraper
from Project.Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Project.Integration.mongodb_handler import MongoDBHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/scraper_test.log'),
        logging.StreamHandler()
    ]
)

def test_derstandard_scraper():
    """Test DerStandard scraper with UTF-8 handling"""
    print("🔍 Testing DerStandard Scraper...")
    
    try:
        scraper = DerStandardScraper(use_selenium=False)  # Disable Selenium for testing
        
        # Test with a small number of pages
        listings = scraper.scrape_search_results(scraper.search_url, max_pages=1)
        
        print(f"✅ DerStandard: Found {len(listings)} listings")
        
        # Test each listing for UTF-8 issues
        for i, listing in enumerate(listings):
            print(f"\n--- Listing {i+1} ---")
            try:
                # Convert listing to dict and test UTF-8 encoding
                listing_dict = listing.__dict__ if hasattr(listing, '__dict__') else dict(listing)
                
                # Test encoding of all string fields
                for key, value in listing_dict.items():
                    if isinstance(value, str):
                        try:
                            # Test UTF-8 encoding
                            encoded = value.encode('utf-8')
                            decoded = encoded.decode('utf-8')
                            print(f"✅ {key}: UTF-8 OK")
                        except UnicodeEncodeError as e:
                            print(f"❌ {key}: UTF-8 encoding error: {e}")
                            print(f"   Value: {repr(value)}")
                        except UnicodeDecodeError as e:
                            print(f"❌ {key}: UTF-8 decoding error: {e}")
                            print(f"   Value: {repr(value)}")
                
                print(f"✅ Listing {i+1} processed successfully")
                
            except Exception as e:
                print(f"❌ Error processing listing {i+1}: {e}")
        
        return listings
        
    except Exception as e:
        print(f"❌ Error testing DerStandard scraper: {e}")
        return []

def test_immo_kurier_scraper():
    """Test Immo Kurier scraper with UTF-8 handling"""
    print("\n🔍 Testing Immo Kurier Scraper...")
    
    try:
        scraper = ImmoKurierScraper()
        
        # Test with a small number of pages
        listings = scraper.scrape_search_results(scraper.search_url, max_pages=1)
        
        print(f"✅ Immo Kurier: Found {len(listings)} listings")
        
        # Test each listing for UTF-8 issues
        for i, listing in enumerate(listings):
            print(f"\n--- Listing {i+1} ---")
            try:
                # Convert listing to dict and test UTF-8 encoding
                listing_dict = listing.__dict__ if hasattr(listing, '__dict__') else dict(listing)
                
                # Test encoding of all string fields
                for key, value in listing_dict.items():
                    if isinstance(value, str):
                        try:
                            # Test UTF-8 encoding
                            encoded = value.encode('utf-8')
                            decoded = encoded.decode('utf-8')
                            print(f"✅ {key}: UTF-8 OK")
                        except UnicodeEncodeError as e:
                            print(f"❌ {key}: UTF-8 encoding error: {e}")
                            print(f"   Value: {repr(value)}")
                        except UnicodeDecodeError as e:
                            print(f"❌ {key}: UTF-8 decoding error: {e}")
                            print(f"   Value: {repr(value)}")
                
                print(f"✅ Listing {i+1} processed successfully")
                
            except Exception as e:
                print(f"❌ Error processing listing {i+1}: {e}")
        
        return listings
        
    except Exception as e:
        print(f"❌ Error testing Immo Kurier scraper: {e}")
        return []

def clean_utf8_string(text):
    """Clean UTF-8 string by removing problematic characters"""
    if not isinstance(text, str):
        return text
    
    try:
        # Try to encode and decode to identify issues
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        # Remove problematic characters
        cleaned = ''
        for char in text:
            try:
                char.encode('utf-8')
                cleaned += char
            except UnicodeEncodeError:
                # Replace problematic character with space
                cleaned += ' '
        return cleaned.strip()

if __name__ == "__main__":
    print("🧪 Starting Scraper UTF-8 Test...")
    
    # Test DerStandard scraper
    derstandard_listings = test_derstandard_scraper()
    
    # Test Immo Kurier scraper
    immo_kurier_listings = test_immo_kurier_scraper()
    
    print(f"\n📊 Test Results:")
    print(f"DerStandard: {len(derstandard_listings)} listings")
    print(f"Immo Kurier: {len(immo_kurier_listings)} listings")
    
    print("\n✅ UTF-8 encoding test completed!") 