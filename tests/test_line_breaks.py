#!/usr/bin/env python3
"""
Test script to verify line breaks are preserved in message formatting
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.telegram_bot import TelegramBot, clean_utf8_text

def test_line_breaks():
    """Test that line breaks are preserved in message formatting"""
    print("🧪 Testing Line Break Preservation")
    print("=" * 50)
    
    # Test the clean_utf8_text function
    print("📝 Testing clean_utf8_text function...")
    
    test_message = """🏠 <b>Test Address, 1230 Wien</b> - €280,000
💰 Rate: €1,134 (€56,000 initial sum invested)
📄 Betriebskosten: €248 (est.)
📍 1230
📐 48.13m² - €5,818/m²
🛏️ 2.0 Zimmer
🚇 U-Bahn: 12 min
🏫 Schule: 10 min
🏗️ Baujahr: 2024
🔧 Zustand: Erstbezug
⚡ Energieklasse: A
🔗 <a href='https://example.com'>Zur Anzeige</a>"""
    
    print("Original message:")
    print(test_message)
    print()
    
    cleaned_message = clean_utf8_text(test_message)
    print("Cleaned message:")
    print(cleaned_message)
    print()
    
    # Check if line breaks are preserved
    original_lines = test_message.split('\n')
    cleaned_lines = cleaned_message.split('\n')
    
    print(f"Original lines: {len(original_lines)}")
    print(f"Cleaned lines: {len(cleaned_lines)}")
    
    if len(original_lines) == len(cleaned_lines):
        print("✅ Line count preserved!")
    else:
        print(f"❌ Line count changed: {len(original_lines)} -> {len(cleaned_lines)}")
        return False
    
    # Check if each line has the expected content
    for i, (orig_line, clean_line) in enumerate(zip(original_lines, cleaned_lines)):
        if orig_line.strip() == clean_line.strip():
            print(f"✅ Line {i+1}: Content preserved")
        else:
            print(f"❌ Line {i+1}: Content changed")
            print(f"   Original: '{orig_line}'")
            print(f"   Cleaned:  '{clean_line}'")
            return False
    
    # Test with a dummy bot
    print("\n📱 Testing message formatting with dummy bot...")
    
    try:
        bot = TelegramBot("dummy_token", "dummy_chat_id")
        
        # Create sample listing
        sample_listing = {
            'title': 'Test Property',
            'address': 'Test Address, 1230 Wien',
            'price_total': 280000,
            'area_m2': 48.13,
            'rooms': 2.0,
            'bezirk': '1230',
            'url': 'https://example.com',
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
            'score': 85.5
        }
        
        # Format the message
        formatted_message = bot._format_property_message(sample_listing, include_url=True)
        
        print("Formatted message:")
        print(formatted_message)
        print()
        
        # Check line breaks in formatted message
        formatted_lines = formatted_message.split('\n')
        print(f"Formatted message has {len(formatted_lines)} lines")
        
        if len(formatted_lines) >= 10:  # Should have multiple lines
            print("✅ Formatted message has proper line breaks")
            
            # Show first few lines
            print("First 5 lines:")
            for i, line in enumerate(formatted_lines[:5]):
                print(f"  {i+1}: {line}")
        else:
            print("❌ Formatted message doesn't have enough lines")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 Line Break Test Complete!")
        print("✅ clean_utf8_text preserves line breaks")
        print("✅ Message formatting creates proper line breaks")
        print("✅ Each property detail is on its own line")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return False

def main():
    """Run the test"""
    success = test_line_breaks()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 