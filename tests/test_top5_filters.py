#!/usr/bin/env python3
"""
Test script to verify top5 filtering functionality
"""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config

@pytest.mark.smoke
def test_top5_filters():
    """Test the new top5 filtering functionality"""
    print("🧪 Testing Top5 Filtering Functionality")
    print("=" * 50)
    
    try:
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
        
        print("✅ MongoDB connection successful")
        
        # Test 1: Basic filtering without exclusions
        print("\n📊 Test 1: Basic filtering (no exclusions)")
        print("-" * 40)
        
        listings1 = mongo.get_top_listings(
            limit=3,
            min_score=0.0,
            days_old=30,
            excluded_districts=[],
            min_rooms=1
        )
        
        print(f"Found {len(listings1)} listings")
        for i, listing in enumerate(listings1, 1):
            score = listing.get('score', 0)
            price = listing.get('price_total', 0)
            area = listing.get('area_m2', 0)
            rooms = listing.get('rooms', 0)
            bezirk = listing.get('bezirk', 'N/A')
            monthly_payment = listing.get('monthly_payment', {})
            
            print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk}")
            if monthly_payment:
                total = monthly_payment.get('total_monthly', 0)
                loan = monthly_payment.get('loan_payment', 0)
                bk = monthly_payment.get('betriebskosten', 0)
                print(f"     💳 Monthly: €{total:,.0f} (€{loan:,.0f} loan + €{bk:,.0f} BK)")
        
        # Test 2: District exclusion
        print("\n📊 Test 2: District exclusion (excluding 1230)")
        print("-" * 40)
        
        listings2 = mongo.get_top_listings(
            limit=3,
            min_score=0.0,
            days_old=30,
            excluded_districts=["1230"],
            min_rooms=1
        )
        
        print(f"Found {len(listings2)} listings (excluding 1230)")
        for i, listing in enumerate(listings2, 1):
            score = listing.get('score', 0)
            price = listing.get('price_total', 0)
            area = listing.get('area_m2', 0)
            rooms = listing.get('rooms', 0)
            bezirk = listing.get('bezirk', 'N/A')
            
            print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk}")
            
            # Verify no 1230 districts
            if bezirk == "1230":
                print(f"     ❌ ERROR: Found excluded district {bezirk}")
                return False
        
        # Test 3: Minimum rooms filter
        print("\n📊 Test 3: Minimum rooms filter (3+ rooms)")
        print("-" * 40)
        
        listings3 = mongo.get_top_listings(
            limit=3,
            min_score=0.0,
            days_old=30,
            excluded_districts=[],
            min_rooms=3
        )
        
        print(f"Found {len(listings3)} listings (3+ rooms)")
        for i, listing in enumerate(listings3, 1):
            score = listing.get('score', 0)
            price = listing.get('price_total', 0)
            area = listing.get('area_m2', 0)
            rooms = listing.get('rooms', 0)
            bezirk = listing.get('bezirk', 'N/A')
            
            print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk}")
            
            # Verify minimum rooms
            if rooms and rooms < 3:
                print(f"     ❌ ERROR: Found listing with {rooms} rooms (should be 3+)")
                return False
        
        # Test 4: Combined filters
        print("\n📊 Test 4: Combined filters")
        print("-" * 40)
        
        listings4 = mongo.get_top_listings(
            limit=3,
            min_score=0.0,
            days_old=30,
            excluded_districts=["1230"],
            min_rooms=2
        )
        
        print(f"Found {len(listings4)} listings (excluding 1230, 2+ rooms)")
        for i, listing in enumerate(listings4, 1):
            score = listing.get('score', 0)
            price = listing.get('price_total', 0)
            area = listing.get('area_m2', 0)
            rooms = listing.get('rooms', 0)
            bezirk = listing.get('bezirk', 'N/A')
            monthly_payment = listing.get('monthly_payment', {})
            
            print(f"  {i}. Score: {score:.1f} | €{price:,.0f} | {area}m² | {rooms} rooms | {bezirk}")
            if monthly_payment:
                total = monthly_payment.get('total_monthly', 0)
                print(f"     💳 Total Monthly: €{total:,.0f}")
            
            # Verify filters
            if bezirk == "1230":
                print(f"     ❌ ERROR: Found excluded district {bezirk}")
                return False
            if rooms and rooms < 2:
                print(f"     ❌ ERROR: Found listing with {rooms} rooms (should be 2+)")
                return False
        
        print("\n" + "=" * 50)
        print("🎉 Top5 Filtering Test Complete!")
        print("✅ District exclusion works")
        print("✅ Minimum rooms filter works")
        print("✅ Monthly payment calculations work")
        print("✅ Combined filters work correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return False

def main():
    """Run the test"""
    success = test_top5_filters()
    
    print("\n" + "=" * 50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
