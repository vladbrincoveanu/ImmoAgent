import json
from scrape import WillhabenScraper
from ollama_analyzer import OllamaAnalyzer
from mongodb_handler import MongoDBHandler
from bs4 import BeautifulSoup
from typing import Optional
import os


def load_config():
    """Load configuration from config.json or config.default.json"""
    config_paths = ['config.json', 'immo-scouter/config.default.json']
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                print(f"✅ Loaded config from {config_path}")
                return config
            except Exception as e:
                print(f"❌ Error loading {config_path}: {e}")
                continue
    
    print("❌ No config file found!")
    return {}


def main():
    alert_url = "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387"
    
    # Load configuration
    config = load_config()
    
    # Create scraper instance with config
    scraper = WillhabenScraper(
        telegram_config={
            'enabled': True,
            'bot_token': config.get('telegram_bot_token'),
            'chat_id': config.get('telegram_chat_id')
        },
        mongo_uri=config.get('mongodb_uri')
    )
    
    # Test Telegram connection if enabled
    telegram_enabled = config.get('telegram_bot_token') and config.get('telegram_chat_id')
    if telegram_enabled and scraper.telegram_bot:
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


def test_ollama_connection():
    print("🧠 Testing Ollama connection...")
    ollama = OllamaAnalyzer()
    if ollama.is_available():
        print("✅ Ollama connection successful!")
        return True
    else:
        print("❌ Ollama connection failed!")
        return False

def test_mongo_connection():
    print("🍃 Testing MongoDB connection...")
    try:
        mongo = MongoDBHandler()
        # Try a simple insert/find
        test_doc = {"test": "connection"}
        mongo.collection.insert_one(test_doc)
        found = mongo.collection.find_one({"test": "connection"})
        mongo.collection.delete_one({"test": "connection"})
        if found:
            print("✅ MongoDB connection successful!")
            return True
        else:
            print("❌ MongoDB test document not found!")
            return False
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

def extract_monatsrate(self, soup: BeautifulSoup) -> Optional[float]:
    # Try to find the label span
    label_span = soup.find(lambda tag: tag.name == "span" and "Monatsrate" in tag.get_text())
    if label_span:
        # Try next sibling span
        value_span = label_span.find_next("span")
        if value_span:
            import re
            rate_match = re.search(r'€\s*([\d\.,]+)', value_span.get_text())
            if rate_match:
                rate_str = rate_match.group(1).replace('.', '').replace(',', '.')
                try:
                    return float(rate_str)
                except ValueError:
                    pass
    # Fallback: old logic
    calculator_form = soup.find('form', {'data-testid': 'mortgageCalculatorForm'})
    if calculator_form:
        form_text = calculator_form.get_text()
        import re
        monatsrate_patterns = [
            r'Monatsrate[:\s]*€\s*([\d\.,]+)',
            r'Monthly\s+Rate[:\s]*€\s*([\d\.,]+)',
            r'€\s*([\d\.,]+)\s*Monatsrate',
            r'€\s*([\d\.,]+)\s*monthly'
        ]
        for pattern in monatsrate_patterns:
            match = re.search(pattern, form_text, re.IGNORECASE)
            if match:
                rate_str = match.group(1).replace('.', '').replace(',', '.')
                try:
                    return float(rate_str)
                except ValueError:
                    pass
    return None

def extract_own_funds(self, soup: BeautifulSoup) -> Optional[float]:
    # Look for data-testid="ownFunds-input"
    own_funds_elem = soup.find(attrs={"data-testid": "ownFunds-input"})
    if own_funds_elem:
        import re
        value = own_funds_elem.get("value") or own_funds_elem.get_text()
        match = re.search(r'([\d\.,]+)', value)
        if match:
            value_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(value_str)
            except ValueError:
                pass
    return None

if __name__ == "__main__":
    ollama_ok = test_ollama_connection()
    mongo_ok = test_mongo_connection()
    if ollama_ok and mongo_ok:
        print("\n🚀 All systems go! Starting main job...\n")
        main()  # or whatever your main function is called
    else:
        print("\n❌ Startup checks failed. Fix the issues above before running the main job.\n")