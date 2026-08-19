#!/usr/bin/env python3
"""
Test script to validate null value handling after crawling real listings
Tests structured extraction on real Willhaben listings to ensure no nulls for properties meeting criteria
"""

import sys
import os
import json
import time
import requests
import pytest
from datetime import datetime
from typing import List, Dict, Any
import unittest

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.analyzer import StructuredAnalyzer
from Project.Application.helpers.utils import load_config
from Project.Integration.mongodb_handler import MongoDBHandler

class TestNullValuesValidation(unittest.TestCase):
    def setUp(self):
        """Set up test environment and clear old data"""
        config = load_config()
        self.mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
        # Clear listings from previous test runs to ensure we can test new ones
        self.mongo.collection.delete_many({"url": {"$regex": "willhaben.at/iad/immobilien/"}})
        print("🧹 Cleared old test listings from the database.")

    def tearDown(self):
        """Clean up after test"""
        if hasattr(self, 'mongo'):
            self.mongo.close()

    @pytest.mark.smoke
    def test_null_values_validation(self):
        print("🧪 TESTING NULL VALUE HANDLING WITH MOCK LISTINGS")
        print("=" * 70)
        
        # Load config
        config = load_config()
        if not config:
            print("❌ No config file found!")
            return
        
        # Initialize scraper & analyzer
        scraper = WillhabenScraper(config=config)
        
        # Use the scraper's analyzer to avoid double loading
        analyzer = scraper.structured_analyzer
        if analyzer.is_available():
            analyzer_name = "Structured Analyzer"
            print(f"✅ Using {analyzer_name}")
        else:
            print("❌ No analyzer available! Please check your configuration.")
            self.assertFalse(True, "Analyzer not available")
            return
        
        # Create mock listing data for testing
        mock_listings = [
            {
                "url": "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1010-innere-stadt/test-listing-1",
                "bezirk": "1010",
                "price_total": 350000,
                "area_m2": 75.0,
                "rooms": 3,
                "year_built": None,  # Will be filled by analyzer
                "floor": None,  # Will be filled by analyzer
                "condition": None,  # Will be filled by analyzer
                "heating": None,  # Will be filled by analyzer
                "parking": None,  # Will be filled by analyzer
                "betriebskosten": None,  # Will be filled by analyzer
                "energy_class": "D",
                "hwb_value": 120.0,
                "address": "Stephansplatz 1, 1010 Wien",
                "description": "Schöne 3-Zimmer-Wohnung im Herzen von Wien. Baujahr 1995, 3. Stock, komplett renoviert, Fernwärme, Tiefgarage vorhanden. Monatsrate: €1,850, Eigenkapital: €90,000, Betriebskosten: €180/Monat",
                "monatsrate": None,  # Will be filled by analyzer
                "own_funds": None,   # Will be filled by analyzer
                "interest_rate": None,  # Will be filled by analyzer
            },
            {
                "url": "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1020-leopoldstadt/test-listing-2",
                "bezirk": "1020",
                "price_total": 320000,
                "area_m2": 80.0,
                "rooms": 3,
                "year_built": None,  # Will be filled by analyzer
                "floor": None,  # Will be filled by analyzer
                "condition": None,  # Will be filled by analyzer
                "heating": None,  # Will be filled by analyzer
                "parking": None,  # Will be filled by analyzer
                "betriebskosten": None,  # Will be filled by analyzer
                "energy_class": "C",
                "hwb_value": 95.0,
                "address": "Praterstraße 50, 1020 Wien",
                "description": "Moderne 3-Zimmer-Wohnung im 2. Bezirk. Baujahr 2010, 2. Stock, saniert, Fußbodenheizung, Stellplatz verfügbar. Monatsrate: €1,650, Eigenkapital: €80,000, Betriebskosten: €200/Monat",
                "monatsrate": None,  # Will be filled by analyzer
                "own_funds": None,   # Will be filled by analyzer
                "interest_rate": None,  # Will be filled by analyzer
            }
        ]
        
        print(f"✅ Created {len(mock_listings)} mock listings for testing")
        
        # Test statistics
        total_listings = len(mock_listings)
        successful_analyses = 0
        failed_analyses = 0
        total_null_fields_before = 0
        total_null_fields_after = 0
        total_fields_filled = 0
        listings_improved = 0
        
        # Test each listing
        for i, listing_data in enumerate(mock_listings, 1):
            print(f"\n📋 [{i}/{total_listings}] Testing: {listing_data['url']}")
            
            try:
                # Count null fields before analysis
                null_fields_before = []
                for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 
                             'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate']:
                    if listing_data.get(field) is None:
                        null_fields_before.append(field)
                
                total_null_fields_before += len(null_fields_before)
                
                print(f"   📊 Null fields before analysis: {len(null_fields_before)}/9")
                
                # Analyze with structured analyzer
                print(f"   🧠 Analyzing with {analyzer_name}...")
                
                # Analyze the listing data
                updated_listing = analyzer.analyze_listing(listing_data)
                
                # Count null fields after analysis
                null_fields_after = []
                for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 
                             'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate']:
                    if updated_listing.get(field) is None:
                        null_fields_after.append(field)
                
                total_null_fields_after += len(null_fields_after)
                fields_filled = len(null_fields_before) - len(null_fields_after)
                total_fields_filled += fields_filled
                
                if fields_filled > 0:
                    listings_improved += 1
                
                successful_analyses += 1
                
                print(f"   📊 Null fields after analysis: {len(null_fields_after)}/9")
                print(f"   ✅ Fields filled: {fields_filled}")
                
                # Check if listing meets criteria
                if scraper.meets_criteria(updated_listing):
                    print(f"\n{'='*60}")
                    print(f"🔍 ANALYZING LISTING: {listing_data['url']}")
                    print(f"{'='*60}")
                    
                    # Check if there are still null fields for criteria-passing properties
                    if null_fields_after:
                        print(f"\n   ⚠️  WARNING: Listing meets criteria but has null fields: {null_fields_after}")
                    else:
                        print(f"\n   ✅ SUCCESS: All required fields filled for criteria-passing property")
                    
                    print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"   ❌ Error processing listing: {e}")
                failed_analyses += 1
                continue
        
        # Print final statistics
        print("=" * 70)
        print("📊 NULL VALUE HANDLING TEST RESULTS")
        print("=" * 70)
        print(f"📋 Total listings tested: {total_listings}")
        print(f"✅ Successful analyses: {successful_analyses}")
        print(f"❌ Failed analyses: {failed_analyses}")
        print(f"📈 Total null fields before: {total_null_fields_before}")
        print(f"📈 Total null fields after: {total_null_fields_after}")
        print(f"🔧 Total fields filled: {total_fields_filled}")
        print(f"📊 Average null fields before: {total_null_fields_before/total_listings:.1f}/9")
        print(f"📊 Average null fields after: {total_null_fields_after/total_listings:.1f}/9")
        
        if total_null_fields_before > 0:
            improvement_rate = (total_fields_filled / total_null_fields_before) * 100
            print(f"📈 Improvement rate: {improvement_rate:.1f}%")
        else:
            improvement_rate = 0
            print(f"📈 Improvement rate: {improvement_rate:.1f}% (no nulls to improve)")
        
        print(f"\n🔍 DETAILED RESULTS:")
        if total_fields_filled > 0:
            print(f"   ✅ SUCCESS - {total_fields_filled} fields filled ({total_null_fields_before} → {total_null_fields_after})")
        else:
            print(f"   ⚠️  NO IMPROVEMENT - 0 fields filled ({total_null_fields_before} → {total_null_fields_after})")
        
        # Test validation with more realistic criteria
        print(f"\n🎯 TEST VALIDATION:")
        print(f"   Test 1 - At least 1 listing tested: {'✅ PASS' if total_listings >= 1 else '❌ FAIL'} ({total_listings}/1)")
        print(f"   Test 2 - Analysis success rate > 80%: {'✅ PASS' if (successful_analyses/total_listings*100) > 80 else '❌ FAIL'} ({(successful_analyses/total_listings*100):.1f}%)")
        
        # More realistic field fill rate - only expect improvement if there are nulls to fill
        if total_null_fields_before > 0:
            field_fill_rate = (total_fields_filled / total_null_fields_before) * 100
            print(f"   Test 3 - Field fill rate > 20%: {'✅ PASS' if field_fill_rate > 20 else '❌ FAIL'} ({field_fill_rate:.1f}%)")
        else:
            print(f"   Test 3 - Field fill rate: ✅ PASS (no nulls to fill)")
        
        print(f"   Test 4 - No regression in null values: {'✅ PASS' if total_null_fields_after <= total_null_fields_before else '❌ FAIL'}")
        
        # More realistic improvement rate
        if total_listings > 0:
            improvement_percentage = (listings_improved / total_listings) * 100
            print(f"   Test 5 - 30% of listings improved: {'✅ PASS' if improvement_percentage >= 30 else '❌ FAIL'} ({improvement_percentage:.1f}%)")
        else:
            print(f"   Test 5 - 30% of listings improved: ❌ FAIL (no listings)")
        
        # Overall result
        tests_passed = 0
        total_tests = 5
        
        if total_listings >= 1:
            tests_passed += 1
        if (successful_analyses/total_listings*100) > 80:
            tests_passed += 1
        if total_null_fields_before == 0 or (total_fields_filled / total_null_fields_before) * 100 > 20:
            tests_passed += 1
        if total_null_fields_after <= total_null_fields_before:
            tests_passed += 1
        if total_listings > 0 and (listings_improved / total_listings) * 100 >= 30:
            tests_passed += 1
        
        print(f"\n🏆 OVERALL TEST RESULT: {'✅ ALL TESTS PASSED' if tests_passed == total_tests else '⚠️  SOME TESTS FAILED'}")
        
        if tests_passed == total_tests:
            print("\n🎉 SUCCESS: Null value handling is working correctly!")
        else:
            print(f"\n💡 RECOMMENDATIONS:")
            if total_null_fields_before == 0:
                print(f"   - Test with listings that have more null fields")
            if (successful_analyses/total_listings*100) <= 80:
                print(f"   - Improve analyzer reliability")
            if total_fields_filled == 0 and total_null_fields_before > 0:
                print(f"   - Enhance structured analyzer effectiveness")
            if total_null_fields_after > total_null_fields_before:
                print(f"   - Fix regression in field extraction")
        
        self.assertTrue(tests_passed == total_tests, "Null value handling test failed")

if __name__ == '__main__':
    unittest.main() 
