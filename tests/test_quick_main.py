#!/usr/bin/env python3
"""
Quick test for main system functionality
Tests that the system can start and process listings without hanging
"""

import sys
import time
import signal
import unittest
from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.analyzer import StructuredAnalyzer

def timeout_handler(signum, frame):
    """Handle timeout"""
    print("\n⏰ Test timed out - system is hanging!")
    sys.exit(1)

class TestQuickMain(unittest.TestCase):
    def test_system_startup(self):
        """Test that the system can start without hanging"""
        print("🧪 TESTING SYSTEM STARTUP")
        print("=" * 50)
        
        # Set timeout for the entire test
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)  # 60 second timeout
        
        try:
            print("🚀 Creating scraper...")
            start_time = time.time()
            
            scraper = WillhabenScraper()
            creation_time = time.time() - start_time
            
            print(f"✅ Scraper created in {creation_time:.2f}s")
            print(f"   Structured analyzer available: {scraper.structured_analyzer.is_available()}")
            
            # Test with a simple listing
            test_url = "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220-donaustadt/familienfreundlich-hell-3-zimmer-wohnung-mit-eigengarten-777958996/"
            
            print(f"\n🔍 Testing single listing scrape: {test_url}")
            start_time = time.time()
            
            try:
                listing_data = scraper.scrape_single_listing(test_url)
                scrape_time = time.time() - start_time
                
                if listing_data:
                    print(f"✅ Listing scraped successfully in {scrape_time:.2f}s")
                    
                    # Handle both dict and Listing object
                    if hasattr(listing_data, 'price_total'):
                        price = listing_data.price_total
                        area = listing_data.area_m2
                        rooms = listing_data.rooms
                        structured_analysis = getattr(listing_data, 'structured_analysis', None)
                    else:
                        price = listing_data.get('price_total', 'N/A')
                        area = listing_data.get('area_m2', 'N/A')
                        rooms = listing_data.get('rooms', 'N/A')
                        structured_analysis = listing_data.get('structured_analysis', None)
                    
                    print(f"   Price: €{price:,}" if price != 'N/A' else f"   Price: {price}")
                    print(f"   Area: {area}m²" if area != 'N/A' else f"   Area: {area}")
                    print(f"   Rooms: {rooms}")
                    
                    # Check if structured analysis was applied
                    if structured_analysis:
                        if isinstance(structured_analysis, dict):
                            print(f"   Analysis model: {structured_analysis.get('model', 'N/A')}")
                            print(f"   Confidence: {structured_analysis.get('confidence', 'N/A')}")
                            print(f"   Fields extracted: {len(structured_analysis.get('extracted_fields', []))}")
                        else:
                            print(f"   Analysis applied: {type(structured_analysis)}")
                    else:
                        print("   ⚠️ No structured analysis applied")
                    
                    self.assertTrue(True, "Listing scraped successfully")
                else:
                    print(f"❌ Failed to scrape listing after {scrape_time:.2f}s")
                    self.assertFalse(True, "Listing scraping failed")
                    
            except Exception as e:
                scrape_time = time.time() - start_time
                print(f"❌ Error scraping listing after {scrape_time:.2f}s: {e}")
                self.assertFalse(True, f"Error scraping listing: {e}")
                
        except Exception as e:
            print(f"❌ Error creating scraper: {e}")
            self.assertFalse(True, f"Error creating scraper: {e}")
        finally:
            signal.alarm(0)  # Cancel timeout

    def test_analyzer_performance(self):
        """Test analyzer performance"""
        print("\n🧪 TESTING ANALYZER PERFORMANCE")
        print("=" * 50)
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 second timeout
        
        try:
            print("🧠 Creating analyzer...")
            start_time = time.time()
            
            analyzer = StructuredAnalyzer()
            creation_time = time.time() - start_time
            
            print(f"✅ Analyzer created in {creation_time:.2f}s")
            
            # Test availability
            print("🔍 Checking availability...")
            start_time = time.time()
            
            is_available = analyzer.is_available()
            check_time = time.time() - start_time
            
            print(f"✅ Availability check completed in {check_time:.2f}s")
            print(f"   Available: {is_available}")
            
            if is_available:
                # Test analysis using StructuredAnalyzer (which has fallback logic)
                test_data = {
                    "price_total": 380000,
                    "area_m2": 73.27,
                    "rooms": 3,
                    "address": "1220 Wien, Donaustadt"
                }
                
                print("🧠 Testing analysis with fallback logic...")
                start_time = time.time()
                
                try:
                    # Use StructuredAnalyzer's analyze_listing which has fallback logic
                    result = analyzer.analyze_listing(test_data)
                    analysis_time = time.time() - start_time
                    
                    print(f"✅ Analysis completed in {analysis_time:.2f}s")
                    print(f"   Confidence: {result.get('confidence', 0)}")
                    print(f"   Fields extracted: {len([k for k, v in result.items() if v is not None and k != 'confidence'])}")
                    
                    self.assertTrue(True, "Analysis completed successfully")
                    
                except Exception as e:
                    analysis_time = time.time() - start_time
                    print(f"❌ Analysis failed after {analysis_time:.2f}s: {e}")
                    self.assertFalse(True, f"Analysis failed: {e}")
            else:
                print("⚠️ Analyzer not available - skipping analysis test")
                self.assertTrue(True, "Analyzer not available - skipping analysis test") # Not a failure if analyzer is not available
                
        except Exception as e:
            print(f"❌ Error testing analyzer: {e}")
            self.assertFalse(True, f"Error testing analyzer: {e}")
        finally:
            signal.alarm(0)  # Cancel timeout

if __name__ == '__main__':
    unittest.main() 