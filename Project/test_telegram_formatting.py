#!/usr/bin/env python3
"""
Test script for Telegram message formatting
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Integration.telegram_bot import TelegramBot, clean_utf8_text

def test_message_formatting():
    """Test the message formatting with sample data"""
    print("🧪 Testing Telegram Message Formatting")
    print("=" * 50)
    
    # Sample listing data with potential whitespace issues
    test_listing = {
        'title': '🏠 Premium Vienna Apartment - Test',
        'address': 'Stipcakgasse, 1230 Wien',
        'price_total': 280000,
        'area_m2': 48.13,
        'rooms': 2.0,
        'bezirk': '1230',
        'url': 'https://example.com/test-listing',
        'price_per_m2': 5818,
        'year_built': 2024,
        'condition': 'Erstbezug',
        'energy_class': 'A',
        'ubahn_walk_minutes': 12,
        'school_walk_minutes': 10,
        'calculated_monatsrate': 1134,
        'betriebskosten': 248,
        'betriebskosten_estimated': True,
        'own_funds': 56000,
        'score': 41.2
    }
    
    # Test the clean_utf8_text function
    print("🔍 Testing clean_utf8_text function...")
    
    test_texts = [
        "Normal text",
        "Text with   extra   spaces",
        "Text\nwith\nnewlines",
        "Text\twith\ttabs",
        "Text with trailing spaces   ",
        "   Text with leading spaces",
        "Text with mixed   \n\t   whitespace"
    ]
    
    for text in test_texts:
        cleaned = clean_utf8_text(text)
        print(f"Original: '{text}'")
        print(f"Cleaned:  '{cleaned}'")
        print()
    
    # Test message formatting
    print("📝 Testing message formatting...")
    
    # Create a dummy bot for testing (we won't actually send messages)
    class DummyBot:
        def __init__(self):
            self.min_score_threshold = 40
            self.max_messages_per_run = 5
    
    bot = DummyBot()
    
    # Test the formatting function directly
    try:
        # Import the formatting function
        from Integration.telegram_bot import TelegramBot
        
        # Create a real bot instance for formatting
        telegram_bot = TelegramBot("dummy_token", "dummy_chat_id")
        
        # Format the message
        formatted_message = telegram_bot._format_property_message(test_listing)
        
        print("✅ Message formatted successfully!")
        print("\n📱 Formatted message:")
        print("-" * 40)
        print(formatted_message)
        print("-" * 40)
        
        # Check for excessive whitespace
        lines = formatted_message.split('\n')
        print(f"\n📊 Message analysis:")
        print(f"   Total lines: {len(lines)}")
        print(f"   Empty lines: {sum(1 for line in lines if not line.strip())}")
        print(f"   Lines with only spaces: {sum(1 for line in lines if line.strip() == '')}")
        
        # Check for whitespace issues
        has_issues = False
        for i, line in enumerate(lines):
            if line.strip() != line:
                print(f"   ⚠️  Line {i+1} has leading/trailing whitespace: '{line}'")
                has_issues = True
        
        if not has_issues:
            print("   ✅ No whitespace issues detected!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing message formatting: {e}")
        return False

if __name__ == "__main__":
    try:
        success = test_message_formatting()
        if success:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed!")
    except Exception as e:
        print(f"❌ Test failed: {e}") 