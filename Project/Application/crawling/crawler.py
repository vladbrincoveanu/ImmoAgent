import requests
import re
import json
import time
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

def parse_listing_html(html: str, url: str) -> Dict[str, Any]:
    """
    Parse HTML content and extract structured real estate data
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get all text content for regex parsing
    raw_text = soup.get_text(separator=' ', strip=True)
    
    # Extract individual fields
    result = {
        "bezirk": extract_bezirk(raw_text),
        "price_total": extract_price(raw_text, soup),
        "area_m2": extract_area(raw_text),
        "year_built": extract_year(raw_text),
        "url": url,
        "special_comment": extract_special_comments(raw_text, soup)
    }
    
    # Calculate price per m²
    if result["price_total"] and result["area_m2"]:
        result["price_per_m2"] = round(result["price_total"] / result["area_m2"], 2)
    else:
        result["price_per_m2"] = None
    
    # Get U-Bahn walking distance
    result["ubahn_walk_minutes"] = calculate_ubahn_distance(result["bezirk"], raw_text)
    
    return result

def extract_bezirk(text: str) -> Optional[str]:
    """Extract Vienna district code (1010-1230)"""
    # Austrian postal codes for Vienna districts
    bezirk_patterns = [
        r'(\d{4})\s+Wien',  # "1210 Wien"
        r'Wien\s+(\d{4})',  # "Wien 1210"
        r'(\d{4})\s*,\s*Wien',  # "1210, Wien"
    ]
    
    for pattern in bezirk_patterns:
        match = re.search(pattern, text)
        if match:
            code = match.group(1)
            # Validate Vienna district codes (1010-1230)
            if code.startswith('1') and len(code) == 4:
                return code
    return None

def extract_price(text: str, soup: BeautifulSoup) -> Optional[int]:
    """Extract total purchase price"""
    # Try specific CSS selectors first
    price_selectors = [
        '.search-result-price',
        '.price-value',
        '[data-testid="price"]',
        '.listing-price'
    ]
    
    for selector in price_selectors:
        price_elem = soup.select_one(selector)
        if price_elem:
            price_text = price_elem.get_text()
            price_match = re.search(r'€\s*([\d\.]+)', price_text)
            if price_match:
                return int(price_match.group(1).replace('.', ''))
    
    # Fallback to regex on full text
    price_patterns = [
        r'Kaufpreis.*?€\s*([\d\.]+)',
        r'Preis.*?€\s*([\d\.]+)',
        r'€\s*([\d\.]+)',
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1).replace('.', ''))
    
    return None

def extract_area(text: str) -> Optional[float]:
    """Extract living area in square meters"""
    area_patterns = [
        r'Wohnfläche.*?([\d,]+)\s*m²',
        r'([\d,]+)\s*m²\s*Wohnfläche',
        r'Nutzfläche.*?([\d,]+)\s*m²',
        r'([\d,]+)\s*m²'
    ]
    
    for pattern in area_patterns:
        match = re.search(pattern, text)
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

def extract_year(text: str) -> Optional[int]:
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
            # Validate reasonable year range
            if 1800 <= year <= 2025:
                return year
    
    return None

def extract_special_comments(text: str, soup: BeautifulSoup) -> Optional[str]:
    """Extract special conditions or comments"""
    special_keywords = [
        'vermietet', 'befristet', 'nicht beziehbar', 'sanierungsbedürftig',
        'renovierungsbedürftig', 'denkmalschutz', 'rented', 'occupied'
    ]
    
    # Look for description sections
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
                    return desc_elem.get_text().strip()[:200]  # Limit length
    
    # Fallback to scanning full text
    text_lower = text.lower()
    for keyword in special_keywords:
        if keyword in text_lower:
            # Extract sentence containing the keyword
            sentences = text.split('.')
            for sentence in sentences:
                if keyword in sentence.lower():
                    return sentence.strip()[:200]
    
    return None

def calculate_ubahn_distance(bezirk: str, text: str) -> Optional[int]:
    """
    Calculate walking distance to nearest U-Bahn station
    """
    if not bezirk:
        return None
    
    # Static mapping for common districts (fallback)
    ubahn_distances = {
        '1010': 3,   # City center - very close to U-Bahn
        '1020': 5,   # Prater area
        '1030': 6,   # Landstraße
        '1040': 4,   # Wieden
        '1050': 5,   # Margareten
        '1060': 4,   # Mariahilf
        '1070': 3,   # Neubau
        '1080': 4,   # Josefstadt
        '1090': 5,   # Alsergrund
        '1100': 8,   # Favoriten
        '1110': 10,  # Simmering
        '1120': 12,  # Meidling
        '1130': 15,  # Hietzing
        '1140': 12,  # Penzing
        '1150': 8,   # Rudolfsheim
        '1160': 10,  # Ottakring
        '1170': 12,  # Hernals
        '1180': 15,  # Währing
        '1190': 18,  # Döbling
        '1200': 10,  # Brigittenau
        '1210': 12,  # Floridsdorf
        '1220': 15,  # Donaustadt
        '1230': 20   # Liesing
    }
    
    # Try to extract specific U-Bahn mentions from text
    ubahn_pattern = r'U\d+.*?(\d+)\s*min'
    ubahn_match = re.search(ubahn_pattern, text)
    if ubahn_match:
        return int(ubahn_match.group(1))
    
    # Use static mapping as fallback
    return ubahn_distances.get(bezirk, 15)  # Default 15 minutes

def calculate_ubahn_distance_api(address: str) -> Optional[int]:
    """
    Alternative: Use Google Maps API for precise walking time
    Requires Google Maps API key
    """
    # This would make an API call to Google Distance Matrix
    # Implementation depends on your API key and rate limits
    pass


def scrape_listing(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch HTML and parse listing data
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return parse_listing_html(response.text, url)
        
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def scrape_multiple_listings(urls: list) -> list:
    """
    Scrape multiple listings and return JSON array
    """
    results = []
    
    for url in urls:
        print(f"Scraping: {url}")
        listing_data = scrape_listing(url)
        
        if listing_data:
            results.append(listing_data)
        
        # Be respectful - add delay between requests
        time.sleep(1)
    
    return results
