"""SwarmUI video generation endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl, Field
import structlog

from app.config import settings
from app.services.swarmui_client import (
    SwarmUIClient,
    SwarmUIError,
    SwarmUIGenerationError,
    get_swarmui_client,
)
from app.services.r2_cache import cache_video
from app.routers.gpu_config import get_swarmui_url

logger = structlog.get_logger()

router = APIRouter(prefix="/swarm", tags=["swarm"])


class VideoGenerateRequest(BaseModel):
    """Request to generate video from image using SwarmUI."""

    image_url: HttpUrl = Field(..., description="URL of the source image")
    prompt: str = Field(..., max_length=2000, description="Motion/content prompt")
    negative_prompt: str = Field(
        default="low quality, blurry, distorted, watermark",
        max_length=1000,
    )
    num_frames: int = Field(
        default=81,
        ge=17,
        le=257,
        description="Number of frames (81 = ~3.4s at 24fps)",
    )
    fps: int = Field(default=24, ge=8, le=60, description="Output frame rate")
    steps: int = Field(default=4, ge=1, le=50, description="Sampling steps")
    cfg_scale: float = Field(
        default=1.0,
        ge=0.1,
        le=20.0,
        description="CFG scale (1.0-3.5 for Wan I2V)",
    )
    seed: int = Field(default=-1, description="Random seed (-1 for random)")
    model: str | None = Field(
        default=None,
        description="Video model name (uses config default if not specified)",
    )
    lora: str | None = Field(
        default=None,
        description="LoRA name (uses config default if not specified)",
    )
    lora_strength: float = Field(default=1.0, ge=0.0, le=2.0)


class VideoGenerateResponse(BaseModel):
    """Response from video generation."""

    video_url: str = Field(..., description="Public URL of the generated video")
    seed: int = Field(..., description="Seed used for generation")
    model: str = Field(..., description="Model used")
    frames: int = Field(..., description="Number of frames generated")


class HealthResponse(BaseModel):
    """SwarmUI health check response."""

    status: str
    swarmui_url: str
    available: bool


async def get_client() -> SwarmUIClient:
    """Dependency to get SwarmUI client using runtime config URL."""
    # Use runtime config URL (can be updated via /api/gpu/config)
    swarmui_url = get_swarmui_url()
    return get_swarmui_client(swarmui_url)


@router.get("/health", response_model=HealthResponse)
async def health_check(client: SwarmUIClient = Depends(get_client)) -> HealthResponse:
    """Check if SwarmUI is running and accessible."""
    available = await client.health_check()
    swarmui_url = get_swarmui_url()

    return HealthResponse(
        status="ok" if available else "unavailable",
        swarmui_url=swarmui_url,
        available=available,
    )


@router.post("/generate-video", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    client: SwarmUIClient = Depends(get_client),
) -> VideoGenerateResponse:
    """
    Generate a video from an image using SwarmUI.

    This endpoint:
    1. Uploads the source image to SwarmUI
    2. Generates video using Wan 2.2 I2V model
    3. Caches the result to R2
    4. Returns the public video URL
    """
    # Use config defaults if not specified
    model = request.model or settings.swarmui_model
    lora = request.lora or settings.swarmui_lora

    logger.info(
        "Starting SwarmUI video generation",
        image_url=str(request.image_url)[:80],
        model=model,
        frames=request.num_frames,
    )

    try:
        # Step 1: Upload image to SwarmUI
        image_path = await client.upload_image(str(request.image_url))

        # Step 2: Generate video
        result = await client.generate_video(
            image_path=image_path,
            prompt=request.prompt,
            model=model,
            num_frames=request.num_frames,
            fps=request.fps,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            lora=lora,
            lora_strength=request.lora_strength,
        )

        video_url = result.get("video_url")
        if not video_url:
            raise SwarmUIGenerationError("No video URL in result")

        # Step 3: Cache to R2
        logger.debug("Caching video to R2", source_url=video_url[:80])

        try:
            # Download video bytes from SwarmUI
            video_bytes = await client.get_video_bytes(result["video_path"])

            # Cache to R2
            cached_url = await cache_video(
                video_url,
                video_bytes=video_bytes,
            )

            if cached_url:
                video_url = cached_url
                logger.info("Video cached to R2", url=cached_url[:80])
            else:
                logger.warning("R2 caching failed, using SwarmUI URL directly")

        except Exception as e:
            logger.warning("Failed to cache video to R2", error=str(e))
            # Continue with SwarmUI URL if caching fails

        return VideoGenerateResponse(
            video_url=video_url,
            seed=result.get("seed", request.seed),
            model=model,
            frames=request.num_frames,
        )

    except SwarmUIGenerationError as e:
        logger.error("Video generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    except SwarmUIError as e:
        logger.error("SwarmUI error", error=str(e))
        raise HTTPException(status_code=502, detail=f"SwarmUI error: {e}")

    except Exception as e:
        logger.exception("Unexpected error in video generation")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@router.get("/models")
async def list_models() -> dict:
    """List available video models and current configuration."""
    return {
        "default_model": settings.swarmui_model,
        "default_lora": settings.swarmui_lora,
        "default_settings": {
            "steps": settings.swarmui_default_steps,
            "cfg_scale": settings.swarmui_default_cfg,
            "frames": settings.swarmui_default_frames,
            "fps": settings.swarmui_default_fps,
        },
        "swarmui_url": get_swarmui_url(),  # Use runtime config
    }
