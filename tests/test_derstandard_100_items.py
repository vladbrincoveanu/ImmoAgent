#!/usr/bin/env python3
"""
Comprehensive derStandard scraper test
Scrapes until we reach 100 items in the database
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import time
import logging
from datetime import datetime

# Add Project directory to path for imports
# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config

pytestmark = pytest.mark.smoke

def get_current_db_count():
    """Get current count of derStandard listings in database"""
    try:
        config = load_config()
        mongo_handler = MongoDBHandler(
            uri=config.get('mongodb_uri', 'mongodb://localhost:27017/'),
            db_name=config.get('mongodb_db_name', 'immo'),
            collection_name=config.get('mongodb_collection_name', 'listings')
        )
        count = mongo_handler.collection.count_documents({"source": "derstandard"})
        mongo_handler.close()
        return count
    except Exception as e:
        print(f"❌ Error getting database count: {e}")
        return 0

def main():
    """Main scraping function"""
    print("🚀 DERSTANDARD SCRAPER - TARGET: 100 ITEMS")
    print("=" * 60)
    
    # Set up logging
    # Ensure log directory exists
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('log/derstandard_scraping.log'),
            logging.StreamHandler()
        ]
    )
    
    # Get initial count
    initial_count = get_current_db_count()
    print(f"📊 Initial database count: {initial_count} derStandard listings")
    
    target_count = 100
    current_count = initial_count
    
    if current_count >= target_count:
        print(f"🎉 Already have {current_count} items! Target reached.")
        return
    
    # Initialize scraper and MongoDB handler
    print("🔧 Initializing derStandard scraper and MongoDB handler...")
    config = load_config()
    scraper = DerStandardScraper(use_selenium=True)
    mongo_handler = MongoDBHandler(
        uri=config.get('mongodb_uri', 'mongodb://localhost:27017/'),
        db_name=config.get('mongodb_db_name', 'immo'),
        collection_name=config.get('mongodb_collection_name', 'listings')
    )
    print("✅ Components initialized")
    
    # Test URLs to scrape
    test_urls = [
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=2",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=1",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung",
        "https://immobilien.derstandard.at/suche/wien/kaufen-haus",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?priceFrom=200000&priceTo=500000",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?priceFrom=500000&priceTo=1000000",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?areaFrom=50&areaTo=100",
        "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?areaFrom=100&areaTo=200"
    ]
    
    total_saved = 0
    
    try:
        for url_index, search_url in enumerate(test_urls, 1):
            if current_count >= target_count:
                break
                
            print(f"\n�� SCRAPING URL {url_index}/{len(test_urls)}")
            print(f"📍 URL: {search_url}")
            print(f"📊 Current count: {current_count}/{target_count}")
            
            try:
                # Start with 1 page, then increase if needed
                max_pages = 1
                while current_count < target_count and max_pages <= 5:
                    print(f"\n📄 Scraping page {max_pages}...")
                    
                    # Extract URLs from this page
                    urls = scraper.extract_listing_urls(search_url, max_pages=max_pages)
                    print(f"✅ Found {len(urls)} URLs on page {max_pages}")
                    
                    if not urls:
                        print("📭 No more URLs found, moving to next search URL")
                        break
                    
                    # Scrape each URL
                    page_saved = 0
                    for i, url in enumerate(urls, 1):
                        if current_count >= target_count:
                            break
                            
                        print(f"🔍 [{i}/{len(urls)}] Scraping: {url}")
                        
                        try:
                            # Check if already exists
                            if mongo_handler.listing_exists(url):
                                print(f"⏭️  Already exists, skipping")
                                continue
                            
                            # Scrape the listing
                            listing = scraper.scrape_single_listing(url)
                            
                            if listing:
                                if scraper.meets_criteria(listing):
                                    print(f"✅ MATCHES CRITERIA: {listing.title}")
                                    
                                    listing_dict = scraper._ensure_serializable(listing)
                                    
                                    if mongo_handler.insert_listing(listing_dict):
                                        page_saved += 1
                                        total_saved += 1
                                        current_count += 1
                                        print(f"💾 SAVED! Total: {current_count}/{target_count}")
                                        
                                        # Progress update every 10 items
                                        if current_count % 10 == 0:
                                            print(f"🎉 PROGRESS: {current_count}/{target_count} items saved!")
                                        
                                        if current_count >= target_count:
                                            print(f"🎉 TARGET REACHED! {current_count} items in database")
                                            break
                                    else:
                                        print(f"⚠️  Failed to save to MongoDB")
                                else:
                                    print(f"❌ Does not match criteria")
                            else:
                                print(f"❌ Failed to scrape")
                                
                        except Exception as e:
                            print(f"❌ Error processing URL {url}: {e}")
                            continue
                        
                        # Rate limiting
                        time.sleep(1)
                    
                    print(f"📊 Page {max_pages} complete: {page_saved} new items saved")
                    
                    if page_saved == 0:
                        print("📭 No new items on this page, trying next page...")
                    
                    max_pages += 1
                    
            except Exception as e:
                print(f"❌ Error scraping URL {url_index}: {e}")
                logging.error(f"Error scraping {search_url}: {e}")
                continue
                
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}")
    finally:
        # Clean up
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()
            print("🧹 Selenium driver closed")
        
        mongo_handler.close()
        print("🧹 MongoDB connection closed")
    
    # Final summary
    final_count = get_current_db_count()
    print(f"\n🎉 SCRAPING COMPLETE!")
    print("=" * 60)
    print(f"📊 Initial count: {initial_count}")
    print(f"📊 Final count: {final_count}")
    print(f"📊 New items added: {final_count - initial_count}")
    print(f"📊 Target: {target_count}")
    
    if final_count >= target_count:
        print(f"✅ SUCCESS! Target of {target_count} items reached!")
    else:
        print(f"⚠️  Target not reached. Only {final_count}/{target_count} items found.")

if __name__ == "__main__":
    main() 
