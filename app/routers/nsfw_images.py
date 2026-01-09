"""NSFW image generation endpoints using vast.ai GPU + ComfyUI."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

from app.services.nsfw_image_executor import (
    generate_nsfw_image,
    get_nsfw_executor,
    NSFW_MODELS,
    NSFWModelType,
)
from app.services.comfyui_workflows import NSFW_PRESETS

router = APIRouter(prefix="/nsfw-images", tags=["NSFW Image Generation"])


class NSFWImageRequest(BaseModel):
    """Request to generate an NSFW image."""
    source_image_url: str = Field(..., description="URL of the source image")
    prompt: str = Field(..., description="Generation prompt")
    model: NSFWModelType = Field(default="pony-v6", description="Model to use")
    negative_prompt: str | None = Field(default=None, description="Negative prompt")
    preset: str | None = Field(default=None, description="Preset configuration")
    denoise: float = Field(default=0.65, ge=0.0, le=1.0, description="Denoising strength")
    steps: int = Field(default=25, ge=10, le=50, description="Sampling steps")
    cfg: float = Field(default=7.0, ge=1.0, le=15.0, description="CFG scale")
    width: int = Field(default=832, ge=512, le=1536, description="Output width")
    height: int = Field(default=1216, ge=512, le=1536, description="Output height")
    lora_name: str | None = Field(default=None, description="Optional LoRA name")
    lora_strength: float = Field(default=0.8, ge=0.0, le=1.5, description="LoRA strength")
    seed: int = Field(default=-1, description="Random seed (-1 for random)")


class NSFWImageResponse(BaseModel):
    """Response from NSFW image generation."""
    status: Literal["completed", "failed", "pending"]
    result_url: str | None = None
    error_message: str | None = None
    generation_time: float | None = None
    model: str
    seed: int | None = None


class NSFWModelsResponse(BaseModel):
    """Available NSFW models."""
    models: dict


class NSFWPresetsResponse(BaseModel):
    """Available NSFW presets."""
    presets: dict


class NSFWStatusResponse(BaseModel):
    """Status of NSFW generation service."""
    available: bool
    vast_api_configured: bool
    warm_instances: int
    models_available: list[str]
    presets_available: list[str]


@router.get("/status", response_model=NSFWStatusResponse)
async def get_status() -> NSFWStatusResponse:
    """
    Check if NSFW image generation is available.

    Returns configuration status and available models.
    """
    import os

    vast_configured = bool(os.getenv("VASTAI_API_KEY"))
    executor = get_nsfw_executor()

    # Count running instances
    instances = await executor.vast_client.list_instances()
    running_count = len([i for i in instances if i.status == "running"])

    return NSFWStatusResponse(
        available=vast_configured,
        vast_api_configured=vast_configured,
        warm_instances=running_count,
        models_available=list(NSFW_MODELS.keys()),
        presets_available=list(NSFW_PRESETS.keys()),
    )


@router.get("/models", response_model=NSFWModelsResponse)
async def get_models() -> NSFWModelsResponse:
    """
    List available NSFW models.

    Each model has different characteristics for anime vs realistic content.
    """
    return NSFWModelsResponse(models=NSFW_MODELS)


@router.get("/presets", response_model=NSFWPresetsResponse)
async def get_presets() -> NSFWPresetsResponse:
    """
    List available generation presets.

    Presets are pre-configured settings optimized for different styles.
    """
    return NSFWPresetsResponse(presets=NSFW_PRESETS)


@router.post("/generate", response_model=NSFWImageResponse)
async def generate_image(request: NSFWImageRequest) -> NSFWImageResponse:
    """
    Generate an NSFW image from a source image.

    This endpoint:
    1. Spins up a GPU instance on vast.ai (or reuses warm instance)
    2. Uploads source image to ComfyUI
    3. Runs img2img with specified model/settings
    4. Returns the generated image URL

    **Pricing**: ~$0.10-0.30 per image depending on model and GPU rental rates.

    **Timing**:
    - Cold start (new instance): 2-5 minutes
    - Warm instance: 30-60 seconds
    """
    from app.config import settings

    # Check if vast.ai is configured
    if not getattr(settings, 'vast_api_key', None):
        raise HTTPException(
            status_code=503,
            detail="NSFW image generation requires VAST_API_KEY to be configured"
        )

    result = await generate_nsfw_image(
        source_image_url=request.source_image_url,
        prompt=request.prompt,
        model=request.model,
        negative_prompt=request.negative_prompt,
        preset=request.preset,
        denoise=request.denoise,
        steps=request.steps,
        cfg=request.cfg,
        width=request.width,
        height=request.height,
        lora_name=request.lora_name,
        lora_strength=request.lora_strength,
        seed=request.seed,
    )

    return NSFWImageResponse(**result)


# Job-based async generation (for longer operations)
# Stores jobs in memory for simplicity - use Redis/DB in production

_pending_jobs: dict[str, dict] = {}


class NSFWJobSubmitResponse(BaseModel):
    """Response from submitting an async NSFW job."""
    job_id: str
    status: str = "pending"
    message: str = "Job submitted successfully"


class NSFWJobStatusResponse(BaseModel):
    """Status of an async NSFW job."""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


@router.post("/submit", response_model=NSFWJobSubmitResponse)
async def submit_job(
    request: NSFWImageRequest,
    background_tasks: BackgroundTasks,
) -> NSFWJobSubmitResponse:
    """
    Submit an NSFW image generation job asynchronously.

    Use this for batch operations or when you don't want to wait.
    Poll /jobs/{job_id} for status.
    """
    from app.config import settings
    import uuid

    if not getattr(settings, 'vast_api_key', None):
        raise HTTPException(
            status_code=503,
            detail="NSFW image generation requires VAST_API_KEY"
        )

    job_id = str(uuid.uuid4())

    # Store job
    _pending_jobs[job_id] = {
        "status": "pending",
        "request": request.model_dump(),
        "created_at": datetime.utcnow(),
        "result": None,
    }

    # Run in background
    async def run_job():
        _pending_jobs[job_id]["status"] = "running"
        try:
            result = await generate_nsfw_image(
                source_image_url=request.source_image_url,
                prompt=request.prompt,
                model=request.model,
                negative_prompt=request.negative_prompt,
                preset=request.preset,
                denoise=request.denoise,
                steps=request.steps,
                cfg=request.cfg,
                width=request.width,
                height=request.height,
                lora_name=request.lora_name,
                lora_strength=request.lora_strength,
                seed=request.seed,
            )
            _pending_jobs[job_id]["status"] = result["status"]
            _pending_jobs[job_id]["result"] = result
            _pending_jobs[job_id]["completed_at"] = datetime.utcnow()
        except Exception as e:
            _pending_jobs[job_id]["status"] = "failed"
            _pending_jobs[job_id]["result"] = {"error_message": str(e)}
            _pending_jobs[job_id]["completed_at"] = datetime.utcnow()

    background_tasks.add_task(run_job)

    return NSFWJobSubmitResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=NSFWJobStatusResponse)
async def get_job_status(job_id: str) -> NSFWJobStatusResponse:
    """Get the status of an async NSFW generation job."""
    if job_id not in _pending_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _pending_jobs[job_id]
    result = job.get("result", {}) or {}

    return NSFWJobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result_url=result.get("result_url"),
        error_message=result.get("error_message"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )
