import sys
import os
# Ensure Project directory is in sys.path for sibling imports
project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
from urllib.parse import urljoin

from Domain.listing import Listing
from Domain.sources import Source
from Integration.telegram_bot import TelegramBot
from Integration.mongodb_handler import MongoDBHandler
from Application.analyzer import StructuredAnalyzer
from Application.helpers.geocoding import ViennaGeocoder
from Application.helpers.utils import calculate_ubahn_proximity, format_currency, get_walking_times, estimate_betriebskosten

class DerStandardScraper:
    # URLs will be loaded from config.json
    
    def __init__(self, config=None, use_selenium=True):  # Enable Selenium by default for derStandard
        # Load config from main Project directory if not provided
        if config is None:
            from Application.helpers.utils import load_config
            self.config = load_config()
        else:
            self.config = config
        self.use_selenium = use_selenium
        self.session = requests.Session()
        
        # Get configuration values
        scraping_config = self.config.get('scraping', {})
        derstandard_config = self.config.get('derstandard', {})
        
        self.base_url = derstandard_config.get('base_url', 'https://immobilien.derstandard.at')
        self.search_url = derstandard_config.get('search_url', 'https://immobilien.derstandard.at/suche/wien/kaufen-wohnung?roomCountFrom=3')
        self.max_pages = derstandard_config.get('max_pages', 5)
        self.timeout = derstandard_config.get('timeout', 30)
        self.selenium_wait_time = derstandard_config.get('selenium_wait_time', 10)
        
        self.session.headers.update({
            'User-Agent': scraping_config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        })
        
        self.driver = None
        
        # Initialize components
        self.geocoder = ViennaGeocoder()
        
        # Initialize Structured analyzer with config
        self.structured_analyzer = StructuredAnalyzer(
            api_key=self.config.get('openai_api_key'),
            model=self.config.get('openai_model', 'gpt-4o-mini')
        )
        
        # Load criteria from the main config
        self.criteria = self.config.get('criteria', {})
        if self.criteria:
            print(f"📋 Loaded criteria from config: {len(self.criteria)} rules")
            print(f"   Price max: €{self.criteria.get('price_max', 'N/A'):,}")
            print(f"   Price per m² max: €{self.criteria.get('price_per_m2_max', 'N/A'):,}")
            print(f"   Area min: {self.criteria.get('area_m2_min', 'N/A')}m²")
            print(f"   Rooms min: {self.criteria.get('rooms_min', 'N/A')}")
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
        
        # Set source information
        self.source = "derstandard"
        self.source_enum = "derstandard"
        
        # Initialize MongoDB handler
        mongo_uri = self.config.get('mongodb_uri') or "mongodb://localhost:27017/"
        self.mongo = MongoDBHandler(uri=mongo_uri)
        
        if self.use_selenium:
            self._setup_selenium()
            # If Selenium setup fails, fall back to requests
            if not self.driver:
                self.use_selenium = False
                logging.warning("⚠️ Selenium setup failed, falling back to requests")
    
    def load_config(self):
        """Load configuration from config.json"""
        try:
            # Try to load from the main Project directory first
            import json
            import os
            main_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
            if os.path.exists(main_config_path):
                with open(main_config_path, 'r') as f:
                    config = json.load(f)
                    logging.info(f"✅ Loaded config from {main_config_path}")
                    return config
            
            # Fallback to local config
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logging.info(f"✅ Loaded config from {config_path}")
                    return config
            
            logging.warning(f"Could not find config.json in {main_config_path} or {config_path}")
            return {}
        except Exception as e:
            logging.warning(f"Could not load config.json: {e}")
            return {}
    
    def _setup_selenium(self):
        """Setup Selenium WebDriver for dynamic content"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("✅ Selenium WebDriver initialized")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Selenium: {e}")
            self.use_selenium = False
    
    def __del__(self):
        """Cleanup Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def extract_listing_urls_from_page(self, html_content: str) -> List[str]:
        """Extract listing URLs from HTML content using various selectors"""
        soup = BeautifulSoup(html_content, 'html.parser')
        urls = []

        # Find all <a> tags with hrefs that match the listing pattern
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Listings have URLs like /detail/123456 or /immobiliensuche/neubau/detail/123456
            if href and ('/detail/' in href or '/immobiliendetail/' in href or '/projektdetail/' in href):
                # Handle both relative and absolute URLs
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                if full_url not in urls:
                    urls.append(full_url)
        
        # Also look for listing cards that might have different URL patterns
        listing_cards = soup.find_all('a', class_='sc-listing-card-gallery-link')
        for card in listing_cards:
            href = card.get('href')
            if href and '/detail/' in href:
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                if full_url not in urls:
                    urls.append(full_url)
        
        return urls

    def is_collection_listing(self, soup: BeautifulSoup) -> bool:
        """Check if this is a collection/project listing that contains multiple properties"""
        try:
            # Only look for very specific, undeniable collection indicators
            collection_indicators = [
                # Only the most specific collection selectors that definitely indicate multiple properties
                '.sc-project-overview',
                '.sc-multiple-properties'
            ]
            
            for indicator in collection_indicators:
                if soup.select_one(indicator):
                    return True
            
            # Check for multiple property links with different IDs (extremely conservative)
            property_links = soup.find_all('a', href=lambda href: href and '/detail/' in href)
            if len(property_links) >= 8:  # Require at least 8 links to be considered a collection
                # Extract IDs from URLs to see if they're actually different properties
                ids = set()
                for link in property_links:
                    href = link.get('href', '')
                    if '/detail/' in href:
                        # Extract ID from URL like /detail/123456
                        parts = href.split('/detail/')
                        if len(parts) > 1:
                            id_part = parts[1].split('/')[0]
                            if id_part.isdigit():
                                ids.add(id_part)
                
                # If we have at least 8 different IDs, it's likely a collection
                if len(ids) >= 8:
                    return True
            
            # Check for very specific text indicators only
            text_indicators = ['mehrere Objekte verfügbar', 'Projekt mit mehreren Wohnungen', 'Neubauprojekt']
            page_text = soup.get_text().lower()
            for text_indicator in text_indicators:
                if text_indicator.lower() in page_text:
                    return True
            
            return False
            
        except Exception as e:
            logging.debug(f"Error checking if collection listing: {e}")
            return False

    def extract_individual_property_urls_from_collection(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract URLs of individual properties from a collection/project listing"""
        urls = []
        
        try:
            # Look for individual property links within the collection
            property_selectors = [
                'a[href*="/detail/"]',
                '.sc-property-link a',
                '.property-item a',
                '.listing-item a',
                '[class*="property"] a[href*="/detail/"]',
                '[class*="listing"] a[href*="/detail/"]',
                '.sc-listing-card a[href*="/detail/"]',
                '.listing-card a[href*="/detail/"]',
                '.property-card a[href*="/detail/"]'
            ]
            
            for selector in property_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        if href.startswith('/'):
                            full_url = urljoin(base_url, href)
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        if full_url not in urls and '/detail/' in full_url:
                            urls.append(full_url)
            
            # Also look for any links that contain property IDs
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link['href']
                if '/detail/' in href and href not in urls:
                    if href.startswith('/'):
                        full_url = urljoin(base_url, href)
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        continue
                    
                    urls.append(full_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            return unique_urls
            
        except Exception as e:
            logging.error(f"Error extracting individual property URLs: {e}")
            return []

    def navigate_collection_listing(self, collection_url: str, visited_urls: set = None) -> List[str]:
        """Navigate through a collection listing to find individual property URLs"""
        if visited_urls is None:
            visited_urls = set()
        
        # Check for cycles
        if collection_url in visited_urls:
            logging.debug(f"🔄 Cycle detected, skipping: {collection_url}")
            return []
        
        visited_urls.add(collection_url)
        
        try:
            logging.info(f"🔍 Navigating collection listing: {collection_url}")
            
            # Get the collection page
            if self.use_selenium:
                html_content = self.get_page_with_selenium(collection_url)
            else:
                response = self.session.get(collection_url)
                response.raise_for_status()
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract individual property URLs
            individual_urls = self.extract_individual_property_urls_from_collection(soup, collection_url)
            
            # Filter out URLs we've already visited to prevent cycles
            new_urls = [url for url in individual_urls if url not in visited_urls]
            
            logging.info(f"✅ Found {len(individual_urls)} individual properties, {len(new_urls)} new")
            return new_urls
            
        except Exception as e:
            logging.error(f"❌ Error navigating collection listing: {e}")
            return []

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
            
            # Try to find image in gallery or main content
            image_selectors = [
                '.sc-listing-card-gallery img',
                '.gallery img',
                '.main-image img',
                '.property-image img',
                '.listing-image img',
                '[data-testid*="main-image"]',
                '[data-testid*="gallery"] img',
                'img[alt*="Hauptbild"]',
                'img[alt*="main"]',
                'img[alt*="property"]'
            ]
            
            for selector in image_selectors:
                img_tag = soup.select_one(selector)
                if img_tag and img_tag.get('src'):
                    src = img_tag['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = self.base_url + src
                    return src
            
            # Fallback: first image with reasonable size that looks like a property image
            for img_tag in soup.find_all('img'):
                src = img_tag.get('src', '')
                alt = img_tag.get('alt', '').lower()
                
                # Skip small images, icons, and non-property images
                if (src.startswith('http') and 
                    any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) and
                    not any(skip in alt for skip in ['icon', 'logo', 'avatar', 'profile']) and
                    not any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'profile', 'placeholder'])):
                    
                    # Check if image size suggests it's a main image (not too small)
                    width = img_tag.get('width')
                    height = img_tag.get('height')
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
            
            # Last resort: look for any image with derStandard domain patterns
            for img_tag in soup.find_all('img'):
                src = img_tag.get('src')
                if src and ('immoupload' in src or 'immoimporte' in src or 'derstandard' in src):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = self.base_url + src
                    return src
            
            return None
        except Exception as e:
            logging.warning(f"Error extracting image URL: {e}")
            return None
    
    def get_page_with_selenium(self, url: str, wait_time: int = 10) -> str:
        """Get page content using Selenium for dynamic content"""
        if not self.driver:
            raise Exception("Selenium driver not initialized")
        try:
            self.driver.get(url)
            # Wait for content to load
            from selenium.common.exceptions import WebDriverException
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Additional wait for dynamic content
            import time
            time.sleep(3)
            return self.driver.page_source
        except Exception as e:
            # If Selenium session is invalid, disable and fallback
            if 'invalid session id' in str(e).lower() or 'session not created' in str(e).lower():
                import logging
                logging.warning(f"⚠️ Selenium session error: {e}. Disabling Selenium and falling back to requests.")
                self.use_selenium = False
                self.driver = None
                raise RuntimeError("Selenium session invalid, fallback to requests")
            else:
                raise

    def extract_listing_urls(self, search_url: str, max_pages: int = 5) -> List[str]:
        """Extract listing URLs from search results"""
        all_urls = []
        
        for page in range(1, max_pages + 1):
            page_url = search_url
            if page > 1:
                if '?' in search_url:
                    page_url += f"&page={page}"
                else:
                    page_url += f"?page={page}"
            
            logging.info(f"🔍 Extracting URLs from page {page}: {page_url}")
            
            try:
                if self.use_selenium:
                    html_content = self.get_page_with_selenium(page_url)
                else:
                    response = self.session.get(page_url)
                    response.raise_for_status()
                    html_content = response.text
                
                page_urls = self.extract_listing_urls_from_page(html_content)
                logging.info(f"✅ Found {len(page_urls)} URLs on page {page}")
                
                all_urls.extend(page_urls)
                
                # If no URLs found, might be the last page
                if not page_urls:
                    logging.info(f"📭 No URLs found on page {page}, stopping")
                    break
                    
            except Exception as e:
                logging.error(f"❌ Error extracting URLs from page {page}: {e}")
                break
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(all_urls))
        logging.info(f"🎯 Total unique URLs found: {len(unique_urls)}")
        
        return unique_urls
    
    def scrape_single_listing(self, listing_url: str, visited_urls: set = None, recursion_depth: int = 0) -> Optional[Listing]:
        """Scrape individual listing data and return a Listing object."""
        import logging
        
        # Initialize visited_urls if not provided
        if visited_urls is None:
            visited_urls = set()
        
        # Check for maximum recursion depth to prevent infinite loops
        max_recursion_depth = 3
        if recursion_depth >= max_recursion_depth:
            logging.warning(f"⚠️ Maximum recursion depth ({max_recursion_depth}) reached, stopping: {listing_url}")
            return None
        
        # Check for cycles
        if listing_url in visited_urls:
            logging.debug(f"🔄 Cycle detected, skipping: {listing_url}")
            return None
        
        visited_urls.add(listing_url)
        logging.info(f"🔍 Scraping listing (depth {recursion_depth}): {listing_url}")
        
        try:
            html_content = None
            if self.use_selenium:
                try:
                    html_content = self.get_page_with_selenium(listing_url)
                except RuntimeError:
                    # Selenium failed, fallback to requests
                    self.use_selenium = False
                    html_content = None
                except Exception as e:
                    logging.error(f"❌ Error getting page with Selenium: {e}")
                    self.use_selenium = False
                    html_content = None
            if html_content is None:
                response = self.session.get(listing_url)
                response.raise_for_status()
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Handle collection listings by extracting individual properties
            actual_url = listing_url  # Track the actual URL we're scraping
            if self.is_collection_listing(soup):
                logging.info(f"📦 Detected collection listing, extracting individual properties: {listing_url}")
                individual_urls = self.navigate_collection_listing(listing_url, visited_urls)
                
                if individual_urls:
                    # Use the first individual property URL for the listing
                    actual_url = individual_urls[0]
                    logging.info(f"🔄 Using individual property URL: {actual_url}")
                    # Re-scrape with the individual property URL
                    return self.scrape_single_listing(actual_url, visited_urls, recursion_depth + 1)
                else:
                    logging.info(f"📦 No individual properties found in collection, trying as regular listing: {listing_url}")
                    # Continue with regular scraping instead of returning None
            
            # Create a Listing object with all required fields
            listing = Listing(
                url=actual_url,  # Use actual_url to ensure we store the correct URL
                source="derstandard",
                source_enum="derstandard",
                title="",  # Will be populated
                bezirk="",  # Will be populated
                address="",  # Will be populated
                price_total=None,  # Will be populated
                area_m2=None,  # Will be populated
                rooms=None,  # Will be populated
                year_built=None,  # Will be populated
                floor=None,  # Will be populated
                condition=None,  # Will be populated
                heating=None,  # Will be populated
                parking=None,  # Will be populated
                betriebskosten=None,  # Will be populated
                energy_class=None,  # Will be populated
                hwb_value=None,  # Will be populated
                fgee_value=None,  # Will be populated
                heating_type=None,  # Will be populated
                energy_carrier=None,  # Will be populated
                available_from=None,  # Will be populated
                special_features=[],  # Will be populated
                monatsrate=None,  # Will be populated
                own_funds=None,  # Will be populated
                price_per_m2=None,  # Will be calculated
                ubahn_walk_minutes=None,  # Will be populated
                school_walk_minutes=None,  # Will be populated
                calculated_monatsrate=None,  # Will be calculated
                mortgage_details={},  # Will be populated
                total_monthly_cost=None,  # Will be calculated
                infrastructure_distances={},  # Will be populated
                image_url=None,  # Will be populated
                structured_analysis={},  # Will be populated
                sent_to_telegram=False,  # Default
                processed_at=time.time(),
                local_image_path=None,  # Will be populated
                coordinates=None,  # Will be populated
                score=0  # Will be calculated
            )

            # NEW APPROACH: Extract data from embedded JSON in script tags
            property_data = self.extract_property_data_from_json(soup)
            if property_data:
                # Populate listing with extracted data
                listing.title = property_data.get('title', '')
                listing.price_total = property_data.get('price_total')
                listing.area_m2 = property_data.get('area_m2')
                listing.rooms = property_data.get('rooms')
                listing.address = property_data.get('address', '')
                listing.bezirk = property_data.get('bezirk', '')
                listing.year_built = property_data.get('year_built')
                listing.condition = property_data.get('condition', '')
                listing.energy_class = property_data.get('energy_class', '')
                listing.hwb_value = property_data.get('hwb_value')
                listing.heating_type = property_data.get('heating_type', '')
                listing.energy_carrier = property_data.get('energy_carrier', '')
                listing.available_from = property_data.get('available_from', '')
                listing.image_url = property_data.get('image_url', '')
                listing.floor = property_data.get('floor', '')
                listing.heating = property_data.get('heating', '')
                listing.parking = property_data.get('parking', '')
                listing.fgee_value = property_data.get('fgee_value')
                listing.special_features = property_data.get('special_features', [])
                listing.monatsrate = property_data.get('monatsrate')
                listing.own_funds = property_data.get('own_funds')
                
                # Extract image URL if not already set
                if not listing.image_url:
                    listing.image_url = self.extract_image_url(soup)
                
                # Calculate price per m²
                if listing.price_total is not None and listing.area_m2 is not None:
                    listing.price_per_m2 = listing.price_total / listing.area_m2
                
                # Add walking times based on district
                if listing.bezirk:
                    ubahn_minutes, school_minutes = self.get_walking_times(listing.bezirk)
                    listing.ubahn_walk_minutes = ubahn_minutes
                    listing.school_walk_minutes = school_minutes
                
                # Handle Betriebskosten - estimate based on area
                if listing.area_m2:
                    betriebskosten_breakdown = estimate_betriebskosten(listing.area_m2)
                    listing.betriebskosten = betriebskosten_breakdown['total_incl_vat']
                    listing.betriebskosten_breakdown = betriebskosten_breakdown
                    listing.betriebskosten_estimated = True
                
                # Calculate mortgage details if price is available
                if listing.price_total:
                    listing.calculated_monatsrate = self.calculate_monthly_rate(listing.price_total)
                    listing.mortgage_details = self.get_mortgage_breakdown(listing.price_total)
                    # Add Betriebskosten to total monthly cost
                    total_monthly = listing.calculated_monatsrate
                    if listing.betriebskosten:
                        total_monthly += listing.betriebskosten
                    listing.total_monthly_cost = total_monthly
                
                # Validate that we have essential data
                if self.validate_listing_data(listing):
                    logging.info(f"✅ Successfully scraped listing: {listing.title}")
                    return listing
                else:
                    logging.warning(f"⚠️ Listing data incomplete: {listing_url}")
                    return None
            else:
                # FALLBACK: Try the old approach with HTML selectors
                logging.info("🔄 Trying fallback HTML extraction...")
                return self.extract_from_html_selectors(soup, listing)
                
        except Exception as e:
            logging.error(f"❌ Error scraping listing {listing_url}: {e}")
            return None

    def extract_property_data_from_json(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract property data from embedded JSON in script tags"""
        try:
            # Look for script tags containing property data
            script_tags = soup.find_all('script')
            
            for script in script_tags:
                script_content = script.get_text()
                
                # Look for property data in various formats
                if 'propertyData' in script_content or 'PropertyEntryResponse' in script_content:
                    # Try to extract JSON data
                    import re
                    import json
                    
                    # Look for JSON-like structures
                    json_patterns = [
                        r'propertyData":\s*({[^}]+})',
                        r'"property":\s*({[^}]+})',
                        r'PropertyEntryResponse[^}]*"property":\s*({[^}]+})',
                    ]
                    
                    for pattern in json_patterns:
                        matches = re.findall(pattern, script_content, re.DOTALL)
                        for match in matches:
                            try:
                                # Clean up the JSON string
                                json_str = match.strip()
                                if json_str.endswith(','):
                                    json_str = json_str[:-1]
                                
                                # Try to parse as JSON
                                data = json.loads(json_str)
                                
                                # Extract relevant fields
                                property_info = {}
                                
                                # Title
                                if 'title' in data:
                                    property_info['title'] = data['title']
                                
                                # Price
                                if 'costs' in data and 'main' in data['costs']:
                                    cost_data = data['costs']['main']
                                    if 'value' in cost_data:
                                        property_info['price_total'] = cost_data['value']
                                
                                # Area and rooms
                                if 'areas' in data and 'details' in data['areas']:
                                    for area_detail in data['areas']['details']:
                                        if area_detail.get('kind') == 'LIVING_SPACE':
                                            property_info['area_m2'] = area_detail.get('value')
                                        elif area_detail.get('kind') == 'ROOM_COUNT':
                                            property_info['rooms'] = area_detail.get('value')
                                
                                # Location
                                if 'location' in data:
                                    location = data['location']
                                    if 'street' in location and 'zipCode' in location and 'city' in location:
                                        property_info['address'] = f"{location['street']}, {location['zipCode']} {location['city']}"
                                        property_info['bezirk'] = location.get('zipCode', '')
                                
                                # Year built
                                if 'condition' in data and 'yearOfConstruction' in data['condition']:
                                    property_info['year_built'] = data['condition']['yearOfConstruction']
                                
                                # Energy data
                                if 'energyConsumption' in data:
                                    energy = data['energyConsumption']
                                    if 'hwb' in energy and 'class' in energy['hwb']:
                                        property_info['energy_class'] = energy['hwb']['class']
                                    if 'hwb' in energy and 'value' in energy['hwb']:
                                        property_info['hwb_value'] = energy['hwb']['value']
                                    if 'fgee' in energy and 'value' in energy['fgee']:
                                        property_info['fgee_value'] = energy['fgee']['value']
                                
                                # Heating and energy carrier
                                if 'heating' in data:
                                    heating = data['heating']
                                    if 'type' in heating:
                                        property_info['heating_type'] = heating['type']
                                    if 'carrier' in heating:
                                        property_info['energy_carrier'] = heating['carrier']
                                
                                # Condition and floor
                                if 'condition' in data:
                                    condition = data['condition']
                                    if 'state' in condition:
                                        property_info['condition'] = condition['state']
                                    if 'floor' in condition:
                                        property_info['floor'] = condition['floor']
                                
                                # Parking
                                if 'parking' in data:
                                    property_info['parking'] = data['parking']
                                
                                # Available from
                                if 'availability' in data and 'from' in data['availability']:
                                    property_info['available_from'] = data['availability']['from']
                                
                                # Special features
                                if 'features' in data and isinstance(data['features'], list):
                                    property_info['special_features'] = data['features']
                                
                                # Images
                                if 'media' in data and 'images' in data['media'] and data['media']['images']:
                                    property_info['image_url'] = data['media']['images'][0].get('path', '')
                                
                                # Try to extract more data from other JSON patterns
                                if 'propertyDetails' in data:
                                    details = data['propertyDetails']
                                    if 'title' in details and not property_info.get('title'):
                                        property_info['title'] = details['title']
                                    if 'price' in details and not property_info.get('price_total'):
                                        property_info['price_total'] = details['price']
                                    if 'area' in details and not property_info.get('area_m2'):
                                        property_info['area_m2'] = details['area']
                                    if 'rooms' in details and not property_info.get('rooms'):
                                        property_info['rooms'] = details['rooms']
                                
                                if property_info:
                                    logging.info(f"✅ Extracted data from JSON: {property_info.get('title', 'Unknown')}")
                                    return property_info
                                    
                            except (json.JSONDecodeError, KeyError) as e:
                                logging.debug(f"Failed to parse JSON pattern: {e}")
                                continue
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting property data from JSON: {e}")
            return None

    def extract_from_html_selectors(self, soup: BeautifulSoup, listing: Listing) -> Optional[Listing]:
        """Extract data using HTML selectors for the new derStandard structure"""
        try:
            logging.info("🔄 Trying HTML selector extraction...")
            
            # Try new derStandard selectors based on page analysis
            # Look for title in h1 or similar elements
            title_selectors = [
                'h1',
                '.sc-detail-title',
                '[class*="title"]',
                '[class*="heading"]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem and title_elem.get_text().strip():
                    listing.title = title_elem.get_text().strip()
                    break
            
            # Look for price information - try multiple approaches
            price_found = False
            
            # Method 1: Look for price elements
            price_selectors = [
                '[class*="price"]',
                '[class*="kaufpreis"]',
                '[class*="preis"]',
                '.sc-price',
                '.price-value'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    # Extract numeric value from price text
                    import re
                    price_match = re.search(r'[\d.,]+', price_text.replace('.', '').replace(',', '.'))
                    if price_match:
                        try:
                            listing.price_total = float(price_match.group().replace(',', '.'))
                            price_found = True
                            break
                        except ValueError:
                            continue
            
            # Method 2: Look for € symbols in text
            if not price_found:
                price_elements = soup.find_all(string=lambda text: text and '€' in text and any(c.isdigit() for c in text))
                for price_text in price_elements:
                    import re
                    # Look for patterns like €1,099,000 or € 1.099.000
                    price_match = re.search(r'€\s*([\d.,]+)', price_text.strip())
                    if price_match:
                        try:
                            price_str = price_match.group(1).replace('.', '').replace(',', '.')
                            listing.price_total = float(price_str)
                            price_found = True
                            break
                        except ValueError:
                            continue
            
            # Look for area information - try multiple approaches
            area_found = False
            
            # Method 1: Look for area elements
            area_selectors = [
                '[class*="area"]',
                '[class*="fläche"]',
                '[class*="m2"]',
                '[class*="qm"]'
            ]
            
            for selector in area_selectors:
                area_elem = soup.select_one(selector)
                if area_elem:
                    area_text = area_elem.get_text().strip()
                    # Extract numeric value from area text
                    import re
                    area_match = re.search(r'[\d.,]+', area_text.replace('.', '').replace(',', '.'))
                    if area_match:
                        try:
                            listing.area_m2 = float(area_match.group().replace(',', '.'))
                            area_found = True
                            break
                        except ValueError:
                            continue
            
            # Method 2: Look for m² in text
            if not area_found:
                area_elements = soup.find_all(string=lambda text: text and ('m²' in text or 'qm' in text) and any(c.isdigit() for c in text))
                for area_text in area_elements:
                    import re
                    # Look for patterns like 78.93 m²
                    area_match = re.search(r'([\d.,]+)\s*m²', area_text.strip())
                    if area_match:
                        try:
                            area_str = area_match.group(1).replace(',', '.')
                            listing.area_m2 = float(area_str)
                            area_found = True
                            break
                        except ValueError:
                            continue
            
            # Look for rooms information
            rooms_selectors = [
                '[class*="room"]',
                '[class*="zimmer"]',
                '[class*="rooms"]'
            ]
            
            for selector in rooms_selectors:
                rooms_elem = soup.select_one(selector)
                if rooms_elem:
                    rooms_text = rooms_elem.get_text().strip()
                    # Extract numeric value from rooms text
                    import re
                    rooms_match = re.search(r'\d+', rooms_text)
                    if rooms_match:
                        try:
                            listing.rooms = float(rooms_match.group())
                            break
                        except ValueError:
                            continue
            
            # Look for address information
            address_selectors = [
                '[class*="address"]',
                '[class*="adresse"]',
                '[class*="location"]',
                '[class*="ort"]'
            ]
            
            for selector in address_selectors:
                address_elem = soup.select_one(selector)
                if address_elem and address_elem.get_text().strip():
                    listing.address = address_elem.get_text().strip()
                    # Try to extract bezirk from address
                    if 'Wien' in listing.address:
                        import re
                        bezirk_match = re.search(r'(\d{4})\s*Wien', listing.address)
                        if bezirk_match:
                            listing.bezirk = bezirk_match.group(1)
                            break
            
            # Look for year built information with enhanced selectors
            year_selectors = [
                '[class*="year"]',
                '[class*="baujahr"]',
                '[class*="construction"]',
                '[class*="bauzeit"]',
                '[class*="erbaut"]',
                '[data-testid*="year"]',
                '[data-testid*="baujahr"]',
                '.property-year',
                '.listing-year',
                '.expose-year',
                '.year-value',
                '.baujahr-value',
                '.construction-year',
                '.building-year'
            ]
            
            for selector in year_selectors:
                year_elem = soup.select_one(selector)
                if year_elem:
                    year_text = year_elem.get_text().strip()
                    year = self.extract_year(year_text)
                    if year:
                        listing.year_built = year
                        break
            
            # Fallback: search in all text for year patterns if not found
            if not listing.year_built:
                all_text = soup.get_text()
                year = self.extract_year(all_text)
                if year:
                    listing.year_built = year
            
            # Look for condition information
            condition_selectors = [
                '[class*="condition"]',
                '[class*="zustand"]',
                '[class*="state"]'
            ]
            
            for selector in condition_selectors:
                condition_elem = soup.select_one(selector)
                if condition_elem and condition_elem.get_text().strip():
                    listing.condition = condition_elem.get_text().strip()
                    break
            
            # Look for heating information
            heating_selectors = [
                '[class*="heating"]',
                '[class*="heizung"]',
                '[class*="heizungsart"]'
            ]
            
            for selector in heating_selectors:
                heating_elem = soup.select_one(selector)
                if heating_elem and heating_elem.get_text().strip():
                    listing.heating = heating_elem.get_text().strip()
                    break
            
            # Look for parking information
            parking_selectors = [
                '[class*="parking"]',
                '[class*="garage"]',
                '[class*="stellplatz"]'
            ]
            
            for selector in parking_selectors:
                parking_elem = soup.select_one(selector)
                if parking_elem and parking_elem.get_text().strip():
                    listing.parking = parking_elem.get_text().strip()
                    break
            
            # Look for energy class information
            energy_selectors = [
                '[class*="energy"]',
                '[class*="energie"]',
                '[class*="hwb"]'
            ]
            
            for selector in energy_selectors:
                energy_elem = soup.select_one(selector)
                if energy_elem:
                    energy_text = energy_elem.get_text().strip()
                    energy_class = self.extract_energy_class(energy_text)
                    if energy_class:
                        listing.energy_class = energy_class
                        break
            
            # Look for available from information
            available_selectors = [
                '[class*="available"]',
                '[class*="verfügbar"]',
                '[class*="from"]'
            ]
            
            for selector in available_selectors:
                available_elem = soup.select_one(selector)
                if available_elem and available_elem.get_text().strip():
                    listing.available_from = available_elem.get_text().strip()
                    break
            
            # Extract image URL
            listing.image_url = self.extract_image_url(soup)
            
            # Extract additional metadata details
            self.extract_metadata_details(soup, listing)
            
            # Add walking times based on district
            if listing.bezirk:
                ubahn_minutes, school_minutes = self.get_walking_times(listing.bezirk)
                listing.ubahn_walk_minutes = ubahn_minutes
                listing.school_walk_minutes = school_minutes
            
            # Handle Betriebskosten - estimate based on area
            if listing.area_m2:
                betriebskosten_breakdown = estimate_betriebskosten(listing.area_m2)
                listing.betriebskosten = betriebskosten_breakdown['total_incl_vat']
                listing.betriebskosten_breakdown = betriebskosten_breakdown
                listing.betriebskosten_estimated = True
            
            # Calculate mortgage details if price is available
            if listing.price_total:
                listing.calculated_monatsrate = self.calculate_monthly_rate(listing.price_total)
                listing.mortgage_details = self.get_mortgage_breakdown(listing.price_total)
                # Add Betriebskosten to total monthly cost
                total_monthly = listing.calculated_monatsrate
                if listing.betriebskosten:
                    total_monthly += listing.betriebskosten
                listing.total_monthly_cost = total_monthly
            
            # Calculate price per m² if we have both price and area
            if listing.price_total is not None and listing.area_m2 is not None:
                listing.price_per_m2 = listing.price_total / listing.area_m2
            
            # Check if we have enough data to consider this a valid listing
            if listing.title and listing.price_total and listing.area_m2:
                logging.info("✅ Successfully extracted data using HTML selectors")
                return listing
            else:
                logging.warning("⚠️ Insufficient data extracted using HTML selectors")
                return None
                
        except Exception as e:
            logging.error(f"❌ Error in HTML selector extraction: {e}")
            return None

    def extract_metadata_details(self, soup: BeautifulSoup, listing: Listing):
        """Extract additional details from metadata sections"""
        try:
            # Find all metadata sections
            metadata_sections = soup.find_all('dl', class_='sc-metadata')
            
            for section in metadata_sections:
                metadata_items = section.find_all('div', class_='sc-metadata-item')
                
                for item in metadata_items:
                    label_elem = item.find('dt', class_='sc-metadata-label')
                    value_elem = item.find('dd', class_='sc-metadata-value')
                    
                    if not label_elem or not value_elem:
                        continue
                    
                    label = label_elem.get_text(strip=True)
                    value = value_elem.get_text(strip=True)
                    
                    # Extract condition
                    if 'Zustand' in label:
                        listing.condition = value
                    
                    # Extract year built from availability
                    elif 'Verfügbarkeit' in label:
                        year = self.extract_year(value)
                        if year:
                            listing.year_built = year
                    
                    # Extract HWB value
                    elif 'Heizwärmebedarf (HWB) kWh/m2 im Jahr' in label:
                        try:
                            listing.hwb_value = float(value)
                        except (ValueError, TypeError):
                            pass
                    
                    # Extract energy class
                    elif 'Gesamtenergieeffizienz-Faktor' in label and not 'fGEE' in label:
                        # Look for badge with energy class
                        badge = value_elem.find('span', class_='sc-badge')
                        if badge:
                            listing.energy_class = badge.get_text(strip=True)
                    
                    # Extract heating type
                    elif 'Heizungsart' in label:
                        listing.heating_type = value
                    
                    # Extract energy carrier
                    elif 'Energieträger' in label:
                        listing.energy_carrier = value
                    
                    # Extract available from
                    elif 'Verfügbar ab' in label:
                        listing.available_from = value
                        
        except Exception as e:
            logging.warning(f"Error extracting metadata details: {e}")

    def extract_price(self, price_text: str) -> Optional[float]:
        """Extract price from text, handling various formats"""
        if not price_text or not isinstance(price_text, str):
            return None
        
        # Clean the text
        price_text = price_text.strip()
        
        # Handle "Preis auf Anfrage" or similar
        if any(phrase in price_text.lower() for phrase in ['anfrage', 'auf anfrage', 'preis auf anfrage']):
            return None
        
        # Handle 'k' format (e.g., "450k" = 450000)
        if price_text.lower().endswith('k'):
            try:
                base_value = float(price_text.lower().replace('k', '').strip())
                return base_value * 1000
            except ValueError:
                return None
        
        # Handle 'M' format (e.g., "1.2M" = 1200000)
        if price_text.lower().endswith('m'):
            try:
                base_value = float(price_text.lower().replace('m', '').strip())
                return base_value * 1000000
            except ValueError:
                return None
        
        # Remove currency symbols and spaces
        price_text = re.sub(r'[€$£¥\s]', '', price_text)
        
        # Handle different decimal separators
        if ',' in price_text and '.' in price_text:
            # Format like "450.000,00" - remove dots, replace comma with dot
            price_text = price_text.replace('.', '').replace(',', '.')
        elif ',' in price_text:
            # Format like "450,000" - replace comma with dot
            price_text = price_text.replace(',', '.')
        
        try:
            return float(price_text)
        except ValueError:
            return None

    def extract_area(self, area_text: str) -> Optional[float]:
        """Extract area from text, handling various formats"""
        if not area_text or not isinstance(area_text, str):
            return None
        
        # Clean the text
        area_text = area_text.strip()
        
        # Handle "Fläche auf Anfrage" or similar
        if any(phrase in area_text.lower() for phrase in ['anfrage', 'auf anfrage', 'fläche auf anfrage']):
            return None
        
        # Extract number from text like "85,5 m²", "85.5 m²", "85 m²", "85qm", etc.
        # Pattern to match numbers with optional decimal part
        area_match = re.search(r'(\d+(?:[.,]\d+)?)', area_text)
        if not area_match:
            return None
        
        try:
            area_str = area_match.group(1)
            # Handle different decimal separators
            if ',' in area_str and '.' in area_str:
                # Format like "85,5" - replace comma with dot
                area_str = area_str.replace(',', '.')
            elif ',' in area_str:
                # Format like "85,5" - replace comma with dot
                area_str = area_str.replace(',', '.')
            
            area_value = float(area_str)
            
            # Validate reasonable range (10-1000 m²)
            if 10 <= area_value <= 1000:
                return area_value
            else:
                return None
                
        except ValueError:
            return None

    def extract_rooms(self, rooms_text: str) -> Optional[float]:
        """Extract number of rooms from text"""
        if not rooms_text:
            return None
        
        # Try to extract just the number
        try:
            return float(rooms_text.strip())
        except ValueError:
            pass
        
        # Fallback to regex
        match = re.search(r'(\d+(?:[\.,]\d+)?)\s*(Zimmer|Zi\.|room)', rooms_text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(',', '.'))
        
        return None

    def extract_district(self, address: str) -> Optional[str]:
        """Extract district from address"""
        if not address:
            return None
        
        # Look for 4-digit Vienna district codes
        district_match = re.search(r'(\d{4})\s*Wien', address)
        if district_match:
            return district_match.group(1)
        
        # Look for district names and convert to codes
        district_map = {
            'innere stadt': '1010',
            'leopoldstadt': '1020',
            'landstraße': '1030',
            'wieden': '1040',
            'margareten': '1050',
            'mariahilf': '1060',
            'neubau': '1070',
            'josefstadt': '1080',
            'alsergrund': '1090',
            'favoriten': '1100',
            'simmering': '1110',
            'meidling': '1120',
            'hietzing': '1130',
            'penzing': '1140',
            'rudolfsheim-fünfhaus': '1150',
            'ottakring': '1160',
            'hernals': '1170',
            'währing': '1180',
            'döbling': '1190',
            'brigittenau': '1200',
            'floridsdorf': '1210',
            'donaustadt': '1220',
            'liesing': '1230'
        }
        
        address_lower = address.lower()
        for district_name, district_code in district_map.items():
            if district_name in address_lower:
                return district_code
        
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
                    year = self.extract_year(text)
                    if year:
                        return year
            
            # Try pattern matching in full text
            all_text = soup.get_text()
            year = self.extract_year(all_text)
            if year:
                return year
            
            return None
        except Exception as e:
            print(f"Error extracting year built: {e}")
            return None
    
    def extract_year(self, year_text: str) -> Optional[int]:
        """Extract year from text with enhanced patterns"""
        if not year_text:
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
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, year_text, re.IGNORECASE)
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
        year_match = re.search(r'(\d{4})', year_text)
        if year_match:
            try:
                year = int(year_match.group(1))
                if 1900 <= year <= 2024:
                    return year
            except ValueError:
                pass
        
        return None
    
    def calculate_monthly_rate(self, purchase_price: float) -> Optional[float]:
        """Calculate monthly mortgage payment using realistic Austrian rates"""
        try:
            # Realistic Austrian mortgage calculation based on loan calculator example
            # €244,299 loan → €1,069 monthly payment (3.815% rate, 35 years)
            # This gives us a ratio of approximately 0.00437
            
            # Calculate loan amount: 80% of property price + 10% extra fees
            # (20% down payment, 80% loan for property + 100% loan for fees)
            down_payment = purchase_price * 0.20  # 20% down payment
            property_loan = purchase_price * 0.80  # 80% loan for property
            extra_fees = purchase_price * 0.10    # 10% extra fees
            total_loan = property_loan + extra_fees
            
            # Use realistic ratio from loan calculator example
            realistic_ratio = 0.00437  # Based on €244,299 → €1,069 monthly (3.815% rate)
            monthly_payment = total_loan * realistic_ratio
            
            return round(monthly_payment, 2)
        except Exception as e:
            logging.warning(f"Error calculating monthly rate: {e}")
            return None
    
    def get_mortgage_breakdown(self, purchase_price: float) -> Dict:
        """Get detailed breakdown of monthly payment components using realistic Austrian rates"""
        try:
            # Realistic Austrian mortgage calculation based on loan calculator example
            # €244,299 loan → €1,069 monthly payment (3.815% rate, 35 years)
            # This gives us a ratio of approximately 0.00437
            
            # Calculate loan amount: 80% of property price + 10% extra fees
            # (20% down payment, 80% loan for property + 100% loan for fees)
            down_payment = purchase_price * 0.20  # 20% down payment
            property_loan = purchase_price * 0.80  # 80% loan for property
            extra_fees = purchase_price * 0.10    # 10% extra fees
            total_loan = property_loan + extra_fees
            
            # Use realistic ratio from loan calculator example
            realistic_ratio = 0.00437  # Based on €244,299 → €1,069 monthly (3.815% rate)
            monthly_payment = total_loan * realistic_ratio
            
            return {
                'base_payment': round(monthly_payment * 0.85, 2),  # 85% of total is base loan
                'extra_fees': round(monthly_payment * 0.15, 2),    # 15% of total is extra fees
                'total_monthly': round(monthly_payment, 2),
                'down_payment': round(down_payment, 2),
                'property_loan': round(property_loan, 2),
                'extra_fees_amount': round(extra_fees, 2),
                'total_loan': round(total_loan, 2)
            }
        except Exception as e:
            logging.warning(f"Error calculating mortgage breakdown: {e}")
            return {}
    
    def extract_energy_class(self, energy_text: str) -> Optional[str]:
        """Extract energy class from text"""
        if not energy_text:
            return None
        # Look for 'Energieklasse X' where X is A-G or A+
        match = re.search(r'Energieklasse\s*([A-G][+]?)\b', energy_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Or match A+ or A, B, ... as a standalone word (not part of 'unbekannt')
        # Use positive lookahead/lookbehind to ensure proper word boundaries
        match = re.search(r'(?<!\w)([A-G][+]?)(?!\w)', energy_text)
        if match:
            return match.group(1).upper()
        return None
    
    def get_walking_times(self, district: str) -> tuple:
        """Get walking times for district"""
        # Default walking times for Vienna districts
        ubahn_times = {
            '1010': 3, '1020': 5, '1030': 6, '1040': 4, '1050': 5,
            '1060': 4, '1070': 3, '1080': 4, '1090': 5, '1100': 8,
            '1120': 6, '1130': 10, '1140': 8, '1150': 6, '1160': 7,
            '1190': 12, '1210': 10, '1220': 15, '1230': 12
        }
        
        school_times = {
            '1010': 5, '1020': 6, '1030': 7, '1040': 5, '1050': 6,
            '1060': 5, '1070': 4, '1080': 5, '1090': 6, '1100': 8,
            '1120': 7, '1130': 10, '1140': 8, '1150': 7, '1160': 8,
            '1190': 12, '1210': 10, '1220': 12, '1230': 10
        }
        
        return (
            ubahn_times.get(district, 10),
            school_times.get(district, 8)
        )
    
    def validate_listing_data(self, data) -> bool:
        """Validate that listing has essential data"""
        required_fields = ['url', 'price_total', 'area_m2', 'rooms', 'bezirk', 'address']
        
        for field in required_fields:
            if hasattr(data, field):
                if not getattr(data, field):
                    return False
            elif isinstance(data, dict):
                if not data.get(field):
                    return False
            else:
                return False
        
        # Additional validation
        price_total = getattr(data, 'price_total', None) if hasattr(data, 'price_total') else data.get('price_total')
        area_m2 = getattr(data, 'area_m2', None) if hasattr(data, 'area_m2') else data.get('area_m2')
        rooms = getattr(data, 'rooms', None) if hasattr(data, 'rooms') else data.get('rooms')
        
        if price_total is not None and price_total < 10000:  # Too cheap
            return False
        
        if area_m2 is not None and area_m2 < 20:  # Too small
            return False
        
        if rooms is not None and rooms < 1:  # Invalid rooms
            return False
        
        return True
    
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
        elif hasattr(data, 'value'):  # Handle enums
            return data.value
        else:
            # Convert anything else to string
            return str(data)
    
    def scrape_search_results(self, search_url: str, max_pages: int = 5) -> List[Listing]:
        """Scrape all listings from search results with MongoDB integration"""
        logging.info(f"🔍 Starting derStandard scraping: {search_url}")
        
        # Get listing URLs
        listing_urls = self.extract_listing_urls(search_url, max_pages)
        
        if not listing_urls:
            logging.warning("⚠️ No listing URLs found")
            return []
        
        # Scrape individual listings
        all_listings: List[Listing] = []
        valid_count = 0
        invalid_count = 0
        saved_count = 0
        telegram_sent_count = 0  # Counter for Telegram messages
        max_telegram_messages = 5  # Limit Telegram messages to avoid spam
        
        for i, url in enumerate(listing_urls, 1):
            logging.info(f"🔍 Scraping listing {i}/{len(listing_urls)}: {url}")
            
            # Check if already exists in MongoDB (check the input URL first)
            if self.mongo.listing_exists(url):
                logging.info(f"⏭️  Skipping already processed: {url}")
                continue
            
            listing = self.scrape_single_listing(url)
            
            if listing:
                # Check if the listing's actual URL (which may differ from input URL for collections) already exists
                if listing.url != url and self.mongo.listing_exists(listing.url):
                    logging.info(f"⏭️  Skipping already processed (individual property): {listing.url}")
                    continue
                if self.meets_criteria(listing):
                    # Calculate score for logging
                    try:
                        from Application.scoring import score_apartment_simple
                        score = score_apartment_simple(listing.__dict__)
                        listing.score = score
                        
                        # Check if score is above threshold for Telegram
                        score_threshold = 40  # Default threshold
                        if self.config and 'telegram' in self.config:
                            score_threshold = self.config['telegram'].get('min_score_threshold', 40)
                        
                        score_above_threshold = score > score_threshold
                        telegram_status = "📱 Will be sent to Telegram" if score_above_threshold else f"⏭️  Score too low for Telegram (threshold: {score_threshold})"
                        
                        logging.info(f"✅ MATCHES CRITERIA: {listing.title}")
                        logging.info(f"   📊 Score: {score:.1f}/100 - {telegram_status}")
                        logging.info(f"   💰 Price: €{listing.price_total:,}" if listing.price_total else "   💰 Price: N/A")
                        logging.info(f"   📐 Area: {listing.area_m2}m²" if listing.area_m2 else "   📐 Area: N/A")
                        logging.info(f"   🏠 Rooms: {listing.rooms}" if listing.rooms else "   🏠 Rooms: N/A")
                        logging.info(f"   📍 District: {listing.bezirk}" if listing.bezirk else "   📍 District: N/A")
                        
                    except Exception as e:
                        logging.warning(f"⚠️  Could not calculate score: {e}")
                        score = 0
                        score_above_40 = False
                        telegram_status = "❌ Score calculation failed"
                    
                    all_listings.append(listing)
                    
                    # Normalize the listing schema to match Willhaben format
                    from Application.main import normalize_listing_schema
                    listing = normalize_listing_schema(listing)
                    
                    # Ensure source_enum is properly set as lowercase string
                    listing.source_enum = "derstandard"
                    
                    # Convert to dict and ensure serializable
                    listing_dict = self._ensure_serializable(listing)
                    
                    # Ensure all required fields are present with proper defaults
                    required_fields = {
                        'url': listing.url,
                        'source': 'derstandard',
                        'source_enum': 'derstandard',
                        'title': listing.title,
                        'bezirk': listing.bezirk,
                        'address': listing.address,
                        'price_total': listing.price_total,
                        'area_m2': listing.area_m2,
                        'rooms': listing.rooms,
                        'year_built': listing.year_built,
                        'floor': listing.floor,
                        'condition': listing.condition,
                        'heating': listing.heating,
                        'parking': listing.parking,
                        'betriebskosten': listing.betriebskosten,
                        'energy_class': listing.energy_class,
                        'hwb_value': listing.hwb_value,
                        'fgee_value': listing.fgee_value,
                        'heating_type': listing.heating_type,
                        'energy_carrier': listing.energy_carrier,
                        'available_from': listing.available_from,
                        'special_features': listing.special_features or [],
                        'monatsrate': listing.monatsrate,
                        'own_funds': listing.own_funds,
                        'price_per_m2': listing.price_per_m2,
                        'ubahn_walk_minutes': listing.ubahn_walk_minutes,
                        'school_walk_minutes': listing.school_walk_minutes,
                        'calculated_monatsrate': listing.calculated_monatsrate,
                        'mortgage_details': listing.mortgage_details or {},
                        'total_monthly_cost': listing.total_monthly_cost,
                        'infrastructure_distances': listing.infrastructure_distances or {},
                        'image_url': listing.image_url,
                        'structured_analysis': listing.structured_analysis or {},
                        'sent_to_telegram': False,
                        'processed_at': time.time(),
                        'local_image_path': listing.local_image_path,
                        'coordinates': listing.coordinates,
                        'score': getattr(listing, 'score', None)
                    }
                    
                    # Update listing_dict with required fields
                    listing_dict.update(required_fields)
                    
                    if self.mongo.insert_listing(listing_dict):
                        logging.info(f"💾 Saved to MongoDB: {listing.url}")
                        saved_count += 1
                        # Note: Telegram notifications are handled centrally in main.py
                    else:
                        logging.warning(f"⚠️  Already exists in MongoDB: {listing.url}")
                else:
                    logging.info(f"❌ Does not match criteria: {listing.url}")
                
                valid_count += 1
            else:
                invalid_count += 1
            
            # Rate limiting
            time.sleep(1)
        
        # Count high-score listings
        score_threshold = 40  # Default threshold
        if self.config and 'telegram' in self.config:
            score_threshold = self.config['telegram'].get('min_score_threshold', 40)
        
        high_score_count = sum(1 for listing in all_listings if hasattr(listing, 'score') and listing.score > score_threshold)
        
        logging.info(f"✅ derStandard scraping complete: {valid_count} valid, {invalid_count} invalid, {saved_count} saved to MongoDB")
        logging.info(f"📊 Score summary: {high_score_count}/{len(all_listings)} listings with score > {score_threshold}")
        return all_listings

def test_derstandard_scraper():
    """Test the derStandard scraper"""
    print("🧪 Testing derStandard Scraper")
    print("=" * 50)
    
    scraper = DerStandardScraper(use_selenium=True)
    
    try:
        print("🔍 Running full scrape and saving to MongoDB...")
        listings = scraper.scrape_search_results(scraper.search_url, max_pages=1)
        print(f"✅ Scraped and processed {len(listings)} listings.")
        if listings:
            # Print a sample listing with score and monthly rate
            from Application.scoring import score_apartment_simple
            sample = listings[0]
            score = score_apartment_simple(sample.__dict__ if hasattr(sample, '__dict__') else sample)
            monat = getattr(sample, 'calculated_monatsrate', None) or (sample.get('calculated_monatsrate') if isinstance(sample, dict) else None)
            print("--- Sample Listing ---")
            print(f"Title: {getattr(sample, 'title', None) or sample.get('title')}")
            print(f"Score: {score}")
            print(f"Monthly Rate: {monat}")
            print(f"Address: {getattr(sample, 'address', None) or sample.get('address')}")
            print(f"URL: {getattr(sample, 'url', None) or sample.get('url')}")
        else:
            print("No listings found.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    test_derstandard_scraper() 