import requests
import json
from typing import Dict, Optional
import logging

class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the Telegram chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
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
    
    def send_property_notification(self, listing: Dict) -> bool:
        """Send a formatted property notification"""
        try:
            # Format the message
            message = self._format_property_message(listing)
            return self.send_message(message)
            
        except Exception as e:
            logging.error(f"Error formatting property notification: {e}")
            return False
    
    def _format_property_message(self, listing: Dict) -> str:
        """Format property listing as HTML message"""
        bezirk = listing.get('bezirk', 'N/A')
        price_total = listing.get('price_total', 'N/A')
        area_m2 = listing.get('area_m2', 'N/A')
        price_per_m2 = listing.get('price_per_m2', 'N/A')
        rooms = listing.get('rooms', 'N/A')
        ubahn_minutes = listing.get('ubahn_walk_minutes', 'N/A')
        year_built = listing.get('year_built', 'N/A')
        monatsrate = listing.get('monatsrate', 'N/A')
        address = listing.get('address', 'N/A')
        url = listing.get('url', 'N/A')
        
        # Format price values
        price_formatted = f"€{price_total:,}" if isinstance(price_total, int) else str(price_total)
        price_per_m2_formatted = f"€{price_per_m2:,}" if isinstance(price_per_m2, (int, float)) else str(price_per_m2)
        monatsrate_formatted = f"€{monatsrate:,}" if isinstance(monatsrate, (int, float)) else str(monatsrate)
        
        message = f"""
            🏠 <b>NEW PROPERTY MATCH FOUND!</b>

            📍 <b>Location:</b> {bezirk} - {address}
            💰 <b>Price:</b> {price_formatted}
            📐 <b>Area:</b> {area_m2}m²
            💸 <b>Price per m²:</b> {price_per_m2_formatted}
            🛏️ <b>Rooms:</b> {rooms}
            🚇 <b>U-Bahn:</b> {ubahn_minutes} min walk
            🏗️ <b>Year Built:</b> {year_built}
            💳 <b>Monthly Rate:</b> {monatsrate_formatted}

            🔗 <a href="{url}">View Listing</a>

            🎉 <i>This property matches your criteria!</i>
        """
        
        return message.strip()
    
    def test_connection(self) -> bool:
        """Test if the bot can send messages"""
        try:
            test_message = "🤖 <b>Property Monitor Bot</b>\n\n✅ Connection test successful!\n\nYour bot is ready to send property notifications."
            return self.send_message(test_message)
        except Exception as e:
            logging.error(f"Telegram connection test failed: {e}")
            return False 