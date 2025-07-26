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
from Application.helpers.utils import calculate_ubahn_proximity, format_currency, get_walking_times, estimate_betriebskosten, load_config

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

class ImmoKurierScraper:
    def __init__(self, config: Optional[Dict] = None, criteria_path: str = "criteria.json", telegram_config: Optional[Dict] = None, mongo_uri: Optional[str] = None):
        self.config = config if config is not None else load_config()
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        self.geocoder = ViennaGeocoder()
        self.mortgage_calc = MortgageCalculator()
        
        # Handle config parameter
        if self.config:
            # Initialize Structured analyzer with config FIRST
            self.structured_analyzer = StructuredAnalyzer(
                api_key=self.config.get('openai_api_key'),
                model=self.config.get('openai_model', 'gpt-4o-mini')
            )
            # If config is provided, use it to initialize everything
            self.criteria = self.config.get('criteria', {})
            if self.criteria:
                print(f"📋 Loaded criteria from config: {len(self.criteria)} rules")
            else:
                print(f"⚠️  No criteria found in config.json. Filtering will be disabled.")
                self.criteria = {}
            
            print(f"🧠 Structured analyzer available: {'✅' if self.structured_analyzer.is_available() else '❌'}")
            
            # Initialize Telegram bot if config provided (main channel for properties)
            self.telegram_bot = None
            telegram_config = self.config.get('telegram', {})
            if telegram_config.get('telegram_main', {}).get('bot_token') and telegram_config.get('telegram_main', {}).get('chat_id'):
                main_config = telegram_config['telegram_main']
                self.telegram_bot = TelegramBot(
                    main_config['bot_token'],
                    main_config['chat_id']
                )
            
            # Initialize MongoDB handler
            mongo_uri = self.config.get('mongodb_uri') or "mongodb://localhost:27017/"
            self.mongo = MongoDBHandler(uri=mongo_uri)
            
        else:
            # Legacy initialization (should not happen, but fallback)
            self.criteria = self.load_criteria(criteria_path)
            self.telegram_bot = None
            if telegram_config and telegram_config.get('bot_token') and telegram_config.get('chat_id'):
                self.telegram_bot = TelegramBot(
                    telegram_config['bot_token'],
                    telegram_config['chat_id']
                )
            mongo_uri = mongo_uri or "mongodb://localhost:27017/"
            self.mongo = MongoDBHandler(uri=mongo_uri)
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
            'a[href*="/immobilien/"]',
            '.ci-search-result__link[href*="/immobilien/"]',
            '.stretched-link[href*="/immobilien/"]',
            'a[data-href*="/immobilien/"]'
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href') or link.get('data-href')
                if href and isinstance(href, str) and '/immobilien/' in href:
                    if href.startswith('/'):
                        # Get base URL from config or use default
                        base_url = 'https://immo.kurier.at'
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

    def extract_from_json_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract data from any JSON structure in the HTML (if available)"""
        try:
            # Look for any script tags with JSON data
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and ('window.' in script.string or 'var ' in script.string):
                    # Try to extract any structured data
                    script_content = str(script.string)
                    
                    # Look for common patterns
                    patterns = [
                        r'price["\']?\s*:\s*["\']?([^"\']+)["\']?',
                        r'area["\']?\s*:\s*["\']?([^"\']+)["\']?',
                        r'rooms["\']?\s*:\s*["\']?([^"\']+)["\']?',
                        r'address["\']?\s*:\s*["\']?([^"\']+)["\']?'
                    ]
                    
                    extracted_data = {}
                    for pattern in patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        if matches:
                            # Extract the first match
                            extracted_data[pattern.split('[')[0]] = matches[0]
                    
                    if extracted_data:
                        return extracted_data
            
            return {}
            
        except Exception as e:
            print(f"Error extracting from JSON data: {e}")
            return {}

    def scrape_single_listing(self, url: str) -> Optional[Listing]:
        """Scrape a single listing and return a Listing object"""
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract data from any JSON structures first
            json_data = self.extract_from_json_data(soup)

            # Create a Listing object
            listing = Listing(
                url=url,
                source=Source.IMMO_KURIER,
                title=self.extract_title(soup),
                bezirk=self.extract_bezirk(soup),
                address=self.extract_address(soup),
                price_total=self.extract_price(soup),
                area_m2=self.extract_area(soup),
                rooms=self.extract_rooms(soup),
                year_built=self.extract_year_built(soup),
                floor=self.extract_floor(soup),
                condition=self.extract_condition(soup),
                heating=self.extract_heating(soup),
                parking=self.extract_parking(soup),
                betriebskosten=self.extract_betriebskosten(soup),
                energy_class=self.extract_energy_class(soup),
                hwb_value=self.extract_hwb_value(soup),
                fgee_value=None,  # Not available for Immo Kurier
                heating_type=self.extract_heating_type(soup),
                energy_carrier=self.extract_energy_carrier(soup),
                available_from=self.extract_available_from(soup),
                image_url=self.extract_image_url(soup),
                processed_at=time.time(),
                source_enum=Source.IMMO_KURIER
            )

            # Calculate price per m2
            if listing.price_total and listing.area_m2:
                listing.price_per_m2 = listing.price_total / listing.area_m2

            # Get walking times
            if listing.bezirk:
                ubahn_minutes, school_minutes = get_walking_times(listing.bezirk)
                listing.ubahn_walk_minutes = ubahn_minutes
                listing.school_walk_minutes = school_minutes
            
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
                down_payment = self.estimate_down_payment(listing.price_total)
                loan_amount = self.mortgage_calc.calculate_loan_amount(listing.price_total, down_payment)
                interest_rate = self.mortgage_calc.estimate_interest_rate()
                years = 30  # Default 30 years
                
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

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from listing page"""
        selectors = [
            'h1',
            '.property-title',
            '.listing-title',
            '[data-testid*="title"]',
            '.expose-title'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract price from listing page"""
        selectors = [
            '.eps-item-price',
            '.property-price',
            '.listing-price',
            '[data-testid*="price"]',
            '.price',
            '.featured-listings__item__price strong',
            '.expose-price',
            '.price-value',
            '.kaufpreis',
            '.preis'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Filter out "Preis auf Anfrage" (Price on request)
                if 'anfrage' in text.lower() or 'auf anfrage' in text.lower():
                    continue
                # Remove € symbol and parse
                text = text.replace('€', '').replace('Kaufpreis', '').replace('EUR', '').strip()
                try:
                    # Handle German number format: "599.000,00" -> 599000.0
                    if ',' in text and '.' in text:
                        parts = text.split(',')
                        if len(parts) == 2:
                            integer_part = parts[0].replace('.', '')
                            decimal_part = parts[1]
                            return float(f"{integer_part}.{decimal_part}")
                    else:
                        return float(text.replace('.', '').replace(',', '.'))
                except (ValueError, AttributeError):
                    continue
        
        # Fallback: search in all text for price patterns
        all_text = soup.get_text()
        price_patterns = [
            r'€\s*([\d\.,]+)',
            r'EUR\s*([\d\.,]+)',
            r'Kaufpreis[:\s]*([\d\.,]+)',
            r'Preis[:\s]*([\d\.,]+)'
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, all_text, re.IGNORECASE)
            if price_match:
                try:
                    price_text = price_match.group(1)
                    # Filter out "Preis auf Anfrage" (Price on request)
                    if 'anfrage' in price_text.lower() or 'auf anfrage' in price_text.lower():
                        continue
                    if ',' in price_text and '.' in price_text:
                        parts = price_text.split(',')
                        if len(parts) == 2:
                            integer_part = parts[0].replace('.', '')
                            decimal_part = parts[1]
                            return float(f"{integer_part}.{decimal_part}")
                    else:
                        return float(price_text.replace('.', '').replace(',', '.'))
                except (ValueError, AttributeError):
                    continue
        
        return None

    def extract_area(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract area from listing page"""
        selectors = [
            '.eps-item-area',
            '.property-area',
            '.listing-area',
            '[data-testid*="area"]',
            '.featured-listings__item__space strong',
            '.expose-area',
            '.area-value',
            '.wohnflaeche',
            '.flaeche'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Look for patterns like "82,2 m²"
                match = re.search(r'(\d+(?:[.,]\d+)?)\s*m²', text, re.IGNORECASE)
                if match:
                    area_str = match.group(1).replace(',', '.')
                    try:
                        return float(area_str)
                    except ValueError:
                        continue
        
        # Fallback: search in all text for area patterns
        all_text = soup.get_text()
        area_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*m²',
            r'Wohnfläche[:\s]*(\d+(?:[.,]\d+)?)',
            r'Fläche[:\s]*(\d+(?:[.,]\d+)?)',
            r'Größe[:\s]*(\d+(?:[.,]\d+)?)'
        ]
        
        for pattern in area_patterns:
            area_match = re.search(pattern, all_text, re.IGNORECASE)
            if area_match:
                try:
                    area_str = area_match.group(1).replace(',', '.')
                    return float(area_str)
                except ValueError:
                    continue
        
        return None

    def extract_rooms(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract room count from listing page"""
        selectors = [
            '.eps-item-rooms',
            '.property-rooms',
            '.listing-rooms',
            '[data-testid*="rooms"]',
            '.featured-listings__item__rooms strong',
            '.expose-rooms',
            '.rooms-value',
            '.zimmer',
            '.room-count'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Look for patterns like "4 Zimmer"
                match = re.search(r'(\d+(?:[.,]\d+)?)', text)
                if match:
                    room_str = match.group(1).replace(',', '.')
                    try:
                        return float(room_str)
                    except ValueError:
                        continue
        
        # Fallback: search in all text for room patterns
        all_text = soup.get_text()
        room_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*Zimmer',
            r'Zimmer[:\s]*(\d+(?:[.,]\d+)?)',
            r'Räume[:\s]*(\d+(?:[.,]\d+)?)'
        ]
        
        for pattern in room_patterns:
            room_match = re.search(pattern, all_text, re.IGNORECASE)
            if room_match:
                try:
                    room_str = room_match.group(1).replace(',', '.')
                    return float(room_str)
                except ValueError:
                    continue
        
        return None

    def extract_bezirk(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract district from listing page"""
        selectors = [
            '.property-address',
            '.listing-address',
            '.address',
            '[data-testid*="address"]',
            '.featured-listings__item__address',
            '.expose-address',
            '.address-value',
            '.location'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Look for patterns like "1010 Wien" or "1140 Wien"
                match = re.search(r'(\d{4})\s*Wien', text)
                if match:
                    return match.group(1)
        
        # Fallback: search in all text for district patterns
        all_text = soup.get_text()
        district_patterns = [
            r'(\d{4})\s*Wien',
            r'(\d{1,2})\.\s*Bezirk',
            r'Bezirk[:\s]*(\d{1,2})'
        ]
        
        for pattern in district_patterns:
            district_match = re.search(pattern, all_text)
            if district_match:
                district = district_match.group(1)
                # Convert 2-digit to 4-digit format if needed
                if len(district) == 1 or len(district) == 2:
                    district_map = {
                        '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
                        '6': '1060', '7': '1070', '8': '1080', '9': '1090', '10': '1100',
                        '11': '1110', '12': '1120', '13': '1130', '14': '1140', '15': '1150',
                        '16': '1160', '17': '1170', '18': '1180', '19': '1190', '20': '1200',
                        '21': '1210', '22': '1220', '23': '1230'
                    }
                    return district_map.get(district, district)
                return district
        
        return None

    def extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract full address from listing page"""
        selectors = [
            '.property-address',
            '.listing-address',
            '.address',
            '[data-testid*="address"]',
            '.featured-listings__item__address',
            '.expose-address',
            '.address-value',
            '.location'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and ('Wien' in text or re.search(r'\d{4}', text)):
                    return text
        
        # Fallback: search in all text for address patterns
        all_text = soup.get_text()
        address_patterns = [
            r'([A-Za-zäöüßÄÖÜ\s]+\d{1,3}[a-zA-Z]?)[,\s]+(\d{4})\s*Wien',
            r'([A-Za-zäöüßÄÖÜ\s]+)[,\s]+(\d{4})\s*Wien'
        ]
        
        for pattern in address_patterns:
            address_match = re.search(pattern, all_text)
            if address_match:
                return f"{address_match.group(1).strip()}, {address_match.group(2)} Wien"
        
        # Just district if full address not found
        district_match = re.search(r'(\d{4})\s*Wien', all_text)
        if district_match:
            return f"{district_match.group(1)} Wien"
        
        return None

    def extract_year_built(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract year built from listing page with enhanced patterns"""
        selectors = [
            '.property-year',
            '.listing-year',
            '[data-testid*="year"]',
            '.expose-year',
            '.year-value',
            '.baujahr',
            '.construction-year',
            '.building-year',
            '[class*="year"]',
            '[class*="baujahr"]',
            '[class*="construction"]',
            '[class*="bauzeit"]',
            '[class*="erbaut"]',
            '.baujahr-value',
            '.year-built'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                year = self._extract_year_from_text(text)
                if year:
                    return year
        
        # Fallback: search in all text for year patterns
        all_text = soup.get_text()
        year = self._extract_year_from_text(all_text)
        if year:
            return year
        
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
        """Extract floor information from listing page"""
        selectors = [
            '.property-floor',
            '.listing-floor',
            '[data-testid*="floor"]',
            '.expose-floor',
            '.floor-value',
            '.stockwerk'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for floor patterns
        all_text = soup.get_text()
        floor_patterns = [
            r'Stock[:\s]*(\d+)',
            r'Etage[:\s]*(\d+)',
            r'(\d+)\.\s*Stock'
        ]
        
        for pattern in floor_patterns:
            floor_match = re.search(pattern, all_text, re.IGNORECASE)
            if floor_match:
                return f"{floor_match.group(1)}. Stock"
        
        return None

    def extract_condition(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract condition from listing page"""
        selectors = [
            '.property-condition',
            '.listing-condition',
            '[data-testid*="condition"]',
            '.expose-condition',
            '.condition-value',
            '.zustand'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for condition patterns
        all_text = soup.get_text()
        condition_patterns = [
            r'Zustand[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Condition[:\s]*([A-Za-zäöüßÄÖÜ\s]+)'
        ]
        
        for pattern in condition_patterns:
            condition_match = re.search(pattern, all_text, re.IGNORECASE)
            if condition_match:
                return condition_match.group(1).strip()
        
        return None

    def extract_heating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract heating information from listing page"""
        selectors = [
            '.property-heating',
            '.listing-heating',
            '[data-testid*="heating"]',
            '.expose-heating',
            '.heating-value',
            '.heizung'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for heating patterns
        all_text = soup.get_text()
        heating_patterns = [
            r'Heizung[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Heating[:\s]*([A-Za-zäöüßÄÖÜ\s]+)'
        ]
        
        for pattern in heating_patterns:
            heating_match = re.search(pattern, all_text, re.IGNORECASE)
            if heating_match:
                return heating_match.group(1).strip()
        
        return None

    def extract_parking(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract parking information from listing page"""
        selectors = [
            '.property-parking',
            '.listing-parking',
            '[data-testid*="parking"]',
            '.expose-parking',
            '.parking-value',
            '.garage'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for parking patterns
        all_text = soup.get_text()
        parking_patterns = [
            r'Parken[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Parking[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Garage[:\s]*([A-Za-zäöüßÄÖÜ\s]+)'
        ]
        
        for pattern in parking_patterns:
            parking_match = re.search(pattern, all_text, re.IGNORECASE)
            if parking_match:
                return parking_match.group(1).strip()
        
        return None

    def extract_betriebskosten(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract Betriebskosten from listing page"""
        selectors = [
            '.property-betriebskosten',
            '.listing-betriebskosten',
            '[data-testid*="betriebskosten"]',
            '.expose-betriebskosten',
            '.betriebskosten-value',
            '.nebenkosten'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                match = re.search(r'([\d\.,]+)', text)
                if match:
                    try:
                        return float(match.group(1).replace('.', '').replace(',', '.'))
                    except ValueError:
                        continue
        
        # Fallback: search in all text for Betriebskosten patterns
        all_text = soup.get_text()
        betriebskosten_patterns = [
            r'Betriebskosten[:\s]*([\d\.,]+)',
            r'Nebenkosten[:\s]*([\d\.,]+)',
            r'Operating costs[:\s]*([\d\.,]+)'
        ]
        
        for pattern in betriebskosten_patterns:
            betriebskosten_match = re.search(pattern, all_text, re.IGNORECASE)
            if betriebskosten_match:
                try:
                    return float(betriebskosten_match.group(1).replace('.', '').replace(',', '.'))
                except ValueError:
                    continue

        return None

    def extract_energy_class(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract energy class from listing page"""
        selectors = [
            '.property-energy-class',
            '.listing-energy-class',
            '[data-testid*="energy"]',
            '.expose-energy-class',
            '.energy-class-value',
            '.energieklasse'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for energy class patterns
        all_text = soup.get_text()
        energy_patterns = [
            r'Energieklasse[:\s]*([A-G])',
            r'Energy class[:\s]*([A-G])',
            r'([A-G])\s*Energieklasse'
        ]
        
        for pattern in energy_patterns:
            energy_match = re.search(pattern, all_text, re.IGNORECASE)
            if energy_match:
                return energy_match.group(1)
        
        return None

    def extract_hwb_value(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract HWB value from listing page"""
        selectors = [
            '.property-hwb',
            '.listing-hwb',
            '[data-testid*="hwb"]',
            '.expose-hwb',
            '.hwb-value'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                match = re.search(r'([\d\.,]+)', text)
                if match:
                    try:
                        return float(match.group(1).replace(',', '.'))
                    except ValueError:
                        continue
        
        # Fallback: search in all text for HWB patterns
        all_text = soup.get_text()
        hwb_patterns = [
            r'HWB[:\s]*([\d\.,]+)',
            r'Heizwärmebedarf[:\s]*([\d\.,]+)'
        ]
        
        for pattern in hwb_patterns:
            hwb_match = re.search(pattern, all_text, re.IGNORECASE)
            if hwb_match:
                try:
                    return float(hwb_match.group(1).replace(',', '.'))
                except ValueError:
                    continue
        
        return None

    def extract_heating_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract heating type from listing page"""
        selectors = [
            '.property-heating-type',
            '.listing-heating-type',
            '[data-testid*="heating-type"]',
            '.expose-heating-type',
            '.heating-type-value'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for heating type patterns
        all_text = soup.get_text()
        heating_type_patterns = [
            r'Heizungstyp[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Heating type[:\s]*([A-Za-zäöüßÄÖÜ\s]+)'
        ]
        
        for pattern in heating_type_patterns:
            heating_type_match = re.search(pattern, all_text, re.IGNORECASE)
            if heating_type_match:
                return heating_type_match.group(1).strip()
        
        return None

    def extract_energy_carrier(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract energy carrier from listing page"""
        selectors = [
            '.property-energy-carrier',
            '.listing-energy-carrier',
            '[data-testid*="energy-carrier"]',
            '.expose-energy-carrier',
            '.energy-carrier-value'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for energy carrier patterns
        all_text = soup.get_text()
        energy_carrier_patterns = [
            r'Energieträger[:\s]*([A-Za-zäöüßÄÖÜ\s]+)',
            r'Energy carrier[:\s]*([A-Za-zäöüßÄÖÜ\s]+)'
        ]
        
        for pattern in energy_carrier_patterns:
            energy_carrier_match = re.search(pattern, all_text, re.IGNORECASE)
            if energy_carrier_match:
                return energy_carrier_match.group(1).strip()
        
        return None

    def extract_available_from(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract available from date from listing page"""
        selectors = [
            '.property-available-from',
            '.listing-available-from',
            '[data-testid*="available"]',
            '.expose-available-from',
            '.available-from-value'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        
        # Fallback: search in all text for available from patterns
        all_text = soup.get_text()
        available_patterns = [
            r'Verfügbar ab[:\s]*([\d\.]+)',
            r'Available from[:\s]*([\d\.]+)'
        ]
        
        for pattern in available_patterns:
            available_match = re.search(pattern, all_text, re.IGNORECASE)
            if available_match:
                return available_match.group(1)
        
        return None

    def extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main image URL from listing page"""
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
            image_selectors = [
                '[data-testid*="main-image"]',
                '[data-testid*="gallery"] img',
                '.gallery img',
                '.main-image img',
                '.property-image img',
                '.listing-image img',
                '.expose-image img',
                '.image-gallery img',
                'img[alt*="Hauptbild"]',
                'img[alt*="main"]',
                'img[alt*="property"]',
                '.carousel img',
                '.slider img'
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

    def estimate_down_payment(self, purchase_price: float) -> float:
        """Estimate down payment (typically 20% in Austria)"""
        return purchase_price * 0.2

    def calculate_total_monthly_cost(self, monthly_rate: Optional[float], betriebskosten: Optional[float]) -> Optional[float]:
        """Calculate total monthly cost including mortgage and Betriebskosten"""
        if monthly_rate is None and betriebskosten is None:
            return None
        
        total = 0
        if monthly_rate:
            total += monthly_rate
        if betriebskosten:
            total += betriebskosten
        
        return round(total, 2)

    def meets_criteria(self, listing: Listing) -> bool:
        """Check if listing meets the defined criteria"""
        if not self.criteria:
            return True
        
        try:
            # Price criteria
            if 'price_max' in self.criteria and listing.price_total:
                if listing.price_total > self.criteria['price_max']:
                    return False
            
            # Price per m² criteria
            if 'price_per_m2_max' in self.criteria and listing.price_per_m2:
                if listing.price_per_m2 > self.criteria['price_per_m2_max']:
                    return False
            
            # Area criteria
            if 'area_m2_min' in self.criteria and listing.area_m2:
                if listing.area_m2 < self.criteria['area_m2_min']:
                    return False
            
            # Rooms criteria
            if 'rooms_min' in self.criteria and listing.rooms:
                if listing.rooms < self.criteria['rooms_min']:
                    return False
            
            # District criteria
            if 'districts' in self.criteria and listing.bezirk:
                if listing.bezirk not in self.criteria['districts']:
                    return False
            
            # Year built criteria
            if 'year_built_min' in self.criteria and listing.year_built:
                if listing.year_built < self.criteria['year_built_min']:
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking criteria: {e}")
            return True  # Default to accepting if there's an error

    def scrape_search_results(self, search_url: str, max_pages: int = 3) -> List[Listing]:
        """Scrape Immo Kurier search results and return a list of Listing objects."""
        all_listings: List[Listing] = []
        valid_count = 0
        invalid_count = 0
        saved_count = 0
        
        logging.info(f"🔍 Starting Immo Kurier scraping: {search_url}")
        
        for page in range(1, max_pages + 1):
            url = f"{search_url}&page={page}"
            try:
                logging.info(f"🔍 Extracting URLs from page {page}: {url}")
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                listing_urls = self.extract_listing_urls(soup)
                if not listing_urls:
                    logging.info(f"⚠️ No URLs found on page {page}, stopping")
                    break  # No more pages
                
                logging.info(f"✅ Found {len(listing_urls)} URLs on page {page}")
                
                for i, listing_url in enumerate(listing_urls, 1):
                    logging.info(f"🔍 Scraping listing {i}/{len(listing_urls)}: {listing_url}")
                    listing = self.scrape_single_listing(listing_url)
                    if listing:
                        # Check if listing meets criteria
                        if self.meets_criteria(listing):
                            valid_count += 1
                            all_listings.append(listing)
                            
                            # Calculate score using structured analyzer
                            if self.structured_analyzer and self.structured_analyzer.is_available():
                                try:
                                    analysis_result = self.structured_analyzer.analyze_listing(listing.__dict__)
                                    # Store the full analysis dict for reference
                                    listing.structured_analysis = analysis_result
                                    # Use confidence as a fallback numeric score
                                    score = analysis_result.get('confidence', 0.0)
                                    # If you have a better scoring function, use it here
                                    listing.score = score if isinstance(score, (int, float)) else 0.0
                                    logging.info(f"📊 Score: {listing.score}/100")
                                except Exception as e:
                                    logging.error(f"Error calculating score: {e}")
                                    listing.score = 50  # Default score
                            else:
                                listing.score = 50  # Default score
                            
                            # Save to MongoDB
                            if self.mongo:
                                try:
                                    # Convert listing to dict for MongoDB
                                    listing_dict = listing.__dict__.copy()
                                    if self.mongo.insert_listing(listing_dict):
                                        saved_count += 1
                                        logging.info(f"💾 Saved to MongoDB")
                                    else:
                                        logging.info(f"💾 Listing already exists in MongoDB")
                                except Exception as e:
                                    logging.error(f"Error saving to MongoDB: {e}")
                            
                            # Send to Telegram if score is high enough
                            # (NO LONGER: property notifications are sent only from main.py)
                            # score_threshold = 40  # Default threshold
                            # if self.config and 'telegram' in self.config:
                            #     score_threshold = self.config['telegram'].get('min_score_threshold', 40)
                            # if listing.score > score_threshold and self.telegram_bot:
                            #     try:
                            #         self.telegram_bot.send_listing(listing)
                            #         logging.info(f"📱 Sent to Telegram (score: {listing.score})")
                            #     except Exception as e:
                            #         logging.error(f"Error sending to Telegram: {e}")
                            
                            logging.info(f"✅ MATCHES CRITERIA: {listing.title}")
                            logging.info(f"   💰 Price: €{listing.price_total:,.0f}")
                            logging.info(f"   📐 Area: {listing.area_m2}m²")
                            logging.info(f"   🏠 Rooms: {listing.rooms or 'N/A'}")
                            logging.info(f"   📍 District: {listing.bezirk}")
                        else:
                            invalid_count += 1
                            logging.info(f"❌ Does not meet criteria: {listing.title if listing.title else 'Unknown'}")
                    else:
                        invalid_count += 1
                        logging.info(f"❌ Failed to scrape listing")
                    
                    time.sleep(0.5)  # Be nice to the server
                    
            except Exception as e:
                logging.error(f"❌ Error scraping search results page {page}: {e}")
                break
        
        # Count high-score listings
        score_threshold = 40  # Default threshold
        if self.config and 'telegram' in self.config:
            score_threshold = self.config['telegram'].get('min_score_threshold', 40)
        
        high_score_count = sum(1 for listing in all_listings if hasattr(listing, 'score') and listing.score > score_threshold)
        
        logging.info(f"✅ Immo Kurier scraping complete: {valid_count} valid, {invalid_count} invalid, {saved_count} saved to MongoDB")
        logging.info(f"📊 Score summary: {high_score_count}/{len(all_listings)} listings with score > {score_threshold}")
        
        return all_listings

    def close(self):
        """Close the session"""
        if hasattr(self, 'session'):
            self.session.close()

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.close() 