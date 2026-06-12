"""Mortgage payment math used by all property scrapers.

Single source of truth for the Austrian mortgage annuity formula
(loan amount, monthly payment, interest rate estimate, breakdown).
Replaces the previous per-scraper duplicate of ``MortgageCalculator``.
"""
from typing import Dict


class MortgageCalculator:
    """Calculate mortgage payments using standard financial formulas"""

    @staticmethod
    def calculate_monthly_payment(loan_amount: float, annual_rate: float, years: int, include_fees: bool = True) -> float:
        """
        Calculate monthly mortgage payment using standard annuity formula.
        M = L * r*(1+r)^n / ((1+r)^n - 1)
        """
        if loan_amount <= 0:
            return 0

        r = (annual_rate / 100) / 12
        n = years * 12

        if r == 0:
            return round(loan_amount / n, 2)

        factor = (1 + r) ** n
        monthly_payment = loan_amount * r * factor / (factor - 1)

        return round(monthly_payment, 2)

    @staticmethod
    def calculate_loan_amount(purchase_price: float, down_payment: float) -> float:
        """Calculate loan amount after down payment"""
        return max(0, purchase_price - down_payment)

    @staticmethod
    def estimate_interest_rate(year: int = 2024) -> float:
        """Estimate current Austrian mortgage interest rates"""
        # Current Austrian mortgage rates (as of 2024)
        # These can be updated based on current market conditions
        base_rates = {
            2024: 3.5,  # Current rates
            2023: 4.2,
            2022: 2.8,
            2021: 1.5
        }
        return base_rates.get(year, 3.5)  # Default to 3.5% if year not found

    @staticmethod
    def get_payment_breakdown(loan_amount: float, annual_rate: float, years: int) -> Dict:
        """Get detailed breakdown of monthly payment components using annuity formula"""
        if loan_amount <= 0:
            return {}

        r = (annual_rate / 100) / 12
        n = years * 12

        if r == 0:
            monthly_payment = loan_amount / n
        else:
            factor = (1 + r) ** n
            monthly_payment = loan_amount * r * factor / (factor - 1)

        return {
            'base_payment': round(monthly_payment, 2),
            'total_monthly': round(monthly_payment, 2),
            'loan_amount': round(loan_amount, 2),
            'interest_rate': annual_rate,
            'years': years,
            'life_insurance': 0.0,
            'property_insurance': 0.0,
            'admin_fees': 0.0,
        }
