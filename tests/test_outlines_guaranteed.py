#!/usr/bin/env python3
"""
Test script for Lightweight Analyzer guaranteed structured output
"""

import sys
import os
import time
import threading
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Project.Application.analyzer import LightweightAnalyzer, OUTLINES_AVAILABLE
import unittest

class TestOutlinesGuaranteed(unittest.TestCase):
    def test_outlines_guaranteed(self):
        """Test LightweightAnalyzer with guaranteed structured output"""
        print("🧪 Testing Lightweight Analyzer Guaranteed Structured Output")
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
        
        # Test LightweightAnalyzer directly - simplified approach
        print("\n1. Testing LightweightAnalyzer directly")
        print("-" * 30)
        
        try:
            # Create analyzer directly without threading
            analyzer = LightweightAnalyzer()
            print("✅ LightweightAnalyzer initialized successfully")
            
            # Run analysis directly
            print("\n🔍 Analyzing sample listing...")
            result = analyzer.analyze_listing(sample_listing)
            
            print(f"\n📊 Analysis Results:")
            print(f"   Year Built: {result.get('year_built')}")
            print(f"   Floor: {result.get('floor')}")
            print(f"   Condition: {result.get('condition')}")
            print(f"   Heating: {result.get('heating')}")
            print(f"   Parking: {result.get('parking')}")
            print(f"   Monatsrate: {result.get('monatsrate')}")
            print(f"   Own Funds: {result.get('own_funds')}")
            print(f"   Betriebskosten: {result.get('betriebskosten')}")
            
            # Validate results with more flexible assertions
            print("\nVALIDATING RESULTS:")
            
            # Test that year_built is extracted (should be 1995)
            self.assertEqual(result.get('year_built'), 1995, "Year built should be 1995")
            
            # Test that floor is extracted (should contain "3. Stock")
            self.assertIsNotNone(result.get('floor'), "Floor should be extracted")
            self.assertIn("3", result.get('floor', ''), "Floor should contain '3'")
            
            # Test that condition is extracted (should contain "renoviert")
            self.assertIsNotNone(result.get('condition'), "Condition should be extracted")
            self.assertIn("renoviert", result.get('condition', ''), "Condition should contain 'renoviert'")
            
            # Test that heating is extracted (should contain "Fernwärme")
            self.assertIsNotNone(result.get('heating'), "Heating should be extracted")
            self.assertIn("Fernwärme", result.get('heating', ''), "Heating should contain 'Fernwärme'")
            
            # Test that parking is extracted (should contain "Tiefgarage")
            self.assertIsNotNone(result.get('parking'), "Parking should be extracted")
            self.assertIn("Tiefgarage", result.get('parking', ''), "Parking should contain 'Tiefgarage'")
            
            # Test that own_funds is extracted (should be around 90000)
            self.assertIsNotNone(result.get('own_funds'), "Own funds should be extracted")
            self.assertAlmostEqual(result.get('own_funds'), 90000.0, delta=1000.0, msg="Own funds should be around 90000")
            
            # Test that betriebskosten is extracted (should be around 180)
            self.assertIsNotNone(result.get('betriebskosten'), "Betriebskosten should be extracted")
            self.assertAlmostEqual(result.get('betriebskosten'), 180.0, delta=10.0, msg="Betriebskosten should be around 180")
            
            print("✅ All fields extracted correctly!")

            # Test with HTML content
            print("\n2. Testing with HTML content")
            print("-" * 30)
            
            html_content = f"""
            <html><body>
            <h1>Wohnung in Wien</h1>
            <p>Beschreibung: {sample_listing['description']}</p>
            <ul>
                <li>Baujahr: 1995</li>
                <li>Stock: 3. Stock</li>
                <li>Zustand: renoviert</li>
                <li>Heizung: Fernwärme</li>
                <li>Parken: Tiefgarage</li>
            </ul>
            </body></html>
            """
            
            result_html = analyzer.analyze_listing_content(sample_listing, html_content)
            
            print("\n📊 HTML Analysis Results:")
            print(f"   Year Built: {result_html.get('year_built')}")
            print(f"   Floor: {result_html.get('floor')}")
            
            # Validate HTML results
            self.assertEqual(result_html.get('year_built'), 1995, "HTML year built should be 1995")
            self.assertIsNotNone(result_html.get('floor'), "HTML floor should be extracted")
            self.assertIn("3", result_html.get('floor', ''), "HTML floor should contain '3'")
            print("✅ HTML fields extracted correctly!")
            
            # Test empty/null data
            print("\n3. Testing with empty data")
            print("-" * 30)
            
            empty_listing = {"description": "Leere Beschreibung"}
            result_empty = analyzer.analyze_listing(empty_listing)
            
            print("\n📊 Empty Analysis Results:")
            null_fields = [k for k, v in result_empty.items() if v is None and k != 'confidence']
            print(f"   Null fields: {len(null_fields)}")
            self.assertTrue(len(null_fields) >= 8, "Should have at least 8 null fields for empty data")
            print("✅ Handles empty data correctly")
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.fail(f"Test failed with exception: {e}")

if __name__ == '__main__':
    unittest.main() 