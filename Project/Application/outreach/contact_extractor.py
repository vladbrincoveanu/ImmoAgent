"""
Contact extractor module for extracting email addresses and contact forms from listing pages.
Supports Willhaben, derStandard, and Immo Kurier.
"""

import re
import logging
import time
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
import requests
from dataclasses import dataclass
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class ContactType(Enum):
    EMAIL = "email"
    CONTACT_FORM = "contact_form"
    PHONE = "phone"
    NONE = "none"


@dataclass
class ContactInfo:
    """Contact information extracted from a listing page."""
    contact_type: ContactType
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_form_url: Optional[str] = None
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    source: str = ""
    listing_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_type": self.contact_type.value,
            "email": self.email,
            "phone": self.phone,
            "contact_form_url": self.contact_form_url,
            "agent_name": self.agent_name,
            "agency_name": self.agency_name,
            "source": self.source,
            "listing_url": self.listing_url
        }


class ContactExtractor:
    """Extract contact information from real estate listing pages."""
    
    # Email regex pattern
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        re.IGNORECASE
    )
    
    # Phone regex pattern (Austrian format)
    PHONE_PATTERN = re.compile(
        r'(?:\+43|0043|0)\s*[1-9]\d{1,4}[\s/.-]?\d{2,4}[\s/.-]?\d{2,4}[\s/.-]?\d{0,4}',
        re.IGNORECASE
    )
    
    def __init__(self, config: Optional[Dict] = None, use_selenium: bool = True):
        self.config = config or {}
        self.use_selenium = use_selenium
        self.driver = None
        
        self.session = requests.Session()
        scraping_config = self.config.get('scraping', {})
        self.session.headers.update({
            'User-Agent': scraping_config.get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        })
        
        self.timeout = scraping_config.get('timeout', 30)
        self.selenium_wait_time = scraping_config.get('selenium_wait_time', 10)
    
    def _init_selenium(self):
        """Initialize Selenium WebDriver if not already initialized."""
        if self.driver is not None:
            return
        
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            logging.info("✅ Selenium WebDriver initialized for contact extraction")
        except Exception as e:
            logging.warning(f"⚠️ Failed to initialize Selenium: {e}")
            self.use_selenium = False
    
    def _close_selenium(self):
        """Close Selenium WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
    
    def _get_page_content(self, url: str) -> Optional[str]:
        """Get page content using Selenium or requests."""
        if self.use_selenium:
            self._init_selenium()
            if self.driver:
                try:
                    self.driver.get(url)
                    time.sleep(2)  # Wait for dynamic content
                    return self.driver.page_source
                except Exception as e:
                    logging.warning(f"⚠️ Selenium failed for {url}: {e}")
        
        # Fallback to requests
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logging.error(f"❌ Failed to fetch {url}: {e}")
            return None
    
    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract all email addresses from text."""
        emails = self.EMAIL_PATTERN.findall(text)
        # Filter out common false positives
        blacklist = ['example.com', 'domain.com', 'email.com', 'test.com', '.png', '.jpg', '.gif']
        return [e for e in set(emails) if not any(b in e.lower() for b in blacklist)]
    
    def _extract_phones_from_text(self, text: str) -> List[str]:
        """Extract all phone numbers from text."""
        phones = self.PHONE_PATTERN.findall(text)
        # Clean and deduplicate
        cleaned = []
        for phone in phones:
            clean = re.sub(r'[\s/.-]', '', phone)
            if len(clean) >= 9:  # Valid Austrian phone numbers
                cleaned.append(phone.strip())
        return list(set(cleaned))
    
    def extract_willhaben_contact(self, url: str, soup: Optional[BeautifulSoup] = None) -> ContactInfo:
        """Extract contact info from Willhaben listing."""
        if soup is None:
            html = self._get_page_content(url)
            if not html:
                return ContactInfo(contact_type=ContactType.NONE, source="willhaben", listing_url=url)
            soup = BeautifulSoup(html, 'html.parser')
        
        contact = ContactInfo(contact_type=ContactType.NONE, source="willhaben", listing_url=url)
        
        # Willhaben uses a contact button that reveals email/form
        # Look for contact section
        contact_section = soup.find('div', {'data-testid': 'contact-box'}) or \
                         soup.find('div', class_=re.compile(r'contact', re.I))
        
        if contact_section:
            text = contact_section.get_text()
            
            # Try to find email
            emails = self._extract_emails_from_text(text)
            if emails:
                contact.email = emails[0]
                contact.contact_type = ContactType.EMAIL
            
            # Try to find phone
            phones = self._extract_phones_from_text(text)
            if phones:
                contact.phone = phones[0]
            
            # Try to find agent/agency name
            name_elem = contact_section.find(['h2', 'h3', 'span'], class_=re.compile(r'name|agent|makler', re.I))
            if name_elem:
                contact.agent_name = name_elem.get_text(strip=True)
        
        # Look for "Anfrage senden" (contact form) button
        contact_btn = soup.find('button', string=re.compile(r'anfrage|kontakt|nachricht', re.I)) or \
                     soup.find('a', href=re.compile(r'contact|anfrage|nachricht', re.I))
        
        if contact_btn and contact.contact_type == ContactType.NONE:
            contact.contact_type = ContactType.CONTACT_FORM
            if contact_btn.get('href'):
                contact.contact_form_url = contact_btn['href']
        
        # Search entire page for emails as fallback
        if contact.contact_type == ContactType.NONE:
            page_text = soup.get_text()
            emails = self._extract_emails_from_text(page_text)
            if emails:
                contact.email = emails[0]
                contact.contact_type = ContactType.EMAIL
        
        return contact
    
    def extract_derstandard_contact(self, url: str, soup: Optional[BeautifulSoup] = None) -> ContactInfo:
        """Extract contact info from derStandard listing."""
        if soup is None:
            html = self._get_page_content(url)
            if not html:
                return ContactInfo(contact_type=ContactType.NONE, source="derstandard", listing_url=url)
            soup = BeautifulSoup(html, 'html.parser')
        
        contact = ContactInfo(contact_type=ContactType.NONE, source="derstandard", listing_url=url)
        
        # First, search for emails in data attributes and hidden elements
        # Many sites hide emails in data attributes to prevent scraping
        for elem in soup.find_all(True):
            # Check data attributes
            for attr_name, attr_value in elem.attrs.items():
                if isinstance(attr_value, str):
                    emails = self._extract_emails_from_text(attr_value)
                    if emails:
                        contact.email = emails[0]
                        contact.contact_type = ContactType.EMAIL
                        break
            
            # Check text content
            if elem.string:
                emails = self._extract_emails_from_text(elem.string)
                if emails:
                    contact.email = emails[0]
                    contact.contact_type = ContactType.EMAIL
                    break
        
        # If no email found, search entire page text
        if contact.contact_type == ContactType.NONE:
            page_text = soup.get_text()
            emails = self._extract_emails_from_text(page_text)
            if emails:
                contact.email = emails[0]
                contact.contact_type = ContactType.EMAIL
        
        # Extract phones
        page_text = soup.get_text()
        phones = self._extract_phones_from_text(page_text)
        if phones:
            contact.phone = phones[0]
        
        # Look for agency info
        agency_elem = soup.find(['span', 'div', 'a'], class_=re.compile(r'agency|makler|anbieter|provider', re.I))
        if agency_elem:
            contact.agency_name = agency_elem.get_text(strip=True)
        
        # Check for contact form (only if no email found)
        if contact.contact_type == ContactType.NONE:
            contact_form = soup.find('form', class_=re.compile(r'contact|anfrage', re.I)) or \
                          soup.find('button', string=re.compile(r'anfrage|kontaktieren', re.I))
            
            if contact_form:
                contact.contact_type = ContactType.CONTACT_FORM
                contact.contact_form_url = url + "#contact"
        
        return contact
    
    def extract_immo_kurier_contact(self, url: str, soup: Optional[BeautifulSoup] = None) -> ContactInfo:
        """Extract contact info from Immo Kurier listing."""
        if soup is None:
            html = self._get_page_content(url)
            if not html:
                return ContactInfo(contact_type=ContactType.NONE, source="immo_kurier", listing_url=url)
            soup = BeautifulSoup(html, 'html.parser')
        
        contact = ContactInfo(contact_type=ContactType.NONE, source="immo_kurier", listing_url=url)
        
        page_text = soup.get_text()
        
        # Extract emails
        emails = self._extract_emails_from_text(page_text)
        if emails:
            contact.email = emails[0]
            contact.contact_type = ContactType.EMAIL
        
        # Extract phones
        phones = self._extract_phones_from_text(page_text)
        if phones:
            contact.phone = phones[0]
        
        # Look for contact section
        contact_section = soup.find('div', class_=re.compile(r'contact|makler|agent', re.I))
        if contact_section:
            name_elem = contact_section.find(['h3', 'h4', 'span'], class_=re.compile(r'name', re.I))
            if name_elem:
                contact.agent_name = name_elem.get_text(strip=True)
        
        return contact
    
    def extract_contact(self, listing: Dict[str, Any]) -> ContactInfo:
        """Extract contact info from a listing based on its source."""
        url = listing.get('url', '')
        source = listing.get('source', '').lower()
        
        if not url:
            return ContactInfo(contact_type=ContactType.NONE, source=source, listing_url=url)
        
        logging.info(f"📧 Extracting contact from {source}: {url}")
        
        try:
            if source == 'willhaben':
                return self.extract_willhaben_contact(url)
            elif source == 'derstandard':
                return self.extract_derstandard_contact(url)
            elif source == 'immo_kurier':
                return self.extract_immo_kurier_contact(url)
            else:
                # Generic extraction
                html = self._get_page_content(url)
                if html:
                    page_text = BeautifulSoup(html, 'html.parser').get_text()
                    emails = self._extract_emails_from_text(page_text)
                    phones = self._extract_phones_from_text(page_text)
                    
                    contact = ContactInfo(
                        contact_type=ContactType.EMAIL if emails else ContactType.NONE,
                        email=emails[0] if emails else None,
                        phone=phones[0] if phones else None,
                        source=source,
                        listing_url=url
                    )
                    return contact
                
                return ContactInfo(contact_type=ContactType.NONE, source=source, listing_url=url)
        except Exception as e:
            logging.error(f"❌ Error extracting contact from {url}: {e}")
            return ContactInfo(contact_type=ContactType.NONE, source=source, listing_url=url)
    
    def cleanup(self):
        """Clean up resources."""
        self._close_selenium()


