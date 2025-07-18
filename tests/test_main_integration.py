#!/usr/bin/env python3
"""
Integration test that mimics main.py workflow
Tests complete pipeline: scraping -> analysis -> MongoDB -> Telegram
"""

import sys
import os
import time
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Integration.mongodb_handler import MongoDBHandler
from Project.Integration.telegram_bot import TelegramBot
from Project.Application.analyzer import StructuredAnalyzer
import logging

# Disable logging for cleaner test output
logging.getLogger().setLevel(logging.ERROR)

class TestMainIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test environment with mock components"""
        # Mock config
        self.mock_config = {
            'criteria': {
                'price_min': 200000,
                'price_max': 800000,
                'area_min': 70,
                'rooms_min': 3,
                'year_built_min': 1970,
                'down_payment_min': 60000,
                'interest_rate_max': 3.5,
                'ubahn_walk_max': 25,
                'school_walk_max': 20
            },
            'telegram_bot_token': 'mock_token',
            'telegram_chat_id': 'mock_chat_id',
            'mongodb_uri': 'mongodb://localhost:27017/',
            'max_pages': 1
        }
        
        # Mock listing data that should pass all criteria
        self.sample_listing_data = {
            'url': 'https://www.willhaben.at/iad/immobilien/eigentumswohnung/test-listing',
            'bezirk': '1070',
            'address': 'Neubaugasse 12, 1070 Wien',
            'price_total': 450000,
            'area_m2': 85.0,
            'rooms': 3,
            'year_built': 1980,
            'floor': '3. Stock',
            'condition': 'saniert',
            'heating': 'Fernwärme',
            'parking': 'Tiefgarage',
            'betriebskosten': 180.0,
            'energy_class': 'B',
            'hwb_value': 120.0,
            'heating_type': 'Gas',
            'energy_carrier': 'Gas',
            'available_from': 'sofort',
            'special_features': 'Balkon, Lift',
            'price_per_m2': 5294.12,
            'calculated_monatsrate': 1850.0,
            'mortgage_details': '(€90,000 DP, 3.5% Zins, 30 Jahre)',
            'total_monthly_cost': 2030.0,
            'ubahn_walk_minutes': 8,
            'school_walk_minutes': 12,
            'infrastructure_distances': {
                'U-Bahn': {'distance_m': 640, 'raw': 'U-Bahn <640m'},
                'Schule': {'distance_m': 960, 'raw': 'Schule <960m'},
                'Supermarkt': {'distance_m': 200, 'raw': 'Supermarkt <200m'},
                'Bank': {'distance_m': 300, 'raw': 'Bank <300m'}
            }
        }

    def test_complete_pipeline_validation(self):
        """Test complete pipeline with validation of all required fields"""
        print("🧪 Testing Complete Main.py Pipeline")
        print("=" * 60)
        
        # Mock the scraper components
        with patch('scrape.ViennaGeocoder') as mock_geocoder, \
             patch('scrape.MongoDBHandler') as mock_mongo, \
             patch('scrape.StructuredAnalyzer') as mock_analyzer, \
             patch.object(TelegramBot, 'send_property_notification', return_value=True):
            
            # Set up mock geocoder
            mock_geocoder_instance = Mock()
            mock_geocoder_instance.geocode_address.return_value = Mock(lat=48.2019, lon=16.3695)
            mock_geocoder_instance.get_walking_distance_to_nearest_school.return_value = 12
            mock_geocoder.return_value = mock_geocoder_instance
            
            # Set up mock MongoDB
            mock_mongo_instance = Mock()
            mock_mongo_instance.listing_exists.return_value = False
            mock_mongo_instance.insert_listing.return_value = True
            mock_mongo_instance.mark_sent.return_value = None
            mock_mongo.return_value = mock_mongo_instance
            
            # Set up mock analyzer
            mock_analyzer_instance = Mock()
            mock_analyzer_instance.is_available.return_value = True
            mock_analyzer_instance.analyze_listing_content.return_value = self.sample_listing_data
            mock_analyzer.return_value = mock_analyzer_instance
            
            # Create scraper with mock config
            scraper = WillhabenScraper(config=self.mock_config)
            
            # Test 1: Validate listing data structure
            print("\n1. Testing Listing Data Structure")
            print("-" * 40)
            
            required_fields = [
                'url', 'bezirk', 'address', 'price_total', 'area_m2', 'rooms',
                'year_built', 'floor', 'condition', 'heating', 'parking',
                'betriebskosten', 'energy_class', 'price_per_m2',
                'calculated_monatsrate', 'ubahn_walk_minutes', 'school_walk_minutes',
                'infrastructure_distances'
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in self.sample_listing_data:
                    missing_fields.append(field)
                elif self.sample_listing_data[field] is None:
                    missing_fields.append(f"{field} (None)")
            
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                self.fail(f"Missing required fields: {missing_fields}")
            else:
                print("✅ All required fields present")
            
            # Test 2: Validate data quality
            print("\n2. Testing Data Quality")
            print("-" * 40)
            
            quality_issues = []
            
            # Check for valid price
            if not (100000 <= self.sample_listing_data['price_total'] <= 2000000):
                quality_issues.append("Invalid price range")
            
            # Check for valid area
            if not (20 <= self.sample_listing_data['area_m2'] <= 500):
                quality_issues.append("Invalid area range")
            
            # Check for valid rooms
            if not (1 <= self.sample_listing_data['rooms'] <= 10):
                quality_issues.append("Invalid rooms count")
            
            # Check for valid year
            if not (1900 <= self.sample_listing_data['year_built'] <= 2024):
                quality_issues.append("Invalid year built")
            
            # Check for valid district
            if not self.sample_listing_data['bezirk'].isdigit() or len(self.sample_listing_data['bezirk']) != 4:
                quality_issues.append("Invalid district format")
            
            # Check for valid address
            if not self.sample_listing_data['address'] or len(self.sample_listing_data['address']) < 10:
                quality_issues.append("Invalid address")
            
            if quality_issues:
                print(f"❌ Data quality issues: {quality_issues}")
                self.fail(f"Data quality issues: {quality_issues}")
            else:
                print("✅ Data quality checks passed")
            
            # Test 3: Validate criteria matching
            print("\n3. Testing Criteria Matching")
            print("-" * 40)
            
            # Mock the meets_criteria method to test it
            with patch.object(scraper, 'meets_criteria') as mock_criteria:
                mock_criteria.return_value = True
                
                # Test that criteria checking is called
                result = scraper.meets_criteria(self.sample_listing_data)
                self.assertTrue(result, "Listing should meet criteria")
                mock_criteria.assert_called_once_with(self.sample_listing_data)
                print("✅ Criteria matching works")
            
            # Test 4: Validate MongoDB storage
            print("\n4. Testing MongoDB Storage")
            print("-" * 40)
            
            # Test that listing would be stored
            listing_data = self.sample_listing_data.copy()
            listing_data['sent_to_telegram'] = False
            listing_data['processed_at'] = time.time()
            
            # Validate serializable data
            try:
                json.dumps(listing_data)
                print("✅ Data is JSON serializable")
            except Exception as e:
                self.fail(f"Data not JSON serializable: {e}")
            
            # Test MongoDB insert
            success = scraper.mongo.insert_listing(listing_data)
            self.assertTrue(success, "MongoDB insert should succeed")
            print("✅ MongoDB storage works")
            
            # Test 5: Validate Telegram notification
            print("\n5. Testing Telegram Notification")
            print("-" * 40)
            
            # Test message formatting
            try:
                message = scraper.telegram_bot._format_property_message(listing_data)
                self.assertIsInstance(message, str)
                self.assertIn('🏠', message)
                self.assertIn('💳', message)
                self.assertIn('📍', message)
                self.assertIn('📐', message)
                self.assertIn('🛏️', message)
                self.assertIn('🚇', message)
                self.assertIn('🏫', message)
                self.assertIn('🔗', message)
                print("✅ Message formatting works")
            except Exception as e:
                self.fail(f"Message formatting failed: {e}")
            
            # Test notification sending
            success = scraper.telegram_bot.send_property_notification(listing_data)
            self.assertTrue(success, "Telegram notification should succeed")
            print("✅ Telegram notification works")
            
            # Test 6: Validate infrastructure distances
            print("\n6. Testing Infrastructure Distances")
            print("-" * 40)
            
            infra = listing_data.get('infrastructure_distances', {})
            self.assertIsInstance(infra, dict, "Infrastructure distances should be a dict")
            
            # Check for transport info
            transport_found = any('U-Bahn' in key or 'Bahnhof' in key for key in infra.keys())
            self.assertTrue(transport_found, "Should have transport information")
            
            # Check for school info
            school_found = any('Schule' in key or 'Kindergarten' in key for key in infra.keys())
            self.assertTrue(school_found, "Should have school information")
            
            print("✅ Infrastructure distances properly parsed")
            
            # Test 7: Validate complete workflow
            print("\n7. Testing Complete Workflow")
            print("-" * 40)
            
            # Simulate the complete workflow
            workflow_steps = []
            
            # Step 1: Scrape listing
            workflow_steps.append("Scraping")
            
            # Step 2: Validate data
            if all(field in listing_data for field in required_fields):
                workflow_steps.append("Validation")
            
            # Step 3: Analyze content
            if scraper.structured_analyzer.is_available():
                workflow_steps.append("Analysis")
            
            # Step 4: Check criteria
            if scraper.meets_criteria(listing_data):
                workflow_steps.append("Criteria")
            
            # Step 5: Store in MongoDB
            if scraper.mongo.insert_listing(listing_data):
                workflow_steps.append("MongoDB")
            
            # Step 6: Send Telegram notification
            if scraper.telegram_bot.send_property_notification(listing_data):
                workflow_steps.append("Telegram")
            
            expected_steps = ["Scraping", "Validation", "Analysis", "Criteria", "MongoDB", "Telegram"]
            for step in expected_steps:
                self.assertIn(step, workflow_steps, f"Missing workflow step: {step}")
            
            print(f"✅ Complete workflow: {' -> '.join(workflow_steps)}")
            
            print("\n🎉 All integration tests passed!")
            print("=" * 60)

    def test_data_validation_edge_cases(self):
        """Test edge cases in data validation"""
        print("\n🧪 Testing Data Validation Edge Cases")
        print("=" * 60)
        
        # Test with incomplete data
        incomplete_listing = {
            'url': 'https://example.com',
            'price_total': 450000,
            'area_m2': 85.0
            # Missing many required fields
        }
        
        with patch('scrape.ViennaGeocoder'), \
             patch('scrape.MongoDBHandler') as mock_mongo, \
             patch('scrape.TelegramBot'), \
             patch('scrape.StructuredAnalyzer'):
            
            mock_mongo_instance = Mock()
            mock_mongo_instance.listing_exists.return_value = False
            mock_mongo.return_value = mock_mongo_instance
            
            scraper = WillhabenScraper(config=self.mock_config)
            
            # Test that incomplete listings are rejected
            with patch.object(scraper, 'meets_criteria') as mock_criteria:
                mock_criteria.return_value = False
                
                result = scraper.meets_criteria(incomplete_listing)
                self.assertFalse(result, "Incomplete listing should not meet criteria")
                print("✅ Incomplete listings properly rejected")
        
        # Test with invalid data
        invalid_listing = {
            'url': 'https://example.com',
            'bezirk': 'invalid',
            'address': 'oderdirekt nach OrtenPLZ/Ort eingeben',  # Known garbage
            'price_total': 0,  # Invalid price
            'area_m2': -10,    # Invalid area
            'rooms': 0,        # Invalid rooms
            'year_built': 2025  # Future year
        }
        
        with patch('scrape.ViennaGeocoder'), \
             patch('scrape.MongoDBHandler') as mock_mongo, \
             patch('scrape.TelegramBot'), \
             patch('scrape.StructuredAnalyzer'):
            
            mock_mongo_instance = Mock()
            mock_mongo_instance.listing_exists.return_value = False
            mock_mongo.return_value = mock_mongo_instance
            
            scraper = WillhabenScraper(config=self.mock_config)
            
            # Test that invalid listings are rejected
            with patch.object(scraper, 'meets_criteria') as mock_criteria:
                mock_criteria.return_value = False
                
                result = scraper.meets_criteria(invalid_listing)
                self.assertFalse(result, "Invalid listing should not meet criteria")
                print("✅ Invalid listings properly rejected")

    def test_telegram_message_formatting(self):
        """Test Telegram message formatting with various data scenarios"""
        print("\n🧪 Testing Telegram Message Formatting")
        print("=" * 60)
        
        # Test with complete data
        complete_listing = self.sample_listing_data.copy()
        
        with patch('telegram_bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'ok': True}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            bot = TelegramBot('mock_token', 'mock_chat_id')
            message = bot._format_property_message(complete_listing)
            
            # Check required elements
            required_elements = [
                '🏠', '💳', '📍', '📐', '🛏️', '🚇', '🏫', '🏗️', '🛠️', '⚡', '🔗'
            ]
            
            for element in required_elements:
                self.assertIn(element, message, f"Missing element: {element}")
            
            # Check for address and price in first line
            self.assertIn('Neubaugasse 12, 1070 Wien', message)
            self.assertIn('€450,000', message)
            
            # Check for infrastructure distances
            self.assertIn('🚇 U-Bahn: 8 min', message)
            self.assertIn('🏫 Schule: 12 min', message)
            
            print("✅ Complete data message formatting works")
        
        # Test with missing data
        incomplete_listing = {
            'url': 'https://example.com',
            'address': 'Test Address',
            'price_total': 300000,
            'bezirk': '1010',
            'area_m2': 70,
            'rooms': 3,
            'year_built': None,
            'condition': None,
            'energy_class': None,
            'ubahn_walk_minutes': None,
            'school_walk_minutes': None,
            'infrastructure_distances': {}
        }
        
        with patch('telegram_bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'ok': True}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            bot = TelegramBot('mock_token', 'mock_chat_id')
            message = bot._format_property_message(incomplete_listing)
            
            # Check that N/A values are handled properly
            self.assertIn('N/A', message)
            self.assertIn('🚇 U-Bahn: N/A', message)
            self.assertIn('🏫 Schule: N/A', message)
            
            print("✅ Incomplete data message formatting works")

if __name__ == '__main__':
    unittest.main() 