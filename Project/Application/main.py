import json
import os
import time
import requests
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Set up logging
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
    if telegram_config.get('telegram_main', {}).get('bot_token') and telegram_config.get('telegram_main', {}).get('chat_id'):
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
    if telegram_config.get('telegram_dev', {}).get('bot_token') and telegram_config.get('telegram_dev', {}).get('chat_id'):
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
    
    # Setup Telegram error logging to dev channel if configured
    telegram_dev_handler = None
    telegram_config = config.get('telegram', {})
    if telegram_config.get('telegram_dev', {}).get('bot_token') and telegram_config.get('telegram_dev', {}).get('chat_id'):
        try:
            from Integration.telegram_bot import TelegramBot
            dev_config = telegram_config['telegram_dev']
            telegram_dev_bot = TelegramBot(dev_config['bot_token'], dev_config['chat_id'])
            telegram_dev_handler = telegram_dev_bot.setup_error_logging(is_dev_channel=True)
            if telegram_dev_handler:
                logging.getLogger().addHandler(telegram_dev_handler)
            logging.info("✅ Telegram dev error logging configured")
        except Exception as e:
            logging.warning(f"⚠️ Failed to setup Telegram dev error logging: {e}")
    else:
        logging.info("ℹ️ Telegram dev not configured, skipping error logging setup")
    
    component_status = test_system_components(config)
    if not component_status['mongodb']:
        logging.error("❌ MongoDB is required but not working. Please fix the connection.")
        return
    
    import sys
    skip_images = "--skip-images" in sys.argv
    willhaben_only = "--willhaben-only" in sys.argv
    immo_kurier_only = "--immo-kurier-only" in sys.argv
    derstandard_only = "--derstandard-only" in sys.argv
    
    max_pages = config.get('max_pages', 5)
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
    
    if all_listings:
        # Calculate scores for all listings and save to MongoDB
        logging.info(f"💾 Saving {len(all_listings)} listings to MongoDB...")
        
        # Initialize Telegram bot for score-based filtering (main channel for properties)
        telegram_bot = None
        telegram_config = config.get('telegram', {})
        if telegram_config.get('telegram_main', {}).get('bot_token') and telegram_config.get('telegram_main', {}).get('chat_id'):
            try:
                main_config = telegram_config['telegram_main']
                telegram_bot = TelegramBot(main_config['bot_token'], main_config['chat_id'])
                logging.info("✅ Telegram main bot initialized for property notifications")
            except Exception as e:
                logging.error(f"❌ Failed to initialize Telegram main bot: {e}")
        
        # Process each listing: save to MongoDB and send to Telegram if score > 40
        saved_count = 0
        telegram_sent_count = 0
        high_score_listings = []
        
        for listing in all_listings:
            # Calculate score for the listing
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
                # If no Telegram bot, still calculate score for UI display
                from Application.scoring import score_apartment_simple
                score = score_apartment_simple(listing.__dict__)
                listing.score = score
        
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
        
        # Send Telegram notifications for high-score listings only
        if telegram_bot and high_score_listings:
            logging.info(f"📱 Sending {len(high_score_listings)} high-score notifications to Telegram...")
            
            for listing in high_score_listings:
                try:
                    success = telegram_bot.send_property_notification(listing.__dict__)
                    if success:
                        telegram_sent_count += 1
                        logging.info(f"✅ Telegram notification sent for {listing.title} (score: {listing.score})")
                    else:
                        logging.error(f"❌ Failed to send Telegram notification for {listing.title}")
                except Exception as e:
                    logging.error(f"❌ Telegram error for {listing.title}: {e}")
            
            logging.info(f"📱 Sent {telegram_sent_count}/{len(high_score_listings)} Telegram notifications")
        
        # Send summary to Telegram (main channel)
        if telegram_bot:
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
    
    else:
        logging.info("❌ No listings found matching your criteria.")
        logging.info("💡 Consider adjusting your criteria in config.json")
            
        # Send "no results" notification (main channel)
        if telegram_bot:
            try:
                no_results_message = """🤷‍♂️ <b>Integrated Immo-Scouter Update</b>

No new properties found matching your criteria.

💡 Consider adjusting your search criteria if this continues."""
                telegram_bot.send_message(no_results_message)
            except Exception as e:
                logging.error(f"❌ Failed to send Telegram notification: {e}")
    
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