import json
import os
import time
import requests
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

from Application.scraping.willhaben_scraper import WillhabenScraper
from Application.scraping.immo_kurier_scraper import ImmoKurierScraper
from Application.scraping.derstandard_scraper import DerStandardScraper
from Application.analyzer import StructuredAnalyzer
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot
from Application.helpers.utils import format_currency, format_walking_time, ViennaDistrictHelper, load_config, get_walking_times
from Application.helpers.listing_validator import filter_valid_listings, get_validation_stats
from Domain.listing import Listing
import logging
from bson import ObjectId
import pymongo

# Try to import PIL for image optimization
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Ensure log directory exists
log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/immo-scouter.log'),
        logging.StreamHandler()
    ]
)

def json_serializable(obj):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    try:
        if isinstance(obj, ObjectId):
            return str(obj)
    except ImportError:
        pass  # bson not available, skip ObjectId conversion
    
    if isinstance(obj, dict):
        return {key: json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(item) for item in obj]
    else:
        return obj

def test_system_components(config):
    """Test all system components before running main job"""
    logging.info("🧪 Testing system components...")
    
    # Test MongoDB connection
    try:
        mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
        test_doc = {"test": "connection", "timestamp": time.time()}
        mongo.collection.insert_one(test_doc)
        found = mongo.collection.find_one({"test": "connection"})
        mongo.collection.delete_one({"test": "connection"})
        if found:
            logging.info("✅ MongoDB connection successful!")
            mongo_ok = True
        else:
            logging.error("❌ MongoDB test document not found!")
            mongo_ok = False
    except Exception as e:
        logging.error(f"❌ MongoDB connection failed: {e}")
        mongo_ok = False
    
    # Test Structured Analyzer
    try:
        analyzer = StructuredAnalyzer(
            api_key=config.get('openai_api_key'),
            model=config.get('openai_model', 'gpt-4o-mini')
        )
        analyzer_ok = analyzer.is_available()
        if analyzer_ok:
            logging.info("✅ Structured Analyzer available!")
        else:
            logging.warning("⚠️  Structured Analyzer not available - will use fallback")
    except Exception as e:
        logging.error(f"❌ Structured Analyzer error: {e}")
        analyzer_ok = False
    
    # Test Telegram Bots
    telegram_ok = False
    telegram_config = config.get('telegram', {})
    
    # Test main Telegram bot
    if os.getenv('TELEGRAM_MAIN_BOT_TOKEN') and os.getenv('TELEGRAM_MAIN_CHAT_ID'):
        bot_token = os.getenv('TELEGRAM_MAIN_BOT_TOKEN')
        bot_chat_id = os.getenv('TELEGRAM_MAIN_CHAT_ID')
        bot = TelegramBot(bot_token, bot_chat_id)
        telegram_ok = bot.test_connection()
    elif telegram_config.get('telegram_main', {}).get('bot_token') and telegram_config.get('telegram_main', {}).get('chat_id'):
        try:
            main_config = telegram_config['telegram_main']
            bot = TelegramBot(main_config['bot_token'], main_config['chat_id'])
            telegram_ok = bot.test_connection()
            if telegram_ok:
                logging.info("✅ Telegram main bot connection successful!")
            else:
                logging.warning("⚠️  Telegram main bot connection failed")
        except Exception as e:
            logging.error(f"❌ Telegram main bot error: {e}")
    else:
        logging.warning("⚠️  Telegram main bot not configured")
    
    # Test dev Telegram bot
    if os.getenv('TELEGRAM_DEV_BOT_TOKEN') and os.getenv('TELEGRAM_DEV_CHAT_ID'):
        bot_token = os.getenv('TELEGRAM_DEV_BOT_TOKEN')
        bot_chat_id = os.getenv('TELEGRAM_DEV_CHAT_ID')
        dev_bot = TelegramBot(bot_token, bot_chat_id)
        dev_ok = dev_bot.test_connection()
    elif telegram_config.get('telegram_dev', {}).get('bot_token') and telegram_config.get('telegram_dev', {}).get('chat_id'):
        try:
            dev_config = telegram_config['telegram_dev']
            dev_bot = TelegramBot(dev_config['bot_token'], dev_config['chat_id'])
            dev_ok = dev_bot.test_connection()
            if dev_ok:
                logging.info("✅ Telegram dev bot connection successful!")
            else:
                logging.warning("⚠️  Telegram dev bot connection failed")
        except Exception as e:
            logging.error(f"❌ Telegram dev bot error: {e}")
    else:
        logging.warning("⚠️  Telegram dev bot not configured")
    
    return {
        'mongodb': mongo_ok,
        'analyzer': analyzer_ok,
        'telegram': telegram_ok
    }

def download_images_for_listings(mongo_uri: str = "mongodb://localhost:27017/", db_name: str = "immo", collection_name: str = "listings"):
    """Download images for listings that have image_url but no minio_image_path"""
    logging.info("📸 Starting image download process...")
    
    # MongoDB connection
    client = pymongo.MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    
    # Initialize MinIO handler
    try:
        from integration.minio_handler import MinIOHandler
        minio_handler = MinIOHandler()
        logging.info("✅ MinIO handler initialized")
    except Exception as e:
        logging.error(f"❌ Failed to initialize MinIO handler: {e}")
        return 0
    
    # Find listings with image_url but no minio_image_path
    listings_with_images = collection.find({
        "image_url": {"$exists": True, "$ne": None},
        "$or": [
            {"minio_image_path": {"$exists": False}},
            {"minio_image_path": None}
        ]
    })
    
    downloaded_count = 0
    error_count = 0
    
    for doc in listings_with_images:
        image_url = doc["image_url"]
        property_id = str(doc["_id"])
        
        # Skip if already uploaded to MinIO
        if doc.get("minio_image_path"):
            continue
        
        try:
            logging.info(f"📥 Downloading and uploading {image_url} to MinIO")
            
            # Upload image to MinIO
            object_name = minio_handler.upload_image_from_url(image_url, f"{property_id}.jpg")
            
            if object_name:
                # Save MinIO path in MongoDB
                collection.update_one({"_id": doc["_id"]}, {"$set": {"minio_image_path": object_name}})
                downloaded_count += 1
                logging.info(f"✅ Uploaded to MinIO: {object_name}")
            else:
                error_count += 1
                logging.error(f"❌ Failed to upload {image_url} to MinIO")
            
        except Exception as e:
            error_count += 1
            logging.error(f"❌ Failed to process {image_url}: {e}")
            continue
    
    client.close()
    
    logging.info(f"📸 Image download complete: {downloaded_count} uploaded to MinIO, {error_count} errors")
    return downloaded_count

def optimize_images(max_size: tuple = (800, 600), quality: int = 85):
    """Optimize all images in MinIO"""
    if not PIL_AVAILABLE:
        logging.warning("⚠️ PIL/Pillow not available. Install with: pip install Pillow")
        return 0
    
    try:
        from integration.minio_handler import MinIOHandler
        minio_handler = MinIOHandler()
        logging.info("✅ MinIO handler initialized for optimization")
    except Exception as e:
        logging.error(f"❌ Failed to initialize MinIO handler: {e}")
        return 0
    
    # List all images in MinIO
    image_objects = minio_handler.list_images()
    
    if not image_objects:
        logging.info("📭 No images found in MinIO to optimize")
        return 0
    
    logging.info(f"🔧 Optimizing {len(image_objects)} images in MinIO...")
    
    optimized_count = 0
    total_savings = 0
    
    for object_name in image_objects:
        try:
            # Download image from MinIO
            temp_path = f"/tmp/{object_name}"
            if minio_handler.download_image(object_name, temp_path):
                with Image.open(temp_path) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Resize if larger than max_size
                    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    # Get original file size
                    original_size = os.path.getsize(temp_path)
                    
                    # Save optimized image
                    img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                    
                    # Get optimized file size
                    optimized_size = os.path.getsize(temp_path)
                    savings = ((original_size - optimized_size) / original_size) * 100
                    total_savings += savings
                    
                    # Upload optimized image back to MinIO
                    if minio_handler.upload_image_from_file(temp_path, object_name):
                        logging.info(f"✅ {object_name}: {original_size/1024:.1f}KB → {optimized_size/1024:.1f}KB ({savings:.1f}% smaller)")
                        optimized_count += 1
                    
                    # Clean up temp file
                    os.remove(temp_path)
                
        except Exception as e:
            logging.error(f"❌ Error optimizing {object_name}: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    if optimized_count > 0:
        avg_savings = total_savings / optimized_count
        logging.info(f"🔧 Optimization complete: {optimized_count}/{len(image_objects)} images optimized (avg {avg_savings:.1f}% smaller)")
    
    return optimized_count

def print_listing_summary(listing):
    """Print a formatted summary of a listing"""
    source = listing.get('source', 'Unknown')
    if hasattr(source, 'value'):
        source = source.value

    district = listing.get('bezirk', 'Unknown')
    district_name = ViennaDistrictHelper.get_district_name(district)
    price = format_currency(listing.get('price_total'))
    area = listing.get('area_m2', 'N/A')
    price_per_m2 = format_currency(listing.get('price_per_m2'))
    
    # Handle walking times with proper None handling
    ubahn_minutes = listing.get('ubahn_walk_minutes')
    school_minutes = listing.get('school_walk_minutes')
    ubahn_time = f"{ubahn_minutes} min" if ubahn_minutes is not None else 'N/A'
    school_time = f"{school_minutes} min" if school_minutes is not None else 'N/A'
    
    year_built = listing.get('year_built', 'N/A')
    condition = listing.get('condition', 'N/A')
    energy_class = listing.get('energy_class', 'N/A')
    
    print(f"\n🏠 [{source}] {district} ({district_name}) - {price}")
    print(f"   📍 {listing.get('address', 'N/A')}")
    print(f"   📐 {area}m² - {price_per_m2}/m²")
    print(f"   🚇 U-Bahn: {ubahn_time}")
    print(f"   🏫 School: {school_time}")
    print(f"   🏗️  Built: {year_built}")
    print(f"   🛠️  Condition: {condition}")
    print(f"   ⚡ Energy: {energy_class}")
    print(f"   🔗 {listing['url']}")

def deep_cleanup_database(mongo_handler: MongoDBHandler) -> Dict[str, int]:
    """One-time comprehensive cleanup: removes invalid data, broken URLs, very old listings, and recalculates scores."""
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0, "old_removed": 0, "scores_calculated": 0}
    
    logging.info("🧹 Running DEEP CLEANUP (comprehensive database cleanup)...")
    
    stats = {
        "invalid_data": 0,
        "broken_urls": 0,
        "old_removed": 0,
        "scores_calculated": 0
    }
    
    # Step 1: Remove listings with invalid data
    invalid_query = {
        "$or": [
            {"url": {"$exists": False}},
            {"url": None},
            {"url": ""},
            {"price_total": {"$exists": False}},
            {"price_total": None},
            {"price_total": {"$lte": 0}},
            {"area_m2": {"$exists": False}},
            {"area_m2": None},
            {"area_m2": {"$lte": 0}}
        ]
    }
    invalid_result = mongo_handler.collection.delete_many(invalid_query)
    stats["invalid_data"] = invalid_result.deleted_count
    if stats["invalid_data"] > 0:
        logging.info(f"   ✅ Removed {stats['invalid_data']} listings with invalid data")
    
    # Step 2: Check and remove broken derstandard URLs
    derstandard_listings = list(mongo_handler.collection.find(
        {"source": "derstandard"},
        {"url": 1, "_id": 1}
    ))
    
    if derstandard_listings:
        logging.info(f"   🔍 Checking {len(derstandard_listings)} derstandard URLs for broken links...")
        broken_count = 0
        for listing in derstandard_listings:
            url = listing.get("url")
            if not url:
                continue
            
            try:
                resp = requests.head(url, allow_redirects=True, timeout=3)
                if resp.status_code >= 400:
                    mongo_handler.collection.delete_one({"_id": listing["_id"]})
                    broken_count += 1
            except Exception:
                mongo_handler.collection.delete_one({"_id": listing["_id"]})
                broken_count += 1
        
        stats["broken_urls"] = broken_count
        if broken_count > 0:
            logging.info(f"   ✅ Removed {broken_count} broken derstandard URLs")
    
    # Step 3: Remove very old listings (older than 365 days)
    cutoff_ts = time.time() - (365 * 86400)
    old_result = mongo_handler.collection.delete_many({"processed_at": {"$lt": cutoff_ts}})
    stats["old_removed"] = old_result.deleted_count
    if stats["old_removed"] > 0:
        logging.info(f"   ✅ Removed {stats['old_removed']} listings older than 365 days")
    
    # Step 4: Recalculate all missing scores
    missing_scores_query = {
        "$or": [
            {"score": {"$exists": False}},
            {"score": None}
        ]
    }
    listings_without_scores = list(mongo_handler.collection.find(missing_scores_query))
    
    if listings_without_scores:
        from Application.scoring import score_apartment_simple
        from collections import Counter
        source_counts = Counter(l.get('source', 'unknown') for l in listings_without_scores)
        logging.info(f"   🔍 Recalculating scores for {len(listings_without_scores)} listings without scores")
        logging.info(f"      By source: {dict(source_counts)}")
        
        success_count = 0
        for listing in listings_without_scores:
            try:
                score = score_apartment_simple(listing)
                mongo_handler.collection.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"score": score}}
                )
                success_count += 1
            except Exception as e:
                logging.debug(f"      ⚠️ Failed to calculate score: {e}")
        
        stats["scores_calculated"] = success_count
        if success_count > 0:
            logging.info(f"   ✅ Calculated {success_count} missing scores")
    
    total_removed = stats["invalid_data"] + stats["broken_urls"] + stats["old_removed"]
    logging.info(f"🧹 Deep cleanup complete: removed {total_removed} listings, calculated {stats['scores_calculated']} scores")
    
    return {
        "checked": len(derstandard_listings) + len(listings_without_scores),
        "removed": total_removed,
        "invalid_data": stats["invalid_data"],
        "broken_urls": stats["broken_urls"],
        "old_removed": stats["old_removed"],
        "scores_calculated": stats["scores_calculated"]
    }

def comprehensive_cleanup_all_listings(mongo_handler: MongoDBHandler, max_age_days: int = 180, verify_urls: bool = True, batch_size: int = 100) -> Dict[str, int]:
    """
    Comprehensive cleanup that checks ALL listings for broken URLs and invalid data.
    This is more thorough than regular cleanup and should be run periodically.
    
    Args:
        mongo_handler: MongoDB handler instance
        max_age_days: Remove listings older than this (default: 180 days)
        verify_urls: Actually check if URLs are accessible (slower but thorough)
        batch_size: Process listings in batches to avoid memory issues
    
    Returns:
        Dictionary with cleanup statistics
    """
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0, "old_removed": 0}
    
    logging.info("🧹 Running COMPREHENSIVE cleanup (checking ALL listings for broken URLs)...")
    
    stats = {
        "checked": 0,
        "removed": 0,
        "invalid_data": 0,
        "broken_urls": 0,
        "old_removed": 0
    }
    
    # Step 1: Remove listings with invalid data (fast, no URL checking needed)
    invalid_query = {
        "$or": [
            {"url": {"$exists": False}},
            {"url": None},
            {"url": ""},
            {"price_total": {"$exists": False}},
            {"price_total": None},
            {"price_total": {"$lte": 0}},
            {"area_m2": {"$exists": False}},
            {"area_m2": None},
            {"area_m2": {"$lte": 0}}
        ]
    }
    invalid_result = mongo_handler.collection.delete_many(invalid_query)
    stats["invalid_data"] = invalid_result.deleted_count
    if stats["invalid_data"] > 0:
        logging.info(f"   ✅ Removed {stats['invalid_data']} listings with invalid data")
    
    # Step 2: Remove very old listings (older than max_age_days)
    cutoff_ts = time.time() - (max_age_days * 86400)
    old_result = mongo_handler.collection.delete_many({"processed_at": {"$lt": cutoff_ts}})
    stats["old_removed"] = old_result.deleted_count
    if stats["old_removed"] > 0:
        logging.info(f"   ✅ Removed {stats['old_removed']} listings older than {max_age_days} days")
    
    # Step 3: Check ALL remaining listings for broken URLs (if verify_urls is enabled)
    if verify_urls:
        # Get all listings with valid URLs (exclude None and empty strings)
        all_listings = list(mongo_handler.collection.find(
            {
                "$and": [
                    {"url": {"$exists": True}},
                    {"url": {"$ne": None}},
                    {"url": {"$ne": ""}}
                ]
            },
            {"url": 1, "_id": 1, "source": 1}
        ))
        
        total_listings = len(all_listings)
        if total_listings > 0:
            logging.info(f"   🔍 Checking {total_listings} listings for broken URLs...")
            
            broken_count = 0
            checked = 0
            
            # Process in batches to show progress
            for i in range(0, total_listings, batch_size):
                batch = all_listings[i:i + batch_size]
                for listing in batch:
                    url = listing.get("url")
                    if not url:
                        continue
                    
                    checked += 1
                    url_invalid = False
                    
                    try:
                        resp = requests.head(url, allow_redirects=True, timeout=5)
                        # Only accept 200 OK status codes
                        if resp.status_code != 200:
                            url_invalid = True
                            logging.debug(f"💀 Broken URL (HTTP {resp.status_code}): {url}")
                    except Exception as e:
                        url_invalid = True
                        logging.debug(f"💀 Unreachable URL ({type(e).__name__}): {url}")
                    
                    if url_invalid:
                        try:
                            mongo_handler.collection.delete_one({"_id": listing["_id"]})
                            broken_count += 1
                        except Exception as exc:
                            logging.warning(f"⚠️ Failed to delete listing {listing.get('_id')}: {exc}")
                
                # Log progress for large batches
                if total_listings > batch_size:
                    progress = min(100, int((checked / total_listings) * 100))
                    logging.info(f"   🔍 Progress: {checked}/{total_listings} checked ({progress}%)...")
            
            stats["broken_urls"] = broken_count
            stats["checked"] = checked
            if broken_count > 0:
                logging.info(f"   ✅ Removed {broken_count} listings with broken URLs")
            else:
                logging.info(f"   ✅ All {checked} URLs are valid")
    
    stats["removed"] = stats["invalid_data"] + stats["broken_urls"] + stats["old_removed"]
    
    if stats["removed"] > 0:
        logging.info(f"🧹 Comprehensive cleanup complete: checked {stats['checked']} URLs, removed {stats['removed']} listings (invalid: {stats['invalid_data']}, broken URLs: {stats['broken_urls']}, old: {stats['old_removed']})")
    else:
        logging.info(f"🧹 Comprehensive cleanup complete: checked {stats['checked']} URLs, no listings removed")
    
    return stats

def clean_stale_or_broken_listings(mongo_handler: MongoDBHandler, max_age_days: int = 180, batch_limit: int = None, verify_urls: bool = True, aggressive: bool = False) -> Dict[str, int]:
    """Prune obviously broken/stale listings to avoid serving dead links.
    
    Args:
        mongo_handler: MongoDB handler instance
        max_age_days: Remove listings older than this (default: 180 days)
        batch_limit: Limit number of listings to check (None = check all)
        verify_urls: Actually check if URLs are accessible (slower but thorough)
        aggressive: If True, check ALL listings regardless of age, focusing on derstandard URLs
    """
    if mongo_handler is None or mongo_handler.collection is None:
        return {"checked": 0, "removed": 0, "invalid_data": 0, "broken_urls": 0}

    # Build query based on cleanup mode
    if aggressive:
        # Aggressive mode: check derstandard listings (they tend to expire quickly)
        query = {"source": "derstandard"}
        logging.info("🧹 Running AGGRESSIVE cleanup on derstandard listings...")
    else:
        # Normal mode: check old listings
        cutoff_ts = time.time() - (max_age_days * 86400)
        query = {"processed_at": {"$lt": cutoff_ts}}
        logging.info(f"🧹 Running cleanup on listings older than {max_age_days} days...")
    
    # Apply batch limit if specified
    cursor = mongo_handler.collection.find(query, {"url": 1, "price_total": 1, "area_m2": 1, "source": 1})
    if batch_limit:
        cursor = cursor.limit(batch_limit)
    
    candidates = list(cursor)
    removed = 0
    invalid_data = 0
    broken_urls = 0

    for doc in candidates:
        doc_id = doc.get("_id")
        url = doc.get("url")
        price_total = doc.get("price_total")
        area_m2 = doc.get("area_m2")
        source = doc.get("source")

        if not doc_id:
            continue

        # Basic data sanity
        data_invalid = (not url) or (not isinstance(price_total, (int, float)) or price_total <= 0) or (not isinstance(area_m2, (int, float)) or area_m2 <= 0)

        url_invalid = False
        if verify_urls and url:
            try:
                resp = requests.head(url, allow_redirects=True, timeout=3)
                url_invalid = resp.status_code >= 400
                if url_invalid:
                    logging.debug(f"💀 Broken URL (HTTP {resp.status_code}): {url}")
            except Exception as e:
                url_invalid = True
                logging.debug(f"💀 Unreachable URL ({type(e).__name__}): {url}")

        if data_invalid or url_invalid:
            try:
                mongo_handler.collection.delete_one({"_id": doc_id})
                removed += 1
                if data_invalid:
                    invalid_data += 1
                if url_invalid:
                    broken_urls += 1
            except Exception as exc:
                logging.warning(f"⚠️ Failed to delete listing {doc_id}: {exc}")

    if candidates:
        logging.info(f"🧹 Cleanup complete: checked {len(candidates)} listings, removed {removed} (invalid data: {invalid_data}, broken URLs: {broken_urls})")
    else:
        logging.info("🧹 No listings found matching cleanup criteria")
    
    return {"checked": len(candidates), "removed": removed, "invalid_data": invalid_data, "broken_urls": broken_urls}

def scrape_willhaben(config: Dict, max_pages: int) -> Tuple[List[Listing], str]:
    """Scrape Willhaben listings"""
    try:
        logging.info("🔍 Starting Willhaben scraping...")
        scraper = WillhabenScraper(config=config)
        
        # Get max_pages from config or use default
        willhaben_config = config.get('willhaben', {})
        max_pages = willhaben_config.get('max_pages', max_pages)
        
        alert_url = config.get('alert_url', "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
        listings = scraper.scrape_search_agent_page(alert_url, max_pages=max_pages)
        logging.info(f"✅ Willhaben scraping complete: {len(listings)} matching listings found")
        return listings, "willhaben"
    except Exception as e:
        logging.error(f"❌ Willhaben scraping failed: {e}")
        return [], "willhaben"

def scrape_immo_kurier(config: Dict, max_pages: int) -> Tuple[List[Listing], str]:
    """Scrape Immo Kurier listings"""
    try:
        logging.info("🔍 Starting Immo Kurier scraping...")
        scraper = ImmoKurierScraper(config=config)
        immo_kurier_config = config.get('immo_kurier', {})
        
        # Get max_pages from config or use default
        max_pages = immo_kurier_config.get('max_pages', max_pages)
        search_url = immo_kurier_config.get('search_url', "https://immo.kurier.at/suche?l=Wien&r=0km&_multiselect_r=0km&a=at.wien&t=all%3Asale%3Aliving&pf=&pt=&rf=&rt=&sf=&st=")
        
        listings = scraper.scrape_search_results(search_url, max_pages=max_pages)
        logging.info(f"✅ Immo Kurier scraping complete: {len(listings)} matching listings found")
        return listings, "immo_kurier"
    except Exception as e:
        logging.error(f"❌ Immo Kurier scraping failed: {e}")
        return [], "immo_kurier"

def scrape_derstandard(config: Dict, max_pages: int) -> Tuple[List[Listing], str]:
    """Scrape derStandard listings"""
    logging.info("🔍 Starting derStandard scraping...")
    try:
        scraper = DerStandardScraper(config=config, use_selenium=True)
        
        # Get max_pages from config or use default
        derstandard_config = config.get('derstandard', {})
        max_pages = derstandard_config.get('max_pages', max_pages)
        search_url = derstandard_config.get('search_url', scraper.search_url)
        
        listings = scraper.scrape_search_results(search_url, max_pages=max_pages)
        logging.info(f"✅ derStandard: {len(listings)} listings found")
        return listings, "derstandard"
    except Exception as e:
        logging.error(f"❌ derStandard scraping failed: {e}")
        return [], "derstandard"

def normalize_listing_schema(listing: Listing) -> Listing:
    """Ensure the listing has all required fields and unified schema for MongoDB/Telegram/UI."""
    # Calculate price per m² if both price and area are available
    if listing.price_total and listing.area_m2 and not listing.price_per_m2:
        listing.price_per_m2 = listing.price_total / listing.area_m2
    
    # Set walking times if bezirk is present and not already set
    if listing.bezirk and (not listing.ubahn_walk_minutes or not listing.school_walk_minutes):
        ubahn, school = get_walking_times(listing.bezirk)
        if not listing.ubahn_walk_minutes:
            listing.ubahn_walk_minutes = ubahn
        if not listing.school_walk_minutes:
            listing.school_walk_minutes = school
    
    return listing

def save_listings_to_mongodb(listings: List[Listing], mongo_uri: str = "mongodb://localhost:27017/", 
                           db_name: str = "immo", collection_name: str = "listings") -> int:
    """Save listings to MongoDB with deduplication"""
    if not listings:
        return 0
    
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        
        saved_count = 0
        duplicate_count = 0
        
        for listing in listings:
            listing = normalize_listing_schema(listing)
            listing_dict = asdict(listing)
            
            existing = collection.find_one({"url": listing.url})
            
            if existing:
                listing_dict['_id'] = existing['_id']
                collection.replace_one({"_id": existing['_id']}, listing_dict)
                duplicate_count += 1
                logging.debug(f"🔄 Updated existing listing: {listing.title}")
            else:
                result = collection.insert_one(listing_dict)
                listing_dict['_id'] = result.inserted_id
                saved_count += 1
                logging.debug(f"💾 Saved new listing: {listing.title}")
        
        client.close()
        
        logging.info(f"💾 MongoDB save complete: {saved_count} new, {duplicate_count} updated")
        return saved_count
        
    except Exception as e:
        logging.error(f"❌ Error saving to MongoDB: {e}")
        return 0

def main():
    """Main function to run the integrated property scraper"""
    logging.info("🚀 Starting Integrated Immo-Scouter Main Job")
    logging.info("=" * 60)
    
    config = load_config()
    if not config:
        logging.error("❌ Cannot proceed without configuration")
        return
    
    # Simplified Telegram error logging setup
    telegram_config = config.get('telegram', {})
    dev_config = telegram_config.get('telegram_dev', {})
    bot_token = os.getenv('TELEGRAM_DEV_BOT_TOKEN') or dev_config.get('bot_token')
    bot_chat_id = os.getenv('TELEGRAM_DEV_CHAT_ID') or dev_config.get('chat_id')

    # Test system components
    component_status = test_system_components(config)
    
    # Setup Telegram error logging if configured
    if bot_token and bot_chat_id:
        from Integration.telegram_bot import TelegramBot
        bot = TelegramBot(bot_token, bot_chat_id)
        handler = bot.setup_error_logging(is_dev_channel=True)
        try:
            if handler:
                logging.getLogger().addHandler(handler)
                logging.info("✅ Telegram error logging configured")
        except Exception as e:
            logging.warning(f"⚠️ Failed to setup Telegram error logging: {e}")
    else:
        logging.info("ℹ️ Telegram not configured, skipping error logging setup")
    
    # Check MongoDB status
    if not component_status['mongodb']:
        logging.error("❌ MongoDB is required but not working. Please fix the connection.")
        return
    
    # Initialize MongoDB handler
    mongo = MongoDBHandler(uri=config.get('mongodb_uri'))
    
    import sys
    skip_images = "--skip-images" in sys.argv
    willhaben_only = "--willhaben-only" in sys.argv
    immo_kurier_only = "--immo-kurier-only" in sys.argv
    derstandard_only = "--derstandard-only" in sys.argv
    send_to_telegram = "--send-to-telegram" in sys.argv
    deep_scan = "--deep-scan" in sys.argv
    quick_scan = "--quick-scan" in sys.argv
    run_cleanup = "--cleanup" in sys.argv
    
    # Parse buyer profile from command line arguments
    buyer_profile = "owner_occupier"  # Default to Owner Occupier profile
    for i, arg in enumerate(sys.argv):
        if arg == "--buyer-profile" and i + 1 < len(sys.argv):
            buyer_profile = sys.argv[i + 1]
        elif arg.startswith("--buyer-profile="):
            buyer_profile = arg.split("=", 1)[1]
    
    # Set the buyer profile for scoring
    from Application.scoring import set_buyer_profile
    set_buyer_profile(buyer_profile)

    # Clean up stale/broken listings before scraping to avoid dead links.
    # Comprehensive cleanup (HTTP HEAD against every listing) is expensive — only run
    # when explicitly requested via --cleanup, or automatically on the first run of the
    # day (before 7 AM UTC, i.e. the morning scrape window).
    cleanup_config = config.get('cleanup', {})
    cleanup_enabled = cleanup_config.get('enabled', True)
    hour_utc = datetime.utcnow().hour
    should_cleanup = run_cleanup or hour_utc < 7
    if cleanup_enabled and should_cleanup:
        # Run comprehensive cleanup first (checks ALL listings for broken URLs)
        comprehensive_cleanup = cleanup_config.get('comprehensive_cleanup', True)
        if comprehensive_cleanup:
            max_age_days = cleanup_config.get('max_age_days', 180)
            verify_urls = cleanup_config.get('verify_urls', True)
            batch_size = cleanup_config.get('cleanup_batch_size', 100)
            comprehensive_cleanup_all_listings(mongo, max_age_days=max_age_days, verify_urls=verify_urls, batch_size=batch_size)

        # Then run deep cleanup (removes invalid data, recalculates scores)
        deep_cleanup = cleanup_config.get('deep_cleanup', True)
        if deep_cleanup:
            deep_cleanup_database(mongo)

        # Finally run regular cleanup (ongoing maintenance for specific sources)
        batch_limit = cleanup_config.get('batch_limit', None)  # None = check all
        aggressive = cleanup_config.get('aggressive', True)
        clean_stale_or_broken_listings(mongo, max_age_days=max_age_days, batch_limit=batch_limit, verify_urls=False, aggressive=aggressive)
    elif cleanup_enabled:
        logging.info("⏭️ Skipping comprehensive cleanup (not the morning run; pass --cleanup to force)")

    # CLI override for crawl depth
    cli_max_pages = None
    for i, arg in enumerate(sys.argv):
        if arg in ("--max-pages", "--max_pages") and i + 1 < len(sys.argv):
            try:
                cli_max_pages = int(sys.argv[i + 1])
            except ValueError:
                logging.warning(f"⚠️ Invalid --max-pages value: {sys.argv[i + 1]}")
        elif arg.startswith("--max-pages="):
            try:
                cli_max_pages = int(arg.split("=", 1)[1])
            except ValueError:
                logging.warning(f"⚠️ Invalid --max-pages value: {arg}")

    max_pages = cli_max_pages or config.get('max_pages', 10)

    scan_depth_config = config.get('scan_depth', {})
    if quick_scan:
        quick_pages = scan_depth_config.get('quick_max_pages', max(2, max_pages // 2))
        max_pages = min(max_pages, quick_pages)
        logging.info(f"⏩ Quick scan enabled: limiting sources to {max_pages} pages each")
    elif deep_scan:
        deep_pages = scan_depth_config.get('deep_max_pages', max_pages * 2)
        if deep_pages > max_pages:
            max_pages = deep_pages
        logging.info(f"🔎 Deep scan enabled: crawling up to {max_pages} pages per source")
    logging.info(f"📋 Max pages per source: {max_pages}")
    
    # Log scraping configuration
    scraping_config = config.get('scraping', {})
    logging.info(f"📋 Scraping configuration:")
    logging.info(f"   Timeout: {scraping_config.get('timeout', 30)}s")
    logging.info(f"   Delay between requests: {scraping_config.get('delay_between_requests', 1)}s")
    logging.info(f"   Selenium wait time: {scraping_config.get('selenium_wait_time', 10)}s")
    
    criteria = config.get('criteria', {})
    logging.info(f"📋 Using {len(criteria)} criteria:")
    for key, value in criteria.items():
        logging.info(f"   {key}: {value}")
    
    scrapers_to_run = []
    if willhaben_only:
        scrapers_to_run.append(('willhaben', scrape_willhaben))
    elif immo_kurier_only:
        scrapers_to_run.append(('immo_kurier', scrape_immo_kurier))
    elif derstandard_only:
        scrapers_to_run.append(('derstandard', scrape_derstandard))
    else:
        scrapers_to_run.extend([
            ('willhaben', scrape_willhaben),
            ('immo_kurier', scrape_immo_kurier),
            ('derstandard', scrape_derstandard)
        ])
    
    all_listings: List[Listing] = []
    scraping_results = {}
    
    logging.info(f"🔍 Starting parallel scraping of {len(scrapers_to_run)} sources...")
    
    with ThreadPoolExecutor(max_workers=len(scrapers_to_run)) as executor:
        future_to_scraper = {executor.submit(scraper_func, config, max_pages): scraper_name for scraper_name, scraper_func in scrapers_to_run}
        
        for future in as_completed(future_to_scraper):
            scraper_name = future_to_scraper[future]
            try:
                listings, source = future.result()
                scraping_results[source] = {'listings': listings, 'count': len(listings)}
                all_listings.extend(listings)
                logging.info(f"✅ {scraper_name} completed: {len(listings)} listings")
            except Exception as e:
                logging.error(f"❌ {scraper_name} failed: {e}")
                scraping_results[scraper_name] = {'listings': [], 'count': 0, 'error': str(e)}
    
    # Initialize Telegram bot for notifications (main channel)
    telegram_bot = None
    if send_to_telegram:
        telegram_config = config.get('telegram', {})
        bot_main_token = os.getenv('TELEGRAM_MAIN_BOT_TOKEN') or telegram_config.get('telegram_main', {}).get('bot_token')
        bot_main_chat_id = os.getenv('TELEGRAM_MAIN_CHAT_ID') or telegram_config.get('telegram_main', {}).get('chat_id')
        if bot_main_token and bot_main_chat_id:
            try:
                telegram_bot = TelegramBot(bot_main_token, bot_main_chat_id)
                logging.info("✅ Telegram main bot initialized for property notifications")
            except Exception as e:
                logging.error(f"❌ Failed to initialize Telegram main bot: {e}")
        else:
            logging.warning("⚠️ Telegram sending requested but bot not configured")
    else:
        logging.info("📱 Telegram notifications disabled (use --send-to-telegram to enable)")

    if all_listings:
        # Calculate scores for all listings and save to MongoDB
        logging.info(f"💾 Saving {len(all_listings)} listings to MongoDB...")
        
        # Calculate additional ratings for all listings before scoring
        from Application.rating_calculator import calculate_all_ratings
        
        for listing in all_listings:
            # Calculate missing ratings
            ratings = calculate_all_ratings(listing.__dict__)
            listing.potential_growth_rating = ratings['potential_growth_rating']
            listing.renovation_needed_rating = ratings['renovation_needed_rating']
            listing.balcony_terrace = ratings['balcony_terrace']
            listing.floor_level = ratings['floor_level']
            
            logging.info(f"📊 Calculated ratings for {listing.title}: Growth={ratings['potential_growth_rating']}, Renovation={ratings['renovation_needed_rating']}, Balcony={ratings['balcony_terrace']}, Floor={ratings['floor_level']}")
        
        # Process each listing: save to MongoDB and send to Telegram if score > 40
        saved_count = 0
        telegram_sent_count = 0
        high_score_listings = []
        
        for listing in all_listings:
            # Calculate score for the listing (always needed for MongoDB storage)
            if telegram_bot:
                score = telegram_bot.calculate_listing_score(listing.__dict__)
                listing.score = score
                
                # Check if score meets threshold for Telegram
                if score > telegram_bot.min_score_threshold:
                    high_score_listings.append(listing)
                    logging.info(f"🔥 High score listing ({score:.1f}): {listing.title}")
                else:
                    logging.info(f"⏭️  Low score listing ({score:.1f}): {listing.title} - skipping Telegram (threshold: {telegram_bot.min_score_threshold})")
            else:
                # If no Telegram bot, still calculate score for UI display and MongoDB storage
                from Application.scoring import score_apartment_simple
                score = score_apartment_simple(listing.__dict__)
                listing.score = score
                logging.info(f"📊 Listing score ({score:.1f}): {listing.title}")
        
        # Save all listings to MongoDB (regardless of score)
        saved_count = save_listings_to_mongodb(all_listings)
        
        score_threshold = 40  # Default threshold
        if config and 'telegram' in config:
            score_threshold = config['telegram'].get('min_score_threshold', 40)
        
        logging.info(f"\n🎉 Found {len(all_listings)} total listings!")
        logging.info(f"💾 {saved_count} listings saved to MongoDB")
        logging.info(f"📱 {len(high_score_listings)} listings with score > {score_threshold}")
        
        logging.info("\n📋 INTEGRATED LISTINGS SUMMARY:")
        logging.info("=" * 60)
        
        for i, listing in enumerate(all_listings, 1):
            logging.info(f"\n[{i}/{len(all_listings)}]")
            print_listing_summary(asdict(listing))
        
        # Overall statistics
        total_price = sum(l.price_total for l in all_listings if l.price_total)
        total_area = sum(l.area_m2 for l in all_listings if l.area_m2)
        avg_price = total_price / len(all_listings) if all_listings else 0
        avg_area = total_area / len(all_listings) if all_listings else 0
        
        if not skip_images:
            downloaded_count = download_images_for_listings()
            if downloaded_count > 0:
                optimize_images()
        else:
            downloaded_count = 0
        
        # Send Telegram notifications for high-score listings only (if enabled)
        if send_to_telegram and telegram_bot and high_score_listings:
            logging.info(f"📱 Sending {len(high_score_listings)} high-score notifications to Telegram...")
            
            for listing in high_score_listings:
                try:
                    success = telegram_bot.send_property_notification(listing.__dict__)
                    if success:
                        telegram_sent_count += 1
                        logging.info(f"✅ Telegram notification sent for {listing.title} (score: {listing.score})")
                        # Mark listing as sent to prevent duplicates
                        mongo.mark_sent(listing.url)
                    else:
                        logging.error(f"❌ Failed to send Telegram notification for {listing.title}")
                except Exception as e:
                    logging.error(f"❌ Telegram error for {listing.title}: {e}")
            
            logging.info(f"📱 Sent {telegram_sent_count}/{len(high_score_listings)} Telegram notifications")
        elif not send_to_telegram:
            logging.info("📱 Telegram notifications skipped (use --send-to-telegram to enable)")
        
        # Send summary to Telegram (main channel) - only if enabled
        if send_to_telegram and telegram_bot:
            try:
                summary_message = f"""🎉 <b>Integrated Immo-Scouter Summary</b>
                    📋 Found <b>{len(all_listings)}</b> total properties
                    💰 Average price: {format_currency(avg_price)}
                    📐 Average area: {avg_area:.1f}m²
                    🔥 High-score properties: {len(high_score_listings)} (score > {score_threshold})
                    📊 By Source:"""
                for source, result in scraping_results.items():
                    count = result['count']
                    if count > 0:
                        summary_message += f"\n   • {source.title()}: {count} listings"
                
                summary_message += f"\n\n📸 Downloaded {downloaded_count} images\n💾 Saved to MongoDB\n📱 Sent {telegram_sent_count} notifications"
                
                telegram_bot.send_message(summary_message)
                logging.info("📱 Summary sent to Telegram main channel")
            except Exception as e:
                logging.error(f"❌ Failed to send Telegram summary: {e}")
        elif not send_to_telegram:
            logging.info("📱 Telegram summary skipped (use --send-to-telegram to enable)")
    
    else:
        logging.info("❌ No listings found matching your criteria.")
        logging.info("💡 Consider adjusting your criteria in config.json")
            
        # Send "no results" notification (main channel) - only if enabled
        if send_to_telegram and telegram_bot:
            try:
                no_results_message = """🤷‍♂️ <b>Integrated Immo-Scouter Update</b>

No new properties found matching your criteria.

💡 Consider adjusting your search criteria if this continues."""
                telegram_bot.send_message(no_results_message)
            except Exception as e:
                logging.error(f"❌ Failed to send Telegram notification: {e}")
        elif not send_to_telegram:
            logging.info("📱 Telegram 'no results' notification skipped (use --send-to-telegram to enable)")
    
    logging.info("\n✅ Integrated Immo-Scouter Main Job Completed")
    logging.info("=" * 60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Immo-Scouter: Vienna Real Estate Scraper with Parallel Processing")
    parser.add_argument("--skip-images", action="store_true", help="Skip image downloading and optimization")
    parser.add_argument("--download-only", action="store_true", help="Only download images (skip scraping)")
    parser.add_argument("--optimize-only", action="store_true", help="Only optimize existing images (skip scraping)")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum pages to scrape per source (default: 5)")
    parser.add_argument("--willhaben-only", action="store_true", help="Only scrape Willhaben")
    parser.add_argument("--immo-kurier-only", action="store_true", help="Only scrape Immo Kurier")
    parser.add_argument("--derstandard-only", action="store_true", help="Only scrape derStandard")
    parser.add_argument("--send-to-telegram", action="store_true", help="Send property notifications to Telegram (disabled by default)")
    
    args = parser.parse_args()
    
    if args.download_only:
        logging.info("📸 Running image download only...")
        download_images_for_listings()
        optimize_images()
    elif args.optimize_only:
        logging.info("🔧 Running image optimization only...")
        optimize_images()
    else:
        main()
