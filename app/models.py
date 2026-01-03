from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func

from app.database import Base


class UploadCache(Base):
    """Cache for uploaded images to Fal CDN."""

    __tablename__ = "upload_cache"

    id = Column(Integer, primary_key=True, index=True)
    local_path = Column(String, unique=True, nullable=False)
    file_hash = Column(String, nullable=False, index=True)
    fal_url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_upload_cache_path", "local_path"),
        Index("idx_upload_cache_hash", "file_hash"),
    )

    def __repr__(self) -> str:
        return f"<UploadCache(id={self.id}, path={self.local_path}, url={self.fal_url[:50]}...)>"


class Job(Base):
    """SQLAlchemy model for video generation jobs."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    motion_prompt = Column(String, nullable=False)
    negative_prompt = Column(String, nullable=True)
    resolution = Column(String, nullable=False, default="1080p")
    duration_sec = Column(Integer, nullable=False, default=5)
    model = Column(String, nullable=False, default="wan")

    # Wan/Fal tracking
    wan_request_id = Column(String, nullable=True)
    wan_status = Column(String, nullable=False, default="pending")
    wan_video_url = Column(String, nullable=True)
    local_video_path = Column(String, nullable=True)  # Path to downloaded video
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, status={self.wan_status}, created={self.created_at})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "image_url": self.image_url,
            "motion_prompt": self.motion_prompt,
            "negative_prompt": self.negative_prompt,
            "resolution": self.resolution,
            "duration_sec": self.duration_sec,
            "model": self.model,
            "wan_request_id": self.wan_request_id,
            "wan_status": self.wan_status,
            "wan_video_url": self.wan_video_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ImageJob(Base):
    """SQLAlchemy model for image generation jobs."""

    __tablename__ = "image_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_image_url = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    negative_prompt = Column(String, nullable=True)
    model = Column(String, nullable=False, default="gpt-image-1.5")
    aspect_ratio = Column(String, nullable=False, default="9:16")
    quality = Column(String, nullable=False, default="high")
    num_images = Column(Integer, nullable=False, default=1)

    # Fal tracking
    request_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    result_image_urls = Column(String, nullable=True)  # JSON array of URLs
    local_image_paths = Column(String, nullable=True)  # JSON array of local paths
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ImageJob(id={self.id}, model={self.model}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for JSON serialization."""
        import json
        return {
            "id": self.id,
            "source_image_url": self.source_image_url,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "model": self.model,
            "aspect_ratio": self.aspect_ratio,
            "quality": self.quality,
            "num_images": self.num_images,
            "request_id": self.request_id,
            "status": self.status,
            "result_image_urls": json.loads(self.result_image_urls) if self.result_image_urls else None,
            "local_image_paths": json.loads(self.local_image_paths) if self.local_image_paths else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
