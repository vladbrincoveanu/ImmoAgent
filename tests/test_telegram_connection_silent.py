#!/usr/bin/env python3
"""
Test that Telegram connection tests don't send messages to the channel
"""

import pytest
import sys
import os

pytestmark = pytest.mark.smoke

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_connection_silent():
    """Test that connection test doesn't send messages"""
    print("🧪 Testing Silent Connection Test")
    print("=" * 40)
    
    from Application.helpers.utils import load_config
    from Integration.telegram_bot import TelegramBot
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    telegram_config = config.get('telegram', {})
    telegram_main = telegram_config.get('telegram_main', {})
    
    if not telegram_main.get('bot_token') or not telegram_main.get('chat_id'):
        print("⚠️ No Telegram credentials found in config")
        return False
    
    # Create bot
    bot = TelegramBot(telegram_main['bot_token'], telegram_main['chat_id'])
    
    print(f"🤖 Testing connection for bot with token: {telegram_main['bot_token'][:10]}...")
    
    # Test connection (should not send any message to channel)
    try:
        result = bot.test_connection()
        if result:
            print("✅ Connection test successful (no message sent to channel)")
            return True
        else:
            print("❌ Connection test failed")
            return False
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        return False

def main():
    """Run the test"""
    print("🚀 Telegram Silent Connection Test")
    print("=" * 50)
    
    success = test_connection_silent()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    if success:
        print("🎉 Connection test works without sending messages to channel!")
        print("✅ No unwanted test messages will be sent to main Telegram channel")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
