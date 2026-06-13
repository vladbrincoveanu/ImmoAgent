"""Mortgage payment math used by all property scrapers.

Single source of truth for the Austrian mortgage annuity formula
(loan amount, monthly payment, interest rate estimate, breakdown).
Replaces the previous per-scraper duplicate of ``MortgageCalculator``.
"""
import logging
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


# Austrian mortgage assumptions baked into the listing schema.
# €1,166 monthly rate for €304,570 loan at 2.89% for 35 years
# gives a ratio of approximately 0.00383 — preserved from the
# pre-MortgageCalculator era for output stability.
_DEFAULT_ANNUAL_RATE = 2.89
_DEFAULT_YEARS = 35
_MONTHLY_RATIO = 0.00383
_DOWN_PAYMENT_FRACTION = 0.20
_FEE_UPLIFT = 1.10


def add_monthly_payment_calculation(listing: Dict) -> None:
    """
    Mutate ``listing`` in place with monthly payment, mortgage details, and a
    negative-score clamp. Pure function — does not touch Mongo or ``self``.

    Austrian assumptions (10% fee uplift, 20% down, 2.89% / 35y, 0.00383 ratio)
    are preserved verbatim from the original MongoDBHandler method so the
    downstream ``run_top5``/Telegram fields stay byte-identical.
    """
    try:
        betriebskosten = listing.get('betriebskosten', 0) or 0
        price_total = listing.get('price_total', 0) or 0

        if not isinstance(betriebskosten, (int, float)):
            betriebskosten = 0
        if not isinstance(price_total, (int, float)):
            price_total = 0

        if price_total > 0:
            adjusted_price = price_total * _FEE_UPLIFT
            down_payment = adjusted_price * _DOWN_PAYMENT_FRACTION
            loan_amount = adjusted_price - down_payment
            monthly_loan_payment = loan_amount * _MONTHLY_RATIO
            total_monthly = monthly_loan_payment + betriebskosten

            listing['monthly_payment'] = {
                'loan_payment': monthly_loan_payment,
                'betriebskosten': betriebskosten,
                'total_monthly': total_monthly,
                'loan_amount': loan_amount,
                'down_payment': down_payment,
                'adjusted_price': adjusted_price
            }
            listing['calculated_monatsrate'] = monthly_loan_payment
            listing['total_monthly_cost'] = total_monthly
            listing['mortgage_details'] = {
                'loan_amount': loan_amount,
                'annual_rate': _DEFAULT_ANNUAL_RATE,
                'years': _DEFAULT_YEARS,
                'monthly_payment': monthly_loan_payment,
                'down_payment': down_payment,
                'adjusted_price': adjusted_price
            }
        else:
            listing['monthly_payment'] = {
                'loan_payment': 0,
                'betriebskosten': betriebskosten,
                'total_monthly': betriebskosten,
                'loan_amount': 0,
                'down_payment': 0,
                'adjusted_price': 0
            }
            listing['calculated_monatsrate'] = 0
            listing['total_monthly_cost'] = betriebskosten
            listing['mortgage_details'] = {
                'loan_amount': 0,
                'annual_rate': _DEFAULT_ANNUAL_RATE,
                'years': _DEFAULT_YEARS,
                'monthly_payment': 0,
                'down_payment': 0,
                'adjusted_price': 0
            }

        score = listing.get('score', 0)
        if score is not None and score < 0:
            listing['score'] = max(0.0, score)
            logging.info(f"Fixed negative score from {score} to {listing['score']}")

    except Exception as e:
        logging.error(f"Error calculating monthly payment for listing: {e}")
        fallback_bk = listing.get('betriebskosten', 0) or 0
        listing['monthly_payment'] = {
            'loan_payment': 0,
            'betriebskosten': fallback_bk,
            'total_monthly': fallback_bk,
            'loan_amount': 0,
            'down_payment': 0,
            'adjusted_price': 0
        }
        listing['calculated_monatsrate'] = 0
        listing['total_monthly_cost'] = fallback_bk
