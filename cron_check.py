#!/usr/bin/env python3
"""
Cron job script for checking new property listings
Run this script every 5-10 minutes using cron:
*/5 * * * * /usr/bin/python3 /path/to/immo-scouter/cron_check.py
"""

import sys
import os
import json
from datetime import datetime
from scrape import WillhabenScraper

def main():
    """Quick check for new listings - designed for cron execution"""
    alert_url = "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387"
    
    print(f"🔍 Quick check at {datetime.now()}")
    
    try:
        scraper = WillhabenScraper()
        
        # Get all listings
        all_listings = scraper.scrape_search_agent_page(alert_url)
        
        if not all_listings:
            print("❌ No listings found")
            return
        
        print(f"📋 Found {len(all_listings)} total listings")
        
        # Check for matches
        matching_listings = []
        for listing in all_listings:
            if scraper.meets_criteria(listing):
                matching_listings.append(listing)
        
        if matching_listings:
            print(f"🎉 Found {len(matching_listings)} matching listings!")
            
            # Save matches with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"cron_matches_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'matches': matching_listings
                }, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Saved matches to {filename}")
            
            # Print summary
            for listing in matching_listings:
                print(f"✅ {listing.get('bezirk', 'N/A')} - €{listing.get('price_total', 'N/A'):,} - {listing.get('area_m2', 'N/A')}m²")
                print(f"   {listing.get('url', 'N/A')}")
        else:
            print("❌ No matching listings found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 