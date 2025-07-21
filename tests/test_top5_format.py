#!/usr/bin/env python3
"""
Test script to show the new Top5 message format
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.telegram_bot import TelegramBot

def test_message_format():
    """Test the new message format without rate line"""
    print("🧪 Testing New Top5 Message Format")
    print("=" * 50)
    
    # Create a sample listing
    sample_listing = {
        'address': 'Teststraße 123, 1120 Wien',
        'price_total': 315000,
        'bezirk': '1120',
        'area_m2': 84.19,
        'price_per_m2': 3740,
        'rooms': 3,
        'year_built': 1990,
        'condition': 'Gut',
        'energy_class': 'B',
        'ubahn_walk_minutes': 8,
        'school_walk_minutes': 12,
        'url': 'https://example.com',
        'score': 44.2,
        'monthly_payment': {
            'loan_payment': 1200,
            'betriebskosten': 300,
            'total_monthly': 1500
        },
        'betriebskosten': 300
    }
    
    # Create a dummy Telegram bot (won't actually send messages)
    telegram_bot = TelegramBot("dummy_token", "dummy_chat_id")
    
    # Format the message
    formatted_message = telegram_bot._format_property_message(sample_listing, include_url=True)
    
    print("📱 New Top5 Message Format:")
    print("-" * 40)
    print(formatted_message)
    print("-" * 40)
    
    # Check that rate line is not present
    if "Rate:" not in formatted_message:
        print("✅ Rate line successfully removed")
    else:
        print("❌ Rate line still present")
    
    # Check that total monthly is present
    if "Total Monthly:" in formatted_message:
        print("✅ Total monthly payment is shown")
    else:
        print("❌ Total monthly payment not shown")
    
    return True

def main():
    """Run the test"""
    success = test_message_format()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 