#!/usr/bin/env python3
"""
Test script for energy extraction functionality
"""

import sys
import os
# Add the parent directory to the path to import scrape module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.analyzer import StructuredAnalyzer
from bs4 import BeautifulSoup

def test_energy_extraction():
    """Test the energy extraction functionality"""
    print("🧪 Testing Energy Extraction Functionality")
    print("=" * 50)
    
    # Create scraper instance
    scraper = WillhabenScraper()
    
    # Test HWB extraction
    print("\n1. Testing HWB Value Extraction:")
    test_html_hwb = """
    <html>
    <body>
        <p>HWB (kWh/m²/Jahr): 29,4</p>
        <p>Heizwärmebedarf: 45.2 kWh/m²/a</p>
        <p>Heating demand: 67.8 kWh</p>
    </body>
    </html>
    """
    soup = BeautifulSoup(test_html_hwb, 'html.parser')
    hwb_value = scraper.extract_hwb_value(soup)
    print(f"   Extracted HWB: {hwb_value}")
    
    # Test fGEE extraction
    print("\n2. Testing fGEE Value Extraction:")
    test_html_fgee = """
    <html>
    <body>
        <p>fGEE: 0,9</p>
        <p>Gesamtenergieeffizienzfaktor: 1.2</p>
        <p>Overall energy efficiency factor: 0.75</p>
    </body>
    </html>
    """
    soup = BeautifulSoup(test_html_fgee, 'html.parser')
    fgee_value = scraper.extract_fgee_value(soup)
    print(f"   Extracted fGEE: {fgee_value}")
    
    # Test energy class calculation
    print("\n3. Testing Energy Class Calculation:")
    test_cases = [
        (29.4, 0.9, "Should be B (HWB-based)"),
        (8.5, 0.6, "Should be A+ (HWB-based)"),
        (120.0, 0.8, "Should be D (HWB-based)"),
        (15.0, 1.3, "Should be D (fGEE-based)"),
        (25.0, 0.5, "Should be A++ (fGEE-based)"),
        (None, 0.9, "Should be B (fGEE-based)"),
        (29.4, None, "Should be B (HWB-based)"),
        (None, None, "Should be None"),
        (25.0, 1.2, "Should be C (combined - fGEE worse)"),
        (80.0, 0.8, "Should be C (combined - HWB worse)"),
    ]
    
    for hwb, fgee, description in test_cases:
        energy_class = scraper.calculate_energy_class(hwb, fgee)
        print(f"   {description}: {energy_class}")
    
    print("\n✅ Energy extraction test completed!")

if __name__ == "__main__":
    test_energy_extraction() 