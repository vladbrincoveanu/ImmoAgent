#!/usr/bin/env python3
"""
Test script to verify configuration loading in GitHub Actions environment
"""

import sys
import os
import tempfile
import shutil
import json

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_github_actions_config_loading():
    """Test configuration loading in a simulated GitHub Actions environment"""
    print("🧪 Testing Configuration Loading in GitHub Actions Environment")
    print("=" * 60)
    
    # Create a temporary directory to simulate GitHub Actions workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Created temporary workspace: {temp_dir}")
        
        # Create the directory structure similar to GitHub Actions
        project_dir = os.path.join(temp_dir, "ImmoAgent")
        os.makedirs(project_dir)
        
        # Create a minimal config.json in the project root
        config_content = {
            "mongodb_uri": "mongodb://test:test@localhost:27017/test",
            "telegram": {
                "telegram_main": {
                    "bot_token": "test_token",
                    "chat_id": "test_chat_id"
                }
            },
            "top5": {
                "limit": 5,
                "min_score": 40.0,
                "days_old": 7
            }
        }
        
        config_path = os.path.join(project_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump(config_content, f, indent=2)
        
        print(f"📄 Created config.json at: {config_path}")
        
        # Change to the project directory (simulating GitHub Actions working directory)
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            print(f"📂 Changed working directory to: {os.getcwd()}")
            
            # Import and test the configuration loading
            from Application.helpers.utils import load_config, get_project_root
            
            # Test project root detection
            project_root = get_project_root()
            print(f"🔍 Detected project root: {project_root}")
            
            # Test configuration loading
            config = load_config()
            print(f"✅ Successfully loaded config with {len(config)} keys")
            print(f"   MongoDB URI: {config.get('mongodb_uri', 'N/A')}")
            print(f"   Telegram configured: {'Yes' if config.get('telegram') else 'No'}")
            print(f"   Top5 configured: {'Yes' if config.get('top5') else 'No'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during configuration loading: {e}")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
            print(f"📂 Restored working directory to: {os.getcwd()}")

def test_current_environment():
    """Test configuration loading in the current environment"""
    print("\n🧪 Testing Configuration Loading in Current Environment")
    print("=" * 60)
    
    try:
        from Application.helpers.utils import load_config, get_project_root
        
        # Test project root detection
        project_root = get_project_root()
        print(f"🔍 Detected project root: {project_root}")
        
        # Test configuration loading
        config = load_config()
        print(f"✅ Successfully loaded config with {len(config)} keys")
        print(f"   MongoDB URI: {config.get('mongodb_uri', 'N/A')}")
        print(f"   Telegram configured: {'Yes' if config.get('telegram') else 'No'}")
        print(f"   Top5 configured: {'Yes' if config.get('top5') else 'No'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during configuration loading: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Configuration Loading Tests")
    print("=" * 60)
    
    # Test 1: GitHub Actions environment simulation
    success1 = test_github_actions_config_loading()
    
    # Test 2: Current environment
    success2 = test_current_environment()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"   GitHub Actions simulation: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"   Current environment: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    overall_success = success1 and success2
    print(f"\nOverall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 