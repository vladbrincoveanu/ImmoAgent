#!/usr/bin/env python3
"""
Script to fix MongoDB documents by converting source and source_enum fields to strings
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pymongo import MongoClient
import json

def load_config():
    """Load configuration from config.json"""
    try:
        with open('Project/config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not load config.json: {e}")
        return {}

def fix_mongodb_sources():
    """Fix source and source_enum fields in MongoDB documents"""
    config = load_config()
    mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
    
    print(f"Connecting to MongoDB: {mongo_uri}")
    
    try:
        client = MongoClient(mongo_uri)
        db = client['immo']
        collection = db['listings']
        
        # Count total documents
        total_docs = collection.count_documents({})
        print(f"Total documents in collection: {total_docs}")
        
        # Find documents with complex source fields
        complex_source_docs = collection.find({
            '$or': [
                {'source': {'$type': 'object'}},
                {'source_enum': {'$type': 'object'}}
            ]
        })
        
        fixed_count = 0
        for doc in complex_source_docs:
            doc_id = doc['_id']
            updates = {}
            
            # Fix source field
            if isinstance(doc.get('source'), dict) and '_value_' in doc['source']:
                updates['source'] = doc['source']['_value_']
                print(f"Fixing source for doc {doc_id}: {doc['source']['_value_']}")
            
            # Fix source_enum field
            if isinstance(doc.get('source_enum'), dict) and '_value_' in doc['source_enum']:
                updates['source_enum'] = doc['source_enum']['_value_']
                print(f"Fixing source_enum for doc {doc_id}: {doc['source_enum']['_value_']}")
            
            # Update the document if there are changes
            if updates:
                result = collection.update_one(
                    {'_id': doc_id},
                    {'$set': updates}
                )
                if result.modified_count > 0:
                    fixed_count += 1
                    print(f"✅ Fixed document {doc_id}")
        
        print(f"\n🎉 Fixed {fixed_count} documents")
        
        # Verify the fix
        remaining_complex = collection.count_documents({
            '$or': [
                {'source': {'$type': 'object'}},
                {'source_enum': {'$type': 'object'}}
            ]
        })
        print(f"Remaining documents with complex source fields: {remaining_complex}")
        
        client.close()
        
    except Exception as e:
        print(f"Error fixing MongoDB documents: {e}")

if __name__ == "__main__":
    fix_mongodb_sources() 