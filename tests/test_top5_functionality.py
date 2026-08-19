#!/usr/bin/env python3
"""
Test script to verify top5 functionality
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot
from Application.helpers.utils import load_config

pytestmark = pytest.mark.smoke

def test_mongodb_top_listings():
    """Test fetching top listings from MongoDB"""
    print("🧪 Testing MongoDB top listings functionality")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Initialize MongoDB
        mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
        mongo = MongoDBHandler(uri=mongo_uri)
        
        if not mongo.client:
            print("❌ Failed to connect to MongoDB")
            return False
        
        # Test fetching top listings
        print("📊 Fetching top 5 listings...")
        listings = mongo.get_top_listings(limit=5, min_score=0.0, days_old=30)
        
        print(f"✅ Found {len(listings)} listings")
        
        if listings:
            print("\n📋 Sample listing data:")
            sample = listings[0]
            print(f"  Title: {sample.get('title', 'N/A')}")
            print(f"  Score: {sample.get('score', 'N/A')}")
            print(f"  Price: €{sample.get('price_total', 'N/A'):,}" if sample.get('price_total') else f"  Price: {sample.get('price_total', 'N/A')}")
            print(f"  Area: {sample.get('area_m2', 'N/A')}m²")
            print(f"  Rooms: {sample.get('rooms', 'N/A')}")
            print(f"  District: {sample.get('bezirk', 'N/A')}")
            print(f"  Source: {sample.get('source', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing MongoDB: {e}")
        return False

def test_telegram_formatting():
    """Test Telegram message formatting"""
    print("\n🧪 Testing Telegram message formatting")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Initialize Telegram bot
        telegram_config = config.get('telegram', {})
        telegram_main = telegram_config.get('telegram_main', {})
        
        if not telegram_main.get('bot_token') or not telegram_main.get('chat_id'):
            print("❌ Telegram configuration not found")
            return False
        
        telegram_bot = TelegramBot(
            telegram_main['bot_token'],
            telegram_main['chat_id']
        )
        
        # Test connection
        if not telegram_bot.test_connection():
            print("❌ Failed to connect to Telegram")
            return False
        
        print("✅ Telegram connection successful")
        
        # Test message formatting with sample data
        sample_listings = [
            {
                'title': 'Test Property 1',
                'price_total': 500000,
                'area_m2': 80,
                'rooms': 3,
                'bezirk': '1010',
                'score': 85.5,
                'url': 'https://example.com/property1',
                'source': 'Willhaben'
            },
            {
                'title': 'Test Property 2',
                'price_total': 450000,
                'area_m2': 75,
                'rooms': 3,
                'bezirk': '1020',
                'score': 82.0,
                'url': 'https://example.com/property2',
                'source': 'Immo Kurier'
            }
        ]
        
        print("📝 Testing message formatting...")
        success = telegram_bot.send_top_listings(
            listings=sample_listings,
            title="🧪 Test Top Properties",
            max_listings=2
        )
        
        if success:
            print("✅ Message formatting and sending successful")
        else:
            print("❌ Failed to format/send message")
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing Telegram: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Top5 Functionality Tests")
    print("=" * 60)
    
    # Test MongoDB functionality
    mongo_success = test_mongodb_top_listings()
    
    # Test Telegram functionality
    telegram_success = test_telegram_formatting()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"  MongoDB: {'✅ PASS' if mongo_success else '❌ FAIL'}")
    print(f"  Telegram: {'✅ PASS' if telegram_success else '❌ FAIL'}")
    
    overall_success = mongo_success and telegram_success
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
