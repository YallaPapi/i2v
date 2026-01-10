"""GPU configuration API for runtime settings."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/gpu", tags=["gpu"])

# Runtime config storage (in production, use Redis or database)
_runtime_config = {
    "comfyui_url": settings.comfyui_url,
    "swarmui_url": settings.swarmui_url,
    "gpu_provider": settings.gpu_provider,
    "vastai_instance_id": settings.vastai_instance_id,
}


class GPUConfigRequest(BaseModel):
    """Request to update GPU configuration."""

    comfyui_url: Optional[str] = Field(
        None, description="ComfyUI API URL (e.g., Cloudflare tunnel URL from vast.ai)"
    )
    swarmui_url: Optional[str] = Field(
        None, description="SwarmUI API URL"
    )
    gpu_provider: Optional[str] = Field(
        None, description="GPU provider: 'none', 'local', or 'vastai'"
    )
    vastai_instance_id: Optional[int] = Field(
        None, description="Active vast.ai instance ID"
    )


class GPUConfigResponse(BaseModel):
    """Current GPU configuration."""

    comfyui_url: str
    comfyui_available: bool
    swarmui_url: str
    swarmui_available: bool
    gpu_provider: str
    vastai_instance_id: Optional[int]


class GPUHealthResponse(BaseModel):
    """GPU service health check response."""

    provider: str
    comfyui_status: str
    comfyui_url: str
    swarmui_status: str
    swarmui_url: str
    models_available: list[str]


def get_comfyui_url() -> str:
    """Get the current ComfyUI URL."""
    return _runtime_config.get("comfyui_url", settings.comfyui_url)


def get_swarmui_url() -> str:
    """Get the current SwarmUI URL."""
    return _runtime_config.get("swarmui_url", settings.swarmui_url)


def get_gpu_provider() -> str:
    """Get the current GPU provider."""
    return _runtime_config.get("gpu_provider", settings.gpu_provider)


def set_swarmui_url(url: str, instance_id: int | None = None) -> None:
    """Set the SwarmUI URL (called automatically after vast.ai instance is ready)."""
    _runtime_config["swarmui_url"] = url
    _runtime_config["gpu_provider"] = "vastai"
    if instance_id:
        _runtime_config["vastai_instance_id"] = instance_id
    logger.info("SwarmUI URL auto-configured", url=url, instance_id=instance_id)


@router.get("/config", response_model=GPUConfigResponse)
async def get_gpu_config() -> GPUConfigResponse:
    """Get current GPU configuration and check availability."""
    comfyui_url = get_comfyui_url()
    swarmui_url = get_swarmui_url()

    # Check ComfyUI availability
    comfyui_available = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{comfyui_url}/system_stats")
            comfyui_available = resp.status_code == 200
    except Exception:
        pass

    # Check SwarmUI availability
    swarmui_available = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{swarmui_url}/")
            swarmui_available = resp.status_code == 200
    except Exception:
        pass

    return GPUConfigResponse(
        comfyui_url=comfyui_url,
        comfyui_available=comfyui_available,
        swarmui_url=swarmui_url,
        swarmui_available=swarmui_available,
        gpu_provider=_runtime_config.get("gpu_provider", "none"),
        vastai_instance_id=_runtime_config.get("vastai_instance_id"),
    )


@router.post("/config", response_model=GPUConfigResponse)
async def update_gpu_config(request: GPUConfigRequest) -> GPUConfigResponse:
    """
    Update GPU configuration at runtime.

    Use this to set the Cloudflare tunnel URL from vast.ai after the instance starts.
    Get the tunnel URL from the vast.ai console by clicking "Open" on your instance.
    """
    updated = []

    if request.comfyui_url is not None:
        _runtime_config["comfyui_url"] = request.comfyui_url
        updated.append(f"comfyui_url={request.comfyui_url}")

    if request.swarmui_url is not None:
        _runtime_config["swarmui_url"] = request.swarmui_url
        updated.append(f"swarmui_url={request.swarmui_url}")

    if request.gpu_provider is not None:
        if request.gpu_provider not in ("none", "local", "vastai"):
            raise HTTPException(
                status_code=400,
                detail="gpu_provider must be 'none', 'local', or 'vastai'",
            )
        _runtime_config["gpu_provider"] = request.gpu_provider
        updated.append(f"gpu_provider={request.gpu_provider}")

    if request.vastai_instance_id is not None:
        _runtime_config["vastai_instance_id"] = request.vastai_instance_id
        updated.append(f"vastai_instance_id={request.vastai_instance_id}")

    logger.info("GPU config updated", updates=updated)

    # Return current config
    return await get_gpu_config()


@router.get("/health", response_model=GPUHealthResponse)
async def gpu_health_check() -> GPUHealthResponse:
    """
    Check GPU service health and available models.
    """
    comfyui_url = get_comfyui_url()
    swarmui_url = get_swarmui_url()
    provider = get_gpu_provider()

    comfyui_status = "unavailable"
    swarmui_status = "unavailable"
    models_available = []

    # Check ComfyUI
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{comfyui_url}/system_stats")
            if resp.status_code == 200:
                comfyui_status = "available"
                data = resp.json()
                # Try to extract GPU info
                if "system" in data and "devices" in data["system"]:
                    for device in data["system"]["devices"]:
                        if device.get("type") == "cuda":
                            models_available.append(f"GPU: {device.get('name', 'Unknown')}")

            # Try to get object info (models)
            try:
                obj_resp = await client.get(f"{comfyui_url}/object_info")
                if obj_resp.status_code == 200:
                    comfyui_status = "available (API ready)"
            except Exception:
                pass

    except Exception as e:
        comfyui_status = f"error: {str(e)[:50]}"

    # Check SwarmUI
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{swarmui_url}/")
            if resp.status_code == 200:
                swarmui_status = "available"
    except Exception as e:
        swarmui_status = f"error: {str(e)[:50]}"

    return GPUHealthResponse(
        provider=provider,
        comfyui_status=comfyui_status,
        comfyui_url=comfyui_url,
        swarmui_status=swarmui_status,
        swarmui_url=swarmui_url,
        models_available=models_available,
    )


@router.post("/test-connection")
async def test_gpu_connection(url: str) -> dict:
    """
    Test connection to a GPU service URL.

    Useful for validating a Cloudflare tunnel URL before setting it.
    """
    results = {"url": url, "reachable": False, "api_type": "unknown", "details": {}}

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Try root endpoint
            resp = await client.get(f"{url.rstrip('/')}/")
            results["reachable"] = resp.status_code in (200, 301, 302)

            # Check if it's ComfyUI
            try:
                stats_resp = await client.get(f"{url.rstrip('/')}/system_stats")
                if stats_resp.status_code == 200:
                    results["api_type"] = "comfyui"
                    results["details"] = stats_resp.json()
            except Exception:
                pass

            # Check if it's SwarmUI
            if results["api_type"] == "unknown" and "swarm" in resp.text.lower():
                results["api_type"] = "swarmui"

    except Exception as e:
        results["error"] = str(e)

    return results
