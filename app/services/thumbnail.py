"""Thumbnail generation service for fast image previews."""
import io
import httpx
import structlog
from PIL import Image
import fal_client

logger = structlog.get_logger()

THUMBNAIL_WIDTH = 300
THUMBNAIL_QUALITY = 80
DOWNLOAD_TIMEOUT = 15.0


async def generate_thumbnail(image_url: str) -> str | None:
    """
    Generate a thumbnail from an image URL.

    1. Downloads the image from URL
    2. Resizes to 300px width (maintaining aspect ratio)
    3. Converts to JPEG at 80% quality
    4. Uploads to Fal CDN
    5. Returns thumbnail URL

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

        # Save to bytes as JPEG
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
        output.seek(0)

        # Upload to Fal CDN
        # fal_client.upload accepts file-like objects
        thumbnail_url = fal_client.upload(output, content_type="image/jpeg")

        thumb_size = len(output.getvalue())
        logger.info("Generated thumbnail",
                   original_url=image_url[:60],
                   thumb_size_kb=thumb_size / 1024,
                   dimensions=f"{THUMBNAIL_WIDTH}x{new_height}")

        return thumbnail_url

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
