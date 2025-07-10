import json
import os
import time
from scrape import WillhabenScraper
from ollama_analyzer import StructuredAnalyzer
from mongodb_handler import MongoDBHandler
from telegram_bot import TelegramBot
from helpers import format_currency, format_walking_time, ViennaDistrictHelper, load_config
import logging
import pymongo # for bson

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('immo-scouter.log'),
        logging.StreamHandler()
    ]
)

def json_serializable(obj):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    try:
        if isinstance(obj, pymongo.mongo_client.ObjectId):
            return str(obj)
    except ImportError:
        pass  # bson not available, skip ObjectId conversion
    
    if isinstance(obj, dict):
        return {key: json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(item) for item in obj]
    else:
        return obj

def test_system_components(config):
    """Test all system components before running main job"""
    logging.info("🧪 Testing system components...")
    
    # Test MongoDB connection
    try:
        mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
        test_doc = {"test": "connection", "timestamp": time.time()}
        mongo.collection.insert_one(test_doc)
        found = mongo.collection.find_one({"test": "connection"})
        mongo.collection.delete_one({"test": "connection"})
        if found:
            logging.info("✅ MongoDB connection successful!")
            mongo_ok = True
        else:
            logging.error("❌ MongoDB test document not found!")
            mongo_ok = False
    except Exception as e:
        logging.error(f"❌ MongoDB connection failed: {e}")
        mongo_ok = False
    
    # Test Structured Analyzer
    try:
        analyzer = StructuredAnalyzer(
            api_key=config.get('openai_api_key'),
            model=config.get('openai_model', 'gpt-4o-mini')
        )
        analyzer_ok = analyzer.is_available()
        if analyzer_ok:
            logging.info("✅ Structured Analyzer available!")
        else:
            logging.warning("⚠️  Structured Analyzer not available - will use fallback")
    except Exception as e:
        logging.error(f"❌ Structured Analyzer error: {e}")
        analyzer_ok = False
    
    # Test Telegram Bot
    telegram_ok = False
    if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
        try:
            bot = TelegramBot(config['telegram_bot_token'], config['telegram_chat_id'])
            telegram_ok = bot.test_connection()
            if telegram_ok:
                logging.info("✅ Telegram bot connection successful!")
            else:
                logging.warning("⚠️  Telegram bot connection failed")
        except Exception as e:
            logging.error(f"❌ Telegram bot error: {e}")
    else:
        logging.warning("⚠️  Telegram bot not configured")
    
    return {
        'mongodb': mongo_ok,
        'analyzer': analyzer_ok,
        'telegram': telegram_ok
    }

def print_listing_summary(listing):
    """Print a formatted summary of a listing"""
    district = listing.get('bezirk', 'Unknown')
    district_name = ViennaDistrictHelper.get_district_name(district)
    price = format_currency(listing.get('price_total'))
    area = listing.get('area_m2', 'N/A')
    price_per_m2 = format_currency(listing.get('price_per_m2'))
    ubahn_time = format_walking_time(listing.get('ubahn_walk_minutes', 0) * 80) if listing.get('ubahn_walk_minutes') else 'N/A'
    school_time = format_walking_time(listing.get('school_walk_minutes', 0) * 80) if listing.get('school_walk_minutes') else 'N/A'
    year_built = listing.get('year_built', 'N/A')
    condition = listing.get('condition', 'N/A')
    energy_class = listing.get('energy_class', 'N/A')
    
    print(f"\n🏠 {district} ({district_name}) - {price}")
    print(f"   📍 {listing.get('address', 'N/A')}")
    print(f"   📐 {area}m² - {price_per_m2}/m²")
    print(f"   🚇 U-Bahn: {ubahn_time}")
    print(f"   🏫 School: {school_time}")
    print(f"   🏗️  Built: {year_built}")
    print(f"   🛠️  Condition: {condition}")
    print(f"   ⚡ Energy: {energy_class}")
    print(f"   🔗 {listing['url']}")

def main():
    """Main function to run the property scraper"""
    logging.info("🚀 Starting Immo-Scouter Main Job")
    logging.info("=" * 60)
    
    # Load configuration
    config = load_config()
    if not config:
        logging.error("❌ Cannot proceed without configuration")
        return
    
    # Test system components
    component_status = test_system_components(config)
    
    # Check if critical components are working
    if not component_status['mongodb']:
        logging.error("❌ MongoDB is required but not working. Please fix the connection.")
        return
    
    # Alert URL from config or default
    alert_url = config.get('alert_url', "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
    
    # Create scraper instance with config
    try:
        scraper = WillhabenScraper(config=config)
        logging.info("✅ Scraper initialized successfully")
    except Exception as e:
        logging.error(f"❌ Failed to initialize scraper: {e}")
        return
    
    # Display criteria being used
    criteria = scraper.criteria
    logging.info(f"📋 Using {len(criteria)} criteria:")
    for key, value in criteria.items():
        logging.info(f"   {key}: {value}")
    
    # Scrape the search results
    max_pages = config.get('max_pages', 5)
    logging.info(f"🔍 Starting comprehensive search (up to {max_pages} pages)...")
    
    try:
        matching_listings = scraper.scrape_search_agent_page(alert_url, max_pages=max_pages)
        
        if matching_listings:
            # Save results to file
            serializable_listings = json_serializable(matching_listings)
            
            output_file = f"filtered_listings_{int(time.time())}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_listings, f, indent=2, ensure_ascii=False)
            
            logging.info(f"\n🎉 Found {len(matching_listings)} listings that meet your criteria!")
            logging.info(f"💾 Results saved to: {output_file}")
            
            # Print detailed summary
            logging.info("\n📋 MATCHING LISTINGS SUMMARY:")
            logging.info("=" * 60)
            
            for i, listing in enumerate(matching_listings, 1):
                logging.info(f"\n[{i}/{len(matching_listings)}]")
                print_listing_summary(listing)
            
            # Statistics
            total_price = sum(listing.get('price_total', 0) for listing in matching_listings)
            avg_price = total_price / len(matching_listings) if matching_listings else 0
            total_area = sum(listing.get('area_m2', 0) for listing in matching_listings)
            avg_area = total_area / len(matching_listings) if matching_listings else 0
            avg_price_per_m2 = sum(listing.get('price_per_m2', 0) for listing in matching_listings) / len(matching_listings) if matching_listings else 0
            
            logging.info(f"\n📊 STATISTICS:")
            logging.info("=" * 60)
            logging.info(f"   Total listings found: {len(matching_listings)}")
            logging.info(f"   Average price: {format_currency(avg_price)}")
            logging.info(f"   Average area: {avg_area:.1f}m²")
            logging.info(f"   Average price/m²: {format_currency(avg_price_per_m2)}")
            
            # Telegram notification summary
            if component_status['telegram'] and scraper.telegram_bot:
                try:
                    summary_message = f"""🎉 <b>Immo-Scouter Summary</b>

📋 Found <b>{len(matching_listings)}</b> matching properties
💰 Average price: {format_currency(avg_price)}
📐 Average area: {avg_area:.1f}m²
💸 Average price/m²: {format_currency(avg_price_per_m2)}

🔗 Check your notifications above for details!"""
                    
                    scraper.telegram_bot.send_message(summary_message)
                    logging.info("📱 Summary sent to Telegram")
                except Exception as e:
                    logging.error(f"❌ Failed to send Telegram summary: {e}")
        
        else:
            logging.info("❌ No listings found matching your criteria.")
            logging.info("💡 Consider adjusting your criteria in config.json")
            
            # Send "no results" notification
            if component_status['telegram'] and scraper.telegram_bot:
                try:
                    no_results_message = """🤷‍♂️ <b>Immo-Scouter Update</b>

No new properties found matching your criteria.

💡 Consider adjusting your search criteria if this continues."""
                    scraper.telegram_bot.send_message(no_results_message)
                except Exception as e:
                    logging.error(f"❌ Failed to send Telegram notification: {e}")
    
    except Exception as e:
        logging.error(f"❌ Error during scraping: {e}")
        
        # Send error notification
        if component_status['telegram'] and scraper.telegram_bot:
            try:
                error_message = f"""⚠️ <b>Immo-Scouter Error</b>

An error occurred during the search:
{str(e)[:200]}...

Please check the logs for more details."""
                scraper.telegram_bot.send_message(error_message)
            except Exception as telegram_error:
                logging.error(f"❌ Failed to send error notification: {telegram_error}")
    
    logging.info("\n✅ Immo-Scouter Main Job Completed")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()