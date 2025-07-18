#!/usr/bin/env python3
"""
Monitor progress of derStandard scraper
"""

import sys
import os
import time

# Add Project directory to path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Project'))

from Integration.mongodb_handler import MongoDBHandler
from Application.helpers.utils import load_config

def get_derstandard_count():
    """Get current count of derStandard listings"""
    try:
        config = load_config()
        mongo_handler = MongoDBHandler(
            uri=config.get('mongodb_uri', 'mongodb://localhost:27017/'),
            db_name=config.get('mongodb_db_name', 'immo'),
            collection_name=config.get('mongodb_collection_name', 'listings')
        )
        
        count = mongo_handler.collection.count_documents({"source": "derstandard"})
        return count
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0

def main():
    """Monitor progress"""
    print("📊 MONITORING DERSTANDARD SCRAPER PROGRESS")
    print("=" * 50)
    
    target = 100
    last_count = 0
    
    while True:
        current_count = get_derstandard_count()
        
        if current_count != last_count:
            print(f"🕐 {time.strftime('%H:%M:%S')} - Count: {current_count}/{target}")
            
            if current_count >= target:
                print(f"🎉 TARGET REACHED! {current_count} items in database")
                break
                
            last_count = current_count
        
        time.sleep(10)  # Check every 10 seconds

if __name__ == "__main__":
    main() 