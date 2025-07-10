import requests
import json
import time
import re
import math
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
from dataclasses import dataclass
from ollama_analyzer import StructuredAnalyzer
from mongodb_handler import MongoDBHandler
from telegram_bot import TelegramBot
from geocoding import ViennaGeocoder
import logging
from helpers import calculate_ubahn_proximity, format_currency

@dataclass
class Amenity:
    name: str
    distance_m: float
    type: str

class MortgageCalculator:
    """Calculate mortgage payments using standard financial formulas"""
    
    @staticmethod
    def calculate_monthly_payment(loan_amount: float, annual_rate: float, years: int, include_fees: bool = True) -> float:
        """
        Calculate monthly mortgage payment using the standard formula:
        M = P * [r(1+r)^n] / [(1+r)^n - 1]
        
        Where:
        M = Monthly payment
        P = Principal loan amount
        r = Monthly interest rate (annual rate / 12)
        n = Total number of payments (years * 12)
        
        Austrian mortgages typically include:
        - Life insurance premium (~0.3-0.5% annually)
        - Property insurance (~0.1-0.2% annually)
        - Administration fees
        """
        if loan_amount <= 0 or annual_rate <= 0 or years <= 0:
            return 0
        
        monthly_rate = annual_rate / 12 / 100  # Convert annual % to monthly decimal
        num_payments = years * 12
        
        # Handle edge case where rate is 0
        if monthly_rate == 0:
            base_payment = loan_amount / num_payments
        else:
            # Standard mortgage formula
            base_payment = loan_amount * (
                monthly_rate * (1 + monthly_rate) ** num_payments
            ) / (
                (1 + monthly_rate) ** num_payments - 1
            )
        
        if include_fees:
            # Add typical Austrian mortgage fees
            # Life insurance: ~0.4% annually of loan amount
            life_insurance_monthly = (loan_amount * 0.004) / 12
            
            # Property insurance: ~0.15% annually of loan amount  
            property_insurance_monthly = (loan_amount * 0.0015) / 12
            
            # Administration fees: ~€20-30 monthly
            admin_fees_monthly = 25
            
            total_monthly = base_payment + life_insurance_monthly + property_insurance_monthly + admin_fees_monthly
            
            return round(total_monthly, 2)
        
        return round(base_payment, 2)
    
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
        """Get detailed breakdown of monthly payment components"""
        if loan_amount <= 0 or annual_rate <= 0 or years <= 0:
            return {}
        
        monthly_rate = annual_rate / 12 / 100
        num_payments = years * 12
        
        # Base mortgage payment
        if monthly_rate == 0:
            base_payment = loan_amount / num_payments
        else:
            base_payment = loan_amount * (
                monthly_rate * (1 + monthly_rate) ** num_payments
            ) / (
                (1 + monthly_rate) ** num_payments - 1
            )
        
        # Additional fees
        life_insurance = (loan_amount * 0.004) / 12
        property_insurance = (loan_amount * 0.0015) / 12
        admin_fees = 25
        
        total = base_payment + life_insurance + property_insurance + admin_fees
        
        return {
            'base_payment': round(base_payment, 2),
            'life_insurance': round(life_insurance, 2),
            'property_insurance': round(property_insurance, 2),
            'admin_fees': round(admin_fees, 2),
            'total_monthly': round(total, 2)
        }

class WillhabenScraper:
    def __init__(self, config: Optional[Dict] = None, criteria_path: str = "criteria.json", telegram_config: Optional[Dict] = None, mongo_uri: Optional[str] = None):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        self.geocoder = ViennaGeocoder()
        self.mortgage_calc = MortgageCalculator()
        
        # Handle config parameter
        if config:
            # Initialize Structured analyzer with config FIRST
            self.structured_analyzer = StructuredAnalyzer(
                api_key=config.get('openai_api_key'),
                model=config.get('openai_model', 'gpt-4o-mini')
            )
            # If config is provided, use it to initialize everything
            self.criteria = config.get('criteria', {})
            if self.criteria:
                print(f"📋 Loaded criteria from config: {len(self.criteria)} rules")
            else:
                print(f"⚠️  No criteria found in config.json. Filtering will be disabled.")
                self.criteria = {}
            
            print(f"🧠 Structured analyzer available: {'✅' if self.structured_analyzer.is_available() else '❌'}")
            
            # Initialize Telegram bot if config provided
            self.telegram_bot = None
            if config.get('telegram_bot_token') and config.get('telegram_chat_id'):
                self.telegram_bot = TelegramBot(
                    config['telegram_bot_token'],
                    config['telegram_chat_id']
                )
            
            # Initialize MongoDB handler
            mongo_uri = config.get('mongodb_uri') or "mongodb://localhost:27017/"
            self.mongo = MongoDBHandler(uri=mongo_uri)
            
        else:
            # Legacy initialization
            self.criteria = self.load_criteria(criteria_path)
            
            # Initialize Telegram bot if config provided
            self.telegram_bot = None
            if telegram_config and telegram_config.get('bot_token') and telegram_config.get('chat_id'):
                self.telegram_bot = TelegramBot(
                    telegram_config['bot_token'],
                    telegram_config['chat_id']
                )
            
            # Initialize MongoDB handler
            mongo_uri = mongo_uri or "mongodb://localhost:27017/"
            self.mongo = MongoDBHandler(uri=mongo_uri)
            
            # Initialize Structured analyzer with defaults
            self.structured_analyzer = StructuredAnalyzer()
        
    def load_criteria(self, criteria_path: str) -> Dict:
        """Load criteria from JSON file"""
        try:
            with open(criteria_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading criteria: {e}")
            return {}

    def extract_listing_urls(self, soup: BeautifulSoup) -> List[str]:
        """Extract listing URLs from search results page"""
        urls = []
        
        # Multiple selectors for different page layouts
        selectors = [
            'a[href*="/iad/immobilien/d/"]',
            'a[href*="/iad/object/"]',
            '.result-list-entry a[href*="/iad/"]',
            '.search-result-entry a[href*="/iad/"]',
            '[data-testid="result-item"] a[href*="/iad/"]',
            'a[href*="immobilien"]'
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and isinstance(href, str) and '/iad/immobilien/' in href:
                    if href.startswith('/'):
                        href = f"https://www.willhaben.at{href}"
                    urls.append(href)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls

    def extract_special_features(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract special features"""
        try:
            # Look for special features in the listing
            feature_selectors = [
                '[data-testid*="feature"]',
                '.feature-list',
                '.amenities'
            ]
            
            for selector in feature_selectors:
                elements = soup.select(selector)
                if elements:
                    features = []
                    for element in elements:
                        text = element.get_text(strip=True)
                        if text:
                            features.append(text)
                    if features:
                        return ', '.join(features)
            
            return None
        except Exception as e:
            print(f"Error extracting special features: {e}")
            return None

    def extract_from_json_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract data from the JSON structure in the HTML"""
        try:
            # Find the __NEXT_DATA__ script tag
            script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
            if script_tag and script_tag.string:  # type: ignore
                # Parse the JSON data
                json_data = json.loads(str(script_tag.string))
            else:
                return {}
            
            # Navigate to the attributes
            attributes = json_data.get('props', {}).get('pageProps', {}).get('advertDetails', {}).get('attributes', {}).get('attribute', [])
            
            extracted_data = {}
            
            # Extract address from LOCATION/ADDRESS_2
            for attr in attributes:
                name = attr.get('name', '')
                values = attr.get('values', [])
                if values:
                    value = values[0]
                    
                    if name == 'LOCATION/ADDRESS_2':
                        extracted_data['address'] = value
                    elif 'Heizungsart:' in value:
                        heating_match = re.search(r'Heizungsart:\s*([^<\n]+)', value)
                        if heating_match:
                            extracted_data['heating_type'] = heating_match.group(1).strip()
                    elif 'Wesentliche Energieträger:' in value:
                        carrier_match = re.search(r'Wesentliche Energieträger:\s*([^<\n]+)', value)
                        if carrier_match:
                            extracted_data['energy_carrier'] = carrier_match.group(1).strip()
                    elif 'Verfügbar ab:' in value:
                        available_match = re.search(r'Verfügbar ab:\s*([^<\n]+)', value)
                        if available_match:
                            extracted_data['available_from'] = available_match.group(1).strip()
            
            return extracted_data
            
        except Exception as e:
            print(f"Error extracting from JSON data: {e}")
            return {}

    def scrape_single_listing(self, url: str) -> Dict[str, Any]:
        """Scrape a single listing"""
        try:
            print("🌐 Scraping listing...")
            
            # Get the HTML content
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract JSON data first to get structured information
            json_data = self.extract_from_json_data(soup)
            
            # Initialize listing data with JSON data
            listing_data = {
                'url': url,
                'bezirk': self.extract_bezirk(soup),
                'address': json_data.get('address') or self.extract_address(soup),
                'price_total': self.extract_price(soup),
                'area_m2': self.extract_area(soup),
                'rooms': self.extract_rooms(soup),
                'year_built': self.extract_year_built(soup),
                'floor': self.extract_floor(soup),
                'condition': self.extract_condition(soup),
                'heating': self.extract_heating(soup),
                'parking': self.extract_parking(soup),
                'betriebskosten': self.extract_betriebskosten(soup),
                'energy_class': self.extract_energy_class(soup),
                'hwb_value': self.extract_hwb_value(soup),
                'heating_type': self.clean_heating_type(json_data.get('heating_type')) or self.extract_heating_type(soup),
                'energy_carrier': json_data.get('energy_carrier') or self.extract_energy_carrier(soup),
                'available_from': json_data.get('available_from') or self.extract_available_from(soup),
                'special_features': self.extract_special_features(soup),
                'monatsrate': None,  # Set if available in listing
                'own_funds': None,   # Set if available in listing
            }
            
            # Calculate derived fields
            if listing_data['price_total'] and listing_data['area_m2']:
                listing_data['price_per_m2'] = round(listing_data['price_total'] / listing_data['area_m2'], 2)
            else:
                listing_data['price_per_m2'] = None

            # Get amenities and calculate walk times
            if listing_data['address']:
                # Use the new real distance calculation methods
                ubahn_walk_minutes = self.get_real_ubahn_walk_minutes(listing_data['address'])
                
                # Calculate school walking time with proper error handling
                coords = self.geocoder.geocode_address(listing_data['address'])
                if coords:
                    school_walk_minutes = self.geocoder.get_walking_distance_to_nearest_school(coords)
                else:
                    school_walk_minutes = None
                
                # Set reasonable values instead of -1
                listing_data['school_walk_minutes'] = school_walk_minutes if school_walk_minutes is not None else None
                listing_data['ubahn_walk_minutes'] = ubahn_walk_minutes if ubahn_walk_minutes is not None else None
            else:
                listing_data['school_walk_minutes'] = None
                listing_data['ubahn_walk_minutes'] = None

            # Calculate mortgage if price is available
            if listing_data['price_total']:
                down_payment = self.criteria.get("down_payment_min")
                interest_rate = self.criteria.get("interest_rate_max")
                loan_years = 30

                if down_payment and interest_rate and listing_data['price_total'] > down_payment:
                    loan_amount = self.mortgage_calc.calculate_loan_amount(listing_data['price_total'], down_payment)
                    
                    if loan_amount > 0:
                        monthly_payment = self.mortgage_calc.calculate_monthly_payment(
                            loan_amount, interest_rate, loan_years, include_fees=True
                        )
                        listing_data['calculated_monatsrate'] = monthly_payment
                        listing_data['mortgage_details'] = f"({format_currency(down_payment)} DP, {interest_rate}% Zins, {loan_years} Jahre)"

                # Calculate total monthly cost by adding betriebskosten
                listing_data['total_monthly_cost'] = listing_data.get('calculated_monatsrate')
                if listing_data.get('betriebskosten') and listing_data.get('total_monthly_cost'):
                    listing_data['total_monthly_cost'] += listing_data['betriebskosten']


            # Analyze content if available
            if self.structured_analyzer:
                try:
                    listing_data = self.structured_analyzer.analyze_listing_content(listing_data, response.text)
                except Exception as e:
                    print(f"❌ Analysis failed: {e}")

            return listing_data

        except Exception as e:
            print(f"❌ Error scraping listing: {e}")
            return {}
    
    def clean_heating_type(self, heating_type: Optional[str]) -> Optional[str]:
        """Clean heating type to extract the base type"""
        if not heating_type:
            return None
        
        # Extract base heating type (e.g., "Gas" from "Gasheizung")
        if 'gas' in heating_type.lower():
            return 'Gas'
        elif 'öl' in heating_type.lower() or 'oil' in heating_type.lower():
            return 'Öl'
        elif 'fernwärme' in heating_type.lower():
            return 'Fernwärme'
        elif 'elektro' in heating_type.lower():
            return 'Elektro'
        elif 'wärmepumpe' in heating_type.lower():
            return 'Wärmepumpe'
        else:
            return heating_type.strip()

    def calculate_manual_monthly_rate(self, purchase_price: float, down_payment: Optional[float], soup: BeautifulSoup) -> Optional[float]:
        """
        Calculate monthly mortgage rate manually using financial formulas
        Based on the calculator shown in the image
        """
        try:
            # Default values if not provided
            if down_payment is None:
                down_payment = self.estimate_down_payment(purchase_price, soup)
            
            # Extract or estimate loan terms
            loan_years = self.extract_loan_years(soup) or 35  # Default 35 years as shown in image
            interest_rate = self.extract_interest_rate(soup) or self.mortgage_calc.estimate_interest_rate()
            
            # Calculate loan amount
            loan_amount = self.mortgage_calc.calculate_loan_amount(purchase_price, down_payment)
            
            if loan_amount <= 0:
                return None
            
            # Calculate monthly payment with Austrian fees included
            monthly_payment = self.mortgage_calc.calculate_monthly_payment(
                loan_amount, interest_rate, loan_years, include_fees=True
            )
            
            # Get detailed breakdown
            breakdown = self.mortgage_calc.get_payment_breakdown(loan_amount, interest_rate, loan_years)
            
            print(f"💰 MORTGAGE CALCULATION:")
            print(f"  Purchase Price: €{purchase_price:,}")
            print(f"  Down Payment: €{down_payment:,}")
            print(f"  Loan Amount: €{loan_amount:,}")
            print(f"  Interest Rate: {interest_rate}%")
            print(f"  Loan Term: {loan_years} years")
            print(f"  📋 PAYMENT BREAKDOWN:")
            print(f"    Base Payment: €{breakdown['base_payment']:,}")
            print(f"    Life Insurance: €{breakdown['life_insurance']:,}")
            print(f"    Property Insurance: €{breakdown['property_insurance']:,}")
            print(f"    Admin Fees: €{breakdown['admin_fees']:,}")
            print(f"  💳 Total Monthly: €{monthly_payment:,}")
            
            return monthly_payment
            
        except Exception as e:
            print(f"Error calculating monthly rate: {e}")
            return None

    def estimate_down_payment(self, purchase_price: float, soup: BeautifulSoup) -> float:
        """Estimate down payment if not provided"""
        # Try to extract from financing calculator
        down_payment = self.extract_down_payment_from_calculator(soup)
        if down_payment:
            return down_payment
        
        # Default to 20% down payment (standard in Austria)
        return purchase_price * 0.20

    def extract_down_payment_from_calculator(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract down payment from mortgage calculator"""
        selectors = [
            '[data-testid*="eigenkapital"]',
            '[data-testid*="downPayment"]',
            '[data-testid*="ownFunds"]',
            'input[placeholder*="Eigenkapital"]'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                value = elem.get('value') or elem.get_text()
                if value and isinstance(value, str):
                    match = re.search(r'([\d.,]+)', value)
                    if match:
                        try:
                            return float(match.group(1).replace('.', '').replace(',', '.'))
                        except:
                            continue
        return None

    def extract_loan_years(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract loan term in years from calculator"""
        selectors = [
            '[data-testid*="laufzeit"]',
            '[data-testid*="years"]',
            '[data-testid*="term"]'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'(\d+)', text)
                if match:
                    return int(match.group(1))
        return None

    def extract_interest_rate(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract interest rate from calculator"""
        selectors = [
            '[data-testid*="zinssatz"]',
            '[data-testid*="interest"]',
            '[data-testid*="rate"]'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'(\d+[.,]\d+)%', text)
                if match:
                    return float(match.group(1).replace(',', '.'))
        return None

    def extract_betriebskosten(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract Betriebskosten (operating costs)"""
        try:
            # Enhanced patterns for better extraction
            all_text = soup.get_text()
            
            # Multiple patterns for operating costs
            operating_cost_patterns = [
                r'[Bb]etriebskosten[:\s]*EUR\s*([\d.,]+)',  # "Betriebskosten: EUR 162,86"
                r'[Bb]etriebskosten[:\s]*€\s*([\d.,]+)',   # "Betriebskosten: €162,86"
                r'[Bb]etriebskosten[:\s]*([\d.,]+)\s*EUR', # "Betriebskosten 162,86 EUR"
                r'[Bb]etriebskosten[:\s]*([\d.,]+)\s*€',   # "Betriebskosten 162,86 €"
                r'[Nn]ebenkosten[:\s]*EUR\s*([\d.,]+)',    # "Nebenkosten: EUR 162,86"
                r'[Nn]ebenkosten[:\s]*€\s*([\d.,]+)',      # "Nebenkosten: €162,86"
                r'[Nn]ebenkosten[:\s]*([\d.,]+)\s*EUR',    # "Nebenkosten 162,86 EUR"
                r'[Nn]ebenkosten[:\s]*([\d.,]+)\s*€',      # "Nebenkosten 162,86 €"
                r'[Oo]perating\s+costs[:\s]*EUR\s*([\d.,]+)',
                r'[Oo]perating\s+costs[:\s]*€\s*([\d.,]+)',
                r'[Mm]aintenance[:\s]*EUR\s*([\d.,]+)',
                r'[Mm]aintenance[:\s]*€\s*([\d.,]+)'
            ]
            
            for pattern in operating_cost_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    cost_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        cost = float(cost_str)
                        if 10 <= cost <= 1000:  # Reasonable range for monthly operating costs
                            return cost
                    except ValueError:
                        continue
            
            # Try selectors as fallback
            selectors = [
                '[data-testid*="betriebskosten"]',
                '[data-testid*="operating"]',
                '[data-testid*="maintenance"]',
                '.betriebskosten',
                '.operating-costs',
                '.maintenance-costs'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        cost_match = re.search(r'([\d.,]+)', text)
                        if cost_match:
                            cost_str = cost_match.group(1).replace('.', '').replace(',', '.')
                            try:
                                cost = float(cost_str)
                                if 10 <= cost <= 1000:
                                    return cost
                            except ValueError:
                                continue
            
            return None
        except Exception as e:
            print(f"Error extracting Betriebskosten: {e}")
            return None

    def calculate_total_monthly_cost(self, monthly_rate: Optional[float], betriebskosten: Optional[float]) -> Optional[float]:
        """Calculate total monthly cost (mortgage + operating costs)"""
        try:
            total = 0
            
            if monthly_rate:
                total += monthly_rate
            
            if betriebskosten:
                total += betriebskosten
            
            return round(total, 2) if total > 0 else None
            
        except Exception as e:
            print(f"Error calculating total monthly cost: {e}")
            return None

    def extract_bezirk(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract Vienna district code"""
        selectors = [
            '[data-testid="object-location-address"]',
            '.address-line',
            '.location-address',
            '.object-location'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                # Look for Vienna district pattern
                match = re.search(r'(\d{4})\s+Wien', text)
                if match:
                    return match.group(1)
        
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract total price"""
        try:
            # Try multiple selectors that actually work on Willhaben
            price_selectors = [
                '[data-testid="contact-box-price-box"]',
                '[data-testid*="price"]',
                '.price-box',
                '.price-value'
            ]
            
            for selector in price_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        # Look for price patterns in the text
                        price_match = re.search(r'€\s*([\d.,]+)', text)
                        if price_match:
                            price_str = price_match.group(1).replace('.', '').replace(',', '.')
                            try:
                                price = float(price_str)
                                if price > 1000:  # Reasonable minimum price
                                    return int(price)  # Convert to int
                            except ValueError:
                                continue
            
            # Fallback: search for any text containing price pattern
            price_texts = soup.find_all(string=re.compile(r'€\s*[\d.,]+'))
            for text in price_texts:
                price_match = re.search(r'€\s*([\d.,]+)', text)
                if price_match:
                    price_str = price_match.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = float(price_str)
                        if price > 1000:  # Reasonable minimum price
                            return int(price)  # Convert to int
                    except ValueError:
                        continue
                        
            return None
        except Exception as e:
            print(f"Error extracting price: {e}")
            return None

    def extract_area(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract living area"""
        try:
            # Try multiple selectors that actually work on Willhaben
            area_selectors = [
                '[data-testid*="attribute"]',
                '.teaser-attribute',
                '.attribute-item',
                '.property-detail'
            ]
            
            for selector in area_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        # Look for area patterns in the text
                        area_match = re.search(r'(\d+(?:[.,]\d+)?)\s*m²', text)
                        if area_match:
                            area_str = area_match.group(1).replace(',', '.')
                            try:
                                area = float(area_str)
                                if area > 10:  # Reasonable minimum area
                                    return area
                            except ValueError:
                                continue
            
            # Fallback: search for any text containing area pattern
            area_texts = soup.find_all(string=re.compile(r'\d+\s*m²'))
            for text in area_texts:
                area_match = re.search(r'(\d+(?:[.,]\d+)?)\s*m²', text)
                if area_match:
                    area_str = area_match.group(1).replace(',', '.')
                    try:
                        area = float(area_str)
                        if area > 10:  # Reasonable minimum area
                            return area
                    except ValueError:
                        continue
                        
            return None
        except Exception as e:
            print(f"Error extracting area: {e}")
            return None

    def extract_rooms(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract number of rooms"""
        try:
            # Try multiple selectors that actually work on Willhaben
            room_selectors = [
                '[data-testid*="attribute"]',
                '.teaser-attribute',
                '.attribute-item',
                '.property-detail'
            ]
            
            for selector in room_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        # Look for room patterns in the text
                        room_match = re.search(r'(\d+)\s*Zimmer', text)
                        if room_match:
                            try:
                                rooms = int(room_match.group(1))
                                if 1 <= rooms <= 20:  # Reasonable range
                                    return rooms
                            except ValueError:
                                continue
            
            # Fallback: search for any text containing room pattern
            room_texts = soup.find_all(string=re.compile(r'\d+\s*Zimmer'))
            for text in room_texts:
                room_match = re.search(r'(\d+)\s*Zimmer', text)
                if room_match:
                    try:
                        rooms = int(room_match.group(1))
                        if 1 <= rooms <= 20:  # Reasonable range
                            return rooms
                    except ValueError:
                        continue
                        
            return None
        except Exception as e:
            print(f"Error extracting rooms: {e}")
            return None

    def extract_year_built(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract construction year"""
        selectors = [
            '[data-testid="attribute-year-built"]',
            '.year-built',
            '.construction-year'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'(\d{4})', text)
                if match:
                    year = int(match.group(1))
                    if 1800 <= year <= 2025:
                        return year
        
        return None

    def extract_floor(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract floor information"""
        try:
            all_text = soup.get_text()
            
            # Enhanced floor patterns
            floor_patterns = [
                r'[Hh]ochparterre',  # "Hochparterre"
                r'[Ee]rdgeschoss',  # "Erdgeschoss"
                r'[Dd]achgeschoss',  # "Dachgeschoss"
                r'(\d+)\.?\s*[Ss]tock',  # "3. Stock"
                r'(\d+)\.?\s*[Ee]tage',  # "3. Etage"
                r'[Ss]tock[:\s]*(\d+)',  # "Stock: 3"
                r'[Ee]tage[:\s]*(\d+)',  # "Etage: 3"
                r'[Ff]loor[:\s]*(\d+)',  # "Floor: 3"
            ]
            
            for pattern in floor_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    if pattern in [r'[Hh]ochparterre', r'[Ee]rdgeschoss', r'[Dd]achgeschoss']:
                        return match.group(0)  # Return the full match
                    else:
                        floor_num = match.group(1)
                        return f"{floor_num}. Stock"
            
            # Try selectors as fallback
            selectors = [
                '[data-testid="attribute-floor"]',
                '.floor-value',
                '.floor-info'
            ]
            
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    return elem.get_text().strip()
            
            return None
        except Exception as e:
            print(f"Error extracting floor: {e}")
            return None

    def extract_condition(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract property condition with more specific patterns"""
        condition_patterns = [
            r"Zustand: (\w+)",
            r"Zustand:\s*([\w\s-]+)",
            (r"Sanierungsbedürftig", "Sanierungsbedürftig"),
            (r"Neuwertig", "Neuwertig"),
            (r"Erstbezug", "Erstbezug")
        ]
        text_content = soup.get_text()
        for pattern, value in condition_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return value if value else match.group(1).strip()
        return None

    def extract_heating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract heating type with more specific patterns"""
        heating_patterns = [
            r"Heizung: (\w+)",
            r"Heizungsart:\s*([\w\s-]+)",
            (r"Etagenheizung", "Etagenheizung"),
            (r"Fußbodenheizung", "Fußbodenheizung"),
            (r"Fernwärme", "Fernwärme"),
            (r"Gasheizung", "Gas")
        ]
        text_content = soup.get_text()
        for pattern, value in heating_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return value if value else match.group(1).strip()
        return None

    def extract_parking(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract parking information"""
        selectors = [
            '[data-testid="attribute-parking"]',
            '.parking-value'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
        
        return None

    def extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract full street address"""
        try:
            # First try to get address from JSON data
            json_data = self.extract_from_json_data(soup)
            if json_data.get('address'):
                return json_data['address']
            
            # Try multiple selectors for address
            address_selectors = [
                '[data-testid="object-location-address"]',
                '.address-line',
                '.location-address',
                '.object-location',
                '.property-address',
                '[data-testid*="address"]',
                '.address-info'
            ]
            
            for selector in address_selectors:
                elem = soup.select_one(selector)
                if elem:
                    address_text = elem.get_text(strip=True)
                    if address_text and len(address_text) > 5:  # Basic validation
                        return address_text
            
            # Try to extract from breadcrumbs or location info
            breadcrumbs = soup.select('.breadcrumb a, [data-testid*="breadcrumb"] a')
            for breadcrumb in breadcrumbs:
                text = breadcrumb.get_text(strip=True)
                if 'Wien' in text and ('Bezirk' in text or 'Döbling' in text):
                    return text
            
            # Look for Vienna district patterns in the text
            all_text = soup.get_text()
            vienna_pattern = r'Wien,?\s*\d{4}\s*[^,\n]*(?:Bezirk|Döbling|Leopoldstadt|Landstraße|Wieden|Margareten|Mariahilf|Neubau|Josefstadt|Alsergrund|Favoriten|Simmering|Meidling|Hietzing|Penzing|Rudolfsheim|Ottakring|Hernals|Währing|Floridsdorf|Brigittenau|Donaustadt|Liesing)[^,\n]*'
            match = re.search(vienna_pattern, all_text, re.IGNORECASE)
            if match:
                return match.group().strip()
            
            return None
            
        except Exception as e:
            print(f"Error extracting address: {e}")
            return None

    def extract_special_comment(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract special comments or conditions"""
        selectors = [
            '.special-conditions',
            '.additional-info',
            '.property-notes'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
        
        return None

    def extract_monatsrate(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract monthly rate"""
        selectors = [
            '[data-testid="mortgageCalculatorForm"]',
            '.mortgage-calculator',
            '.monthly-rate'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'Monatsrate[:\s]*€\s*([\d\.,]+)', text)
                if match:
                    try:
                        return float(match.group(1).replace(',', '.'))
                    except:
                        continue
        
        return None

    def extract_own_funds(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract required own funds"""
        selectors = [
            '[data-testid="ownFunds-input"]',
            '.own-funds',
            '.eigenkapital'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                match = re.search(r'([\d\.,]+)', text)
                if match:
                    try:
                        return float(match.group(1).replace(',', '.'))
                    except:
                        continue
        
        return None

    def extract_energy_class(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract energy class (e.g., A, B, C, D, E, F, G)"""
        try:
            all_text = soup.get_text()
            
            # Patterns for energy class
            energy_patterns = [
                r'[Kk]lasse[:\s]*([A-G])',  # "Klasse D"
                r'[Ee]nergieklasse[:\s]*([A-G])',  # "Energieklasse D"
                r'[Ee]nergy\s+class[:\s]*([A-G])',  # "Energy class D"
                r'[Ee]nergieausweis[:\s]*([A-G])',  # "Energieausweis D"
            ]
            
            for pattern in energy_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    energy_class = match.group(1).upper()
                    if energy_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                        return energy_class
            
            return None
        except Exception as e:
            print(f"Error extracting energy class: {e}")
            return None

    def extract_hwb_value(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract HWB (Heizwärmebedarf) value in kWh/m²/year"""
        try:
            all_text = soup.get_text()
            
            # Patterns for HWB value
            hwb_patterns = [
                r'HWB[:\s]*([\d.,]+)\s*kWh/qm/a',  # "HWB 111,7 kWh/qm/a"
                r'HWB[:\s]*([\d.,]+)\s*kWh/m²/a',  # "HWB 111,7 kWh/m²/a"
                r'HWB[:\s]*([\d.,]+)\s*kWh/m²/Jahr',  # "HWB 111,7 kWh/m²/Jahr"
                r'[Hh]eizwärmebedarf[:\s]*([\d.,]+)\s*kWh',  # "Heizwärmebedarf 111,7 kWh"
                r'[Hh]eating\s+demand[:\s]*([\d.,]+)\s*kWh',  # "Heating demand 111,7 kWh"
            ]
            
            for pattern in hwb_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    hwb_str = match.group(1).replace(',', '.')
                    try:
                        hwb_value = float(hwb_str)
                        if 0 <= hwb_value <= 1000:  # Reasonable range
                            return hwb_value
                    except ValueError:
                        continue
            
            return None
        except Exception as e:
            print(f"Error extracting HWB value: {e}")
            return None

    def extract_heating_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract detailed heating type information"""
        try:
            all_text = soup.get_text()
            
            # Enhanced heating patterns with better boundaries and more comprehensive matching
            heating_patterns = [
                r'[Hh]eizungsart[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Heizungsart: Gasheizung"
                r'[Hh]eizung[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Heizung: Etagenheizung"
                r'[Hh]eating\s+type[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Heating type: Gas"
                r'\b[Gg]asheizung\b',  # "Gasheizung"
                r'\b[Gg]as\s*[Hh]eizung\b',  # "Gas Heizung"
                r'\b[Ee]tagenheizung\b',  # "Etagenheizung"
                r'\b[Zz]entralheizung\b',  # "Zentralheizung"
                r'\b[Ff]ernwärme\b',  # "Fernwärme"
                r'\b[Oo]lheizung\b',  # "Ölheizung"
                r'\b[Ww]ärmepumpe\b',  # "Wärmepumpe"
                r'\b[Ff]ußbodenheizung\b',  # "Fußbodenheizung"
                r'\b[Gg]as\b',  # "Gas" (fallback)
            ]
            
            for pattern in heating_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    heating_type = match.group(1).strip() if match.groups() else match.group(0)
                    # Clean up the heating type
                    heating_type = re.sub(r'[:\s]+$', '', heating_type)
                    if heating_type and len(heating_type) > 2 and len(heating_type) < 50:  # Reasonable length
                        # Normalize common variations
                        heating_type_lower = heating_type.lower()
                        if 'gas' in heating_type_lower:
                            return "Gas"
                        elif 'etagen' in heating_type_lower:
                            return "Etagenheizung"
                        elif 'zentral' in heating_type_lower:
                            return "Zentralheizung"
                        elif 'fernwärme' in heating_type_lower:
                            return "Fernwärme"
                        else:
                            return heating_type
            
            return None
        except Exception as e:
            print(f"Error extracting heating type: {e}")
            return None

    def extract_energy_carrier(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract energy carrier (e.g., Gas, Oil, Electricity)"""
        try:
            all_text = soup.get_text()
            
            # Patterns for energy carrier with better boundaries and more comprehensive matching
            carrier_patterns = [
                r'[Ww]esentliche\s+Energieträger[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Wesentliche Energieträger: Gas"
                r'[Ee]nergieträger[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Energieträger: Gas"
                r'[Ee]nergy\s+carrier[:\s]*([^,\n\r]+?)(?=\s*[,\n\r]|$)',  # "Energy carrier: Gas"
                r'\b[Gg]as\b',  # "Gas"
                r'\b[Oo]l\b',  # "Öl"
                r'\b[Ee]lektrizität\b',  # "Elektrizität"
                r'\b[Ee]lectricity\b',  # "Electricity"
                r'\b[Ff]ernwärme\b',  # "Fernwärme"
                r'\b[Dd]istrict\s+heating\b',  # "District heating"
                r'\b[Ww]ärmepumpe\b',  # "Wärmepumpe"
            ]
            
            for pattern in carrier_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    carrier = match.group(1).strip() if match.groups() else match.group(0)
                    # Clean up the carrier
                    carrier = re.sub(r'[:\s]+$', '', carrier)
                    if carrier and len(carrier) > 1 and len(carrier) < 30:  # Reasonable length
                        # Normalize common variations
                        carrier_lower = carrier.lower()
                        if 'gas' in carrier_lower:
                            return "Gas"
                        elif 'öl' in carrier_lower or 'oil' in carrier_lower:
                            return "Öl"
                        elif 'elektrizität' in carrier_lower or 'electricity' in carrier_lower:
                            return "Elektrizität"
                        elif 'fernwärme' in carrier_lower:
                            return "Fernwärme"
                        else:
                            return carrier
            
            return None
        except Exception as e:
            print(f"Error extracting energy carrier: {e}")
            return None

    def extract_available_from(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract availability with a less greedy pattern"""
        available_patterns = [
            r"Verfügbar ab: (\w+)",
            r"Verfügbar ab sofort",
            r"Beziehbar ab: (\w+)"
        ]
        text_content = soup.get_text()
        for pattern in available_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip() if len(match.groups()) > 0 else "sofort"
        return None

    def calculate_ubahn_distance(self, bezirk: str, address: str) -> Optional[int]:
        """Calculate U-Bahn walking distance"""
        if not bezirk:
            return None
            
        # District-based fallback times
        district_times = {
            '1010': 5, '1020': 8, '1030': 10, '1040': 7, '1050': 9,
            '1060': 6, '1070': 5, '1080': 8, '1090': 7, '1100': 12,
            '1120': 10, '1130': 15, '1140': 12, '1150': 8, '1160': 10,
            '1190': 15, '1210': 12, '1220': 18
        }
        
        return district_times.get(bezirk, 15)

    def get_amenities(self, bezirk: str, address: str) -> Tuple[List[Dict], Optional[int]]:
        """Get nearby amenities and calculate school proximity using real distance calculations"""
        coords = self.geocoder.geocode_address(address)
        amenities: List[Dict] = []
        school_walk_minutes: Optional[int] = None
        
        if coords:
            print(f"📍 Geocoded address: {address} -> {coords.lat:.4f}, {coords.lon:.4f}")
            
            # Calculate actual walking time to nearest school using Vienna schools data
            school_walk_minutes = self.geocoder.get_walking_distance_to_nearest_school(coords)
            
            # Optionally, you can still get other amenities using Overpass API
            # For now, we focus on schools as requested
            
        else:
            print(f"❌ Could not geocode address: {address}")
            
        return amenities, school_walk_minutes

    def get_real_ubahn_walk_minutes(self, address: str) -> Optional[int]:
        """Calculate real walking minutes to nearest U-Bahn station"""
        if not address:
            return None
            
        coords = self.geocoder.geocode_address(address)
        if coords:
            print(f"📍 Geocoded address for U-Bahn: {address} -> {coords.lat:.4f}, {coords.lon:.4f}")
            return self.geocoder.get_walking_distance_to_nearest_ubahn(coords)
        else:
            print(f"❌ Could not geocode address for U-Bahn calculation: {address}")
            return None

    def scrape_search_agent_page(self, alert_url: str, max_pages: int = 3) -> List[Dict]:
        """Scrape search agent page and return matching listings"""
        try:
            all_listings = []
            all_urls = set()
            
            for page in range(1, max_pages + 1):
                if page == 1:
                    page_url = alert_url
                else:
                    separator = '&' if '?' in alert_url else '?'
                    page_url = f"{alert_url}{separator}page={page}"
                    
                print(f"🔍 Scraping page {page}: {page_url}")
                response = self.session.get(page_url)
                if response.status_code != 200:
                    break
                    
                soup = BeautifulSoup(response.content, 'html.parser')
                page_urls = self.extract_listing_urls(soup)
                new_urls = [url for url in page_urls if url not in all_urls]
                
                if not new_urls:
                    print(f"No new URLs found on page {page}, stopping")
                    break
                    
                all_urls.update(new_urls)
                print(f"Found {len(new_urls)} new listings on page {page}")
                
                for url in new_urls:
                    # Check if already in MongoDB
                    if self.mongo.listing_exists(url):
                        print(f"⏭️  Skipping already processed: {url}")
                        continue
                        
                    print(f"🏠 Processing: {url}")
                    listing_data = self.scrape_single_listing(url)
                    
                    if not listing_data:
                        print(f"❌ Failed to scrape: {url}")
                        continue
                    
                    # Use Structured Analyzer to fill missing fields if available
                    if self.structured_analyzer.is_available():
                        print("🧠 Analyzing content with Structured Analyzer...")
                        try:
                            # Get the raw HTML for analysis
                            listing_response = self.session.get(url)
                            if listing_response.status_code == 200:
                                listing_data = self.structured_analyzer.analyze_listing_content(
                                    listing_data, listing_response.text
                                )
                        except Exception as e:
                            print(f"⚠️  Structured analysis failed: {e}")
                    
                    # Convert Amenity objects to dictionaries for MongoDB
                    if 'amenities' in listing_data:
                        amenities_list = []
                        for amenity in listing_data['amenities']:
                            if hasattr(amenity, '__dict__'):
                                # Convert dataclass/object to dict
                                amenities_list.append({
                                    'name': amenity.name,
                                    'distance_m': amenity.distance_m,
                                    'type': amenity.type
                                })
                            else:
                                amenities_list.append(amenity)
                        listing_data['amenities'] = amenities_list
                    
                    # Ensure all data is JSON serializable
                    listing_data = self._ensure_serializable(listing_data)
                    
                    if isinstance(listing_data, dict):
                        # Save to MongoDB (all listings, not just matching ones)
                        listing_data['sent_to_telegram'] = False
                        listing_data['processed_at'] = time.time()
                        
                        if self.mongo.insert_listing(listing_data):
                            print(f"💾 Saved to MongoDB: {url}")
                        else:
                            print(f"⚠️  Already exists in MongoDB: {url}")
                        
                        # Check if it meets criteria
                        if self.meets_criteria(listing_data):
                            print(f"✅ MATCHES CRITERIA: {url}")
                            all_listings.append(listing_data)
                            
                            # Send to Telegram if bot is available
                            if self.telegram_bot:
                                try:
                                    success = self.telegram_bot.send_property_notification(listing_data)
                                    if success:
                                        self.mongo.mark_sent(url)
                                        print(f"📱 Telegram notification sent")
                                    else:
                                        print(f"❌ Failed to send Telegram notification")
                                except Exception as e:
                                    print(f"⚠️  Telegram error: {e}")
                        else:
                            print(f"❌ Does not match criteria: {url}")
                    else:
                        print(f"❌ Does not match criteria because data is not a dict: {url}")

                # Check if there are more pages
                next_page_selectors = [
                    '.pagination .next',
                    '.pagination a[rel="next"]',
                    'a[aria-label="Next"]',
                    '.next-page',
                    'a[href*="page="]'
                ]
                
                has_next = False
                for selector in next_page_selectors:
                    if soup.select_one(selector):
                        has_next = True
                        break
                
                if not has_next:
                    print(f"No next page found, stopping at page {page}")
                    break
                    
            print(f"\n🎯 SUMMARY:")
            print(f"📋 Total URLs processed: {len(all_urls)}")
            print(f"✅ Matching listings: {len(all_listings)}")
            return all_listings
            
        except Exception as e:
            print(f"Error scraping search agent page: {e}")
            return []

    def _ensure_serializable(self, data):
        """Ensure all data is JSON serializable for MongoDB"""
        if isinstance(data, dict):
            return {key: self._ensure_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._ensure_serializable(item) for item in data]
        elif hasattr(data, '__dict__'):
            # Convert objects to dictionaries
            return self._ensure_serializable(data.__dict__)
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # Convert anything else to string
            return str(data)

    def meets_criteria(self, listing_data: Dict) -> bool:
        """Check if listing meets the defined criteria"""
        c = self.criteria
        criteria_checks = []
        print(f"\n{'='*60}")
        print(f"🔍 ANALYZING LISTING: {listing_data.get('url', 'Unknown URL')}")
        print(f"{'='*60}")
        
        # Log all available data for debugging
        print(f"📊 LISTING DATA:")
        print(f"  Bezirk: {listing_data.get('bezirk', 'N/A')}")
        print(f"  Price Total: €{listing_data.get('price_total', 'N/A'):,}" if listing_data.get('price_total') else f"  Price Total: {listing_data.get('price_total', 'N/A')}")
        print(f"  Area: {listing_data.get('area_m2', 'N/A')}m²")
        print(f"  Price per m²: €{listing_data.get('price_per_m2', 'N/A'):,}" if listing_data.get('price_per_m2') else f"  Price per m²: {listing_data.get('price_per_m2', 'N/A')}")
        print(f"  Rooms: {listing_data.get('rooms', 'N/A')}")
        print(f"  Year Built: {listing_data.get('year_built', 'N/A')}")
        print(f"  Address: {listing_data.get('address', 'N/A')}")
        print(f"  Monatsrate: €{listing_data.get('monatsrate', 'N/A'):,}" if listing_data.get('monatsrate') else f"  Monatsrate: {listing_data.get('monatsrate', 'N/A')}")
        print(f"  Calculated Rate: €{listing_data.get('calculated_monatsrate', 'N/A'):,}" if listing_data.get('calculated_monatsrate') else f"  Calculated Rate: {listing_data.get('calculated_monatsrate', 'N/A')}")
        print(f"  Betriebskosten: €{listing_data.get('betriebskosten', 'N/A'):,}" if listing_data.get('betriebskosten') else f"  Betriebskosten: {listing_data.get('betriebskosten', 'N/A')}")
        print(f"  Total Monthly Cost: €{listing_data.get('total_monthly_cost', 'N/A'):,}" if listing_data.get('total_monthly_cost') else f"  Total Monthly Cost: {listing_data.get('total_monthly_cost', 'N/A')}")

        # U-Bahn proximity (max X minutes walking with fallback)
        ubahn_minutes = listing_data.get("ubahn_walk_minutes")
        max_ubahn = c.get("ubahn_max_minutes", 25)
        
        if ubahn_minutes is None:
            # Fallback to district-based estimation
            district_ubahn_times = {
                '1010': 5, '1020': 8, '1030': 10, '1040': 7, '1050': 9,
                '1060': 6, '1070': 5, '1080': 8, '1090': 7, '1100': 12,
                '1120': 10, '1130': 15, '1140': 12, '1150': 8, '1160': 10,
                '1190': 15, '1210': 12, '1220': 18
            }
            ubahn_minutes = district_ubahn_times.get(listing_data.get('bezirk') or '', 15)
            print(f"  🚇 U-Bahn (fallback): {ubahn_minutes} min walk (max {max_ubahn})")
        else:
            print(f"  🚇 U-Bahn: {ubahn_minutes} min walk (max {max_ubahn})")
            
        ubahn_ok = ubahn_minutes <= max_ubahn
        print(f"    → {'✓ PASS' if ubahn_ok else '✗ FAIL'}")
        criteria_checks.append(("U-Bahn proximity", ubahn_ok))

        # Price per m² reasonable
        price_per_m2 = listing_data.get("price_per_m2")
        if price_per_m2 is None:
            price_ok = False
            print(f"  💰 Price per m²: Missing → ✗ FAIL")
        else:
            price_ok = c["price_per_m2_min"] <= price_per_m2 <= c["price_per_m2_max"]
            print(f"  💰 Price per m²: €{price_per_m2:,} (€{c['price_per_m2_min']}-€{c['price_per_m2_max']}) → {'✓ PASS' if price_ok else '✗ FAIL'}")
        criteria_checks.append(("Price per m²", price_ok))

        # Minimum area
        area_m2 = listing_data.get("area_m2")
        if area_m2 is None:
            area_ok = False
            print(f"  📐 Area: Missing → ✗ FAIL")
        else:
            area_ok = area_m2 >= c["area_m2_min"]
            print(f"  📐 Area: {area_m2}m² (min {c['area_m2_min']}) → {'✓ PASS' if area_ok else '✗ FAIL'}")
        criteria_checks.append(("Minimum area", area_ok))

        # Minimum rooms
        rooms = listing_data.get("rooms")
        rooms_min = c.get("rooms_min")
        if rooms is None or rooms_min is None:
            rooms_ok = False
            print(f"  🛏️ Rooms: {rooms} (min {rooms_min}) → ✗ FAIL")
        else:
            rooms_ok = rooms >= rooms_min
            print(f"  🛏️ Rooms: {rooms} (min {rooms_min}) → {'✓ PASS' if rooms_ok else '✗ FAIL'}")
        criteria_checks.append((f"Minimum rooms ({rooms_min})", rooms_ok))

        # Not currently rented or unavailable
        special_comment = listing_data.get("special_comment", "")
        special_comment_lower = special_comment.lower() if special_comment else ""
        availability_ok = not any(keyword in special_comment_lower for keyword in c["availability_keywords"])
        print(f"  ✅ Availability: {special_comment[:50] if special_comment else 'No issues'} → {'✓ PASS' if availability_ok else '✗ FAIL'}")
        criteria_checks.append(("Availability", availability_ok))

        # Construction year - MANDATORY
        year_built = listing_data.get("year_built")
        year_min = c.get("year_built_min")
        if year_built is None:
            year_ok = False  # FAIL if missing year - this is mandatory
            print(f"  🏗️  Year Built: Missing (min {year_min}) → ✗ FAIL (mandatory)")
        else:
            year_ok = year_built >= year_min
            print(f"  🏗️  Year Built: {year_built} (min {year_min}) → {'✓ PASS' if year_ok else '✗ FAIL'}")
        criteria_checks.append(("Construction year", year_ok))

        # School proximity (NEW)
        school_max = c.get("school_max_minutes")
        school_minutes = listing_data.get("school_walk_minutes")
        if school_max is not None:
            if school_minutes is None:
                school_ok = False
                print(f"  🏫 School: Missing (max {school_max}) → ✗ FAIL")
            else:
                school_ok = school_minutes <= school_max
                print(f"  🏫 School: {school_minutes} min walk (max {school_max}) → {'✓ PASS' if school_ok else '✗ FAIL'}")
            criteria_checks.append((f"School proximity (max {school_max})", school_ok))

        # Down payment (Eigenkapital)
        down_payment_min = c.get("down_payment_min")
        own_funds = listing_data.get("own_funds")
        if down_payment_min is not None:
            if own_funds is None:
                down_ok = False
                print(f"  💸 Down payment: Missing (min {down_payment_min}) → ✗ FAIL")
            else:
                down_ok = own_funds >= down_payment_min
                print(f"  💸 Down payment: €{own_funds} (min {down_payment_min}) → {'✓ PASS' if down_ok else '✗ FAIL'}")
            criteria_checks.append((f"Down payment (min {down_payment_min})", down_ok))
        # Interest rate
        interest_rate_max = c.get("interest_rate_max")
        interest_rate = listing_data.get("interest_rate")
        if interest_rate_max is not None:
            if interest_rate is None:
                ir_ok = False
                print(f"  📈 Interest rate: Missing (max {interest_rate_max}) → ✗ FAIL")
            else:
                ir_ok = interest_rate <= interest_rate_max
                print(f"  📈 Interest rate: {interest_rate}% (max {interest_rate_max}) → {'✓ PASS' if ir_ok else '✗ FAIL'}")
            criteria_checks.append((f"Interest rate (max {interest_rate_max})", ir_ok))

        # Energy class (NEW)
        energy_class_min = c.get("energy_class_min")
        energy_class = listing_data.get("energy_class")
        if energy_class_min is not None:
            if energy_class is None:
                energy_ok = True  # Allow missing energy class
                print(f"  ⚡ Energy class: Missing (min {energy_class_min}) → ✓ PASS (optional)")
            else:
                # Convert energy classes to numbers for comparison (A=1, B=2, ..., G=7)
                energy_values = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7}
                energy_min_value = energy_values.get(energy_class_min, 7)
                energy_actual_value = energy_values.get(energy_class, 7)
                energy_ok = energy_actual_value <= energy_min_value  # Lower is better
                print(f"  ⚡ Energy class: {energy_class} (min {energy_class_min}) → {'✓ PASS' if energy_ok else '✗ FAIL'}")
            criteria_checks.append((f"Energy class (min {energy_class_min})", energy_ok))

        # HWB value (NEW)
        hwb_max = c.get("hwb_max")
        hwb_value = listing_data.get("hwb_value")
        if hwb_max is not None:
            if hwb_value is None:
                hwb_ok = True  # Allow missing HWB value
                print(f"  🌡️ HWB value: Missing (max {hwb_max}) → ✓ PASS (optional)")
            else:
                hwb_ok = hwb_value <= hwb_max
                print(f"  🌡️ HWB value: {hwb_value} kWh/m²/Jahr (max {hwb_max}) → {'✓ PASS' if hwb_ok else '✗ FAIL'}")
            criteria_checks.append((f"HWB value (max {hwb_max})", hwb_ok))

        # Calculate overall result
        passed_criteria = sum(1 for _, passed in criteria_checks if passed)
        total_criteria = len(criteria_checks)
        print(f"\n📋 CRITERIA SUMMARY:")
        print(f"  Passed: {passed_criteria}/{total_criteria}")
        for criterion, passed in criteria_checks:
            status = "✓" if passed else "✗"
            print(f"    {status} {criterion}")
        
        final_result = all(check[1] for check in criteria_checks)
        print(f"\n🎯 FINAL RESULT: {'✅ MATCHES CRITERIA' if final_result else '❌ DOES NOT MATCH'}")
        print(f"{'='*60}\n")
        
        return final_result 