import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Set, List, Dict
from scrape import WillhabenScraper
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('immo-scouter/monitor.log'),
        logging.StreamHandler()
    ]
)

def load_config():
    config_paths = ['config.json', 'immo-scouter/config.default.json']
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logging.info(f"Loaded config from {config_path}")
                return config
            except Exception as e:
                logging.error(f"Error loading {config_path}: {e}")
                continue
    
    logging.error("No config file found!")
    return {}

class RealTimeMonitor:
    def __init__(self, alert_url: str, check_interval_minutes: int = 5):
        self.alert_url = alert_url
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        
        # Load configuration
        config = load_config()
        
        # Create scraper with Telegram support
        self.scraper = WillhabenScraper(
            telegram_config={
                'enabled': True,
                'bot_token': config.get('telegram_bot_token'),
                'chat_id': config.get('telegram_chat_id')
            },
            mongo_uri=config.get('mongodb_uri')
        )
        self.seen_listings: Set[str] = set()
        self.load_seen_listings()
        
        # Email configuration (optional)
        self.email_config = {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email': 'your-email@gmail.com',
            'password': 'your-app-password',
            'to_email': 'your-email@gmail.com'
        }
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'total_listings_found': 0,
            'matching_listings': 0,
            'last_check': None,
            'start_time': datetime.now()
        }

    def load_seen_listings(self):
        """Load previously seen listings from file"""
        try:
            if os.path.exists('seen_listings.json'):
                with open('seen_listings.json', 'r') as f:
                    data = json.load(f)
                    self.seen_listings = set(data.get('seen_listings', []))
                    logging.info(f"Loaded {len(self.seen_listings)} previously seen listings")
        except Exception as e:
            logging.error(f"Error loading seen listings: {e}")

    def save_seen_listings(self):
        """Save seen listings to file"""
        try:
            with open('seen_listings.json', 'w') as f:
                json.dump({
                    'seen_listings': list(self.seen_listings),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving seen listings: {e}")

    def send_email_notification(self, listing: Dict):
        """Send email notification for new matching listing"""
        if not self.email_config['enabled']:
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['email']
            msg['To'] = self.email_config['to_email']
            msg['Subject'] = f"🏠 New Property Match Found! - {listing.get('bezirk', 'Unknown')}"
            
            body = f"""
            🎉 NEW PROPERTY MATCH FOUND!
            
            📍 Location: {listing.get('bezirk', 'N/A')} - {listing.get('address', 'N/A')}
            💰 Price: €{listing.get('price_total', 'N/A'):,}
            📐 Area: {listing.get('area_m2', 'N/A')}m²
            💸 Price per m²: €{listing.get('price_per_m2', 'N/A'):,}
            🚇 U-Bahn: {listing.get('ubahn_walk_minutes', 'N/A')} min walk
            🏠 Rooms: {listing.get('rooms', 'N/A')}
            🏗️ Year Built: {listing.get('year_built', 'N/A')}
            💳 Monthly Rate: €{listing.get('monatsrate', 'N/A'):,}
            
            🔗 View Listing: {listing.get('url', 'N/A')}
            
            ⏰ Found at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email'], self.email_config['password'])
            server.send_message(msg)
            server.quit()
            
            logging.info(f"Email notification sent for listing: {listing.get('url')}")
            
        except Exception as e:
            logging.error(f"Error sending email notification: {e}")

    def send_desktop_notification(self, listing: Dict):
        """Send desktop notification (macOS)"""
        try:
            title = f"🏠 New Property Match - {listing.get('bezirk', 'Unknown')}"
            message = f"€{listing.get('price_total', 'N/A'):,} - {listing.get('area_m2', 'N/A')}m² - {listing.get('ubahn_walk_minutes', 'N/A')}min to U-Bahn"
            
            os.system(f"""
                osascript -e 'display notification "{message}" with title "{title}"'
            """)
            
            logging.info(f"Desktop notification sent for listing: {listing.get('url')}")
            
        except Exception as e:
            logging.error(f"Error sending desktop notification: {e}")

    def check_for_new_listings(self) -> List[Dict]:
        """Check for new listings and return matching ones"""
        try:
            logging.info(f"🔍 Checking for new listings... (Check #{self.stats['total_checks'] + 1})")
            
            # Get only new listings that haven't been processed yet
            # The scraper will handle MongoDB deduplication and only return truly new ones
            all_listings = self.scraper.scrape_search_agent_page(self.alert_url)
            
            if not all_listings:
                logging.info("No new matching listings found")
                return []
            
            logging.info(f"Found {len(all_listings)} new matching listings")
            
            # All listings returned are already new and matching criteria
            new_matching_listings = all_listings
            
            for listing in new_matching_listings:
                listing_url = listing.get('url', '')
                self.stats['matching_listings'] += 1
                
                logging.info(f"✅ NEW MATCHING LISTING FOUND!")
                logging.info(f"   URL: {listing_url}")
                logging.info(f"   Price: €{listing.get('price_total', 'N/A'):,}")
                logging.info(f"   Area: {listing.get('area_m2', 'N/A')}m²")
                logging.info(f"   U-Bahn: {listing.get('ubahn_walk_minutes', 'N/A')} min")
                
                # Send notifications (Telegram already sent by scraper)
                self.send_desktop_notification(listing)
                self.send_email_notification(listing)
                
                # Save to special file for matches
                self.save_matching_listing(listing)
            
            self.stats['total_checks'] += 1
            self.stats['last_check'] = datetime.now()
            
            return new_matching_listings
            
        except Exception as e:
            logging.error(f"Error checking for new listings: {e}")
            return []

    def save_matching_listing(self, listing: Dict):
        """Save matching listing to a special file"""
        try:
            filename = f"immo-scouter/matches_{datetime.now().strftime('%Y%m%d')}.json"
            
            # Load existing matches
            existing_matches = []
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    existing_matches = json.load(f)
            
            # Add new match with timestamp
            listing_with_timestamp = {
                **listing,
                'found_at': datetime.now().isoformat(),
                'check_number': self.stats['total_checks']
            }
            existing_matches.append(listing_with_timestamp)
            
            # Save back to file
            with open(filename, 'w') as f:
                json.dump(existing_matches, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved matching listing to {filename}")
            
        except Exception as e:
            logging.error(f"Error saving matching listing: {e}")

    def print_stats(self):
        """Print monitoring statistics"""
        runtime = datetime.now() - self.stats['start_time']
        hours = runtime.total_seconds() / 3600
        
        print(f"\n{'='*60}")
        print(f"📊 MONITORING STATISTICS")
        print(f"{'='*60}")
        print(f"⏱️  Runtime: {hours:.1f} hours")
        print(f"🔍 Total Checks: {self.stats['total_checks']}")
        print(f"📋 Total Listings Found: {self.stats['total_listings_found']}")
        print(f"✅ Matching Listings: {self.stats['matching_listings']}")
        print(f"🕐 Last Check: {self.stats['last_check']}")
        print(f"📝 Seen Listings: {len(self.seen_listings)}")
        print(f"{'='*60}\n")

    def run(self):
        """Run the monitoring loop"""
        logging.info("🚀 Starting real-time property monitor...")
        logging.info(f"📅 Started at: {datetime.now()}")
        logging.info(f"⏰ Check interval: {self.check_interval/60} minutes")
        logging.info(f"🔗 Monitoring URL: {self.alert_url}")
        
        try:
            while True:
                # Check for new listings
                new_matches = self.check_for_new_listings()
                
                if new_matches:
                    logging.info(f"🎉 Found {len(new_matches)} new matching listings!")
                else:
                    logging.info("No new matching listings found")
                
                # Print stats every 10 checks
                if self.stats['total_checks'] % 10 == 0:
                    self.print_stats()
                
                # Wait before next check
                logging.info(f"⏳ Waiting {self.check_interval/60} minutes before next check...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logging.info("🛑 Monitoring stopped by user")
            self.save_seen_listings()
            self.print_stats()
        except Exception as e:
            logging.error(f"❌ Fatal error in monitoring: {e}")
            self.save_seen_listings()

def main():
    """Main function to run the monitor"""
    alert_url = "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387"
    
    # Create and run monitor
    monitor = RealTimeMonitor(alert_url, check_interval_minutes=5)
    monitor.run()

if __name__ == "__main__":
    main() 