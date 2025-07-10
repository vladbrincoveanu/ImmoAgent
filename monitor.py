#!/usr/bin/env python3
"""
Vienna Real Estate Monitor - Continuous monitoring service
Monitors Willhaben for new listings and sends notifications
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from scrape import WillhabenScraper
from mongodb_handler import MongoDBHandler
from telegram_bot import TelegramBot
from helpers import format_currency, format_walking_time, ViennaDistrictHelper, load_config
import hashlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

class PropertyMonitor:
    """Main monitoring class for Vienna real estate"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.mongo = MongoDBHandler(uri=config.get('mongodb_uri', ''))
        self.scraper = WillhabenScraper(config=config)
        self.telegram_bot = self.scraper.telegram_bot
        
        # Monitoring settings
        self.check_interval = config.get('monitor_interval_minutes', 15) * 60  # seconds
        self.max_pages = config.get('max_pages', 3)
        self.alert_url = config.get('alert_url', 
            "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
        
        # Track seen listings to avoid duplicates
        self.seen_listings: Set[str] = set()
        self.load_seen_listings()
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'new_listings_found': 0,
            'notifications_sent': 0,
            'errors': 0,
            'last_check': None,
            'last_new_listing': None
        }
        
        logging.info("🔍 Property Monitor initialized")
        logging.info(f"   Check interval: {self.check_interval//60} minutes")
        logging.info(f"   Max pages per check: {self.max_pages}")
        logging.info(f"   Alert URL: {self.alert_url}")
    
    def load_seen_listings(self):
        """Load previously seen listings from MongoDB"""
        try:
            # Load from MongoDB recent listings (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_listings = self.mongo.collection.find({
                'timestamp': {'$gte': thirty_days_ago}
            })
            
            for listing in recent_listings:
                listing_id = self.get_listing_id(listing)
                self.seen_listings.add(listing_id)
            
            logging.info(f"📋 Loaded {len(self.seen_listings)} seen listings from database")
            
        except Exception as e:
            logging.error(f"❌ Error loading seen listings: {e}")
    
    def get_listing_id(self, listing: Dict) -> str:
        """Generate unique ID for a listing"""
        # Use URL as primary identifier, fallback to hash of key properties
        if 'url' in listing:
            return listing['url']
        
        # Fallback: hash of key properties
        key_data = f"{listing.get('bezirk', '')}-{listing.get('price_total', 0)}-{listing.get('area_m2', 0)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def is_new_listing(self, listing: Dict) -> bool:
        """Check if listing is new (not seen before)"""
        listing_id = self.get_listing_id(listing)
        return listing_id not in self.seen_listings
    
    def mark_as_seen(self, listing: Dict):
        """Mark listing as seen"""
        listing_id = self.get_listing_id(listing)
        self.seen_listings.add(listing_id)
    
    def format_listing_notification(self, listing: Dict) -> str:
        """Format listing for Telegram notification"""
        district = listing.get('bezirk', 'Wien')
        district_name = ViennaDistrictHelper.get_district_name(district)
        price = format_currency(listing.get('price_total'))
        area = listing.get('area_m2', 'N/A')
        price_per_m2 = format_currency(listing.get('price_per_m2'))
        ubahn_time = listing.get('ubahn_walk_minutes', 0)
        school_time = listing.get('school_walk_minutes', 0)
        year_built = listing.get('year_built', 'N/A')
        condition = listing.get('condition', 'N/A')
        energy_class = listing.get('energy_class', 'N/A')
        address = listing.get('address', 'N/A')
        
        message = f"""🏠 <b>Neue Immobilie!</b>

📍 {district} ({district_name})
🏡 {address}
💰 {price}
📐 {area}m² - {price_per_m2}/m²
🛏️ {listing.get('rooms', 'N/A')} Zimmer
🚇 U-Bahn: {ubahn_time} min
🏫 Schule: {school_time} min
🏗️ Baujahr: {year_built}
🛠️ Zustand: {condition}
⚡ Energieklasse: {energy_class}

🔗 <a href="{listing.get('url', '#')}">Zur Anzeige</a>"""
        
        return message
    
    def send_notification(self, listing: Dict):
        """Send Telegram notification for new listing"""
        try:
            if not self.telegram_bot:
                logging.warning("⚠️ Telegram bot not configured")
                return False
            
            message = self.format_listing_notification(listing)
            success = self.telegram_bot.send_message(message)
            
            if success:
                self.stats['notifications_sent'] += 1
                logging.info(f"📱 Notification sent for {listing.get('bezirk', 'Unknown')} listing")
                return True
            else:
                logging.error("❌ Failed to send Telegram notification")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error sending notification: {e}")
            return False
    
    def check_for_new_listings(self) -> List[Dict]:
        """Check for new listings and return any found"""
        try:
            logging.info("🔍 Checking for new listings...")
            self.stats['total_checks'] += 1
            self.stats['last_check'] = datetime.utcnow()
            
            # Scrape current listings
            all_listings = self.scraper.scrape_search_agent_page(
                self.alert_url, 
                max_pages=self.max_pages
            )
            
            if not all_listings:
                logging.info("📭 No listings found in current search")
                return []
            
            # Filter for new listings
            new_listings = []
            for listing in all_listings:
                if self.is_new_listing(listing):
                    new_listings.append(listing)
                    self.mark_as_seen(listing)
                    
                    # Save to MongoDB
                    listing['timestamp'] = datetime.utcnow()
                    listing['monitor_found'] = True
                    self.mongo.collection.insert_one(listing)
            
            if new_listings:
                self.stats['new_listings_found'] += len(new_listings)
                self.stats['last_new_listing'] = datetime.utcnow()
                logging.info(f"🎉 Found {len(new_listings)} new listings!")
            else:
                logging.info("📋 No new listings found")
            
            return new_listings
            
        except Exception as e:
            logging.error(f"❌ Error checking for new listings: {e}")
            self.stats['errors'] += 1
            return []
    
    def send_status_update(self):
        """Send periodic status update via Telegram"""
        try:
            if not self.telegram_bot:
                return
            
            uptime = datetime.utcnow() - self.start_time
            uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            
            message = f"""📊 <b>Monitor Status Update</b>

⏰ Uptime: {uptime_str}
🔍 Total checks: {self.stats['total_checks']}
🎉 New listings found: {self.stats['new_listings_found']}
📱 Notifications sent: {self.stats['notifications_sent']}
❌ Errors: {self.stats['errors']}
🕐 Last check: {self.stats['last_check'].strftime('%H:%M:%S') if self.stats['last_check'] else 'Never'}
🏠 Last new listing: {self.stats['last_new_listing'].strftime('%H:%M:%S') if self.stats['last_new_listing'] else 'None'}

✅ Monitor running normally"""
            
            self.telegram_bot.send_message(message)
            logging.info("📊 Status update sent")
            
        except Exception as e:
            logging.error(f"❌ Error sending status update: {e}")
    
    def run(self):
        """Main monitoring loop"""
        logging.info("🚀 Starting Property Monitor")
        logging.info("=" * 60)
        
        self.start_time = datetime.utcnow()
        last_status_update = datetime.utcnow()
        status_interval = timedelta(hours=6)  # Send status every 6 hours
        
        # Send startup notification
        if self.telegram_bot:
            try:
                startup_message = f"""🚀 <b>Property Monitor Started</b>

🔍 Monitoring every {self.check_interval//60} minutes
📋 Max {self.max_pages} pages per check
🎯 {len(self.scraper.criteria)} criteria active

Monitor is now running..."""
                self.telegram_bot.send_message(startup_message)
            except Exception as e:
                logging.error(f"❌ Failed to send startup notification: {e}")
        
        try:
            while True:
                # Check for new listings
                new_listings = self.check_for_new_listings()
                
                # Send notifications for new listings
                for listing in new_listings:
                    self.send_notification(listing)
                    time.sleep(2)  # Rate limit notifications
                
                # Send periodic status updates
                now = datetime.utcnow()
                if now - last_status_update > status_interval:
                    self.send_status_update()
                    last_status_update = now
                
                # Wait for next check
                logging.info(f"😴 Sleeping for {self.check_interval//60} minutes...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logging.info("⏹️ Monitor stopped by user")
            
            # Send shutdown notification
            if self.telegram_bot:
                try:
                    shutdown_message = f"""⏹️ <b>Property Monitor Stopped</b>

📊 Final Statistics:
🔍 Total checks: {self.stats['total_checks']}
🎉 New listings found: {self.stats['new_listings_found']}
📱 Notifications sent: {self.stats['notifications_sent']}
❌ Errors: {self.stats['errors']}

Monitor has been stopped."""
                    self.telegram_bot.send_message(shutdown_message)
                except Exception as e:
                    logging.error(f"❌ Failed to send shutdown notification: {e}")
                    
        except Exception as e:
            logging.error(f"❌ Critical error in monitor: {e}")
            
            # Send error notification
            if self.telegram_bot:
                try:
                    error_message = f"""⚠️ <b>Monitor Error</b>

Critical error occurred:
{str(e)[:200]}...

Monitor has stopped. Please check logs."""
                    self.telegram_bot.send_message(error_message)
                except Exception as telegram_error:
                    logging.error(f"❌ Failed to send error notification: {telegram_error}")

def test_system_components(config):
    """Test all system components before starting monitor"""
    logging.info("🧪 Testing system components...")
    
    # Test MongoDB connection
    try:
        mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
        test_doc = {"test": "connection", "timestamp": datetime.utcnow()}
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
    
    # Test Telegram Bot
    telegram_ok = False
    if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
        try:
            bot = TelegramBot(config['telegram_bot_token'], config['telegram_chat_id'])
            telegram_ok = bot.test_connection()
            if telegram_ok:
                logging.info("✅ Telegram bot connection successful!")
            else:
                logging.warning("⚠️ Telegram bot connection failed")
        except Exception as e:
            logging.error(f"❌ Telegram bot error: {e}")
    else:
        logging.warning("⚠️ Telegram bot not configured")
    
    # Test Scraper
    scraper_ok = False
    try:
        scraper = WillhabenScraper(config=config)
        scraper_ok = True
        logging.info("✅ Scraper initialized successfully!")
    except Exception as e:
        logging.error(f"❌ Scraper initialization failed: {e}")
    
    return {
        'mongodb': mongo_ok,
        'telegram': telegram_ok,
        'scraper': scraper_ok
    }

def main():
    """Main function to run the property monitor"""
    logging.info("🔍 Vienna Real Estate Monitor")
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
    
    if not component_status['scraper']:
        logging.error("❌ Scraper is required but not working. Please fix the configuration.")
        return
    
    if not component_status['telegram']:
        logging.warning("⚠️ Telegram notifications will not be available")
    
    # Display configuration
    logging.info(f"📋 Configuration:")
    logging.info(f"   Monitor interval: {config.get('monitor_interval_minutes', 15)} minutes")
    logging.info(f"   Max pages per check: {config.get('max_pages', 3)}")
    logging.info(f"   Telegram enabled: {component_status['telegram']}")
    
    # Start monitor
    try:
        monitor = PropertyMonitor(config)
        monitor.run()
    except Exception as e:
        logging.error(f"❌ Failed to start monitor: {e}")

if __name__ == "__main__":
    main() 