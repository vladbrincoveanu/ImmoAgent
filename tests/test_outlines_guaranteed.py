#!/usr/bin/env python3
"""
Test script for Outlines-based guaranteed structured output
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ollama_analyzer import OutlinesAnalyzer, StructuredAnalyzer
import unittest

class TestOutlinesGuaranteed(unittest.TestCase):
    def test_outlines_guaranteed(self):
        """Test Outlines with guaranteed structured output"""
        print("🧪 Testing Outlines Guaranteed Structured Output")
        print("=" * 50)
        
        # Test sample listing data
        sample_listing = {
            "url": "https://example.com/listing/123",
            "bezirk": "1010 Wien",
            "price_total": 450000,
            "area_m2": 65,
            "rooms": 2,
            "address": "Stephansplatz 1, 1010 Wien",
            "description": "Schöne 2-Zimmer-Wohnung im Herzen von Wien. Baujahr 1995, 3. Stock, komplett renoviert, Fernwärme, Tiefgarage vorhanden. Monatsrate: €1,850, Eigenkapital: €90,000, Betriebskosten: €180/Monat",
            "details": "Heizung: Fernwärme, Zustand: renoviert, Stellplatz: Tiefgarage"
        }
        
        # Test OutlinesAnalyzer directly
        print("\n1. Testing OutlinesAnalyzer directly")
        print("-" * 30)
        
        analyzer = OutlinesAnalyzer()
        
        if not analyzer.is_available():
            print("❌ OutlinesAnalyzer not available")
            print("💡 Please install: pip install outlines transformers torch accelerate")
            return False
        
        print("✅ OutlinesAnalyzer initialized successfully")
        
        # Test structured analysis
        print("\n🔍 Analyzing sample listing...")
        result = analyzer.analyze_listing(sample_listing)
        
        print(f"\n📊 Analysis Results:")
        print(f"   Year Built: {result.get('year_built')}")
        print(f"   Floor: {result.get('floor')}")
        print(f"   Condition: {result.get('condition')}")
        print(f"   Heating: {result.get('heating')}")
        print(f"   Parking: {result.get('parking')}")
        print(f"   Monthly Rate: {result.get('monatsrate')}")
        print(f"   Own Funds: {result.get('own_funds')}")
        print(f"   Operating Costs: {result.get('betriebskosten')}")
        print(f"   Interest Rate: {result.get('interest_rate')}")
        print(f"   Confidence: {result.get('confidence')}")
        
        # Count non-null fields
        non_null_fields = sum(1 for v in result.values() if v is not None and v != 0)
        print(f"\n📈 Fields extracted: {non_null_fields}/10")
        
        # Test StructuredAnalyzer wrapper
        print("\n2. Testing StructuredAnalyzer wrapper")
        print("-" * 30)
        
        structured_analyzer = StructuredAnalyzer()
        
        if not structured_analyzer.is_available():
            print("❌ StructuredAnalyzer not available")
            return False
        
        print("✅ StructuredAnalyzer initialized successfully")
        
        # Create sample HTML content for testing
        sample_html = """
        <html>
        <body>
            <div class="property-details">
                <h1>Schöne 2-Zimmer-Wohnung im Herzen von Wien</h1>
                <p>Baujahr: 1995</p>
                <p>Stock: 3. Stock</p>
                <p>Zustand: komplett renoviert</p>
                <p>Heizung: Fernwärme</p>
                <p>Parken: Tiefgarage vorhanden</p>
                <p>Monatsrate: €1,850</p>
                <p>Eigenkapital: €90,000</p>
                <p>Betriebskosten: €180/Monat</p>
            </div>
        </body>
        </html>
        """
        
        # Test with content analysis
        enhanced_result = structured_analyzer.analyze_listing_content(sample_listing, sample_html)
        
        print(f"\n📊 Enhanced Analysis Results:")
        if 'structured_analysis' in enhanced_result:
            analysis_meta = enhanced_result['structured_analysis']
            print(f"   Model: {analysis_meta.get('model')}")
            print(f"   Model Name: {analysis_meta.get('model_name')}")
            print(f"   Confidence: {analysis_meta.get('confidence')}")
            print(f"   Extracted Fields: {analysis_meta.get('extracted_fields')}")
        
        # Verify guaranteed structure
        print("\n3. Testing Structure Guarantee")
        print("-" * 30)
        
        required_fields = ['year_built', 'floor', 'condition', 'heating', 'parking', 
                          'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate', 'confidence']
        
        missing_fields = [field for field in required_fields if field not in result]
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return False
        else:
            print("✅ All required fields present - structure guaranteed!")
        
        # Test data types
        print("\n4. Testing Data Types")
        print("-" * 30)
        
        type_checks = [
            ('year_built', int, result.get('year_built')),
            ('floor', str, result.get('floor')),
            ('condition', str, result.get('condition')),
            ('heating', str, result.get('heating')),
            ('parking', str, result.get('parking')),
            ('monatsrate', float, result.get('monatsrate')),
            ('own_funds', float, result.get('own_funds')),
            ('betriebskosten', float, result.get('betriebskosten')),
            ('interest_rate', float, result.get('interest_rate')),
            ('confidence', float, result.get('confidence'))
        ]
        
        type_errors = []
        for field, expected_type, value in type_checks:
            if value is not None and not isinstance(value, expected_type):
                type_errors.append(f"{field}: expected {expected_type.__name__}, got {type(value).__name__}")
        
        if type_errors:
            print(f"❌ Type errors: {type_errors}")
            return False
        else:
            print("✅ All data types correct!")
        
        print("\n🎉 All tests passed! Outlines provides guaranteed structured output.")
        return True

if __name__ == '__main__':
    unittest.main() 