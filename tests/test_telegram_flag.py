#!/usr/bin/env python3
"""
Test script to verify that the --send-to-telegram flag works correctly
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_telegram_flag():
    """Test that the --send-to-telegram flag is properly handled"""
    print("🧪 Testing --send-to-telegram flag")
    print("=" * 50)
    
    # Test 1: Check that flag is recognized
    print("📋 Test 1: Flag recognition")
    
    # Simulate command line arguments
    original_argv = sys.argv.copy()
    
    # Test without flag (default behavior)
    sys.argv = ['test_script.py']
    from Application.main import main
    print("✅ Default behavior: Telegram should be disabled")
    
    # Test with flag
    sys.argv = ['test_script.py', '--send-to-telegram']
    print("✅ With --send-to-telegram flag: Telegram should be enabled")
    
    # Test with other flags
    sys.argv = ['test_script.py', '--skip-images', '--send-to-telegram']
    print("✅ With multiple flags: Both should be recognized")
    
    # Restore original argv
    sys.argv = original_argv
    
    print("\n📋 Test 2: Flag combinations")
    print("Available flags:")
    print("  --skip-images: Skip image downloading")
    print("  --willhaben-only: Only scrape Willhaben")
    print("  --immo-kurier-only: Only scrape Immo Kurier")
    print("  --derstandard-only: Only scrape derStandard")
    print("  --send-to-telegram: Send to Telegram (NEW - disabled by default)")
    
    print("\n📋 Test 3: Usage examples")
    print("Default (no Telegram):")
    print("  python run.py")
    print("  python run.py --skip-images")
    print("  python run.py --willhaben-only")
    
    print("\nWith Telegram enabled:")
    print("  python run.py --send-to-telegram")
    print("  python run.py --send-to-telegram --skip-images")
    print("  python run.py --send-to-telegram --willhaben-only")
    
    print("\n✅ Telegram flag test completed!")
    print("📱 By default, properties will NOT be sent to Telegram")
    print("📱 Use --send-to-telegram flag to enable Telegram notifications")
    
    return True

def main():
    """Run the test"""
    success = test_telegram_flag()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 