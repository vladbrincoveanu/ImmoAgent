import time
import requests
import re
import json
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from geocoding import ViennaGeocoder
from telegram_bot import TelegramBot
from ollama_analyzer import OllamaAnalyzer
import os
from mongodb_handler import MongoDBHandler

class WillhabenScraper:
    def __init__(self, criteria_path: str = "immo-scouter/criteria.json", telegram_config: Optional[Dict] = None, mongo_uri: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.geocoder = ViennaGeocoder()
        self.criteria = self.load_criteria(criteria_path)
        
        # Initialize Telegram bot if config provided
        self.telegram_bot = None
        if telegram_config and telegram_config.get('enabled', False):
            bot_token = telegram_config.get('bot_token')
            chat_id = telegram_config.get('chat_id')
            if bot_token and chat_id:
                self.telegram_bot = TelegramBot(bot_token, chat_id)
                print(f"🤖 Telegram bot initialized for chat: {chat_id}")
            else:
                print("⚠️  Telegram config incomplete - bot disabled")

        self.mongo = MongoDBHandler(uri=mongo_uri)

    def load_criteria(self, path: str) -> dict:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        # Default fallback
        return {
            "ubahn_max_minutes": 25,
            "price_per_m2_min": 2000,
            "price_per_m2_max": 8000,
            "area_m2_min": 70,
            "year_built_min": 1955,
            "require_shopping_nearby": False,
            "require_education_nearby": False,
            "availability_keywords": ["vermietet", "nicht verfügbar", "reserviert", "verkauft"],
            "rooms_min": 3
        }

    def extract_bezirk(self, text: str) -> Optional[str]:
        """Extract Vienna district code (1010-1230)"""
        bezirk_patterns = [
            r'(\d{4})\s+Wien',
            r'Wien\s+(\d{4})',
            r'(\d{4})\s*,\s*Wien',
        ]
        
        for pattern in bezirk_patterns:
            match = re.search(pattern, text)
            if match:
                code = match.group(1)
                if code.startswith('1') and len(code) == 4:
                    return code
        return None

    def extract_price(self, text: str, soup: BeautifulSoup) -> Optional[int]:
        """Extract total purchase price"""
        price_selectors = [
            '.search-result-price',
            '.price-value',
            '[data-testid="price"]',
            '.listing-price',
            '.price',
            '.search-result-entry__price',
            '.result-list-entry__price',
            '[data-testid="search-result-price"]',
            '.price-display',
            '.listing-price-value'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text()
                # More comprehensive price patterns
                price_patterns = [
                    r'€\s*([\d\.]+)',
                    r'([\d\.]+)\s*€',
                    r'Kaufpreis.*?€\s*([\d\.]+)',
                    r'Preis.*?€\s*([\d\.]+)',
                    r'([\d\.]+)\s*EUR',
                    r'EUR\s*([\d\.]+)'
                ]
                
                for pattern in price_patterns:
                    price_match = re.search(pattern, price_text)
                    if price_match:
                        try:
                            return int(price_match.group(1).replace('.', ''))
                        except ValueError:
                            continue
        
        # Fallback to regex on full text
        price_patterns = [
            r'Kaufpreis.*?€\s*([\d\.]+)',
            r'Preis.*?€\s*([\d\.]+)',
            r'€\s*([\d\.]+)',
            r'([\d\.]+)\s*€',
            r'([\d\.]+)\s*EUR'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1).replace('.', ''))
                except ValueError:
                    continue
        
        return None

    def extract_area(self, text: str) -> Optional[float]:
        """Extract living area in square meters"""
        area_patterns = [
            r'Wohnfläche.*?([\d,]+)\s*m²',
            r'([\d,]+)\s*m²\s*Wohnfläche',
            r'Nutzfläche.*?([\d,]+)\s*m²',
            r'([\d,]+)\s*m²',
            r'Fläche.*?([\d,]+)\s*m²',
            r'([\d,]+)\s*m²\s*Fläche',
            r'Größe.*?([\d,]+)\s*m²',
            r'([\d,]+)\s*m²\s*Größe',
            r'([\d,]+)\s*Quadratmeter',
            r'([\d,]+)\s*qm',
            r'([\d,]+)\s*QM'
        ]
        
        for pattern in area_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                area_str = match.group(1).replace(',', '.')
                try:
                    area = float(area_str)
                    # Validate reasonable area (20-500 m²)
                    if 20 <= area <= 500:
                        return area
                except ValueError:
                    continue
        
        return None

    def extract_rooms(self, text: str) -> Optional[int]:
        """Extract number of rooms"""
        room_patterns = [
            r'(\d+)\s*Zimmer',
            r'(\d+)\s*Räume',
            r'(\d+)\s*rooms'
        ]
        
        for pattern in room_patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        return None

    def extract_year(self, text: str) -> Optional[int]:
        """Extract construction year"""
        year_patterns = [
            r'Baujahr\s*(\d{4})',
            r'Errichtung\s*(\d{4})',
            r'Baubeginn\s*(\d{4})',
            r'erbaut\s*(\d{4})'
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                year = int(match.group(1))
                if 1800 <= year <= 2025:
                    return year
        return None

    def extract_floor(self, text: str) -> Optional[str]:
        """Extract floor information"""
        floor_patterns = [
            r'(\d+)\.?\s*Stock',
            r'(\d+)\.?\s*floor',
            r'Etage\s*(\d+)'
        ]
        
        for pattern in floor_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def extract_condition(self, text: str) -> Optional[str]:
        """Extract property condition"""
        condition_keywords = ['neuwertig', 'renoviert', 'saniert', 'original', 'modern']
        text_lower = text.lower()
        
        for keyword in condition_keywords:
            if keyword in text_lower:
                return keyword
        return None

    def extract_heating(self, text: str) -> Optional[str]:
        """Extract heating type"""
        heating_patterns = [
            r'Fernwärme',
            r'Gasheizung',
            r'Ölheizung',
            r'Pellets',
            r'Elektroheizung'
        ]
        
        for pattern in heating_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern
        return None

    def extract_parking(self, text: str) -> Optional[str]:
        """Extract parking information"""
        parking_patterns = [
            r'Garage',
            r'Parkplatz',
            r'Stellplatz',
            r'Carport'
        ]
        
        for pattern in parking_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern
        return None

    def extract_address(self, text: str) -> Optional[str]:
        """Extract property address"""
        address_patterns = [
            r'Adresse[:\s]+([^,\n]+?)(?:\s+\d{4}\s+Wien|\s+Kontakt|\s+Referenz)',
            r'Standort[:\s]+([^,\n]+?)(?:\s+\d{4}\s+Wien|\s+Kontakt|\s+Referenz)',
            r'([A-Za-zäöüß\s]+,\s*\d{4}\s+Wien)',
            r'([A-Za-zäöüß\s]+\s+\d+/\d+\s+\d{4}\s+Wien)',
            r'([A-Za-zäöüß\s]+\s+\d+\s+\d{4}\s+Wien)'
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text)
            if match:
                address = match.group(1).strip()
                # Clean up the address
                address = re.sub(r'\s+', ' ', address)  # Remove extra spaces
                address = re.sub(r'^\s+|\s+$', '', address)  # Trim
                if len(address) > 5:  # Ensure it's a reasonable length
                    return address
        return None

    def extract_agent_info(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract agent/agency information"""
        agent_selectors = [
            '.agent-name',
            '.agency-name',
            '[data-testid="agent"]'
        ]
        
        for selector in agent_selectors:
            agent_elem = soup.select_one(selector)
            if agent_elem:
                return {
                    'name': agent_elem.get_text().strip(),
                    'phone': self.extract_phone(soup),
                    'email': self.extract_email(soup)
                }
        return None

    def extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract phone number"""
        phone_pattern = r'[\+]?[0-9\s\-\(\)]{10,}'
        text = soup.get_text()
        match = re.search(phone_pattern, text)
        return match.group(0) if match else None

    def extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract email address"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        text = soup.get_text()
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def extract_special_comments(self, text: str, soup: BeautifulSoup) -> Optional[str]:
        """Extract special conditions or comments"""
        special_keywords = [
            'vermietet', 'befristet', 'nicht beziehbar', 'sanierungsbedürftig',
            'renovierungsbedürftig', 'denkmalschutz', 'rented', 'occupied'
        ]
        
        description_selectors = [
            '.description', '.listing-description', 
            '.property-details', '.additional-info'
        ]
        
        for selector in description_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                desc_text = desc_elem.get_text().lower()
                for keyword in special_keywords:
                    if keyword in desc_text:
                        return desc_elem.get_text().strip()[:200]
        
        text_lower = text.lower()
        for keyword in special_keywords:
            if keyword in text_lower:
                sentences = text.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        return sentence.strip()[:200]
        
        return None

    def calculate_ubahn_proximity(self, address: str, bezirk: str) -> Optional[int]:
        """Calculate walking distance to nearest U-Bahn station using geocoding"""
        if not address or not bezirk:
            return None
        
        try:
            # Geocode the address
            coords = self.geocoder.geocode_address(address)
            if not coords:
                return None
            
            # Find nearest U-Bahn station
            distance_m, station_name = self.geocoder.find_nearest_ubahn(coords, bezirk)
            if distance_m is None:
                return None
            
            # Convert meters to walking minutes (assuming 80m/minute walking speed)
            walking_minutes = int(distance_m / 80)
            return walking_minutes
            
        except Exception as e:
            print(f"Error calculating U-Bahn proximity: {e}")
            return None

    def calculate_transport_score(self, address: str, bezirk: str) -> Optional[int]:
        """Calculate transport accessibility score (1-10)"""
        ubahn_minutes = self.calculate_ubahn_proximity(address, bezirk)
        if ubahn_minutes is None:
            return None
        
        if ubahn_minutes <= 5:
            return 10
        elif ubahn_minutes <= 10:
            return 8
        elif ubahn_minutes <= 15:
            return 6
        elif ubahn_minutes <= 20:
            return 4
        else:
            return 2

    def find_nearby_amenities(self, address: str) -> Dict:
        """Find nearby amenities using geocoding"""
        if not address:
            return {}
        
        try:
            # Geocode the address
            coords = self.geocoder.geocode_address(address)
            if not coords:
                return {}
            
            # Find nearby amenities
            amenities = self.geocoder.find_nearby_amenities(coords, radius_m=1000)
            
            # Get summary
            summary = self.geocoder.get_amenity_summary(amenities)
            
            return {
                'amenities': [{'name': a.name, 'distance_m': a.distance_m, 'type': a.type} for a in amenities],
                'summary': summary
            }
            
        except Exception as e:
            print(f"Error finding nearby amenities: {e}")
            return {}

    def extract_listing_urls(self, soup: BeautifulSoup) -> List[str]:
        """Extract only valid property detail URLs from search results"""
        urls = []
        link_selectors = [
            'a[href*="/iad/immobilien/d/eigentumswohnung/"]',
            'a[href*="/iad/immobilien/d/haus/"]',
        ]
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and ('/iad/immobilien/d/eigentumswohnung/' in href or '/iad/immobilien/d/haus/' in href):
                    if href.startswith('/'):
                        full_url = f"https://www.willhaben.at{href}"
                    else:
                        full_url = href
                    urls.append(full_url)
        # Remove duplicates while preserving order
        return list(dict.fromkeys(urls))

    def extract_monatsrate(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract Monatsrate (monthly loan payment) for 35 years if available"""
        try:
            # Find the mortgage calculator form
            calculator_form = soup.find('form', {'data-testid': 'mortgageCalculatorForm'})
            if not calculator_form:
                return None
            
            # Look for the monthly rate display within the form
            # Common patterns for monthly rate display
            monatsrate_selectors = [
                '[data-testid="monthlyRate"]',
                '.monthly-rate',
                '.monatsrate',
                '[data-testid="monthlyPayment"]',
                '.monthly-payment'
            ]
            
            for selector in monatsrate_selectors:
                rate_elem = calculator_form.select_one(selector)
                if rate_elem:
                    rate_text = rate_elem.get_text()
                    # Extract number from text like "€ 1,234" or "1.234 €"
                    rate_match = re.search(r'€\s*([\d\.,]+)', rate_text)
                    if rate_match:
                        rate_str = rate_match.group(1).replace('.', '').replace(',', '.')
                        return float(rate_str)
            
            # Fallback: search for any text containing "Monatsrate" or "monthly rate"
            form_text = calculator_form.get_text()
            monatsrate_patterns = [
                r'Monatsrate[:\s]*€\s*([\d\.,]+)',
                r'Monthly\s+Rate[:\s]*€\s*([\d\.,]+)',
                r'€\s*([\d\.,]+)\s*Monatsrate',
                r'€\s*([\d\.,]+)\s*monthly'
            ]
            
            for pattern in monatsrate_patterns:
                match = re.search(pattern, form_text, re.IGNORECASE)
                if match:
                    rate_str = match.group(1).replace('.', '').replace(',', '.')
                    return float(rate_str)
            
            return None
            
        except Exception as e:
            print(f"Error extracting Monatsrate: {e}")
            return None

    def scrape_single_listing(self, url: str) -> Optional[Dict]:
        """Scrape individual listing with comprehensive data extraction"""
        try:
            response = self.session.get(url)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            raw_text = soup.get_text(separator=' ', strip=True)
            
            # Extract all property details
            listing_data = {
                "url": url,
                "bezirk": self.extract_bezirk(raw_text),
                "price_total": self.extract_price(raw_text, soup),
                "area_m2": self.extract_area(raw_text),
                "rooms": self.extract_rooms(raw_text),
                "year_built": self.extract_year(raw_text),
                "floor": self.extract_floor(raw_text),
                "condition": self.extract_condition(raw_text),
                "heating": self.extract_heating(raw_text),
                "parking": self.extract_parking(raw_text),
                "special_comment": self.extract_special_comments(raw_text, soup),
                "address": self.extract_address(raw_text),
                "agent_info": self.extract_agent_info(soup),
                "monatsrate": self.extract_monatsrate(soup)  # New field
            }
            
            # Calculate derived values
            if listing_data["price_total"] and listing_data["area_m2"]:
                listing_data["price_per_m2"] = round(listing_data["price_total"] / listing_data["area_m2"], 2)
            
            # Add proximity calculations
            listing_data["ubahn_walk_minutes"] = self.calculate_ubahn_proximity(listing_data["address"], listing_data["bezirk"])
            listing_data["transport_score"] = self.calculate_transport_score(listing_data["address"], listing_data["bezirk"])
            
            # Add amenities information
            amenities_data = self.find_nearby_amenities(listing_data["address"])
            listing_data["amenities"] = amenities_data.get("amenities", [])
            listing_data["amenities_summary"] = amenities_data.get("summary", {})
            
            return listing_data
            
        except Exception as e:
            print(f"Error scraping listing {url}: {e}")
            return None

    def scrape_search_agent_page(self, alert_url: str, max_pages: int = 3) -> List[Dict]:
        try:
            all_listings = []
            all_urls = set()
            for page in range(1, max_pages + 1):
                if page == 1:
                    page_url = alert_url
                else:
                    separator = '&' if '?' in alert_url else '?'
                    page_url = f"{alert_url}{separator}page={page}"
                response = self.session.get(page_url)
                if response.status_code != 200:
                    break
                soup = BeautifulSoup(response.content, 'html.parser')
                page_urls = self.extract_listing_urls(soup)
                new_urls = [url for url in page_urls if url not in all_urls]
                if not new_urls:
                    break
                all_urls.update(new_urls)
                for url in new_urls:
                    # MongoDB deduplication
                    if self.mongo.listing_exists(url):
                        continue
                    listing_data = self.scrape_single_listing(url)
                    # Use Ollama to fill missing fields
                    if self.ollama_analyzer.is_available():
                        listing_data = self.ollama_analyzer.analyze_listing_content(listing_data, response.text)
                    # Only send/save if all required fields are present
                    required_fields = ["bezirk", "price_total", "area_m2", "rooms", "address"]
                    if all(listing_data.get(f) not in [None, "", "None"] for f in required_fields):
                        # Save to MongoDB
                        listing_data['sent_to_telegram'] = False
                        self.mongo.insert_listing(listing_data)
                        # Send to Telegram
                        if self.telegram_bot:
                            self.telegram_bot.send_property_notification(listing_data)
                            self.mongo.mark_sent(url)
                        all_listings.append(listing_data)
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
            return all_listings
        except Exception as e:
            print(f"Error scraping search agent page: {e}")
            return []

    def meets_criteria(self, listing_data: Dict) -> bool:
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

        # U-Bahn proximity (max X minutes walking with fallback)
        ubahn_minutes = listing_data.get("ubahn_walk_minutes")
        max_ubahn = c.get("ubahn_max_minutes", 15)
        if ubahn_minutes is None:
            # Fallback to district-based estimation
            district_ubahn_times = {
                '1010': 5, '1020': 8, '1030': 10, '1040': 7, '1050': 9,
                '1060': 6, '1070': 5, '1080': 8, '1090': 7, '1100': 12,
                '1120': 10, '1130': 15, '1140': 12, '1150': 8, '1160': 10,
                '1190': 15, '1210': 12, '1220': 18
            }
            fallback_minutes = district_ubahn_times.get(listing_data.get('bezirk'), 15)
            ubahn_ok = fallback_minutes <= max_ubahn
            print(f"  🚇 U-Bahn (fallback): {fallback_minutes} min walk (max {max_ubahn}) → {'✓' if ubahn_ok else '✗'}")
        else:
            ubahn_ok = ubahn_minutes <= max_ubahn
            print(f"  🚇 U-Bahn: {ubahn_minutes} min walk (max {max_ubahn}) → {'✓' if ubahn_ok else '✗'}")
        criteria_checks.append(("U-Bahn proximity", ubahn_ok))

        # Price per m² reasonable
        price_per_m2 = listing_data.get("price_per_m2")
        price_ok = price_per_m2 is not None and c["price_per_m2_min"] <= price_per_m2 <= c["price_per_m2_max"]
        criteria_checks.append(("Price per m²", price_ok))
        print(f"  💰 Price per m²: €{price_per_m2:,} (€{c['price_per_m2_min']}-€{c['price_per_m2_max']}) → {'✓' if price_ok else '✗'}")

        # Minimum area
        area_m2 = listing_data.get("area_m2")
        area_ok = area_m2 is not None and area_m2 >= c["area_m2_min"]
        criteria_checks.append(("Minimum area", area_ok))
        print(f"  📐 Area: {area_m2}m² (min {c['area_m2_min']}) → {'✓' if area_ok else '✗'}")

        # Minimum rooms
        rooms = listing_data.get("rooms")
        rooms_min = c.get("rooms_min")
        rooms_ok = rooms is not None and rooms_min is not None and rooms >= rooms_min
        criteria_checks.append((f"Minimum rooms ({rooms_min})", rooms_ok))
        print(f"  🛏️ Rooms: {rooms} (min {rooms_min}) → {'✓' if rooms_ok else '✗'}")

        # Not currently rented or unavailable
        special_comment = listing_data.get("special_comment", "")
        special_comment_lower = special_comment.lower() if special_comment else ""
        availability_ok = not any(keyword in special_comment_lower for keyword in c["availability_keywords"])
        criteria_checks.append(("Availability", availability_ok))
        print(f"  ✅ Availability: {special_comment[:100] if special_comment else 'No issues'} → {'✓' if availability_ok else '✗'}")

        # Construction year
        year_built = listing_data.get("year_built")
        year_ok = year_built is None or year_built >= c["year_built_min"]
        criteria_checks.append(("Construction year", year_ok))
        print(f"  🏗️  Year Built: {year_built} (min {c['year_built_min']}) → {'✓' if year_ok else '✗'}")

        # Amenities proximity
        amenities_summary = listing_data.get("amenities_summary", {})
        shopping_ok = not c["require_shopping_nearby"] or amenities_summary.get("shopping", {}).get("count", 0) > 0
        education_ok = not c["require_education_nearby"] or amenities_summary.get("education", {}).get("count", 0) > 0
        criteria_checks.append(("Shopping nearby", shopping_ok))
        criteria_checks.append(("Education nearby", education_ok))
        print(f"  🛒 Shopping: {amenities_summary.get('shopping', {}).get('count', 0)} facilities → {'✓' if shopping_ok else '✗'}")
        print(f"  🎓 Education: {amenities_summary.get('education', {}).get('count', 0)} facilities → {'✓' if education_ok else '✗'}")

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
        
        # Send Telegram notification if criteria met and bot is available
        if final_result and self.telegram_bot:
            try:
                print("📱 Sending Telegram notification...")
                success = self.telegram_bot.send_property_notification(listing_data)
                if success:
                    print("✅ Telegram notification sent successfully!")
                else:
                    print("❌ Failed to send Telegram notification")
            except Exception as e:
                print(f"⚠️  Error sending Telegram notification: {e}")
        
        return final_result