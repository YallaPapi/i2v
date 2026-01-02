"""Upload local images to Fal CDN with caching."""
import hashlib
from pathlib import Path
import httpx
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import UploadCache

logger = structlog.get_logger()

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}


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
    """Upload file to Fal CDN using REST API."""
    url = "https://fal.ai/api/storage/upload"

    with open(file_path, "rb") as f:
        file_content = f.read()

    # Determine content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    content_type = content_types.get(suffix, "application/octet-stream")

    headers = {
        "Authorization": f"Key {settings.fal_api_key}",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            files={"file": (file_path.name, file_content, content_type)},
        )

        if response.status_code >= 400:
            raise Exception(f"Fal upload error: {response.status_code} - {response.text}")

        data = response.json()
        fal_url = data.get("url") or data.get("file_url") or data.get("access_url")

        if not fal_url:
            # If response is just the URL string
            if isinstance(data, str):
                fal_url = data
            else:
                raise Exception(f"No URL in upload response: {data}")

        logger.info("Uploaded to Fal", file=file_path.name, url=fal_url[:60])
        return fal_url


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
