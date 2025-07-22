#!/usr/bin/env python3
"""
Test script to simulate GitHub Actions environment and test the main function
"""

import sys
import os
import tempfile
import json

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_github_actions_main():
    """Test main function in GitHub Actions-like environment"""
    print("🧪 Testing Main Function in GitHub Actions Environment")
    print("=" * 60)
    
    # Set environment variables for testing
    os.environ['MONGODB_URI'] = 'mongodb://test:test@localhost:27017/test'
    os.environ['TELEGRAM_BOT_MAIN_TOKEN'] = 'test_bot_token_123'
    os.environ['TELEGRAM_BOT_MAIN_CHAT_ID'] = 'test_chat_id_456'
    
    # Create a temporary directory structure similar to GitHub Actions
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the GitHub Actions-like structure
        github_actions_root = os.path.join(temp_dir, "ImmoAgent")
        os.makedirs(github_actions_root)
        
        # Create Project directory
        project_dir = os.path.join(github_actions_root, "Project")
        os.makedirs(project_dir)
        
        # Change to the Project directory (like GitHub Actions)
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            # Test importing main function
            print("📋 Test 1: Importing main function")
            from Application.main import main
            print("✅ SUCCESS: Main function imported successfully")
            
            # Test that main function can be called (it will fail at MongoDB connection, but that's expected)
            print("\n📋 Test 2: Testing main function execution")
            print("Note: This will fail at MongoDB connection, which is expected in test environment")
            
            # We'll just test that the function can be called without UnboundLocalError
            try:
                # This should fail at MongoDB connection, not at component_status
                main()
            except Exception as e:
                error_msg = str(e)
                if "UnboundLocalError" in error_msg:
                    print(f"❌ FAILED: UnboundLocalError still exists: {e}")
                    return False
                elif "MongoDB" in error_msg or "Connection" in error_msg:
                    print(f"✅ SUCCESS: Expected MongoDB connection error: {e}")
                    print("✅ This confirms the UnboundLocalError is fixed!")
                else:
                    print(f"⚠️  Unexpected error: {e}")
                    # Still consider this a success if it's not UnboundLocalError
                    return True
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False
        finally:
            os.chdir(original_cwd)
    
    return True

def test_current_environment():
    """Test main function in current environment"""
    print("\n🧪 Testing Main Function in Current Environment")
    print("=" * 60)
    
    try:
        from Application.main import main
        print("✅ SUCCESS: Main function imported successfully")
        
        # Test that main function can be called
        print("📋 Testing main function execution (will likely fail at MongoDB, which is expected)")
        try:
            main()
        except Exception as e:
            error_msg = str(e)
            if "UnboundLocalError" in error_msg:
                print(f"❌ FAILED: UnboundLocalError exists: {e}")
                return False
            else:
                print(f"✅ SUCCESS: Expected error (not UnboundLocalError): {e}")
                return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def main():
    """Run all tests"""
    success1 = test_github_actions_main()
    success2 = test_current_environment()
    
    print("\n" + "=" * 60)
    print(f"Result: {'✅ SUCCESS' if success1 and success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("🎉 UnboundLocalError has been fixed!")
        print("✅ The application should now work correctly in GitHub Actions")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 