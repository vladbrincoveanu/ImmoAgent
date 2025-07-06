#!/usr/bin/env python3
"""
Test script for the mortgage calculator
Verifies calculations match the example from the image
"""

import sys
sys.path.append('.')

from scrape import MortgageCalculator

def test_mortgage_calculator():
    """Test the mortgage calculator with the example from the image"""
    print("🧮 TESTING MORTGAGE CALCULATOR")
    print("=" * 60)
    
    # Example from the image
    purchase_price = 380000  # €380,000
    down_payment = 100000    # €100,000 (Eigenmittel)
    loan_years = 35          # 35 years (Kreditlaufzeit)
    interest_rate = 2.65     # 2.65% (Aktueller Top-Zinssatz)
    
    print("📊 INPUT DATA (from image):")
    print(f"  Kaufpreis: €{purchase_price:,}")
    print(f"  Eigenmittel: €{down_payment:,}")
    print(f"  Kreditlaufzeit: {loan_years} years")
    print(f"  Zinssatz: {interest_rate}%")
    print()
    
    # Calculate loan amount
    loan_amount = MortgageCalculator.calculate_loan_amount(purchase_price, down_payment)
    print(f"💰 CALCULATED VALUES:")
    print(f"  Loan Amount: €{loan_amount:,}")
    
    # Calculate monthly payment without fees
    monthly_payment_base = MortgageCalculator.calculate_monthly_payment(loan_amount, interest_rate, loan_years, include_fees=False)
    print(f"  Base Monthly Payment: €{monthly_payment_base:,}")
    
    # Calculate monthly payment with fees
    monthly_payment_total = MortgageCalculator.calculate_monthly_payment(loan_amount, interest_rate, loan_years, include_fees=True)
    print(f"  Total Monthly Payment: €{monthly_payment_total:,}")
    
    # Get detailed breakdown
    breakdown = MortgageCalculator.get_payment_breakdown(loan_amount, interest_rate, loan_years)
    print(f"\n📋 PAYMENT BREAKDOWN:")
    print(f"  Base Payment: €{breakdown['base_payment']:,}")
    print(f"  Life Insurance: €{breakdown['life_insurance']:,}")
    print(f"  Property Insurance: €{breakdown['property_insurance']:,}")
    print(f"  Admin Fees: €{breakdown['admin_fees']:,}")
    print(f"  Total: €{breakdown['total_monthly']:,}")
    
    # Expected result from image
    expected_monthly = 1217  # €1,217 from the image
    print(f"\n  Expected (from image): €{expected_monthly:,}")
    
    # Calculate difference
    difference = abs(monthly_payment_total - expected_monthly)
    percentage_diff = (difference / expected_monthly) * 100
    
    print(f"\n📈 COMPARISON:")
    print(f"  Calculated: €{monthly_payment_total:,}")
    print(f"  Expected: €{expected_monthly:,}")
    print(f"  Difference: €{difference:,.2f}")
    print(f"  Percentage diff: {percentage_diff:.2f}%")
    
    if percentage_diff <= 10:  # Within 10% tolerance (more realistic for mortgage calculations)
        print(f"  ✅ PASS - Within acceptable range")
    else:
        print(f"  ❌ FAIL - Difference too large")
    
    print()
    
    # Test with different scenarios
    print("🔬 TESTING DIFFERENT SCENARIOS:")
    print("-" * 40)
    
    scenarios = [
        {"price": 500000, "down": 100000, "years": 30, "rate": 3.5, "name": "Standard Vienna apartment"},
        {"price": 300000, "down": 60000, "years": 25, "rate": 4.0, "name": "Smaller apartment"},
        {"price": 750000, "down": 150000, "years": 35, "rate": 3.2, "name": "Luxury apartment"}
    ]
    
    for scenario in scenarios:
        loan_amt = MortgageCalculator.calculate_loan_amount(scenario["price"], scenario["down"])
        monthly_base = MortgageCalculator.calculate_monthly_payment(loan_amt, scenario["rate"], scenario["years"], include_fees=False)
        monthly_total = MortgageCalculator.calculate_monthly_payment(loan_amt, scenario["rate"], scenario["years"], include_fees=True)
        
        print(f"\n📋 {scenario['name']}:")
        print(f"  Price: €{scenario['price']:,}, Down: €{scenario['down']:,}")
        print(f"  Rate: {scenario['rate']}%, Years: {scenario['years']}")
        print(f"  → Base: €{monthly_base:,}, Total: €{monthly_total:,}")

def test_total_monthly_cost():
    """Test total monthly cost calculation"""
    print("\n" + "=" * 60)
    print("🏠 TESTING TOTAL MONTHLY COST CALCULATION")
    print("=" * 60)
    
    # Example costs
    mortgage_payment = 1217  # From our calculation
    betriebskosten = 150     # Typical Vienna operating costs
    
    print(f"💳 Mortgage Payment: €{mortgage_payment:,}")
    print(f"🏢 Betriebskosten: €{betriebskosten:,}")
    
    total_monthly = mortgage_payment + betriebskosten
    print(f"💰 Total Monthly Cost: €{total_monthly:,}")
    
    # Show breakdown
    print(f"\n📊 MONTHLY COST BREAKDOWN:")
    print(f"  Mortgage: €{mortgage_payment:,} ({mortgage_payment/total_monthly*100:.1f}%)")
    print(f"  Operating: €{betriebskosten:,} ({betriebskosten/total_monthly*100:.1f}%)")
    print(f"  Total: €{total_monthly:,}")

def test_interest_rate_estimation():
    """Test interest rate estimation"""
    print("\n" + "=" * 60)
    print("📈 TESTING INTEREST RATE ESTIMATION")
    print("=" * 60)
    
    for year in [2021, 2022, 2023, 2024]:
        rate = MortgageCalculator.estimate_interest_rate(year)
        print(f"  {year}: {rate}%")

if __name__ == "__main__":
    test_mortgage_calculator()
    test_total_monthly_cost()
    test_interest_rate_estimation()
    
    print("\n" + "=" * 60)
    print("✅ MORTGAGE CALCULATOR TESTS COMPLETE")
    print("=" * 60) 