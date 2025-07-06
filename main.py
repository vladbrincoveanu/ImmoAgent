import json
from scrape import WillhabenScraper


def load_telegram_config():
    """Load Telegram configuration from file"""
    try:
        with open('telegram_config.json', 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("⚠️  telegram_config.json not found - Telegram notifications disabled")
        return {"enabled": False}
    except json.JSONDecodeError:
        print("⚠️  Invalid telegram_config.json - Telegram notifications disabled")
        return {"enabled": False}


def main():
    alert_url = "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387"
    
    # Load Telegram configuration
    telegram_config = load_telegram_config()
    
    # Create scraper instance with Telegram config
    scraper = WillhabenScraper(telegram_config=telegram_config)
    
    # Test Telegram connection if enabled
    if telegram_config.get('enabled') and scraper.telegram_bot:
        print("🧪 Testing Telegram connection...")
        if scraper.telegram_bot.test_connection():
            print("✅ Telegram connection successful!")
        else:
            print("❌ Telegram connection failed - check your bot token and chat ID")
    
    # Scrape the search results
    matching_listings = scraper.scrape_search_agent_page(alert_url)
    
    # Save results
    if matching_listings:
        with open('filtered_listings.json', 'w', encoding='utf-8') as f:
            json.dump(matching_listings, f, indent=2, ensure_ascii=False)
        
        print(f"\nFound {len(matching_listings)} listings that meet your criteria!")
        
        # Print summary
        for listing in matching_listings:
            print(f"\n📍 {listing['bezirk']} - €{listing['price_total']:,}")
            print(f"   {listing['area_m2']}m² - €{listing['price_per_m2']}/m²")
            print(f"   U-Bahn: {listing['ubahn_walk_minutes']} min walk")
            print(f"   {listing['url']}")
    else:
        print("No listings found matching your criteria.")

if __name__ == "__main__":
    main()