#!/usr/bin/env python3
"""
Test script for the reworked Immo Kurier scraper
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.helpers.utils import load_config
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_immo_kurier_scraper():
    """Test the reworked Immo Kurier scraper"""
    
    print("🧪 Testing reworked Immo Kurier scraper...")
    
    # Load config
    config = load_config()
    
    # Initialize scraper
    scraper = ImmoKurierScraper(config=config)
    
    # Test URL extraction
    print("\n🔍 Testing URL extraction...")
    search_url = "https://immo.kurier.at/suche?l=Wien&r=0km&_multiselect_r=0km&a=at.wien&t=all%3Asale%3Aliving&pf=&pt=&rf=&rt=&sf=&st="
    
    try:
        response = scraper.session.get(search_url, headers=scraper.headers)
        response.raise_for_status()
        soup = scraper.session.get(search_url, headers=scraper.headers).content
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(soup, 'html.parser')
        
        urls = scraper.extract_listing_urls(soup)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            print(f"   First URL: {urls[0]}")
            
            # Test single listing scraping
            print(f"\n🔍 Testing single listing scraping...")
            listing = scraper.scrape_single_listing(urls[0])
            
            if listing:
                print(f"✅ Successfully scraped listing:")
                print(f"   Title: {listing.title}")
                print(f"   Price: €{listing.price_total:,.0f}" if listing.price_total else "   Price: N/A")
                print(f"   Area: {listing.area_m2}m²" if listing.area_m2 else "   Area: N/A")
                print(f"   Rooms: {listing.rooms}" if listing.rooms else "   Rooms: N/A")
                print(f"   District: {listing.bezirk}" if listing.bezirk else "   District: N/A")
                print(f"   Address: {listing.address}" if listing.address else "   Address: N/A")
                print(f"   Source: {listing.source}")
                print(f"   Score: {listing.score}" if hasattr(listing, 'score') else "   Score: N/A")
                
                # Test criteria matching
                print(f"\n🔍 Testing criteria matching...")
                matches = scraper.meets_criteria(listing)
                print(f"   Meets criteria: {matches}")
                
                # Test MongoDB saving
                if scraper.mongo:
                    print(f"\n💾 Testing MongoDB saving...")
                    try:
                        # Convert listing to dict for MongoDB
                        listing_dict = listing.__dict__.copy()
                        if scraper.mongo.insert_listing(listing_dict):
                            print(f"   ✅ Successfully saved to MongoDB")
                        else:
                            print(f"   💾 Listing already exists in MongoDB")
                    except Exception as e:
                        print(f"   ❌ Error saving to MongoDB: {e}")
                
                # Test Telegram sending
                if scraper.telegram_bot and hasattr(listing, 'score') and listing.score and listing.score > 40:
                    print(f"\n📱 Testing Telegram sending...")
                    try:
                        scraper.telegram_bot.send_listing(listing)
                        print(f"   ✅ Successfully sent to Telegram")
                    except Exception as e:
                        print(f"   ❌ Error sending to Telegram: {e}")
            else:
                print(f"❌ Failed to scrape listing")
        else:
            print(f"❌ No URLs found")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    
    finally:
        scraper.close()

if __name__ == "__main__":
    test_immo_kurier_scraper() 