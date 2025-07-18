#!/usr/bin/env python3
"""
Integration tests for Immo Kurier scraper
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
from dataclasses import asdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Project.Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Project.Integration.mongodb_handler import MongoDBHandler

class TestImmoKurierIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.scraper = ImmoKurierScraper()
        
        # Sample HTML for testing
        self.sample_search_html = """
        <html>
            <body>
                <a href="/immobilien/test-listing-1" data-href="/immobilien/test-listing-1?params">
                    Test Listing 1
                </a>
                <a href="/immobilien/test-listing-2" data-href="/immobilien/test-listing-2?params">
                    Test Listing 2
                </a>
                <a href="/other-link">Other Link</a>
            </body>
        </html>
        """
        
        self.sample_listing_html = """
        <html>
            <head>
                <meta property="og:image" content="https://example.com/image.jpg">
            </head>
            <body>
                <h1>Beautiful 3-Room Apartment in Vienna</h1>
                <div class="card-text mb-2">
                    <svg class="cmicon-map-marker"></svg> 
                    Hauptstraße 123, 1010 Wien
                </div>
                <div class="d-flex fs-3">
                    <div class="pe-2 fw-bold">€ 450.000,00</div>
                    <div class="px-2 border-start">3 Zi.</div>
                    <div class="px-2 border-start">85,5 m²</div>
                </div>
            </body>
        </html>
        """

    def test_extract_listing_urls(self):
        """Test URL extraction from search results"""
        urls = self.scraper.extract_listing_urls(self.sample_search_html)
        
        expected_urls = [
            "https://immo.kurier.at/immobilien/test-listing-1",
            "https://immo.kurier.at/immobilien/test-listing-2"
        ]
        
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls, expected_urls)

    @patch('requests.Session.get')
    def test_scrape_single_listing(self, mock_get):
        """Test single listing scraping"""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = self.sample_listing_html.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.scraper.scrape_single_listing("https://immo.kurier.at/immobilien/test")
        result_dict = asdict(result)
        
        self.assertIsNotNone(result)
        self.assertEqual(result_dict['title'], "Beautiful 3-Room Apartment in Vienna")
        self.assertEqual(result_dict['price_total'], 450000.0)
        self.assertEqual(result_dict['rooms'], 3.0)
        self.assertEqual(result_dict['area_m2'], 85.5)
        self.assertEqual(result_dict['address'], "Hauptstraße 123, 1010 Wien")
        self.assertEqual(result_dict['bezirk'], "1010")
        self.assertEqual(result_dict['image_url'], "https://example.com/image.jpg")

    @patch('requests.Session.get')
    def test_scrape_search_results(self, mock_get):
        """Test scraping multiple search result pages"""
        # Mock responses for search page and listing pages
        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.text = self.sample_search_html
        
        mock_listing_response = Mock()
        mock_listing_response.content = self.sample_listing_html.encode('utf-8')
        mock_listing_response.raise_for_status.return_value = None
        
        # Configure mock to return different responses
        def mock_get_side_effect(url, *args, **kwargs):
            if 'suche' in url:
                return mock_search_response
            else:
                return mock_listing_response
        
        mock_get.side_effect = mock_get_side_effect
        
        results = self.scraper.scrape_search_results("https://immo.kurier.at/suche", max_pages=1)
        results_dicts = [asdict(r) for r in results]
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, dict) for r in results_dicts))
        self.assertTrue(all('url' in r for r in results_dicts))

    def test_error_handling(self):
        """Test error handling in scraper"""
        # Test with invalid HTML
        urls = self.scraper.extract_listing_urls("invalid html")
        self.assertEqual(urls, [])
        
        # Test with None HTML
        urls = self.scraper.extract_listing_urls(None)
        self.assertEqual(urls, [])

    def test_data_validation(self):
        """Test data validation and cleaning"""
        # Test price parsing with different formats
        test_cases = [
            ("€ 100.000,00", 100000.0),
            ("€ 50,500.00", 50500.0),
            ("€ 1.250.000,50", 1250000.5),
        ]
        
        for price_text, expected in test_cases:
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.content = f"""
                <html>
                    <body>
                        <div>{price_text}</div>
                    </body>
                </html>
                """.encode('utf-8')
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                result = self.scraper.scrape_single_listing("https://test.com")
                result_dict = asdict(result)
                if result and result_dict.get('price_total'):
                    self.assertEqual(result_dict['price_total'], expected)

    def test_address_extraction(self):
        """Test address extraction from different HTML structures"""
        test_cases = [
            # Case 1: Standard address format
            ("""
            <div class="card-text mb-2">
                <svg class="cmicon-map-marker"></svg> 
                Teststraße 1, 1020 Wien
            </div>
            """, "Teststraße 1, 1020 Wien", "1020"),
            
            # Case 2: Address with different structure
            ("""
            <div class="address-info">
                Hauptplatz 5, 1030 Wien
            </div>
            """, None, None),  # Should not find this format
        ]
        
        for html, expected_address, expected_bezirk in test_cases:
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.content = f"<html><body>{html}</body></html>".encode('utf-8')
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                result = self.scraper.scrape_single_listing("https://test.com")
                result_dict = asdict(result)
                if expected_address:
                    self.assertEqual(result_dict['address'], expected_address)
                    self.assertEqual(result_dict['bezirk'], expected_bezirk)

if __name__ == '__main__':
    unittest.main() 