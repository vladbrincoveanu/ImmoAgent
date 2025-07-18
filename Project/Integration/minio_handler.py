import os
import io
import mimetypes
from typing import Optional, Dict, Any
from minio import Minio
from minio.error import S3Error
import logging
from urllib.parse import urlparse
import requests
from PIL import Image
import uuid

class MinIOHandler:
    """Handler for MinIO object storage operations"""
    
    def __init__(self, 
                 endpoint: str = "localhost:9000",
                 access_key: str = "minioadmin",
                 secret_key: str = "minioadmin123",
                 secure: bool = False,
                 bucket_name: str = "property-images"):
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if it doesn't"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logging.info(f"✅ Created MinIO bucket: {self.bucket_name}")
            else:
                logging.info(f"✅ MinIO bucket exists: {self.bucket_name}")
        except S3Error as e:
            logging.error(f"❌ MinIO bucket error: {e}")
            raise
    
    def upload_image_from_url(self, image_url: str, object_name: Optional[str] = None) -> Optional[str]:
        """Download image from URL and upload to MinIO"""
        try:
            # Download image from URL
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get('content-type', 'image/jpeg')
            ext = mimetypes.guess_extension(content_type) or '.jpg'
            
            # Generate object name if not provided
            if not object_name:
                object_name = f"{uuid.uuid4()}{ext}"
            
            # Upload to MinIO
            image_data = io.BytesIO(response.content)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=image_data,
                length=len(response.content),
                content_type=content_type
            )
            
            logging.info(f"✅ Uploaded image to MinIO: {object_name}")
            return object_name
            
        except Exception as e:
            logging.error(f"❌ Failed to upload image from URL {image_url}: {e}")
            return None
    
    def upload_image_from_file(self, file_path: str, object_name: Optional[str] = None) -> Optional[str]:
        """Upload image from local file to MinIO"""
        try:
            if not os.path.exists(file_path):
                logging.error(f"❌ File not found: {file_path}")
                return None
            
            # Generate object name if not provided
            if not object_name:
                ext = os.path.splitext(file_path)[1]
                object_name = f"{uuid.uuid4()}{ext}"
            
            # Get content type
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'image/jpeg'
            
            # Upload to MinIO
            with open(file_path, 'rb') as file_data:
                self.client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    data=file_data,
                    length=os.path.getsize(file_path),
                    content_type=content_type
                )
            
            logging.info(f"✅ Uploaded file to MinIO: {object_name}")
            return object_name
            
        except Exception as e:
            logging.error(f"❌ Failed to upload file {file_path}: {e}")
            return None
    
    def download_image(self, object_name: str, local_path: str) -> bool:
        """Download image from MinIO to local file"""
        try:
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=local_path
            )
            logging.info(f"✅ Downloaded image from MinIO: {object_name} -> {local_path}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to download image {object_name}: {e}")
            return False
    
    def get_image_url(self, object_name: str, expires: int = 3600) -> Optional[str]:
        """Get presigned URL for image access"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires
            )
            return url
        except Exception as e:
            logging.error(f"❌ Failed to generate presigned URL for {object_name}: {e}")
            return None
    
    def delete_image(self, object_name: str) -> bool:
        """Delete image from MinIO"""
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            logging.info(f"✅ Deleted image from MinIO: {object_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to delete image {object_name}: {e}")
            return False
    
    def list_images(self, prefix: str = "") -> list:
        """List all images in the bucket"""
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix
            )
            return [obj.object_name for obj in objects]
        except Exception as e:
            logging.error(f"❌ Failed to list images: {e}")
            return []
    
    def image_exists(self, object_name: str) -> bool:
        """Check if image exists in MinIO"""
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            else:
                logging.error(f"❌ Error checking image existence {object_name}: {e}")
                return False
        except Exception as e:
            logging.error(f"❌ Error checking image existence {object_name}: {e}")
            return False
    
    def optimize_and_upload_image(self, image_data: bytes, object_name: str, 
                                max_size: tuple = (800, 600), quality: int = 85) -> Optional[str]:
        """Optimize image and upload to MinIO"""
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            # Resize if larger than max_size
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image to bytes
            optimized_data = io.BytesIO()
            image.save(optimized_data, 'JPEG', quality=quality, optimize=True)
            optimized_data.seek(0)
            
            # Upload to MinIO
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=optimized_data,
                length=len(optimized_data.getvalue()),
                content_type='image/jpeg'
            )
            
            logging.info(f"✅ Optimized and uploaded image: {object_name}")
            return object_name
            
        except Exception as e:
            logging.error(f"❌ Failed to optimize and upload image {object_name}: {e}")
            return None
    
    def migrate_from_local_images(self, local_images_dir: str) -> Dict[str, str]:
        """Migrate all images from local directory to MinIO"""
        migrated = {}
        
        if not os.path.exists(local_images_dir):
            logging.warning(f"⚠️ Local images directory not found: {local_images_dir}")
            return migrated
        
        # Find all image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        for root, dirs, files in os.walk(local_images_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, local_images_dir)
                    
                    # Upload to MinIO
                    object_name = self.upload_image_from_file(file_path, relative_path)
                    if object_name:
                        migrated[file_path] = object_name
        
        logging.info(f"✅ Migrated {len(migrated)} images to MinIO")
        return migrated 