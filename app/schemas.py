from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
import json


# Model-specific resolution support
MODEL_RESOLUTIONS = {
    "wan": ["480p", "720p", "1080p"],
    "wan21": ["480p", "720p"],
    "wan22": ["480p", "580p", "720p"],
    "wan-pro": ["1080p"],
    "kling": ["720p", "1080p"],
    "kling-master": ["720p", "1080p"],
    "kling-standard": ["720p", "1080p"],
    "veo2": ["720p"],
    "veo31": ["720p", "1080p"],
    "veo31-fast": ["720p", "1080p"],
    "veo31-flf": ["720p", "1080p"],
    "veo31-fast-flf": ["720p", "1080p"],
    "sora-2": ["720p"],
    "sora-2-pro": ["720p", "1080p"],
}


class JobCreate(BaseModel):
    """Schema for creating a new job."""

    image_url: str
    motion_prompt: str
    negative_prompt: Optional[str] = None
    resolution: Literal["480p", "580p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10] = 5
    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "kling",
        "kling-master",
        "kling-standard",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
    ] = "wan"

    @field_validator("resolution")
    @classmethod
    def validate_resolution_for_model(cls, v, info):
        """Validate resolution is supported by the selected model."""
        model = info.data.get("model", "wan")
        valid_resolutions = MODEL_RESOLUTIONS.get(model, ["480p", "720p", "1080p"])
        if v not in valid_resolutions:
            raise ValueError(
                f"Resolution '{v}' not supported for model '{model}'. Valid options: {valid_resolutions}"
            )
        return v


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
    model: Literal["gpt-image-1.5", "kling-image", "nano-banana-pro", "nano-banana"] = (
        "gpt-image-1.5"
    )
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

    @field_validator("result_image_urls", "local_image_paths", mode="before")
    @classmethod
    def parse_json_list(cls, v):
        """Parse JSON string to list if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class ImageModelsResponse(BaseModel):
    """Schema for listing available image models."""

    models: dict


# ============== Face Swap Schemas ==============


class FaceSwapCreate(BaseModel):
    """Schema for creating a face swap job."""

    face_image_url: str  # Image containing the face to swap FROM
    target_image_url: str  # Image to swap the face TO
    gender: Literal["male", "female", "non-binary"] = "female"
    workflow_type: Literal["target_hair", "user_hair"] = "target_hair"
    upscale: bool = True
    detailer: bool = False
    # Optional second face for multiplayer mode
    face_image_url_2: Optional[str] = None
    gender_2: Optional[Literal["male", "female", "non-binary"]] = None


class FaceSwapResponse(BaseModel):
    """Schema for face swap response."""

    model_config = ConfigDict(from_attributes=True)

    request_id: str
    status: str
    result_image_url: Optional[str] = None
    error_message: Optional[str] = None
    model: str = "easel-advanced"
    cost: float = 0.05


class FaceSwapModelsResponse(BaseModel):
    """Schema for listing available face swap models."""

    models: dict


# ============== Pipeline Schemas ==============


class PromptEnhanceConfig(BaseModel):
    """Config for prompt enhancement step."""

    input_prompts: List[str]
    variations_per_prompt: int = 5
    target_type: Literal["i2i", "i2v"] = "i2i"
    style_hints: Optional[List[str]] = None
    theme_focus: Optional[str] = None


class I2ISetMode(BaseModel):
    """Set mode config for I2I variations."""

    enabled: bool = False
    variations: Optional[
        List[Literal["angles", "expressions", "poses", "outfits", "lighting"]]
    ] = None
    count_per_variation: int = 1


class I2IConfig(BaseModel):
    """Config for I2I step."""

    model: Literal["gpt-image-1.5", "kling-image", "nano-banana", "nano-banana-pro"] = (
        "gpt-image-1.5"
    )
    images_per_prompt: int = 1
    set_mode: Optional[I2ISetMode] = None
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"


class I2VConfig(BaseModel):
    """Config for I2V step."""

    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "kling",
        "kling-master",
        "kling-standard",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
    ] = "kling"
    videos_per_image: int = 1
    resolution: Literal["480p", "580p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10] = 5

    @field_validator("resolution")
    @classmethod
    def validate_resolution_for_model(cls, v, info):
        """Validate resolution is supported by the selected model."""
        model = info.data.get("model", "kling")
        valid_resolutions = MODEL_RESOLUTIONS.get(model, ["480p", "720p", "1080p"])
        if v not in valid_resolutions:
            raise ValueError(
                f"Resolution '{v}' not supported for model '{model}'. Valid: {valid_resolutions}"
            )
        return v


class PipelineStepCreate(BaseModel):
    """Schema for creating a pipeline step."""

    step_type: Literal["prompt_enhance", "i2i", "i2v"]
    step_order: int
    config: (
        dict  # Will be PromptEnhanceConfig, I2IConfig, or I2VConfig based on step_type
    )
    inputs: Optional[dict] = None  # image_urls, prompts


class PipelineStepResponse(BaseModel):
    """Schema for pipeline step response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    step_type: str
    step_order: int
    config: dict
    status: str
    inputs: Optional[dict] = None
    outputs: Optional[dict] = None
    cost_estimate: Optional[float] = None
    cost_actual: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("config", "inputs", "outputs", mode="before")
    @classmethod
    def parse_json_dict(cls, v):
        """Parse JSON string to dict if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v


class PipelineCreate(BaseModel):
    """Schema for creating a new pipeline."""

    name: str
    mode: Literal["manual", "auto", "checkpoint"] = "manual"
    checkpoints: Optional[List[Literal["prompt_enhance", "i2i", "i2v"]]] = None
    steps: List[PipelineStepCreate]
    tags: Optional[List[str]] = None
    description: Optional[str] = None


class PipelineUpdate(BaseModel):
    """Schema for updating a pipeline."""

    name: Optional[str] = None
    mode: Optional[Literal["manual", "auto", "checkpoint"]] = None
    checkpoints: Optional[List[Literal["prompt_enhance", "i2i", "i2v"]]] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None
    is_hidden: Optional[bool] = None
    description: Optional[str] = None


class PipelineResponse(BaseModel):
    """Schema for pipeline response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    mode: str
    checkpoints: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_favorite: bool = False
    is_hidden: bool = False
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    steps: Optional[List[PipelineStepResponse]] = None

    @field_validator("checkpoints", "tags", mode="before")
    @classmethod
    def parse_json_list_checkpoints(cls, v):
        """Parse JSON string to list if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("is_favorite", "is_hidden", mode="before")
    @classmethod
    def parse_int_to_bool(cls, v):
        """Convert SQLite integer to bool."""
        if isinstance(v, int):
            return bool(v)
        return v


class PipelineListResponse(BaseModel):
    """Schema for listing pipelines (full details - used for detail view)."""

    pipelines: List[PipelineResponse]
    total: int


class PipelineSummary(BaseModel):
    """Lightweight schema for pipeline list - NO steps/outputs for fast loading."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    tags: Optional[List[str]] = None
    is_favorite: bool = False
    is_hidden: bool = False
    # Summary stats instead of full data
    output_count: int = 0
    step_count: int = 0
    total_cost: Optional[float] = None
    first_thumbnail_url: Optional[str] = None
    # Brief info for display
    model_info: Optional[str] = None  # e.g., "gpt-image-1.5 • medium"
    first_prompt: Optional[str] = None  # First prompt truncated

    @field_validator("tags", mode="before")
    @classmethod
    def parse_json_list_tags(cls, v):
        """Parse JSON string to list if needed."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("is_favorite", "is_hidden", mode="before")
    @classmethod
    def parse_int_to_bool_summary(cls, v):
        """Convert SQLite integer to bool."""
        if isinstance(v, int):
            return bool(v)
        return v


class PipelineSummaryListResponse(BaseModel):
    """Schema for listing pipelines with lightweight summaries."""

    pipelines: List[PipelineSummary]
    total: int


# ============== Prompt Enhancement Schemas ==============


class PromptEnhanceRequest(BaseModel):
    """Request to enhance prompts."""

    prompts: List[str]
    count: int = 3
    target: Literal["i2i", "i2v"] = "i2i"
    style: str = "photorealistic"
    theme_focus: Optional[str] = None
    # New enhancement options
    mode: Literal["quick_improve", "category_based", "raw"] = "quick_improve"
    categories: Optional[List[str]] = (
        None  # e.g., ["camera_movement", "motion_intensity"]
    )


class PromptEnhanceResponse(BaseModel):
    """Response with enhanced prompts."""

    original_prompts: List[str]
    enhanced_prompts: List[List[str]]  # List of variations per original prompt
    total_count: int


# ============== Cost Estimation Schemas ==============


class StepCostBreakdown(BaseModel):
    """Cost breakdown for a single step."""

    step_type: str
    step_order: int
    model: Optional[str] = None
    unit_count: int
    unit_price: float
    total: float


class CostEstimateRequest(BaseModel):
    """Request for cost estimation."""

    steps: List[PipelineStepCreate]


class CostEstimateResponse(BaseModel):
    """Response with cost breakdown."""

    breakdown: List[StepCostBreakdown]
    total: float
    currency: str = "USD"


# ============== Bulk Pipeline Schemas ==============


class BulkI2IConfig(BaseModel):
    """Config for bulk I2I generation (optional step)."""

    enabled: bool = True
    prompts: List[str]  # 1-10 prompts
    model: Literal["gpt-image-1.5", "kling-image", "nano-banana", "nano-banana-pro"] = (
        "gpt-image-1.5"
    )
    images_per_prompt: int = 1
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"
    negative_prompt: Optional[str] = None


class BulkI2VConfig(BaseModel):
    """Config for bulk I2V generation."""

    prompts: List[str]  # 1-10 motion prompts
    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "kling",
        "kling-master",
        "kling-standard",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
    ] = "kling"
    resolution: Literal["480p", "720p", "1080p"] = "1080p"
    duration_sec: int = 5  # Model-specific: Kling 5/10, Veo 4/6/8, Sora 4/8/12
    negative_prompt: Optional[str] = None
    enable_audio: bool = False  # Veo 3.1 models only - adds audio (costs 1.5-2x more)


class BulkPipelineCreate(BaseModel):
    """Schema for creating a bulk pipeline."""

    name: str = "Bulk Generation"
    source_images: List[str]  # 1-10 image URLs
    i2i_config: Optional[BulkI2IConfig] = None  # Optional: skip to go straight to video
    i2v_config: BulkI2VConfig
    tags: Optional[List[str]] = None
    description: Optional[str] = None


class SourceGroupOutput(BaseModel):
    """Outputs grouped by source image."""

    source_image: str
    source_index: int
    i2i_outputs: List[str] = []  # Full resolution image URLs
    i2i_thumbnails: List[Optional[str]] = []  # Thumbnail URLs for fast loading
    i2v_outputs: List[str] = []


class BulkPipelineTotals(BaseModel):
    """Summary counts for bulk pipeline."""

    source_images: int
    i2i_generated: int
    i2v_generated: int
    total_cost: float


class BulkPipelineResponse(BaseModel):
    """Response for bulk pipeline with grouped outputs."""

    pipeline_id: int
    name: str
    status: str
    groups: List[SourceGroupOutput]
    totals: BulkPipelineTotals
    created_at: datetime


class BulkCostBreakdown(BaseModel):
    """Cost breakdown for bulk pipeline."""

    i2i_count: int
    i2i_cost_per_image: float
    i2i_total: float
    i2v_count: int
    i2v_cost_per_video: float
    i2v_total: float
    grand_total: float


class BulkCostEstimateResponse(BaseModel):
    """Response for bulk pipeline cost estimation."""

    breakdown: BulkCostBreakdown
    combinations: (
        dict  # Matrix info: {"sources": 3, "i2i_prompts": 2, "i2v_prompts": 2, ...}
    )
    currency: str = "USD"


# ============== Animate Selected Images ==============


class AnimateSelectedRequest(BaseModel):
    """Request to create videos from selected images."""

    image_urls: List[str]  # URLs of images to animate
    prompts: List[str]  # Motion prompts
    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "kling",
        "kling-master",
        "kling-standard",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
    ] = "kling"
    resolution: Literal["480p", "720p", "1080p"] = "1080p"
    duration_sec: int = 5  # Model-specific: Kling 5/10, Veo 4/6/8, Sora 4/8/12
    negative_prompt: Optional[str] = None
    enable_audio: bool = False  # Veo 3.1 models only
    name: str = "Animate Selected"


# ============== Prompt Generator Schemas ==============


class PromptGeneratorRequest(BaseModel):
    """Request to generate i2i prompts with on-screen captions."""

    count: int = 10  # 1-50 prompts
    style: Literal["cosplay", "cottagecore"] = "cosplay"
    location: Literal["outdoor", "indoor", "mixed"] = "mixed"


class PromptGeneratorResponse(BaseModel):
    """Response with generated prompts."""

    prompts: List[str]
    count: int
    style: str
    location: str
