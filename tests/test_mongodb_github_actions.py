#!/usr/bin/env python3
"""
Test MongoDB connection in GitHub Actions environment
"""

import sys
import os

# Add the Project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Project'))

def test_mongodb_connection():
    """Test MongoDB connection with GitHub Actions compatible settings"""
    print("🧪 Testing MongoDB Connection for GitHub Actions")
    print("=" * 50)
    
    from Application.helpers.utils import load_config
    from Integration.mongodb_handler import MongoDBHandler
    
    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False
    
    # Get MongoDB URI
    mongo_uri = config.get('mongodb_uri') or os.environ.get('MONGODB_URI')
    if not mongo_uri:
        print("❌ No MongoDB URI found")
        return False
    
    print(f"🔧 Testing connection to: {mongo_uri[:50]}...")
    
    try:
        # Initialize MongoDB handler
        mongo = MongoDBHandler(uri=mongo_uri)
        
        if mongo.client:
            print("✅ MongoDB connection successful!")
            
            # Test a simple query
            try:
                count = mongo.collection.count_documents({})
                print(f"✅ Database contains {count} documents")
                return True
            except Exception as e:
                print(f"⚠️ Query test failed: {e}")
                return False
        else:
            print("❌ MongoDB connection failed")
            return False
            
    except Exception as e:
        print(f"❌ MongoDB test error: {e}")
        return False

def test_alternative_connection():
    """Test alternative connection methods"""
    print("\n🧪 Testing Alternative Connection Methods")
    print("=" * 40)
    
    from pymongo import MongoClient
    
    # Get MongoDB URI
    mongo_uri = os.environ.get('MONGODB_URI')
    if not mongo_uri:
        print("❌ No MONGODB_URI environment variable")
        return False
    
    print(f"🔧 Testing alternative connection to: {mongo_uri[:50]}...")
    
    # Method 1: Direct connection with TLS options
    try:
        client = MongoClient(
            mongo_uri,
            tlsAllowInvalidCertificates=True,
            tlsInsecure=True,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        
        # Test connection
        client.admin.command('ping')
        print("✅ Alternative connection method 1 successful!")
        
        # Test database access
        db = client['immo']
        collection = db['listings']
        count = collection.count_documents({})
        print(f"✅ Found {count} documents in collection")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Alternative method 1 failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 MongoDB GitHub Actions Connection Tests")
    print("=" * 60)
    
    success1 = test_mongodb_connection()
    success2 = test_alternative_connection()
    
    print("\n" + "=" * 60)
    print(f"Result: {'✅ SUCCESS' if success1 or success2 else '❌ FAILED'}")
    
    if success1 or success2:
        print("🎉 MongoDB connection works in GitHub Actions environment!")
        print("✅ Connection established successfully")
        print("✅ Database queries work")
    else:
        print("❌ All connection methods failed")
        print("💡 Check your MongoDB URI and network settings")
    
    return success1 or success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 