#!/usr/bin/env python3
"""
Quick test of derStandard scraper
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

import logging

from Application.scraping.derstandard_scraper import DerStandardScraper

def main():
    """Quick test"""
    print("🧪 QUICK DERSTANDARD TEST")
    print("=" * 40)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initialize scraper
    print("🔧 Initializing scraper...")
    scraper = DerStandardScraper(use_selenium=True)
    print("✅ Scraper initialized")
    
    # Test URL
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    print(f"🔍 Testing URL: {test_url}")
    
    try:
        # Extract URLs
        print("📄 Extracting URLs...")
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            # Test first URL
            test_url = urls[0]
            print(f"🔍 Testing first URL: {test_url}")
            
            listing = scraper.scrape_single_listing(test_url)
            
            if listing:
                print(f"✅ Successfully scraped: {listing.title}")
                print(f"💰 Price: €{listing.price_total:,.0f}" if listing.price_total else "💰 Price: N/A")
                print(f"📐 Area: {listing.area_m2}m²" if listing.area_m2 else "📐 Area: N/A")
                print(f"🛏️  Rooms: {listing.rooms}" if listing.rooms else "🛏️  Rooms: N/A")
                print(f"📍 Address: {listing.address}" if listing.address else "📍 Address: N/A")
                
                # Test saving to MongoDB
                print("💾 Testing MongoDB save...")
                listing_dict = scraper._ensure_serializable(listing)
                
                if scraper.mongo.insert_listing(listing_dict):
                    print("✅ Successfully saved to MongoDB!")
                else:
                    print("❌ Failed to save to MongoDB")
            else:
                print("❌ Failed to scrape listing")
        else:
            print("❌ No URLs found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Clean up
    if hasattr(scraper, 'driver') and scraper.driver:
        scraper.driver.quit()
        print("🧹 Selenium driver closed")

if __name__ == "__main__":
    main() 