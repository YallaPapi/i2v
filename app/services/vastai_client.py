"""vast.ai GPU instance management and job execution."""

import os
import io
import json
import asyncio
import httpx
import structlog
from typing import Literal
from dataclasses import dataclass
from dotenv import load_dotenv

from app.services.r2_cache import cache_image, cache_video

load_dotenv()

logger = structlog.get_logger()


# Content type to file extension mapping
CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


async def upload_image_to_comfyui(
    image_url: str,
    comfyui_base_url: str,
    http_client: httpx.AsyncClient | None = None,
) -> str:
    """
    Download an image from a URL and upload it to ComfyUI's input folder.

    ComfyUI's LoadImage node only loads from its local /input folder,
    so we need to upload images before they can be used in workflows.

    Args:
        image_url: URL of the image to download
        comfyui_base_url: Base URL of ComfyUI API (e.g., http://host:8188)
        http_client: Optional httpx client to reuse

    Returns:
        Filename as returned by ComfyUI (e.g., "upload_abc123.png")

    Raises:
        RuntimeError: If download or upload fails
    """
    client = http_client or httpx.AsyncClient(timeout=60.0)
    should_close = http_client is None

    try:
        # Step 1: Download image from URL
        logger.debug("Downloading image for ComfyUI upload", url=image_url[:80])

        download_resp = await client.get(image_url, follow_redirects=True)
        download_resp.raise_for_status()

        # Determine file extension from content type
        content_type = download_resp.headers.get("Content-Type", "image/png")
        content_type = content_type.split(";")[0].strip().lower()
        ext = CONTENT_TYPE_TO_EXT.get(content_type, ".png")

        # Check file size (limit to 50MB)
        content_length = len(download_resp.content)
        if content_length > 50 * 1024 * 1024:
            raise RuntimeError(f"Image too large: {content_length / 1024 / 1024:.1f}MB (max 50MB)")

        # Step 2: Upload to ComfyUI
        upload_url = f"{comfyui_base_url.rstrip('/')}/upload/image"

        # Create file-like object for multipart upload
        import uuid
        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"

        files = {
            "image": (filename, io.BytesIO(download_resp.content), content_type)
        }

        logger.debug("Uploading image to ComfyUI", upload_url=upload_url, filename=filename)

        upload_resp = await client.post(upload_url, files=files)
        upload_resp.raise_for_status()

        # Parse response - ComfyUI returns {"name": "filename.png"} or a list
        data = upload_resp.json()

        if isinstance(data, dict) and "name" in data:
            result_filename = data["name"]
        elif isinstance(data, list) and data and isinstance(data[0], dict) and "name" in data[0]:
            result_filename = data[0]["name"]
        else:
            raise RuntimeError(f"Unexpected ComfyUI upload response: {data}")

        logger.info("Image uploaded to ComfyUI", filename=result_filename)
        return result_filename

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error during ComfyUI image upload",
                    status_code=e.response.status_code,
                    url=str(e.request.url)[:80])
        raise RuntimeError(f"Failed to upload image to ComfyUI: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error("Failed to upload image to ComfyUI", error=str(e))
        raise RuntimeError(f"Failed to upload image to ComfyUI: {e}")
    finally:
        if should_close:
            await client.aclose()

VASTAI_API_URL = "https://console.vast.ai/api/v0"

# Recommended Docker images for different workloads
# Set COMFYUI_DOCKER_IMAGE env var to use a custom image with pre-baked models
# Using pytorch base image with manual ComfyUI install for simplicity
DOCKER_IMAGES = {
    "comfyui": os.getenv("COMFYUI_DOCKER_IMAGE", "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"),
    "a1111": "ghcr.io/ai-dock/stable-diffusion-webui:latest",
    "kohya": "ghcr.io/ai-dock/kohya-ss:latest",
}

# Minimum specs for different workloads
MIN_SPECS = {
    "image": {"gpu_ram": 12, "disk_space": 50},  # SDXL/Pony (increased for models)
    "video": {"gpu_ram": 24, "disk_space": 80},  # HunyuanVideo
    "lora": {"gpu_ram": 24, "disk_space": 100},  # LoRA training
}

# ComfyUI installation and model download script
# This runs on startup to install ComfyUI and download required models
COMFYUI_STARTUP_SCRIPT = """#!/bin/bash
set -e

echo "[startup] Starting ComfyUI setup..."

# Install system dependencies
apt-get update && apt-get install -y git wget aria2 libgl1-mesa-glx libglib2.0-0 || true

# Clone ComfyUI if not exists
if [ ! -d "/workspace/ComfyUI" ]; then
    echo "[startup] Cloning ComfyUI..."
    cd /workspace
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
    pip install -r requirements.txt
else
    echo "[startup] ComfyUI already exists"
    cd /workspace/ComfyUI
fi

MODEL_DIR="/workspace/ComfyUI/models"
mkdir -p "$MODEL_DIR/checkpoints" "$MODEL_DIR/vae" "$MODEL_DIR/loras"

# Download models function
download_model() {
    local url="$1" dest="$2"
    if [ ! -f "$dest" ]; then
        echo "[models] Downloading $(basename $dest)..."
        aria2c -x 16 -s 16 -k 1M -o "$dest" "$url" || wget --progress=dot:giga -O "$dest" "$url" || rm -f "$dest"
    else
        echo "[models] Already exists: $(basename $dest)"
    fi
}

# Download SDXL Base (priority - smaller and always works)
download_model "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors" "$MODEL_DIR/checkpoints/sd_xl_base_1.0.safetensors"

# Download SDXL VAE
download_model "https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors" "$MODEL_DIR/vae/sdxl_vae.safetensors"

# Download Pony (if time permits - it's large)
download_model "https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors" "$MODEL_DIR/checkpoints/ponyDiffusionV6XL_v6.safetensors" &

echo "[startup] Starting ComfyUI server..."
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 &

# Wait for ComfyUI to be ready
sleep 10
echo "[startup] ComfyUI should be running on port 8188"

# Wait for background downloads
wait
echo "[startup] Setup complete"

# Keep container running
tail -f /dev/null
"""


@dataclass
class VastInstance:
    """Represents a vast.ai GPU instance."""
    id: int
    status: str
    gpu_name: str
    gpu_ram: float
    cpu_cores: int
    ram: float
    disk_space: float
    dph_total: float  # $/hr
    ssh_host: str | None = None
    ssh_port: int | None = None
    api_port: int | None = None  # ComfyUI API port


class VastAIClient:
    """Client for vast.ai GPU rental and job management."""

    def __init__(self):
        self.api_key = os.getenv("VASTAI_API_KEY")
        if not self.api_key:
            logger.warning("VASTAI_API_KEY not set, vast.ai features disabled")
        self._active_instance: VastInstance | None = None
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        return self._http

    def _headers(self) -> dict:
        """Get auth headers."""
        return {"Authorization": f"Bearer {self.api_key}"}

    async def search_offers(
        self,
        gpu_ram_min: int = 24,
        disk_space_min: int = 50,
        max_price: float = 0.50,
        gpu_name: str | None = None,
        verified: bool = True,
    ) -> list[dict]:
        """
        Search for available GPU offers on vast.ai.

        Args:
            gpu_ram_min: Minimum GPU RAM in GB
            disk_space_min: Minimum disk space in GB
            max_price: Maximum price per hour in USD
            gpu_name: Filter by GPU name (e.g., "RTX 4090", "RTX 3090")
            verified: Only show verified machines

        Returns:
            List of available offers sorted by price
        """
        if not self.api_key:
            return []

        client = await self._get_client()

        # Build query
        query = {
            "gpu_ram": {"gte": gpu_ram_min},
            "disk_space": {"gte": disk_space_min},
            "dph_total": {"lte": max_price},
            "rentable": {"eq": True},
        }
        if verified:
            query["verified"] = {"eq": True}
        if gpu_name:
            query["gpu_name"] = {"eq": gpu_name}

        try:
            response = await client.get(
                f"{VASTAI_API_URL}/bundles/",
                headers=self._headers(),
                params={"q": json.dumps(query)},
            )
            response.raise_for_status()
            data = response.json()

            # Sort by price
            offers = data.get("offers", [])
            offers.sort(key=lambda x: x.get("dph_total", 999))

            logger.info("Found vast.ai offers", count=len(offers))
            return offers
        except Exception as e:
            logger.error("Failed to search vast.ai offers", error=str(e))
            return []

    async def get_cheapest_offer(
        self,
        workload: Literal["image", "video", "lora"] = "video",
        max_price: float = 0.50,
    ) -> dict | None:
        """Get the cheapest suitable offer for a workload type."""
        specs = MIN_SPECS.get(workload, MIN_SPECS["video"])
        offers = await self.search_offers(
            gpu_ram_min=specs["gpu_ram"],
            disk_space_min=specs["disk_space"],
            max_price=max_price,
        )
        return offers[0] if offers else None

    async def create_instance(
        self,
        offer_id: int,
        docker_image: str = "ai-dock/comfyui:latest",
        disk_space: int = 50,
        env_vars: dict | None = None,
        onstart_script: str | None = None,
    ) -> VastInstance | None:
        """
        Rent a GPU instance from vast.ai.

        Args:
            offer_id: The offer ID to rent
            docker_image: Docker image to run
            disk_space: Disk space in GB
            env_vars: Environment variables for the container
            onstart_script: Script to run on startup

        Returns:
            VastInstance if successful, None otherwise
        """
        if not self.api_key:
            return None

        client = await self._get_client()

        # Use ComfyUI startup script that installs everything from scratch
        if onstart_script is None:
            onstart_script = COMFYUI_STARTUP_SCRIPT

        # Environment configuration
        default_env = {
            "PYTHONUNBUFFERED": "1",
        }
        if env_vars:
            default_env.update(env_vars)

        payload = {
            "client_id": "i2v-app",
            "image": docker_image,
            "disk": disk_space,
            "runtype": "ssh_direc ssh_proxy",  # Enable direct port access and SSH
            "onstart": onstart_script,
            "env": default_env,
            "python_utf8": True,
            "lang_utf8": True,
        }

        try:
            response = await client.put(
                f"{VASTAI_API_URL}/asks/{offer_id}/",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            instance_id = data.get("new_contract")
            if not instance_id:
                logger.error("Failed to create instance", response=data)
                return None

            logger.info("Created vast.ai instance", instance_id=instance_id)

            # Wait for instance to be ready
            instance = await self._wait_for_instance(instance_id)
            self._active_instance = instance
            return instance

        except Exception as e:
            logger.error("Failed to create vast.ai instance", error=str(e))
            return None

    async def _wait_for_instance(
        self, instance_id: int, timeout: int = 300
    ) -> VastInstance | None:
        """Wait for an instance to be ready."""
        client = await self._get_client()
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            try:
                response = await client.get(
                    f"{VASTAI_API_URL}/instances/{instance_id}/",
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()

                # API returns {"instances": {...}} for single instance
                if "instances" in data:
                    data = data["instances"]

                status = data.get("actual_status", "unknown")
                if status == "running":
                    # Extract port mapping - format varies
                    ports = data.get("ports") or {}
                    api_port = None
                    if isinstance(ports, dict):
                        port_info = ports.get("8188/tcp", [])
                        if port_info and isinstance(port_info, list):
                            api_port = port_info[0].get("HostPort")

                    return VastInstance(
                        id=instance_id,
                        status=status,
                        gpu_name=data.get("gpu_name", "Unknown"),
                        gpu_ram=data.get("gpu_ram", 0),
                        cpu_cores=data.get("cpu_cores", 0),
                        ram=data.get("cpu_ram", 0),
                        disk_space=data.get("disk_space", 0),
                        dph_total=data.get("dph_total", 0),
                        ssh_host=data.get("ssh_host"),
                        ssh_port=data.get("ssh_port"),
                        api_port=api_port,
                    )
                elif status in ("exited", "error"):
                    logger.error("Instance failed to start", status=status, msg=data.get("status_msg"))
                    return None

                logger.debug("Waiting for instance", status=status)
                await asyncio.sleep(10)

            except Exception as e:
                logger.warning("Error checking instance status", error=str(e))
                await asyncio.sleep(5)

        logger.error("Instance startup timeout", instance_id=instance_id)
        return None

    async def get_instance(self, instance_id: int) -> VastInstance | None:
        """Get instance details by ID."""
        if not self.api_key:
            return None

        client = await self._get_client()

        try:
            response = await client.get(
                f"{VASTAI_API_URL}/instances/{instance_id}/",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

            # API returns {"instances": {...}} for single instance
            if "instances" in data:
                data = data["instances"]

            # Extract port mapping
            ports = data.get("ports") or {}
            api_port = None
            if isinstance(ports, dict):
                port_info = ports.get("8188/tcp", [])
                if port_info and isinstance(port_info, list):
                    api_port = port_info[0].get("HostPort")

            return VastInstance(
                id=instance_id,
                status=data.get("actual_status", "unknown"),
                gpu_name=data.get("gpu_name", "Unknown"),
                gpu_ram=data.get("gpu_ram", 0),
                cpu_cores=data.get("cpu_cores", 0),
                ram=data.get("cpu_ram", 0),
                disk_space=data.get("disk_space", 0),
                dph_total=data.get("dph_total", 0),
                ssh_host=data.get("ssh_host"),
                ssh_port=data.get("ssh_port"),
                api_port=api_port,
            )
        except Exception as e:
            logger.error("Failed to get instance", instance_id=instance_id, error=str(e))
            return None

    async def list_instances(self) -> list[VastInstance]:
        """List all rented instances."""
        if not self.api_key:
            return []

        client = await self._get_client()

        try:
            response = await client.get(
                f"{VASTAI_API_URL}/instances/",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

            instances = []
            for inst in data.get("instances", []):
                instances.append(VastInstance(
                    id=inst.get("id"),
                    status=inst.get("actual_status", "unknown"),
                    gpu_name=inst.get("gpu_name", "Unknown"),
                    gpu_ram=inst.get("gpu_ram", 0),
                    cpu_cores=inst.get("cpu_cores", 0),
                    ram=inst.get("cpu_ram", 0),
                    disk_space=inst.get("disk_space", 0),
                    dph_total=inst.get("dph_total", 0),
                    ssh_host=inst.get("ssh_host"),
                    ssh_port=inst.get("ssh_port"),
                ))
            return instances
        except Exception as e:
            logger.error("Failed to list instances", error=str(e))
            return []

    async def destroy_instance(self, instance_id: int) -> bool:
        """Destroy/terminate an instance."""
        if not self.api_key:
            return False

        client = await self._get_client()

        try:
            response = await client.delete(
                f"{VASTAI_API_URL}/instances/{instance_id}/",
                headers=self._headers(),
            )
            response.raise_for_status()
            logger.info("Destroyed vast.ai instance", instance_id=instance_id)

            if self._active_instance and self._active_instance.id == instance_id:
                self._active_instance = None
            return True
        except Exception as e:
            logger.error("Failed to destroy instance", instance_id=instance_id, error=str(e))
            return False

    async def submit_comfyui_job(
        self,
        instance: VastInstance,
        workflow: dict,
        timeout: int = 300,
    ) -> dict | None:
        """
        Submit a ComfyUI workflow to a running instance.

        Args:
            instance: The VastInstance to run on
            workflow: ComfyUI workflow JSON
            timeout: Timeout in seconds

        Returns:
            Result dict with output URLs if successful
        """
        if not instance.ssh_host or not instance.api_port:
            logger.error("Instance not ready for API calls")
            return None

        api_url = f"http://{instance.ssh_host}:{instance.api_port}"
        client = await self._get_client()

        try:
            # Queue the prompt
            response = await client.post(
                f"{api_url}/prompt",
                json={"prompt": workflow},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            prompt_id = data.get("prompt_id")

            if not prompt_id:
                logger.error("No prompt_id in response", response=data)
                return None

            logger.info("Submitted ComfyUI job", prompt_id=prompt_id)

            # Poll for completion
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < timeout:
                history_response = await client.get(
                    f"{api_url}/history/{prompt_id}",
                    timeout=10.0,
                )
                history = history_response.json()

                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    if outputs:
                        # Extract output images/videos
                        result = await self._process_comfyui_outputs(
                            api_url, outputs
                        )
                        return result

                await asyncio.sleep(2)

            logger.error("ComfyUI job timeout", prompt_id=prompt_id)
            return None

        except Exception as e:
            logger.error("ComfyUI job failed", error=str(e))
            return None

    async def _process_comfyui_outputs(
        self, api_url: str, outputs: dict
    ) -> dict:
        """Process ComfyUI outputs and cache to R2."""
        client = await self._get_client()
        result = {"images": [], "videos": []}

        for node_id, node_output in outputs.items():
            # Handle images
            for img in node_output.get("images", []):
                filename = img.get("filename")
                subfolder = img.get("subfolder", "")
                img_url = f"{api_url}/view?filename={filename}&subfolder={subfolder}&type=output"

                # Cache to R2
                cached_url = await cache_image(img_url, prefix="vast-outputs")
                if cached_url:
                    result["images"].append(cached_url)
                else:
                    result["images"].append(img_url)

            # Handle videos/gifs
            for vid in node_output.get("gifs", []):
                filename = vid.get("filename")
                subfolder = vid.get("subfolder", "")
                vid_url = f"{api_url}/view?filename={filename}&subfolder={subfolder}&type=output"

                # Cache to R2
                cached_url = await cache_video(vid_url)
                if cached_url:
                    result["videos"].append(cached_url)
                else:
                    result["videos"].append(vid_url)

        return result

    async def get_or_create_instance(
        self,
        workload: Literal["image", "video", "lora"] = "video",
        max_price: float = 0.35,
    ) -> VastInstance | None:
        """
        Get an existing instance or create a new one if needed.

        This is the main entry point for getting a GPU for generation.
        """
        # Check for existing running instance
        instances = await self.list_instances()
        running = [i for i in instances if i.status == "running"]

        if running:
            logger.info("Using existing instance", instance_id=running[0].id)
            self._active_instance = running[0]
            return running[0]

        # Find cheapest offer and create new instance
        offer = await self.get_cheapest_offer(workload, max_price)
        if not offer:
            logger.error("No suitable offers found", workload=workload, max_price=max_price)
            return None

        logger.info(
            "Creating new instance",
            offer_id=offer["id"],
            gpu=offer.get("gpu_name"),
            price=offer.get("dph_total"),
        )

        # Use the ComfyUI Docker image
        docker_image = DOCKER_IMAGES["comfyui"]
        # The startup script is set in create_instance
        onstart_script = None

        return await self.create_instance(
            offer_id=offer["id"],
            docker_image=docker_image,
            disk_space=MIN_SPECS[workload]["disk_space"],
            onstart_script=onstart_script,
        )

    async def shutdown_idle_instances(self, idle_minutes: int = 15) -> int:
        """Destroy instances that have been idle for too long."""
        # TODO: Track last job time and destroy idle instances
        # For now, this is a placeholder
        destroyed = 0
        # instances = await self.list_instances()
        # for instance in instances:
        #     if instance.is_idle(idle_minutes):
        #         await self.destroy_instance(instance.id)
        #         destroyed += 1
        return destroyed

    async def close(self):
        """Close the HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Singleton instance
_vastai_client: VastAIClient | None = None


def get_vastai_client() -> VastAIClient:
    """Get the vast.ai client singleton."""
    global _vastai_client
    if _vastai_client is None:
        _vastai_client = VastAIClient()
    return _vastai_client
