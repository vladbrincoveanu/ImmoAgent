#!/usr/bin/env python3
"""
Script to fetch top 5 listings from MongoDB and send to Telegram main channel
"""

import sys
import os
import logging
from datetime import datetime
import numpy as np
import random

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
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot

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

def calculate_investment_analysis(listing: dict) -> dict | None:
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
        elif mortgage_details and isinstance(mortgage_details, dict):
            # Use mortgage details if available
            adjusted_price = mortgage_details.get('adjusted_price', price_total * 1.10)
            down_payment = mortgage_details.get('down_payment', adjusted_price * 0.20)
            loan_amount = mortgage_details.get('loan_amount', adjusted_price - down_payment)
            monthly_loan_payment = mortgage_details.get('monthly_payment', 0)
        else:
            # Fallback to manual calculation (same as in MongoDB handler)
            adjusted_price = price_total * 1.10  # Price + 10% fees
            down_payment = adjusted_price * 0.20  # 20% down payment
            loan_amount = adjusted_price - down_payment  # 80% loan
            monthly_loan_payment = loan_amount * 0.00383  # Realistic ratio
        
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
        
        # Add to result
        result.update({
            'profit_difference': profit_difference,
            'percentage_better': percentage_better,
            'makes_sense': profit_difference > 0,
            'down_payment': down_payment,
            'loan_amount': loan_amount,
            'adjusted_price': adjusted_price,
            'monthly_loan_payment': monthly_loan_payment
        })
        
        return result
        
    except Exception as e:
        logging.error(f"Error calculating investment analysis: {e}")
        return None

def format_investment_summary(investment_result: dict | None) -> str:
    """
    Format investment analysis results for display
    """
    if not investment_result:
        return "❌ Investment analysis not available"
    
    profit_diff = investment_result['profit_difference']
    percentage = investment_result['percentage_better']
    makes_sense = investment_result['makes_sense']
    
    summary = f"📊 <b>Investment Analysis (35 years):</b>\n"
    summary += f"💰 Property Profit: €{investment_result['profit_property']:,.0f}\n"
    summary += f"📈 ETF Total Profit: €{investment_result['profit_etf_total']:,.0f}\n"
    summary += f"  • Down Payment: €{investment_result['etf_value_direct']:,.0f}\n"
    summary += f"  • Monthly Investments: €{investment_result['etf_value_monthly']:,.0f}\n"
    summary += f"📊 Difference: €{profit_diff:,.0f} ({percentage:+.1f}%)\n"
    
    # Add rental income details
    summary += f"\n🏠 <b>Rental Income Details:</b>\n"
    summary += f"• Gross Rent (3.5%): €{investment_result['initial_gross_rent']:,.0f}/year\n"
    summary += f"• Maintenance Costs: €{investment_result['annual_maintenance_cost']:,.0f}/year\n"
    summary += f"• Net Rent Income: €{investment_result['initial_net_rent_income']:,.0f}/year\n"
    summary += f"• Future Rent ETF Value: €{investment_result['etf_value_from_rents']:,.0f}\n"
    
    if makes_sense:
        summary += f"\n✅ <b>Real Estate makes sense!</b>"
    else:
        summary += f"\n⚠️ <b>ETF might be better</b>"
    
    return summary

def main():
    """Main function to fetch top 5 listings and send to Telegram"""
    setup_logging()
    
    # Parse buyer profile from command line arguments
    buyer_profile = "diy_renovator"  # Default to DIY Renovator profile
    is_weekly = False
    for i, arg in enumerate(sys.argv):
        if arg == "--buyer-profile" and i + 1 < len(sys.argv):
            buyer_profile = sys.argv[i + 1]
        elif arg.startswith("--buyer-profile="):
            buyer_profile = arg.split("=", 1)[1]
        elif arg == "--weekly":
            is_weekly = True
    
    # Set the buyer profile for scoring
    from Application.scoring import set_buyer_profile
    set_buyer_profile(buyer_profile)
    
    print("🏆 Starting Top 5 Properties Report")
    print("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        if not config:
            logging.error("❌ Failed to load configuration")
            return False
        
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
        
        # Get parameters from config or use defaults
        limit = config.get('top5', {}).get('limit', 5)
        min_score = config.get('top5', {}).get('min_score', 30.0)
        excluded_districts = config.get('top5', {}).get('excluded_districts', [])
        min_rooms = config.get('top5', {}).get('min_rooms', 0)
        include_monthly_payment = config.get('top5', {}).get('include_monthly_payment', True)
        include_investment_analysis = config.get('top5', {}).get('include_investment_analysis', True)
        exclude_recently_sent = True

        # Weekly mode overrides
        if is_weekly:
            limit = 10
            exclude_recently_sent = False
            logging.info("📅 Weekly mode enabled: sending top 10, including previously sent listings")
        
        print(f"📊 Fetching top {limit} listings...")
        print(f"🎯 Minimum score: {min_score}")
        if exclude_recently_sent:
            print(f"🚫 Excluding listings sent to Telegram in last 14 days")
        else:
            print(f"✅ Including listings even if sent recently (weekly mode)")
        print(f"🚫 Filtering out 'unbefristet vermietete' (rental) properties")
        print(f"🚫 Filtering out 'Preis auf Anfrage' (price on request) properties")
        print(f"🎯 Properties above €400k need score 40+ (stricter requirements)")
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
            limit=60,  # Get a larger pool of listings to select from
            min_score=min_score,
            days_old=365,  # Look back 1 year to get all available listings
            excluded_districts=excluded_districts,
            min_rooms=min_rooms,
            exclude_recently_sent=exclude_recently_sent,  # Control duplicate suppression
            recently_sent_days=14
        )

        # Extra safeguard: filter out listings without numeric prices (Preis auf Anfrage)
        listings = [
            l for l in listings
            if isinstance(l.get('price_total'), (int, float)) and l.get('price_total', 0) > 0
        ]
        
        # Filter out garbage listings with unrealistic prices
        original_count = len(listings)
        valid_listings = filter_valid_listings(listings)
        
        # Log validation statistics
        stats = get_validation_stats(listings[:original_count])
        logging.info(f"📊 Validation stats: {stats['valid']}/{stats['total']} valid ({stats['valid_percentage']:.1f}%)")
        logging.info(f"🚫 Filtered out rental properties and expensive properties with low scores")

        # Take top 20 for the pool and randomize selection
        pool = valid_listings[:20]
        if len(pool) < limit:
            logging.warning(f"⚠️ Pool size ({len(pool)}) is less than requested limit ({limit}). Sending all available.")
            limit = len(pool)
        
        listings_to_send = random.sample(pool, limit)
        
        # Add investment analysis to each listing
        if include_investment_analysis:
            print("📊 Calculating investment analysis for each property...")
            for listing in listings_to_send:
                investment_result = calculate_investment_analysis(listing)
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