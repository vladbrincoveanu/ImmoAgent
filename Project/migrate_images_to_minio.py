#!/usr/bin/env python3
"""
Migration script to move existing local images to MinIO
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from integration.minio_handler import MinIOHandler
from integration.mongodb_handler import MongoDBHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/migration.log'),
        logging.StreamHandler()
    ]
)

def migrate_images_to_minio():
    """Migrate all local images to MinIO and update MongoDB records"""
    logging.info("🚀 Starting image migration to MinIO...")
    
    try:
        # Initialize handlers
        minio_handler = MinIOHandler()
        mongo_handler = MongoDBHandler()
        
        logging.info("✅ Handlers initialized successfully")
        
        # Get all listings with local_image_path
        client = mongo_handler.client
        db = client[mongo_handler.db.name]
        collection = db[mongo_handler.collection.name]
        
        # Find listings with local_image_path but no minio_image_path
        listings = collection.find({
            "local_image_path": {"$exists": True, "$ne": None},
            "$or": [
                {"minio_image_path": {"$exists": False}},
                {"minio_image_path": None}
            ]
        })
        
        migrated_count = 0
        error_count = 0
        
        for listing in listings:
            try:
                local_path = listing.get('local_image_path')
                if not local_path:
                    continue
                
                # Convert relative path to absolute path
                if local_path.startswith('/static/'):
                    local_path = local_path[1:]  # Remove leading slash
                
                absolute_path = os.path.join(project_root, local_path)
                
                if not os.path.exists(absolute_path):
                    logging.warning(f"⚠️ Local image not found: {absolute_path}")
                    continue
                
                # Generate MinIO object name
                property_id = str(listing['_id'])
                object_name = f"{property_id}.jpg"
                
                # Upload to MinIO
                logging.info(f"📤 Uploading {absolute_path} to MinIO as {object_name}")
                uploaded_name = minio_handler.upload_image_from_file(absolute_path, object_name)
                
                if uploaded_name:
                    # Update MongoDB record
                    collection.update_one(
                        {"_id": listing["_id"]},
                        {"$set": {"minio_image_path": uploaded_name}}
                    )
                    migrated_count += 1
                    logging.info(f"✅ Successfully migrated: {object_name}")
                else:
                    error_count += 1
                    logging.error(f"❌ Failed to upload: {absolute_path}")
                
            except Exception as e:
                error_count += 1
                logging.error(f"❌ Error processing listing {listing.get('_id')}: {e}")
        
        # Also migrate static/images directory if it exists
        static_images_dir = os.path.join(project_root, 'static', 'images')
        if os.path.exists(static_images_dir):
            logging.info(f"📁 Migrating static images directory: {static_images_dir}")
            migrated_files = minio_handler.migrate_from_local_images(static_images_dir)
            logging.info(f"✅ Migrated {len(migrated_files)} static images")
        
        logging.info(f"🎉 Migration complete: {migrated_count} listings migrated, {error_count} errors")
        
        # Close connections
        client.close()
        
        return migrated_count, error_count
        
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        return 0, 1

def cleanup_local_images():
    """Remove local images after successful migration"""
    logging.info("🧹 Cleaning up local images...")
    
    try:
        # Remove static/images directory
        static_images_dir = os.path.join(project_root, 'static', 'images')
        if os.path.exists(static_images_dir):
            import shutil
            shutil.rmtree(static_images_dir)
            logging.info(f"✅ Removed local images directory: {static_images_dir}")
        
        logging.info("✅ Cleanup complete")
        
    except Exception as e:
        logging.error(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    print("🔄 Image Migration to MinIO")
    print("=" * 50)
    
    # Run migration
    migrated, errors = migrate_images_to_minio()
    
    if errors == 0 and migrated > 0:
        print(f"\n✅ Migration successful: {migrated} images migrated")
        
        # Ask for cleanup confirmation
        response = input("\n🧹 Do you want to remove local images? (y/N): ")
        if response.lower() in ['y', 'yes']:
            cleanup_local_images()
        else:
            print("ℹ️ Local images preserved")
    else:
        print(f"\n⚠️ Migration completed with {errors} errors")
        print("ℹ️ Local images preserved due to errors") 