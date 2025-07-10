#!/usr/bin/env python3
"""
Test script for Instructor integration with Ollama
Tests the new structured output capabilities
"""

import sys
sys.path.append('.')

from ollama_analyzer import OllamaAnalyzer, RealEstateData, OUTLINES_AVAILABLE
import json
import unittest

try:
    import outlines # type: ignore
    import transformers # type: ignore
except ImportError:
    outlines = None
    transformers = None

class TestOutlinesIntegration(unittest.TestCase):
    def test_outlines_integration(self):
        """Test Outlines integration with sample real estate data"""
        print("🧪 TESTING OUTLINES INTEGRATION WITH OLLAMA")
        print("=" * 60)
        
        # Check if Outlines is available
        print(f"📦 Outlines Available: {'✅ YES' if OUTLINES_AVAILABLE else '❌ NO'}")
        
        # Sample listing data
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
        
        # Initialize analyzer
        print("\n🔧 Initializing OllamaAnalyzer...")
        analyzer = OllamaAnalyzer(model_name="microsoft/DialoGPT-medium")
        
        # Test analysis
        print("\n🔍 Testing structured analysis...")
        result = analyzer.analyze_listing(sample_listing)
        
        print("\n📊 ANALYSIS RESULTS:")
        print("=" * 40)
        print(f"Year Built: {result.get('year_built')}")
        print(f"Floor: {result.get('floor')}")
        print(f"Condition: {result.get('condition')}")
        print(f"Heating: {result.get('heating')}")
        print(f"Parking: {result.get('parking')}")
        print(f"Monthly Rate: €{result.get('monatsrate')}")
        print(f"Own Funds: €{result.get('own_funds')}")
        print(f"Operating Costs: €{result.get('betriebskosten')}")
        print(f"Confidence: {result.get('confidence')}")
        
        # Test with minimal data
        print("\n" + "=" * 60)
        print("🧪 TESTING WITH MINIMAL DATA")
        print("=" * 60)
        
        minimal_listing = {
            "url": "https://example.com/minimal",
            "bezirk": "1010",
            "price_total": 300000,
            "area_m2": 60.0,
            "rooms": 2,
            "description": "Kleine Wohnung, keine weiteren Details verfügbar."
        }
        
        minimal_result = analyzer.analyze_listing(minimal_listing)
        print(f"Minimal data confidence: {minimal_result.get('confidence')}")
        print(f"Extracted fields: {[k for k, v in minimal_result.items() if v is not None and k not in ['url', 'bezirk', 'price_total', 'area_m2', 'rooms']]}")

    def test_outlines_direct(self):
        """Test Outlines directly if available"""
        if not OUTLINES_AVAILABLE or not outlines or not transformers:
            print("=" * 60)
            print("⚠️ Outlines not available, skipping direct test.")
            print("💡 To enable, run: pip install outlines transformers torch accelerate")
            print("=" * 60)
            return

        try:
            
            # Initialize client using correct API
            print("🔧 Initializing Outlines client...")
            model = outlines.models.transformers("microsoft/DialoGPT-medium")
            
            # Test prompt
            prompt = """Extract real estate data from this text:
            
            Diese schöne 3-Zimmer-Wohnung befindet sich im 3. Stock eines Gebäudes aus dem Jahr 1995.
            Die Wohnung wurde vollständig renoviert und verfügt über Zentralheizung.
            Ein Tiefgaragenstellplatz ist verfügbar.
            Monatsrate: €1.200, Eigenkapital: €50.000, Betriebskosten: €120/Monat
            """
            
            print("📤 Sending request to Ollama via Outlines...")
            
            # Get structured response
            generator = outlines.generate.json(model, RealEstateData)
            response = generator(prompt, max_tokens=500)
            
            print("✅ Direct Outlines test successful!")
            print(f"📊 Result: {response}")
            
        except Exception as e:
            print(f"❌ Direct Outlines test failed: {e}")
            print("💡 Make sure Ollama is running with OpenAI compatibility enabled")

if __name__ == '__main__':
    unittest.main() 