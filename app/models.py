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
    resolution = Column(String, nullable=False, default="1080p")
    duration_sec = Column(Integer, nullable=False, default=5)
    model = Column(String, nullable=False, default="wan")  # "wan" or "kling"

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
