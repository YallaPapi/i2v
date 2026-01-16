from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
import json


# Model-specific resolution support
MODEL_RESOLUTIONS = {
    # fal.ai models
    "wan": ["480p", "720p", "1080p"],
    "wan21": ["480p", "720p"],
    "wan22": ["480p", "580p", "720p"],
    "wan-pro": ["1080p"],
    "wan26": ["720p", "1080p"],  # Wan 2.6
    "kling": ["720p", "1080p"],
    "kling-master": ["720p", "1080p"],
    "kling-standard": ["720p", "1080p"],
    "kling26-pro": ["720p", "1080p"],  # Kling 2.6 Pro
    "veo2": ["720p"],
    "veo31": ["720p", "1080p"],
    "veo31-fast": ["720p", "1080p"],
    "veo31-flf": ["720p", "1080p"],
    "veo31-fast-flf": ["720p", "1080p"],
    "sora-2": ["720p"],
    "sora-2-pro": ["720p", "1080p"],
    "luma": ["540p", "720p", "1080p"],
    "luma-ray2": ["540p", "720p", "1080p"],
    "cogvideox": ["480p", "720p"],  # CogVideoX-5B
    "stable-video": ["576p"],  # SVD fixed resolution
    # Vast.ai self-hosted models
    "vastai-wan22-i2v": ["480p", "720p", "1080p"],  # Wan 2.2 I2V 14B (1080p may OOM)
    "vastai-wan22-t2v": ["480p", "720p"],
    "vastai-cogvideox": ["480p", "720p"],
    "vastai-svd": ["576p"],
    # Pinokio WAN GP self-hosted models
    "pinokio-wan22-i2v": ["480p", "720p"],  # Wan 2.2 I2V via Pinokio
    "pinokio-hunyuan-i2v": ["480p", "720p"],  # Hunyuan 1.5 i2v
}


# ============================================================
# VAST.AI CONFIGURATION
# ============================================================

class VastaiVideoConfig(BaseModel):
    """Config for Vast.ai video generation with Wan 2.2."""

    # LoRA params (high+low pair for dual-model Wan 2.2)
    lora_high: Optional[str] = None  # Lightning LoRA for high-noise model
    lora_low: Optional[str] = None   # Lightning LoRA for low-noise swap model
    lora_strength: float = 1.0  # 0.0-1.0
    steps: int = 10  # Image gen steps
    cfg_scale: float = 7.0  # Image gen CFG scale
    frames: int = 80  # Number of frames (17-257)
    fps: int = 16  # Output FPS
    seed: Optional[int] = -1  # Random seed (-1 for random)

    # Advanced Wan 2.2 I2V params
    video_steps: int = 5  # Video diffusion steps (5 with lightning LoRA)
    video_cfg: float = 1.0  # Video CFG scale (1.0 for Wan)
    swap_model: Optional[str] = None  # Model to swap to at swap_percent
    swap_percent: float = 0.6  # When to swap (0.6 = 60%)
    interpolation_method: Optional[str] = "RIFE"  # Frame interpolation
    interpolation_multiplier: int = 2  # Interpolation factor (2x frames)

    # Post-processing options
    caption: Optional[str] = None  # Caption text for overlay
    apply_spoof: bool = False  # Apply spoofing transforms


def is_vastai_model(model: str) -> bool:
    """Check if model runs on Vast.ai."""
    return model.startswith("vastai-")


# ============================================================
# PINOKIO WAN GP CONFIGURATION
# ============================================================

class PinokioVideoConfig(BaseModel):
    """Config for Pinokio WAN GP video generation.

    Source: .taskmaster/docs/pinokio-integration-prd.txt
    Verified: wgp.py:5164 generate_video() signature
    """

    steps: int = 4  # Inference steps (4 for distilled models)
    cfg_scale: float = 5.0  # Guidance scale
    frames: int = 81  # Number of frames (81 = ~5sec at 16fps)
    seed: int = -1  # Random seed (-1 for random)


def is_pinokio_model(model: str) -> bool:
    """Check if model runs on Pinokio WAN GP."""
    return model.startswith("pinokio-")


class JobCreate(BaseModel):
    """Schema for creating a new job."""

    image_url: str
    motion_prompt: str
    negative_prompt: Optional[str] = None
    resolution: Literal["480p", "576p", "580p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10, 15] = 5  # 15s supported by Wan 2.6
    model: Literal[
        # fal.ai models
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "wan26",
        "kling",
        "kling-master",
        "kling-standard",
        "kling26-pro",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
        "luma",
        "luma-ray2",
        "cogvideox",
        "stable-video",
        # Vast.ai self-hosted models
        "vastai-wan22-i2v",
        "vastai-wan22-t2v",
        "vastai-cogvideox",
        "vastai-svd",
        # Pinokio WAN GP self-hosted models
        "pinokio-wan22-i2v",
        "pinokio-hunyuan-i2v",
    ] = "wan"
    # Vast.ai config (only used when model starts with 'vastai-')
    vastai_config: Optional[VastaiVideoConfig] = None
    # Pinokio config (only used when model starts with 'pinokio-')
    pinokio_config: Optional[PinokioVideoConfig] = None

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

    def get_provider(self) -> Literal["fal", "vastai", "pinokio"]:
        """Get provider based on model selection."""
        if is_vastai_model(self.model):
            return "vastai"
        elif is_pinokio_model(self.model):
            return "pinokio"
        else:
            return "fal"


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
    provider: str = "fal"  # Video generation provider
    wan_request_id: Optional[str] = None
    wan_status: str
    wan_video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str = "ok"


# Image model type - includes all FLUX.1, FLUX.2, Kontext, and Ideogram variants
ImageModelType = Literal[
    "gpt-image-1.5",
    "kling-image",
    "nano-banana-pro",
    "nano-banana",
    "flux-general",  # FLUX.1
    # FLUX.2 variants
    "flux-2-dev",
    "flux-2-pro",
    "flux-2-flex",
    "flux-2-max",
    # FLUX.1 Kontext (in-context editing)
    "flux-kontext-dev",
    "flux-kontext-pro",
    # Ideogram (text-in-image)
    "ideogram-2",
]


# Image generation schemas
class ImageJobCreate(BaseModel):
    """Schema for creating a new image generation job."""

    source_image_url: str
    prompt: str
    negative_prompt: Optional[str] = None
    model: ImageModelType = "gpt-image-1.5"
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"
    num_images: Literal[1, 2, 3, 4] = 1
    # FLUX.1 parameters (flux-general only)
    flux_strength: Optional[float] = None  # 0.0-1.0, default 0.75
    flux_scheduler: Optional[Literal["euler", "dpmpp_2m"]] = None  # FLUX.1 only
    # FLUX.2 & Kontext parameters (only used if model supports them)
    flux_guidance_scale: Optional[float] = None  # dev: 0-20 (default 2.5), flex: 1.5-10 (default 3.5), kontext: 0-20 (default 3.5)
    flux_num_inference_steps: Optional[int] = None  # dev/flex/kontext only, default 28
    flux_seed: Optional[int] = None  # For reproducibility
    flux_image_urls: Optional[List[str]] = None  # Multi-reference: dev(4), pro(9), flex/max(10)
    flux_output_format: Literal["png", "jpeg", "webp"] = "png"
    flux_enable_safety_checker: bool = False  # Set false for NSFW
    flux_enable_prompt_expansion: Optional[bool] = None  # dev/flex only (flex defaults true)
    flux_safety_tolerance: Optional[Literal["1", "2", "3", "4", "5"]] = None  # pro/flex/max only ("5" = most permissive)
    flux_acceleration: Optional[Literal["none", "regular", "high"]] = None  # dev only


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

    model: ImageModelType = "gpt-image-1.5"
    images_per_prompt: int = 1
    set_mode: Optional[I2ISetMode] = None
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"
    # FLUX.1 parameters (flux-general only)
    flux_strength: Optional[float] = None  # 0.0-1.0, default 0.75
    flux_scheduler: Optional[Literal["euler", "dpmpp_2m"]] = None  # FLUX.1 only
    # FLUX.2 & Kontext parameters
    flux_guidance_scale: Optional[float] = None  # dev/flex/kontext only
    flux_num_inference_steps: Optional[int] = None  # dev/flex/kontext only
    flux_seed: Optional[int] = None
    flux_image_urls: Optional[List[str]] = None  # Multi-ref for dev/pro/flex/max
    flux_output_format: Literal["png", "jpeg", "webp"] = "png"
    flux_enable_safety_checker: bool = False
    flux_enable_prompt_expansion: Optional[bool] = None  # dev/flex only
    flux_safety_tolerance: Optional[Literal["1", "2", "3", "4", "5"]] = None  # pro/flex/max
    flux_acceleration: Optional[Literal["none", "regular", "high"]] = None  # dev only


class I2VConfig(BaseModel):
    """Config for I2V step."""

    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "wan26",
        "kling",
        "kling-master",
        "kling-standard",
        "kling26-pro",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
        "luma",
        "luma-ray2",
        "cogvideox",
        "stable-video",
        # Self-hosted
        "vastai-wan22-i2v",
        "pinokio-wan22-i2v",
        "pinokio-hunyuan-i2v",
    ] = "kling"
    videos_per_image: int = 1
    resolution: Literal["480p", "576p", "580p", "720p", "1080p"] = "1080p"
    duration_sec: Literal[5, 10, 15] = 5  # 15s supported by Wan 2.6

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
    intensity: Literal["subtle", "moderate", "wild"] = "moderate"


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
    model: ImageModelType = "gpt-image-1.5"
    images_per_prompt: int = 1
    aspect_ratio: Literal["1:1", "9:16", "16:9", "4:3", "3:4"] = "9:16"
    quality: Literal["low", "medium", "high"] = "high"
    negative_prompt: Optional[str] = None  # User additions - baseline is always appended in backend
    # FLUX.1 parameters (flux-general only)
    flux_strength: Optional[float] = None  # 0.0-1.0, default 0.75
    flux_scheduler: Optional[Literal["euler", "dpmpp_2m"]] = None  # FLUX.1 only
    # FLUX.2 & Kontext parameters (only used if model supports them)
    flux_guidance_scale: Optional[float] = None  # dev/flex/kontext only
    flux_num_inference_steps: Optional[int] = None  # dev/flex/kontext only
    flux_seed: Optional[int] = None  # For reproducibility
    flux_image_urls: Optional[List[str]] = None  # Multi-ref: dev(4), pro(9), flex/max(10)
    flux_output_format: Literal["png", "jpeg", "webp"] = "png"
    flux_enable_safety_checker: bool = False  # Set false for NSFW
    flux_enable_prompt_expansion: Optional[bool] = None  # dev/flex only
    flux_safety_tolerance: Optional[Literal["1", "2", "3", "4", "5"]] = None  # pro/flex/max ("5" = most permissive)
    flux_acceleration: Optional[Literal["none", "regular", "high"]] = None  # dev only


class BulkI2VConfig(BaseModel):
    """Config for bulk I2V generation."""

    prompts: List[str]  # 1-10 motion prompts
    model: Literal[
        "wan",
        "wan21",
        "wan22",
        "wan-pro",
        "wan26",
        "kling",
        "kling-master",
        "kling-standard",
        "kling26-pro",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
        "luma",
        "luma-ray2",
        "cogvideox",
        "stable-video",
        # Self-hosted
        "vastai-wan22-i2v",
        "pinokio-wan22-i2v",
        "pinokio-hunyuan-i2v",
    ] = "kling"
    resolution: Literal["480p", "576p", "720p", "1080p"] = "1080p"
    duration_sec: int = 5  # Model-specific: Kling 5/10, Veo 4/6/8, Sora 4/8/12, Wan26 5/10/15
    negative_prompt: Optional[str] = None
    enable_audio: bool = False  # Veo/Kling26 models - adds audio (costs 1.5-2x more)


class BulkPipelineCreate(BaseModel):
    """Schema for creating a bulk pipeline."""

    name: str = "Bulk Generation"
    source_images: List[str]  # 1-10 image URLs
    i2i_config: Optional[BulkI2IConfig] = None  # Optional: skip to go straight to video
    i2v_config: Optional[BulkI2VConfig] = None  # Optional: skip video generation
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
        "wan26",
        "kling",
        "kling-master",
        "kling-standard",
        "kling26-pro",
        "veo2",
        "veo31-fast",
        "veo31",
        "veo31-flf",
        "veo31-fast-flf",
        "sora-2",
        "sora-2-pro",
        "luma",
        "luma-ray2",
        "cogvideox",
        "stable-video",
    ] = "kling"
    resolution: Literal["480p", "576p", "720p", "1080p"] = "1080p"
    duration_sec: int = 5  # Model-specific: Kling 5/10, Veo 4/6/8, Sora 4/8/12, Wan26 5/10/15
    negative_prompt: Optional[str] = None
    enable_audio: bool = False  # Veo/Kling26 models
    name: str = "Animate Selected"


# ============== Prompt Generator Schemas ==============


class PromptGeneratorRequest(BaseModel):
    """Request to generate i2i prompts with on-screen captions."""

    count: int = 10  # 1-50 prompts
    style: Literal["cosplay", "cottagecore", "gym", "bookish", "nurse"] = "cosplay"
    location: Literal["outdoor", "indoor", "mixed"] = "mixed"
    bust_size: Literal["none", "subtle", "moderate", "exaggerated"] = "none"  # Bust enhancement level
    preserve_identity: bool = True  # Add "preserving her exact facial features" to prompts
    framing: Literal["close", "medium", "full"] = "medium"  # close=face/shoulders, medium=waist up, full=head to toe
    realism_preset: Literal["default", "phone_grainy", "harsh_flash", "film_aesthetic", "selfie", "candid"] = "default"


class PromptGeneratorResponse(BaseModel):
    """Response with generated prompts."""

    prompts: List[str]
    count: int
    style: str
    location: str
    framing: str = "medium"
    realism_preset: str = "default"
