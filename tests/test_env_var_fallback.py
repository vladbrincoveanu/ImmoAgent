#!/usr/bin/env python3
"""
Test script to verify environment variable fallback for config loading
"""

import sys
import os
import tempfile
import json

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_env_var_fallback():
    """Test environment variable fallback for config loading"""
    print("🧪 Testing Environment Variable Fallback")
    print("=" * 50)
    
    # Test 1: No config file, only environment variables
    print("\n📋 Test 1: No config file, environment variables only")
    
    # Set environment variables
    os.environ['MONGODB_URI'] = 'mongodb://test:test@localhost:27017/test'
    os.environ['TELEGRAM_BOT_MAIN_TOKEN'] = 'test_bot_token_123'
    os.environ['TELEGRAM_BOT_MAIN_CHAT_ID'] = 'test_chat_id_456'
    os.environ['MINIO_ENDPOINT'] = 'test-minio:9000'
    os.environ['OPENAI_API_KEY'] = 'test_openai_key'
    
    try:
        from Application.helpers.utils import load_config
        config = load_config()
        print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
        print(f"✅ MongoDB URI: {config.get('mongodb_uri', 'NOT_FOUND')}")
        print(f"✅ Telegram Main Token: {config.get('telegram', {}).get('telegram_main', {}).get('bot_token', 'NOT_FOUND')}")
        print(f"✅ Telegram Main Chat ID: {config.get('telegram', {}).get('telegram_main', {}).get('chat_id', 'NOT_FOUND')}")
        print(f"✅ MinIO Endpoint: {config.get('minio', {}).get('endpoint', 'NOT_FOUND')}")
        print(f"✅ OpenAI API Key: {config.get('openai_api_key', 'NOT_FOUND')}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    
    # Test 2: Partial config file with environment variable supplementation
    print("\n📋 Test 2: Partial config file with environment variable supplementation")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a partial config file
        partial_config = {
            "mongodb_uri": "mongodb://old:old@localhost:27017/old",
            "telegram": {
                "telegram_main": {
                    "bot_token": "old_token",
                    "chat_id": "old_chat_id"
                }
            },
            "scraping": {
                "timeout": 30
            }
        }
        
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump(partial_config, f, indent=2)
        
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            from Application.helpers.utils import load_config
            config = load_config()
            print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
            print(f"✅ MongoDB URI (should be from env): {config.get('mongodb_uri', 'NOT_FOUND')}")
            print(f"✅ Telegram Main Token (should be from env): {config.get('telegram', {}).get('telegram_main', {}).get('bot_token', 'NOT_FOUND')}")
            print(f"✅ Telegram Main Chat ID (should be from env): {config.get('telegram', {}).get('telegram_main', {}).get('chat_id', 'NOT_FOUND')}")
            print(f"✅ MinIO Endpoint (should be from env): {config.get('minio', {}).get('endpoint', 'NOT_FOUND')}")
            print(f"✅ OpenAI API Key (should be from env): {config.get('openai_api_key', 'NOT_FOUND')}")
            
            # Verify environment variables override config file
            assert config.get('mongodb_uri') == 'mongodb://test:test@localhost:27017/test'
            assert config.get('telegram', {}).get('telegram_main', {}).get('bot_token') == 'test_bot_token_123'
            assert config.get('minio', {}).get('endpoint') == 'test-minio:9000'
            print("✅ Environment variables correctly override config file values")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
        finally:
            os.chdir(original_cwd)
    
    # Test 3: Missing sections in config file
    print("\n📋 Test 3: Missing sections in config file")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a minimal config file without telegram or minio sections
        minimal_config = {
            "mongodb_uri": "mongodb://minimal:minimal@localhost:27017/minimal",
            "scraping": {
                "timeout": 30
            }
        }
        
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump(minimal_config, f, indent=2)
        
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            from Application.helpers.utils import load_config
            config = load_config()
            print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
            print(f"✅ Has telegram section: {'telegram' in config}")
            print(f"✅ Has minio section: {'minio' in config}")
            print(f"✅ Telegram Main Token: {config.get('telegram', {}).get('telegram_main', {}).get('bot_token', 'NOT_FOUND')}")
            print(f"✅ MinIO Endpoint: {config.get('minio', {}).get('endpoint', 'NOT_FOUND')}")
            
            # Verify missing sections are created
            assert 'telegram' in config
            assert 'minio' in config
            assert config.get('telegram', {}).get('telegram_main', {}).get('bot_token') == 'test_bot_token_123'
            assert config.get('minio', {}).get('endpoint') == 'test-minio:9000'
            print("✅ Missing sections correctly created from environment variables")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
        finally:
            os.chdir(original_cwd)
    
    return True

def test_current_environment():
    """Test config loading in current environment"""
    print("\n🧪 Testing Current Environment Config Loading")
    print("=" * 50)
    
    try:
        from Application.helpers.utils import load_config
        config = load_config()
        print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
        print(f"✅ Config keys: {list(config.keys())}")
        
        # Show which values came from environment variables
        if os.getenv('MONGODB_URI'):
            print(f"🔧 MongoDB URI from env: {os.getenv('MONGODB_URI')}")
        if os.getenv('TELEGRAM_BOT_MAIN_TOKEN'):
            print(f"🔧 Telegram token from env: {os.getenv('TELEGRAM_BOT_MAIN_TOKEN')[:10]}...")
        if os.getenv('MINIO_ENDPOINT'):
            print(f"🔧 MinIO endpoint from env: {os.getenv('MINIO_ENDPOINT')}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def main():
    """Run all tests"""
    success1 = test_env_var_fallback()
    success2 = test_current_environment()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 