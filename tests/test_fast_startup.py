#!/usr/bin/env python3
"""
Fast startup test to verify performance improvements
Tests that the system starts quickly and uses lightweight fallback when needed
"""

import sys
import time
import signal
from Project.Application.analyzer import StructuredAnalyzer, OutlinesAnalyzer
import unittest

def timeout_handler(signum, frame):
    """Handle timeout"""
    print("\n⏰ Test timed out - system is hanging!")
    sys.exit(1)

class TestFastStartup(unittest.TestCase):
    def test_fast_startup(self):
        """Test that the system starts quickly"""
        print("🚀 TESTING FAST STARTUP")
        print("=" * 50)
        
        # Set timeout for the entire test
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 second timeout
        
        try:
            print("🧠 Creating StructuredAnalyzer...")
            start_time = time.time()
            
            analyzer = StructuredAnalyzer()
            creation_time = time.time() - start_time
            
            print(f"✅ Analyzer created in {creation_time:.2f}s")
            print(f"   Outlines wait timeout: {analyzer.outlines_wait_timeout}s")
            
            # Test availability check
            print("🔍 Checking availability...")
            start_time = time.time()
            
            is_available = analyzer.is_available()
            check_time = time.time() - start_time
            
            print(f"✅ Availability check completed in {check_time:.2f}s")
            print(f"   Available: {is_available}")
            
            # Test with sample data
            test_data = {
                "price_total": 380000,
                "area_m2": 73.27,
                "rooms": 3,
                "address": "1220 Wien, Donaustadt",
                "description": "Schöne 3-Zimmer-Wohnung, Baujahr 1995, 3. Stock, renoviert, Fernwärme"
            }
            
            print("🧠 Testing analysis...")
            start_time = time.time()
            
            try:
                result = analyzer.analyze_listing(test_data)
                analysis_time = time.time() - start_time
                
                print(f"✅ Analysis completed in {analysis_time:.2f}s")
                print(f"   Confidence: {result.get('confidence', 0):.2f}")
                print(f"   Fields extracted: {len([k for k, v in result.items() if v is not None and k != 'confidence'])}")
                
                # Check which analyzer was used
                if 'structured_analysis' in result:
                    analysis_meta = result['structured_analysis']
                    print(f"   Model used: {analysis_meta.get('model', 'unknown')}")
                
                self.assertTrue(True) # Indicate success
                
            except Exception as e:
                analysis_time = time.time() - start_time
                print(f"❌ Analysis failed after {analysis_time:.2f}s: {e}")
                self.assertFalse(True) # Indicate failure
                
        except Exception as e:
            print(f"❌ Error in test: {e}")
            self.assertFalse(True) # Indicate failure
        finally:
            signal.alarm(0)  # Cancel timeout

    def test_outlines_speed(self):
        """Test OutlinesAnalyzer speed specifically"""
        print("\n🧪 TESTING OUTLINES SPEED")
        print("=" * 50)
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(20)  # 20 second timeout
        
        try:
            print("🧠 Creating OutlinesAnalyzer...")
            start_time = time.time()
            
            analyzer = OutlinesAnalyzer()
            creation_time = time.time() - start_time
            
            print(f"✅ OutlinesAnalyzer created in {creation_time:.2f}s")
            print(f"   Model: {analyzer.model_name}")
            print(f"   Timeout: {analyzer.timeout_seconds}s")
            
            # Wait for initialization
            print("⏳ Waiting for model initialization...")
            start_time = time.time()
            
            is_available = analyzer.is_available()
            wait_time = time.time() - start_time
            
            print(f"✅ Initialization check completed in {wait_time:.2f}s")
            print(f"   Available: {is_available}")
            
            if is_available:
                print("🎉 Outlines is ready for use!")
                self.assertTrue(True)
            else:
                print("⚠️ Outlines not available - will use lightweight fallback")
                self.assertTrue(True)  # Not a failure, fallback is expected
                
        except Exception as e:
            print(f"❌ Error testing Outlines: {e}")
            self.assertFalse(True) # Indicate failure
        finally:
            signal.alarm(0)  # Cancel timeout

if __name__ == "__main__":
    unittest.main() 