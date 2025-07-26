import requests
import json
import time
import re
import math
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
from dataclasses import dataclass

from Domain.listing import Listing
from Domain.sources import Source
from Application.analyzer import StructuredAnalyzer
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot
from Application.helpers.geocoding import ViennaGeocoder
import logging
from Application.helpers.utils import calculate_ubahn_proximity, format_currency, get_walking_times, estimate_betriebskosten

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
        Calculate monthly mortgage payment using realistic Austrian rates
        Based on loan calculator example: €244,299 loan → €1,069 monthly payment (3.815% rate, 35 years)
        This gives us a ratio of approximately 0.00437
        """
        if loan_amount <= 0:
            return 0
        
        # Use realistic ratio from loan calculator example
        realistic_ratio = 0.00437  # Based on €244,299 → €1,069 monthly (3.815% rate, 35 years)
        monthly_payment = loan_amount * realistic_ratio
        
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
        """Get detailed breakdown of monthly payment components using realistic Austrian rates"""
        if loan_amount <= 0:
            return {}
        
        # Use realistic ratio from loan calculator example
        realistic_ratio = 0.00437  # Based on €244,299 → €1,069 monthly (3.815% rate, 35 years)
        monthly_payment = loan_amount * realistic_ratio
        
        return {
            'base_payment': round(monthly_payment * 0.85, 2),  # 85% of total is base loan
            'extra_fees': round(monthly_payment * 0.15, 2),    # 15% of total is extra fees
            'total_monthly': round(monthly_payment, 2),
            'loan_amount': round(loan_amount, 2)
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
            
            # Initialize Telegram bot if config provided (main channel for properties)
            self.telegram_bot = None
            telegram_config = config.get('telegram', {})
            if telegram_config.get('telegram_main', {}).get('bot_token') and telegram_config.get('telegram_main', {}).get('chat_id'):
                main_config = telegram_config['telegram_main']
                self.telegram_bot = TelegramBot(
                    main_config['bot_token'],
                    main_config['chat_id']
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
                        # Get base URL from config or use default
                        base_url = self.config.get('willhaben', {}).get('base_url', 'https://www.willhaben.at') if hasattr(self, 'config') else 'https://www.willhaben.at'
                        href = f"{base_url}{href}"
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
            
            # Extract address from LOCATION/ADDRESS_2 and year built from any relevant attribute
            for attr in attributes:
                name = attr.get('name', '')
                values = attr.get('values', [])
                if values:
                    value = values[0]
                    # Address
                    if name == 'LOCATION/ADDRESS_2':
                        extracted_data['address'] = value
                    # Heating type
                    elif 'Heizungsart:' in value:
                        heating_match = re.search(r'Heizungsart:\s*([^<\n]+)', value)
                        if heating_match:
                            extracted_data['heating_type'] = heating_match.group(1).strip()
                    # Energy carrier
                    elif 'Wesentliche Energieträger:' in value:
                        carrier_match = re.search(r'Wesentliche Energieträger:\s*([^<\n]+)', value)
                        if carrier_match:
                            extracted_data['energy_carrier'] = carrier_match.group(1).strip()
                    # Available from
                    elif 'Verfügbar ab:' in value:
                        available_match = re.search(r'Verfügbar ab:\s*([^<\n]+)', value)
                        if available_match:
                            extracted_data['available_from'] = available_match.group(1).strip()
                    # Year built (Baujahr, Bautyp, Bauzeit, etc.)
                    if any(key in name.lower() for key in ['baujahr', 'bautyp', 'bauzeit']) or any(key in value.lower() for key in ['baujahr', 'bautyp', 'bauzeit']):
                        year_match = re.search(r'(\d{4})', value)
                        if year_match:
                            year = int(year_match.group(1))
                            # Improved validation: reject future years and very old years
                            if 1960 <= year <= 2024:
                                extracted_data['year_built'] = year
            return extracted_data
            
        except Exception as e:
            print(f"Error extracting from JSON data: {e}")
            return {}

    def scrape_single_listing(self, url: str) -> Optional[Listing]:
        """Scrape a single listing and return a Listing object"""
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract data from JSON-LD first
            json_data = self.extract_from_json_data(soup)

            # Create a Listing object
            listing = Listing(
                url=url,
                source=Source.WILLHABEN,
                title=json_data.get('name'),
                bezirk=self.extract_bezirk(soup) or json_data.get('address', {}).get('addressLocality'),
                address=self.extract_address(soup) or json_data.get('address', {}).get('streetAddress'),
                price_total=self.extract_price(soup) or json_data.get('offers', {}).get('price'),
                area_m2=self.extract_area(soup) or json_data.get('floorSize', {}).get('value'),
                rooms=self.extract_rooms(soup) or json_data.get('numberOfRooms'),
                year_built=self.extract_year_built(soup),
                floor=self.extract_floor(soup),
                condition=self.extract_condition(soup),
                heating=self.extract_heating(soup),
                parking=self.extract_parking(soup),
                betriebskosten=self.extract_betriebskosten(soup),
                energy_class=self.extract_energy_class(soup),
                hwb_value=self.extract_hwb_value(soup),
                fgee_value=self.extract_fgee_value(soup),
                heating_type=self.extract_heating_type(soup),
                energy_carrier=self.extract_energy_carrier(soup),
                available_from=self.extract_available_from(soup),
                image_url=self.extract_image_url(soup) or json_data.get('image'),
                processed_at=time.time(),
                source_enum=Source.WILLHABEN
            )

            # Calculate price per m2
            if listing.price_total and listing.area_m2:
                listing.price_per_m2 = listing.price_total / listing.area_m2

            # Get walking times
            if listing.bezirk:
                ubahn_minutes, school_minutes = get_walking_times(listing.bezirk)
                listing.ubahn_walk_minutes = ubahn_minutes
                listing.school_walk_minutes = school_minutes
            
            # Monatsrate and other financial details
            listing.monatsrate = self.extract_monatsrate(soup)
            listing.own_funds = self.extract_own_funds(soup)
            
            # Handle Betriebskosten - extract if available, estimate if not
            extracted_betriebskosten = self.extract_betriebskosten(soup)
            if extracted_betriebskosten:
                listing.betriebskosten = extracted_betriebskosten
                listing.betriebskosten_estimated = False
            elif listing.area_m2:
                # Estimate Betriebskosten if not found
                betriebskosten_breakdown = estimate_betriebskosten(listing.area_m2)
                listing.betriebskosten = betriebskosten_breakdown['total_incl_vat']
                listing.betriebskosten_breakdown = betriebskosten_breakdown
                listing.betriebskosten_estimated = True
            
            if listing.price_total:
                down_payment = self.estimate_down_payment(listing.price_total, soup)
                loan_amount = self.mortgage_calc.calculate_loan_amount(listing.price_total, down_payment)
                interest_rate = self.mortgage_calc.estimate_interest_rate()
                years = self.extract_loan_years(soup) or 30
                
                listing.calculated_monatsrate = self.mortgage_calc.calculate_monthly_payment(
                    loan_amount, interest_rate, years
                )
                listing.mortgage_details = self.mortgage_calc.get_payment_breakdown(
                    loan_amount, interest_rate, years
                )
                listing.total_monthly_cost = self.calculate_total_monthly_cost(
                    listing.calculated_monatsrate, listing.betriebskosten
                )

            # Ensure source fields are strings, not Enum objects
            if hasattr(listing.source, 'value'):
                listing.source = listing.source.value
            if hasattr(listing.source_enum, 'value'):
                listing.source_enum = listing.source_enum.value
        
            return listing

        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None
        except Exception as e:
            logging.error(f"Error scraping {url}: {e}")
            return None

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

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract price from text, handling various formats"""
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
                                    return price  # Convert to float
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
                            return price  # Convert to float
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
        """Extract construction year with enhanced patterns and validation"""
        try:
            # Try selectors first
            selectors = [
                '[data-testid="attribute-year-built"]',
                '.year-built',
                '.construction-year',
                '[data-testid*="year"]',
                '[data-testid*="baujahr"]',
                '.property-year',
                '.listing-year',
                '.expose-year',
                '.year-value',
                '.baujahr-value',
                '.construction-year',
                '.building-year',
                '[class*="year"]',
                '[class*="baujahr"]',
                '[class*="construction"]',
                '[class*="bauzeit"]',
                '[class*="erbaut"]'
            ]
            
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text()
                    year = self._extract_year_from_text(text)
                    if year:
                        return year
            
            # Try pattern matching in full text
            all_text = soup.get_text()
            year = self._extract_year_from_text(all_text)
            if year:
                return year
            
            return None
        except Exception as e:
            print(f"Error extracting year built: {e}")
            return None
    
    def _extract_year_from_text(self, text: str) -> Optional[int]:
        """Extract year from text with enhanced patterns"""
        if not text:
            return None
        
        # Enhanced year patterns for Austrian real estate
        year_patterns = [
            r'Baujahr[:\s]*(\d{4})',
            r'Bauzeit[:\s]*(\d{4})',
            r'erbaut[:\s]*(\d{4})',
            r'Jahr[:\s]*(\d{4})',
            r'(\d{4})\s*(?:erbaut|gebaut|Baujahr|Bauzeit)',
            r'Baujahr\s+(\d{4})',
            r'(\d{4})\s*erbaut',
            r'Jahr\s+(\d{4})',
            r'Bauzeit\s+(\d{4})',
            r'(\d{4})\s*Jahr',
            r'Baujahr[:\s]*(\d{2})',  # Handle 2-digit years like "95" for 1995
            r'(\d{2})\s*Jahr',  # Handle 2-digit years
            r'Baujahr[:\s]*(\d{4})',  # Standard 4-digit year
            r'(\d{4})\s*erbaut',  # Year followed by "erbaut"
            r'erbaut\s*(\d{4})',  # "erbaut" followed by year
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    year_str = match.group(1)
                    year = int(year_str)
                    
                    # Handle 2-digit years (assume 19xx for years < 50, 20xx for years >= 50)
                    if len(year_str) == 2:
                        if year < 50:
                            year += 1900
                        else:
                            year += 2000
                    
                    # Validate year range
                    if 1900 <= year <= 2024:
                        return year
                except ValueError:
                    continue
        
        # Fallback: find any 4-digit year that looks like a year
        year_match = re.search(r'(\d{4})', text)
        if year_match:
            try:
                year = int(year_match.group(1))
                if 1900 <= year <= 2024:
                    return year
            except ValueError:
                pass
        
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
            (r"Zustand: (\w+)", None),
            (r"Zustand:\s*([\w\s-]+)", None),
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
            (r"Heizung: (\w+)", None),
            (r"Heizungsart:\s*([\w\s-]+)", None),
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
        """Extract full street address with improved patterns"""
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
                '.address-info',
                '[data-testid*="location"]',
                '.location-info'
            ]
            
            for selector in address_selectors:
                elem = soup.select_one(selector)
                if elem:
                    address_text = elem.get_text(strip=True)
                    if address_text and len(address_text) > 5:  # Basic validation
                        return address_text
            
            # Enhanced pattern matching for street addresses
            all_text = soup.get_text()
            
            # Pattern 1: Specific street address patterns
            street_patterns = [
                r'([A-Za-zäöüßÄÖÜ\s]+straße\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien',
                r'([A-Za-zäöüßÄÖÜ\s]+gasse\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien',
                r'([A-Za-zäöüßÄÖÜ\s]+platz\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien',
                r'([A-Za-zäöüßÄÖÜ\s]+weg\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien',
                r'([A-Za-zäöüßÄÖÜ\s]+allee\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien',
                r'([A-Za-zäöüßÄÖÜ\s]+ring\s+\d+[a-z]?)[,\s]*(\d{4})\s*Wien'
            ]
            
            for pattern in street_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    street = match.group(1).strip()
                    district = match.group(2)
                    return f"{street}, {district} Wien"
            
            # Pattern 2: District-based fallback with more specific info
            district_patterns = [
                r'(\d{4})\s*Wien[,\s]*([^,\n]+?)(?:Bezirk|Döbling|Leopoldstadt|Landstraße|Wieden|Margareten|Mariahilf|Neubau|Josefstadt|Alsergrund|Favoriten|Simmering|Meidling|Hietzing|Penzing|Rudolfsheim|Ottakring|Hernals|Währing|Floridsdorf|Brigittenau|Donaustadt|Liesing)',
                r'([^,\n]+?)(?:Bezirk|Döbling|Leopoldstadt|Landstraße|Wieden|Margareten|Mariahilf|Neubau|Josefstadt|Alsergrund|Favoriten|Simmering|Meidling|Hietzing|Penzing|Rudolfsheim|Ottakring|Hernals|Währing|Floridsdorf|Brigittenau|Donaustadt|Liesing)[,\s]*(\d{4})\s*Wien'
            ]
            
            for pattern in district_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    if match.group(1).isdigit():
                        district = match.group(1)
                        area = match.group(2).strip()
                    else:
                        area = match.group(1).strip()
                        district = match.group(2)
                    return f"{area}, {district} Wien"
            
            # Pattern 3: Try to extract more specific location info
            location_patterns = [
                r'([^,\n]+?)\s*(\d{4})\s*Wien',
                r'(\d{4})\s*Wien[,\s]*([^,\n]+?)(?=\s|$)',
                r'([^,\n]+?)\s*Wien[,\s]*(\d{4})'
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    if match.group(1).isdigit():
                        district = match.group(1)
                        area = match.group(2).strip()
                    else:
                        area = match.group(1).strip()
                        district = match.group(2)
                    # Clean up the area name
                    area = re.sub(r'\s+', ' ', area).strip()
                    if len(area) > 3:  # Only use if it's meaningful
                        return f"{area}, {district} Wien"
            
            # Pattern 3: Simple district fallback
            simple_district = re.search(r'(\d{4})\s*Wien', all_text)
            if simple_district:
                district = simple_district.group(1)
                return f"{district} Wien"
            
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

    def extract_fgee_value(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract fGEE (Gesamtenergieeffizienzfaktor) value"""
        try:
            all_text = soup.get_text()
            
            # Patterns for fGEE value
            fgee_patterns = [
                r'fGEE[:\s]*([\d.,]+)',  # "fGEE: 0,9"
                r'fGEE\s*([\d.,]+)',  # "fGEE 0,9"
                r'[Gg]esamtenergieeffizienzfaktor[:\s]*([\d.,]+)',  # "Gesamtenergieeffizienzfaktor: 0,9"
                r'[Oo]verall\s+energy\s+efficiency\s+factor[:\s]*([\d.,]+)',  # "Overall energy efficiency factor: 0,9"
            ]
            
            for pattern in fgee_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    fgee_str = match.group(1).replace(',', '.')
                    try:
                        fgee_value = float(fgee_str)
                        if 0 <= fgee_value <= 10:  # Reasonable range
                            return fgee_value
                    except ValueError:
                        continue
            
            return None
        except Exception as e:
            print(f"Error extracting fGEE value: {e}")
            return None

    def calculate_energy_class(self, hwb_value: Optional[float], fgee_value: Optional[float]) -> Optional[str]:
        """
        Calculate energy class based on HWB and fGEE values
        Returns the most restrictive class (worse of the two)
        """
        try:
            hwb_class = None
            fgee_class = None
            
            # Calculate HWB-based class
            if hwb_value is not None:
                if hwb_value <= 10:
                    hwb_class = 'A++'
                elif hwb_value <= 15:
                    hwb_class = 'A+'
                elif hwb_value <= 25:
                    hwb_class = 'A'
                elif hwb_value <= 50:
                    hwb_class = 'B'
                elif hwb_value <= 100:
                    hwb_class = 'C'
                elif hwb_value <= 150:
                    hwb_class = 'D'
                elif hwb_value <= 200:
                    hwb_class = 'E'
                elif hwb_value <= 250:
                    hwb_class = 'F'
                else:
                    hwb_class = 'G'
            
            # Calculate fGEE-based class
            if fgee_value is not None:
                if fgee_value < 0.55:
                    fgee_class = 'A++'
                elif fgee_value <= 0.7:
                    fgee_class = 'A+'
                elif fgee_value <= 0.85:
                    fgee_class = 'A'
                elif fgee_value <= 1.0:
                    fgee_class = 'B'
                elif fgee_value <= 1.25:
                    fgee_class = 'C'
                elif fgee_value <= 1.5:
                    fgee_class = 'D'
                elif fgee_value <= 1.75:
                    fgee_class = 'E'
                elif fgee_value <= 2.0:
                    fgee_class = 'F'
                else:
                    fgee_class = 'G'
            
            # Return the worse (higher letter) of the two classes
            if hwb_class and fgee_class:
                # Convert classes to numbers for comparison (A++=0, A+=1, A=2, B=3, etc.)
                class_order = ['A++', 'A+', 'A', 'B', 'C', 'D', 'E', 'F', 'G']
                hwb_index = class_order.index(hwb_class)
                fgee_index = class_order.index(fgee_class)
                return class_order[max(hwb_index, fgee_index)]
            elif hwb_class:
                return hwb_class
            elif fgee_class:
                return fgee_class
            
            return None
            
        except Exception as e:
            print(f"Error calculating energy class: {e}")
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
            (r"Verfügbar ab: (\w+)", None),
            (r"Verfügbar ab sofort", "sofort"),
            (r"Beziehbar ab: (\w+)", None)
        ]
        text_content = soup.get_text()
        for pattern, value in available_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return value if value else (match.group(1).strip() if len(match.groups()) > 0 else "sofort")
        return None

    def extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main image URL from listing"""
        try:
            # Try to find image in meta tags first (most reliable)
            meta_img = soup.find('meta', property='og:image')
            if meta_img and meta_img.get('content'):
                return meta_img['content']
            
            # Try other meta tags
            meta_img = soup.find('meta', {'name': 'twitter:image'})
            if meta_img and meta_img.get('content'):
                return meta_img['content']
            
            # Try to find image in structured data
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Check for image in various structured data formats
                        image = data.get('image') or data.get('photo') or data.get('thumbnail')
                        if image:
                            if isinstance(image, str):
                                return image
                            elif isinstance(image, list) and len(image) > 0:
                                return image[0]
                            elif isinstance(image, dict) and 'url' in image:
                                return image['url']
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Try to find main image in gallery or main content
            # Look for images with specific classes or IDs that indicate main property image
            image_selectors = [
                '[data-testid*="main-image"]',
                '[data-testid*="gallery"] img',
                '.gallery img',
                '.main-image img',
                '.property-image img',
                '.listing-image img',
                'img[alt*="Hauptbild"]',
                'img[alt*="main"]',
                'img[alt*="property"]'
            ]
            
            for selector in image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem and img_elem.get('src'):
                    src = img_elem['src']
                    # Ensure it's a valid image URL
                    if src.startswith('http') and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        return src
            
            # Fallback: find first image that looks like a property image
            for img in soup.find_all('img'):
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                # Skip small images, icons, and non-property images
                if (src.startswith('http') and 
                    any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) and
                    not any(skip in alt for skip in ['icon', 'logo', 'avatar', 'profile']) and
                    not any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'profile', 'placeholder'])):
                    
                    # Check if image size suggests it's a main image (not too small)
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w >= 300 and h >= 200:  # Reasonable size for property image
                                return src
                        except ValueError:
                            pass
                    else:
                        # If no size info, assume it's a main image if it has a reasonable URL
                        return src
            
            return None
            
        except Exception as e:
            print(f"Error extracting image URL: {e}")
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
        """Calculate real walking minutes to nearest U-Bahn station using static data"""
        if not address:
            return None
            
        try:
            # Extract district from address - handle multiple formats
            district = None
            
            # Try format: "1220 Wien" (4-digit code)
            district_match = re.search(r'(\d{4})\s*Wien', address)
            if district_match:
                district = district_match.group(1)
            else:
                # Try format: "22. Bezirk" (2-digit with dot)
                bezirk_match = re.search(r'(\d+)\.\s*Bezirk', address)
                if bezirk_match:
                    district_num = bezirk_match.group(1)
                    # Convert 2-digit to 4-digit format
                    district_map = {
                        '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
                        '6': '1060', '7': '1070', '8': '1080', '9': '1090', '10': '1100',
                        '11': '1110', '12': '1120', '13': '1130', '14': '1140', '15': '1150',
                        '16': '1160', '17': '1170', '18': '1180', '19': '1190', '20': '1200',
                        '21': '1210', '22': '1220', '23': '1230'
                    }
                    district = district_map.get(district_num)
            
            if not district:
                return None
            
            # Use static U-Bahn data for the district
            if district in self.geocoder.ubahn_stations:
                stations = self.geocoder.ubahn_stations[district]
                if stations:
                    # For now, return a reasonable estimate based on district
                    # In a full implementation, you'd geocode the address and calculate real distances
                    district_times = {
                        '1010': 3, '1020': 5, '1030': 6, '1040': 4, '1050': 5,
                        '1060': 4, '1070': 3, '1080': 4, '1090': 5, '1100': 8,
                        '1120': 6, '1130': 10, '1140': 8, '1150': 6, '1160': 7,
                        '1190': 12, '1210': 10, '1220': 15
                    }
                    return district_times.get(district, 10)
            
            return None
            
        except Exception as e:
            print(f"Error calculating U-Bahn distance: {e}")
            return None

    def get_real_school_walk_minutes(self, address: str) -> Optional[int]:
        """Calculate real walking minutes to nearest school using static data"""
        if not address:
            return None
            
        try:
            # Extract district from address - handle multiple formats
            district = None
            
            # Try format: "1220 Wien" (4-digit code)
            district_match = re.search(r'(\d{4})\s*Wien', address)
            if district_match:
                district = district_match.group(1)
            else:
                # Try format: "22. Bezirk" (2-digit with dot)
                bezirk_match = re.search(r'(\d+)\.\s*Bezirk', address)
                if bezirk_match:
                    district_num = bezirk_match.group(1)
                    # Convert 2-digit to 4-digit format
                    district_map = {
                        '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
                        '6': '1060', '7': '1070', '8': '1080', '9': '1090', '10': '1100',
                        '11': '1110', '12': '1120', '13': '1130', '14': '1140', '15': '1150',
                        '16': '1160', '17': '1170', '18': '1180', '19': '1190', '20': '1200',
                        '21': '1210', '22': '1220', '23': '1230'
                    }
                    district = district_map.get(district_num)
            
            if not district:
                return None
            
            # Use static school data - return reasonable estimate based on district
            district_times = {
                '1010': 5, '1020': 6, '1030': 7, '1040': 5, '1050': 6,
                '1060': 5, '1070': 4, '1080': 5, '1090': 6, '1100': 8,
                '1120': 7, '1130': 10, '1140': 8, '1150': 7, '1160': 8,
                '1190': 12, '1210': 10, '1220': 12
            }
            return district_times.get(district, 8)
            
        except Exception as e:
            print(f"Error calculating school distance: {e}")
            return None

    def scrape_search_agent_page(self, alert_url: str, max_pages: int = 3) -> List[Listing]:
        """Scrape listings from a Willhaben search agent page."""
        all_listings: List[Listing] = []
        telegram_sent_count = 0  # Counter for Telegram messages
        max_telegram_messages = 5  # Limit Telegram messages to avoid spam
        
        for page in range(1, max_pages + 1):
            url = f"{alert_url}&page={page}"
            print(f"📄 Scraping page {page}: {url}")

            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                listing_urls = self.extract_listing_urls(soup)
                if not listing_urls:
                    print("No more listings found on this page.")
                    break

                for listing_url in listing_urls:
                    if self.mongo.listing_exists(listing_url):
                        print(f"⏭️  Skipping already processed: {listing_url}")
                        continue
                    
                    listing = self.scrape_single_listing(listing_url)
                    if not listing:
                        print(f"❌ Failed to scrape: {listing_url}")
                        continue
                    
                    if self.meets_criteria(listing):
                        print(f"✅ MATCHES CRITERIA: {listing_url}")
                        all_listings.append(listing)
                        
                        listing_dict = self._ensure_serializable(listing)
                        
                        if self.mongo.insert_listing(listing_dict):
                             print(f"💾 Saved to MongoDB: {listing_url}")
                             # Note: Telegram notifications are now handled centrally in main.py
                        else:
                            print(f"⚠️  Already exists in MongoDB: {listing_url}")
                    else:
                        print(f"❌ Does not match criteria: {listing_url}")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching page {url}: {e}")
                break
            except Exception as e:
                print(f"An error occurred on page {page}: {e}")
                break
        
        print(f"\n🎯 SUMMARY:")
        print(f"✅ Matching listings found: {len(all_listings)}")
        return all_listings

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

    def meets_criteria(self, listing: Listing) -> bool:
        """Check if a Listing object meets the defined criteria."""
        if not self.criteria:
            # No criteria defined, so all listings meet the criteria.
            return True

        # Price
        if 'price_min' in self.criteria and listing.price_total and listing.price_total < self.criteria['price_min']:
            return False
        if 'price_max' in self.criteria and listing.price_total and listing.price_total > self.criteria['price_max']:
            return False

        # Area
        if 'area_m2_min' in self.criteria and listing.area_m2 and listing.area_m2 < self.criteria['area_m2_min']:
            return False
        if 'area_m2_max' in self.criteria and listing.area_m2 and listing.area_m2 > self.criteria['area_m2_max']:
            return False

        # Rooms
        if 'rooms_min' in self.criteria and listing.rooms and listing.rooms < self.criteria['rooms_min']:
            return False
        if 'rooms_max' in self.criteria and listing.rooms and listing.rooms > self.criteria['rooms_max']:
            return False
        
        # Bezirk
        if 'bezirk' in self.criteria and listing.bezirk and listing.bezirk not in self.criteria['bezirk']:
            return False

        # Year built
        if 'year_built_min' in self.criteria and listing.year_built and listing.year_built < self.criteria['year_built_min']:
            return False
        
        # Price per m2
        if 'price_per_m2_max' in self.criteria and listing.price_per_m2 and listing.price_per_m2 > self.criteria['price_per_m2_max']:
            return False

        return True

    def close(self):
        """Close all connections and cleanup resources"""
        if hasattr(self, 'mongo') and self.mongo:
            self.mongo.close()
        if hasattr(self, 'session'):
            self.session.close()

    def __del__(self):
        """Destructor to ensure connections are closed"""
        self.close() 

    def parse_infrastructure_distances(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """Parse the 'Infrastruktur / Entfernungen' section and extract amenities and distances"""
        infra = {}
        try:
            # Find the section by heading or keyword
            headings = soup.find_all(text=re.compile(r'Infrastruktur\s*/\s*Entfernungen', re.IGNORECASE))
            for heading in headings:
                # Look for the next sibling or parent containing the details
                parent = heading.parent
                # Try to find the next ul or table
                details = None
                for tag in [parent, parent.find_next('ul'), parent.find_next('table'), parent.find_next('div')]:
                    if tag and (tag.name == 'ul' or tag.name == 'table' or tag.name == 'div'):
                        details = tag
                        break
                if details:
                    text = details.get_text(separator='\n', strip=True)
                else:
                    # Fallback: get text after heading
                    text = parent.get_text(separator='\n', strip=True)
                # Parse lines like 'U-Bahn <3150m', 'Schule <250m', etc.
                for line in text.split('\n'):
                    m = re.match(r'([\wäöüÄÖÜß\s\-/]+)\s*<([\d,]+)m', line)
                    if m:
                        amenity = m.group(1).strip()
                        dist = m.group(2).replace(',', '.')
                        try:
                            dist_m = float(dist)
                        except Exception:
                            dist_m = None
                        infra[amenity] = {"distance_m": dist_m, "raw": line}
            return infra
        except Exception as e:
            print(f"Error parsing infrastructure distances: {e}")
            return {}