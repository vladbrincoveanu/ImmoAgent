#!/usr/bin/env python3
"""
Debug script to help troubleshoot config loading issues
"""

import os
import sys

def debug_environment():
    """Debug the current environment and config loading"""
    print("🔍 Environment Debug Information")
    print("=" * 50)
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Script location: {os.path.abspath(__file__)}")
    
    # List files in current directory
    print(f"\n📁 Files in current directory:")
    try:
        for item in os.listdir('.'):
            if os.path.isfile(item):
                print(f"   📄 {item}")
            elif os.path.isdir(item):
                print(f"   📁 {item}/")
    except Exception as e:
        print(f"   ❌ Error listing directory: {e}")
    
    # Check for config.json in various locations
    print(f"\n🔍 Looking for config.json:")
    possible_paths = [
        'config.json',
        '../config.json',
        '../../config.json',
        'Project/config.json',
        '../Project/config.json',
        '/home/runner/work/ImmoAgent/ImmoAgent/config.json',
        '/home/runner/work/ImmoAgent/ImmoAgent/Project/config.json',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"   ✅ Found: {path}")
            try:
                with open(path, 'r') as f:
                    content = f.read(200)  # Read first 200 chars
                    print(f"      Content preview: {content[:100]}...")
            except Exception as e:
                print(f"      ❌ Error reading: {e}")
        else:
            print(f"   ❌ Not found: {path}")
    
    # Try to load config
    print(f"\n🔧 Testing config loading:")
    try:
        from Application.helpers.utils import load_config
        config = load_config()
        print(f"   ✅ SUCCESS: Loaded config with {len(config)} keys")
        print(f"   📋 Config keys: {list(config.keys())}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_environment() 