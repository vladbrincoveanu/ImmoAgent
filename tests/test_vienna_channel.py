#!/usr/bin/env python3
"""
Test script for ViennaApartmentsLive channel
"""

import json
import sys
import os

# Add the project root to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.join(current_dir, 'Project')
sys.path.insert(0, project_dir)

from Application.main import load_config
from Integration.telegram_bot import TelegramBot

def test_vienna_channel():
    """Test the ViennaApartmentsLive channel setup"""
    print("🏠 Testing ViennaApartmentsLive Channel")
    print("=" * 50)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Check telegram configuration
    telegram_config = config.get('telegram', {})
    main_config = telegram_config.get('telegram_main', {})
    
    bot_token = main_config.get('bot_token')
    chat_id = main_config.get('chat_id')
    
    if not bot_token or not chat_id:
        print("❌ Telegram main bot not configured")
        print("   Please run setup_vienna_channel.py first")
        return False
    
    print(f"🤖 Bot token: {bot_token[:10]}...")
    print(f"📱 Channel ID: {chat_id}")
    print()
    
    # Test bot connection
    try:
        bot = TelegramBot(bot_token, chat_id)
        print("✅ Telegram bot created")
        
        # Test connection
        if bot.test_connection():
            print("✅ Channel connection successful")
        else:
            print("❌ Channel connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")
        return False
    
    # Test property notification
    print("\n📤 Testing property notification...")
    
    test_listing = {
        'title': '🏠 Premium Vienna Apartment - Test',
        'address': 'Premium Address 123, 1010 Wien',
        'price_total': 750000,
        'area_m2': 95,
        'rooms': 3,
        'bezirk': '1010',
        'url': 'https://example.com/test-listing',
        'price_per_m2': 7895,
        'year_built': 2020,
        'condition': 'Neubau',
        'energy_class': 'A',
        'ubahn_walk_minutes': 3,
        'school_walk_minutes': 8,
        'calculated_monatsrate': 2200,
        'own_funds': 150000,
        'score': 85
    }
    
    success = bot.send_property_notification(test_listing)
    if success:
        print("✅ Test property notification sent successfully!")
        print("📱 Check your ViennaApartmentsLive channel for the test message")
    else:
        print("❌ Failed to send test property notification")
        return False
    
    print("\n🎉 ViennaApartmentsLive Channel Test Complete!")
    print("=" * 50)
    print("✅ Bot connection working")
    print("✅ Channel access working")
    print("✅ Property notifications working")
    print()
    print("🚀 Your channel is ready to receive apartment listings!")
    print("💡 Run 'python Application/main.py' to start scraping and posting")
    
    return True

if __name__ == "__main__":
    try:
        success = test_vienna_channel()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1) 