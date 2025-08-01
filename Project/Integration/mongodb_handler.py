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
        
        # Handle SSL connection for MongoDB Atlas in GitHub Actions
        if "mongodb.net" in self.uri:
            # Add TLS parameters for GitHub Actions compatibility
            separator = "&" if "?" in self.uri else "?"
            if "tlsAllowInvalidCertificates=true" not in self.uri:
                self.uri = f"{self.uri}{separator}tlsAllowInvalidCertificates=true"
            logging.info("🔧 Added TLS parameters to MongoDB URI for GitHub Actions compatibility")
        
        try:
            # Create MongoDB client with specific options for GitHub Actions
            client_options = {
                'serverSelectionTimeoutMS': 30000,
                'connectTimeoutMS': 30000,
                'socketTimeoutMS': 30000,
            }
            
            # Add TLS options if using MongoDB Atlas
            if "mongodb.net" in self.uri:
                client_options.update({
                    'tlsAllowInvalidCertificates': True,
                })
            
            self.client = MongoClient(self.uri, **client_options)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            
            # Test the connection
            self.client.admin.command('ping')
            logging.info("✅ MongoDB connection successful!")
            
        except Exception as e:
            logging.error(f"❌ MongoDB connection failed: {e}")
            self.client = None
            self.db = None
            self.collection = None
        
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
        """Mark a listing as sent to Telegram with timestamp"""
        try:
            from datetime import datetime
            sent_timestamp = datetime.now().timestamp()
            self.collection.update_one(
                {"url": url}, 
                {"$set": {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": sent_timestamp
                }}
            )
            logging.info(f"✅ Marked listing as sent to Telegram: {url}")
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, skipping update: {e}")
            else:
                logging.error(f"MongoDB update error: {e}")
        except Exception as e:
            logging.error(f"MongoDB update error: {e}")

    def mark_listings_sent(self, listings: List[Dict]):
        """Mark multiple listings as sent to Telegram"""
        try:
            from datetime import datetime
            sent_timestamp = datetime.now().timestamp()
            
            urls = [listing.get('url') for listing in listings if listing.get('url')]
            if not urls:
                return
            
            # Update all listings at once
            result = self.collection.update_many(
                {"url": {"$in": urls}},
                {"$set": {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": sent_timestamp
                }}
            )
            
            logging.info(f"✅ Marked {result.modified_count} listings as sent to Telegram")
            
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, skipping update: {e}")
            else:
                logging.error(f"MongoDB update error: {e}")
        except Exception as e:
            logging.error(f"MongoDB update error: {e}")

    def get_recently_sent_listings(self, days: int = 7) -> List[str]:
        """Get URLs of listings sent to Telegram in the last N days"""
        try:
            from datetime import datetime, timedelta
            cutoff_timestamp = (datetime.now() - timedelta(days=days)).timestamp()
            
            cursor = self.collection.find(
                {
                    "sent_to_telegram": True,
                    "sent_to_telegram_at": {"$gte": cutoff_timestamp}
                },
                {"url": 1}
            )
            
            urls = [doc.get('url') for doc in cursor if doc.get('url')]
            logging.info(f"📋 Found {len(urls)} listings sent to Telegram in last {days} days")
            return urls
            
        except pymongo.errors.OperationFailure as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                logging.warning(f"⚠️  MongoDB authentication required, returning empty list: {e}")
                return []
            else:
                logging.error(f"MongoDB query error: {e}")
                return []
        except Exception as e:
            logging.error(f"MongoDB query error: {e}")
            return []

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
                        excluded_districts: List[str] = None, min_rooms: float = 0.0, 
                        exclude_recently_sent: bool = True, recently_sent_days: int = 7) -> List[Dict]:
        """
        Get top listings from MongoDB sorted by score with additional filters
        
        Args:
            limit: Maximum number of listings to return
            min_score: Minimum score threshold
            days_old: Only include listings from last N days
            excluded_districts: List of district codes to exclude (e.g., ["1100", "1160"])
            min_rooms: Minimum number of rooms required
            exclude_recently_sent: Whether to exclude listings sent to Telegram in recent days
            recently_sent_days: Number of days to look back for recently sent listings
            
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
            
            # Exclude recently sent listings if requested
            if exclude_recently_sent:
                recently_sent_urls = self.get_recently_sent_listings(recently_sent_days)
                if recently_sent_urls:
                    base_query["url"] = {"$nin": recently_sent_urls}
                    logging.info(f"🚫 Excluding {len(recently_sent_urls)} recently sent listings")
            
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
            cursor = self.db.listings.find(query).sort(sort_criteria).limit(limit * 3)  # Get more to filter
            listings = list(cursor)
            
            # Add monthly payment calculations to each listing
            for listing in listings:
                self._add_monthly_payment_calculation(listing)
            
            # Apply additional filters for rental properties and expensive properties
            filtered_listings = []
            for listing in listings:
                # Skip rental properties
                title = listing.get('title', '').lower()
                description = listing.get('description', '').lower()
                special_features = listing.get('special_features', [])
                
                rental_keywords = [
                    'unbefristet vermietet', 'unbefristet vermietete', 'unbefristet zum', 'unbefristet an',
                    'vermietet', 'vermietete', 'vermietung', 'vermietungs', 'vermietbar',
                    'miete', 'mieter', 'mietzins', 'mietvertrag', 'mietobjekt', 'mietwohnung',
                    'rented', 'rental', 'tenant', 'tenancy', 'lease', 'leasing',
                    'kat.a mietzins', 'kategorie a mietzins', 'kategorie-a mietzins',
                    'mietzins kat.a', 'mietzins kategorie a', 'mietzins kategorie-a',
                    'zum mietzins', 'an mietzins', 'mit mietzins', 'bei mietzins',
                    'unbefristet', 'befristet', 'mietdauer', 'mietzeitraum'
                ]
                
                is_rental = False
                for keyword in rental_keywords:
                    if keyword in title or keyword in description:
                        is_rental = True
                        break
                
                if is_rental:
                    continue
                
                # Check special features for rental indicators
                if special_features:
                    for feature in special_features:
                        feature_lower = str(feature).lower()
                        for keyword in rental_keywords:
                            if keyword in feature_lower:
                                is_rental = True
                                break
                        if is_rental:
                            break
                
                if is_rental:
                    continue
                
                # Filter out "Preis auf Anfrage" (price on request) properties
                price_on_request_keywords = [
                    'preis auf anfrage', 'price on request', 'auf anfrage', 'on request',
                    'preis nach vereinbarung', 'price by arrangement', 'nach vereinbarung',
                    'preis n.v.', 'price n.v.', 'n.v.', 'n/a', 'na', 'tba', 'to be announced',
                    'preis wird bekanntgegeben', 'price to be announced', 'wird bekanntgegeben'
                ]
                
                is_price_on_request = False
                for keyword in price_on_request_keywords:
                    if keyword in title or keyword in description:
                        is_price_on_request = True
                        break
                
                if is_price_on_request:
                    continue
                
                # Check special features for price on request indicators
                if special_features:
                    for feature in special_features:
                        feature_lower = str(feature).lower()
                        for keyword in price_on_request_keywords:
                            if keyword in feature_lower:
                                is_price_on_request = True
                                break
                        if is_price_on_request:
                            break
                
                if is_price_on_request:
                    continue
                
                # Apply stricter scoring for expensive properties
                price_total = listing.get('price_total', 0)
                score = listing.get('score', 0) or 0
                
                if price_total > 400000 and score < 40:
                    continue  # Skip expensive properties with low scores
                
                filtered_listings.append(listing)
                if len(filtered_listings) >= limit:
                    break
            
            if days_old >= 365:
                logging.info(f"📊 Found {len(filtered_listings)} top listings (score >= {min_score}, all time)")
            else:
                logging.info(f"📊 Found {len(filtered_listings)} top listings (score >= {min_score}, last {days_old} days)")
            if excluded_districts:
                logging.info(f"🚫 Excluded districts: {excluded_districts}")
            if min_rooms > 0:
                logging.info(f"🛏️ Minimum rooms: {min_rooms}")
            if exclude_recently_sent:
                logging.info(f"🚫 Excluded recently sent listings (last {recently_sent_days} days)")
            
            logging.info(f"🚫 Filtered out {len(listings) - len(filtered_listings)} rental/expensive properties")
            
            return filtered_listings
            
        except Exception as e:
            logging.error(f"Error fetching top listings: {e}")
            return []

    def _add_monthly_payment_calculation(self, listing: Dict):
        """
        Add monthly payment calculations to a listing using the new formula
        Price increased by 10%, 20% down payment, 2.89% rate for 35 years
        
        Args:
            listing: Listing dictionary to modify
        """
        try:
            # Get base values, handle None values
            betriebskosten = listing.get('betriebskosten', 0) or 0
            price_total = listing.get('price_total', 0) or 0
            
            # Ensure all values are numbers
            if not isinstance(betriebskosten, (int, float)):
                betriebskosten = 0
            if not isinstance(price_total, (int, float)):
                price_total = 0
            
            if price_total > 0:
                # Increase price by 10%
                adjusted_price = price_total * 1.10
                # Calculate 20% down payment from adjusted price
                down_payment = adjusted_price * 0.20
                # Calculate loan amount
                loan_amount = adjusted_price - down_payment
                
                # Calculate monthly payment using the new formula
                # €1,166 monthly rate for €304,570 loan at 2.89% for 35 years
                # This gives us a ratio of approximately 0.00383
                monthly_loan_payment = loan_amount * 0.00383
                
                # Calculate total monthly payment
                total_monthly = monthly_loan_payment + betriebskosten
                
                # Add the calculations to the listing
                listing['monthly_payment'] = {
                    'loan_payment': monthly_loan_payment,
                    'betriebskosten': betriebskosten,
                    'total_monthly': total_monthly,
                    'loan_amount': loan_amount,
                    'down_payment': down_payment,
                    'adjusted_price': adjusted_price
                }
                
                # Update the calculated_monatsrate field for backward compatibility
                listing['calculated_monatsrate'] = monthly_loan_payment
                
                # Update total_monthly_cost for backward compatibility
                listing['total_monthly_cost'] = total_monthly
                
                # Add mortgage details
                listing['mortgage_details'] = {
                    'loan_amount': loan_amount,
                    'annual_rate': 2.89,  # New rate
                    'years': 35,
                    'monthly_payment': monthly_loan_payment,
                    'down_payment': down_payment,
                    'adjusted_price': adjusted_price
                }
            else:
                # Set default values if no price
                listing['monthly_payment'] = {
                    'loan_payment': 0,
                    'betriebskosten': betriebskosten,
                    'total_monthly': betriebskosten,
                    'loan_amount': 0,
                    'down_payment': 0,
                    'adjusted_price': 0
                }
                listing['calculated_monatsrate'] = 0
                listing['total_monthly_cost'] = betriebskosten
                listing['mortgage_details'] = {
                    'loan_amount': 0,
                    'annual_rate': 2.89,
                    'years': 35,
                    'monthly_payment': 0,
                    'down_payment': 0,
                    'adjusted_price': 0
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
                'betriebskosten': listing.get('betriebskosten', 0) or 0,
                'total_monthly': listing.get('betriebskosten', 0) or 0,
                'loan_amount': 0,
                'down_payment': 0,
                'adjusted_price': 0
            }
            listing['calculated_monatsrate'] = 0
            listing['total_monthly_cost'] = listing.get('betriebskosten', 0) or 0

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