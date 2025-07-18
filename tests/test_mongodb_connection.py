#!/usr/bin/env python3
"""
Test MongoDB connection and authentication
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config
import pymongo

def test_mongodb():
    """Test MongoDB connection"""
    print("🧪 TESTING MONGODB CONNECTION")
    print("=" * 40)
    
    try:
        config = load_config()
        print(f"📋 Config loaded: {config.get('mongodb_uri', 'No URI found')}")
        
        # Test direct connection
        print("🔌 Testing direct connection...")
        client = pymongo.MongoClient(config.get('mongodb_uri'))
        
        # Test authentication
        print("🔐 Testing authentication...")
        db = client['immo']
        collection = db['listings']
        
        # Try to count documents
        count = collection.count_documents({})
        print(f"✅ Authentication successful! Total documents: {count}")
        
        # Test derStandard count
        derstandard_count = collection.count_documents({"source": "derstandard"})
        print(f"📊 derStandard documents: {derstandard_count}")
        
        # Test insert
        print("📝 Testing insert...")
        test_doc = {
            "url": "https://test.com",
            "title": "Test Listing",
            "source": "test",
            "price_total": 100000
        }
        
        result = collection.insert_one(test_doc)
        print(f"✅ Insert successful! ID: {result.inserted_id}")
        
        # Clean up test document
        collection.delete_one({"_id": result.inserted_id})
        print("🧹 Test document cleaned up")
        
        client.close()
        
    except Exception as e:
        print(f"❌ MongoDB test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mongodb() 