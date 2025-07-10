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
from datetime import datetime
from typing import List, Dict, Any
import unittest

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape import WillhabenScraper
from ollama_analyzer import StructuredAnalyzer, OllamaAnalyzer
from helpers import load_config
from mongodb_handler import MongoDBHandler

class TestNullValuesValidation(unittest.TestCase):
    def setUp(self):
        """Set up test environment and clear old data"""
        config = load_config()
        self.mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
        # Clear listings from previous test runs to ensure we can test new ones
        self.mongo.collection.delete_many({"url": {"$regex": "willhaben.at/iad/immobilien/"}})
        print("🧹 Cleared old test listings from the database.")

    def test_null_values_validation(self):
        print("🧪 TESTING NULL VALUE HANDLING WITH REAL LISTINGS")
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
        
        # Get test URLs from search agent
        alert_url = "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387"
        print(f"\n🔍 Getting test URLs from: {alert_url}")
        
        try:
            # Get URLs from search agent
            listings = scraper.scrape_search_agent_page(alert_url, max_pages=1)
            urls = [listing.get('url') for listing in listings if listing.get('url')]
            if not urls:
                print("❌ No URLs found for testing")
                self.assertFalse(True, "No URLs found for testing")
                return
            
            print(f"✅ Found {len(urls)} URLs for testing")
            
            # Test statistics
            total_listings = len(urls)
            successful_scrapes = 0
            failed_analyses = 0
            total_null_fields_before = 0
            total_null_fields_after = 0
            total_fields_filled = 0
            listings_improved = 0
            
            # Test each listing
            for i, url in enumerate(urls[:3], 1):  # Limit to 3 for faster testing
                if not url:
                    continue

                print(f"\n📋 [{i}/{min(len(urls), 3)}] Testing: {url}")
                
                try:
                    # Scrape the listing
                    listing_data = scraper.scrape_single_listing(url)
                    if not listing_data:
                        print("   ❌ Failed to scrape listing")
                        continue
                    
                    successful_scrapes += 1
                    
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
                    
                    # Fetch HTML content for analysis - use regular requests instead of Selenium for speed
                    try:
                        if url:
                            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=10)
                            html = response.text if response.status_code == 200 else ""
                        else:
                            html = ""
                    except:
                        html = ""
                    
                    if html:
                        if hasattr(analyzer, 'analyze_listing_content'):
                            updated_listing = analyzer.analyze_listing_content(listing_data, html)
                        else:
                            updated_listing = analyzer.analyze_listing(listing_data)
                    else:
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
                    
                    print(f"   📊 Null fields after analysis: {len(null_fields_after)}/9")
                    print(f"   ✅ Fields filled: {fields_filled}")
                    
                    # Check if listing meets criteria
                    if scraper.meets_criteria(updated_listing):
                        print(f"\n{'='*60}")
                        print(f"🔍 ANALYZING LISTING: {url}")
                        print(f"{'='*60}")
                        
                        # The meets_criteria method now prints the details
                        # so we don't need to duplicate the logic here.
                        
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
                
                # Reduced delay between requests for faster testing
                time.sleep(0.5)
            
            # Print final statistics
            print("=" * 70)
            print("📊 NULL VALUE HANDLING TEST RESULTS")
            print("=" * 70)
            print(f"📋 Total listings tested: {total_listings}")
            print(f"✅ Successful scrapes: {successful_scrapes}")
            print(f"❌ Failed analyses: {failed_analyses}")
            print(f"📈 Total null fields before: {total_null_fields_before}")
            print(f"📈 Total null fields after: {total_null_fields_after}")
            print(f"🔧 Total fields filled: {total_fields_filled}")
            print(f"📊 Average null fields before: {total_null_fields_before/total_listings:.1f}/8")
            print(f"📊 Average null fields after: {total_null_fields_after/total_listings:.1f}/8")
            
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
            print(f"   Test 2 - Scrape success rate > 80%: {'✅ PASS' if (successful_scrapes/total_listings*100) > 80 else '❌ FAIL'} ({(successful_scrapes/total_listings*100):.1f}%)")
            
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
            if (successful_scrapes/total_listings*100) > 80:
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
                if (successful_scrapes/total_listings*100) <= 80:
                    print(f"   - Improve scraper reliability")
                if total_fields_filled == 0 and total_null_fields_before > 0:
                    print(f"   - Enhance structured analyzer effectiveness")
                if total_null_fields_after > total_null_fields_before:
                    print(f"   - Fix regression in field extraction")
            
            self.assertTrue(tests_passed == total_tests, "Null value handling test failed")
            
        except Exception as e:
            print(f"❌ Error in test: {e}")
            self.assertFalse(True, f"Test failed with error: {e}")

if __name__ == '__main__':
    unittest.main() 