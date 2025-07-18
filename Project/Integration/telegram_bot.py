import requests
import json
from typing import Dict
import logging
from Application.helpers.utils import load_config
from Application.scoring import score_apartment_simple

def clean_utf8_text(text: str) -> str:
    """Clean text to ensure it's UTF-8 compatible and remove surrogate characters"""
    if not isinstance(text, str):
        return str(text)
    
    try:
        # First, try to handle surrogate characters by encoding as utf-8 with error handling
        cleaned = text.encode('utf-8', errors='replace').decode('utf-8')
        return cleaned
    except Exception:
        # If that fails, manually remove problematic characters
        cleaned = ''
        for char in text:
            try:
                # Check if character is a surrogate
                if 0xD800 <= ord(char) <= 0xDFFF:
                    cleaned += ' '  # Replace surrogate with space
                else:
                    char.encode('utf-8')  # Test if character is valid UTF-8
                    cleaned += char
            except UnicodeEncodeError:
                cleaned += ' '  # Replace problematic character with space
            except Exception:
                cleaned += ' '  # Replace any other problematic character with space
        return cleaned.strip()

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
    
    def _format_property_message(self, listing: Dict) -> str:
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
            return clean_utf8_text(str(value))

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
                            transport_lines.append(f"{emoji} {key}: {min_str}")
                            found_transport = True
                            break
            if found_transport:
                break
        if not found_transport:
            # Fallback to ubahn_walk_minutes
            ubahn_min = safe_minutes(listing.get('ubahn_walk_minutes'))
            if ubahn_min:
                transport_lines.append(f"🚇 U-Bahn: {ubahn_min}")

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
                            school_lines.append(f"{emoji} {key}: {min_str}")
                            found_school = True
                            break
            if found_school:
                break
        if not found_school:
            school_min = safe_minutes(listing.get('school_walk_minutes'))
            if school_min:
                school_lines.append(f"🏫 Schule: {school_min}")

        # Build message sections
        message_parts = []
        
        # Title line with address and price
        if address and price:
            message_parts.append(f"🏠 <b>{address}</b> - {price}")
        
        # Rate line with initial sum invested
        if monthly_rate:
            rate_line = f"💰 Rate: {monthly_rate}"
            if initial_sum:
                rate_line += f" ({initial_sum} initial sum invested)"
            if mortgage_line:
                rate_line += mortgage_line
            message_parts.append(rate_line)
        
        # Betriebskosten line
        if betriebskosten:
            betriebskosten_line = f"📄 Betriebskosten: {betriebskosten}"
            if betriebskosten_estimated:
                betriebskosten_line += " (est.)"
            message_parts.append(betriebskosten_line)
        
        # District
        if bezirk:
            message_parts.append(f"📍 {bezirk}")
        
        # Area and price per m²
        if area and price_per_m2:
            message_parts.append(f"📐 {area}m² - {price_per_m2}/m²")
        
        # Rooms
        if rooms:
            message_parts.append(f"🛏️ {rooms} Zimmer")
        
        # Score (if available)
        if score is not None:
            message_parts.append(f"🔥 <b>Score:</b> <b>{score}</b>")
        
        # Transport
        if transport_lines:
            message_parts.extend(transport_lines)
        
        # School
        if school_lines:
            message_parts.extend(school_lines)
        
        # Year built
        if year_built:
            message_parts.append(f"🏗️ Baujahr: {year_built}")
        
        # Condition
        if condition:
            message_parts.append(f"🔧 Zustand: {condition}")
        
        # Energy class
        if energy_class:
            message_parts.append(f"⚡ Energieklasse: {energy_class}")
        
        # URL
        if url:
            message_parts.append(f"🔗 <a href='{url}'>Zur Anzeige</a>")
        
        # Join all parts with newlines
        message = "\n".join(message_parts)
        
        return message
    
    def test_connection(self) -> bool:
        """Test if the bot can send messages"""
        try:
            test_message = "🤖 <b>Property Monitor Bot</b>\n\n✅ Connection test successful!\n\nYour bot is ready to send property notifications."
            return self.send_message(test_message)
        except Exception as e:
            logging.error(f"Telegram connection test failed: {e}")
            return False 