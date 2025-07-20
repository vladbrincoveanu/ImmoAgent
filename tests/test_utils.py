#!/usr/bin/env python3
"""
Test utilities for immo-scouter
Provides functions to load test configuration and set up test environments
"""

import os
import json
import sys
from typing import Dict, Optional

def get_test_config_path() -> str:
    """Get the path to the test configuration file"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'test_config.json')

def load_test_config() -> Dict:
    """
    Load test configuration from Tests/test_config.json
    
    Returns:
        Dict: Test configuration dictionary
        
    Raises:
        FileNotFoundError: If test config file doesn't exist
    """
    config_path = get_test_config_path()
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Test config file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"✅ Loaded test config from {config_path}")
            return config
    except Exception as e:
        raise Exception(f"Error loading test config: {e}")

def setup_test_environment():
    """
    Set up test environment by temporarily setting environment variables
    to use test configuration
    """
    # Set environment variable to indicate we're in test mode
    os.environ['IMMO_SCOUTER_TEST_MODE'] = 'true'
    
    # Set test database name
    os.environ['MONGODB_TEST_DB'] = 'test_immo'
    
    print("🧪 Test environment set up")

def cleanup_test_environment():
    """Clean up test environment variables"""
    # Remove test environment variables
    os.environ.pop('IMMO_SCOUTER_TEST_MODE', None)
    os.environ.pop('MONGODB_TEST_DB', None)
    
    print("🧹 Test environment cleaned up")

def is_test_mode() -> bool:
    """Check if we're running in test mode"""
    return os.environ.get('IMMO_SCOUTER_TEST_MODE') == 'true'

def get_test_mongodb_uri() -> str:
    """Get MongoDB URI for testing"""
    if is_test_mode():
        return "mongodb://localhost:27017/test_immo"
    else:
        return "mongodb://localhost:27017/immo"

def create_test_config_template():
    """Create a test config template if it doesn't exist"""
    config_path = get_test_config_path()
    
    if os.path.exists(config_path):
        print(f"✅ Test config already exists: {config_path}")
        return
    
    # Create test config template
    test_config = {
        "mongodb_uri": "mongodb://localhost:27017/test_immo",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3.1:8b",
        "openai_api_key": null,
        "openai_model": "gpt-4o-mini",
        "source": "willhaben",
        "max_pages": 2,
        "scraping": {
            "timeout": 10,
            "delay_between_requests": 0.5,
            "selenium_wait_time": 5,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        "willhaben": {
            "base_url": "https://www.willhaben.at",
            "search_url": "https://www.willhaben.at/iad/immobilien/eigentumswohnung/wien",
            "max_pages": 1,
            "timeout": 10
        },
        "immo_kurier": {
            "base_url": "https://immo.kurier.at",
            "search_url": "https://immo.kurier.at/suche?l=Wien&r=0km&_multiselect_r=0km&a=at.wien&t=all%3Asale%3Aliving&pf=&pt=&rf=&rt=&sf=&st=",
            "max_pages": 1,
            "timeout": 10
        },
        "derstandard": {
            "base_url": "https://immobilien.derstandard.at",
            "search_url": "https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3",
            "max_pages": 1,
            "timeout": 10
        },
        "telegram": {
            "telegram_main": {
                "bot_token": "TEST_BOT_TOKEN_1234567890",
                "chat_id": "TEST_CHAT_ID_1234567890"
            },
            "telegram_vienna": {
                "bot_token": "TEST_BOT_TOKEN_1234567890",
                "chat_id": "TEST_CHAT_ID_1234567890"
            },
            "min_score_threshold": 40
        },
        "top5": {
            "limit": 3,
            "min_score": 30.0,
            "days_old": 1
        },
        "criteria": {
            "price_max": 500000,
            "price_per_m2_max": 15000,
            "area_m2_min": 15,
            "rooms_min": 2,
            "year_built_min": 1960,
            "districts": [
                "1010", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090", "1100"
            ]
        },
        "minio": {
            "endpoint": "localhost:9000",
            "access_key": "test_access_key",
            "secret_key": "test_secret_key",
            "bucket_name": "test-immo-images",
            "secure": false
        }
    }
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2, ensure_ascii=False)
        print(f"✅ Created test config template: {config_path}")
    except Exception as e:
        print(f"❌ Error creating test config: {e}")

if __name__ == "__main__":
    # Create test config template if run directly
    create_test_config_template() 