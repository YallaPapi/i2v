"""Upload local images to Fal CDN with caching."""
import hashlib
import os
from pathlib import Path
import structlog
from sqlalchemy.orm import Session
import fal_client

from app.config import settings
from app.database import SessionLocal
from app.models import UploadCache

logger = structlog.get_logger()

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}

# Set FAL_KEY environment variable for fal_client
if settings.fal_api_key:
    os.environ["FAL_KEY"] = settings.fal_api_key


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_cached_url(db: Session, local_path: str, file_hash: str) -> str | None:
    """Check cache for existing upload."""
    cached = (
        db.query(UploadCache)
        .filter(
            (UploadCache.local_path == local_path) | (UploadCache.file_hash == file_hash)
        )
        .first()
    )
    if cached:
        logger.debug("Cache hit", local_path=local_path, fal_url=cached.fal_url)
        return cached.fal_url
    return None


def insert_cache(db: Session, local_path: str, file_hash: str, fal_url: str) -> None:
    """Insert upload into cache."""
    cache_entry = UploadCache(
        local_path=local_path,
        file_hash=file_hash,
        fal_url=fal_url,
    )
    db.add(cache_entry)
    db.commit()
    logger.debug("Cached upload", local_path=local_path, fal_url=fal_url)


async def upload_to_fal(file_path: Path) -> str:
    """Upload file to Fal CDN using fal_client library."""
    # fal_client.upload_file is synchronous, use it directly
    # The library handles authentication via FAL_KEY env var
    try:
        fal_url = fal_client.upload_file(file_path)
        logger.info("Uploaded to Fal", file=file_path.name, url=fal_url[:60] if len(fal_url) > 60 else fal_url)
        return fal_url
    except Exception as e:
        logger.error("Fal upload failed", file=file_path.name, error=str(e))
        raise Exception(f"Fal upload error: {str(e)}")


async def upload_image(local_path: str | Path) -> str:
    """
    Upload local image to Fal CDN with caching.

    Returns the Fal CDN URL.
    """
    path = Path(local_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {path.suffix}. Supported: {SUPPORTED_FORMATS}")

    path_str = str(path)
    file_hash = compute_file_hash(path)

    # Check cache if enabled
    if settings.upload_cache_enabled:
        db = SessionLocal()
        try:
            cached_url = get_cached_url(db, path_str, file_hash)
            if cached_url:
                return cached_url
        finally:
            db.close()

    # Upload to Fal
    logger.info("Uploading image", path=path_str)
    fal_url = await upload_to_fal(path)

    # Cache the result
    if settings.upload_cache_enabled:
        db = SessionLocal()
        try:
            insert_cache(db, path_str, file_hash, fal_url)
        finally:
            db.close()

    return fal_url


def scan_images_dir(images_dir: str | Path) -> list[Path]:
    """Scan directory for supported image files."""
    dir_path = Path(images_dir)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")

    images = []
    for ext in SUPPORTED_FORMATS:
        images.extend(dir_path.glob(f"*{ext}"))
        images.extend(dir_path.glob(f"*{ext.upper()}"))

    images = sorted(set(images))
    logger.info("Found images", count=len(images), directory=str(dir_path))
    return images
