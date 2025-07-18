#!/usr/bin/env python3
"""
Test script to compare Outlines analyzer vs scraper-only performance and accuracy
"""

import sys
import os
import time
import unittest
import statistics
import random
from typing import Dict, List, Tuple
sys.path.append('.')

from Project.Application.analyzer import OutlinesAnalyzer, LightweightAnalyzer, StructuredAnalyzer
from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.helpers.utils import load_config

class TestOutlinesVsScraper(unittest.TestCase):
    def setUp(self):
        """Set up test data and analyzers"""
        self.config = load_config()
        self.scraper = WillhabenScraper(config=self.config)
        
        # Create a larger, more realistic test dataset
        self.test_listings = self._generate_realistic_test_data()
        
        # Expected data for accuracy testing
        self.expected_data = self._generate_expected_data()

    def _generate_realistic_test_data(self) -> List[Dict]:
        """Generate realistic test data with various scenarios"""
        base_listings = [
            {
                "url": "https://example.com/listing1",
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
            },
            {
                "url": "https://example.com/listing2", 
                "bezirk": "1010",
                "price_total": 650000,
                "area_m2": 95.0,
                "rooms": 4,
                "address": "Stephansplatz 5, 1010 Wien",
                "description": """
                Luxuriöse 4-Zimmer-Wohnung im 1. Stock, Baujahr 1995, erstbezug.
                Fußbodenheizung, Tiefgarage, Lift. Monatsrate €2.200.
                Eigenkapital €120.000, Betriebskosten €250/Monat.
                """,
                "details": "Premium Lage, hochwertige Ausstattung"
            },
            {
                "url": "https://example.com/listing3",
                "bezirk": "1040", 
                "price_total": 380000,
                "area_m2": 65.0,
                "rooms": 2,
                "address": "Wiedner Hauptstraße 15, 1040 Wien",
                "description": """
                2-Zimmer-Wohnung im 4. Stock, Baujahr 1975, renoviert.
                Gasheizung, Stellplatz im Hof. Monatsrate €1.400.
                Eigenkapital €70.000, Betriebskosten €150/Monat.
                """,
                "details": "Ruhige Lage, guter Zustand"
            },
            {
                "url": "https://example.com/listing4",
                "bezirk": "1080",
                "price_total": 520000,
                "area_m2": 78.0,
                "rooms": 3,
                "address": "Josefstädter Straße 8, 1080 Wien",
                "description": """
                Charmante 3-Zimmer-Wohnung im 3. Stock, Baujahr 1965, teilweise renoviert.
                Zentralheizung, Garage vorhanden. Monatsrate €1.950.
                Eigenkapital €100.000, Betriebskosten €200/Monat.
                """,
                "details": "Altbau-Charme, hohe Decken"
            },
            {
                "url": "https://example.com/listing5",
                "bezirk": "1090",
                "price_total": 580000,
                "area_m2": 82.0,
                "rooms": 3,
                "address": "Alser Straße 25, 1090 Wien",
                "description": """
                Moderne 3-Zimmer-Wohnung im 5. Stock, Baujahr 2010, neuwertig.
                Fernwärme, Tiefgarage, Lift. Monatsrate €2.100.
                Eigenkapital €110.000, Betriebskosten €220/Monat.
                """,
                "details": "Neubau, moderne Ausstattung"
            }
        ]
        
        # Add some edge cases and variations
        edge_cases = [
            {
                "url": "https://example.com/edge1",
                "bezirk": "1020",
                "price_total": 280000,
                "area_m2": 45.0,
                "rooms": 1,
                "address": "Praterstraße 50, 1020 Wien",
                "description": "Kleine 1-Zimmer-Wohnung, Baujahr 1985, renoviert. Gasheizung.",
                "details": "Minimalistische Ausstattung"
            },
            {
                "url": "https://example.com/edge2",
                "bezirk": "1130",
                "price_total": 750000,
                "area_m2": 120.0,
                "rooms": 5,
                "address": "Hietzinger Hauptstraße 100, 1130 Wien",
                "description": """
                Große 5-Zimmer-Wohnung im Erdgeschoss, Baujahr 2005, erstbezug.
                Fußbodenheizung, Doppelgarage. Monatsrate €2.800.
                Eigenkapital €150.000, Betriebskosten €300/Monat.
                """,
                "details": "Luxuriöse Ausstattung, Garten"
            }
        ]
        
        return base_listings + edge_cases

    def _generate_expected_data(self) -> List[Dict]:
        """Generate expected data for accuracy testing"""
        return [
            {
                "year_built": 1980,
                "floor": "2. Stock", 
                "condition": "saniert",
                "heating": "Fernwärme",
                "parking": "Tiefgarage",
                "own_funds": 90000,
                "betriebskosten": 180
            },
            {
                "year_built": 1995,
                "floor": "1. Stock",
                "condition": "erstbezug", 
                "heating": "Fußbodenheizung",
                "parking": "Tiefgarage",
                "own_funds": 120000,
                "betriebskosten": 250
            },
            {
                "year_built": 1975,
                "floor": "4. Stock",
                "condition": "renoviert",
                "heating": "Gas",
                "parking": "Stellplatz", 
                "own_funds": 70000,
                "betriebskosten": 150
            },
            {
                "year_built": 1965,
                "floor": "3. Stock",
                "condition": "teilweise renoviert",
                "heating": "Zentralheizung",
                "parking": "Garage",
                "own_funds": 100000,
                "betriebskosten": 200
            },
            {
                "year_built": 2010,
                "floor": "5. Stock",
                "condition": "neuwertig",
                "heating": "Fernwärme",
                "parking": "Tiefgarage",
                "own_funds": 110000,
                "betriebskosten": 220
            },
            {
                "year_built": 1985,
                "floor": None,
                "condition": "renoviert",
                "heating": "Gas",
                "parking": None,
                "own_funds": None,
                "betriebskosten": None
            },
            {
                "year_built": 2005,
                "floor": "Erdgeschoss",
                "condition": "erstbezug",
                "heating": "Fußbodenheizung",
                "parking": "Doppelgarage",
                "own_funds": 150000,
                "betriebskosten": 300
            }
        ]

    def test_performance_comparison(self):
        """Compare performance speed between Outlines and scraper-only approaches"""
        print("🏃‍♂️ PERFORMANCE COMPARISON: Outlines vs Scraper-Only")
        print("=" * 60)
        
        # Initialize analyzers
        lightweight_analyzer = LightweightAnalyzer()
        structured_analyzer = StructuredAnalyzer()
        
        # Test performance for each listing with multiple iterations
        performance_results = {
            'lightweight': {'times': [], 'success_count': 0},
            'structured': {'times': [], 'success_count': 0},
            'scraper_only': {'times': [], 'success_count': 0}
        }
        
        iterations = 3  # Run each test multiple times for more accurate timing
        
        for i, listing in enumerate(self.test_listings):
            print(f"\n📋 Testing Listing {i+1}/{len(self.test_listings)}")
            
            # Test LightweightAnalyzer
            lightweight_times = []
            for _ in range(iterations):
                start_time = time.perf_counter()
                try:
                    lightweight_result = lightweight_analyzer.analyze_listing(listing)
                    lightweight_time = time.perf_counter() - start_time
                    lightweight_times.append(lightweight_time)
                except Exception as e:
                    print(f"   ❌ LightweightAnalyzer failed: {e}")
                    break
            
            if lightweight_times:
                avg_lightweight_time = statistics.mean(lightweight_times)
                performance_results['lightweight']['times'].append(avg_lightweight_time)
                performance_results['lightweight']['success_count'] += 1
                print(f"   ⚡ LightweightAnalyzer: {avg_lightweight_time:.6f}s (avg of {len(lightweight_times)} runs)")
            
            # Test StructuredAnalyzer
            structured_times = []
            for _ in range(iterations):
                start_time = time.perf_counter()
                try:
                    structured_result = structured_analyzer.analyze_listing(listing)
                    structured_time = time.perf_counter() - start_time
                    structured_times.append(structured_time)
                except Exception as e:
                    print(f"   ❌ StructuredAnalyzer failed: {e}")
                    break
            
            if structured_times:
                avg_structured_time = statistics.mean(structured_times)
                performance_results['structured']['times'].append(avg_structured_time)
                performance_results['structured']['success_count'] += 1
                print(f"   �� StructuredAnalyzer: {avg_structured_time:.6f}s (avg of {len(structured_times)} runs)")
            
            # Test scraper-only approach
            scraper_times = []
            for _ in range(iterations):
                start_time = time.perf_counter()
                try:
                    scraper_result = self._extract_with_scraper_logic(listing)
                    scraper_time = time.perf_counter() - start_time
                    scraper_times.append(scraper_time)
                except Exception as e:
                    print(f"   ❌ Scraper-only failed: {e}")
                    break
            
            if scraper_times:
                avg_scraper_time = statistics.mean(scraper_times)
                performance_results['scraper_only']['times'].append(avg_scraper_time)
                performance_results['scraper_only']['success_count'] += 1
                print(f"   🔧 Scraper-only: {avg_scraper_time:.6f}s (avg of {len(scraper_times)} runs)")
        
        # Calculate statistics
        print(f"\n📊 PERFORMANCE STATISTICS")
        print("=" * 60)
        
        for method, data in performance_results.items():
            if data['times']:
                avg_time = statistics.mean(data['times'])
                min_time = min(data['times'])
                max_time = max(data['times'])
                success_rate = data['success_count'] / len(self.test_listings) * 100
                
                print(f"\n{method.upper()}:")
                print(f"   Average time: {avg_time:.6f}s")
                print(f"   Min time: {min_time:.6f}s")
                print(f"   Max time: {max_time:.6f}s")
                print(f"   Success rate: {success_rate:.1f}%")
                print(f"   Total time for {len(self.test_listings)} listings: {sum(data['times']):.6f}s")
        
        # Performance assertions
        if performance_results['lightweight']['times']:
            avg_lightweight = statistics.mean(performance_results['lightweight']['times'])
            self.assertLess(avg_lightweight, 0.01, "LightweightAnalyzer should be very fast (< 0.01s)")
        
        if performance_results['structured']['times']:
            avg_structured = statistics.mean(performance_results['structured']['times'])
            self.assertLess(avg_structured, 0.01, "StructuredAnalyzer should be very fast (< 0.01s)")
        
        if performance_results['scraper_only']['times']:
            avg_scraper = statistics.mean(performance_results['scraper_only']['times'])
            self.assertLess(avg_scraper, 0.005, "Scraper-only should be extremely fast (< 0.005s)")

    def test_accuracy_comparison(self):
        """Compare accuracy between Outlines and scraper-only approaches"""
        print("\n🎯 ACCURACY COMPARISON: Outlines vs Scraper-Only")
        print("=" * 60)
        
        # Initialize analyzers
        lightweight_analyzer = LightweightAnalyzer()
        structured_analyzer = StructuredAnalyzer()
        
        accuracy_results = {
            'lightweight': {'correct': 0, 'total': 0, 'field_accuracy': {}},
            'structured': {'correct': 0, 'total': 0, 'field_accuracy': {}},
            'scraper_only': {'correct': 0, 'total': 0, 'field_accuracy': {}}
        }
        
        # Fields to test
        test_fields = ['year_built', 'floor', 'condition', 'heating', 'parking', 'own_funds', 'betriebskosten']
        
        for i, (listing, expected) in enumerate(zip(self.test_listings, self.expected_data)):
            print(f"\n📋 Testing Accuracy for Listing {i+1}")
            
            # Test LightweightAnalyzer
            try:
                lightweight_result = lightweight_analyzer.analyze_listing(listing)
                lightweight_accuracy = self._calculate_accuracy(lightweight_result, expected, test_fields)
                accuracy_results['lightweight']['correct'] += lightweight_accuracy['correct']
                accuracy_results['lightweight']['total'] += lightweight_accuracy['total']
                self._update_field_accuracy(accuracy_results['lightweight']['field_accuracy'], lightweight_accuracy['field_results'])
                print(f"   ⚡ LightweightAnalyzer: {lightweight_accuracy['correct']}/{lightweight_accuracy['total']} correct")
            except Exception as e:
                print(f"   ❌ LightweightAnalyzer failed: {e}")
            
            # Test StructuredAnalyzer
            try:
                structured_result = structured_analyzer.analyze_listing(listing)
                structured_accuracy = self._calculate_accuracy(structured_result, expected, test_fields)
                accuracy_results['structured']['correct'] += structured_accuracy['correct']
                accuracy_results['structured']['total'] += structured_accuracy['total']
                self._update_field_accuracy(accuracy_results['structured']['field_accuracy'], structured_accuracy['field_results'])
                print(f"   🧠 StructuredAnalyzer: {structured_accuracy['correct']}/{structured_accuracy['total']} correct")
            except Exception as e:
                print(f"   ❌ StructuredAnalyzer failed: {e}")
            
            # Test scraper-only approach
            try:
                scraper_result = self._extract_with_scraper_logic(listing)
                scraper_accuracy = self._calculate_accuracy(scraper_result, expected, test_fields)
                accuracy_results['scraper_only']['correct'] += scraper_accuracy['correct']
                accuracy_results['scraper_only']['total'] += scraper_accuracy['total']
                self._update_field_accuracy(accuracy_results['scraper_only']['field_accuracy'], scraper_accuracy['field_results'])
                print(f"   🔧 Scraper-only: {scraper_accuracy['correct']}/{scraper_accuracy['total']} correct")
            except Exception as e:
                print(f"   ❌ Scraper-only failed: {e}")
        
        # Calculate overall accuracy
        print(f"\n📊 ACCURACY STATISTICS")
        print("=" * 60)
        
        for method, data in accuracy_results.items():
            if data['total'] > 0:
                overall_accuracy = data['correct'] / data['total'] * 100
                print(f"\n{method.upper()}:")
                print(f"   Overall accuracy: {overall_accuracy:.1f}% ({data['correct']}/{data['total']})")
                
                # Field-specific accuracy
                print("   Field accuracy:")
                for field, field_data in data['field_accuracy'].items():
                    if field_data['total'] > 0:
                        field_accuracy = field_data['correct'] / field_data['total'] * 100
                        print(f"     {field}: {field_accuracy:.1f}% ({field_data['correct']}/{field_data['total']})")
        
        # Accuracy assertions
        for method, data in accuracy_results.items():
            if data['total'] > 0:
                overall_accuracy = data['correct'] / data['total']
                self.assertGreater(overall_accuracy, 0.6, f"{method} should have at least 60% accuracy")

    def test_scalability_comparison(self):
        """Test how well each approach scales with larger datasets"""
        print("\n📈 SCALABILITY COMPARISON")
        print("=" * 60)
        
        # Generate larger dataset
        large_dataset = self._generate_large_dataset(50)  # 50 listings
        
        # Initialize analyzers
        lightweight_analyzer = LightweightAnalyzer()
        structured_analyzer = StructuredAnalyzer()
        
        scalability_results = {
            'lightweight': {'total_time': 0, 'success_count': 0},
            'structured': {'total_time': 0, 'success_count': 0},
            'scraper_only': {'total_time': 0, 'success_count': 0}
        }
        
        print(f"Testing with {len(large_dataset)} listings...")
        
        # Test LightweightAnalyzer
        start_time = time.perf_counter()
        for listing in large_dataset:
            try:
                lightweight_analyzer.analyze_listing(listing)
                scalability_results['lightweight']['success_count'] += 1
            except Exception:
                pass
        scalability_results['lightweight']['total_time'] = time.perf_counter() - start_time
        
        # Test StructuredAnalyzer
        start_time = time.perf_counter()
        for listing in large_dataset:
            try:
                structured_analyzer.analyze_listing(listing)
                scalability_results['structured']['success_count'] += 1
            except Exception:
                pass
        scalability_results['structured']['total_time'] = time.perf_counter() - start_time
        
        # Test scraper-only
        start_time = time.perf_counter()
        for listing in large_dataset:
            try:
                self._extract_with_scraper_logic(listing)
                scalability_results['scraper_only']['success_count'] += 1
            except Exception:
                pass
        scalability_results['scraper_only']['total_time'] = time.perf_counter() - start_time
        
        # Print results
        for method, data in scalability_results.items():
            avg_time_per_listing = data['total_time'] / len(large_dataset)
            success_rate = data['success_count'] / len(large_dataset) * 100
            
            print(f"\n{method.upper()}:")
            print(f"   Total time: {data['total_time']:.3f}s")
            print(f"   Average per listing: {avg_time_per_listing:.6f}s")
            print(f"   Success rate: {success_rate:.1f}%")
            print(f"   Throughput: {len(large_dataset)/data['total_time']:.1f} listings/second")
        
        # Scalability assertions
        self.assertLess(scalability_results['lightweight']['total_time'], 5.0, "LightweightAnalyzer should process 50 listings in < 5s")
        self.assertLess(scalability_results['structured']['total_time'], 5.0, "StructuredAnalyzer should process 50 listings in < 5s")
        self.assertLess(scalability_results['scraper_only']['total_time'], 1.0, "Scraper-only should process 50 listings in < 1s")

    def _generate_large_dataset(self, size: int) -> List[Dict]:
        """Generate a large dataset for scalability testing"""
        templates = [
            {
                "description": "Schöne Wohnung im {floor}. Stock, Baujahr {year}, {condition}. {heating}. {parking}. Eigenkapital €{own_funds}, Betriebskosten €{betriebskosten}.",
                "year": 1980,
                "floor": "2",
                "condition": "saniert",
                "heating": "Fernwärme",
                "parking": "Tiefgarage",
                "own_funds": 90000,
                "betriebskosten": 180
            },
            {
                "description": "Moderne Wohnung im {floor}. Stock, Baujahr {year}, {condition}. {heating}. {parking}. Eigenkapital €{own_funds}, Betriebskosten €{betriebskosten}.",
                "year": 1995,
                "floor": "1",
                "condition": "erstbezug",
                "heating": "Fußbodenheizung",
                "parking": "Tiefgarage",
                "own_funds": 120000,
                "betriebskosten": 250
            }
        ]
        
        dataset = []
        for i in range(size):
            template = random.choice(templates)
            listing = {
                "url": f"https://example.com/listing{i}",
                "bezirk": f"10{random.randint(10, 30)}",
                "price_total": random.randint(300000, 800000),
                "area_m2": random.uniform(50, 120),
                "rooms": random.randint(1, 5),
                "address": f"Teststraße {i}, Wien",
                "description": template["description"].format(**template),
                "details": "Test details"
            }
            dataset.append(listing)
        
        return dataset

    def _extract_with_scraper_logic(self, listing: Dict) -> Dict:
        """Simulate scraper-only extraction logic"""
        result = {
            "year_built": None,
            "floor": None,
            "condition": None,
            "heating": None,
            "parking": None,
            "own_funds": None,
            "betriebskosten": None,
            "confidence": 0.0
        }
        
        # Extract text content
        text = listing.get('description', '') + ' ' + listing.get('details', '')
        
        # Use simple regex patterns (similar to scraper logic)
        import re
        
        # Year built
        year_match = re.search(r'Baujahr\s*(\d{4})', text)
        if year_match:
            result['year_built'] = int(year_match.group(1))
        
        # Floor
        floor_match = re.search(r'(\d+)\.?\s*Stock', text)
        if floor_match:
            result['floor'] = f"{floor_match.group(1)}. Stock"
        
        # Condition
        if 'saniert' in text:
            result['condition'] = 'saniert'
        elif 'renoviert' in text:
            result['condition'] = 'renoviert'
        elif 'erstbezug' in text:
            result['condition'] = 'erstbezug'
        elif 'neuwertig' in text:
            result['condition'] = 'neuwertig'
        elif 'teilweise renoviert' in text:
            result['condition'] = 'teilweise renoviert'
        
        # Heating
        if 'Fernwärme' in text:
            result['heating'] = 'Fernwärme'
        elif 'Fußbodenheizung' in text:
            result['heating'] = 'Fußbodenheizung'
        elif 'Gas' in text:
            result['heating'] = 'Gas'
        elif 'Zentralheizung' in text:
            result['heating'] = 'Zentralheizung'
        
        # Parking
        if 'Tiefgarage' in text:
            result['parking'] = 'Tiefgarage'
        elif 'Stellplatz' in text:
            result['parking'] = 'Stellplatz'
        elif 'Garage' in text:
            result['parking'] = 'Garage'
        elif 'Doppelgarage' in text:
            result['parking'] = 'Doppelgarage'
        
        # Own funds
        eigenkapital_match = re.search(r'Eigenkapital\s*€?\s*([\d.,]+)', text)
        if eigenkapital_match:
            amount_str = eigenkapital_match.group(1).replace('.', '').replace(',', '')
            result['own_funds'] = float(amount_str)
        
        # Betriebskosten
        betriebskosten_match = re.search(r'Betriebskosten\s*€?\s*([\d.,]+)', text)
        if betriebskosten_match:
            amount_str = betriebskosten_match.group(1).replace('.', '').replace(',', '')
            result['betriebskosten'] = float(amount_str)
        
        # Calculate confidence
        extracted_count = sum(1 for v in result.values() if v is not None and v != 0.0)
        result['confidence'] = min(0.9, extracted_count / 7.0)
        
        return result

    def _calculate_accuracy(self, actual: Dict, expected: Dict, fields: List[str]) -> Dict:
        """Calculate accuracy between actual and expected results"""
        correct = 0
        total = len(fields)
        field_results = {field: {'correct': 0, 'total': 1} for field in fields}
        
        for field in fields:
            actual_value = actual.get(field)
            expected_value = expected.get(field)
            
            if self._values_match(actual_value, expected_value):
                correct += 1
                field_results[field]['correct'] = 1
        
        return {
            'correct': correct,
            'total': total,
            'field_results': field_results
        }

    def _values_match(self, actual, expected) -> bool:
        """Check if actual and expected values match (with tolerance for numbers)"""
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False
        
        # Handle numeric values with tolerance
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return abs(actual - expected) <= 1  # Allow 1 unit tolerance
        
        # Handle string values
        if isinstance(actual, str) and isinstance(expected, str):
            return actual.lower() == expected.lower()
        
        # Handle partial string matches
        if isinstance(actual, str) and isinstance(expected, str):
            return expected.lower() in actual.lower() or actual.lower() in expected.lower()
        
        return actual == expected

    def _update_field_accuracy(self, field_accuracy: Dict, field_results: Dict):
        """Update field accuracy statistics"""
        for field, result in field_results.items():
            if field not in field_accuracy:
                field_accuracy[field] = {'correct': 0, 'total': 0}
            field_accuracy[field]['correct'] += result['correct']
            field_accuracy[field]['total'] += result['total']

if __name__ == '__main__':
    unittest.main() 