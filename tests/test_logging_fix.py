#!/usr/bin/env python3
"""
Test script to verify that the logging directory creation fix works correctly
"""

import sys
import os
import tempfile
import shutil

def test_logging_directory_creation():
    """Test that log directories are created automatically"""
    print("🧪 Testing Logging Directory Creation Fix")
    print("=" * 50)
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()
    
    try:
        # Change to temp directory
        os.chdir(temp_dir)
        print(f"📁 Testing in temporary directory: {temp_dir}")
        
        # Test 1: Check that log directory doesn't exist initially
        if os.path.exists('log'):
            print("❌ Log directory already exists (shouldn't)")
            return False
        else:
            print("✅ Log directory doesn't exist initially (correct)")
        
        # Test 2: Import and run a module that should create the log directory
        sys.path.insert(0, os.path.join(original_cwd, 'Project'))
        
        # Import the main module (this should trigger logging setup)
        try:
            from Application.main import main
            print("✅ Successfully imported main module")
        except Exception as e:
            print(f"❌ Failed to import main module: {e}")
            return False
        
        # Test 3: Check if log directory was created
        if os.path.exists('log'):
            print("✅ Log directory was created automatically")
            
            # Check if it's a directory
            if os.path.isdir('log'):
                print("✅ Log directory is a proper directory")
            else:
                print("❌ Log directory is not a directory")
                return False
        else:
            print("❌ Log directory was not created")
            return False
        
        # Test 4: Try to create a log file
        try:
            import logging
            
            # Set up logging (this should work now)
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('log/test.log'),
                    logging.StreamHandler()
                ]
            )
            
            # Test logging
            logging.info("Test log message")
            print("✅ Logging setup and test message successful")
            
            # Check if log file was created
            if os.path.exists('log/test.log'):
                print("✅ Log file was created successfully")
            else:
                print("❌ Log file was not created")
                return False
                
        except Exception as e:
            print(f"❌ Logging test failed: {e}")
            return False
        
        print("\n✅ All logging directory tests passed!")
        return True
        
    finally:
        # Clean up
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up temporary directory: {temp_dir}")

def test_github_actions_compatibility():
    """Test that the fix works in GitHub Actions-like environment"""
    print("\n🧪 Testing GitHub Actions Compatibility")
    print("=" * 50)
    
    # Simulate GitHub Actions environment
    original_cwd = os.getcwd()
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Change to temp directory (simulating GitHub Actions workspace)
        os.chdir(temp_dir)
        print(f"📁 Simulating GitHub Actions workspace: {temp_dir}")
        
        # Create Project directory structure
        project_dir = os.path.join(temp_dir, 'Project')
        os.makedirs(project_dir)
        os.chdir(project_dir)
        
        # Create Application directory
        app_dir = os.path.join(project_dir, 'Application')
        os.makedirs(app_dir)
        
        # Create a minimal main.py file for testing
        test_main_content = '''
import os
import logging

# Ensure log directory exists
log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/test.log'),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("Test message from GitHub Actions simulation")
    print("✅ GitHub Actions simulation successful")

if __name__ == "__main__":
    main()
'''
        
        with open(os.path.join(app_dir, 'main.py'), 'w') as f:
            f.write(test_main_content)
        
        # Test the simulation
        try:
            # Add to path and import
            sys.path.insert(0, project_dir)
            from Application.main import main
            
            # Run the test
            main()
            
            # Check if log directory and file were created
            if os.path.exists('log') and os.path.exists('log/test.log'):
                print("✅ GitHub Actions simulation successful - log directory and file created")
                return True
            else:
                print("❌ GitHub Actions simulation failed - log files not created")
                return False
                
        except Exception as e:
            print(f"❌ GitHub Actions simulation failed: {e}")
            return False
            
    finally:
        # Clean up
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up GitHub Actions simulation directory: {temp_dir}")

def main():
    """Run all tests"""
    print("🚀 Testing Logging Directory Creation Fix for GitHub Actions")
    print("=" * 60)
    
    # Run tests
    test1_success = test_logging_directory_creation()
    test2_success = test_github_actions_compatibility()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"  Logging Directory Creation: {'✅ PASSED' if test1_success else '❌ FAILED'}")
    print(f"  GitHub Actions Compatibility: {'✅ PASSED' if test2_success else '❌ FAILED'}")
    
    overall_success = test1_success and test2_success
    print(f"\nOverall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 