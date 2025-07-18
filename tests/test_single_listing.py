#!/usr/bin/env python3
"""
Test script to analyze a single listing with structured output
"""

import sys
import json
import requests
from bs4 import BeautifulSoup
from Project.Application.analyzer import StructuredAnalyzer, OllamaAnalyzer
import unittest

class TestSingleListing(unittest.TestCase):
    def test_fetch_listing_data(self):
        """Fetch and parse basic listing data"""
        test_url = "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1030-landstrasse/wohnung-mit-potenzial-in-naehe-schloss-belvedere-rennweg-1305784468/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(test_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Create basic listing data structure
            listing_data = {
                'url': test_url,
                'bezirk': '1030',  # Example
                'price_total': 339000,
                'area_m2': 73,
                'rooms': 3,
                'address': 'Dietrichgasse, 1030 Wien',
                'year_built': None,
                'floor': None,
                'condition': None,
                'heating': None,
                'parking': None,
                'monatsrate': None,
                'own_funds': None,
                'betriebskosten': None
            }
            
            return listing_data, response.text
            
        except Exception as e:
            print(f"❌ Error fetching {test_url}: {e}")
            return None, None

if __name__ == '__main__':
    unittest.main() 