import logging
import sys
import os

# Add the Project directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Project'))

from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Project.Application.scraping.derstandard_scraper import DerStandardScraper
from Project.Application.analyzer import StructuredAnalyzer
from Project.Integration.mongodb_handler import MongoDBHandler
from Project.Integration.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/immo-scouter.log'),
        logging.StreamHandler()
    ]
)

def scrape_willhaben(max_listings: int = 10):
    """Scrape listings from Willhaben"""
    scraper = WillhabenScraper()
    listings = scraper.scrape_search_results(max_listings=max_listings)
    return listings

def scrape_immo_kurier(max_listings: int = 10):
    """Scrape listings from Immo Kurier"""
    scraper = ImmoKurierScraper()
    listings = scraper.scrape_search_results(max_listings=max_listings)
    return listings

def scrape_derstandard(max_listings: int = 10):
    """Scrape listings from derStandard"""
    scraper = DerStandardScraper()
    listings = scraper.scrape_search_results(max_listings=max_listings)
    return listings

def save_listings_to_mongodb(listings):
    """Save listings to MongoDB"""
    return MongoDBHandler.save_listings_to_mongodb(listings)

def normalize_listing_schema(listing_data):
    """Normalize listing data to ensure consistent schema"""
    return StructuredAnalyzer.normalize_listing_schema(listing_data)

def send_telegram_notification(listing_data, bot_token=None, chat_id=None):
    """Send listing notification to Telegram"""
    if bot_token and chat_id:
        bot = TelegramBot(bot_token=bot_token, chat_id=chat_id)
        return bot.send_property_notification(listing_data)
    return False

if __name__ == "__main__":
    # Main execution logic
    print("🏠 Starting Immo Scouter...")
    
    # Scrape from all sources
    all_listings = []
    
    try:
        print("🔍 Scraping Willhaben...")
        willhaben_listings = scrape_willhaben(max_listings=5)
        all_listings.extend(willhaben_listings)
        print(f"✅ Found {len(willhaben_listings)} Willhaben listings")
    except Exception as e:
        print(f"❌ Error scraping Willhaben: {e}")
    
    try:
        print("🔍 Scraping Immo Kurier...")
        immo_kurier_listings = scrape_immo_kurier(max_listings=5)
        all_listings.extend(immo_kurier_listings)
        print(f"✅ Found {len(immo_kurier_listings)} Immo Kurier listings")
    except Exception as e:
        print(f"❌ Error scraping Immo Kurier: {e}")
    
    try:
        print("🔍 Scraping derStandard...")
        derstandard_listings = scrape_derstandard(max_listings=5)
        all_listings.extend(derstandard_listings)
        print(f"✅ Found {len(derstandard_listings)} derStandard listings")
    except Exception as e:
        print(f"❌ Error scraping derStandard: {e}")
    
    # Save to MongoDB
    if all_listings:
        print(f"💾 Saving {len(all_listings)} listings to MongoDB...")
        saved_count = save_listings_to_mongodb(all_listings)
        print(f"✅ Saved {saved_count} listings to MongoDB")
    else:
        print("⚠️ No listings found to save") 