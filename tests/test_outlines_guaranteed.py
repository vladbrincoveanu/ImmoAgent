#!/usr/bin/env python3
"""
Test script for Outlines-based guaranteed structured output
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ollama_analyzer import LightweightAnalyzer, OUTLINES_AVAILABLE
import unittest
import signal

def timeout_handler(signum, frame):
    """Handle timeout"""
    raise TimeoutError("Test timed out")

class TestOutlinesGuaranteed(unittest.TestCase):
    def test_outlines_guaranteed(self):
        """Test Outlines with guaranteed structured output"""
        print("🧪 Testing Lightweight Analyzer Guaranteed Structured Output")
        print("=" * 50)
        
        # Set a longer timeout for this test
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)  # 15 second timeout
        
        try:
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
            
            # Test LightweightAnalyzer directly
            print("\n1. Testing LightweightAnalyzer directly")
            print("-" * 30)
            
            analyzer = LightweightAnalyzer()
            
            print("✅ LightweightAnalyzer initialized successfully")
            
            # Test structured analysis
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
            
            # Validate results
            print("\nVALIDATING RESULTS:")
            self.assertEqual(result.get('year_built'), 1995)
            self.assertEqual(result.get('floor'), '3. Stock')
            self.assertEqual(result.get('condition'), 'renoviert')
            self.assertEqual(result.get('heating'), 'Fernwärme')
            self.assertEqual(result.get('parking'), 'Tiefgarage')
            self.assertEqual(result.get('monatsrate'), 1850.0)
            self.assertEqual(result.get('own_funds'), 90000.0)
            self.assertEqual(result.get('betriebskosten'), 180.0)
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
            self.assertEqual(result_html.get('year_built'), 1995)
            self.assertEqual(result_html.get('floor'), '3. Stock')
            print("✅ HTML fields extracted correctly!")
            
            # Test empty/null data
            print("\n3. Testing with empty data")
            print("-" * 30)
            
            empty_listing = {"description": "Leere Beschreibung"}
            result_empty = analyzer.analyze_listing(empty_listing)
            
            print("\n📊 Empty Analysis Results:")
            null_fields = [k for k, v in result_empty.items() if v is None and k != 'confidence']
            print(f"   Null fields: {len(null_fields)}")
            self.assertTrue(len(null_fields) >= 8)
            print("✅ Handles empty data correctly")
            
        except TimeoutError:
            print("\n❌ TEST TIMED OUT")
            self.fail("Test timed out after 15 seconds")
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            self.fail(f"Test failed with exception: {e}")
        finally:
            signal.alarm(0)  # Disable the alarm

if __name__ == '__main__':
    unittest.main() 