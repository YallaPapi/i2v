"""Image generation client for multiple AI models."""
import httpx
from typing import Literal
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = structlog.get_logger()

# Image generation models configuration
# Pricing: gpt-image $0.009-0.20, kling-o1 $0.028, nano-banana $0.039, nano-banana-pro $0.15
IMAGE_MODELS = {
    "gpt-image-1.5": {
        "submit_url": "https://queue.fal.run/fal-ai/gpt-image-1.5/edit",
        "status_url": "https://queue.fal.run/fal-ai/gpt-image-1.5",
        "pricing": "$0.009-$0.20/image (quality dependent)",
        "identity_preservation": False,
        "description": "High-fidelity image editing with strong prompt adherence",
    },
    "kling-image": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-image/o1",
        "status_url": "https://queue.fal.run/fal-ai/kling-image",
        "pricing": "$0.028/image",
        "identity_preservation": True,
        "description": "Multi-reference control with Elements for character consistency",
    },
    "nano-banana-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/nano-banana-pro/edit",
        "status_url": "https://queue.fal.run/fal-ai/nano-banana-pro",
        "pricing": "$0.15/image (2x for 4K)",
        "identity_preservation": False,
        "description": "Google's best model - realistic, good typography",
    },
    "nano-banana": {
        "submit_url": "https://queue.fal.run/fal-ai/nano-banana/edit",
        "status_url": "https://queue.fal.run/fal-ai/nano-banana",
        "pricing": "$0.039/image",
        "identity_preservation": False,
        "description": "Budget Google model for general editing",
    },
}

ImageModelType = Literal["gpt-image-1.5", "kling-image", "nano-banana-pro", "nano-banana"]


class ImageAPIError(Exception):
    """Exception raised for image API errors."""
    pass


def _get_headers() -> dict:
    """Get authentication headers for Fal API."""
    return {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json",
    }


def _build_image_payload(model: ImageModelType, image_url: str, prompt: str,
                         negative_prompt: str | None = None,
                         num_images: int = 1,
                         aspect_ratio: str = "9:16",
                         quality: str = "high") -> dict:
    """Build request payload based on image model type."""

    # GPT Image 1.5 Edit
    if model == "gpt-image-1.5":
        quality_map = {"low": "low", "medium": "medium", "high": "high"}
        size_map = {
            "1:1": "1024x1024",
            "9:16": "1024x1536",
            "16:9": "1536x1024",
        }
        return {
            "prompt": prompt,
            "image_urls": [image_url],
            "image_size": size_map.get(aspect_ratio, "1024x1536"),
            "quality": quality_map.get(quality, "high"),
            "num_images": num_images,
            "output_format": "png",
        }

    # Kling Image O1 - Multi-reference with Elements
    elif model == "kling-image":
        ar_map = {
            "1:1": "1:1",
            "9:16": "9:16",
            "16:9": "16:9",
            "4:3": "4:3",
            "3:4": "3:4",
        }
        return {
            "prompt": f"@Image1 {prompt}",  # Reference the image in prompt
            "image_urls": [image_url],
            "aspect_ratio": ar_map.get(aspect_ratio, "9:16"),
            "resolution": "2K",  # High quality
            "num_images": num_images,
            "output_format": "png",
        }

    # Nano Banana Pro Edit (Google's best)
    elif model == "nano-banana-pro":
        return {
            "prompt": prompt,
            "image_urls": [image_url],
            "aspect_ratio": aspect_ratio,
            "resolution": "2K",
            "num_images": num_images,
            "output_format": "png",
        }

    # Nano Banana Edit (Budget Google)
    elif model == "nano-banana":
        return {
            "prompt": prompt,
            "image_urls": [image_url],
            "aspect_ratio": aspect_ratio,
            "num_images": num_images,
            "output_format": "png",
        }

    else:
        raise ValueError(f"Unknown image model: {model}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def submit_image_job(
    model: ImageModelType,
    image_url: str,
    prompt: str,
    negative_prompt: str | None = None,
    num_images: int = 1,
    aspect_ratio: str = "9:16",
    quality: str = "high",
) -> str:
    """
    Submit an image generation job to Fal's queue.

    Returns the request_id for polling.
    """
    if model not in IMAGE_MODELS:
        raise ValueError(f"Unknown image model: {model}")

    config = IMAGE_MODELS[model]
    payload = _build_image_payload(
        model, image_url, prompt, negative_prompt, num_images, aspect_ratio, quality
    )

    logger.debug("Submitting image job to Fal", model=model, image_url=image_url)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            config["submit_url"],
            headers=_get_headers(),
            json=payload,
        )

        if response.status_code >= 400:
            error_msg = f"Fal API error: {response.status_code} - {response.text}"
            logger.error(error_msg, model=model)
            raise ImageAPIError(error_msg)

        data = response.json()
        request_id = data.get("request_id")

        if not request_id:
            raise ImageAPIError("No request_id in Fal response")

        logger.info("Image job submitted to Fal", model=model, request_id=request_id)
        return request_id


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def get_image_result(model: ImageModelType, request_id: str) -> dict:
    """
    Poll Fal's queue for image job result.

    Returns dict with:
        - status: "pending" | "running" | "completed" | "failed"
        - image_urls: list[str] | None
        - error_message: str | None
    """
    if model not in IMAGE_MODELS:
        raise ValueError(f"Unknown image model: {model}")

    config = IMAGE_MODELS[model]
    url = f"{config['status_url']}/requests/{request_id}/status"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=_get_headers())

        if response.status_code >= 400:
            error_msg = f"Fal API error: {response.status_code} - {response.text}"
            logger.error(error_msg, model=model, request_id=request_id)
            raise ImageAPIError(error_msg)

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
        "image_urls": None,
        "error_message": None,
    }

    if status == "completed":
        # Get the actual result
        result_url = f"{config['status_url']}/requests/{request_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            result_response = await client.get(result_url, headers=_get_headers())
            logger.debug("Image result response", status_code=result_response.status_code)
            if result_response.status_code == 200:
                result_data = result_response.json()
                logger.debug("Image result data", model=model, keys=list(result_data.keys()), data=str(result_data)[:500])

                image_urls = []

                # Format 1: {"images": [{"url": "..."}, ...]}
                images = result_data.get("images", [])
                if images:
                    for img in images:
                        if isinstance(img, dict) and img.get("url"):
                            image_urls.append(img["url"])
                        elif isinstance(img, str):
                            image_urls.append(img)

                # Format 2: {"output": [...]} or {"output": {"url": "..."}}
                if not image_urls and "output" in result_data:
                    output = result_data["output"]
                    if isinstance(output, list):
                        for item in output:
                            if isinstance(item, dict) and item.get("url"):
                                image_urls.append(item["url"])
                            elif isinstance(item, str):
                                image_urls.append(item)
                    elif isinstance(output, dict) and output.get("url"):
                        image_urls.append(output["url"])

                # Format 3: {"data": {"images": [...]}} (nested)
                if not image_urls and "data" in result_data:
                    data_obj = result_data["data"]
                    if isinstance(data_obj, dict):
                        nested_images = data_obj.get("images", [])
                        for img in nested_images:
                            if isinstance(img, dict) and img.get("url"):
                                image_urls.append(img["url"])
                            elif isinstance(img, str):
                                image_urls.append(img)

                # Format 4: Direct URLs in result (some models)
                if not image_urls:
                    for key in ["image_url", "url", "result_url"]:
                        if key in result_data and result_data[key]:
                            image_urls.append(result_data[key])
                            break

                result["image_urls"] = image_urls if image_urls else None
                logger.debug("Parsed image URLs", count=len(image_urls) if image_urls else 0, urls=image_urls[:2] if image_urls else None)
            else:
                logger.error("Failed to fetch image result", status_code=result_response.status_code, text=result_response.text[:200])

    elif status == "failed":
        result["error_message"] = data.get("error", "Unknown error from Fal")

    logger.debug("Image job status", model=model, request_id=request_id, status=status)
    return result


def list_image_models() -> dict:
    """Return information about all available image models."""
    return {
        name: {
            "pricing": config["pricing"],
            "identity_preservation": config["identity_preservation"],
            "description": config["description"],
        }
        for name, config in IMAGE_MODELS.items()
    }
