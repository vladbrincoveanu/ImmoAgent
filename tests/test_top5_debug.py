#!/usr/bin/env python3
"""
Debug script to investigate Top5 report issues
"""

import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Application.helpers.utils import load_config
from Integration.mongodb_handler import MongoDBHandler

def debug_top5_issues():
    """Debug why Top5 report is finding 0 listings"""
    print("🔍 Debugging Top5 Report Issues")
    print("=" * 50)
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Initialize MongoDB handler
    mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
    mongo = MongoDBHandler(uri=mongo_uri)
    
    if not mongo.client:
        print("❌ Failed to connect to MongoDB")
        return False
    
    # Get Top5 criteria from config
    top5_config = config.get('top5', {})
    limit = top5_config.get('limit', 5)
    min_score = top5_config.get('min_score', 40.0)
    days_old = top5_config.get('days_old', 7)
    excluded_districts = top5_config.get('excluded_districts', [])
    min_rooms = top5_config.get('min_rooms', 0)
    
    print(f"📋 Top5 Criteria:")
    print(f"   Limit: {limit}")
    print(f"   Min Score: {min_score}")
    print(f"   Days Old: {days_old}")
    print(f"   Excluded Districts: {excluded_districts}")
    print(f"   Min Rooms: {min_rooms}")
    print()
    
    # Check total listings in database
    total_listings = mongo.collection.count_documents({})
    print(f"📊 Total listings in database: {total_listings}")
    
    if total_listings == 0:
        print("❌ No listings in database at all!")
        return False
    
    # Check listings by score
    high_score_listings = mongo.collection.count_documents({"score": {"$gte": min_score}})
    print(f"📊 Listings with score >= {min_score}: {high_score_listings}")
    
    # Check listings by date
    cutoff_date = datetime.now() - timedelta(days=days_old)
    recent_listings = mongo.collection.count_documents({"created_at": {"$gte": cutoff_date}})
    print(f"📊 Listings from last {days_old} days (created_at): {recent_listings}")
    
    # Check for processed_at field (which is what the actual query uses)
    cutoff_timestamp = cutoff_date.timestamp()
    recent_listings_processed = mongo.collection.count_documents({"processed_at": {"$gte": cutoff_timestamp}})
    print(f"📊 Listings from last {days_old} days (processed_at): {recent_listings_processed}")
    
    # Check what date fields exist
    sample_with_dates = list(mongo.collection.find({"$or": [{"created_at": {"$exists": True}}, {"processed_at": {"$exists": True}}]}).limit(3))
    print(f"📊 Sample listings with date fields:")
    for i, listing in enumerate(sample_with_dates, 1):
        print(f"  {i}. created_at: {listing.get('created_at', 'N/A')}, processed_at: {listing.get('processed_at', 'N/A')}")
    
    # Check listings by rooms
    if min_rooms > 0:
        room_filtered = mongo.collection.count_documents({"rooms": {"$gte": min_rooms}})
        print(f"📊 Listings with {min_rooms}+ rooms: {room_filtered}")
    
    # Check listings by district (excluding excluded districts)
    if excluded_districts:
        district_filter = {"bezirk": {"$nin": excluded_districts}}
        district_filtered = mongo.collection.count_documents(district_filter)
        print(f"📊 Listings excluding districts {excluded_districts}: {district_filtered}")
    
    # Check combined filters using the correct field (processed_at)
    combined_filter = {"score": {"$gte": min_score}}
    
    if excluded_districts:
        combined_filter["bezirk"] = {"$nin": excluded_districts}
    
    if min_rooms > 0:
        combined_filter["rooms"] = {"$gte": min_rooms}
    
    combined_filter["processed_at"] = {"$gte": cutoff_timestamp}
    
    combined_count = mongo.collection.count_documents(combined_filter)
    print(f"📊 Listings matching ALL criteria (using processed_at): {combined_count}")
    
    # Show some sample listings to understand the data
    print(f"\n📋 Sample Listings Analysis:")
    print("-" * 40)
    
    # Get a few sample listings
    sample_listings = list(mongo.collection.find().limit(5))
    
    for i, listing in enumerate(sample_listings, 1):
        print(f"\n🏠 Sample Listing {i}:")
        print(f"   Title: {listing.get('title', 'N/A')}")
        print(f"   Score: {listing.get('score', 'N/A')}")
        print(f"   Created: {listing.get('created_at', 'N/A')}")
        print(f"   Rooms: {listing.get('rooms', 'N/A')}")
        print(f"   District: {listing.get('bezirk', 'N/A')}")
        print(f"   Price: €{listing.get('price_total', 'N/A'):,}" if listing.get('price_total') else "   Price: N/A")
    
    # Check what happens if we remove the date filter
    print(f"\n🔍 Testing without date filter:")
    no_date_filter = {"score": {"$gte": min_score}}
    
    if excluded_districts:
        no_date_filter["bezirk"] = {"$nin": excluded_districts}
    
    if min_rooms > 0:
        no_date_filter["rooms"] = {"$gte": min_rooms}
    
    no_date_count = mongo.collection.count_documents(no_date_filter)
    print(f"📊 Listings without date filter: {no_date_count}")
    
    if no_date_count > 0:
        print("✅ Found listings when removing date filter!")
        print("💡 The issue is likely the 'days_old' filter")
        
        # Show some of these listings
        no_date_listings = list(mongo.collection.find(no_date_filter).limit(3))
        print(f"\n📋 Sample listings without date filter:")
        for i, listing in enumerate(no_date_listings, 1):
            print(f"  {i}. Score: {listing.get('score', 'N/A')} | Processed: {listing.get('processed_at', 'N/A')} | District: {listing.get('bezirk', 'N/A')}")
    
    # Check what happens if we remove the room filter
    if min_rooms > 0:
        print(f"\n🔍 Testing without room filter:")
        no_room_filter = {"score": {"$gte": min_score}}
        
        if excluded_districts:
            no_room_filter["bezirk"] = {"$nin": excluded_districts}
        
        no_room_filter["processed_at"] = {"$gte": cutoff_timestamp}
        
        no_room_count = mongo.collection.count_documents(no_room_filter)
        print(f"📊 Listings without room filter: {no_room_count}")
        
        if no_room_count > 0:
            print("✅ Found listings when removing room filter!")
            print("💡 The issue might also be the 'min_rooms' filter")
    
    # Check what happens if we remove the district filter
    if excluded_districts:
        print(f"\n🔍 Testing without district filter:")
        no_district_filter = {"score": {"$gte": min_score}}
        
        if min_rooms > 0:
            no_district_filter["rooms"] = {"$gte": min_rooms}
        
        no_district_filter["processed_at"] = {"$gte": cutoff_timestamp}
        
        no_district_count = mongo.collection.count_documents(no_district_filter)
        print(f"📊 Listings without district filter: {no_district_count}")
        
        if no_district_count > 0:
            print("✅ Found listings when removing district filter!")
            print("💡 The issue might also be the 'excluded_districts' filter")
    
    print(f"\n💡 Recommendations:")
    print("1. Check if your properties are older than 7 days")
    print("2. Consider increasing 'days_old' in config.json")
    print("3. Check if properties have the correct 'rooms' field")
    print("4. Verify district codes in the database")
    
    return True

def main():
    """Run the debug script"""
    success = debug_top5_issues()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 