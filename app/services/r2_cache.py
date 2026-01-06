"""Cloudflare R2 caching service for fast image/video loading."""

import os
import hashlib
import httpx
import boto3
from botocore.config import Config
import structlog
from dotenv import load_dotenv

# Load .env file so os.getenv() can read R2 credentials
load_dotenv()

logger = structlog.get_logger()

_s3_client = None


def get_s3_client():
    """Get or create S3 client for R2."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    # Read env vars at runtime (after load_dotenv has run)
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    endpoint = os.getenv("R2_ENDPOINT")

    if not all([access_key, secret_key, endpoint]):
        logger.warning("R2 not configured, caching disabled")
        return None

    _s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    return _s3_client


def get_public_url():
    """Get the R2 public URL."""
    domain = os.getenv("R2_PUBLIC_DOMAIN", "")
    return f"https://{domain}" if domain else None


def get_bucket():
    """Get the R2 bucket name."""
    return os.getenv("R2_BUCKET_NAME", "i2v")


def url_to_key(url: str, prefix: str = "images") -> str:
    """Convert URL to R2 object key using hash."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    ext = ".jpg"
    if ".png" in url.lower():
        ext = ".png"
    elif ".mp4" in url.lower():
        ext = ".mp4"
    elif ".webp" in url.lower():
        ext = ".webp"
    return f"{prefix}/{url_hash}{ext}"


async def cache_image(source_url: str, prefix: str = "images") -> str | None:
    """Cache an image from external URL to R2. Returns R2 public URL if successful."""
    client = get_s3_client()
    public_url = get_public_url()
    bucket = get_bucket()

    if not client or not public_url:
        return None

    key = url_to_key(source_url, prefix)

    # Check if already cached
    try:
        client.head_object(Bucket=bucket, Key=key)
        cached_url = f"{public_url}/{key}"
        logger.debug("Image already cached", key=key)
        return cached_url
    except Exception:
        pass  # Object doesn't exist, proceed to cache it

    # Download from source
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.get(source_url)
            if response.status_code != 200:
                logger.warning(
                    "Failed to download image for caching",
                    url=source_url[:60],
                    status=response.status_code,
                )
                return None
            image_data = response.content
            content_type = response.headers.get("content-type", "image/jpeg")
    except Exception as e:
        logger.error("Failed to download image", url=source_url[:60], error=str(e))
        return None

    # Upload to R2
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000",
        )
        cached_url = f"{public_url}/{key}"
        logger.info("Cached image to R2", key=key, size_kb=len(image_data) / 1024)
        return cached_url
    except Exception as e:
        logger.error("Failed to upload to R2", key=key, error=str(e))
        return None


async def cache_images_batch(
    urls: list[str], prefix: str = "images"
) -> list[str | None]:
    """Cache multiple images to R2. Returns list of cached URLs (or None for failures)."""
    import asyncio

    tasks = [cache_image(url, prefix) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=False)


async def cache_video(source_url: str) -> str | None:
    """Cache a video from external URL to R2. Returns R2 public URL if successful."""
    client = get_s3_client()
    public_url = get_public_url()
    bucket = get_bucket()

    if not client or not public_url:
        logger.warning("R2 caching skipped - client or public_url not configured",
                      has_client=client is not None, has_public_url=public_url is not None)
        return None

    logger.info("Starting R2 cache for video", url=source_url[:60])

    url_hash = hashlib.sha256(source_url.encode()).hexdigest()[:16]
    key = f"videos/{url_hash}.mp4"

    # Check if already cached
    try:
        client.head_object(Bucket=bucket, Key=key)
        cached_url = f"{public_url}/{key}"
        logger.debug("Video already cached", key=key)
        return cached_url
    except Exception:
        pass  # Object doesn't exist, proceed to cache it

    # Download video (longer timeout for large files)
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            response = await http.get(source_url)
            if response.status_code != 200:
                logger.warning(
                    "Failed to download video",
                    url=source_url[:60],
                    status=response.status_code,
                )
                return None
            video_data = response.content
    except Exception as e:
        logger.error("Failed to download video", url=source_url[:60], error=str(e))
        return None

    # Upload to R2
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=video_data,
            ContentType="video/mp4",
            CacheControl="public, max-age=31536000",
        )
        cached_url = f"{public_url}/{key}"
        logger.info(
            "Cached video to R2", key=key, size_mb=len(video_data) / (1024 * 1024)
        )
        return cached_url
    except Exception as e:
        logger.error("Failed to upload video to R2", key=key, error=str(e))
        return None


async def cache_videos_batch(urls: list[str]) -> list[str | None]:
    """Cache multiple videos to R2."""
    import asyncio

    tasks = [cache_video(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=False)


def get_cached_url(source_url: str, prefix: str = "images") -> str | None:
    """Get the R2 cached URL for a source URL if it exists."""
    client = get_s3_client()
    public_url = get_public_url()
    bucket = get_bucket()

    if not client or not public_url:
        return None

    key = url_to_key(source_url, prefix)
    try:
        client.head_object(Bucket=bucket, Key=key)
        return f"{public_url}/{key}"
    except Exception:
        return None
