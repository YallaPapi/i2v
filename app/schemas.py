from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class JobCreate(BaseModel):
    """Schema for creating a new job."""
    image_url: str
    motion_prompt: str
    resolution: Literal["480p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10] = 5
    model: Literal["wan", "wan21", "wan22", "wan-pro", "kling", "veo2", "veo31-fast", "veo31", "veo31-flf", "veo31-fast-flf"] = "wan"


class JobResponse(BaseModel):
    """Schema for job response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    motion_prompt: str
    resolution: str
    duration_sec: int
    model: str
    wan_request_id: Optional[str] = None
    wan_status: str
    wan_video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = "ok"
