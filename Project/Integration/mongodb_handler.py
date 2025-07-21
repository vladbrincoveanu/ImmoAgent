import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Dict, Any, Optional, List
import os
import json
from Application.helpers.utils import load_config
import logging

class MongoDBHandler:
    def __init__(self, uri: str = None, db_name: str = "immo", collection_name: str = "listings"):
        config = load_config()
        self.uri = uri or config.get("mongodb_uri") or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
        self.client = MongoClient(self.uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        
        # Try to create index, but don't fail if authentication is required
        try:
            self.collection.create_index("url", unique=True)
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, skipping index creation: {e}")
            else:
                print(f"⚠️  Could not create MongoDB index: {e}")
        except Exception as e:
            print(f"⚠️  MongoDB initialization warning: {e}")

    def close(self):
        """Close the MongoDB connection"""
        if hasattr(self, 'client') and self.client:
            self.client.close()

    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()

    def insert_listing(self, listing: Dict) -> bool:
        try:
            self.collection.insert_one(listing)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"MongoDB insert error: command insert requires authentication, full error: {e}")
            else:
                print(f"MongoDB insert error: {e}")
            return False
        except Exception as e:
            print(f"MongoDB insert error: {e}")
            return False

    def listing_exists(self, url: str) -> bool:
        try:
            return self.collection.find_one({"url": url}) is not None
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"MongoDB query error: command find requires authentication, full error: {e}")
            else:
                print(f"MongoDB query error: {e}")
            return False
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return False

    def mark_sent(self, url: str):
        try:
            self.collection.update_one({"url": url}, {"$set": {"sent_to_telegram": True}})
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, skipping update: {e}")
            else:
                print(f"MongoDB update error: {e}")
        except Exception as e:
            print(f"MongoDB update error: {e}")

    def get_unsent_listings(self):
        try:
            return list(self.collection.find({"sent_to_telegram": {"$ne": True}}))
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, returning empty list: {e}")
                return []
            else:
                print(f"MongoDB query error: {e}")
                return []
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return []

    def get_listing(self, url: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({"url": url})
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print(f"⚠️  MongoDB authentication required, returning None: {e}")
                return None
            else:
                print(f"MongoDB query error: {e}")
                return None
        except Exception as e:
            print(f"MongoDB query error: {e}")
            return None
    
    def get_top_listings(self, limit: int = 5, min_score: float = 0.0, days_old: int = 30, 
                        excluded_districts: List[str] = None, min_rooms: float = 0.0) -> List[Dict]:
        """
        Get top listings from MongoDB sorted by score with additional filters
        
        Args:
            limit: Maximum number of listings to return
            min_score: Minimum score threshold
            days_old: Only include listings from last N days
            excluded_districts: List of district codes to exclude (e.g., ["1100", "1160"])
            min_rooms: Minimum number of rooms required
            
        Returns:
            List of listing dictionaries sorted by score (highest first)
        """
        try:
            if not self.client:
                logging.error("MongoDB client not connected")
                return []
            
            # Calculate cutoff date
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cutoff_timestamp = cutoff_date.timestamp()
            
            # Build base query
            base_query = {
                "processed_at": {"$gte": cutoff_timestamp}
            }
            
            # Add score filter if specified
            if min_score > 0:
                base_query["score"] = {"$gte": min_score}
            
            # Add district exclusion filter
            if excluded_districts and len(excluded_districts) > 0:
                base_query["bezirk"] = {"$nin": excluded_districts}
            
            # Build final query with room filter handling
            if min_rooms > 0:
                # Handle None values - include properties with None rooms OR rooms >= min_rooms
                query = {
                    "$and": [
                        base_query,
                        {
                            "$or": [
                                {"rooms": {"$gte": min_rooms}},
                                {"rooms": None}
                            ]
                        }
                    ]
                }
            else:
                query = base_query
            
            # Sort by score descending, then by processed_at descending
            sort_criteria = [
                ("score", -1),  # Highest score first
                ("processed_at", -1)  # Most recent first for same scores
            ]
            
            # Execute query
            cursor = self.db.listings.find(query).sort(sort_criteria).limit(limit)
            listings = list(cursor)
            
            # Add monthly payment calculations to each listing
            for listing in listings:
                self._add_monthly_payment_calculation(listing)
            
            logging.info(f"📊 Found {len(listings)} top listings (score >= {min_score}, last {days_old} days)")
            if excluded_districts:
                logging.info(f"🚫 Excluded districts: {excluded_districts}")
            if min_rooms > 0:
                logging.info(f"🛏️ Minimum rooms: {min_rooms}")
            
            return listings
            
        except Exception as e:
            logging.error(f"Error fetching top listings: {e}")
            return []

    def _add_monthly_payment_calculation(self, listing: Dict):
        """
        Add monthly payment calculations to a listing and fix score if needed
        
        Args:
            listing: Listing dictionary to modify
        """
        try:
            # Get loan payment and Betriebskosten, handle None values
            loan_payment = listing.get('calculated_monatsrate', 0) or 0
            betriebskosten = listing.get('betriebskosten', 0) or 0
            
            # Ensure both values are numbers
            if not isinstance(loan_payment, (int, float)):
                loan_payment = 0
            if not isinstance(betriebskosten, (int, float)):
                betriebskosten = 0
            
            # Calculate total monthly payment
            total_monthly = loan_payment + betriebskosten
            
            # Add the calculations to the listing
            listing['monthly_payment'] = {
                'loan_payment': loan_payment,
                'betriebskosten': betriebskosten,
                'total_monthly': total_monthly
            }
            
            # Fix score calculation: multiply by 100 if below 0
            score = listing.get('score', 0)
            if score is not None and score < 0:
                listing['score'] = score * 100
                logging.info(f"Fixed score from {score} to {listing['score']}")
            
        except Exception as e:
            logging.error(f"Error calculating monthly payment for listing: {e}")
            # Set default values if calculation fails
            listing['monthly_payment'] = {
                'loan_payment': 0,
                'betriebskosten': 0,
                'total_monthly': 0
            }

    @staticmethod
    def save_listings_to_mongodb(listings: list) -> int:
        """
        Save multiple listings to MongoDB
        Returns the number of successfully saved listings
        """
        try:
            handler = MongoDBHandler()
            saved_count = 0
            
            for listing in listings:
                # Convert Listing object to dict if needed
                if hasattr(listing, '__dict__'):
                    listing_dict = listing.__dict__
                else:
                    listing_dict = listing
                
                if handler.insert_listing(listing_dict):
                    saved_count += 1
            
            handler.close()
            return saved_count
            
        except Exception as e:
            print(f"Error saving listings to MongoDB: {e}")
            return 0 