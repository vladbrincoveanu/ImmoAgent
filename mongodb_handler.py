import pymongo
from pymongo import MongoClient
from typing import Dict, Optional
import os
import json
from helpers import load_config

class MongoDBHandler:
    def __init__(self, uri: str = None, db_name: str = "immo", collection_name: str = "listings"):
        config = load_config()
        self.uri = uri or config.get("mongodb_uri") or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
        self.client = MongoClient(self.uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("url", unique=True)

    def insert_listing(self, listing: Dict) -> bool:
        try:
            self.collection.insert_one(listing)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False
        except Exception as e:
            print(f"MongoDB insert error: {e}")
            return False

    def listing_exists(self, url: str) -> bool:
        return self.collection.find_one({"url": url}) is not None

    def mark_sent(self, url: str):
        self.collection.update_one({"url": url}, {"$set": {"sent_to_telegram": True}})

    def get_unsent_listings(self):
        return list(self.collection.find({"sent_to_telegram": {"$ne": True}}))

    def get_listing(self, url: str) -> Optional[Dict]:
        return self.collection.find_one({"url": url}) 