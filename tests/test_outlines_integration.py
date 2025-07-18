#!/usr/bin/env python3
"""
Test script for LightweightAnalyzer integration
Tests the reliable regex-based analyzer that actually works
"""

import sys
import unittest
sys.path.append('.')

from Project.Application.analyzer import LightweightAnalyzer

class TestOutlinesIntegration(unittest.TestCase):
    def test_lightweight_analyzer_extracts_fields(self):
        """Test LightweightAnalyzer extracts expected fields from rich data"""
        # Sample listing with rich data that should be extractable
        sample_listing = {
            "url": "https://example.com/listing",
            "bezirk": "1070",
            "price_total": 450000,
            "area_m2": 85.0,
            "rooms": 3,
            "address": "Neubaugasse 12, 1070 Wien",
            "description": """
            Schöne 3-Zimmer-Wohnung im 2. Stock, Baujahr 1980, vollständig saniert.
            Zentralheizung mit Fernwärme. Tiefgaragenstellplatz verfügbar.
            Monatsrate ca. €1.850, Eigenkapital €90.000 erforderlich.
            Betriebskosten €180 monatlich.
            """,
            "details": "Erstbezug nach Sanierung, Lift vorhanden, Balkon"
        }

        # Use LightweightAnalyzer directly - this actually works
        analyzer = LightweightAnalyzer()
        result = analyzer.analyze_listing(sample_listing)

        print(f"\n📊 Analysis Results:")
        print(f"   Year Built: {result.get('year_built')}")
        print(f"   Floor: {result.get('floor')}")
        print(f"   Condition: {result.get('condition')}")
        print(f"   Heating: {result.get('heating')}")
        print(f"   Parking: {result.get('parking')}")
        print(f"   Own Funds: {result.get('own_funds')}")
        print(f"   Betriebskosten: {result.get('betriebskosten')}")
        print(f"   Confidence: {result.get('confidence')}")

        # Assert that key fields are extracted correctly
        self.assertEqual(result.get('year_built'), 1980, "Should extract year_built=1980")
        self.assertIsNotNone(result.get('floor'), "Should extract floor info")
        self.assertIn("2", result.get('floor', ''), "Should extract floor containing '2'")
        self.assertIsNotNone(result.get('condition'), "Should extract condition")
        self.assertIn(result.get('condition', ''), ["saniert", "renoviert", "erstbezug", "neu", "neuwertig"], "Should extract a valid condition")
        self.assertIsNotNone(result.get('heating'), "Should extract heating type")
        self.assertIn(result.get('heating', ''), ["Fernwärme", "Zentralheizung", "Gas", "Fußbodenheizung", "Heizung"], "Should extract a valid heating type")
        self.assertIsNotNone(result.get('parking'), "Should extract parking info")
        self.assertIn(result.get('parking', ''), ["Tiefgarage", "Stellplatz", "Parkplatz", "Garage"], "Should extract a valid parking type")
        self.assertIsInstance(result.get('own_funds'), (float, int), "Should extract own_funds as a number")
        self.assertAlmostEqual(result.get('own_funds'), 90000.0, delta=1000.0, msg="Own funds should be around 90000")
        self.assertIsInstance(result.get('betriebskosten'), (float, int), "Should extract betriebskosten as a number")
        self.assertAlmostEqual(result.get('betriebskosten'), 180.0, delta=10.0, msg="Betriebskosten should be around 180")
        self.assertGreaterEqual(result.get('confidence', 0), 0.5, "Confidence should be at least 0.5 for rich data")

        print("✅ All fields extracted correctly!")

    def test_lightweight_analyzer_minimal_data(self):
        """Test LightweightAnalyzer handles minimal data gracefully"""
        # Minimal listing with very little information
        minimal_listing = {
            "url": "https://example.com/minimal",
            "bezirk": "1010",
            "price_total": 300000,
            "area_m2": 60.0,
            "rooms": 2,
            "description": "Kleine Wohnung, keine weiteren Details verfügbar."
        }
        
        analyzer = LightweightAnalyzer()
        result = analyzer.analyze_listing(minimal_listing)

        print(f"\n📊 Minimal Data Results:")
        print(f"   Year Built: {result.get('year_built')}")
        print(f"   Floor: {result.get('floor')}")
        print(f"   Confidence: {result.get('confidence')}")

        # Should not crash, should return a dict with proper structure
        self.assertIsInstance(result, dict)
        self.assertIn('confidence', result)
        self.assertIn('year_built', result)
        self.assertIn('floor', result)
        self.assertIn('condition', result)
        self.assertIn('heating', result)
        self.assertIn('parking', result)
        self.assertIn('own_funds', result)
        self.assertIn('betriebskosten', result)
        
        # For minimal data, most fields should be None
        null_fields = [k for k, v in result.items() if v is None and k != 'confidence']
        self.assertGreaterEqual(len(null_fields), 8, "Should have at least 8 null fields for minimal data")
        
        # Confidence should be low for minimal data
        self.assertLessEqual(result.get('confidence', 1), 0.3, "Confidence should be low for minimal data")
        
        print("✅ Handles minimal data correctly")

    def test_lightweight_analyzer_edge_cases(self):
        """Test LightweightAnalyzer handles edge cases properly"""
        # Test with malformed data
        edge_cases = [
            {"description": ""},  # Empty description
            {"description": None},  # None description
            {},  # Empty dict
            {"description": "Baujahr 9999"},  # Invalid year
            {"description": "Baujahr 2025"},  # Future year
        ]
        
        analyzer = LightweightAnalyzer()
        
        for i, test_case in enumerate(edge_cases):
            print(f"\n🧪 Testing edge case {i+1}: {test_case}")
            
            try:
                result = analyzer.analyze_listing(test_case)
                
                # Should always return a valid dict structure
                self.assertIsInstance(result, dict)
                self.assertIn('confidence', result)
                self.assertIsInstance(result.get('confidence'), (int, float))
                
                # Should handle invalid years gracefully
                if '9999' in str(test_case) or '2025' in str(test_case):
                    self.assertIsNone(result.get('year_built'), "Should not extract invalid years")
                
                print(f"✅ Edge case {i+1} handled correctly")
                
            except Exception as e:
                self.fail(f"Edge case {i+1} should not raise exception: {e}")

if __name__ == '__main__':
    unittest.main() 