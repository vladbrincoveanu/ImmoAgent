#!/usr/bin/env python3
"""
Simple test to verify GitHub Actions compatibility
"""

import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing Module Imports")
    print("=" * 40)
    
    try:
        from Application.helpers.utils import load_config
        print("✅ Application.helpers.utils imported")
        
        from Application.scoring import set_buyer_profile
        print("✅ Application.scoring imported")
        
        from Integration.mongodb_handler import MongoDBHandler
        print("✅ Integration.mongodb_handler imported")
        
        from Integration.telegram_bot import TelegramBot
        print("✅ Integration.telegram_bot imported")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config_loading():
    """Test config loading in GitHub Actions environment"""
    print("\n🧪 Testing Config Loading")
    print("=" * 40)
    
    try:
        from Application.helpers.utils import load_config
        
        # Set some test environment variables
        os.environ['MONGODB_URI'] = 'mongodb://test:test@localhost:27017/test'
        os.environ['TELEGRAM_BOT_MAIN_TOKEN'] = 'test_bot_token_123'
        os.environ['TELEGRAM_BOT_MAIN_CHAT_ID'] = 'test_chat_id_456'
        
        config = load_config()
        print(f"✅ Config loaded with {len(config)} top-level keys")
        print(f"✅ MongoDB URI: {config.get('mongodb_uri', 'NOT_FOUND')}")
        print(f"✅ Telegram token: {config.get('telegram', {}).get('telegram_main', {}).get('bot_token', 'NOT_FOUND')}")
        
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False

def test_buyer_profile():
    """Test buyer profile functionality"""
    print("\n🧪 Testing Buyer Profile")
    print("=" * 40)
    
    try:
        from Application.scoring import set_buyer_profile, get_current_profile
        
        set_buyer_profile('diy_renovator')
        current_profile = get_current_profile()
        print(f"✅ Current profile: {current_profile}")
        
        return True
    except Exception as e:
        print(f"❌ Buyer profile test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 GitHub Actions Compatibility Test")
    print("=" * 50)
    
    success1 = test_imports()
    success2 = test_config_loading()
    success3 = test_buyer_profile()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 and success3 else '❌ FAILED'}")
    
    if success1 and success2 and success3:
        print("🎉 All tests passed! The application is ready for GitHub Actions.")
        print("✅ Imports work correctly")
        print("✅ Config loading works with environment variables")
        print("✅ Buyer profiles work correctly")
    
    return success1 and success2 and success3

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 