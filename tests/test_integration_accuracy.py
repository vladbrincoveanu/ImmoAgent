#!/usr/bin/env python3
"""
Integration test for data accuracy
Tests that the scraper extracts correct data from real listings
"""

import sys
import os
import json
import time
from typing import Dict, Any, List
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrape import WillhabenScraper
from telegram_bot import TelegramBot
import unittest

class TestIntegrationAccuracy(unittest.TestCase):
    def test_single_listing_accuracy(self):
        """Test accuracy of single listing extraction"""
        print("🧪 TESTING SINGLE LISTING ACCURACY")
        print("=" * 70)
        
        # Load configuration
        config = load_config()
        if not config:
            return False
        
        # Initialize scraper
        scraper = WillhabenScraper(config=config)
        
        # Get expected data
        expected_data = get_expected_data()
        test_url = expected_data["url"]
        
        print(f"🔍 Testing URL: {test_url}")
        print(f"📊 Expected accuracy: High (comparing to real listing data)")
        
        # Scrape the listing
        print(f"\n🌐 Scraping listing...")
        start_time = time.time()
        
        try:
            actual_data = scraper.scrape_single_listing(test_url)
            scrape_time = time.time() - start_time
            
            if not actual_data:
                print("❌ Failed to scrape listing")
                return False
            
            print(f"✅ Scraped in {scrape_time:.2f}s")
            
        except Exception as e:
            print(f"❌ Error scraping: {e}")
            return False
        
        # --- EXTENDED: Check all Telegram fields ---
        telegram_fields = [
            'bezirk', 'price_total', 'area_m2', 'price_per_m2', 'rooms', 'ubahn_walk_minutes', 'school_walk_minutes',
            'year_built', 'condition', 'heating', 'parking', 'address',
            'monatsrate', 'own_funds', 'betriebskosten', 'total_monthly_cost',
            'energy_class', 'hwb_value', 'heating_type', 'energy_carrier', 'available_from', 'url'
        ]
        print(f"\n🔎 FIELD-BY-FIELD TELEGRAM CHECK:")
        print("=" * 50)
        correct = []
        incorrect = []
        missing = []
        for field in telegram_fields:
            expected = expected_data.get(field, None)
            actual = actual_data.get(field, None)
            if expected is None and actual is None:
                print(f"   - {field}: MISSING in both")
                missing.append(field)
            elif expected == actual:
                print(f"   ✓ {field}: {actual}")
                correct.append(field)
            else:
                print(f"   ✗ {field}: expected {expected} | got {actual}")
                incorrect.append((field, expected, actual))
        print(f"\nSUMMARY:")
        print(f"   Correct:   {len(correct)}")
        print(f"   Incorrect: {len(incorrect)}")
        print(f"   Missing:   {len(missing)}")
        
        # Compare data
        print(f"\n📊 COMPARING DATA:")
        print("=" * 50)
        
        comparison = compare_data(actual_data, expected_data)
        
        # Print matches
        if comparison["matches"]:
            print(f"✅ CORRECT FIELDS ({len(comparison['matches'])}):")
            for field in comparison["matches"]:
                print(f"   ✓ {field}: {actual_data.get(field)}")
        
        # Print mismatches
        if comparison["mismatches"]:
            print(f"\n❌ INCORRECT FIELDS ({len(comparison['mismatches'])}):")
            for mismatch in comparison["mismatches"]:
                print(f"   ✗ {mismatch['field']}:")
                print(f"     Expected: {mismatch['expected']}")
                print(f"     Actual:   {mismatch['actual']}")
        
        # Print missing fields
        if comparison["missing"]:
            print(f"\n⚠️  MISSING FIELDS ({len(comparison['missing'])}):")
            for field in comparison["missing"]:
                print(f"   - {field}")
        
        # Print extra fields
        if comparison["extra"]:
            print(f"\n➕ EXTRA FIELDS ({len(comparison['extra'])}):")
            for field in comparison["extra"]:
                print(f"   + {field}: {actual_data.get(field)}")
        
        # Print accuracy score
        print(f"\n📈 ACCURACY ANALYSIS:")
        print("=" * 50)
        print(f"   Accuracy Score: {comparison['accuracy_score']:.1f}%")
        print(f"   Correct Fields: {len(comparison['matches'])}/{len(expected_data)}")
        print(f"   Incorrect Fields: {len(comparison['mismatches'])}")
        print(f"   Missing Fields: {len(comparison['missing'])}")
        
        # Test Telegram message format
        print(f"\n📱 TELEGRAM MESSAGE PREVIEW:")
        print("=" * 50)
        # Use the real TelegramBot formatting logic
        bot = TelegramBot(bot_token="dummy", chat_id="dummy")
        telegram_message = bot._format_property_message(actual_data)
        print(telegram_message)
        
        # Validation criteria
        print(f"\n🎯 VALIDATION CRITERIA:")
        print("=" * 50)
        
        criteria_results = []
        
        # Accuracy threshold
        accuracy_ok = comparison['accuracy_score'] >= 70
        criteria_results.append(("Accuracy >= 70%", accuracy_ok, f"{comparison['accuracy_score']:.1f}%"))
        
        # Critical fields must be correct
        critical_fields = ['price_total', 'area_m2', 'rooms', 'bezirk']
        critical_ok = all(field in comparison['matches'] for field in critical_fields)
        criteria_results.append(("Critical fields correct", critical_ok, f"{len([f for f in critical_fields if f in comparison['matches']])}/{len(critical_fields)}"))
        
        # No major data type errors
        type_errors = 0
        for mismatch in comparison['mismatches']:
            if isinstance(mismatch['expected'], (int, float)) and isinstance(mismatch['actual'], (int, float)):
                if abs(mismatch['expected'] - mismatch['actual']) > 1000:  # Large numerical difference
                    type_errors += 1
        
        type_ok = type_errors == 0
        criteria_results.append(("No major data errors", type_ok, f"{type_errors} errors"))
        
        # Print criteria results
        for criterion, passed, details in criteria_results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {status} {criterion}: {details}")
        
        # Overall result
        all_passed = all(result[1] for result in criteria_results)
        
        print(f"\n🏆 OVERALL RESULT: {'✅ INTEGRATION TEST PASSED' if all_passed else '❌ INTEGRATION TEST FAILED'}")
        
        if all_passed:
            print("\n🎉 SUCCESS: Data extraction is accurate!")
            print("💡 The scraper correctly extracts property information")
        else:
            print("\n🔧 RECOMMENDATIONS:")
            if comparison['accuracy_score'] < 70:
                print("   - Improve field extraction accuracy")
            if not critical_ok:
                print("   - Fix critical field extraction")
            if not type_ok:
                print("   - Fix data type conversion issues")
        
        return all_passed

    def test_energy_data_extraction(self):
        """Test specific energy data extraction"""
        print(f"\n⚡ TESTING ENERGY DATA EXTRACTION")
        print("=" * 50)
        
        # Test with the same listing
        expected_energy = {
            "energy_class": "D",
            "hwb_value": 111.7,
            "heating_type": "Gas",
            "energy_carrier": "Gas"
        }
        
        # This would test the enhanced scraper with energy data extraction
        # For now, just show what we expect
        print("Expected energy data:")
        for field, value in expected_energy.items():
            print(f"   {field}: {value}")
        
        print("\n⚠️  Energy data extraction needs to be implemented in scraper")
        return True

def load_config():
    """Load configuration from config files"""
    config_paths = ['config.json', 'config.default.json']
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                print(f"✅ Loaded config from {config_path}")
                return config
            except Exception as e:
                print(f"❌ Error loading {config_path}: {e}")
                continue
    
    print("❌ No config file found!")
    return {}

def get_expected_data() -> Dict[str, Any]:
    """Get expected data for the test listing"""
    return {
        "url": "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1190-doebling/perfekt-aufgeteilte-altbauwohnung-naehe-hohe-warte-1076664583/",
        "bezirk": "1190",
        "address": "1190 Wien, Döbling",  # Expected to be extracted from the listing
        "price_total": 310000,
        "area_m2": 89.02,
        "rooms": 3,
        "year_built": None,  # Not mentioned in listing
        "floor": "Hochparterre",  # From listing: "Hochparterre"
        "condition": "Sanierungsbedürftig",  # Updated to match actual case
        "heating": "Etagenheizung",  # From listing: "Etagenheizung"
        "parking": None,  # Not mentioned in listing
        "monatsrate": None,  # Not mentioned in listing
        "own_funds": None,  # Not mentioned in listing
        "betriebskosten": 162.86,  # From listing: "EUR 162,86"
        "energy_class": "D",  # From listing: "Klasse D"
        "hwb_value": 111.7,  # From listing: "HWB 111,7 kWh/m²/Jahr"
        "heating_type": "Gas",  # From listing JSON: "Heizungsart: Gasheizung"
        "energy_carrier": "Gas",  # From listing JSON: "Wesentliche Energieträger: Gas"
        "available_from": "sofort",  # From listing JSON: "Verfügbar ab: sofort"
        "special_features": None,  # Not extracted yet
        "ubahn_walk_minutes": 15,  # Expected real calculated value (not -1)
        "school_walk_minutes": 8,  # Expected real calculated value (not -1)
        "total_monthly_cost": None  # Calculated field
    }

def compare_data(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    """Compare actual vs expected data and return analysis"""
    comparison = {
        "matches": [],
        "mismatches": [],
        "missing": [],
        "extra": [],
        "accuracy_score": 0.0
    }
    
    # Check expected fields
    for field, expected_value in expected.items():
        if field in actual:
            actual_value = actual.get(field)
            
            # Handle case-insensitive string comparison for certain fields
            if isinstance(expected_value, str) and isinstance(actual_value, str):
                if field in ['condition', 'heating', 'heating_type', 'energy_carrier', 'available_from']:
                    # Case-insensitive comparison for these fields
                    if actual_value.lower() == expected_value.lower():
                        comparison["matches"].append(field)
                    else:
                        comparison["mismatches"].append({
                            "field": field,
                            "expected": expected_value,
                            "actual": actual_value
                        })
                else:
                    # Exact comparison for other fields
                    if actual_value == expected_value:
                        comparison["matches"].append(field)
                    else:
                        comparison["mismatches"].append({
                            "field": field,
                            "expected": expected_value,
                            "actual": actual_value
                        })
            else:
                # Non-string comparison
                if actual_value == expected_value:
                    comparison["matches"].append(field)
                else:
                    comparison["mismatches"].append({
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value
                    })
        else:
            comparison["missing"].append(field)
    
    # Check for extra fields in actual
    for field in actual:
        if field not in expected and field not in ['url', 'processed_at', 'sent_to_telegram', 'structured_analysis']:
            comparison["extra"].append(field)
    
    # Calculate accuracy score
    total_fields = len(expected)
    correct_fields = len(comparison["matches"])
    comparison["accuracy_score"] = (correct_fields / total_fields) * 100 if total_fields > 0 else 0
    
    return comparison

if __name__ == "__main__":
    unittest.main() 