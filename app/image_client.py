"""Image generation client for multiple AI models."""

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

# Image generation models configuration
# Pricing: gpt-image $0.009-0.20, kling-o1 $0.028, nano-banana $0.039, nano-banana-pro $0.15
IMAGE_MODELS = {
    "gpt-image-1.5": {
        "submit_url": "https://queue.fal.run/fal-ai/gpt-image-1.5/edit",
        "status_url": "https://queue.fal.run/fal-ai/gpt-image-1.5",
        "pricing": "$0.009-$0.20/image (quality dependent)",
        "identity_preservation": False,
        "description": "High-fidelity image editing with strong prompt adherence",
        "is_flux2": False,
    },
    "kling-image": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-image/o1",
        "status_url": "https://queue.fal.run/fal-ai/kling-image",
        "pricing": "$0.028/image",
        "identity_preservation": True,
        "description": "Multi-reference control with Elements for character consistency",
        "is_flux2": False,
    },
    "nano-banana-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/nano-banana-pro/edit",
        "status_url": "https://queue.fal.run/fal-ai/nano-banana-pro",
        "pricing": "$0.15/image (2x for 4K)",
        "identity_preservation": False,
        "description": "Google's best model - realistic, good typography",
        "is_flux2": False,
    },
    "nano-banana": {
        "submit_url": "https://queue.fal.run/fal-ai/nano-banana/edit",
        "status_url": "https://queue.fal.run/fal-ai/nano-banana",
        "pricing": "$0.039/image",
        "identity_preservation": False,
        "description": "Budget Google model for general editing",
        "is_flux2": False,
    },
    "flux-general": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-general/image-to-image",
        "status_url": "https://queue.fal.run/fal-ai/flux-general",
        "pricing": "$0.025/image",
        "identity_preservation": True,
        "description": "FLUX 1.0 i2i - strength controls transformation amount",
        "is_flux2": False,
    },
    # ============== FLUX.2 Models (Black Forest Labs - Nov 2025) ==============
    # Per fal.ai API docs - each model has different supported parameters
    "flux-2-dev": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-2/edit",
        "status_url": "https://queue.fal.run/fal-ai/flux-2",
        "pricing": "$0.012/MP",
        "identity_preservation": True,
        "description": "FLUX.2 Dev - Open-source, configurable, fast prototyping",
        "is_flux2": True,
        "supports_multi_ref": True,
        "max_references": 4,
        # Supported params: guidance_scale, num_inference_steps, enable_prompt_expansion
        "supports_guidance_scale": True,
        "default_guidance_scale": 2.5,
        "max_guidance": 20.0,
        "supports_num_steps": True,
        "supports_prompt_expansion": True,
        "supports_safety_tolerance": False,
        "supports_acceleration": True,  # none, regular, high
    },
    "flux-2-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-2-pro/edit",
        "status_url": "https://queue.fal.run/fal-ai/flux-2-pro",
        "pricing": "$0.03/MP",
        "identity_preservation": True,
        "description": "FLUX.2 Pro - Zero-config production, best quality",
        "is_flux2": True,
        "supports_multi_ref": True,
        "max_references": 9,
        # Zero-config: NO guidance_scale, NO num_inference_steps
        "supports_guidance_scale": False,
        "supports_num_steps": False,
        "supports_prompt_expansion": False,
        "supports_safety_tolerance": True,
    },
    "flux-2-flex": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-2-flex/edit",
        "status_url": "https://queue.fal.run/fal-ai/flux-2-flex",
        "pricing": "$0.04/image",
        "identity_preservation": True,
        "description": "FLUX.2 Flex - Multi-reference (up to 10), fully configurable",
        "is_flux2": True,
        "supports_multi_ref": True,
        "max_references": 10,
        # Full params: guidance_scale, num_inference_steps, enable_prompt_expansion, safety_tolerance
        "supports_guidance_scale": True,
        "default_guidance_scale": 3.5,
        "max_guidance": 10.0,
        "supports_num_steps": True,
        "supports_prompt_expansion": True,
        "default_prompt_expansion": True,  # defaults to true for flex
        "supports_safety_tolerance": True,
    },
    "flux-2-max": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-2-max/edit",
        "status_url": "https://queue.fal.run/fal-ai/flux-2-max",
        "pricing": "$0.08/image",
        "identity_preservation": True,
        "description": "FLUX.2 Max - Highest quality, zero-config",
        "is_flux2": True,
        "supports_multi_ref": True,
        "max_references": 10,
        # Zero-config like Pro: NO guidance_scale, NO num_inference_steps
        "supports_guidance_scale": False,
        "supports_num_steps": False,
        "supports_prompt_expansion": False,
        "supports_safety_tolerance": True,
    },
    # ============== FLUX.1 Kontext (In-context editing) ==============
    "flux-kontext-dev": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-kontext/dev",
        "status_url": "https://queue.fal.run/fal-ai/flux-kontext",
        "pricing": "$0.025/image",
        "identity_preservation": True,
        "description": "FLUX Kontext Dev - Natural language image editing",
        "is_flux2": True,
        "is_kontext": True,
        "supports_multi_ref": False,  # Kontext uses single image_url
        # Configurable params
        "supports_guidance_scale": True,
        "default_guidance_scale": 3.5,
        "max_guidance": 20.0,
        "supports_num_steps": True,
        "supports_prompt_expansion": False,
        "supports_safety_tolerance": False,
    },
    "flux-kontext-pro": {
        "submit_url": "https://queue.fal.run/fal-ai/flux-pro/kontext",
        "status_url": "https://queue.fal.run/fal-ai/flux-pro",
        "pricing": "$0.04/image",
        "identity_preservation": True,
        "description": "FLUX Kontext Pro - Production in-context editing",
        "is_flux2": True,
        "is_kontext": True,
        "supports_multi_ref": False,
        # Configurable params
        "supports_guidance_scale": True,
        "default_guidance_scale": 3.5,
        "max_guidance": 20.0,
        "supports_num_steps": True,
        "supports_prompt_expansion": False,
        "supports_safety_tolerance": False,
    },
}

ImageModelType = Literal[
    "gpt-image-1.5", "kling-image", "nano-banana-pro", "nano-banana", "flux-general",
    "flux-2-dev", "flux-2-pro", "flux-2-flex", "flux-2-max",
    "flux-kontext-dev", "flux-kontext-pro"
]

# Helper to check if model is FLUX.2 family
def is_flux2_model(model: str) -> bool:
    """Check if model is a FLUX.2 or Kontext variant."""
    return IMAGE_MODELS.get(model, {}).get("is_flux2", False)


class ImageAPIError(Exception):
    """Exception raised for image API errors."""

    pass


def _get_headers() -> dict:
    """Get authentication headers for Fal API."""
    return {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json",
    }


def _build_image_payload(
    model: ImageModelType,
    image_url: str,
    prompt: str,
    negative_prompt: str | None = None,
    num_images: int = 1,
    aspect_ratio: str = "9:16",
    quality: str = "high",
) -> dict:
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
        payload = {
            "prompt": prompt,
            "image_urls": [image_url],
            "aspect_ratio": aspect_ratio,
            "resolution": "2K",
            "num_images": num_images,
            "output_format": "png",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    # Nano Banana Edit (Budget Google)
    elif model == "nano-banana":
        payload = {
            "prompt": prompt,
            "image_urls": [image_url],
            "aspect_ratio": aspect_ratio,
            "resolution": "1K",
            "num_images": num_images,
            "output_format": "png",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    else:
        raise ValueError(f"Unknown image model: {model}")


def _build_flux_payload(
    image_url: str,
    prompt: str,
    aspect_ratio: str = "9:16",
    num_images: int = 1,
    strength: float = 0.75,
    guidance_scale: float = 3.5,  # fal.ai real_cfg_scale max is 5
    num_inference_steps: int = 28,
    seed: int | None = None,
    negative_prompt: str | None = None,
    scheduler: str = "euler",
) -> dict:
    """Build FLUX-specific payload with all configurable parameters.

    API docs: https://fal.ai/models/fal-ai/flux-general/image-to-image/api
    """
    # Map aspect ratio to preset image size strings (more reliable than custom dimensions)
    size_map = {
        "1:1": "square_hd",
        "9:16": "portrait_16_9",
        "16:9": "landscape_16_9",
        "4:3": "landscape_4_3",
        "3:4": "portrait_4_3",
    }
    image_size = size_map.get(aspect_ratio, "portrait_16_9")

    # Clamp guidance_scale to fal.ai's real_cfg_scale limit (0-5)
    clamped_guidance = min(max(guidance_scale, 0.0), 5.0)

    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "image_size": image_size,
        "strength": strength,
        "num_inference_steps": num_inference_steps,
        "num_images": num_images,
        "output_format": "png",
        "enable_safety_checker": False,
        "guidance_scale": clamped_guidance,
        # Scheduler: "euler" (default) or "dpmpp_2m"
        "scheduler": scheduler,
    }

    if seed is not None:
        payload["seed"] = seed

    if negative_prompt and negative_prompt.strip():
        payload["negative_prompt"] = negative_prompt

    return payload


# FLUX.2 image size presets - maps to actual dimensions
FLUX2_SIZE_PRESETS = {
    "square_hd": {"width": 1024, "height": 1024},
    "square": {"width": 512, "height": 512},
    "portrait_4_3": {"width": 768, "height": 1024},
    "portrait_16_9": {"width": 576, "height": 1024},
    "landscape_4_3": {"width": 1024, "height": 768},
    "landscape_16_9": {"width": 1024, "height": 576},
}


def _build_flux2_payload(
    model: str,
    image_url: str | None,
    image_urls: list[str] | None,
    prompt: str,
    aspect_ratio: str = "9:16",
    num_images: int = 1,
    guidance_scale: float | None = None,  # Only for dev, flex, kontext
    num_inference_steps: int | None = None,  # Only for dev, flex, kontext
    seed: int | None = None,
    output_format: str = "png",
    enable_safety_checker: bool = False,
    enable_prompt_expansion: bool | None = None,  # Only for dev, flex
    safety_tolerance: str | None = None,  # Only for pro, flex, max ("1"-"5")
    acceleration: str | None = None,  # Only for dev ("none", "regular", "high")
) -> dict:
    """Build FLUX.2 payload with ONLY parameters supported by each model.

    Per fal.ai API docs (Jan 2026):

    FLUX.2 Dev:
      - guidance_scale (default 2.5, range 0-20)
      - num_inference_steps (default 28, range 4-50)
      - enable_prompt_expansion (default false)
      - acceleration (none/regular/high)
      - image_urls (max 4)
      - NO safety_tolerance

    FLUX.2 Pro:
      - ZERO-CONFIG: NO guidance_scale, NO num_inference_steps
      - safety_tolerance ("1"-"5", default "2")
      - image_urls (max 9)

    FLUX.2 Flex:
      - guidance_scale (default 3.5, range 1.5-10)
      - num_inference_steps (default 28, range 2-50)
      - enable_prompt_expansion (default true)
      - safety_tolerance ("1"-"5", default "2")
      - image_urls (max 10)

    FLUX.2 Max:
      - ZERO-CONFIG: NO guidance_scale, NO num_inference_steps
      - safety_tolerance ("1"-"5", default "2")
      - image_urls (max 10)

    FLUX.1 Kontext (dev/pro):
      - guidance_scale (default 3.5)
      - num_inference_steps (default 28)
      - image_url (single, NOT array)
      - NO safety_tolerance
    """
    # Map aspect ratio to image_size enum
    size_map = {
        "1:1": "square_hd",
        "9:16": "portrait_16_9",
        "16:9": "landscape_16_9",
        "4:3": "landscape_4_3",
        "3:4": "portrait_4_3",
    }
    image_size = size_map.get(aspect_ratio, "portrait_16_9")

    # Get model config
    model_config = IMAGE_MODELS.get(model, {})
    is_kontext = model_config.get("is_kontext", False)
    supports_multi_ref = model_config.get("supports_multi_ref", False)
    supports_guidance = model_config.get("supports_guidance_scale", False)
    supports_steps = model_config.get("supports_num_steps", False)
    supports_prompt_exp = model_config.get("supports_prompt_expansion", False)
    supports_safety_tol = model_config.get("supports_safety_tolerance", False)
    supports_accel = model_config.get("supports_acceleration", False)
    default_guidance = model_config.get("default_guidance_scale", 3.5)
    max_guidance = model_config.get("max_guidance", 10.0)

    # Build base payload - only required params
    payload = {
        "prompt": prompt,
        "image_size": image_size,
        "output_format": output_format,
        "enable_safety_checker": enable_safety_checker,
    }

    # Handle image input(s)
    if is_kontext:
        # Kontext uses single image_url, not array
        if image_url:
            payload["image_url"] = image_url
        elif image_urls and len(image_urls) > 0:
            payload["image_url"] = image_urls[0]
        logger.info("FLUX Kontext edit mode", model=model, edit_instruction=prompt[:100])
    elif supports_multi_ref:
        # FLUX.2 models use image_urls array
        max_refs = model_config.get("max_references", 10)
        if image_urls and len(image_urls) > 0:
            payload["image_urls"] = image_urls[:max_refs]
        elif image_url:
            payload["image_urls"] = [image_url]
        if "image_urls" in payload:
            logger.info("FLUX.2 image input", model=model, num_refs=len(payload["image_urls"]))
    else:
        # Fallback to single image
        if image_url:
            payload["image_url"] = image_url
        elif image_urls and len(image_urls) > 0:
            payload["image_url"] = image_urls[0]

    # Only add guidance_scale if model supports it
    if supports_guidance:
        gs = guidance_scale if guidance_scale is not None else default_guidance
        payload["guidance_scale"] = min(max(gs, 0.0), max_guidance)

    # Only add num_inference_steps if model supports it
    if supports_steps:
        steps = num_inference_steps if num_inference_steps is not None else 28
        payload["num_inference_steps"] = min(max(steps, 2), 50)

    # Only add num_images for models that support it (dev)
    if model == "flux-2-dev":
        payload["num_images"] = num_images

    # Only add enable_prompt_expansion if model supports it
    if supports_prompt_exp:
        default_exp = model_config.get("default_prompt_expansion", False)
        exp = enable_prompt_expansion if enable_prompt_expansion is not None else default_exp
        payload["enable_prompt_expansion"] = exp

    # Only add safety_tolerance if model supports it (pro, flex, max)
    if supports_safety_tol and safety_tolerance:
        payload["safety_tolerance"] = safety_tolerance

    # Only add acceleration if model supports it (dev only)
    if supports_accel and acceleration:
        payload["acceleration"] = acceleration

    # Optional seed
    if seed is not None:
        payload["seed"] = seed

    return payload


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
    # FLUX.1 specific parameters
    flux_strength: float | None = None,
    flux_scheduler: str | None = None,
    # FLUX.2 & Kontext parameters (only sent if model supports them)
    flux_guidance_scale: float | None = None,  # dev, flex, kontext only
    flux_num_inference_steps: int | None = None,  # dev, flex, kontext only
    flux_seed: int | None = None,
    flux_image_urls: list[str] | None = None,  # Multi-reference for dev/pro/flex/max
    flux_output_format: str = "png",
    flux_enable_safety_checker: bool = False,
    flux_enable_prompt_expansion: bool | None = None,  # dev, flex only
    flux_safety_tolerance: str | None = None,  # pro, flex, max only ("1"-"5")
    flux_acceleration: str | None = None,  # dev only ("none", "regular", "high")
) -> str:
    """
    Submit an image generation job to Fal's queue.

    Supports all models including FLUX.2 variants:
    - flux-2-dev: configurable (guidance_scale, steps, prompt_expansion, acceleration)
    - flux-2-pro: zero-config (only safety_tolerance)
    - flux-2-flex: fully configurable (all params)
    - flux-2-max: zero-config (only safety_tolerance)
    - flux-kontext-dev/pro: configurable (guidance_scale, steps)

    Returns the request_id for polling.
    """
    if model not in IMAGE_MODELS:
        raise ValueError(f"Unknown image model: {model}")

    config = IMAGE_MODELS[model]

    # Check if this is a FLUX.2 or Kontext model
    if is_flux2_model(model):
        # Use FLUX.2 payload builder - it handles per-model param support
        payload = _build_flux2_payload(
            model=model,
            image_url=image_url,
            image_urls=flux_image_urls,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            guidance_scale=flux_guidance_scale,
            num_inference_steps=flux_num_inference_steps,
            seed=flux_seed,
            output_format=flux_output_format,
            enable_safety_checker=flux_enable_safety_checker,
            enable_prompt_expansion=flux_enable_prompt_expansion,
            safety_tolerance=flux_safety_tolerance,
            acceleration=flux_acceleration,
        )
        logger.info("FLUX.2 payload built",
                    model=model,
                    prompt=prompt[:100] if prompt else "NO PROMPT",
                    guidance=payload.get("guidance_scale", "N/A (zero-config)"),
                    steps=payload.get("num_inference_steps", "N/A (zero-config)"),
                    image_size=payload["image_size"],
                    has_multi_ref="image_urls" in payload,
                    num_refs=len(payload.get("image_urls", [])) if "image_urls" in payload else 0,
                    safety_tolerance=payload.get("safety_tolerance"),
                    payload_keys=list(payload.keys()))
    # Use FLUX.1 payload builder for flux-general
    elif model == "flux-general":
        payload = _build_flux_payload(
            image_url=image_url,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            strength=flux_strength if flux_strength is not None else 0.75,
            guidance_scale=flux_guidance_scale if flux_guidance_scale is not None else 3.5,
            num_inference_steps=flux_num_inference_steps if flux_num_inference_steps is not None else 28,
            seed=flux_seed,
            negative_prompt=negative_prompt,
            scheduler=flux_scheduler if flux_scheduler else "euler",
        )
        logger.info("FLUX.1 payload built",
                    prompt=prompt[:100] if prompt else "NO PROMPT",
                    strength=payload["strength"],
                    guidance=payload["guidance_scale"],
                    steps=payload["num_inference_steps"],
                    scheduler=payload["scheduler"],
                    image_size=payload["image_size"])
    else:
        payload = _build_image_payload(
            model, image_url, prompt, negative_prompt, num_images, aspect_ratio, quality
        )

    # Log the FULL payload for debugging
    logger.info("Submitting image job to Fal",
                model=model,
                image_url=image_url[:80],
                prompt_in_payload=payload.get("prompt", "MISSING")[:100],
                strength=payload.get("strength"),
                guidance=payload.get("guidance_scale"),
                all_keys=list(payload.keys()))

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
            logger.debug(
                "Image result response", status_code=result_response.status_code
            )
            if result_response.status_code == 200:
                result_data = result_response.json()
                logger.debug(
                    "Image result data",
                    model=model,
                    keys=list(result_data.keys()),
                    data=str(result_data)[:500],
                )

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
                logger.debug(
                    "Parsed image URLs",
                    count=len(image_urls) if image_urls else 0,
                    urls=image_urls[:2] if image_urls else None,
                )
            else:
                logger.error(
                    "Failed to fetch image result",
                    status_code=result_response.status_code,
                    text=result_response.text[:200],
                )

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
