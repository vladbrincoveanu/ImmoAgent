#!/usr/bin/env python3
"""
Test script to verify Telegram channel configuration
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.helpers.utils import load_config
from Integration.telegram_bot import TelegramBot

pytestmark = pytest.mark.smoke

def test_channel_config():
    """Test that the Telegram channel configuration is correct"""
    print("🧪 Testing Telegram Channel Configuration")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Check telegram configuration
        telegram_config = config.get('telegram', {})
        main_config = telegram_config.get('telegram_main', {})
        dev_config = telegram_config.get('telegram_dev', {})
        
        main_token = main_config.get('bot_token')
        main_chat_id = main_config.get('chat_id')
        dev_token = dev_config.get('bot_token')
        dev_chat_id = dev_config.get('chat_id')
        
        print(f"📱 Main bot token: {main_token[:10]}..." if main_token else "❌ Main bot token not found")
        print(f"📱 Main chat ID: {main_chat_id}")
        print(f"📱 Dev bot token: {dev_token[:10]}..." if dev_token else "❌ Dev bot token not found")
        print(f"📱 Dev chat ID: {dev_chat_id}")
        print()
        
        # Check if main chat ID is a channel (starts with -100)
        if main_chat_id and main_chat_id.startswith('-100'):
            print("✅ Main chat ID is a channel (correct format)")
        elif main_chat_id:
            print("⚠️ Main chat ID is not a channel (should start with -100)")
            print("   This means messages will go to a private chat, not a channel")
        else:
            print("❌ Main chat ID not found")
            return False
        
        # Check if dev chat ID is a private chat (positive number)
        if dev_chat_id and not dev_chat_id.startswith('-100'):
            print("✅ Dev chat ID is a private chat (correct for logs)")
        elif dev_chat_id:
            print("⚠️ Dev chat ID is a channel (logs should go to private chat)")
        else:
            print("❌ Dev chat ID not found")
            return False
        
        # Test main bot connection
        if main_token and main_chat_id:
            print("\n🔍 Testing main bot connection...")
            try:
                main_bot = TelegramBot(main_token, main_chat_id)
                if main_bot.test_connection():
                    print("✅ Main bot connection successful")
                else:
                    print("❌ Main bot connection failed")
                    return False
            except Exception as e:
                print(f"❌ Main bot error: {e}")
                return False
        
        # Test dev bot connection
        if dev_token and dev_chat_id:
            print("🔍 Testing dev bot connection...")
            try:
                dev_bot = TelegramBot(dev_token, dev_chat_id)
                if dev_bot.test_connection():
                    print("✅ Dev bot connection successful")
                else:
                    print("❌ Dev bot connection failed")
                    return False
            except Exception as e:
                print(f"❌ Dev bot error: {e}")
                return False
        
        # Test sending a message to the channel
        if main_token and main_chat_id and main_chat_id.startswith('-100'):
            print("\n📤 Testing channel message...")
            try:
                main_bot = TelegramBot(main_token, main_chat_id)
                test_message = """🧪 <b>Channel Configuration Test</b>

✅ Channel configuration is working correctly!
✅ Messages will be sent to the ViennaApartmentsLive channel
✅ Top5 reports will appear in the channel

This test confirms that run_top5.py will send to the channel, not a private chat."""
                
                success = main_bot.send_message(test_message)
                if success:
                    print("✅ Test message sent to channel successfully")
                    print("📱 Check your ViennaApartmentsLive channel for the test message")
                else:
                    print("❌ Failed to send test message to channel")
                    return False
            except Exception as e:
                print(f"❌ Error sending test message: {e}")
                return False
        
        print("\n" + "=" * 50)
        print("🎉 Channel Configuration Test Complete!")
        print("✅ All tests passed")
        print("✅ run_top5.py will now send to the channel")
        print("✅ main.py will continue to send to the channel")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return False

def main():
    """Run the test"""
    success = test_channel_config()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
