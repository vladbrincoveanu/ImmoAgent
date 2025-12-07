#!/usr/bin/env python3
"""
Script to fetch top 5 listings from MongoDB and send to Telegram main channel
"""

import argparse
import sys
import os
import logging
import time
from datetime import datetime
import numpy as np
import random
from typing import Dict, Any, Optional, List

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Robust config.json search logic (same as run.py, plus CI/CD paths)
def ensure_config_json_on_path():
    possible_paths = [
        os.path.join(project_root, 'config.json'),
        os.path.join(os.path.dirname(project_root), 'config.json'),
        os.path.join(project_root, 'Project', 'config.json'),
        os.path.join(project_root, '..', 'config.json'),
        os.path.join(project_root, '..', 'Project', 'config.json'),
        '/home/runner/work/ImmoAgent/ImmoAgent/config.json',
        '/home/runner/work/ImmoAgent/ImmoAgent/Project/config.json',
        '/home/runner/work/ImmoAgent/ImmoAgent/Project/../config.json',
        '/home/runner/work/ImmoAgent/config.json',
        '/home/runner/work/ImmoAgent/Project/config.json',
        '/home/runner/work/ImmoAgent/Project/../config.json',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            # Set CWD to the directory containing config.json
            os.chdir(os.path.dirname(path))
            print(f"✅ Found config.json at: {path}")
            break

ensure_config_json_on_path()

from Application.helpers.utils import load_config
from Application.helpers.listing_validator import filter_valid_listings, get_validation_stats
from Application.buyer_profiles import BuyerPersona
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

DEFAULT_RENT_BENCHMARKS: Dict[str, float] = {
    # Approximate warm rent €/m² baselines by district; override via config if available
    '1010': 22.0, '1020': 17.0, '1030': 16.5, '1040': 16.5, '1050': 15.5,
    '1060': 17.0, '1070': 17.5, '1080': 18.0, '1090': 18.0, '1100': 14.0,
    '1110': 13.8, '1120': 14.5, '1130': 16.0, '1140': 13.5, '1150': 14.0,
    '1160': 13.5, '1170': 14.0, '1180': 17.0, '1190': 17.5, '1200': 13.5,
    '1210': 13.0, '1220': 13.8, '1230': 12.8,
    'default': 13.5,
}


def buyer_persona_type(value: str) -> BuyerPersona:
    """argparse helper to coerce user input into a BuyerPersona."""
    try:
        return BuyerPersona.from_value(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI flags for the Top5 report."""
    parser = argparse.ArgumentParser(
        description="Send the Top5 (or TopN) property report to Telegram"
    )
    parser.add_argument(
        "--buyer-profile",
        help="Buyer profile key (e.g. budget_buyer, retiree). Overrides config and persona.",
    )
    parser.add_argument(
        "--buyer-persona",
        "--persona",
        dest="buyer_persona",
        type=buyer_persona_type,
        help="Buyer persona enum shortcut (owner_occupier, diy_renovator, etc.)",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Weekly digest mode (top 10, allow resends).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Override how many listings to send (default 5, or 10 in weekly mode).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        help="Minimum listing score to consider.",
    )
    parser.add_argument(
        "--min-rooms",
        type=int,
        help="Minimum room count to consider.",
    )
    parser.add_argument(
        "--pool-size",
        type=int,
        help="Number of listings to pull from Mongo before filtering (default 150).",
    )
    parser.add_argument(
        "--candidate-pool",
        type=int,
        help="Number of high quality listings to consider before sampling (default 50).",
    )
    parser.add_argument(
        "--exclude-district",
        dest="exclude_districts",
        action="append",
        help="District code to exclude. Pass multiple times for several districts.",
    )
    parser.add_argument(
        "--include-investment-analysis",
        dest="include_investment_analysis",
        action="store_true",
        help="Force-enable investment analysis calculations.",
    )
    parser.add_argument(
        "--skip-investment-analysis",
        dest="include_investment_analysis",
        action="store_false",
        help="Disable investment analysis calculations.",
    )
    parser.add_argument(
        "--include-monthly-payment",
        dest="include_monthly_payment",
        action="store_true",
        help="Force monthly payment calculations.",
    )
    parser.add_argument(
        "--skip-monthly-payment",
        dest="include_monthly_payment",
        action="store_false",
        help="Disable monthly payment calculations.",
    )
    parser.set_defaults(
        include_investment_analysis=None,
        include_monthly_payment=None,
        buyer_persona=None,
    )
    return parser.parse_args(argv)


def normalize_district_code(bezirk: Optional[Any]) -> str:
    """Normalize district codes to a consistent string format."""
    if bezirk is None:
        return ""
    bezirk_str = str(bezirk).strip()
    if bezirk_str.isdigit() and len(bezirk_str) == 3:
        return bezirk_str.zfill(4)
    return bezirk_str


def ensure_price_metrics(listing: Dict[str, Any]) -> None:
    """Backfill derived price metrics if missing."""
    price_total = listing.get('price_total')
    area_m2 = listing.get('area_m2')
    if not listing.get('price_per_m2') and isinstance(price_total, (int, float)) and isinstance(area_m2, (int, float)) and area_m2:
        listing['price_per_m2'] = round(price_total / area_m2)


def compute_listing_depth(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a lightweight data quality snapshot for a listing."""
    critical_fields = [
        'price_total', 'area_m2', 'rooms', 'year_built', 'hwb_value',
        'ubahn_walk_minutes', 'school_walk_minutes', 'balcony_terrace',
        'floor_level', 'price_per_m2'
    ]
    present = [field for field in critical_fields if listing.get(field) not in (None, '', 0)]
    missing = [field for field in critical_fields if field not in present]
    coverage_pct = (len(present) / len(critical_fields)) * 100 if critical_fields else 0
    return {
        'coverage_pct': coverage_pct,
        'missing_fields': missing,
        'present_fields': present
    }


def estimate_regional_rent(listing: Dict[str, Any], rent_benchmarks: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Estimate market rent for a similar unit in the same district."""
    try:
        bezirk = normalize_district_code(listing.get('bezirk'))
        area_m2 = listing.get('area_m2') or 0
        if not area_m2 or area_m2 <= 0:
            return None

        rate_per_m2 = None
        if bezirk in rent_benchmarks:
            rate_per_m2 = rent_benchmarks[bezirk]
            source = 'config'
        elif 'default' in rent_benchmarks:
            rate_per_m2 = rent_benchmarks['default']
            source = 'config-default'
        else:
            source = 'derived'

        # Fall back to a yield-based estimate if no benchmark provided
        if rate_per_m2 is None:
            price_per_m2 = listing.get('price_per_m2')
            if isinstance(price_per_m2, (int, float)) and price_per_m2 > 0:
                implied = (price_per_m2 * 0.035) / 12  # 3.5% gross yield assumption
                rate_per_m2 = max(8.0, min(23.0, implied))
            else:
                return None

        # Adjust for property condition/age
        year_built = listing.get('year_built') or 0
        if year_built >= 2015:
            rate_per_m2 *= 1.08
        elif year_built and year_built < 1970:
            rate_per_m2 *= 0.94

        monthly_rent = rate_per_m2 * area_m2
        return {
            'regional_rent_monthly': monthly_rent,
            'regional_rent_per_m2': rate_per_m2,
            'rent_benchmark_source': source,
        }
    except Exception as exc:
        logging.warning(f"⚠️ Failed to estimate regional rent: {exc}")
        return None


def enrich_listing(listing: Dict[str, Any], rent_benchmarks: Dict[str, float]) -> Dict[str, Any]:
    """Perform deeper, non-destructive enrichment on a listing."""
    ensure_price_metrics(listing)
    listing['bezirk'] = normalize_district_code(listing.get('bezirk'))
    listing['data_quality'] = compute_listing_depth(listing)

    rent_info = estimate_regional_rent(listing, rent_benchmarks)
    if rent_info:
        listing.update(rent_info)

    return listing


def recency_score(listing: Dict[str, Any], horizon_days: int = 120) -> float:
    """Compute a small recency bonus (0-1) for newer postings."""
    ts = listing.get('processed_at')
    if not isinstance(ts, (int, float)):
        return 0.0
    age_days = max((time.time() - ts) / 86400, 0)
    return max(0.0, (horizon_days - age_days) / horizon_days)

def setup_logging():
    """Setup logging configuration"""
    # Ensure log directory exists
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('log/top5.log')
        ]
    )

def investment_comparison(
    initial_investment: float,  # Total property value (price + 10% fees)
    down_payment: float,  # Initial cash invested in property (20% of adjusted price)
    loan_amount: float,  # Mortgage loan amount (80% of adjusted price)
    monthly_loan_payment: float,  # Monthly mortgage payment
    annual_mortgage_rate: float = 0.0289,  # Annual mortgage interest rate (2.89%)
    years: int = 35,  # Investment duration
    property_appreciation_rate: float = 0.01,  # Annual property value growth
    initial_rent_yield_net: float = 0.025,  # Initial net rental yield
    occupancy_rate: float = 0.95,  # Average occupancy rate
    annual_rent_increase_rate: float = 0.02,  # Annual rent increase (indexed)
    etf_annual_return_rate: float = 0.07  # Annual ETF return rate
):
    """
    Compare real estate investment vs ETF investment returns
    """
    # Calculate future property value
    future_property_value = initial_investment * (1 + property_appreciation_rate) ** years

    # Calculate rental income (3.5% gross yield)
    initial_gross_rent = initial_investment * 0.035  # 3.5% gross rental yield
    
    # Calculate maintenance costs (typically 1-2% of property value annually)
    annual_maintenance_rate = 0.015  # 1.5% of property value for maintenance
    annual_maintenance_cost = initial_investment * annual_maintenance_rate
    
    # Calculate net rental income (gross rent - maintenance costs)
    initial_net_rent_income = initial_gross_rent - annual_maintenance_cost
    
    # Apply occupancy rate to net rental income
    initial_net_rent_income = initial_net_rent_income * occupancy_rate

    # Calculate future value of net rents reinvested in ETF (growing annuity)
    # Formula for future value of growing annuity: FV = P * ((1+r)^n - (1+g)^n) / (r-g)
    P = initial_net_rent_income
    r = etf_annual_return_rate
    g = annual_rent_increase_rate
    n = years
    
    if r != g:
        etf_value_from_rents = P * ((1 + r) ** n - (1 + g) ** n) / (r - g)
    else:
        etf_value_from_rents = P * n * (1 + r) ** (n-1)

    # Calculate total mortgage cost using the provided monthly payment
    months = years * 12
    total_mortgage_cost = monthly_loan_payment * months

    # Calculate net profit from real estate investment
    net_profit_property = future_property_value + etf_value_from_rents - total_mortgage_cost

    # Calculate direct ETF investment value
    etf_value_direct = down_payment * (1 + etf_annual_return_rate) ** years

    # Calculate the difference (total sum - down payment) split over 35 years, monthly invested in ETF
    monthly_investment = (initial_investment - down_payment) / (years * 12)
    months = years * 12
    # Future value of a series of monthly investments (ordinary annuity formula)
    etf_value_monthly = monthly_investment * (((1 + etf_annual_return_rate / 12) ** months - 1) / (etf_annual_return_rate / 12))

    # Calculate net profits
    profit_property = net_profit_property - down_payment
    profit_etf_direct = etf_value_direct - down_payment
    
    # Calculate total ETF value (down payment + monthly investments)
    etf_value_total = etf_value_direct + etf_value_monthly
    profit_etf_total = etf_value_total - initial_investment

    return {
        'future_property_value': future_property_value,
        'etf_value_from_rents': etf_value_from_rents,
        'total_mortgage_cost': total_mortgage_cost,
        'net_profit_property': net_profit_property,
        'etf_value_direct': etf_value_direct,
        'etf_value_monthly': etf_value_monthly,
        'etf_value_total': etf_value_total,
        'profit_property': profit_property,
        'profit_etf_direct': profit_etf_direct,
        'profit_etf_total': profit_etf_total,
        'monthly_payment': monthly_loan_payment,
        'initial_net_rent_income': initial_net_rent_income,
        'initial_gross_rent': initial_gross_rent,
        'annual_maintenance_cost': annual_maintenance_cost,
        'monthly_investment': monthly_investment
    }

def calculate_investment_analysis(listing: dict, rent_info: Optional[Dict[str, Any]] = None) -> dict | None:
    """
    Calculate investment analysis for a property listing using real calculated values
    """
    try:
        # Extract property data from listing
        price_total = listing.get('price_total', 0)
        if price_total <= 0:
            return None
        
        # Get the real calculated values from the listing
        # These should be calculated by _add_monthly_payment_calculation in MongoDB handler
        monthly_payment_data = listing.get('monthly_payment', {})
        mortgage_details = listing.get('mortgage_details', {})
        
        # Use real calculated values if available, otherwise calculate them
        if monthly_payment_data and isinstance(monthly_payment_data, dict):
            # Use the real calculated values
            adjusted_price = monthly_payment_data.get('adjusted_price', price_total * 1.10)
            down_payment = monthly_payment_data.get('down_payment', adjusted_price * 0.20)
            loan_amount = monthly_payment_data.get('loan_amount', adjusted_price - down_payment)
            monthly_loan_payment = monthly_payment_data.get('loan_payment', 0)
            total_monthly_cost = monthly_payment_data.get('total_monthly', monthly_loan_payment + (monthly_payment_data.get('betriebskosten', 0) or 0))
        elif mortgage_details and isinstance(mortgage_details, dict):
            # Use mortgage details if available
            adjusted_price = mortgage_details.get('adjusted_price', price_total * 1.10)
            down_payment = mortgage_details.get('down_payment', adjusted_price * 0.20)
            loan_amount = mortgage_details.get('loan_amount', adjusted_price - down_payment)
            monthly_loan_payment = mortgage_details.get('monthly_payment', 0)
            total_monthly_cost = monthly_loan_payment + (listing.get('betriebskosten', 0) or 0)
        else:
            # Fallback to manual calculation (same as in MongoDB handler)
            adjusted_price = price_total * 1.10  # Price + 10% fees
            down_payment = adjusted_price * 0.20  # 20% down payment
            loan_amount = adjusted_price - down_payment  # 80% loan
            monthly_loan_payment = loan_amount * 0.00383  # Realistic ratio
            total_monthly_cost = monthly_loan_payment + (listing.get('betriebskosten', 0) or 0)
        
        # Investment parameters (can be made configurable)
        annual_mortgage_rate = 0.0289  # 2.89% annual rate (from mortgage details)
        years = 35
        property_appreciation_rate = 0.01  # 1% annual appreciation
        occupancy_rate = 0.95  # 95% occupancy rate
        annual_rent_increase_rate = 0.02  # 2% annual rent increase
        etf_annual_return_rate = 0.07  # 7% annual ETF return
        
        # Run investment comparison with real values
        result = investment_comparison(
            initial_investment=adjusted_price,  # Use adjusted price (price + 10% fees)
            down_payment=down_payment,
            loan_amount=loan_amount,
            monthly_loan_payment=monthly_loan_payment,
            annual_mortgage_rate=annual_mortgage_rate,
            years=years,
            property_appreciation_rate=property_appreciation_rate,
            occupancy_rate=occupancy_rate,
            annual_rent_increase_rate=annual_rent_increase_rate,
            etf_annual_return_rate=etf_annual_return_rate
        )
        
        # Calculate additional metrics using total ETF comparison
        profit_difference = result['profit_property'] - result['profit_etf_total']
        percentage_better = (profit_difference / result['profit_etf_total']) * 100 if result['profit_etf_total'] > 0 else 0

        # Merge rent comparison info
        rent_details = rent_info or {}
        if not rent_details:
            # Fall back to existing enrichment on listing
            rent_month = listing.get('regional_rent_monthly')
            rent_per_m2 = listing.get('regional_rent_per_m2')
            if rent_month:
                rent_details = {
                    'regional_rent_monthly': rent_month,
                    'regional_rent_per_m2': rent_per_m2,
                    'rent_benchmark_source': listing.get('rent_benchmark_source')
                }
        rent_monthly = rent_details.get('regional_rent_monthly') if isinstance(rent_details, dict) else None
        rent_vs_own = None
        rent_to_own_ratio = None
        if rent_monthly is not None:
            rent_vs_own = rent_monthly - total_monthly_cost
            rent_to_own_ratio = (rent_monthly / total_monthly_cost) if total_monthly_cost else None
        
        # Add to result
        result.update({
            'profit_difference': profit_difference,
            'percentage_better': percentage_better,
            'makes_sense': profit_difference > 0,
            'down_payment': down_payment,
            'loan_amount': loan_amount,
            'adjusted_price': adjusted_price,
            'monthly_loan_payment': monthly_loan_payment,
            'total_monthly_cost': total_monthly_cost,
            'regional_rent_monthly': rent_monthly,
            'regional_rent_per_m2': rent_details.get('regional_rent_per_m2') if isinstance(rent_details, dict) else None,
            'rent_vs_own_monthly_diff': rent_vs_own,
            'rent_to_own_ratio': rent_to_own_ratio,
            'rent_benchmark_source': rent_details.get('rent_benchmark_source') if isinstance(rent_details, dict) else None,
        })
        
        return result
        
    except Exception as e:
        logging.error(f"Error calculating investment analysis: {e}")
        return None

def format_investment_summary(investment_result: dict | None) -> str:
    """
    Format investment analysis results for display (concise)
    """
    if not investment_result:
        return "❌ Investment analysis not available"
    
    profit_diff = investment_result['profit_difference']
    percentage = investment_result['percentage_better']
    makes_sense = investment_result['makes_sense']

    # Net rent per month (rounded)
    monthly_net_rent = (investment_result.get('initial_net_rent_income', 0) or 0) / 12.0

    # Concise summary: RE vs ETF and net rent per month
    re_profit = investment_result['profit_property']
    etf_profit = investment_result['profit_etf_total']
    verdict = "✅ RE" if makes_sense else "⚠️ ETF"
    rent_month = investment_result.get('regional_rent_monthly')
    own_month = investment_result.get('total_monthly_cost')
    rent_line = ""
    if rent_month and own_month:
        rent_diff = rent_month - own_month
        rent_line = f"\n🏠 Rent vs Own: Rent €{rent_month:,.0f}/mo vs Own €{own_month:,.0f} ({rent_diff:+,.0f})"

    return (
        f"📊 RE vs ETF: RE €{re_profit:,.0f} vs ETF €{etf_profit:,.0f} | Δ €{profit_diff:,.0f} ({percentage:+.1f}%)\n"
        f"💵 Net rent: €{monthly_net_rent:,.0f}/mo | {verdict}"
        f"{rent_line}"
    )

def main(argv: Optional[List[str]] = None):
    """Main function to fetch top 5 listings and send to Telegram"""
    setup_logging()

    args = parse_cli_args(argv)
    default_persona = BuyerPersona.OWNER_OCCUPIER
    buyer_profile_override = args.buyer_profile
    buyer_persona = args.buyer_persona or default_persona
    is_weekly = args.weekly
    
    print("🏆 Starting Top 5 Properties Report")
    print("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        if not config:
            logging.error("❌ Failed to load configuration")
            return False
        
        top5_config = config.get('top5', {})

        # Determine buyer profile (CLI > config > persona default)
        config_profile = top5_config.get('buyer_profile') or top5_config.get('buyer_persona')
        active_profile = buyer_profile_override or config_profile or buyer_persona.value

        # Set the buyer profile for scoring
        from Application.scoring import set_buyer_profile
        set_buyer_profile(active_profile)
        logging.info(f"👤 Using buyer persona: {active_profile}")
        
        # Initialize MongoDB handler
        mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
        mongo = MongoDBHandler(uri=mongo_uri)
        
        if not mongo.client:
            logging.error("❌ Failed to connect to MongoDB")
            logging.info("ℹ️ This is expected in GitHub Actions environment without MongoDB")
            return False
        
        # Initialize Telegram bot
        telegram_config = config.get('telegram', {})
        telegram_main = telegram_config.get('telegram_main', {})
        
        if not telegram_main.get('bot_token') or not telegram_main.get('chat_id'):
            logging.error("❌ Telegram configuration not found")
            return False
        
        telegram_bot = TelegramBot(
            telegram_main['bot_token'],
            telegram_main['chat_id']
        )
        
        # Test Telegram connection
        if not telegram_bot.test_connection():
            logging.error("❌ Failed to connect to Telegram")
            logging.info("ℹ️ This is expected if Telegram bot token is not configured or invalid")
            return False
        
        # Get parameters from config or use defaults (allow CLI overrides)
        limit = args.limit if args.limit is not None else top5_config.get('limit', 5)
        min_score = args.min_score if args.min_score is not None else top5_config.get('min_score', 30.0)

        excluded_districts_cfg = top5_config.get('excluded_districts', [])
        if not isinstance(excluded_districts_cfg, list):
            excluded_districts_cfg = []
        excluded_districts = args.exclude_districts if args.exclude_districts is not None else excluded_districts_cfg
        excluded_districts = [normalize_district_code(d) for d in excluded_districts if d]

        min_rooms = args.min_rooms if args.min_rooms is not None else top5_config.get('min_rooms', 0)
        include_monthly_payment = (
            args.include_monthly_payment
            if args.include_monthly_payment is not None
            else top5_config.get('include_monthly_payment', True)
        )
        include_investment_analysis = (
            args.include_investment_analysis
            if args.include_investment_analysis is not None
            else top5_config.get('include_investment_analysis', True)
        )
        pool_size = args.pool_size if args.pool_size is not None else top5_config.get('pool_size', 150)
        candidate_pool = args.candidate_pool if args.candidate_pool is not None else top5_config.get('candidate_pool', 50)
        exclude_recently_sent = True

        # Rent benchmarks (configurable, fallback to defaults)
        rent_benchmarks = DEFAULT_RENT_BENCHMARKS.copy()
        config_rent_benchmarks = top5_config.get('rent_benchmarks', {})
        if isinstance(config_rent_benchmarks, dict):
            for key, value in config_rent_benchmarks.items():
                try:
                    rent_benchmarks[normalize_district_code(key)] = float(value)
                except (TypeError, ValueError):
                    continue

        # Weekly mode overrides
        if is_weekly:
            if args.limit is None:
                limit = 10
            exclude_recently_sent = False
            logging.info(f"📅 Weekly mode enabled: sending top {limit}, including previously sent listings")
        
        candidate_pool = max(candidate_pool, limit)
        
        print(f"📊 Fetching top {limit} listings...")
        print(f"🎯 Minimum score: {min_score}")
        if exclude_recently_sent:
            print(f"🚫 Excluding listings sent to Telegram in last 14 days")
        else:
            print(f"✅ Including listings even if sent recently (weekly mode)")
        print(f"🚫 Filtering out 'unbefristet vermietete' (rental) properties")
        print(f"🚫 Filtering out 'Preis auf Anfrage' (price on request) properties")
        print(f"🎯 Properties above €400k need score 40+ (stricter requirements)")
        print(f"🧠 Deep scan pool: {pool_size} listings → top {candidate_pool} considered for sending")
        print(f"📉 Rent benchmark source: {'custom config' if config_rent_benchmarks else 'built-in defaults'}")
        if excluded_districts:
            print(f"🚫 Excluded districts: {excluded_districts}")
        if min_rooms > 0:
            print(f"🛏️ Minimum rooms: {min_rooms}")
        if include_monthly_payment:
            print(f"💰 Including monthly payment calculations")
        if include_investment_analysis:
            print(f"📊 Including investment analysis (RE vs ETF comparison)")
        
        # Fetch top listings from MongoDB (all time, excluding recently sent)
        listings = mongo.get_top_listings(
            limit=pool_size,  # Get a larger pool of listings to select from
            min_score=min_score,
            days_old=365,  # Look back 1 year to get all available listings
            excluded_districts=excluded_districts,
            min_rooms=min_rooms,
            exclude_recently_sent=exclude_recently_sent,  # Control duplicate suppression
            recently_sent_days=14
        )

        # Enrich and guard against missing prices
        listings = [
            enrich_listing(l, rent_benchmarks)
            for l in listings
            if isinstance(l.get('price_total'), (int, float)) and l.get('price_total', 0) > 0
        ]
        
        # Filter out garbage listings with unrealistic prices
        original_count = len(listings)
        valid_listings = filter_valid_listings(listings)
        
        # Log validation statistics
        stats = get_validation_stats(listings[:original_count])
        logging.info(f"📊 Validation stats: {stats['valid']}/{stats['total']} valid ({stats['valid_percentage']:.1f}%)")
        logging.info(f"🚫 Filtered out rental properties and expensive properties with low scores")

        # Prioritize data richness before random selection
        def candidate_sort_key(l: Dict[str, Any]):
            coverage = l.get('data_quality', {}).get('coverage_pct', 0)
            rent_flag = 1 if l.get('regional_rent_monthly') else 0
            # Small recency influence (max +20 boost vs coverage at 100)
            recency_bonus = recency_score(l) * 20
            return (
                coverage,
                rent_flag,
                recency_bonus,
                l.get('score', 0)
            )

        sorted_candidates = sorted(valid_listings, key=candidate_sort_key, reverse=True)

        pool = sorted_candidates[:candidate_pool]
        if pool:
            avg_coverage = sum(l.get('data_quality', {}).get('coverage_pct', 0) for l in pool) / len(pool)
            logging.info(f"🧮 Avg data coverage in candidate pool: {avg_coverage:.1f}%")
        if len(pool) < limit:
            logging.warning(f"⚠️ Pool size ({len(pool)}) is less than requested limit ({limit}). Sending all available.")
            limit = len(pool)
        
        if pool:
            listings_to_send = random.sample(pool, limit) if limit > 0 else []
        else:
            logging.warning("⚠️ No listings available after filtering")
            print("⚠️ No listings found matching criteria - no message sent to Telegram")
            return True
        
        # Add investment analysis to each listing
        if include_investment_analysis:
            print("📊 Calculating investment analysis for each property...")
            for listing in listings_to_send:
                rent_context = {}
                if listing.get('regional_rent_monthly') is not None:
                    rent_context = {
                        'regional_rent_monthly': listing.get('regional_rent_monthly'),
                        'regional_rent_per_m2': listing.get('regional_rent_per_m2'),
                        'rent_benchmark_source': listing.get('rent_benchmark_source'),
                    }
                investment_result = calculate_investment_analysis(listing, rent_context)
                if investment_result:
                    listing['investment_analysis'] = investment_result
                    listing['investment_summary'] = format_investment_summary(investment_result)
                else:
                    listing['investment_analysis'] = None
                    listing['investment_summary'] = "❌ Investment analysis not available"
        else:
            # Clear any existing investment analysis
            for listing in listings_to_send:
                listing['investment_analysis'] = None
                listing['investment_summary'] = None
        
        if not listings_to_send:
            logging.warning("⚠️ No listings found matching criteria")
            print("⚠️ No listings found matching criteria - no message sent to Telegram")
            return True
        
        # Create title for the report
        if is_weekly:
            title = f"📅 Weekly Top {len(listings_to_send)} Properties Report (Randomized)"
        else:
            title = f"🏆 Top {len(listings_to_send)} Properties Report (Randomized)"
        
        # Send to Telegram
        success = telegram_bot.send_top_listings(
            listings=listings_to_send,
            title=title,
            max_listings=limit
        )
        
        if success:
            print(f"✅ Successfully sent top {len(listings_to_send)} listings to Telegram")
            
            # Mark listings as sent to prevent duplicates (skip in weekly mode)
            if not is_weekly:
                mongo.mark_listings_sent(listings_to_send)
            
            # Print summary
            print("\n📊 Summary:")
            for i, listing in enumerate(listings_to_send, 1):
                score = listing.get('score', 0)
                price = listing.get('price_total', 0)
                area = listing.get('area_m2', 0)
                rooms = listing.get('rooms', 0)
                bezirk = listing.get('bezirk', 'N/A')
                source = listing.get('source', 'Unknown')
                
                # Investment analysis info
                if include_investment_analysis:
                    investment_analysis = listing.get('investment_analysis')
                    investment_status = ""
                    if investment_analysis:
                        if investment_analysis.get('makes_sense', False):
                            investment_status = "✅ RE makes sense"
                        else:
                            investment_status = "⚠️ ETF better"
                        rent_delta = investment_analysis.get('rent_vs_own_monthly_diff')
                        if rent_delta is not None:
                            investment_status += f" | Rent Δ {rent_delta:+,.0f}/mo"
                    else:
                        investment_status = "❌ No analysis"
                    
                    print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk} | {source} | {investment_status}")
                else:
                    print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk} | {source}")
            
            return True
        else:
            logging.error("❌ Failed to send listings to Telegram")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error in main function: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
