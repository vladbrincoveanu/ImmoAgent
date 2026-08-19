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
from Application.helpers.utils import get_project_root, load_config


def _get_vienna_bot_token(config):
    """Return the explicit Vienna token, then the token stored for Vienna."""
    bot_token = os.getenv('TELEGRAM_BOT_VIENNA_TOKEN')
    if bot_token:
        return bot_token

    telegram_config = config.get('telegram', {})
    if not isinstance(telegram_config, dict):
        return None
    vienna_config = telegram_config.get('telegram_vienna', {})
    if not isinstance(vienna_config, dict):
        return None
    return vienna_config.get('bot_token')


def _resolve_config_path(project_root=None):
    """Resolve the config path using the loader's root and legacy locations."""
    project_root = project_root or get_project_root()
    root_config_path = os.path.join(project_root, 'config.json')
    if os.path.exists(root_config_path):
        return root_config_path

    project_config_path = os.path.join(project_root, 'Project', 'config.json')
    if os.path.exists(project_config_path):
        return project_config_path

    return root_config_path


def _write_vienna_channel_config(config_path, channel_id):
    """Persist only the Vienna chat ID without storing runtime credentials."""
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as config_file:
            raw_config = json.load(config_file)
    else:
        raw_config = {}

    if not isinstance(raw_config, dict):
        raw_config = {}

    telegram_config = raw_config.setdefault('telegram', {})
    if not isinstance(telegram_config, dict):
        telegram_config = {}
        raw_config['telegram'] = telegram_config

    vienna_config = telegram_config.setdefault('telegram_vienna', {})
    if not isinstance(vienna_config, dict):
        vienna_config = {}
        telegram_config['telegram_vienna'] = vienna_config

    vienna_config['chat_id'] = channel_id

    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(raw_config, config_file, indent=2)

def _create_session_with_retry() -> requests.Session:
    """Create requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
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
    
    bot_token = _get_vienna_bot_token(config)
    
    if not bot_token:
        print("❌ No Vienna bot token found in config or environment")
        print("   Set TELEGRAM_BOT_VIENNA_TOKEN or add a Vienna token to config.json")
        return False
    
    print("🤖 Using configured bot token")
    print()
    
    # Test bot token
    print("🔍 Testing bot token...")
    session = _create_session_with_retry()
    try:
        response = session.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
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
    except Exception:
        print("❌ Error testing bot token")
        return False
    
    # Test channel access
    print("\n🔍 Testing channel access...")
    try:
        response = session.get(
            f"https://api.telegram.org/bot{bot_token}/getChat",
            params={'chat_id': channel_id},
            timeout=10,
        )
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
    except Exception:
        print("❌ Error testing channel access")
        return False
    
    # Send test message
    print("\n📤 Sending test message...")
    try:
        test_message = f"🧪 Test message from ViennaApartmentsBot\n\nThis channel is now configured for apartment notifications!"
        response = session.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            params={
                'chat_id': channel_id,
                'text': test_message,
                'parse_mode': 'HTML'
            },
            timeout=10,
        )
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
    except Exception:
        print("❌ Error sending test message")
        return False
    
    # Update config to use ViennaApartmentsLive as the Vienna channel
    print("\n📝 Updating config...")
    try:
        config_path = _resolve_config_path()
        _write_vienna_channel_config(config_path, channel_id)
        
        print(f"✅ Config updated: {config_path}")
        print("   Vienna channel now points to ViennaApartmentsLive")
        
    except Exception:
        print("❌ Error updating config")
        return False
    
    print("\n🎉 ViennaApartmentsLive Channel Setup Complete!")
    print("=" * 50)
    print("✅ Bot token validated")
    print("✅ Channel access confirmed")
    print("✅ Test message sent")
    print("✅ Config updated")
    print()
    print("🚀 Your ViennaApartmentsLive channel is ready!")
    print("💡 Run 'python tests/test_vienna_channel.py' to test")
    print("💡 Run 'python Project/Application/main.py' to start scraping and posting")
    
    return True

if __name__ == "__main__":
    try:
        success = setup_vienna_channel()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception:
        print("❌ Setup failed")
        sys.exit(1) 
