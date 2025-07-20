#!/usr/bin/env python3
"""
Test script to verify dual Telegram setup:
- Dev channel receives all logs (INFO, WARNING, ERROR)
- Main channel receives only property notifications
"""

import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Application.main import load_config
from Integration.telegram_bot import TelegramBot

def test_dual_telegram_setup():
    """Test the dual Telegram setup"""
    print("🧪 Testing Dual Telegram Setup")
    print("=" * 50)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Test dev Telegram bot
    telegram_config = config.get('telegram', {})
    dev_config = telegram_config.get('telegram_dev', {})
    if not dev_config.get('bot_token') or not dev_config.get('chat_id'):
        print("❌ Dev Telegram not configured")
        return False
    
    try:
        dev_bot = TelegramBot(dev_config['bot_token'], dev_config['chat_id'])
        print("✅ Dev Telegram bot created")
        
        # Test dev bot connection
        if dev_bot.test_connection():
            print("✅ Dev Telegram connection successful")
        else:
            print("❌ Dev Telegram connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Dev Telegram bot error: {e}")
        return False
    
    # Test main Telegram bot
    main_config = telegram_config.get('telegram_main', {})
    main_token = main_config.get('bot_token')
    main_chat_id = main_config.get('chat_id')
    if not main_token or not main_chat_id:
        print("❌ Main Telegram not configured")
        return False
    
    try:
        main_bot = TelegramBot(main_token, main_chat_id)
        print("✅ Main Telegram bot created")
        
        # Test main bot connection
        if main_bot.test_connection():
            print("✅ Main Telegram connection successful")
        else:
            print("❌ Main Telegram connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Main Telegram bot error: {e}")
        return False
    
    # Test logging setup
    print("\n📝 Testing logging setup...")
    
    # Setup dev logging
    dev_handler = dev_bot.setup_error_logging(is_dev_channel=True)
    logger = logging.getLogger()
    logger.addHandler(dev_handler)
    logger.setLevel(logging.INFO)
    
    # Send test messages
    print("📤 Sending test messages...")
    
    # These should go to dev channel
    logging.info("ℹ️ This is an INFO message - should go to dev channel")
    logging.warning("⚠️ This is a WARNING message - should go to dev channel")
    logging.error("❌ This is an ERROR message - should go to dev channel")
    
    # Test property notification (should go to main channel)
    test_listing = {
        'title': 'High-Score Test Property',
        'address': 'Premium Address 456, Vienna',
        'price_total': 800000,
        'area_m2': 120,
        'rooms': 4,
        'bezirk': 'Innere Stadt',
        'url': 'https://example.com',
        'price_per_m2': 6667,
        'year_built': 2020,
        'condition': 'Neubau',
        'energy_class': 'A',
        'ubahn_walk_minutes': 5,
        'school_walk_minutes': 10,
        'calculated_monatsrate': 2500,
        'own_funds': 200000
    }
    
    print("📤 Sending test property notification to main channel...")
    success = main_bot.send_property_notification(test_listing)
    if success:
        print("✅ Test property notification sent to main channel")
    else:
        print("❌ Failed to send test property notification")
    
    # Clean up
    logger.removeHandler(dev_handler)
    
    print("\n✅ Dual Telegram setup test completed!")
    print("📱 Check your Telegram channels:")
    print("   - Dev channel: Should have INFO, WARNING, ERROR messages")
    print("   - Main channel: Should have property notification")
    
    return True

if __name__ == "__main__":
    test_dual_telegram_setup() 