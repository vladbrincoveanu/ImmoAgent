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
        """Format property listing as concise HTML message"""
        def safe_format(value, prefix="€"):
            """Safely format values that might be None"""
            if value is None:
                return "N/A"
            if isinstance(value, (int, float)):
                return f"{prefix}{value:,.0f}"
            return str(value)
        
        # Create a concise message with essential info only
        bezirk = listing.get('bezirk', 'Wien')
        address = listing.get('address', 'N/A')
        price = safe_format(listing.get('price_total'))
        
        # New mortgage info
        monthly_rate = safe_format(listing.get('calculated_monatsrate'))
        mortgage_details = listing.get('mortgage_details', '')

        area = listing.get('area_m2', 'N/A')
        price_per_m2 = safe_format(listing.get('price_per_m2'))
        rooms = listing.get('rooms', 'N/A')
        ubahn_min = listing.get('ubahn_walk_minutes', 'N/A')
        school_min = listing.get('school_walk_minutes', 'N/A')
        year_built = listing.get('year_built', 'N/A')
        condition = listing.get('condition', 'N/A')
        energy_class = listing.get('energy_class', 'N/A')
        url = listing.get('url', '')
        
        message = f"""🏠 <b>{bezirk}</b> - {price}
💳 Rate: {monthly_rate} {mortgage_details}
📍 {address}
📐 {area}m² - {price_per_m2}/m²
🛏️ {rooms} Zimmer
🚇 U-Bahn: {ubahn_min} min
🏫 Schule: {school_min} min
🏗️ Baujahr: {year_built}
🛠️ Zustand: {condition}
⚡ Energieklasse: {energy_class}

🔗 <a href='{url}'>Zur Anzeige</a>"""
        
        return message
    
    def test_connection(self) -> bool:
        """Test if the bot can send messages"""
        try:
            test_message = "🤖 <b>Property Monitor Bot</b>\n\n✅ Connection test successful!\n\nYour bot is ready to send property notifications."
            return self.send_message(test_message)
        except Exception as e:
            logging.error(f"Telegram connection test failed: {e}")
            return False 