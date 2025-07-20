#!/usr/bin/env python3
"""
Test script to verify Telegram spacing fixes
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.telegram_bot import TelegramBot, clean_utf8_text

def test_telegram_spacing():
    """Test that Telegram message spacing is properly formatted"""
    print("🧪 Testing Telegram spacing fixes")
    print("=" * 50)
    
    # Test the clean_utf8_text function
    print("🔍 Testing clean_utf8_text function...")
    
    test_cases = [
        ("Normal text", "Normal text"),
        ("Text with   extra   spaces", "Text with extra spaces"),
        ("Text\nwith\nnewlines", "Text with newlines"),
        ("Text\twith\ttabs", "Text with tabs"),
        ("Text with trailing spaces   ", "Text with trailing spaces"),
        ("   Text with leading spaces", "Text with leading spaces"),
        ("Text with mixed   \n\t   whitespace", "Text with mixed whitespace"),
        ("Text with . punctuation", "Text with. punctuation"),
        ("Text with , commas", "Text with, commas"),
        ("Text with ! exclamation", "Text with! exclamation"),
        ("Text with ? question", "Text with? question"),
    ]
    
    for original, expected in test_cases:
        cleaned = clean_utf8_text(original)
        if cleaned == expected:
            print(f"   ✅ '{original}' -> '{cleaned}'")
        else:
            print(f"   ❌ '{original}' -> '{cleaned}' (expected: '{expected}')")
    
    print("\n🔍 Testing message formatting...")
    
    # Create a test listing with potential spacing issues
    test_listing = {
        'title': '🏠 Premium Vienna Apartment - Test',
        'address': 'Stipcakgasse, 1230 Wien',
        'price_total': 280000,
        'area_m2': 48.13,
        'rooms': 3.0,
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
    
    try:
        # Create a dummy bot for testing
        bot = TelegramBot("dummy_token", "dummy_chat_id")
        
        # Format the message
        message = bot._format_property_message(test_listing)
        
        print("✅ Message formatted successfully!")
        print(f"Message length: {len(message)} characters")
        
        # Check for spacing issues
        lines = message.split('\n')
        print(f"Total lines: {len(lines)}")
        print(f"Empty lines: {sum(1 for line in lines if not line.strip())}")
        
        # Check for excessive whitespace
        has_issues = False
        for i, line in enumerate(lines):
            if line.strip() != line:
                print(f"   ⚠️  Line {i+1} has leading/trailing whitespace: '{line}'")
                has_issues = True
        
        if not has_issues:
            print("   ✅ No whitespace issues detected!")
        
        # Show first few lines of the message
        print("\n📱 Sample formatted message:")
        print("-" * 40)
        for i, line in enumerate(lines[:10]):  # Show first 10 lines
            print(f"{i+1:2d}: {line}")
        if len(lines) > 10:
            print("    ...")
        print("-" * 40)
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing message formatting: {e}")
        return False

if __name__ == "__main__":
    test_telegram_spacing() 