#!/usr/bin/env python3
"""
Script to help get your correct Telegram chat ID
"""

import requests
import json
import time
import os

def get_chat_id(bot_token):
    """Get chat ID by monitoring for new messages"""
    print("🔍 To get your chat ID:")
    print("1. Open Telegram")
    print("2. Search for your bot: @myunique_11111_Vienna6_bot")
    print("3. Send any message to the bot (e.g., 'Hello')")
    print("4. This script will detect the message and show your chat ID")
    print()
    print("Waiting for your message... (Press Ctrl+C to stop)")
    
    try:
        while True:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        if 'message' in update:
                            chat = update['message']['chat']
                            print(f"\n✅ Found message from:")
                            print(f"   Chat ID: {chat['id']}")
                            print(f"   Type: {chat['type']}")
                            print(f"   Name: {chat.get('first_name', 'N/A')} {chat.get('last_name', '')}")
                            print(f"   Username: @{chat.get('username', 'N/A')}")
                            print()
                            print("📝 Update your config.json with this chat ID!")
                            return chat['id']
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopped waiting for messages")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    # Load current config
    config_paths = ['config.json', 'immo-scouter/config.default.json']
    config = None
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                print(f"✅ Loaded config from {config_path}")
                break
            except Exception as e:
                print(f"❌ Error loading {config_path}: {e}")
                continue
    
    if not config:
        print("❌ No config file found!")
        return
        
    bot_token = config.get('telegram_bot_token')
    current_chat_id = config.get('telegram_chat_id')
    
    print(f"🤖 Bot: @myunique_11111_Vienna6_bot")
    print(f"📱 Current chat ID: {current_chat_id}")
    print()
    
    if current_chat_id == "7664691648":
        print("⚠️  Current chat ID appears to be a bot ID, not a user ID!")
        print("   This is why you're getting 'Forbidden: bots can't send messages to bots'")
        print()
    
    new_chat_id = get_chat_id(bot_token)
    
    if new_chat_id:
        # Update config and save to config.json
        config['telegram_chat_id'] = str(new_chat_id)
        with open('immo-scouter/config.default.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        print(f"✅ Updated config.json with chat ID: {new_chat_id}")
        print()
        print("🧪 Testing the new configuration...")
        
        # Test the new configuration
        from telegram_bot import TelegramBot
        bot = TelegramBot(bot_token, str(new_chat_id))
        if bot.test_connection():
            print("✅ Telegram notifications are now working!")
        else:
            print("❌ Still having issues. Check the troubleshooting guide.")

if __name__ == "__main__":
    main() 