#!/usr/bin/env python3
"""
Test script to simulate GitHub Actions environment and test config loading
"""

import sys
import os
import tempfile
import shutil
import json

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def create_test_config():
    """Create a test config.json file"""
    config = {
        "mongodb_uri": "mongodb://localhost:27017/",
        "telegram": {
            "telegram_main": {
                "bot_token": "test_token",
                "chat_id": "test_chat_id"
            }
        },
        "scraping": {
            "timeout": 30,
            "delay_between_requests": 1
        }
    }
    return config

def test_github_actions_simulation():
    """Simulate GitHub Actions environment and test config loading"""
    print("🧪 Testing GitHub Actions Config Loading")
    print("=" * 50)
    
    # Create a temporary directory structure similar to GitHub Actions
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the GitHub Actions-like structure
        github_actions_root = os.path.join(temp_dir, "ImmoAgent")
        os.makedirs(github_actions_root)
        
        # Create config.json in the root
        config = create_test_config()
        config_path = os.path.join(github_actions_root, "config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Create Project directory
        project_dir = os.path.join(github_actions_root, "Project")
        os.makedirs(project_dir)
        
        # Create a simple test script in Project directory
        test_script = os.path.join(project_dir, "test_config.py")
        with open(test_script, 'w') as f:
            f.write("""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Application.helpers.utils import load_config

try:
    config = load_config()
    print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
    print(f"✅ Config keys: {list(config.keys())}")
except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)
""")
        
        # Test 1: Run from Project directory (like GitHub Actions)
        print("\n📋 Test 1: Running from Project directory (GitHub Actions style)")
        print(f"Working directory: {project_dir}")
        
        # Change to the Project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            # Import and test
            from Application.helpers.utils import load_config
            config = load_config()
            print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
            print(f"✅ Config keys: {list(config.keys())}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
        finally:
            os.chdir(original_cwd)
        
        # Test 2: Run from root directory
        print("\n📋 Test 2: Running from root directory")
        print(f"Working directory: {github_actions_root}")
        
        os.chdir(github_actions_root)
        
        try:
            from Application.helpers.utils import load_config
            config = load_config()
            print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
            print(f"✅ Config keys: {list(config.keys())}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
        finally:
            os.chdir(original_cwd)
        
        # Test 3: Run from parent directory
        print("\n📋 Test 3: Running from parent directory")
        parent_dir = os.path.dirname(github_actions_root)
        print(f"Working directory: {parent_dir}")
        
        os.chdir(parent_dir)
        
        try:
            from Application.helpers.utils import load_config
            config = load_config()
            print(f"✅ SUCCESS: Loaded config with {len(config)} top-level keys")
            print(f"✅ Config keys: {list(config.keys())}")
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
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def main():
    """Run all tests"""
    success1 = test_github_actions_simulation()
    success2 = test_current_environment()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 