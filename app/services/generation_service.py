"""
Service to dispatch generation jobs to the correct provider (Fal, Vast.ai, Pinokio).
Provider is determined automatically based on model selection.
"""
import asyncio
from typing import Optional, List
import structlog

from app.models import BatchJobItem
from app.services.vastai_orchestrator import get_vastai_orchestrator
from app import fal_client
from app import image_client
from app.schemas import is_vastai_model, is_pinokio_model
from app.config import settings

logger = structlog.get_logger()


# ============== Pipeline-facing API ==============
# These functions are used by pipelines.py for bulk/pipeline operations


async def generate_image(
    image_url: str,
    prompt: str,
    model: str = "flux-general",
    aspect_ratio: str = "16:9",
    quality: str = "medium",
    num_images: int = 1,
    negative_prompt: Optional[str] = None,
    flux_strength: Optional[float] = None,
    flux_guidance_scale: Optional[float] = None,
    flux_num_inference_steps: Optional[int] = None,
    flux_seed: Optional[int] = None,
    flux_scheduler: Optional[str] = None,
    flux_image_urls: Optional[List[str]] = None,
    flux_enable_safety_checker: Optional[bool] = None,
    flux_enable_prompt_expansion: Optional[bool] = None,
    flux_safety_tolerance: Optional[str] = None,
    flux_acceleration: Optional[str] = None,
    flux_output_format: Optional[str] = None,
) -> List[str]:
    """Generate image(s) using fal.ai image models.

    Returns a list of generated image URLs.

    Used by: app.routers.pipelines
    """
    logger.info("generate_image called", model=model, prompt=prompt[:50] if prompt else "")

    try:
        request_id = await image_client.submit_image_job(
            model=model,
            image_url=image_url,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            num_images=num_images,
            negative_prompt=negative_prompt,
            flux_strength=flux_strength,
            flux_guidance_scale=flux_guidance_scale,
            flux_num_inference_steps=flux_num_inference_steps,
            flux_seed=flux_seed,
            flux_scheduler=flux_scheduler,
            flux_image_urls=flux_image_urls,
            flux_output_format=flux_output_format or "png",
            flux_enable_safety_checker=flux_enable_safety_checker,
            flux_enable_prompt_expansion=flux_enable_prompt_expansion,
            flux_safety_tolerance=flux_safety_tolerance,
            flux_acceleration=flux_acceleration,
        )

        # Poll for completion (5 min max)
        for _ in range(60):
            await asyncio.sleep(5)
            result = await image_client.get_image_result(model=model, request_id=request_id)

            if result["status"] == "completed":
                urls = result.get("image_urls", [])
                if urls:
                    logger.info("Image generation completed", model=model, count=len(urls))
                    return urls
                else:
                    raise Exception("Image generation completed but no URLs returned")

            elif result["status"] == "failed":
                error_msg = result.get("error_message", "Unknown error")
                raise Exception(f"Image generation failed: {error_msg}")

        raise TimeoutError("Image generation timed out after 5 minutes")

    except Exception as e:
        logger.error("Image generation failed", model=model, error=str(e))
        raise


async def generate_video(
    image_url: str,
    prompt: str,
    model: str = "kling",
    resolution: str = "1080p",
    duration_sec: int = 5,
    enable_audio: bool = False,
    negative_prompt: Optional[str] = None,
) -> str:
    """Generate video using fal.ai video models.

    Returns the generated video URL.

    Used by: app.routers.pipelines
    """
    logger.info("generate_video called", model=model, prompt=prompt[:50] if prompt else "")

    try:
        request_id = await fal_client.submit_job(
            model=model,
            image_url=image_url,
            motion_prompt=prompt,
            resolution=resolution,
            duration_sec=duration_sec,
            negative_prompt=negative_prompt,
            enable_audio=enable_audio,
        )

        # Poll for completion (10 min max)
        for _ in range(120):
            await asyncio.sleep(5)
            result = await fal_client.get_job_result(model=model, request_id=request_id)

            if result["status"] == "completed":
                video_url = result.get("video_url")
                if video_url:
                    logger.info("Video generation completed", model=model, url=video_url[:50])
                    return video_url
                else:
                    raise Exception("Video generation completed but no URL returned")

            elif result["status"] == "failed":
                error_msg = result.get("error_message", "Unknown error")
                raise Exception(f"Video generation failed: {error_msg}")

        raise TimeoutError("Video generation timed out after 10 minutes")

    except Exception as e:
        logger.error("Video generation failed", model=model, error=str(e))
        raise


# ============== Batch Queue API ==============
# These functions are used by the batch queue for automated processing

async def _run_fal_job_and_wait(item: BatchJobItem, config: dict) -> str:
    """
    Runs a job on Fal.ai and polls until completion.
    Returns the final video URL.
    """
    logger.info("Dispatching job to Fal.ai", item_id=item.id, config=config)

    # Extract parameters for fal_client
    # This part needs to be robust to handle different expected keys
    # For now, we assume a simple mapping.
    # TODO: Create a more robust mapping from generic config to provider-specific params.
    model = config.get("model", "kling")
    # A default image_url is needed if not in the item
    # This might come from a parent job or a template in a real scenario
    image_url = item.get_variation_params().get("image_url", "https://example.com/placeholder.jpg")
    motion_prompt = item.prompt or "A gentle breeze"
    
    # These might not always be present, provide defaults
    resolution = config.get("resolution", "1080p")
    duration_sec = config.get("duration_sec", 5)
    negative_prompt = config.get("negative_prompt")
    enable_audio = config.get("enable_audio", False)

    try:
        request_id = await fal_client.submit_job(
            model=model,
            image_url=image_url,
            motion_prompt=motion_prompt,
            resolution=resolution,
            duration_sec=duration_sec,
            negative_prompt=negative_prompt,
            enable_audio=enable_audio,
        )

        # Poll for completion
        for _ in range(120):  # Max wait time of 10 minutes (120 * 5s)
            await asyncio.sleep(5)
            result = await fal_client.get_job_result(model=model, request_id=request_id)
            
            if result["status"] == "completed":
                if result.get("video_url"):
                    logger.info("Fal.ai job completed", item_id=item.id, video_url=result["video_url"])
                    return result["video_url"]
                else:
                    raise Exception("Fal.ai job completed but no video URL was returned.")
            
            elif result["status"] == "failed":
                error_message = result.get("error_message", "Unknown error from Fal.ai")
                raise Exception(f"Fal.ai job failed: {error_message}")
        
        raise TimeoutError("Fal.ai job timed out after 10 minutes.")

    except Exception as e:
        logger.error("Fal.ai job processing failed", item_id=item.id, error=str(e))
        raise


async def _run_pinokio_job(item: BatchJobItem, config: dict) -> str:
    """
    Runs a job on Pinokio WAN GP.
    Returns the final video URL (R2).

    Source: .taskmaster/docs/pinokio-integration-prd.txt
    """
    from app.services.pinokio_client import PinokioClient, PinokioAPIError

    logger.info("Dispatching job to Pinokio WAN GP", item_id=item.id, config=config)

    if not settings.pinokio_wan_url:
        raise Exception("Pinokio not configured. Set PINOKIO_WAN_URL in .env")

    # Extract parameters
    variation_params = item.get_variation_params() if hasattr(item, 'get_variation_params') else {}
    image_url = variation_params.get("image_url", config.get("image_url"))

    if not image_url:
        raise Exception("No image_url provided for I2V generation")

    prompt = item.prompt or config.get("motion_prompt", "A gentle motion")

    # Get Pinokio-specific config
    pinokio_config = config.get("pinokio_config", {})
    steps = pinokio_config.get("steps", 4)
    frames = pinokio_config.get("frames", 81)
    cfg_scale = pinokio_config.get("cfg_scale", 5.0)
    seed = pinokio_config.get("seed", -1)

    # Map model name to WAN GP model
    model = config.get("model", "pinokio-wan22-i2v")
    model_short = model.replace("pinokio-", "")

    try:
        client = PinokioClient(
            base_url=settings.pinokio_wan_url,
            ssh_config=settings.pinokio_ssh_config
        )

        result = await client.generate_video(
            image_url=image_url,
            prompt=prompt,
            model=model_short,
            frames=frames,
            steps=steps,
            seed=seed,
            guidance_scale=cfg_scale,
        )

        if result.get("status") == "completed" and result.get("video_url"):
            logger.info("Pinokio job completed", item_id=item.id, video_url=result["video_url"][:50])
            return result["video_url"]
        else:
            error_msg = result.get("error_message", "Unknown error from Pinokio")
            raise Exception(f"Pinokio job failed: {error_msg}")

    except PinokioAPIError as e:
        logger.error("Pinokio API error", item_id=item.id, error=str(e))
        raise Exception(f"Pinokio API error: {e}")
    except Exception as e:
        logger.error("Pinokio job processing failed", item_id=item.id, error=str(e))
        raise


async def dispatch_generation(item: BatchJobItem, config: dict) -> str:
    """
    The main generation_fn for the BatchQueue.
    Provider is determined automatically based on the model name.
    - Models starting with 'vastai-' go to Vast.ai
    - Models starting with 'pinokio-' go to Pinokio WAN GP
    - All other models go to fal.ai
    """
    model = config.get("model", "kling")

    # Determine provider based on model (not from config)
    if is_vastai_model(model):
        provider = "vastai"
    elif is_pinokio_model(model):
        provider = "pinokio"
    else:
        provider = "fal"

    logger.info("Dispatching generation job", item_id=item.id, provider=provider, model=model)

    if provider == "vastai":
        orchestrator = get_vastai_orchestrator()
        result_dict = await orchestrator.generation_fn(item=item, **config)
        if result_dict.get("status") == "completed" and result_dict.get("video_url"):
            return result_dict["video_url"]
        else:
            error_msg = result_dict.get("error_message", "Unknown error from VastAI")
            raise Exception(f"Vast.ai job failed: {error_msg}")

    elif provider == "pinokio":
        return await _run_pinokio_job(item, config)

    else:  # fal.ai (default)
        return await _run_fal_job_and_wait(item, config)