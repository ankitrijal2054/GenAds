"""
S3 utilities for file uploads and management.
Handles product image uploads and S3 integration.
"""

import logging
import boto3
from typing import Optional
import os
from uuid import uuid4

from app.config import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    """
    Get S3 client configured with AWS credentials.
    
    **Returns:**
    - boto3.client: Configured S3 client
    
    **Raises:**
    - RuntimeError: If AWS credentials not configured
    """
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise RuntimeError("AWS credentials not configured in .env")
    
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key
    )


async def upload_product_image(
    file_content: bytes,
    filename: str,
    project_id: str
) -> dict:
    """
    Upload product image to S3.
    
    **Arguments:**
    - file_content: File bytes to upload
    - filename: Original filename
    - project_id: Project UUID (used in S3 path)
    
    **Returns:**
    - dict: {
        "url": "https://s3.amazonaws.com/...",
        "s3_key": "products/...",
        "size_bytes": 123456,
        "filename": "product.jpg"
      }
    
    **Raises:**
    - RuntimeError: If upload fails
    """
    try:
        if not settings.s3_bucket_name:
            raise RuntimeError("S3_BUCKET_NAME not configured in .env")
        
        # Generate S3 key
        file_ext = os.path.splitext(filename)[1].lower()
        s3_key = f"products/{project_id}/{uuid4()}{file_ext}"
        
        # Upload to S3
        s3 = get_s3_client()
        s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType=get_content_type(file_ext),
            ACL="public-read"
        )
        
        # Generate public URL
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        
        logger.info(f"✅ Uploaded product image: {s3_key}")
        
        return {
            "url": s3_url,
            "s3_key": s3_key,
            "size_bytes": len(file_content),
            "filename": filename
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to upload product image: {e}")
        raise RuntimeError(f"Failed to upload image: {str(e)}")


def get_content_type(file_ext: str) -> str:
    """
    Get MIME type for file extension.
    
    **Arguments:**
    - file_ext: File extension including dot (e.g., ".jpg")
    
    **Returns:**
    - str: MIME type
    """
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    return mime_types.get(file_ext, "application/octet-stream")


def validate_image_file(
    filename: str,
    file_size: int,
    max_size_mb: int = 10
) -> dict:
    """
    Validate product image file.
    
    **Arguments:**
    - filename: Original filename
    - file_size: File size in bytes
    - max_size_mb: Maximum file size in MB
    
    **Returns:**
    - dict: {"valid": bool, "error": "message or None"}
    
    **Validation:**
    - Only jpg, png, webp, gif allowed
    - Maximum size: 10MB
    """
    # Check extension
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in allowed_ext:
        return {
            "valid": False,
            "error": f"File type not allowed. Only {', '.join(allowed_ext)} accepted"
        }
    
    # Check size
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return {
            "valid": False,
            "error": f"File too large. Maximum {max_size_mb}MB allowed"
        }
    
    return {"valid": True, "error": None}


def delete_s3_file(s3_key: str) -> bool:
    """
    Delete a file from S3.
    
    **Arguments:**
    - s3_key: S3 object key (e.g., "products/xxx/file.jpg")
    
    **Returns:**
    - bool: True if deleted, False if error
    """
    try:
        if not settings.s3_bucket_name:
            logger.warning("S3_BUCKET_NAME not configured")
            return False
        
        s3 = get_s3_client()
        s3.delete_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key
        )
        
        logger.info(f"✅ Deleted S3 file: {s3_key}")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to delete S3 file {s3_key}: {e}")
        return False


def get_s3_file_url(s3_key: str) -> str:
    """
    Generate public URL for S3 file.
    
    **Arguments:**
    - s3_key: S3 object key
    
    **Returns:**
    - str: Public HTTPS URL
    """
    return f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"

