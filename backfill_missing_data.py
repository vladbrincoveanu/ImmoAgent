#!/usr/bin/env python3
"""
Backfill missing data for existing listings in MongoDB
Uses the structured analyzer to fill in null values
"""

import sys
import json
import time
from typing import Dict, List
from mongodb_handler import MongoDBHandler
from ollama_analyzer import StructuredAnalyzer, OllamaAnalyzer
import requests
from bs4 import BeautifulSoup

def load_config():
    """Load configuration from config files"""
    config_paths = ['config.json', 'immo-scouter/config.default.json']
    
    for config_path in config_paths:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                print(f"✅ Loaded config from {config_path}")
                return config
        except Exception as e:
            print(f"❌ Error loading {config_path}: {e}")
            continue
    
    print("❌ No config file found!")
    return {}

def get_listings_with_nulls(mongo: MongoDBHandler) -> List[Dict]:
    """Get listings that have null values in key fields"""
    null_fields = ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds', 'betriebskosten']
    
    # Create query to find documents with any null values
    query = {
        "$or": [
            {field: {"$in": [None, "null", ""]}} for field in null_fields
        ]
    }
    
    listings = list(mongo.collection.find(query))
    print(f"📋 Found {len(listings)} listings with missing data")
    return listings

def fetch_listing_html(url: str) -> str:
    """Fetch HTML content for a listing URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return ""

def count_null_fields(listing: Dict) -> int:
    """Count how many fields are null/missing"""
    null_fields = ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds', 'betriebskosten']
    count = 0
    for field in null_fields:
        if listing.get(field) in [None, "null", "", 0]:
            count += 1
    return count

def update_listing_in_db(mongo: MongoDBHandler, listing_id, updated_data: Dict) -> bool:
    """Update listing in MongoDB with new data"""
    try:
        # Only update fields that were actually filled
        update_fields = {}
        for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds', 'betriebskosten']:
            if field in updated_data and updated_data[field] is not None:
                update_fields[field] = updated_data[field]
        
        if update_fields:
            # Add metadata about the backfill
            update_fields['backfilled_at'] = time.time()
            update_fields['backfilled_fields'] = list(update_fields.keys())
            
            result = mongo.collection.update_one(
                {"_id": listing_id},
                {"$set": update_fields}
            )
            return result.modified_count > 0
        return False
    except Exception as e:
        print(f"❌ Error updating listing {listing_id}: {e}")
        return False

def main():
    """Main backfill process"""
    print("🔄 STARTING DATA BACKFILL PROCESS")
    print("=" * 60)
    
    # Load configuration
    config = load_config()
    
    # Initialize components
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    
    # Try to use StructuredAnalyzer first (OpenAI), fallback to OllamaAnalyzer
    structured_analyzer = StructuredAnalyzer(
        api_key=config.get('openai_api_key'),
        model=config.get('openai_model', 'gpt-4o-mini')
    )
    
    ollama_analyzer = OllamaAnalyzer()
    
    # Determine which analyzer to use
    if structured_analyzer.is_available():
        analyzer = structured_analyzer
        analyzer_name = "OpenAI StructuredAnalyzer"
        print(f"✅ Using {analyzer_name}")
    elif ollama_analyzer.is_available():
        analyzer = ollama_analyzer
        analyzer_name = "Ollama Analyzer"
        print(f"✅ Using {analyzer_name}")
    else:
        print("❌ No analyzer available! Please check your configuration.")
        return
    
    # Get listings with missing data
    listings_with_nulls = get_listings_with_nulls(mongo)
    
    if not listings_with_nulls:
        print("🎉 No listings found with missing data!")
        return
    
    print(f"🔧 Processing {len(listings_with_nulls)} listings...")
    
    # Statistics
    stats = {
        'processed': 0,
        'updated': 0,
        'failed': 0,
        'fields_filled': 0
    }
    
    for i, listing in enumerate(listings_with_nulls, 1):
        url = listing.get('url', 'Unknown')
        listing_id = listing.get('_id')
        
        print(f"\n📋 [{i}/{len(listings_with_nulls)}] Processing: {url}")
        
        # Count null fields before processing
        nulls_before = count_null_fields(listing)
        print(f"   📊 Null fields before: {nulls_before}")
        
        try:
            # Fetch HTML content
            print("   🌐 Fetching HTML...")
            html_content = fetch_listing_html(url)
            
            if not html_content:
                print("   ❌ Failed to fetch HTML content")
                stats['failed'] += 1
                continue
            
            # Analyze with structured analyzer
            print(f"   🧠 Analyzing with {analyzer_name}...")
            if hasattr(analyzer, 'analyze_listing_content'):
                updated_listing = analyzer.analyze_listing_content(listing, html_content)
            else:
                # Fallback for OllamaAnalyzer
                analysis_result = analyzer.analyze_listing(listing)
                updated_listing = listing.copy()
                updated_listing.update(analysis_result)
            
            # Count null fields after processing
            nulls_after = count_null_fields(updated_listing)
            fields_filled = nulls_before - nulls_after
            
            print(f"   📊 Null fields after: {nulls_after}")
            print(f"   ✅ Fields filled: {fields_filled}")
            
            # Update in database if we filled any fields
            if fields_filled > 0:
                if update_listing_in_db(mongo, listing_id, updated_listing):
                    print("   💾 Updated in database")
                    stats['updated'] += 1
                    stats['fields_filled'] += fields_filled
                else:
                    print("   ⚠️  Failed to update database")
            else:
                print("   ℹ️  No new data extracted")
            
            stats['processed'] += 1
            
            # Add small delay to be respectful
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Error processing listing: {e}")
            stats['failed'] += 1
            continue
    
    # Print final statistics
    print("\n" + "=" * 60)
    print("📊 BACKFILL COMPLETE - STATISTICS")
    print("=" * 60)
    print(f"📋 Total processed: {stats['processed']}")
    print(f"✅ Successfully updated: {stats['updated']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"🔧 Total fields filled: {stats['fields_filled']}")
    print(f"📈 Success rate: {(stats['updated']/stats['processed']*100):.1f}%" if stats['processed'] > 0 else "0%")
    
    if stats['updated'] > 0:
        print(f"\n🎉 Successfully backfilled data for {stats['updated']} listings!")
        print("💡 You can now run your main script to see improved data quality.")
    else:
        print("\n⚠️  No listings were updated. Check your analyzer configuration.")

if __name__ == "__main__":
    main() 