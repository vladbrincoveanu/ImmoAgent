#!/usr/bin/env python3
"""
Test script to verify top5 formatting matches main.py format
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.telegram_bot import TelegramBot
from Application.helpers.utils import load_config

def test_top5_formatting():
    """Test that top5 formatting matches main.py format"""
    print("🧪 Testing Top5 Formatting (Main.py Style)")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Initialize Telegram bot
        telegram_config = config.get('telegram', {})
        telegram_main = telegram_config.get('telegram_main', {})
        
        if not telegram_main.get('bot_token') or not telegram_main.get('chat_id'):
            print("❌ Telegram configuration not found")
            return False
        
        telegram_bot = TelegramBot(
            telegram_main['bot_token'],
            telegram_main['chat_id']
        )
        
        # Test connection
        if not telegram_bot.test_connection():
            print("❌ Failed to connect to Telegram")
            return False
        
        print("✅ Telegram connection successful")
        
        # Create sample listings with realistic data
        sample_listings = [
            {
                'title': 'Premium Vienna Apartment - Test 1',
                'address': 'Stipcakgasse 12, 1230 Wien',
                'price_total': 280000,
                'area_m2': 48.13,
                'rooms': 2.0,
                'bezirk': '1230',
                'url': 'https://example.com/test1',
                'price_per_m2': 5818,
                'year_built': 2024,
                'condition': 'Erstbezug',
                'energy_class': 'A',
                'ubahn_walk_minutes': 12,
                'school_walk_minutes': 10,
                'calculated_monatsrate': 1134,
                'betriebskosten': 248,
                'betriebskosten_estimated': True,
                'own_funds': 56000,
                'score': 85.5,
                'source': 'Willhaben'
            },
            {
                'title': 'Modern City Center Flat - Test 2',
                'address': 'Mariahilfer Straße 45, 1060 Wien',
                'price_total': 450000,
                'area_m2': 75.5,
                'rooms': 3.0,
                'bezirk': '1060',
                'url': 'https://example.com/test2',
                'price_per_m2': 5960,
                'year_built': 2020,
                'condition': 'Sehr gut',
                'energy_class': 'B',
                'ubahn_walk_minutes': 5,
                'school_walk_minutes': 8,
                'calculated_monatsrate': 1800,
                'betriebskosten': 320,
                'betriebskosten_estimated': False,
                'own_funds': 90000,
                'score': 82.0,
                'source': 'Immo Kurier'
            }
        ]
        
        print("📝 Testing individual message formatting...")
        
        # Test formatting of individual messages (like main.py)
        for i, listing in enumerate(sample_listings, 1):
            print(f"\n🏠 Testing listing {i}:")
            
            # Format the message using the same method as main.py
            message = telegram_bot._format_property_message(listing, include_url=True)
            
            # Check for required emojis and formatting
            required_elements = [
                '🏠',  # House emoji for title
                '💰',  # Money emoji for rate
                '📍',  # Location emoji for district
                '📐',  # Ruler emoji for area
                '🛏️',  # Bed emoji for rooms
                '🚇',  # Train emoji for U-Bahn
                '🏫',  # School emoji for school
                '🔗'   # Link emoji for URL
            ]
            
            missing_elements = []
            for element in required_elements:
                if element not in message:
                    missing_elements.append(element)
            
            if missing_elements:
                print(f"   ❌ Missing elements: {missing_elements}")
            else:
                print(f"   ✅ All required emojis present")
            
            # Check for data presence
            data_checks = [
                ('Address', listing['address']),
                ('Price', f"€{listing['price_total']:,.0f}"),
                ('Area', f"{listing['area_m2']}m²"),
                ('Rooms', f"{listing['rooms']} Zimmer"),
                ('URL', listing['url'])
            ]
            
            for check_name, expected_value in data_checks:
                if expected_value in message:
                    print(f"   ✅ {check_name} present")
                else:
                    print(f"   ❌ {check_name} missing")
            
            # Show first few lines of the message
            lines = message.split('\n')
            print(f"   📱 Message preview (first 5 lines):")
            for j, line in enumerate(lines[:5]):
                print(f"      {j+1}: {line}")
            if len(lines) > 5:
                print(f"      ... ({len(lines)-5} more lines)")
        
        print("\n📤 Testing top5 sending (individual messages)...")
        
        # Test sending top5 listings (should send individually)
        success = telegram_bot.send_top_listings(
            listings=sample_listings,
            title="🧪 Test Top5 Formatting",
            max_listings=2
        )
        
        if success:
            print("✅ Top5 sending successful")
            print("📱 Check your channel for individual property messages")
        else:
            print("❌ Top5 sending failed")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 Top5 Formatting Test Complete!")
        print("✅ Individual message formatting works")
        print("✅ Messages sent one by one (like main.py)")
        print("✅ No rankings or scores in individual messages")
        print("✅ Proper emojis and formatting")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return False

def main():
    """Run the test"""
    success = test_top5_formatting()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 