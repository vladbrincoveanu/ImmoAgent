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

def is_valid_listing(listing):
    """
    Validate if a listing has realistic prices and data
    
    Args:
        listing: Listing dictionary
        
    Returns:
        bool: True if listing is valid, False if garbage
    """
    try:
        price_total = listing.get('price_total', 0)
        area_m2 = listing.get('area_m2', 0)
        
        # Skip if missing essential data
        if not price_total or not area_m2:
            return False
        
        # Calculate price per m²
        price_per_m2 = price_total / area_m2
        
        # Vienna price validation rules
        # Minimum realistic price per m² in Vienna (even for very cheap areas)
        min_price_per_m2 = 1000  # €1,000/m² minimum
        
        # Maximum realistic price per m² in Vienna (even for luxury areas)
        max_price_per_m2 = 25000  # €25,000/m² maximum
        
        # Check if price per m² is realistic
        if price_per_m2 < min_price_per_m2:
            print(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (too cheap)")
            return False
        
        if price_per_m2 > max_price_per_m2:
            print(f"🚫 Filtered out garbage: €{price_total:,} for {area_m2}m² = €{price_per_m2:.0f}/m² (too expensive)")
            return False
        
        # Additional checks for obviously wrong data
        if price_total < 50000:  # Less than €50k total price is suspicious
            print(f"🚫 Filtered out garbage: €{price_total:,} total price (too low)")
            return False
        
        if area_m2 < 20:  # Less than 20m² is suspicious
            print(f"🚫 Filtered out garbage: {area_m2}m² area (too small)")
            return False
        
        # Check monthly payment filter (below €2,000)
        monthly_payment = listing.get('monthly_payment', {})
        if monthly_payment and isinstance(monthly_payment, dict):
            total_monthly = monthly_payment.get('total_monthly', 0)
            if total_monthly > 2000:  # More than €2,000 monthly payment
                print(f"🚫 Filtered out expensive: €{total_monthly:,.0f} monthly payment (above €2,000)")
                return False
        
        return True
        
    except Exception as e:
        print(f"🚫 Error validating listing: {e}")
        return False

def setup_logging():
    """Setup logging configuration"""
    # Ensure log directory exists
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

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
    
    # Parse buyer profile from command line arguments
    buyer_profile = "diy_renovator"  # Default to DIY Renovator profile
    for i, arg in enumerate(sys.argv):
        if arg == "--buyer-profile" and i + 1 < len(sys.argv):
            buyer_profile = sys.argv[i + 1]
        elif arg.startswith("--buyer-profile="):
            buyer_profile = arg.split("=", 1)[1]
    
    # Set the buyer profile for scoring
    from Application.scoring import set_buyer_profile
    set_buyer_profile(buyer_profile)
    
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
            logging.info("ℹ️ This is expected in GitHub Actions environment without MongoDB")
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
            logging.info("ℹ️ This is expected if Telegram bot token is not configured or invalid")
            return False
        
        # Get parameters from config or use defaults
        limit = config.get('top5', {}).get('limit', 5)
        min_score = config.get('top5', {}).get('min_score', 40.0)
        days_old = config.get('top5', {}).get('days_old', 7)
        excluded_districts = config.get('top5', {}).get('excluded_districts', [])
        min_rooms = config.get('top5', {}).get('min_rooms', 0)
        include_monthly_payment = config.get('top5', {}).get('include_monthly_payment', True)
        
        print(f"📊 Fetching top {limit} listings...")
        print(f"🎯 Minimum score: {min_score}")
        print(f"📅 Last {days_old} days")
        if excluded_districts:
            print(f"🚫 Excluded districts: {excluded_districts}")
        if min_rooms > 0:
            print(f"🛏️ Minimum rooms: {min_rooms}")
        if include_monthly_payment:
            print(f"💰 Including monthly payment calculations")
        
        # Fetch top listings from MongoDB
        # Note: If days_old is set but no created_at field exists, we'll skip the date filter
        listings = mongo.get_top_listings(
            limit=limit * 3,  # Get more listings to filter out garbage
            min_score=min_score,
            days_old=days_old,
            excluded_districts=excluded_districts,
            min_rooms=min_rooms
        )
        
        # Filter out garbage listings with unrealistic prices
        valid_listings = []
        for listing in listings:
            if is_valid_listing(listing):
                valid_listings.append(listing)
                if len(valid_listings) >= limit:
                    break
        
        listings = valid_listings[:limit]
        
        if not listings:
            logging.warning("⚠️ No listings found matching criteria")
            
            # Send a message indicating no listings found
            no_listings_msg = f"📊 **Top Properties Report**\n\n"
            no_listings_msg += f"❌ No properties found matching criteria:\n"
            no_listings_msg += f"• Minimum score: {min_score}\n"
            no_listings_msg += f"• Last {days_old} days\n"
            if excluded_districts:
                no_listings_msg += f"• Excluded districts: {excluded_districts}\n"
            if min_rooms > 0:
                no_listings_msg += f"• Minimum rooms: {min_rooms}\n"
            if not include_monthly_payment:
                no_listings_msg += f"• Monthly payment not included\n"
            no_listings_msg += f"\n📅 Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
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