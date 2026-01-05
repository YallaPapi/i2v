"""Thumbnail generation service for fast image previews."""
import os
import io
import hashlib
import httpx
import structlog
from PIL import Image
import boto3
from botocore.config import Config

logger = structlog.get_logger()

THUMBNAIL_WIDTH = 600  # High quality preview
THUMBNAIL_QUALITY = 85  # Sharp quality
DOWNLOAD_TIMEOUT = 15.0

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

    if all([access_key, secret_key, endpoint]):
        _s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
    return _s3_client


async def generate_thumbnail(image_url: str) -> str | None:
    """
    Generate a thumbnail from an image URL and upload to R2.

    1. Downloads the image from URL
    2. Resizes to 400px width (maintaining aspect ratio)
    3. Converts to JPEG at 80% quality
    4. Uploads to Cloudflare R2
    5. Returns R2 public URL

    Returns None if generation fails (caller should fallback to original URL).
    """
    try:
        # Download the image
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            response = await client.get(image_url)
            if response.status_code != 200:
                logger.warning("Failed to download image for thumbnail",
                             url=image_url[:80], status=response.status_code)
                return None
            image_data = response.content

        # Open and resize
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Calculate new dimensions maintaining aspect ratio
        original_width, original_height = img.size
        ratio = THUMBNAIL_WIDTH / original_width
        new_height = int(original_height * ratio)

        # Resize using high-quality Lanczos resampling
        img = img.resize((THUMBNAIL_WIDTH, new_height), Image.Resampling.LANCZOS)

        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
        thumb_data = buffer.getvalue()
        thumb_size = len(thumb_data)

        # Generate unique key from source URL
        url_hash = hashlib.sha256(image_url.encode()).hexdigest()[:16]
        key = f"thumbnails/{url_hash}.jpg"

        # Upload to R2
        s3 = get_s3_client()
        if s3:
            bucket = os.getenv("R2_BUCKET_NAME", "i2v")
            public_domain = os.getenv("R2_PUBLIC_DOMAIN", "")

            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=thumb_data,
                ContentType='image/jpeg',
                CacheControl='public, max-age=31536000'
            )
            # Return public URL
            if public_domain:
                thumbnail_url = f"https://{public_domain}/{key}"
            else:
                # Fallback to endpoint-based URL (requires public access)
                endpoint = os.getenv("R2_ENDPOINT")
                thumbnail_url = f"{endpoint}/{bucket}/{key}"

            logger.info("Generated thumbnail to R2",
                       key=key,
                       thumb_size_kb=thumb_size / 1024,
                       dimensions=f"{THUMBNAIL_WIDTH}x{new_height}")
            return thumbnail_url
        else:
            # Fallback to Fal CDN if R2 not configured
            import tempfile
            from pathlib import Path
            import fal_client
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(thumb_data)
                tmp_path = Path(tmp.name)
            try:
                thumbnail_url = fal_client.upload_file(tmp_path)
                logger.info("Generated thumbnail to Fal (R2 not configured)",
                           thumb_size_kb=thumb_size / 1024)
                return thumbnail_url
            finally:
                tmp_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error("Thumbnail generation failed",
                    url=image_url[:80] if image_url else "None",
                    error=str(e))
        return None


async def generate_thumbnails_batch(image_urls: list[str]) -> list[str | None]:
    """
    Generate thumbnails for a batch of images.

    Returns list of thumbnail URLs (or None for failures) in same order as input.
    """
    import asyncio

    tasks = [generate_thumbnail(url) for url in image_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to None
    return [r if isinstance(r, str) else None for r in results]
