#!/usr/bin/env python3
"""
Debug test for derStandard scraper
Tests multi-level navigation and data extraction
"""

import sys
import os
import logging

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Project'))

from Application.scraping.derstandard_scraper import DerStandardScraper
from bs4 import BeautifulSoup
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_derstandard_scraper():
    """Test the derStandard scraper with various URLs"""
    print("🧪 Testing derStandard Scraper")
    print("=" * 60)
    
    # Initialize scraper
    scraper = DerStandardScraper(use_selenium=False)
    
    # Test URLs - mix of individual and collection listings
    test_urls = [
        "https://immobilien.derstandard.at/detail/14463580",  # Individual listing
        "https://immobilien.derstandard.at/immobiliensuche/neubau/detail/14692813",  # Project listing
        "https://immobilien.derstandard.at/detail/14826650",  # Another individual
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n🔍 Test {i}: {url}")
        print("-" * 40)
        
        try:
            # First, get the raw HTML to analyze
            print("📥 Fetching page...")
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check if it's a collection listing
            print("🔍 Checking if collection listing...")
            is_collection = scraper.is_collection_listing(soup)
            print(f"   Collection: {is_collection}")
            
            if is_collection:
                print("📦 Detected collection, extracting individual properties...")
                individual_urls = scraper.extract_individual_property_urls_from_collection(soup, url)
                print(f"   Found {len(individual_urls)} individual properties:")
                for j, individual_url in enumerate(individual_urls[:3], 1):  # Show first 3
                    print(f"     {j}. {individual_url}")
                
                if individual_urls:
                    print(f"🔄 Testing first individual property...")
                    test_individual_listing(scraper, individual_urls[0])
            else:
                print("🏠 Individual listing, testing extraction...")
                test_individual_listing(scraper, url)
            
        except Exception as e:
            print(f"❌ Error testing {url}: {e}")
    
    print("\n✅ Test completed!")

def test_individual_listing(scraper, url):
    """Test extraction from an individual listing"""
    try:
        print(f"   📥 Fetching: {url}")
        
        # Get the page
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response.raise_for_status()
        html_content = response.text
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for the specific selectors mentioned
        print("   🔍 Looking for specific selectors...")
        
        # Check for sc-detail-section-group
        detail_sections = soup.find_all(class_='sc-detail-section-group')
        print(f"     sc-detail-section-group: {len(detail_sections)} found")
        
        # Check for heading-section-stats
        stats_sections = soup.find_all(class_='heading-section-stats')
        print(f"     heading-section-stats: {len(stats_sections)} found")
        
        # Check for heading-section-address
        address_sections = soup.find_all(class_='heading-section-address')
        print(f"     heading-section-address: {len(address_sections)} found")
        
        # Look for any elements with these classes
        all_elements = soup.find_all(class_=True)
        relevant_classes = []
        for elem in all_elements:
            classes = elem.get('class', [])
            for cls in classes:
                if any(keyword in cls.lower() for keyword in ['heading', 'section', 'stats', 'address', 'detail']):
                    relevant_classes.append(cls)
        
        print(f"     Relevant classes found: {list(set(relevant_classes))[:10]}")  # Show first 10 unique
        
        # Try to extract data using the scraper
        print("   🔄 Testing scraper extraction...")
        listing = scraper.scrape_single_listing(url)
        
        if listing:
            print("   ✅ Successfully extracted listing:")
            print(f"     Title: {listing.title}")
            print(f"     Price: {listing.price_total}")
            print(f"     Area: {listing.area_m2}")
            print(f"     Rooms: {listing.rooms}")
            print(f"     Address: {listing.address}")
            print(f"     Bezirk: {listing.bezirk}")
        else:
            print("   ❌ Failed to extract listing data")
            
            # Try JSON extraction manually
            print("   🔍 Trying manual JSON extraction...")
            property_data = scraper.extract_property_data_from_json(soup)
            if property_data:
                print(f"     ✅ Found JSON data: {property_data}")
            else:
                print("     ❌ No JSON data found")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def analyze_page_structure(url):
    """Analyze the page structure to understand the layout"""
    print(f"\n🔍 Analyzing page structure: {url}")
    print("-" * 40)
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response.raise_for_status()
        html_content = response.text
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for script tags with property data
        script_tags = soup.find_all('script')
        print(f"📜 Found {len(script_tags)} script tags")
        
        for i, script in enumerate(script_tags):
            script_content = script.get_text()
            if 'propertyData' in script_content or 'PropertyEntryResponse' in script_content:
                print(f"   Script {i}: Contains property data")
                # Show first 200 characters
                print(f"   Content preview: {script_content[:200]}...")
        
        # Look for specific elements
        print("\n🏗️ Page structure analysis:")
        
        # Check for main content areas
        main_content = soup.find('main')
        if main_content:
            print("   ✅ Found <main> element")
        
        # Check for article elements
        articles = soup.find_all('article')
        print(f"   📄 Found {len(articles)} <article> elements")
        
        # Check for div elements with specific classes
        divs_with_classes = soup.find_all('div', class_=True)
        print(f"   📦 Found {len(divs_with_classes)} divs with classes")
        
        # Show some class names
        all_classes = set()
        for div in divs_with_classes[:50]:  # Check first 50
            classes = div.get('class', [])
            all_classes.update(classes)
        
        print(f"   📋 Sample classes: {list(all_classes)[:20]}")
        
    except Exception as e:
        print(f"❌ Error analyzing page: {e}")

if __name__ == "__main__":
    # Run the main test
    test_derstandard_scraper()
    
    # Analyze a specific page structure
    print("\n" + "="*60)
    analyze_page_structure("https://immobilien.derstandard.at/detail/14463580") 