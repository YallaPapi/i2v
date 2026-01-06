"""Face swap client for Easel AI models on Fal.ai."""

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

# Face swap models configuration
# Pricing: easel-advanced $0.05/image
FACE_SWAP_MODELS = {
    "easel-advanced": {
        "submit_url": "https://queue.fal.run/easel-ai/advanced-face-swap",
        "status_url": "https://queue.fal.run/easel-ai/advanced-face-swap",
        "pricing": "$0.05/swap",
        "description": "Advanced face swap with likeness preservation, supports hair options",
    },
}

FaceSwapModelType = Literal["easel-advanced"]
GenderType = Literal["male", "female", "non-binary"]
WorkflowType = Literal["user_hair", "target_hair"]


class FaceSwapAPIError(Exception):
    """Exception raised for face swap API errors."""

    pass


def _get_headers() -> dict:
    """Get authentication headers for Fal API."""
    return {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json",
    }


def _build_face_swap_payload(
    face_image_url: str,
    target_image_url: str,
    gender: GenderType = "female",
    workflow_type: WorkflowType = "target_hair",
    upscale: bool = True,
    detailer: bool = False,
    face_image_url_2: str | None = None,
    gender_2: GenderType | None = None,
) -> dict:
    """Build request payload for face swap."""
    payload = {
        "face_image_0": {"url": face_image_url},
        "gender_0": gender,
        "target_image": {"url": target_image_url},
        "workflow_type": workflow_type,
        "upscale": upscale,
        "detailer": detailer,
    }

    # Optional second face for multiplayer mode
    if face_image_url_2 and gender_2:
        payload["face_image_1"] = {"url": face_image_url_2}
        payload["gender_1"] = gender_2

    return payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def submit_face_swap_job(
    face_image_url: str,
    target_image_url: str,
    gender: GenderType = "female",
    workflow_type: WorkflowType = "target_hair",
    upscale: bool = True,
    detailer: bool = False,
    face_image_url_2: str | None = None,
    gender_2: GenderType | None = None,
    model: FaceSwapModelType = "easel-advanced",
) -> str:
    """
    Submit a face swap job to Fal's queue.

    Args:
        face_image_url: URL of image containing the face to swap FROM
        target_image_url: URL of image to swap the face TO
        gender: Gender of person in face image (male/female/non-binary)
        workflow_type: 'target_hair' preserves target's hair, 'user_hair' preserves source's hair
        upscale: Apply 2x upscale (default True)
        detailer: Apply detail enhancement (default False)
        face_image_url_2: Optional second face for multiplayer swap
        gender_2: Gender of second person

    Returns:
        request_id for polling
    """
    if model not in FACE_SWAP_MODELS:
        raise ValueError(f"Unknown face swap model: {model}")

    config = FACE_SWAP_MODELS[model]
    payload = _build_face_swap_payload(
        face_image_url=face_image_url,
        target_image_url=target_image_url,
        gender=gender,
        workflow_type=workflow_type,
        upscale=upscale,
        detailer=detailer,
        face_image_url_2=face_image_url_2,
        gender_2=gender_2,
    )

    logger.debug(
        "Submitting face swap job to Fal",
        model=model,
        face_url=face_image_url[:50],
        target_url=target_image_url[:50],
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
            raise FaceSwapAPIError(error_msg)

        data = response.json()
        request_id = data.get("request_id")

        if not request_id:
            raise FaceSwapAPIError("No request_id in Fal response")

        logger.info("Face swap job submitted to Fal", model=model, request_id=request_id)
        return request_id


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def get_face_swap_result(
    request_id: str, model: FaceSwapModelType = "easel-advanced"
) -> dict:
    """
    Poll Fal's queue for face swap job result.

    Returns dict with:
        - status: "pending" | "running" | "completed" | "failed"
        - image_url: str | None
        - error_message: str | None
    """
    if model not in FACE_SWAP_MODELS:
        raise ValueError(f"Unknown face swap model: {model}")

    config = FACE_SWAP_MODELS[model]
    url = f"{config['status_url']}/requests/{request_id}/status"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=_get_headers())

        if response.status_code >= 400:
            error_msg = f"Fal API error: {response.status_code} - {response.text}"
            logger.error(error_msg, model=model, request_id=request_id)
            raise FaceSwapAPIError(error_msg)

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
        "image_url": None,
        "error_message": None,
    }

    if status == "completed":
        # Get the actual result
        result_url = f"{config['status_url']}/requests/{request_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            result_response = await client.get(result_url, headers=_get_headers())
            logger.debug("Face swap result response", status_code=result_response.status_code)

            if result_response.status_code == 200:
                result_data = result_response.json()
                logger.debug(
                    "Face swap result data",
                    keys=list(result_data.keys()),
                )

                # Output format: {"image": {"url": "...", ...}}
                image_data = result_data.get("image", {})
                if isinstance(image_data, dict) and image_data.get("url"):
                    result["image_url"] = image_data["url"]
                elif isinstance(image_data, str):
                    result["image_url"] = image_data

                # Fallback formats
                if not result["image_url"]:
                    for key in ["url", "output", "result_url"]:
                        if key in result_data:
                            val = result_data[key]
                            if isinstance(val, str):
                                result["image_url"] = val
                                break
                            elif isinstance(val, dict) and val.get("url"):
                                result["image_url"] = val["url"]
                                break

                logger.debug("Parsed face swap URL", url=result["image_url"][:50] if result["image_url"] else None)
            else:
                logger.error(
                    "Failed to fetch face swap result",
                    status_code=result_response.status_code,
                )

    elif status == "failed":
        result["error_message"] = data.get("error", "Unknown error from Fal")

    logger.debug("Face swap job status", model=model, request_id=request_id, status=status)
    return result


def list_face_swap_models() -> dict:
    """Return information about all available face swap models."""
    return {
        name: {
            "pricing": config["pricing"],
            "description": config["description"],
        }
        for name, config in FACE_SWAP_MODELS.items()
    }
