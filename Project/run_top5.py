#!/usr/bin/env python3
"""
Script to fetch top 5 listings from MongoDB and send to Telegram main channel
"""

import sys
import os
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Application.helpers.utils import load_config
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('log/top5.log')
        ]
    )

def main():
    """Main function to fetch top 5 listings and send to Telegram"""
    setup_logging()
    
    print("🏆 Starting Top 5 Properties Report")
    print("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        if not config:
            logging.error("❌ Failed to load configuration")
            return False
        
        # Initialize MongoDB handler
        mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
        mongo = MongoDBHandler(uri=mongo_uri)
        
        if not mongo.client:
            logging.error("❌ Failed to connect to MongoDB")
            return False
        
        # Initialize Telegram bot
        telegram_config = config.get('telegram', {})
        telegram_main = telegram_config.get('telegram_main', {})
        
        if not telegram_main.get('bot_token') or not telegram_main.get('chat_id'):
            logging.error("❌ Telegram configuration not found")
            return False
        
        telegram_bot = TelegramBot(
            telegram_main['bot_token'],
            telegram_main['chat_id']
        )
        
        # Test Telegram connection
        if not telegram_bot.test_connection():
            logging.error("❌ Failed to connect to Telegram")
            return False
        
        # Get parameters from config or use defaults
        limit = config.get('top5', {}).get('limit', 5)
        min_score = config.get('top5', {}).get('min_score', 40.0)
        days_old = config.get('top5', {}).get('days_old', 7)
        
        print(f"📊 Fetching top {limit} listings...")
        print(f"🎯 Minimum score: {min_score}")
        print(f"📅 Last {days_old} days")
        
        # Fetch top listings from MongoDB
        listings = mongo.get_top_listings(
            limit=limit,
            min_score=min_score,
            days_old=days_old
        )
        
        if not listings:
            logging.warning("⚠️ No listings found matching criteria")
            
            # Send a message indicating no listings found
            no_listings_msg = f"📊 **Top Properties Report**\n\n"
            no_listings_msg += f"❌ No properties found matching criteria:\n"
            no_listings_msg += f"• Minimum score: {min_score}\n"
            no_listings_msg += f"• Last {days_old} days\n\n"
            no_listings_msg += f"📅 Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            telegram_bot.send_message(no_listings_msg)
            return True
        
        # Create title for the report
        title = f"🏆 Top {len(listings)} Properties Report"
        
        # Send to Telegram
        success = telegram_bot.send_top_listings(
            listings=listings,
            title=title,
            max_listings=limit
        )
        
        if success:
            print(f"✅ Successfully sent top {len(listings)} listings to Telegram")
            
            # Print summary
            print("\n📊 Summary:")
            for i, listing in enumerate(listings, 1):
                score = listing.get('score', 0)
                price = listing.get('price_total', 0)
                area = listing.get('area_m2', 0)
                rooms = listing.get('rooms', 0)
                bezirk = listing.get('bezirk', 'N/A')
                source = listing.get('source', 'Unknown')
                
                print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk} | {source}")
            
            return True
        else:
            logging.error("❌ Failed to send listings to Telegram")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error in main function: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 