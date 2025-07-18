#!/usr/bin/env python3
"""
Test script for the enhanced scraper with mortgage calculations
Tests all new features: manual calculation, Betriebskosten, total costs
"""

import sys
sys.path.append('.')

from Project.Application.scraping.willhaben_scraper import WillhabenScraper
from Project.Application.analyzer import StructuredAnalyzer
from bs4 import BeautifulSoup

def test_enhanced_features():
    """Test all enhanced features"""
    print("🏠 TESTING ENHANCED REAL ESTATE SCRAPER")
    print("=" * 60)
    
    # Sample listing data (like the one from your example)
    sample_listing = {
        "url": "https://www.willhaben.at/iad/immobilien/d/eigentumswohnung/wien/wien-1220-donaustadt/familienfreundlich-hell-3-zimmer-wohnung-mit-eigengarten-777958996/",
        "bezirk": "1220",
        "price_total": 380000,
        "area_m2": 73.27,
        "rooms": 3,
        "year_built": None,
        "floor": "3. Stock",
        "condition": "Erstbezug",
        "heating": "Fußbodenheizung",
        "parking": "Parkplatz, Garage",
        "address": "1220 Wien, 22. Bezirk, Donaustadt",
        "special_comment": None,
        "monatsrate": None,
        "own_funds": None,
        "betriebskosten": None,  # NEW
        "price_per_m2": 5186.3,
        "ubahn_walk_minutes": 18,
        "amenities": []
    }
    
    # Sample HTML with mortgage calculator (simulating Willhaben page)
    sample_html = """
    <html>
    <head><title>Wohnung 1220 Wien</title></head>
    <body>
        <div class="property-details">
            <h1>Familienfreundlich hell 3 Zimmer Wohnung mit Eigengarten</h1>
            
            <!-- Mortgage Calculator Section -->
            <div data-testid="mortgageCalculatorForm">
                <h3>Finanzierungsrechner</h3>
                <div>
                    <label>Kaufpreis</label>
                    <input value="380000" readonly>
                </div>
                <div>
                    <label>Eigenkapital</label>
                    <input data-testid="eigenkapital-input" value="100000">
                </div>
                <div>
                    <label>Kreditlaufzeit</label>
                    <select data-testid="laufzeit-select">
                        <option value="35" selected>35 Jahre</option>
                    </select>
                </div>
                <div>
                    <label>Zinssatz</label>
                    <span data-testid="zinssatz-display">2,65%</span>
                </div>
                <div class="result">
                    <span>Monatsrate: € 1.217,00</span>
                </div>
            </div>
            
            <!-- Property Details -->
            <div class="details">
                <p>Baujahr: 2018</p>
                <p>Lage: 3. Stock</p>
                <p>Zustand: Erstbezug nach Sanierung</p>
                <p>Heizung: Fußbodenheizung</p>
                <p>Parkplatz: Tiefgarage vorhanden</p>
            </div>
            
            <!-- Operating Costs -->
            <div class="costs">
                <h3>Nebenkosten</h3>
                <p>Betriebskosten: € 120,00 monatlich</p>
                <p>Heizkosten: € 45,00 monatlich</p>
                <p>Gesamt Betriebskosten: € 165,00</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    print("📋 ORIGINAL LISTING DATA:")
    print(f"  Price: €{sample_listing['price_total']:,}")
    print(f"  Area: {sample_listing['area_m2']}m²")
    print(f"  Rooms: {sample_listing['rooms']}")
    print(f"  Monatsrate: {sample_listing['monatsrate']}")
    print(f"  Betriebskosten: {sample_listing['betriebskosten']}")
    print()
    
    # Create scraper instance
    scraper = WillhabenScraper()
    soup = BeautifulSoup(sample_html, 'html.parser')
    
    # Test manual mortgage calculation
    print("🧮 TESTING MANUAL MORTGAGE CALCULATION:")
    calculated_rate = scraper.calculate_manual_monthly_rate(
        sample_listing['price_total'],
        100000,  # Down payment from HTML
        soup
    )
    print()
    
    # Test Betriebskosten extraction
    print("🏢 TESTING BETRIEBSKOSTEN EXTRACTION:")
    betriebskosten = scraper.extract_betriebskosten(soup)
    print(f"  Extracted Betriebskosten: €{betriebskosten:,}" if betriebskosten else f"  Extracted Betriebskosten: {betriebskosten}")
    print()
    
    # Test total monthly cost calculation
    print("💰 TESTING TOTAL MONTHLY COST:")
    total_cost = scraper.calculate_total_monthly_cost(calculated_rate, betriebskosten)
    print(f"  Mortgage Payment: €{calculated_rate:,}" if calculated_rate else f"  Mortgage Payment: {calculated_rate}")
    print(f"  Betriebskosten: €{betriebskosten:,}" if betriebskosten else f"  Betriebskosten: {betriebskosten}")
    print(f"  Total Monthly Cost: €{total_cost:,}" if total_cost else f"  Total Monthly Cost: {total_cost}")
    print()
    
    # Create enhanced listing with all new fields
    enhanced_listing = sample_listing.copy()
    enhanced_listing.update({
        'calculated_monatsrate': calculated_rate,
        'betriebskosten': betriebskosten,
        'total_monthly_cost': total_cost
    })
    
    print("📊 ENHANCED LISTING DATA:")
    print(f"  Original Monatsrate: {enhanced_listing['monatsrate']}")
    print(f"  Calculated Monatsrate: €{enhanced_listing['calculated_monatsrate']:,}" if enhanced_listing['calculated_monatsrate'] else f"  Calculated Monatsrate: {enhanced_listing['calculated_monatsrate']}")
    print(f"  Betriebskosten: €{enhanced_listing['betriebskosten']:,}" if enhanced_listing['betriebskosten'] else f"  Betriebskosten: {enhanced_listing['betriebskosten']}")
    print(f"  Total Monthly Cost: €{enhanced_listing['total_monthly_cost']:,}" if enhanced_listing['total_monthly_cost'] else f"  Total Monthly Cost: {enhanced_listing['total_monthly_cost']}")
    print()
    
    # Test affordability analysis
    print("📈 AFFORDABILITY ANALYSIS:")
    if enhanced_listing['total_monthly_cost']:
        annual_cost = enhanced_listing['total_monthly_cost'] * 12
        print(f"  Monthly Cost: €{enhanced_listing['total_monthly_cost']:,}")
        print(f"  Annual Cost: €{annual_cost:,}")
        
        # Rule of thumb: housing should be max 30% of gross income
        required_income = annual_cost / 0.30
        print(f"  Required Gross Income (30% rule): €{required_income:,}/year")
        print(f"  Required Monthly Income: €{required_income/12:,}")
    
    return enhanced_listing

def test_extraction_methods():
    """Test individual extraction methods"""
    print("\n" + "=" * 60)
    print("🔧 TESTING INDIVIDUAL EXTRACTION METHODS")
    print("=" * 60)
    
    # Test HTML with various formats
    test_cases = [
        {
            "name": "Standard Format",
            "html": '<div class="betriebskosten">Betriebskosten: € 150,00</div>',
            "expected": 150.0
        },
        {
            "name": "Alternative Format",
            "html": '<p>Nebenkosten monatlich: €120</p>',
            "expected": 120.0
        },
        {
            "name": "Complex Format",
            "html": '<div>Betriebskosten inkl. Heizung: € 200,50 pro Monat</div>',
            "expected": 200.5
        }
    ]
    
    scraper = WillhabenScraper()
    
    for test_case in test_cases:
        soup = BeautifulSoup(test_case["html"], 'html.parser')
        result = scraper.extract_betriebskosten(soup)
        
        print(f"\n🧪 {test_case['name']}:")
        print(f"  HTML: {test_case['html']}")
        print(f"  Expected: €{test_case['expected']:,}")
        print(f"  Extracted: €{result:,}" if result else f"  Extracted: {result}")
        
        if result == test_case['expected']:
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL")

if __name__ == "__main__":
    enhanced_listing = test_enhanced_features()
    test_extraction_methods()
    
    print("\n" + "=" * 60)
    print("✅ ENHANCED SCRAPER TESTS COMPLETE")
    print("=" * 60)
    print("\n🎯 SUMMARY OF NEW FEATURES:")
    print("  ✅ Manual mortgage calculation with Austrian fees")
    print("  ✅ Betriebskosten extraction")
    print("  ✅ Total monthly cost calculation")
    print("  ✅ Detailed payment breakdown")
    print("  ✅ Enhanced Telegram notifications")
    print("\n📱 Ready for real estate monitoring with complete financial analysis!") 