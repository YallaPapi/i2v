"""Generation service for pipeline execution - wraps fal_client and image_client."""

import asyncio
from typing import List, Optional
import structlog

from app.fal_client import submit_job, get_job_result, MODELS as VIDEO_MODELS
from app.image_client import submit_image_job, get_image_result, IMAGE_MODELS

logger = structlog.get_logger()

# Poll interval and timeout for job completion
POLL_INTERVAL_SECONDS = 3
MAX_POLL_TIME_SECONDS = 600  # 10 minutes max per job


async def wait_for_video_completion(model: str, request_id: str) -> dict:
    """Poll for video job completion."""
    elapsed = 0
    while elapsed < MAX_POLL_TIME_SECONDS:
        result = await get_job_result(model, request_id)

        if result["status"] == "completed":
            return result
        elif result["status"] == "failed":
            raise Exception(result.get("error_message", "Video generation failed"))

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise Exception(f"Video generation timed out after {MAX_POLL_TIME_SECONDS}s")


async def wait_for_image_completion(model: str, request_id: str) -> dict:
    """Poll for image job completion."""
    elapsed = 0
    while elapsed < MAX_POLL_TIME_SECONDS:
        result = await get_image_result(model, request_id)

        if result["status"] == "completed":
            return result
        elif result["status"] == "failed":
            raise Exception(result.get("error_message", "Image generation failed"))

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise Exception(f"Image generation timed out after {MAX_POLL_TIME_SECONDS}s")


async def generate_video(
    image_url: str,
    prompt: str,
    model: str = "kling",
    resolution: str = "1080p",
    duration_sec: int = 5,
    negative_prompt: Optional[str] = None,
    enable_audio: bool = False,
) -> str:
    """
    Generate a single video from an image.

    Returns the video URL.
    """
    logger.info(
        "Generating video",
        model=model,
        image_url=image_url[:50],
        enable_audio=enable_audio,
    )

    # Validate model
    if model not in VIDEO_MODELS:
        raise ValueError(
            f"Unknown video model: {model}. Available: {list(VIDEO_MODELS.keys())}"
        )

    # Submit job
    request_id = await submit_job(
        model=model,
        image_url=image_url,
        motion_prompt=prompt,
        resolution=resolution,
        duration_sec=duration_sec,
        negative_prompt=negative_prompt,
        enable_audio=enable_audio,
    )

    # Wait for completion
    result = await wait_for_video_completion(model, request_id)

    if not result.get("video_url"):
        raise Exception("No video URL in completed result")

    logger.info("Video generated", model=model, url=result["video_url"][:50])
    return result["video_url"]


async def generate_image(
    image_url: str,
    prompt: str,
    model: str = "gpt-image-1.5",
    aspect_ratio: str = "9:16",
    quality: str = "high",
    num_images: int = 1,
    negative_prompt: Optional[str] = None,
    # FLUX.1 parameters (flux-general only)
    flux_strength: Optional[float] = None,
    flux_scheduler: Optional[str] = None,
    # FLUX.2 & Kontext parameters (only used if model supports them)
    flux_guidance_scale: Optional[float] = None,  # dev/flex/kontext only
    flux_num_inference_steps: Optional[int] = None,  # dev/flex/kontext only
    flux_seed: Optional[int] = None,
    flux_image_urls: Optional[List[str]] = None,  # Multi-ref for dev/pro/flex/max
    flux_output_format: str = "png",
    flux_enable_safety_checker: bool = False,
    flux_enable_prompt_expansion: Optional[bool] = None,  # dev/flex only
    flux_safety_tolerance: Optional[str] = None,  # pro/flex/max: "1"-"5"
    flux_acceleration: Optional[str] = None,  # dev only: "none"/"regular"/"high"
) -> List[str]:
    """
    Generate image(s) from a source image.

    Supports all image models including FLUX.2 variants:
    - flux-2-dev: configurable (guidance_scale, steps, prompt_expansion, acceleration)
    - flux-2-pro: zero-config (only safety_tolerance)
    - flux-2-flex: fully configurable (all params)
    - flux-2-max: zero-config (only safety_tolerance)
    - flux-kontext-dev/pro: configurable (guidance_scale, steps)

    Returns list of image URLs.
    """
    # Check if FLUX.2 model for enhanced logging
    is_flux2 = model.startswith("flux-2") or model.startswith("flux-kontext")

    logger.info("Generating image",
                model=model,
                is_flux2=is_flux2,
                image_url=image_url[:50] if image_url else "NO IMAGE",
                prompt=prompt[:80] if prompt else "NO PROMPT",
                flux_guidance=flux_guidance_scale,
                flux_steps=flux_num_inference_steps,
                multi_ref=len(flux_image_urls) if flux_image_urls else 0,
                safety_tolerance=flux_safety_tolerance,
                acceleration=flux_acceleration)

    # Validate model
    if model not in IMAGE_MODELS:
        raise ValueError(
            f"Unknown image model: {model}. Available: {list(IMAGE_MODELS.keys())}"
        )

    # Submit job with all parameters - payload builder handles per-model support
    request_id = await submit_image_job(
        model=model,
        image_url=image_url,
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_images=num_images,
        aspect_ratio=aspect_ratio,
        quality=quality,
        # FLUX.1 params
        flux_strength=flux_strength,
        flux_scheduler=flux_scheduler,
        # FLUX.2 & Kontext params (payload builder filters per model)
        flux_guidance_scale=flux_guidance_scale,
        flux_num_inference_steps=flux_num_inference_steps,
        flux_seed=flux_seed,
        flux_image_urls=flux_image_urls,
        flux_output_format=flux_output_format,
        flux_enable_safety_checker=flux_enable_safety_checker,
        flux_enable_prompt_expansion=flux_enable_prompt_expansion,
        flux_safety_tolerance=flux_safety_tolerance,
        flux_acceleration=flux_acceleration,
    )

    # Wait for completion
    result = await wait_for_image_completion(model, request_id)

    if not result.get("image_urls"):
        raise Exception("No image URLs in completed result")

    logger.info("Images generated",
                model=model,
                count=len(result["image_urls"]),
                is_flux2=is_flux2)
    return result["image_urls"]


async def generate_images_batch(
    image_url: str,
    prompts: List[str],
    model: str = "gpt-image-1.5",
    aspect_ratio: str = "9:16",
    quality: str = "high",
) -> List[dict]:
    """
    Generate images for multiple prompts from a single source image.

    Returns list of {url, prompt, type} dicts.
    """
    results = []

    for prompt in prompts:
        try:
            urls = await generate_image(
                image_url=image_url,
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                quality=quality,
                num_images=1,
            )
            for url in urls:
                results.append(
                    {
                        "url": url,
                        "prompt": prompt,
                        "type": "image",
                    }
                )
        except Exception as e:
            logger.error("Image generation failed", prompt=prompt[:50], error=str(e))
            # Continue with other prompts

    return results


async def generate_videos_batch(
    image_urls: List[str],
    prompts: List[str],
    model: str = "kling",
    resolution: str = "1080p",
    duration_sec: int = 5,
) -> List[dict]:
    """
    Generate videos for image/prompt combinations.

    Returns list of {url, source_image, prompt, type} dicts.
    """
    results = []

    # Generate for each image/prompt combination
    for image_url in image_urls:
        for prompt in prompts:
            try:
                video_url = await generate_video(
                    image_url=image_url,
                    prompt=prompt,
                    model=model,
                    resolution=resolution,
                    duration_sec=duration_sec,
                )
                results.append(
                    {
                        "url": video_url,
                        "source_image": image_url,
                        "prompt": prompt,
                        "type": "video",
                    }
                )
            except Exception as e:
                logger.error(
                    "Video generation failed",
                    image=image_url[:50],
                    prompt=prompt[:50],
                    error=str(e),
                )
                # Continue with other combinations

    return results


# Pipeline-compatible wrapper functions
async def pipeline_generate_images(
    image_urls: List[str],
    prompts: List[str],
    model: str = "gpt-image-1.5",
    aspect_ratio: str = "9:16",
    quality: str = "high",
    images_per_prompt: int = 1,
) -> dict:
    """
    Generate images for pipeline step.

    Returns dict with 'items' list containing all generated images.
    """
    items = []

    for image_url in image_urls:
        batch_results = await generate_images_batch(
            image_url=image_url,
            prompts=prompts,
            model=model,
            aspect_ratio=aspect_ratio,
            quality=quality,
        )
        items.extend(batch_results)

    return {"items": items}


async def pipeline_generate_videos(
    image_urls: List[str],
    prompts: List[str],
    model: str = "kling",
    resolution: str = "1080p",
    duration_sec: int = 5,
    videos_per_image: int = 1,
) -> dict:
    """
    Generate videos for pipeline step.

    Returns dict with 'items' list containing all generated videos.
    """
    items = await generate_videos_batch(
        image_urls=image_urls,
        prompts=prompts,
        model=model,
        resolution=resolution,
        duration_sec=duration_sec,
    )

    return {"items": items}
