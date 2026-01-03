from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
import json


class JobCreate(BaseModel):
    """Schema for creating a new job."""
    image_url: str
    motion_prompt: str
    negative_prompt: Optional[str] = None
    resolution: Literal["480p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10] = 5
    model: Literal["wan", "wan21", "wan22", "wan-pro", "kling", "kling-master", "kling-standard", "veo2", "veo31-fast", "veo31", "veo31-flf", "veo31-fast-flf", "sora-2", "sora-2-pro"] = "wan"


class JobResponse(BaseModel):
    """Schema for job response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    motion_prompt: str
    negative_prompt: Optional[str] = None
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


# Image generation schemas
class ImageJobCreate(BaseModel):
    """Schema for creating a new image generation job."""
    source_image_url: str
    prompt: str
    negative_prompt: Optional[str] = None
    model: Literal["gpt-image-1.5", "kling-image", "nano-banana-pro", "nano-banana"] = "gpt-image-1.5"
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"
    num_images: Literal[1, 2, 3, 4] = 1


class ImageJobResponse(BaseModel):
    """Schema for image job response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_image_url: str
    prompt: str
    negative_prompt: Optional[str] = None
    model: str
    aspect_ratio: str
    quality: str
    num_images: int
    request_id: Optional[str] = None
    status: str
    result_image_urls: Optional[List[str]] = None
    local_image_paths: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('result_image_urls', 'local_image_paths', mode='before')
    @classmethod
    def parse_json_list(cls, v):
        """Parse JSON string to list if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class ImageModelsResponse(BaseModel):
    """Schema for listing available image models."""
    models: dict
