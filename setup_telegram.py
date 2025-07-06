#!/usr/bin/env python3
"""
Telegram Bot Setup Script for Property Monitor

This script helps you set up Telegram notifications for your property monitor.
Follow the steps below to create a bot and get your credentials.
"""

import json
import requests
import os

def print_header():
    print("=" * 60)
    print("🤖 TELEGRAM BOT SETUP FOR PROPERTY MONITOR")
    print("=" * 60)
    print()

def print_steps():
    print("📋 SETUP STEPS:")
    print("1. Create a Telegram bot using @BotFather")
    print("2. Get your bot token")
    print("3. Get your chat ID")
    print("4. Configure the bot")
    print()

def create_bot_instructions():
    print("🔧 STEP 1: Create a Telegram Bot")
    print("- Open Telegram and search for @BotFather")
    print("- Send /newbot command")
    print("- Choose a name for your bot (e.g., 'Property Monitor')")
    print("- Choose a username (must end with 'bot', e.g., 'property_monitor_bot')")
    print("- BotFather will give you a bot token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
    print()

def get_chat_id_instructions():
    print("🔧 STEP 2: Get Your Chat ID")
    print("Option A - Send message to your bot:")
    print("- Search for your bot by username")
    print("- Send any message to it")
    print("- Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates")
    print("- Look for 'chat' -> 'id' in the response")
    print()
    print("Option B - Use @userinfobot:")
    print("- Search for @userinfobot in Telegram")
    print("- Send /start to it")
    print("- It will reply with your chat ID")
    print()

def test_bot_connection(bot_token, chat_id):
    """Test if the bot can send messages"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "🤖 Property Monitor Bot Test\n\n✅ Connection successful!\n\nYour bot is ready to send property notifications."
        }
        
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            print("✅ Bot connection test successful!")
            return True
        else:
            print(f"❌ Bot connection failed: {result.get('description')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing bot connection: {e}")
        return False

def save_config(bot_token, chat_id):
    """Save the Telegram configuration"""
    # Load existing config or create new
    config_paths = ['config.json', 'immo-scouter/config.default.json']
    config = {}
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                break
            except Exception as e:
                print(f"Error loading {config_path}: {e}")
                continue
    
    # Update with new Telegram credentials
    config['telegram_bot_token'] = bot_token
    config['telegram_chat_id'] = chat_id
    
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        print("✅ Configuration saved to config.json")
        return True
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False

def main():
    print_header()
    print_steps()
    
    # Show instructions
    create_bot_instructions()
    get_chat_id_instructions()
    
    print("🔧 STEP 3: Configure Your Bot")
    print("Enter your bot credentials below:")
    print()
    
    # Get bot token
    bot_token = input("Enter your bot token: ").strip()
    if not bot_token:
        print("❌ Bot token is required!")
        return
    
    # Get chat ID
    chat_id = input("Enter your chat ID: ").strip()
    if not chat_id:
        print("❌ Chat ID is required!")
        return
    
    print()
    print("🧪 Testing bot connection...")
    
    # Test the connection
    if test_bot_connection(bot_token, chat_id):
        print()
        print("💾 Saving configuration...")
        
        if save_config(bot_token, chat_id):
            print()
            print("🎉 SETUP COMPLETE!")
            print("Your Telegram bot is now configured and ready to use.")
            print()
            print("📱 To test it, run:")
            print("   python main.py")
            print()
            print("🔄 For continuous monitoring, run:")
            print("   python monitor.py")
            print()
            print("📋 To disable Telegram notifications:")
            print("   Edit config.json and set 'telegram_enabled' to false")
        else:
            print("❌ Failed to save configuration")
    else:
        print("❌ Bot setup failed. Please check your credentials and try again.")

if __name__ == "__main__":
    main() 