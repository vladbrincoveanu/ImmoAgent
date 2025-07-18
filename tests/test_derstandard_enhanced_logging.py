#!/usr/bin/env python3
"""
Test enhanced logging for derStandard scraper
Verify score calculation and Telegram status logging
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.helpers.utils import load_config

def main():
    """Test enhanced logging"""
    print("🧪 TESTING ENHANCED DERSTANDARD LOGGING")
    print("=" * 60)
    
    # Load config
    config = load_config()
    print(f"✅ Config loaded")
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=True)
    print(f"✅ Scraper initialized")
    
    # Test URL extraction
    test_url = "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3"
    print(f"\n🔍 Testing URL extraction from: {test_url}")
    
    try:
        urls = scraper.extract_listing_urls(test_url, max_pages=1)
        print(f"✅ Found {len(urls)} URLs")
        
        if urls:
            # Test first 3 URLs to see enhanced logging
            for i, url in enumerate(urls[:3], 1):
                print(f"\n🔍 [{i}/3] Testing: {url}")
                
                listing = scraper.scrape_single_listing(url)
                
                if listing:
                    print(f"📊 EXTRACTED DATA:")
                    print(f"   Title: {listing.title}")
                    print(f"   Price: €{listing.price_total:,}" if listing.price_total else "   Price: None")
                    print(f"   Area: {listing.area_m2}m²" if listing.area_m2 else "   Area: None")
                    print(f"   Rooms: {listing.rooms}" if listing.rooms else "   Rooms: None")
                    print(f"   District: {listing.bezirk}" if listing.bezirk else "   District: None")
                    
                    # Test criteria matching with enhanced logging
                    print(f"\n🔍 TESTING CRITERIA MATCHING:")
                    matches = scraper.meets_criteria(listing)
                    
                    if matches:
                        # Calculate score for logging
                        try:
                            from Application.scoring import score_apartment_simple
                            score = score_apartment_simple(listing.__dict__)
                            listing.score = score
                            
                            # Check if score is above 40 for Telegram
                            score_above_40 = score > 40
                            telegram_status = "📱 Will be sent to Telegram" if score_above_40 else "⏭️  Score too low for Telegram"
                            
                            print(f"✅ MATCHES CRITERIA: {listing.title}")
                            print(f"   📊 Score: {score:.1f}/100 - {telegram_status}")
                            print(f"   💰 Price: €{listing.price_total:,}" if listing.price_total else "   💰 Price: N/A")
                            print(f"   📐 Area: {listing.area_m2}m²" if listing.area_m2 else "   📐 Area: N/A")
                            print(f"   🏠 Rooms: {listing.rooms}" if listing.rooms else "   🏠 Rooms: N/A")
                            print(f"   📍 District: {listing.bezirk}" if listing.bezirk else "   📍 District: N/A")
                            
                        except Exception as e:
                            print(f"⚠️  Could not calculate score: {e}")
                    else:
                        print(f"❌ Does not match criteria: {listing.title}")
                else:
                    print(f"   ❌ Failed to scrape listing")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()
            print("🧹 Selenium driver closed")

if __name__ == "__main__":
    main() 