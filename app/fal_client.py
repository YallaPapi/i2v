import httpx
from typing import Literal
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

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
    # Kling models
    "kling": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video",
        "pricing": "$0.35/5s + $0.07/extra sec",
    },
    "kling-master": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v2.1/master/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video",
        "pricing": "$1.40/5s + $0.28/extra sec (highest quality)",
    },
    "kling-standard": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v2.1/standard/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video",
        "pricing": "$0.25/5s + $0.05/extra sec (budget)",
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
    # Sora 2 models (OpenAI)
    "sora-2": {
        "submit_url": "https://queue.fal.run/fal-ai/sora-2/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/sora-2",
        "pricing": "$0.10/s (720p only, 4/8/12s)",
    },
    "sora-2-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/sora-2/image-to-video/pro",
        "status_url": "https://queue.fal.run/fal-ai/sora-2",
        "pricing": "$0.30/s (720p), $0.50/s (1080p) - 4/8/12s",
    },
    # Luma Dream Machine models
    "luma": {
        "submit_url": "https://queue.fal.run/fal-ai/luma-dream-machine/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/luma-dream-machine",
        "pricing": "$0.032/s (5s=$0.16, 9s=$0.29)",
    },
    "luma-ray2": {
        "submit_url": "https://queue.fal.run/fal-ai/luma-dream-machine/ray-2/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/luma-dream-machine",
        "pricing": "$0.05/s (5s=$0.25, 9s=$0.45) - better quality",
    },
    # Wan 2.6 model (latest Wan version)
    "wan26": {
        "submit_url": "https://queue.fal.run/wan/v2.6/image-to-video",
        "status_url": "https://queue.fal.run/wan/v2.6",
        "pricing": "720p=$0.10/s, 1080p=$0.15/s (5/10/15s durations)",
    },
    # Kling 2.6 Pro model (latest Kling with native audio)
    "kling26-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v2.6/pro/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video",
        "pricing": "$0.07/s (audio off), $0.14/s (audio on)",
    },
    # CogVideoX-5B (flat rate pricing)
    "cogvideox": {
        "submit_url": "https://queue.fal.run/fal-ai/cogvideox-5b/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/cogvideox-5b",
        "pricing": "$0.20/video (flat rate)",
    },
    # Stable Video Diffusion (no prompt, image-only)
    "stable-video": {
        "submit_url": "https://queue.fal.run/fal-ai/stable-video",
        "status_url": "https://queue.fal.run/fal-ai/stable-video",
        "pricing": "$0.075/video (flat rate)",
    },
}

ModelType = Literal[
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
]

# Default negative prompt - used when none specified
DEFAULT_NEGATIVE_PROMPT = "low resolution, error, worst quality, low quality, artifacts, horizontal video, landscape"


class FalAPIError(Exception):
    """Exception raised for Fal API errors."""

    pass


def _get_headers() -> dict:
    """Get authentication headers for Fal API."""
    return {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json",
    }


def _build_payload(
    model: ModelType,
    image_url: str,
    prompt: str,
    resolution: str,
    duration_sec: int,
    negative_prompt: str | None = None,
    enable_audio: bool = False,
) -> dict:
    """Build request payload based on model type."""
    # Use default negative prompt if none specified
    neg_prompt = (
        negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT
    )

    # Wan models (wan, wan21, wan22, wan-pro) - duration: 5 or 10 seconds
    if model in ("wan", "wan21", "wan22", "wan-pro"):
        return {
            "prompt": prompt,
            "image_url": image_url,
            "resolution": resolution,
            "aspect_ratio": "9:16",
            "duration": str(duration_sec),
            "negative_prompt": neg_prompt,
            "enable_prompt_expansion": True,
            "enable_safety_checker": True,
        }
    # Kling models (all variants) - duration: 5 or 10 seconds
    elif model in ("kling", "kling-master", "kling-standard"):
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": str(duration_sec),
            "aspect_ratio": "9:16",
            "negative_prompt": neg_prompt,
        }
    # Veo2 model - duration: 5-8 seconds (fixed)
    elif model == "veo2":
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": "5s",
            "aspect_ratio": "9:16",
            "enable_audio": enable_audio,
        }
    # Veo 3.1 models (image-to-video) - duration: 4, 6, 8 seconds
    elif model in ("veo31", "veo31-fast"):
        # Map to valid Veo durations: 4s, 6s, 8s
        veo_duration_map = {4: "4s", 5: "6s", 6: "6s", 8: "8s", 10: "8s"}
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": veo_duration_map.get(duration_sec, "6s"),
            "aspect_ratio": "9:16",
            "enable_audio": enable_audio,
        }
    # Veo 3.1 First-Last Frame models - duration: 4, 6, 8 seconds
    elif model in ("veo31-flf", "veo31-fast-flf"):
        veo_duration_map = {4: "4s", 5: "6s", 6: "6s", 8: "8s", 10: "8s"}
        return {
            "prompt": prompt,
            "first_frame_image": image_url,
            "last_frame_image": image_url,  # Same image for now - can be extended
            "duration": veo_duration_map.get(duration_sec, "6s"),
            "aspect_ratio": "9:16",
            "enable_audio": enable_audio,
        }
    # Sora 2 models (OpenAI) - duration: 4, 8, 12 seconds
    elif model in ("sora-2", "sora-2-pro"):
        # Map to valid Sora durations: 4, 8, 12
        sora_duration_map = {4: 4, 5: 4, 8: 8, 10: 8, 12: 12}
        sora_duration = sora_duration_map.get(duration_sec, 4)
        # Resolution: sora-2 = 720p only, sora-2-pro = 720p or 1080p
        sora_resolution = (
            "1080p" if model == "sora-2-pro" and resolution == "1080p" else "720p"
        )
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": sora_duration,
            "resolution": sora_resolution,
            "aspect_ratio": "9:16",
        }
    # Luma Dream Machine models - duration: 5s or 9s
    elif model in ("luma", "luma-ray2"):
        # Luma only supports 5s or 9s duration
        luma_duration = "9s" if duration_sec >= 8 else "5s"
        # Resolution mapping: 540p, 720p, 1080p
        luma_resolution = resolution if resolution in ("540p", "720p", "1080p") else "720p"
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": luma_duration,
            "aspect_ratio": "9:16",
            "resolution": luma_resolution,
        }
    # Wan 2.6 model - duration: 5, 10, or 15 seconds
    elif model == "wan26":
        # Wan 2.6 supports 5, 10, 15 second durations
        wan26_duration = "15" if duration_sec >= 12 else ("10" if duration_sec >= 8 else "5")
        wan26_resolution = resolution if resolution in ("720p", "1080p") else "720p"
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": wan26_duration,
            "resolution": wan26_resolution,
            "aspect_ratio": "9:16",
            "negative_prompt": neg_prompt,
        }
    # Kling 2.6 Pro model - duration: 5 or 10 seconds, supports native audio
    elif model == "kling26-pro":
        return {
            "prompt": prompt,
            "image_url": image_url,
            "duration": str(duration_sec),
            "aspect_ratio": "9:16",
            "negative_prompt": neg_prompt,
            "generate_audio": enable_audio,
        }
    # CogVideoX-5B - flat rate, configurable settings
    elif model == "cogvideox":
        # Map resolution to CogVideoX video_size format
        cogvideo_size_map = {
            "480p": "portrait_4_3",  # ~480x640
            "720p": "portrait_16_9",  # ~720x1280
            "1080p": "portrait_16_9",  # API caps at 720p for i2v
        }
        return {
            "prompt": prompt,
            "image_url": image_url,
            "video_size": cogvideo_size_map.get(resolution, "portrait_16_9"),
            "negative_prompt": neg_prompt,
            "num_inference_steps": 50,
            "guidance_scale": 7,
            "use_rife": True,
            "export_fps": 16,
        }
    # Stable Video Diffusion - image-only, no prompt support
    elif model == "stable-video":
        return {
            "image_url": image_url,
            "motion_bucket_id": 127,  # 1-255, controls motion intensity
            "cond_aug": 0.02,  # Conditioning noise
            "fps": 25,
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
    negative_prompt: str | None = None,
    enable_audio: bool = False,
) -> str:
    """
    Submit a job to Fal's queue.

    Returns the request_id for polling.
    """
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")

    config = MODELS[model]
    payload = _build_payload(
        model,
        image_url,
        motion_prompt,
        resolution,
        duration_sec,
        negative_prompt,
        enable_audio,
    )

    logger.info(
        "Submitting job to Fal",
        model=model,
        enable_audio=enable_audio,
        payload_audio=payload.get("enable_audio"),
    )

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
        logger.debug("Fetching result", url=result_url)
        async with httpx.AsyncClient(timeout=60.0) as client:
            result_response = await client.get(result_url, headers=_get_headers())
            logger.debug("Result response", status_code=result_response.status_code)
            if result_response.status_code == 200:
                result_data = result_response.json()
                logger.debug(
                    "Fal result data",
                    model=model,
                    keys=list(result_data.keys()),
                    data=str(result_data)[:500],
                )

                # Try multiple possible locations for video URL
                video_url = None

                # Format 1: {"video": {"url": "..."}}
                if "video" in result_data:
                    video_data = result_data["video"]
                    if isinstance(video_data, dict):
                        video_url = video_data.get("url")
                    elif isinstance(video_data, str):
                        video_url = video_data

                # Format 2: {"output": {"video_url": "..."}} or {"output": {"video": {"url": "..."}}}
                if not video_url and "output" in result_data:
                    output = result_data["output"]
                    if isinstance(output, dict):
                        video_url = output.get("video_url") or output.get("url")
                        if not video_url and "video" in output:
                            video_url = (
                                output["video"].get("url")
                                if isinstance(output["video"], dict)
                                else output["video"]
                            )

                # Format 3: {"video_url": "..."} (direct)
                if not video_url:
                    video_url = result_data.get("video_url")

                result["video_url"] = video_url
                logger.debug(
                    "Extracted video URL",
                    video_url=video_url[:50] if video_url else None,
                )
            else:
                logger.error(
                    "Failed to fetch result",
                    status_code=result_response.status_code,
                    text=result_response.text[:200],
                )

    elif status == "failed":
        result["error_message"] = data.get("error", "Unknown error from Fal")

    logger.debug("Fal job status", model=model, request_id=request_id, status=status)
    return result


# Backwards compatibility aliases
async def submit_wan_job(
    image_url: str, motion_prompt: str, resolution: str, duration_sec: int
) -> str:
    return await submit_job("wan", image_url, motion_prompt, resolution, duration_sec)


async def get_wan_result(request_id: str) -> dict:
    return await get_job_result("wan", request_id)
