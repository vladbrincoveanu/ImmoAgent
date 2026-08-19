#!/usr/bin/env python3
"""
Simple derStandard scraper test
Tests basic functionality without complex logic
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import time

# Add Project directory to path for imports
# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Project'))

from Project.Application.scraping.derstandard_scraper import DerStandardScraper
from Project.Integration.mongodb_handler import MongoDBHandler
from Project.Application.helpers.utils import load_config

def main():
    """Simple test function"""
    print("🚀 SIMPLE DERSTANDARD SCRAPER TEST")
    print("=" * 50)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded: {config.get('mongodb_uri', 'No URI')}")
    
    # Test MongoDB connection
    print("🔧 Testing MongoDB connection...")
    mongo_handler = MongoDBHandler(uri=config.get('mongodb_uri'))
    test_doc = {'url': 'test-simple', 'source': 'derstandard', 'title': 'Simple Test'}
    insert_result = mongo_handler.insert_listing(test_doc)
    print(f"✅ MongoDB test insert: {insert_result}")
    
    # Get current count
    current_count = mongo_handler.collection.count_documents({"source": "derstandard"})
    print(f"📊 Current derStandard count: {current_count}")
    
    # Initialize scraper
    print("🔧 Initializing scraper...")
    scraper = DerStandardScraper(use_selenium=True)
    print("✅ Scraper initialized")
    
    # Test URL extraction
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    print(f"🔍 Testing URL extraction from: {test_url}")
    
    try:
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            # Test scraping first URL
            first_url = urls[0]
            print(f"🔍 Testing scraping: {first_url}")
            
            # Check if already exists
            if not mongo_handler.listing_exists(first_url):
                listing = scraper.scrape_single_listing(first_url)
                
                if listing:
                    print(f"✅ Successfully scraped: {listing.title}")
                    
                    if scraper.meets_criteria(listing):
                        print("✅ Matches criteria")
                        
                        listing_dict = scraper._ensure_serializable(listing)
                        
                        if mongo_handler.insert_listing(listing_dict):
                            print("💾 Successfully saved to MongoDB!")
                            new_count = mongo_handler.collection.count_documents({"source": "derstandard"})
                            print(f"📊 New count: {new_count}")
                        else:
                            print("❌ Failed to save to MongoDB")
                    else:
                        print("❌ Does not match criteria")
                else:
                    print("❌ Failed to scrape listing")
            else:
                print("⏭️  Already exists in database")
        else:
            print("❌ No URLs found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()
            print("🧹 Selenium driver closed")
        
        mongo_handler.close()
        print("🧹 MongoDB connection closed")

if __name__ == "__main__":
    main() 
