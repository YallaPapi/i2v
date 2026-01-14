"""SwarmUI video generation endpoints."""

import os
import tempfile
import asyncio
from pathlib import Path

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

logger = structlog.get_logger()


def get_swarmui_url() -> str:
    """Get SwarmUI URL from settings."""
    return settings.swarmui_url or "http://localhost:7801"

# Import post-processing (relative to project root)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "caption_overlay"))
from post_process import post_process_video

router = APIRouter(prefix="/swarm", tags=["swarm"])


class VideoGenerateRequest(BaseModel):
    """Request to generate video from image using SwarmUI with Wan 2.2 I2V."""

    image_url: HttpUrl = Field(..., description="URL of the source image")
    prompt: str = Field(..., max_length=2000, description="Motion/content prompt")
    negative_prompt: str = Field(
        default="blurry, jerky motion, stuttering, flickering, frame skipping, ghosting, motion blur, extra fingers, extra hands, extra limbs, missing fingers, missing limbs, deformed hands, mutated hands, fused fingers, bad anatomy, disfigured, malformed, distorted face, ugly, low quality, worst quality, logo, duplicate frames, static, frozen, morphing, warping, glitching, plastic skin",
        max_length=2000,
    )
    num_frames: int = Field(
        default=80,
        ge=17,
        le=257,
        description="Number of frames (80 default for Wan 2.2)",
    )
    fps: int = Field(default=16, ge=8, le=60, description="Output frame rate")
    steps: int = Field(default=10, ge=1, le=50, description="Image gen steps")
    cfg_scale: float = Field(
        default=7.0,
        ge=0.1,
        le=20.0,
        description="Image gen CFG scale",
    )
    seed: int = Field(default=-1, description="Random seed (-1 for random)")
    model: str | None = Field(
        default=None,
        description="High-noise video model (uses config default if not specified)",
    )
    swap_model: str | None = Field(
        default=None,
        description="Low-noise model to swap at swap_percent (uses config default)",
    )
    swap_percent: float = Field(default=0.6, ge=0.0, le=1.0, description="When to swap models (0.6 = 60%)")

    # LoRAs with section confinement (exact from working metadata)
    lora_high: str | None = Field(
        default=None,
        description="Lightning LoRA for high-noise model (cid=2)",
    )
    lora_low: str | None = Field(
        default=None,
        description="Lightning LoRA for low-noise swap model (cid=3)",
    )

    # Advanced Wan 2.2 I2V parameters
    video_steps: int = Field(default=5, ge=1, le=50, description="Video diffusion steps (5 with lightning LoRA)")
    video_cfg: float = Field(default=1.0, ge=0.1, le=20.0, description="Video CFG scale (1.0 for Wan)")
    interpolation_method: str = Field(default="RIFE", description="Frame interpolation method")
    interpolation_multiplier: int = Field(default=2, ge=1, le=4, description="Interpolation factor (2x frames)")
    video_resolution: str = Field(default="Image Aspect, Model Res", description="Video resolution mode")
    video_format: str = Field(default="h264-mp4", description="Output video format")
    width: int = Field(default=720, ge=256, le=1920, description="Output width")
    height: int = Field(default=1280, ge=256, le=1920, description="Output height")

    # Post-processing options
    caption: str | None = Field(default=None, description="Caption text for post-processing overlay")
    apply_spoof: bool = Field(default=False, description="Apply spoofing transforms")


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
    2. Generates video using Wan 2.2 I2V model with advanced params
    3. Optionally applies post-processing (caption overlay, spoof)
    4. Caches the result to R2
    5. Returns the public video URL
    """
    # Use config defaults if not specified
    model = request.model or settings.swarmui_model
    swap_model = request.swap_model or settings.swarmui_swap_model
    lora_high = request.lora_high or settings.swarmui_lora_high
    lora_low = request.lora_low or settings.swarmui_lora_low

    # Build LoRA arrays with section confinement
    loras = [lora_high, lora_low]
    lora_weights = ["1", "1"]
    lora_section_confinement = ["2", "3"]  # cid=2 for video, cid=3 for videoswap

    logger.info(
        "Starting SwarmUI video generation",
        image_url=str(request.image_url)[:80],
        model=model,
        swap_model=swap_model,
        frames=request.num_frames,
        video_steps=request.video_steps,
        video_cfg=request.video_cfg,
        caption=request.caption[:30] if request.caption else None,
    )

    try:
        # Step 1: Upload image to SwarmUI (converts to base64 data URI)
        image_path = await client.upload_image(str(request.image_url))

        # Step 2: Generate video with EXACT Wan 2.2 I2V params from working metadata
        result = await client.generate_video(
            image_path=image_path,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            model=model,
            num_frames=request.num_frames,
            fps=request.fps,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            # Wan 2.2 I2V specific parameters
            video_steps=request.video_steps,
            video_cfg=request.video_cfg,
            swap_model=swap_model,
            swap_percent=request.swap_percent,
            interpolation_method=request.interpolation_method,
            interpolation_multiplier=request.interpolation_multiplier,
            video_resolution=request.video_resolution,
            video_format=request.video_format,
            width=request.width,
            height=request.height,
            # LoRAs with section confinement
            loras=loras,
            lora_weights=lora_weights,
            lora_section_confinement=lora_section_confinement,
        )

        video_url = result.get("video_url")
        if not video_url:
            raise SwarmUIGenerationError("No video URL in result")

        # Step 3: Download video bytes from SwarmUI
        logger.debug("Downloading video from SwarmUI", path=result["video_path"])
        video_bytes = await client.get_video_bytes(result["video_path"])

        # Step 4: Post-processing (caption overlay + spoof) if requested
        if request.caption or request.apply_spoof:
            logger.info(
                "Applying post-processing",
                caption=bool(request.caption),
                spoof=request.apply_spoof,
            )

            # Save raw video to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as raw_file:
                raw_file.write(video_bytes)
                raw_path = raw_file.name

            # Create output temp file
            processed_path = tempfile.mktemp(suffix="_processed.mp4")

            try:
                # Run post-processing in thread pool (blocking ffmpeg call)
                loop = asyncio.get_event_loop()
                pp_result = await loop.run_in_executor(
                    None,
                    lambda: post_process_video(
                        input_path=raw_path,
                        output_path=processed_path,
                        caption=request.caption,
                        apply_spoof=request.apply_spoof,
                        use_nvenc=False,  # Use software encoding for portability
                    )
                )

                if pp_result.get("success"):
                    # Read processed video
                    with open(processed_path, "rb") as f:
                        video_bytes = f.read()
                    logger.info("Post-processing complete", result=pp_result)
                else:
                    logger.warning("Post-processing failed", error=pp_result.get("error"))
                    # Continue with original video

            finally:
                # Cleanup temp files
                try:
                    os.remove(raw_path)
                except:
                    pass
                try:
                    os.remove(processed_path)
                except:
                    pass

        # Step 5: Cache to R2
        logger.debug("Caching video to R2")

        try:
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
    """List available video models and current configuration (Wan 2.2 I2V)."""
    return {
        "models": {
            "high_noise": settings.swarmui_model,
            "low_noise_swap": settings.swarmui_swap_model,
        },
        "loras": {
            "high_noise_lora": settings.swarmui_lora_high,
            "low_noise_lora": settings.swarmui_lora_low,
            "section_confinement": ["2", "3"],  # cid=2 for video, cid=3 for videoswap
        },
        "default_settings": {
            "steps": settings.swarmui_default_steps,
            "cfg_scale": settings.swarmui_default_cfg,
            "frames": settings.swarmui_default_frames,
            "fps": settings.swarmui_default_fps,
            "video_steps": settings.swarmui_video_steps,
            "video_cfg": settings.swarmui_video_cfg,
            "swap_percent": settings.swarmui_swap_percent,
        },
        "swarmui_url": get_swarmui_url(),
    }
