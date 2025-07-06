#!/usr/bin/env python3
"""
Test script for Telegram bot debugging
"""

import requests
import json

def test_bot_info(bot_token):
    """Test if bot token is valid"""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        response = requests.get(url, timeout=10)
        print(f"Bot info response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Bot info: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Error getting bot info: {e}")
        return False

def test_get_updates(bot_token):
    """Get recent updates to see available chats"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        print(f"Updates response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Updates: {json.dumps(data, indent=2)}")
            
            # Extract chat IDs
            if data.get('ok') and data.get('result'):
                chat_ids = set()
                for update in data['result']:
                    if 'message' in update:
                        chat = update['message']['chat']
                        chat_ids.add(chat['id'])
                        print(f"Found chat: ID={chat['id']}, Type={chat['type']}, Title={chat.get('title', 'N/A')}")
                return list(chat_ids)
        else:
            print(f"Error: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting updates: {e}")
        return []

def test_send_message(bot_token, chat_id, message="Test message"):
    """Test sending a message"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"Send message response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Send result: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def main():
    # Load config
    try:
        with open('telegram_config.json', 'r') as f:
            config = json.load(f)
        
        bot_token = config.get('bot_token')
        chat_id = config.get('chat_id')
        
        print(f"Bot token: {bot_token}")
        print(f"Chat ID: {chat_id}")
        print()
        
        # Test bot token
        print("1. Testing bot token...")
        if not test_bot_info(bot_token):
            print("❌ Invalid bot token!")
            return
        
        print("✅ Bot token is valid!")
        print()
        
        # Test getting updates
        print("2. Getting recent updates...")
        chat_ids = test_get_updates(bot_token)
        
        if chat_ids:
            print(f"✅ Found {len(chat_ids)} chat(s)")
            if chat_id not in chat_ids:
                print(f"⚠️  Your chat ID ({chat_id}) not found in recent updates")
                print(f"Available chat IDs: {chat_ids}")
                print("Try sending a message to your bot first!")
        else:
            print("⚠️  No recent updates found")
            print("Try sending a message to your bot first!")
        print()
        
        # Test sending message
        print("3. Testing message sending...")
        if test_send_message(bot_token, chat_id, "🧪 Property Monitor Bot Test\n\nThis is a test message to verify the connection."):
            print("✅ Message sent successfully!")
        else:
            print("❌ Failed to send message")
            print("\nTroubleshooting:")
            print("1. Make sure you've sent a message to your bot first")
            print("2. Check if the chat ID is correct")
            print("3. Make sure the bot hasn't been blocked")
        
    except FileNotFoundError:
        print("❌ telegram_config.json not found!")
    except json.JSONDecodeError:
        print("❌ Invalid telegram_config.json!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 