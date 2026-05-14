#!/usr/bin/env python3
"""
Setup script for ViennaApartmentsLive channel
"""

import json
import os
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from Application.main import load_config

def _create_session_with_retry() -> requests.Session:
    """Create requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy, timeout=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def setup_vienna_channel():
    """Setup ViennaApartmentsLive channel"""
    print("🏠 Setting up ViennaApartmentsLive Channel")
    print("=" * 50)
    
    # ViennaApartmentsLive channel details
    channel_name = "ViennaApartmentsLive"
    channel_id = "-1002541247936"
    
    print(f"📱 Channel: {channel_name}")
    print(f"🆔 Channel ID: {channel_id}")
    print()
    
    # Load existing config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Get bot token from environment variable first
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        # Get bot token from existing config
        telegram_config = config.get('telegram', {})
        main_config = telegram_config.get('telegram_main', {})
        dev_config = telegram_config.get('telegram_dev', {})
        
        # Try to get bot token from main config first, then dev config
        bot_token = main_config.get('bot_token') or dev_config.get('bot_token')
    
        if not bot_token:
            print("❌ No bot token found in config")
            print("   Please add a bot token to config.json first")
            return False
    
    print(f"🤖 Using bot token: {bot_token[:10]}...")
    print()
    
    # Test bot token
    print("🔍 Testing bot token...")
    session = _create_session_with_retry()
    try:
        response = session.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                bot_data = bot_info['result']
                print(f"✅ Bot token valid!")
                print(f"   Bot name: {bot_data.get('first_name', 'Unknown')}")
                print(f"   Bot username: @{bot_data.get('username', 'Unknown')}")
            else:
                print(f"❌ Bot token invalid: {bot_info.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ Failed to validate bot token: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing bot token: {e}")
        return False
    
    # Test channel access
    print("\n🔍 Testing channel access...")
    try:
        response = session.get(f"https://api.telegram.org/bot{bot_token}/getChat", 
                              params={'chat_id': channel_id})
        if response.status_code == 200:
            chat_info = response.json()
            if chat_info.get('ok'):
                chat_data = chat_info['result']
                print(f"✅ Channel access successful!")
                print(f"   Channel: {chat_data.get('title', 'Unknown')}")
                print(f"   Type: {chat_data.get('type', 'Unknown')}")
            else:
                print(f"❌ Failed to access channel: {chat_info.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ Failed to access channel: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing channel access: {e}")
        return False
    
    # Send test message
    print("\n📤 Sending test message...")
    try:
        test_message = f"🧪 Test message from ViennaApartmentsBot\n\nThis channel is now configured for apartment notifications!"
        response = session.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                               params={
                                   'chat_id': channel_id,
                                   'text': test_message,
                                   'parse_mode': 'HTML'
                               })
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Test message sent successfully!")
                print("📱 Check your ViennaApartmentsLive channel")
            else:
                print(f"❌ Failed to send test message: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ Failed to send test message: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error sending test message: {e}")
        return False
    
    # Update config to use ViennaApartmentsLive as main channel
    print("\n📝 Updating config...")
    try:
        # Update the main channel to use ViennaApartmentsLive
        config['telegram']['telegram_main'] = {
            'bot_token': bot_token,
            'chat_id': channel_id
        }
        
        # Save updated config
        config_path = "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Config updated: {config_path}")
        print(f"   Main channel now points to ViennaApartmentsLive")
        
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False
    
    print("\n🎉 ViennaApartmentsLive Channel Setup Complete!")
    print("=" * 50)
    print("✅ Bot token validated")
    print("✅ Channel access confirmed")
    print("✅ Test message sent")
    print("✅ Config updated")
    print()
    print("🚀 Your ViennaApartmentsLive channel is ready!")
    print("💡 Run 'python ../Tests/test_vienna_channel.py' to test")
    print("💡 Run 'python Application/main.py' to start scraping and posting")
    
    return True

if __name__ == "__main__":
    try:
        success = setup_vienna_channel()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1) 