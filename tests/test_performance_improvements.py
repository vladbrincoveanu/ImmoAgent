#!/usr/bin/env python3
"""
Performance test for the improved Outlines analyzer
Tests timeout handling, lazy loading, and fallback mechanisms
"""

import sys
import time
import signal
from ollama_analyzer import OutlinesAnalyzer, StructuredAnalyzer
import unittest

class TestPerformanceImprovements(unittest.TestCase):
    def test_timeout_handling(self):
        """Test that the analyzer handles timeouts gracefully"""
        print("🧪 TESTING TIMEOUT HANDLING")
        print("=" * 50)
        
        # Test with a very short timeout
        analyzer = OutlinesAnalyzer(timeout_seconds=5)
        
        print("⏱️ Testing with 5-second timeout...")
        start_time = time.time()
        
        # Test availability check
        is_available = analyzer.is_available()
        elapsed = time.time() - start_time
        
        print(f"✅ Availability check completed in {elapsed:.2f}s")
        print(f"   Available: {is_available}")
        
        if is_available:
            # Test analysis with timeout
            test_data = {
                "price_total": 380000,
                "area_m2": 73.27,
                "rooms": 3,
                "address": "1220 Wien, Donaustadt"
            }
            
            print("🧠 Testing analysis with timeout...")
            start_time = time.time()
            
            try:
                result = analyzer.analyze_listing(test_data)
                elapsed = time.time() - start_time
                
                print(f"✅ Analysis completed in {elapsed:.2f}s")
                print(f"   Confidence: {result.get('confidence', 0)}")
                print(f"   Extracted fields: {len([k for k, v in result.items() if v is not None and k != 'confidence'])}")
                
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"❌ Analysis failed after {elapsed:.2f}s: {e}")
        
        print()

    def test_lazy_loading(self):
        """Test that model loading is lazy and doesn't block"""
        print("🧪 TESTING LAZY LOADING")
        print("=" * 50)
        
        print("🚀 Creating analyzer (should not block)...")
        start_time = time.time()
        
        analyzer = OutlinesAnalyzer()
        creation_time = time.time() - start_time
        
        print(f"✅ Analyzer created in {creation_time:.2f}s")
        print(f"   Initialization started: {analyzer._initialization_started}")
        print(f"   Initialization complete: {analyzer._initialization_complete.is_set()}")
        
        # Wait a bit for background initialization
        print("⏳ Waiting for background initialization...")
        time.sleep(2)
        
        print(f"   After 2s - Complete: {analyzer._initialization_complete.is_set()}")
        print(f"   Available: {analyzer.is_available()}")
        
        print()

    def test_fallback_mechanism(self):
        """Test that the system falls back gracefully when analysis fails"""
        print("🧪 TESTING FALLBACK MECHANISM")
        print("=" * 50)
        
        analyzer = StructuredAnalyzer()
        
        # Test with minimal data
        test_data = {
            "price_total": 380000,
            "area_m2": 73.27
        }
        
        print("🧠 Testing analysis with minimal data...")
        start_time = time.time()
        
        try:
            result = analyzer.analyze_listing(test_data)
            elapsed = time.time() - start_time
            
            print(f"✅ Analysis completed in {elapsed:.2f}s")
            print(f"   Result type: {type(result)}")
            print(f"   Has confidence: {'confidence' in result}")
            print(f"   Confidence value: {result.get('confidence', 'N/A')}")
            
            # Check that we got a valid result structure
            expected_fields = ['year_built', 'floor', 'condition', 'heating', 'parking', 
                              'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate', 'confidence']
            
            missing_fields = [field for field in expected_fields if field not in result]
            if missing_fields:
                print(f"   ⚠️ Missing fields: {missing_fields}")
            else:
                print(f"   ✅ All expected fields present")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Analysis failed after {elapsed:.2f}s: {e}")
        
        print()

    def test_concurrent_access(self):
        """Test that multiple analyzers can be created without conflicts"""
        print("🧪 TESTING CONCURRENT ACCESS")
        print("=" * 50)
        
        print("🚀 Creating multiple analyzers...")
        analyzers = []
        
        for i in range(3):
            start_time = time.time()
            analyzer = OutlinesAnalyzer()
            creation_time = time.time() - start_time
            analyzers.append(analyzer)
            
            print(f"   Analyzer {i+1}: Created in {creation_time:.2f}s")
        
        # Test availability of all analyzers
        print("🔍 Checking availability of all analyzers...")
        for i, analyzer in enumerate(analyzers):
            is_available = analyzer.is_available()
            print(f"   Analyzer {i+1}: Available = {is_available}")
        
        print()

    def test_memory_usage(self):
        """Test that model caching works and doesn't consume excessive memory"""
        print("🧪 TESTING MEMORY USAGE")
        print("=" * 50)
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"📊 Initial memory usage: {initial_memory:.1f} MB")
        
        # Create multiple analyzers
        analyzers = []
        for i in range(3):
            analyzer = OutlinesAnalyzer()
            analyzers.append(analyzer)
            
            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"   After analyzer {i+1}: {current_memory:.1f} MB")
        
        # Test that they all use the same cached model
        print("🔍 Testing model caching...")
        for i, analyzer in enumerate(analyzers):
            if analyzer.model is not None:
                model_id = id(analyzer.model)
                print(f"   Analyzer {i+1} model ID: {model_id}")
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"📊 Final memory usage: {final_memory:.1f} MB")
        print(f"📊 Memory increase: {memory_increase:.1f} MB")
        
        if memory_increase < 100:  # Should be reasonable
            print("✅ Memory usage is reasonable")
        else:
            print("⚠️ Memory usage seems high")
        
        print()

if __name__ == '__main__':
    unittest.main() 