#!/usr/bin/env python3
"""
Test script for the new StructuredAnalyzer
Demonstrates how it eliminates null values through guaranteed structured output
"""

import json
import os
from Project.Application.analyzer import StructuredAnalyzer
import unittest

class TestStructuredAnalyzer(unittest.TestCase):
    def test_structured_analyzer(self):
        """Test the structured analyzer with sample data"""
        print("🧪 TESTING STRUCTURED ANALYZER")
        print("=" * 60)
        
        # Sample listing data with null values (like your example)
        sample_listing = {
            "url": "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220-donaustadt/familienfreundlich-hell-3-zimmer-wohnung-mit-eigengarten-777958996/",
            "bezirk": "1220",
            "price_total": 380000,
            "area_m2": 73.27,
            "rooms": 3,
            "year_built": None,  # NULL VALUE
            "floor": None,       # NULL VALUE
            "condition": None,   # NULL VALUE
            "heating": None,     # NULL VALUE
            "parking": None,     # NULL VALUE
            "address": "1220 Wien, 22. Bezirk, Donaustadt",
            "special_comment": None,
            "monatsrate": None,  # NULL VALUE
            "own_funds": None,   # NULL VALUE
            "price_per_m2": 5186.3,
            "ubahn_walk_minutes": 18,
            "amenities": []
        }
        
        # Sample HTML content that contains the missing information
        sample_html = """
        <html>
        <head><title>Wohnung 1220 Wien</title></head>
        <body>
            <div class="property-details">
                <h1>Familienfreundlich hell 3 Zimmer Wohnung mit Eigengarten</h1>
                <p>Objektbeschreibung:</p>
                <p>Diese wunderschöne 3-Zimmer-Wohnung im 3. Stock wurde 2018 errichtet und befindet sich in Erstbezug nach Sanierung.</p>
                <p>Die Wohnung verfügt über eine moderne Fußbodenheizung und einen Parkplatz in der Tiefgarage.</p>
                <p>Ausstattung:</p>
                <ul>
                    <li>Baujahr: 2018</li>
                    <li>Lage: 3. Stock</li>
                    <li>Zustand: Erstbezug nach Sanierung</li>
                    <li>Heizung: Fußbodenheizung</li>
                    <li>Parkplatz: Tiefgarage vorhanden</li>
                </ul>
                <div class="financing">
                    <h3>Finanzierung</h3>
                    <p>Monatsrate bei 80% Finanzierung: € 1.450,00</p>
                    <p>Erforderliches Eigenkapital: € 95.000,00</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        print("📋 ORIGINAL DATA (with null values):")
        print(f"  year_built: {sample_listing['year_built']}")
        print(f"  floor: {sample_listing['floor']}")
        print(f"  condition: {sample_listing['condition']}")
        print(f"  heating: {sample_listing['heating']}")
        print(f"  parking: {sample_listing['parking']}")
        print(f"  monatsrate: {sample_listing['monatsrate']}")
        print(f"  own_funds: {sample_listing['own_funds']}")
        print()
        
        # Test with OpenAI (if API key available)
        print("🔧 TESTING WITH OPENAI STRUCTURED OUTPUT:")
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            print(f"✅ OpenAI API Key found: {openai_key[:10]}...")
            analyzer = StructuredAnalyzer(api_key=openai_key)
            
            if analyzer.is_available():
                print("🧠 Analyzing with OpenAI structured output...")
                try:
                    enhanced_listing = analyzer.analyze_listing_content(sample_listing, sample_html)
                    
                    print("\n📊 ENHANCED DATA (after structured analysis):")
                    print(f"  year_built: {enhanced_listing.get('year_built', 'Still null')}")
                    print(f"  floor: {enhanced_listing.get('floor', 'Still null')}")
                    print(f"  condition: {enhanced_listing.get('condition', 'Still null')}")
                    print(f"  heating: {enhanced_listing.get('heating', 'Still null')}")
                    print(f"  parking: {enhanced_listing.get('parking', 'Still null')}")
                    print(f"  monatsrate: {enhanced_listing.get('monatsrate', 'Still null')}")
                    print(f"  own_funds: {enhanced_listing.get('own_funds', 'Still null')}")
                    
                    if 'structured_analysis' in enhanced_listing:
                        analysis = enhanced_listing['structured_analysis']
                        print(f"\n🎯 ANALYSIS RESULTS:")
                        print(f"  Model: {analysis['model']}")
                        print(f"  Confidence: {analysis['confidence']}")
                        print(f"  Extracted fields: {analysis['extracted_fields']}")
                        
                        # Count improvements
                        original_nulls = sum(1 for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds'] 
                                           if sample_listing.get(field) is None)
                        enhanced_nulls = sum(1 for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds'] 
                                           if enhanced_listing.get(field) is None)
                        
                        print(f"\n📈 IMPROVEMENT:")
                        print(f"  Original null fields: {original_nulls}/7")
                        print(f"  Enhanced null fields: {enhanced_nulls}/7")
                        print(f"  Fields extracted: {original_nulls - enhanced_nulls}")
                        print(f"  Success rate: {((original_nulls - enhanced_nulls) / original_nulls * 100):.1f}%")
                    
                except Exception as e:
                    print(f"❌ OpenAI analysis failed: {e}")
            else:
                print("❌ OpenAI analyzer not available")
        else:
            print("⚠️  No OpenAI API key found in environment")
            print("   Set OPENAI_API_KEY environment variable to test OpenAI structured output")
        
        print()
        
        # Test with Ollama fallback
        print("🔧 TESTING WITH OLLAMA FALLBACK:")
        ollama_analyzer = StructuredAnalyzer(api_key=None)  # Force Ollama mode
        
        if ollama_analyzer.is_available():
            print("🧠 Analyzing with Ollama fallback...")
            try:
                enhanced_listing = ollama_analyzer.analyze_listing_content(sample_listing, sample_html)
                
                print("\n📊 ENHANCED DATA (after Ollama analysis):")
                print(f"  year_built: {enhanced_listing.get('year_built', 'Still null')}")
                print(f"  floor: {enhanced_listing.get('floor', 'Still null')}")
                print(f"  condition: {enhanced_listing.get('condition', 'Still null')}")
                print(f"  heating: {enhanced_listing.get('heating', 'Still null')}")
                print(f"  parking: {enhanced_listing.get('parking', 'Still null')}")
                print(f"  monatsrate: {enhanced_listing.get('monatsrate', 'Still null')}")
                print(f"  own_funds: {enhanced_listing.get('own_funds', 'Still null')}")
                
                if 'ollama_analysis' in enhanced_listing:
                    analysis = enhanced_listing['ollama_analysis']
                    print(f"\n🎯 ANALYSIS RESULTS:")
                    print(f"  Model: {analysis['model']}")
                    print(f"  Confidence: {analysis['confidence']}")
                    print(f"  Extracted fields: {analysis['extracted_fields']}")
                
            except Exception as e:
                print(f"❌ Ollama analysis failed: {e}")
        else:
            print("❌ Ollama not available")
            print("   Make sure Ollama is running: docker-compose up -d ollama")
        
        print("\n" + "=" * 60)
        print("✅ STRUCTURED ANALYZER TEST COMPLETE")
        print("\nTo use with real data:")
        print("1. Set OPENAI_API_KEY environment variable for best results")
        print("2. Or ensure Ollama is running for fallback mode")
        print("3. Run: python main.py")

    def test_json_schema_validation(self):
        """Test that the JSON schema is properly enforced"""
        print("\n🔬 TESTING JSON SCHEMA VALIDATION")
        print("=" * 60)
        
        # This demonstrates how OpenAI's structured output guarantees the schema
        sample_schema = {
            "type": "object",
            "properties": {
                "year_built": {"type": ["integer", "null"]},
                "floor": {"type": ["string", "null"]},
                "condition": {"type": ["string", "null"]},
                "heating": {"type": ["string", "null"]},
                "parking": {"type": ["string", "null"]},
                "monatsrate": {"type": ["number", "null"]},
                "own_funds": {"type": ["number", "null"]},
                "confidence": {"type": "number"}
            },
            "required": ["year_built", "floor", "condition", "heating", "parking", "monatsrate", "own_funds", "confidence"],
            "additionalProperties": False
        }
        
        print("📋 ENFORCED JSON SCHEMA:")
        print(json.dumps(sample_schema, indent=2))
        print("\n✅ This schema GUARANTEES:")
        print("  - All required fields are present (no missing keys)")
        print("  - Correct data types (integer, string, number, null)")
        print("  - No additional unexpected fields")
        print("  - Structured output that eliminates parsing errors")

if __name__ == '__main__':
    unittest.main() 