#!/usr/bin/env python3
"""
Test script to verify Telegram bot UTF-8 encoding fix
"""

import sys
import os

# Add the Project directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Project'))

from Project.Integration.telegram_bot import clean_utf8_text, TelegramBot

def test_utf8_cleaning():
    """Test the UTF-8 cleaning function"""
    print("🧪 Testing UTF-8 cleaning function...")
    
    # Test cases with problematic characters
    test_cases = [
        "Normal text",
        "Text with emoji 🏠",
        "Text with surrogate characters \ud800\udc00",  # This should cause issues
        "Mixed text with 🏠 and \ud800\udc00",
        "German text: Österreich, München, Köln",
        "Price: €422,100",
        "Area: 34.74 m²",
        "Condition: Erstbezug",
        "Energy: A+",
        "Address: 1220 Wien, Wagramer Straße 2/30-06"
    ]
    
    for i, test_text in enumerate(test_cases, 1):
        try:
            cleaned = clean_utf8_text(test_text)
            print(f"✅ Test {i}: '{test_text}' -> '{cleaned}'")
        except Exception as e:
            print(f"❌ Test {i} failed: {e}")
    
    print("\n✅ UTF-8 cleaning tests completed!")

def test_telegram_message_formatting():
    """Test Telegram message formatting with problematic data"""
    print("\n🧪 Testing Telegram message formatting...")
    
    # Create a sample listing with potentially problematic data
    sample_listing = {
        'address': '1220 Wien, Wagramer Straße 2/30-06',
        'price_total': 422100,
        'bezirk': '1220 Wien',
        'calculated_monatsrate': 1500,
        'betriebskosten': 300,
        'area_m2': 34.74,
        'price_per_m2': 12150,
        'rooms': 1,
        'year_built': 2025,
        'condition': 'Erstbezug',
        'energy_class': 'A+',
        'url': 'https://example.com',
        'score': 85,
        'ubahn_walk_minutes': 5,
        'school_walk_minutes': 8
    }
    
    try:
        # Create a mock Telegram bot (without real token)
        bot = TelegramBot("fake_token", "fake_chat_id")
        
        # Test message formatting
        message = bot._format_property_message(sample_listing)
        print(f"✅ Message formatted successfully!")
        print(f"Message length: {len(message)} characters")
        print(f"First 200 chars: {message[:200]}...")
        
        # Test UTF-8 encoding
        try:
            message.encode('utf-8')
            print("✅ Message is UTF-8 compatible!")
        except UnicodeEncodeError as e:
            print(f"❌ Message has UTF-8 issues: {e}")
            
    except Exception as e:
        print(f"❌ Message formatting failed: {e}")
    
    print("\n✅ Telegram message formatting tests completed!")

if __name__ == "__main__":
    print("🚀 Starting Telegram UTF-8 Fix Tests...")
    
    test_utf8_cleaning()
    test_telegram_message_formatting()
    
    print("\n🎉 All tests completed!") 