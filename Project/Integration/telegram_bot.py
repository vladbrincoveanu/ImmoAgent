import requests
import json
from typing import Dict, List
import logging
from Application.helpers.utils import load_config
from Application.scoring import score_apartment_simple
import time

def clean_utf8_text(text: str) -> str:
    """Clean text to ensure UTF-8 compatibility and proper formatting"""
    if not text:
        return ""
    
    # Convert to string if needed
    text = str(text)
    
    # Remove or replace problematic characters
    text = text.replace('\x00', '')  # Remove null bytes
    text = text.replace('\r\n', '\n')  # Normalize line endings
    text = text.replace('\r', '\n')  # Normalize line endings
    
    # Remove excessive whitespace while preserving intentional formatting
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Strip leading/trailing whitespace from each line
        cleaned_line = line.strip()
        # Remove excessive internal whitespace (keep single spaces)
        cleaned_line = ' '.join(cleaned_line.split())
        if cleaned_line:  # Only add non-empty lines
            cleaned_lines.append(cleaned_line)
    
    # Join lines with single newlines, preserving the line structure
    result = '\n'.join(cleaned_lines)
    
    # Final cleanup: fix punctuation spacing but preserve line breaks
    result = result.replace(' .', '.').replace(' ,', ',').replace(' !', '!').replace(' ?', '?')
    
    return result

class TelegramLogHandler(logging.Handler):
    """Custom logging handler that sends logs to Telegram"""
    
    def __init__(self, telegram_bot, level=logging.INFO, is_dev_channel=False):
        super().__init__(level)
        self.telegram_bot = telegram_bot
        self.is_dev_channel = is_dev_channel
        # Prevent using main bot for dev logging
        if self.is_dev_channel:
            # Try to detect if this is the main channel
            main_config = None
            try:
                from Application.main import load_config
                main_config = load_config()
            except Exception:
                pass
            if main_config:
                telegram_config = main_config.get('telegram', {})
                main_bot_config = telegram_config.get('telegram_main', {})
                main_token = main_bot_config.get('bot_token')
                main_chat_id = main_bot_config.get('chat_id')
                if self.telegram_bot.bot_token == main_token and self.telegram_bot.chat_id == main_chat_id:
                    raise RuntimeError("[SECURITY] Refusing to attach dev log handler to main Telegram bot!")
    
    def emit(self, record):
        try:
            # For dev channel, only send ERROR and CRITICAL logs (not INFO/WARNING)
            # For main channel, only send ERROR logs
            if self.is_dev_channel and record.levelno >= logging.ERROR:
                # Format the message based on log level
                if record.levelno >= logging.CRITICAL:
                    prefix = "🚨 <b>Critical Log</b>"
                else:
                    prefix = "⚠️ <b>Error Log</b>"
                # Add dev prefix if dev channel
                prefix = "[DEV LOG] " + prefix
                log_msg = f"{prefix}\n\n{self.format(record)}"
                cleaned_log_msg = clean_utf8_text(log_msg)
                self.telegram_bot.send_message(cleaned_log_msg)
            elif not self.is_dev_channel and record.levelno >= logging.ERROR:
                # Main channel only gets ERROR logs
                prefix = "⚠️ <b>Error Log</b>"
                log_msg = f"{prefix}\n\n{self.format(record)}"
                cleaned_log_msg = clean_utf8_text(log_msg)
                self.telegram_bot.send_message(cleaned_log_msg)
        except Exception as e:
            # Don't log here to avoid infinite recursion
            print(f"Failed to send log to Telegram: {e}")

class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Load config to get score threshold
        config = load_config()
        telegram_config = config.get('telegram', {}) if config else {}
        self.min_score_threshold = telegram_config.get('min_score_threshold', 40)
        self.max_messages_per_run = telegram_config.get('max_messages_per_run', 5)
        
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the Telegram chat"""
        try:
            # Clean the text to ensure UTF-8 compatibility
            cleaned_text = clean_utf8_text(text)
            
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": cleaned_text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                logging.info(f"Telegram message sent successfully")
                return True
            else:
                logging.error(f"Telegram API error: {result.get('description')}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")
            return False
    
    def setup_error_logging(self, logger=None, is_dev_channel=False):
        """Setup logging to Telegram for the specified logger"""
        if logger is None:
            logger = logging.getLogger()
        
        # Create and add the Telegram log handler
        telegram_handler = TelegramLogHandler(self, is_dev_channel=is_dev_channel)
        telegram_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(telegram_handler)
        
        return telegram_handler
    
    def calculate_listing_score(self, listing: Dict) -> float:
        """Calculate the score for a listing"""
        try:
            # Convert Listing object to dict if needed
            if not isinstance(listing, dict):
                listing = listing.__dict__ if hasattr(listing, '__dict__') else dict(listing)
            
            # Calculate score using the scoring system
            score = score_apartment_simple(listing)
            return score
        except Exception as e:
            logging.error(f"Error calculating score for listing: {e}")
            return 0.0
    
    def send_property_notification(self, listing: Dict) -> bool:
        """Send a formatted property notification if score is above threshold"""
        try:
            # Calculate score for the listing
            score = self.calculate_listing_score(listing)
            
            # Check if score meets the minimum threshold
            if score <= self.min_score_threshold:
                title = listing.get('title', 'Unknown')
                logging.info(f"⏭️  Skipping Telegram for '{title}' - Score {score:.1f} below threshold {self.min_score_threshold}")
                return False
            
            logging.info(f"📱 Sending Telegram for '{listing.get('title', 'Unknown')}' - Score {score:.1f} above threshold {self.min_score_threshold}")
            
            # Add score to listing for display
            if isinstance(listing, dict):
                listing['score'] = score
            else:
                # For Listing objects, we'll add it to the dict version
                listing_dict = listing.__dict__ if hasattr(listing, '__dict__') else dict(listing)
                listing_dict['score'] = score
                listing = listing_dict
            
            # Format the message
            message = self._format_property_message(listing)
            
            # Send the message
            success = self.send_message(message)
            
            if success:
                logging.info(f"✅ Sent property notification with score {score}")
            else:
                logging.error(f"❌ Failed to send property notification with score {score}")
            
            return success
            
        except Exception as e:
            logging.error(f"Error formatting property notification: {e}")
            return False
    
    def _format_property_message(self, listing: Dict, include_url: bool = False) -> str:
        """Format property listing as concise HTML message"""
        def safe_format(value, prefix="€"):
            if value is None or value == "N/A":
                return None
            if isinstance(value, (int, float)):
                return f"{prefix}{value:,.0f}"
            return str(value)

        def safe_minutes(value):
            if value is None or value == "N/A":
                return None
            return f"{value} min"

        def safe_text(value):
            if value is None or value == "N/A" or value == "None":
                return None
            # Clean and strip whitespace
            cleaned = clean_utf8_text(str(value))
            # Remove excessive whitespace and normalize
            cleaned = ' '.join(cleaned.split())
            return cleaned.strip()

        # Ensure listing is a dict and handle None values
        if listing is None:
            return "⚠️ Error: No listing data available"
        
        if not isinstance(listing, dict):
            # Convert Listing object to dict if needed
            try:
                listing = listing.__dict__ if hasattr(listing, '__dict__') else dict(listing)
            except:
                return "⚠️ Error: Invalid listing data format"

        # Clean all text fields to prevent UTF-8 encoding issues
        address = safe_text(listing.get('address'))
        price = safe_format(listing.get('price_total'))
        bezirk = safe_text(listing.get('bezirk'))
        monthly_rate = safe_format(listing.get('calculated_monatsrate'))
        betriebskosten = safe_format(listing.get('betriebskosten'))
        betriebskosten_estimated = listing.get('betriebskosten_estimated', False)
        
        # Get initial sum invested (down payment)
        own_funds = listing.get('own_funds')
        initial_sum = safe_format(own_funds) if own_funds else None
        
        # Format mortgage details more cleanly
        mortgage_details = listing.get('mortgage_details', {})
        mortgage_line = ""
        if isinstance(mortgage_details, dict) and mortgage_details:
            loan_amount = mortgage_details.get('loan_amount')
            annual_rate = mortgage_details.get('annual_rate')
            years = mortgage_details.get('years')
            if loan_amount and annual_rate and years:
                mortgage_line = f" (€{loan_amount:,.0f} @ {annual_rate}% for {years}y)"
            
        area = listing.get('area_m2')
        price_per_m2 = safe_format(listing.get('price_per_m2'))
        rooms = listing.get('rooms')
        year_built = listing.get('year_built')
        condition = safe_text(listing.get('condition'))
        energy_class = safe_text(listing.get('energy_class'))
        url = listing.get('url', '')
        score = listing.get('score', None)
        
        # --- Use infrastructure_distances for transport and school proximity, fallback to walk_minutes fields ---
        infra = listing.get('infrastructure_distances', {})
        if infra is None:
            infra = {}
        
        # Transport: U-Bahn, Bahnhof, Bus
        transport_lines = []
        transport_priority = [
            ('U-Bahn', '🚇'),
            ('Bahnhof', '🚉'),
            ('Bus', '🚌'),
            ('Autobahnanschluss', '🛣️'),
        ]
        found_transport = False
        for key, emoji in transport_priority:
            for amenity in infra:
                if key.lower() in amenity.lower():
                    dist = infra[amenity].get('distance_m')
                    if dist is not None:
                        min_str = f"{int(round(dist/80))} min" if dist else None
                        if min_str:
                            # Translate transport names
                            if key == 'U-Bahn':
                                display_name = 'Subway'
                            elif key == 'Bahnhof':
                                display_name = 'Train Station'
                            elif key == 'Bus':
                                display_name = 'Bus'
                            elif key == 'Autobahnanschluss':
                                display_name = 'Highway'
                            else:
                                display_name = key
                            transport_lines.append(f"{emoji} {display_name}: {min_str}")
                            found_transport = True
                            break
            if found_transport:
                break
        if not found_transport:
            # Fallback to ubahn_walk_minutes
            ubahn_min = safe_minutes(listing.get('ubahn_walk_minutes'))
            if ubahn_min:
                transport_lines.append(f"🚇 Subway: {ubahn_min}")

        # School: Schule, Kindergarten, Universität
        school_lines = []
        school_priority = [
            ('Schule', '🏫'),
            ('Kindergarten', '🏫'),
            ('Universität', '🎓'),
            ('Höhere Schule', '🏫'),
        ]
        found_school = False
        for key, emoji in school_priority:
            for amenity in infra:
                if key.lower() in amenity.lower():
                    dist = infra[amenity].get('distance_m')
                    if dist is not None:
                        min_str = f"{int(round(dist/80))} min" if dist else None
                        if min_str:
                            # Translate school names
                            if key == 'Schule':
                                display_name = 'School'
                            elif key == 'Kindergarten':
                                display_name = 'Kindergarten'
                            elif key == 'Universität':
                                display_name = 'University'
                            elif key == 'Höhere Schule':
                                display_name = 'High School'
                            else:
                                display_name = key
                            school_lines.append(f"{emoji} {display_name}: {min_str}")
                            found_school = True
                            break
            if found_school:
                break
        if not found_school:
            school_min = safe_minutes(listing.get('school_walk_minutes'))
            if school_min:
                school_lines.append(f"🏫 School: {school_min}")

        # Build message sections
        message_parts = []
        
        # Title line with address and price
        if address and price:
            message_parts.append(f"🏠 <b>{address}</b> - {price}")
        
        # Year built (moved to top for maximum prominence)
        if year_built:
            message_parts.append(f"🏗️ <b>Year of Construction: {year_built}</b>")
        else:
            # Add a note when year built is not available
            message_parts.append(f"🏗️ <b>Year of Construction: On Request</b>")
        
        # Calculate mortgage with new formula
        price_total = listing.get('price_total', 0)
        if price_total > 0:
            # Increase price by 10%
            adjusted_price = price_total * 1.10
            # Calculate 20% down payment from adjusted price
            down_payment = adjusted_price * 0.20
            # Calculate loan amount
            loan_amount = adjusted_price - down_payment
            
            # Calculate monthly payment using the provided formula
            # €1,166 monthly rate for €304,570 loan at 2.89% for 35 years
            # This gives us a ratio of approximately 0.00383
            monthly_loan_payment = loan_amount * 0.00383
            
            # Get betriebskosten (operating costs)
            betriebskosten = listing.get('betriebskosten', 0) or 0
            
            # Calculate total monthly payment
            total_monthly = monthly_loan_payment + betriebskosten
            
            message_parts.append(f"💰 Initial Investment: €{down_payment:,.0f} (20% down payment)")
            message_parts.append(f"💳 Total Monthly: €{total_monthly:,.0f} (€{monthly_loan_payment:,.0f} loan + €{betriebskosten:,.0f} BK)")
        
        # District
        if bezirk:
            message_parts.append(f"📍 {bezirk}")
        
        # Area and price per m²
        if area and price_per_m2:
            message_parts.append(f"📐 {area}m² - {price_per_m2}/m²")
        
        # Rooms
        if rooms:
            message_parts.append(f"🛏️ {rooms} Rooms")
        
        # Score (REMOVED - no longer displayed in Telegram messages)
        # if score is not None:
        #     message_parts.append(f"🔥 <b>Score:</b> <b>{score}</b>")
        
        # Transport
        if transport_lines:
            message_parts.extend(transport_lines)
        
        # School
        if school_lines:
            message_parts.extend(school_lines)
        
        # Condition
        if condition:
            message_parts.append(f"🔧 Condition: {condition}")
        
        # Energy class
        if energy_class:
            message_parts.append(f"⚡ Energy Class: {energy_class}")
        
        # URL
        if url and include_url:
            message_parts.append(f"🔗 <a href='{url}'>View Listing</a>")
        
        # Join all parts with newlines and clean up
        message = "\n".join(message_parts)
        
        # Final cleanup: remove any excessive whitespace and normalize
        message = '\n'.join(line.strip() for line in message.split('\n') if line.strip())
        
        # Ensure proper spacing between sections
        message = message.replace('\n\n\n', '\n\n')  # Remove triple newlines
        message = message.replace('\n\n\n', '\n\n')  # Do it again in case there were more
        
        # Clean up any remaining whitespace issues but preserve line breaks
        lines = message.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_line = line.strip()
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
        
        # Join with single newlines
        message = '\n'.join(cleaned_lines)
        
        return message
    
    def test_connection(self) -> bool:
        """Test if the bot can connect to Telegram API without sending a message"""
        try:
            # Just test the API connection by getting bot info
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    logging.info(f"✅ Telegram connection test successful for bot: {data['result'].get('username', 'Unknown')}")
                    return True
                else:
                    logging.error(f"❌ Telegram API returned error: {data}")
                    return False
            else:
                logging.error(f"❌ Telegram API request failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Telegram connection test failed: {e}")
            return False 

    def send_top_listings(self, listings: List[Dict], title: str = "🏆 Top Properties", max_listings: int = 5) -> bool:
        """
        Send top listings to Telegram channel (one by one, like main.py)
        
        Args:
            listings: List of listing dictionaries from MongoDB
            title: Title for the message
            max_listings: Maximum number of listings to send
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if not listings:
                logging.info("No listings to send")
                return True
            
            # Limit to max_listings
            top_listings = listings[:max_listings]
            
            # Send header message
            header_message = f"{title}\n"
            header_message += f"📊 Found {len(listings)} total properties\n"
            header_message += f"🎯 Showing top {len(top_listings)} by score\n"
            header_message += f"📅 Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            success = self.send_message(header_message)
            if not success:
                logging.error("Failed to send header message")
                return False
            
            # Send each listing individually (like main.py does)
            sent_count = 0
            for i, listing in enumerate(top_listings, 1):
                try:
                    # Format the listing using the same method as main.py
                    message = self._format_property_message(listing, include_url=True)
                    
                    # Send the individual listing
                    success = self.send_message(message)
                    if success:
                        sent_count += 1
                        logging.info(f"✅ Sent listing {i}/{len(top_listings)} to Telegram")
                    else:
                        logging.error(f"❌ Failed to send listing {i}/{len(top_listings)}")
                    
                    # Small delay between messages to avoid rate limiting
                    time.sleep(1)
                        
                except Exception as e:
                    logging.error(f"Error sending listing {i}: {e}")
                    continue
            
            # Send footer message
            footer_message = f"✅ Sent {sent_count}/{len(top_listings)} top properties to channel"
            self.send_message(footer_message)
            
            logging.info(f"✅ Sent {sent_count} top listings to Telegram")
            return sent_count > 0
            
        except Exception as e:
            logging.error(f"Error sending top listings: {e}")
            return False 