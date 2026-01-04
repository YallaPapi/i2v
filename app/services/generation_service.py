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
) -> str:
    """
    Generate a single video from an image.

    Returns the video URL.
    """
    logger.info("Generating video", model=model, image_url=image_url[:50])

    # Validate model
    if model not in VIDEO_MODELS:
        raise ValueError(f"Unknown video model: {model}. Available: {list(VIDEO_MODELS.keys())}")

    # Submit job
    request_id = await submit_job(
        model=model,
        image_url=image_url,
        motion_prompt=prompt,
        resolution=resolution,
        duration_sec=duration_sec,
        negative_prompt=negative_prompt,
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
) -> List[str]:
    """
    Generate image(s) from a source image.

    Returns list of image URLs.
    """
    logger.info("Generating image", model=model, image_url=image_url[:50])

    # Validate model
    if model not in IMAGE_MODELS:
        raise ValueError(f"Unknown image model: {model}. Available: {list(IMAGE_MODELS.keys())}")

    # Submit job
    request_id = await submit_image_job(
        model=model,
        image_url=image_url,
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_images=num_images,
        aspect_ratio=aspect_ratio,
        quality=quality,
    )

    # Wait for completion
    result = await wait_for_image_completion(model, request_id)

    if not result.get("image_urls"):
        raise Exception("No image URLs in completed result")

    logger.info("Images generated", model=model, count=len(result["image_urls"]))
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
                results.append({
                    "url": url,
                    "prompt": prompt,
                    "type": "image",
                })
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
                results.append({
                    "url": video_url,
                    "source_image": image_url,
                    "prompt": prompt,
                    "type": "video",
                })
            except Exception as e:
                logger.error("Video generation failed", image=image_url[:50], prompt=prompt[:50], error=str(e))
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
