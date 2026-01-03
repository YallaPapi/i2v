import httpx
from typing import Literal
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = structlog.get_logger()

# Model configurations
# Pricing per second (approx): wan=$0.05-0.15, wan22=$0.04-0.08, kling=$0.07, veo2=$0.50, veo31=$0.10-0.20
MODELS = {
    # Wan models
    "wan": {
        "submit_url": "https://queue.fal.run/fal-ai/wan-25-preview/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/wan-25-preview",
        "pricing": "480p=$0.05/s, 720p=$0.10/s, 1080p=$0.15/s",
    },
    "wan21": {
        "submit_url": "https://queue.fal.run/fal-ai/wan-i2v",
        "status_url": "https://queue.fal.run/fal-ai/wan-i2v",
        "pricing": "480p=$0.20/vid, 720p=$0.40/vid",
    },
    "wan22": {
        "submit_url": "https://queue.fal.run/fal-ai/wan/v2.2-a14b/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/wan",
        "pricing": "480p=$0.04/s, 580p=$0.06/s, 720p=$0.08/s",
    },
    "wan-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/wan-pro/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/wan-pro",
        "pricing": "1080p=$0.16/s (~$0.80/5s)",
    },
    # Kling model
    "kling": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video",
        "pricing": "$0.35/5s + $0.07/extra sec",
    },
    # Veo models (Google)
    "veo2": {
        "submit_url": "https://queue.fal.run/fal-ai/veo2/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/veo2",
        "pricing": "$0.50/s (720p only)",
    },
    "veo31-fast": {
        "submit_url": "https://queue.fal.run/fal-ai/veo3.1/fast/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/veo3.1",
        "pricing": "$0.10/s (no audio), $0.15/s (audio)",
    },
    "veo31": {
        "submit_url": "https://queue.fal.run/fal-ai/veo3.1/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/veo3.1",
        "pricing": "$0.20/s (no audio), $0.40/s (audio)",
    },
    # First-Last Frame models (require TWO images: first and last frame)
    "veo31-flf": {
        "submit_url": "https://queue.fal.run/fal-ai/veo3.1/first-last-frame-to-video",
        "status_url": "https://queue.fal.run/fal-ai/veo3.1",
        "pricing": "$0.20/s (no audio), $0.40/s (audio)",
        "first_last_frame": True,
    },
    "veo31-fast-flf": {
        "submit_url": "https://queue.fal.run/fal-ai/veo3.1/fast/first-last-frame-to-video",
        "status_url": "https://queue.fal.run/fal-ai/veo3.1",
        "pricing": "$0.10/s (no audio), $0.15/s (audio)",
        "first_last_frame": True,
    },
}

ModelType = Literal["wan", "wan21", "wan22", "wan-pro", "kling", "veo2", "veo31-fast", "veo31", "veo31-flf", "veo31-fast-flf"]


class FalAPIError(Exception):
    """Exception raised for Fal API errors."""
    pass


def _get_headers() -> dict:
    """Get authentication headers for Fal API."""
    return {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json",
    }


def _build_payload(model: ModelType, image_url: str, prompt: str, resolution: str, duration_sec: int) -> dict:
    """Build request payload based on model type."""
    # Wan models (wan, wan21, wan22, wan-pro)
    if model in ("wan", "wan21", "wan22", "wan-pro"):
        return {
            "prompt": prompt,
            "image_url": image_url,
            "resolution": resolution,
            "duration": str(duration_sec),
            "negative_prompt": "low resolution, error, worst quality, low quality, artifacts",
            "enable_prompt_expansion": True,
            "enable_safety_checker": True,
        }
    # Kling model
    elif model == "kling":
        aspect_map = {"480p": "9:16", "720p": "9:16", "1080p": "9:16"}
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": str(duration_sec),
            "aspect_ratio": aspect_map.get(resolution, "9:16"),
            "negative_prompt": "low resolution, error, worst quality, low quality, artifacts",
        }
    # Veo2 model
    elif model == "veo2":
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": "5s",  # Veo2 supports 5-8s
            "aspect_ratio": "9:16",
        }
    # Veo 3.1 models (image-to-video)
    elif model in ("veo31", "veo31-fast"):
        # Map duration to valid options: 4s, 6s, 8s
        duration_map = {5: "6s", 10: "8s"}
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": duration_map.get(duration_sec, "6s"),
            "aspect_ratio": "9:16",
            "enable_audio": False,  # Set True to add audio (costs more)
        }
    # Veo 3.1 First-Last Frame models (require two images)
    elif model in ("veo31-flf", "veo31-fast-flf"):
        duration_map = {5: "6s", 10: "8s"}
        return {
            "prompt": prompt,
            "first_frame_image": image_url,
            "last_frame_image": image_url,  # Same image for now - can be extended
            "duration": duration_map.get(duration_sec, "6s"),
            "aspect_ratio": "9:16",
            "enable_audio": False,
        }
    else:
        raise ValueError(f"Unknown model: {model}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def submit_job(
    model: ModelType,
    image_url: str,
    motion_prompt: str,
    resolution: str,
    duration_sec: int,
) -> str:
    """
    Submit a job to Fal's queue.

    Returns the request_id for polling.
    """
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")

    config = MODELS[model]
    payload = _build_payload(model, image_url, motion_prompt, resolution, duration_sec)

    logger.debug("Submitting job to Fal", model=model, image_url=image_url, resolution=resolution)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            config["submit_url"],
            headers=_get_headers(),
            json=payload,
        )

        if response.status_code >= 400:
            error_msg = f"Fal API error: {response.status_code} - {response.text}"
            logger.error(error_msg, model=model)
            raise FalAPIError(error_msg)

        data = response.json()
        request_id = data.get("request_id")

        if not request_id:
            raise FalAPIError("No request_id in Fal response")

        logger.info("Job submitted to Fal", model=model, request_id=request_id)
        return request_id


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def get_job_result(model: ModelType, request_id: str) -> dict:
    """
    Poll Fal's queue for job result.

    Returns dict with:
        - status: "pending" | "running" | "completed" | "failed"
        - video_url: str | None
        - error_message: str | None
    """
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")

    config = MODELS[model]
    url = f"{config['status_url']}/requests/{request_id}/status"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=_get_headers())

        if response.status_code >= 400:
            error_msg = f"Fal API error: {response.status_code} - {response.text}"
            logger.error(error_msg, model=model, request_id=request_id)
            raise FalAPIError(error_msg)

        data = response.json()

    # Map Fal statuses to our internal statuses
    fal_status = data.get("status", "").upper()
    status_map = {
        "IN_QUEUE": "pending",
        "IN_PROGRESS": "running",
        "COMPLETED": "completed",
        "FAILED": "failed",
    }
    status = status_map.get(fal_status, "pending")

    result = {
        "status": status,
        "video_url": None,
        "error_message": None,
    }

    if status == "completed":
        # Get the actual result
        result_url = f"{config['status_url']}/requests/{request_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            result_response = await client.get(result_url, headers=_get_headers())
            if result_response.status_code == 200:
                result_data = result_response.json()
                video_data = result_data.get("video", {})
                result["video_url"] = video_data.get("url")

    elif status == "failed":
        result["error_message"] = data.get("error", "Unknown error from Fal")

    logger.debug("Fal job status", model=model, request_id=request_id, status=status)
    return result


# Backwards compatibility aliases
async def submit_wan_job(image_url: str, motion_prompt: str, resolution: str, duration_sec: int) -> str:
    return await submit_job("wan", image_url, motion_prompt, resolution, duration_sec)


async def get_wan_result(request_id: str) -> dict:
    return await get_job_result("wan", request_id)
