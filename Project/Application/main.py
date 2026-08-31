import json
import math
import os
import time
import html
import requests
import pymongo
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
from Application.scraping.genossenschaft_scraper import scrape_all as scrape_all_genossenschaft
from Application.analyzer import StructuredAnalyzer
from Integration.mongodb_handler import MongoDBHandler
from Integration.telegram_bot import TelegramBot
from Application.helpers.utils import format_currency, format_walking_time, ViennaDistrictHelper, load_config, get_walking_times
from Application.helpers.listing_validator import filter_valid_listings, get_validation_stats, compute_content_fingerprint, compute_content_fingerprint_v2, compute_xsrc_fingerprint, validate_url
from Application.helpers.geocoding import geocode_listing, ViennaGeocoder
from Domain.location import Coordinates
from Application.feasibility import derive_profile_fields
from Application.coop_format import format_coop_message
from Application.cleanup import deep_cleanup_database, comprehensive_cleanup_all_listings, clean_stale_or_broken_listings, check_and_alert_rejection_rate, mark_taken_listings
from Application.telegram_delivery import (
    COOP_CHANNEL,
    preserve_delivery_state,
    send_coop_listing,
    send_vienna_listings,
)
from Domain.listing import Listing
import logging
import logging.handlers
from bson import ObjectId

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

os.makedirs(log_dir, exist_ok=True)

rotating = logging.handlers.RotatingFileHandler(
    'log/immo-scouter.log',
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
rotating.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        rotating,
        logging.StreamHandler()
    ]
)


def resolve_vienna_telegram_bot(config):
    telegram_config = config.get('telegram', {})
    vienna_config = telegram_config.get('telegram_vienna', {})
    vienna_token = os.getenv('TELEGRAM_BOT_VIENNA_TOKEN') or vienna_config.get('bot_token')
    vienna_chat_id = os.getenv('TELEGRAM_BOT_VIENNA_CHAT_ID') or vienna_config.get('chat_id')

    if vienna_token and vienna_chat_id:
        return TelegramBot(vienna_token, vienna_chat_id)
    return None


def was_listing_sent_recently(mongo, url, days=7) -> bool:
    try:
        document = mongo.get_listing(url)
    except Exception as exc:
        logging.warning(f"Could not check recent Telegram delivery for {url}: {exc}")
        return False

    if not document:
        logging.warning(f"No stored listing found while checking recent Telegram delivery: {url}")
        return False
    if not isinstance(document, dict):
        logging.warning(f"Invalid stored listing while checking recent Telegram delivery: {url}")
        return False

    sent_at = document.get('sent_to_telegram_at')
    try:
        finite_timestamp = math.isfinite(sent_at)
    except (TypeError, ValueError, OverflowError):
        finite_timestamp = False
    if (
        isinstance(sent_at, bool)
        or not isinstance(sent_at, (int, float))
        or not finite_timestamp
    ):
        logging.warning(f"Invalid Telegram delivery timestamp for {url}: {sent_at!r}")
        return False

    try:
        now = time.time()
        cutoff = now - (days * 86400)
    except (TypeError, ValueError, OverflowError) as exc:
        logging.warning(f"Invalid recent-delivery window for {url}: {exc}")
        return False

    return cutoff <= sent_at <= now


def calculate_listing_score(listing, telegram_bot):
    listing_data = listing.__dict__ if hasattr(listing, '__dict__') else listing
    if telegram_bot is not None:
        return telegram_bot.calculate_listing_score(listing_data)

    from Application.scoring import score_apartment_simple
    return score_apartment_simple(listing_data)


def new_coop_candidates(mongo, listings):
    candidates = []
    seen_urls = set()
    for listing in listings:
        if (
            not getattr(listing, "is_genossenschaft", False)
            or getattr(listing, "coop_source", None) == "willhaben"
            or not getattr(listing, "url", None)
            or listing.url in seen_urls
        ):
            continue
        seen_urls.add(listing.url)
        candidates.append(listing)

    if not candidates:
        return []
    existing = mongo.get_listings_by_urls([listing.url for listing in candidates])
    if existing is None:
        logging.error("Could not determine new co-op listings; skipping source delivery")
        return []
    return [listing for listing in candidates if listing.url not in existing]


def compute_coordinate_precision_m(coordinate_source):
    """Confidence radius in meters for a given coordinate_source tier."""
    return {"exact": 10, "landmark": 200}.get(coordinate_source)

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


def scrape_willhaben(config: Dict, max_pages: int) -> Tuple[List[Listing], str]:
    """Scrape Willhaben listings"""
    try:
        logging.info("🔍 Starting Willhaben scraping...")
        scraper = WillhabenScraper(config=config)
        
        # Get max_pages from config or use default
        willhaben_config = config.get('willhaben', {})
        max_pages = willhaben_config.get('max_pages', max_pages)
        
        alert_url = config.get('alert_url', "https://www.willhaben.at/iad/searchagent/alert?verticalId=2&searchId=101&alertId=59840387")
        all_listings = scraper.scrape_search_agent_page(alert_url, max_pages=max_pages)

        default_extra = ['https://www.willhaben.at/iad/immobilien/neubauprojekt/wien']
        for extra_url in willhaben_config.get('search_url_extra', default_extra):
            logging.info(f"🏗️  Scraping extra URL: {extra_url}")
            extra_listings = scraper.scrape_search_agent_page(extra_url, max_pages=max_pages)
            all_listings.extend(extra_listings)

        logging.info(f"✅ Willhaben scraping complete: {len(all_listings)} matching listings found")
        return all_listings, "willhaben"
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

def scrape_genossenschaft(config: Dict, max_pages: int) -> Tuple[List[Listing], str]:
    """Scrape Genossenschaft (co-op Bauträger) listings"""
    try:
        logging.info("🔍 Starting Genossenschaft scraping...")
        listings = scrape_all_genossenschaft()
        logging.info(f"✅ Genossenschaft scraping complete: {len(listings)} listings found")
        return listings, "genossenschaft"
    except Exception as e:
        logging.error(f"❌ Genossenschaft scraping failed: {e}")
        return [], "genossenschaft"

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

def _persist_profile_scores(mongodb_handler, listing_dict: dict) -> None:
    """Compute and persist per-profile scores for a listing.

    Best-effort: a single failing profile must not block the scrape.
    """
    try:
        from Application.profile_scoring import score_all_profiles
        all_scores = score_all_profiles(listing_dict)
        if all_scores and listing_dict.get('_id') is not None:
            mongodb_handler.update_profile_scores(listing_dict['_id'], all_scores)
    except Exception as e:
        logging.warning(f"_persist_profile_scores failed for {listing_dict.get('url', '<no-url>')}: {e}")


def save_listings_to_mongodb(listings: List[Listing], mongo_uri: str = None,
                           db_name: str = "immo", collection_name: str = "listings") -> int:
    """Save listings to MongoDB with deduplication"""
    if not listings:
        return 0

    try:
        # Resolve mongo_uri from config if not provided
        if mongo_uri is None:
            config = load_config()
            mongo_uri = config.get('mongodb_uri') if config else "mongodb://localhost:27017/"
        
        from Integration.mongodb_handler import MongoDBHandler, is_valid_listing_data, handle_fingerprint_match
        from types import SimpleNamespace
        mongodb_handler = MongoDBHandler(uri=mongo_uri)

        client = pymongo.MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]

        collection.create_index([("content_fingerprint", 1), ("source_enum", 1)])

        saved_count = 0
        duplicate_count = 0

        for listing in listings:
            listing = normalize_listing_schema(listing)
            listing_dict = asdict(listing)
            listing_dict = derive_profile_fields(listing_dict)

            # Co-op listings get their own validation gate + cross-source dedup
            # (mongodb_handler.insert_listing() isn't used by this save path, so
            # replicate its co-op branch here instead of skipping it).
            if listing_dict.get('is_genossenschaft'):
                valid, reason = is_valid_listing_data(listing_dict)
                if not valid:
                    logging.info(f"🚫 Skipping co-op save: validation failed — {reason}")
                    continue
                xfp = compute_xsrc_fingerprint(SimpleNamespace(**listing_dict))
                if xfp:
                    listing_dict['content_fingerprint_xsrc'] = xfp
                    existing_xsrc = collection.find_one({"content_fingerprint_xsrc": xfp})
                    if existing_xsrc:
                        if (listing_dict.get('coop_source') == 'bautraeger_direct'
                                and existing_xsrc.get('coop_source') == 'willhaben'):
                            listing_dict['content_fingerprint'] = compute_content_fingerprint(listing_dict)
                            listing_dict['_id'] = existing_xsrc['_id']
                            listing_dict = preserve_delivery_state(existing_xsrc, listing_dict)
                            collection.replace_one({"_id": existing_xsrc['_id']}, listing_dict)
                        logging.info(f"🚫 Skipping cross-source co-op duplicate: {xfp}")
                        duplicate_count += 1
                        continue

            fingerprint = compute_content_fingerprint_v2(listing_dict)
            listing_dict['content_fingerprint'] = fingerprint
            source_enum = listing_dict.get('source_enum', listing_dict.get('source', ''))

            existing_by_url = collection.find_one({"url": listing.url})

            if existing_by_url:
                listing_dict['_id'] = existing_by_url['_id']
                listing_dict['listing_status'] = existing_by_url.get('listing_status', 'active')
                listing_dict['taken_at'] = existing_by_url.get('taken_at')

                old_price = existing_by_url.get('price_total')
                new_price = listing_dict.get('price_total')
                price_history = list(existing_by_url.get('price_history', []))
                if new_price is not None and old_price is not None and new_price != old_price:
                    from datetime import datetime
                    price_history.append({'price_total': old_price, 'recorded_at': datetime.utcnow()})
                listing_dict['price_history'] = price_history

                listing_dict = preserve_delivery_state(existing_by_url, listing_dict)
                collection.replace_one({"_id": existing_by_url['_id']}, listing_dict)
                duplicate_count += 1
                logging.debug(f"🔄 Updated existing listing: {listing.title}")
                _persist_profile_scores(mongodb_handler, listing_dict)
            else:
                existing_by_fingerprint = collection.find_one(
                    {"content_fingerprint": fingerprint, "source_enum": source_enum}
                )
                if existing_by_fingerprint:
                    logging.info(f"🚫 Skipping duplicate by content fingerprint: {listing.title} (URL: {listing.url})")
                    duplicate_count += 1
                    prior_precision = compute_coordinate_precision_m(listing_dict.get('coordinate_source'))
                    geocoded = geocode_listing(listing_dict)
                    if geocoded.get('coordinate_source') != 'none' and not existing_by_fingerprint.get('coordinates'):
                        new_precision = compute_coordinate_precision_m(geocoded.get('coordinate_source'))
                        listing_dict['coordinate_precision_m'] = new_precision
                        mongodb_handler.update_listing_coordinates(listing_dict['url'], geocoded)
                        if new_precision is not None and (prior_precision is None or new_precision < prior_precision):
                            # Precision improved (e.g. landmark -> exact): recompute
                            # walk-distance calcs that were based on the coarser fix.
                            coords_dict = geocoded.get('coordinates')
                            if coords_dict:
                                coords = Coordinates(coords_dict['lat'], coords_dict['lon'])
                                geocoding_handler = ViennaGeocoder()
                                listing_dict['school_walk_minutes'] = geocoding_handler.get_school_walk_minutes(coords)
                                listing_dict['ubahn_walk_minutes'] = geocoding_handler.get_walking_distance_to_nearest_ubahn(coords)


                    update_payload = handle_fingerprint_match(existing_by_fingerprint, listing_dict)
                    if update_payload:
                        collection.update_one({"_id": existing_by_fingerprint["_id"]}, {"$set": update_payload})
                    continue
                result = collection.insert_one(listing_dict)
                listing_dict['_id'] = result.inserted_id
                saved_count += 1
                logging.debug(f"💾 Saved new listing: {listing.title}")
                _persist_profile_scores(mongodb_handler, listing_dict)

                prior_precision = compute_coordinate_precision_m(listing_dict.get('coordinate_source'))
                geocoded = geocode_listing(listing_dict)
                if geocoded.get('coordinate_source') != 'none':
                    new_precision = compute_coordinate_precision_m(geocoded.get('coordinate_source'))
                    listing_dict['coordinate_precision_m'] = new_precision
                    mongodb_handler.update_listing_coordinates(listing_dict['url'], geocoded)
                    if new_precision is not None and (prior_precision is None or new_precision < prior_precision):
                        # Precision improved (e.g. landmark -> exact): recompute
                        # walk-distance calcs that were based on the coarser fix.
                        coords_dict = geocoded.get('coordinates')
                        if coords_dict:
                            coords = Coordinates(coords_dict['lat'], coords_dict['lon'])
                            geocoding_handler = ViennaGeocoder()
                            listing_dict['school_walk_minutes'] = geocoding_handler.get_school_walk_minutes(coords)
                            listing_dict['ubahn_walk_minutes'] = geocoding_handler.get_walking_distance_to_nearest_ubahn(coords)

        mongodb_handler.close()
        client.close()
        
        logging.info(f"💾 MongoDB save complete: {saved_count} new, {duplicate_count} updated")
        return saved_count
        
    except Exception as e:
        logging.error(f"❌ Error saving to MongoDB: {e}")
        if 'mongodb_handler' in dir():
            mongodb_handler.close()
        return 0
