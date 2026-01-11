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

# =============================================================================
# VAST.AI TEMPLATE CONFIGURATION
# =============================================================================
# ComfyUI Template (legacy)
#   Hash: 2188dfd3e0a0b83691bb468ddae0a4e5
#   Port: 8188
#
# SwarmUI Template (preferred for video generation)
#   Hash: 8e5e6ab1fceb9db3f813e815907b3390
#   External Port: 7865 (internal: 17865)
#   Docs: docs/VASTAI_SWARMUI_TEMPLATE.md
#   Includes ComfyUI backend automatically
# =============================================================================

# SwarmUI Docker image (VERIFIED WORKING)
# Note: Template hash doesn't work ("not accessible by user")
# Must use direct Docker image with runtype="jupyter_direct" for port exposure
SWARMUI_DOCKER_IMAGE = os.getenv(
    "SWARMUI_DOCKER_IMAGE",
    "vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311"
)
SWARMUI_PORT = 7865  # Internal port (mapped to dynamic external port)

# ComfyUI template (legacy fallback)
COMFYUI_TEMPLATE_HASH = os.getenv(
    "COMFYUI_TEMPLATE_HASH",
    "2188dfd3e0a0b83691bb468ddae0a4e5"  # Official Vast.ai ComfyUI template
)
COMFYUI_PORT = 8188

# Fallback: Direct image configuration (only used if template fails)
COMFYUI_DOCKER_IMAGE = os.getenv(
    "COMFYUI_DOCKER_IMAGE",
    "vastai/comfy:cuda-12.6-auto"  # Official vastai/comfy image
)

# Docker images for different workloads (fallback only)
DOCKER_IMAGES = {
    "comfyui": COMFYUI_DOCKER_IMAGE,
    "a1111": "ghcr.io/ai-dock/stable-diffusion-webui:latest",
    "kohya": "ghcr.io/ai-dock/kohya-ss:latest",
}


def get_comfyui_template_hash() -> str:
    """Get the official Vast.ai ComfyUI template hash.

    This is the recommended way to create ComfyUI instances on Vast.ai.
    Using a template hash ensures correct configuration of ports, env vars,
    and startup scripts.
    """
    return COMFYUI_TEMPLATE_HASH


def get_comfyui_image() -> str:
    """Get the ComfyUI Docker image (fallback, prefer template_hash).

    Returns the official vast.ai ComfyUI image. However, using
    create_instance_from_template() with the template hash is preferred.
    """
    return COMFYUI_DOCKER_IMAGE


def get_swarmui_template_hash() -> str:
    """Get the official Vast.ai SwarmUI template hash.

    SwarmUI is preferred for video generation as it provides:
    - Better UI for debugging
    - Built-in ComfyUI backend
    - Easier model management
    """
    return SWARMUI_TEMPLATE_HASH


def _extract_swarmui_port(instance_or_ports: dict) -> int:
    """Extract the external SwarmUI port from vast.ai instance data.

    Vast.ai SwarmUI template uses:
    - Internal port: 17865
    - External port: 7865
    See: docs/VASTAI_SWARMUI_TEMPLATE.md
    """
    if "ports" in instance_or_ports:
        ports = instance_or_ports.get("ports") or {}
    else:
        ports = instance_or_ports

    if not isinstance(ports, dict):
        raise RuntimeError(f"Invalid ports data type: {type(ports)}")

    def _get_host_port(key: str) -> int | None:
        entries = ports.get(key)
        if not entries or not isinstance(entries, list) or not entries:
            return None
        host_port = entries[0].get("HostPort")
        if host_port is None:
            return None
        try:
            return int(host_port)
        except (ValueError, TypeError):
            return None

    # Try SwarmUI internal port 17865 (maps to external 7865)
    port = _get_host_port("17865/tcp")
    if port is not None:
        logger.debug(f"Found SwarmUI port on 17865/tcp -> external port {port}")
        return port

    # Fallback: try external port directly
    port = _get_host_port("7865/tcp")
    if port is not None:
        logger.debug(f"Found SwarmUI port on 7865/tcp -> external port {port}")
        return port

    available_ports = list(ports.keys()) if ports else []
    raise RuntimeError(
        f"No SwarmUI port mapping found (tried 17865/tcp, 7865/tcp). "
        f"Available ports: {available_ports}"
    )


def build_swarmui_url(instance: "VastInstance", scheme: str = "http") -> str:
    """Build the SwarmUI base URL from a VastInstance.

    Args:
        instance: VastInstance with public_ip and swarmui_port populated
        scheme: URL scheme (http or https), defaults to http

    Returns:
        Base URL string like "http://78.83.187.54:17533"
    """
    if not instance.public_ip:
        raise ValueError("Instance missing public_ip for SwarmUI URL")
    if not instance.swarmui_port:
        raise ValueError("Instance missing swarmui_port for SwarmUI URL")

    return f"{scheme}://{instance.public_ip}:{instance.swarmui_port}"


# Minimum specs for different workloads
MIN_SPECS = {
    "image": {"gpu_ram": 12, "disk_space": 50},  # SDXL/Pony (increased for models)
    "video": {"gpu_ram": 24, "disk_space": 80},  # HunyuanVideo
    "lora": {"gpu_ram": 24, "disk_space": 100},  # LoRA training
}



# =============================================================================
# PORT PARSING HELPER
# =============================================================================
def _extract_comfyui_port(instance_or_ports: dict) -> int:
    """Extract the external ComfyUI API port from vast.ai instance data.

    Vast.ai maps internal container ports to random external ports.
    This function extracts the external HostPort that can be used to
    connect to ComfyUI from outside the container.

    Args:
        instance_or_ports: Either a full instance dict with a "ports" key,
                          or just the ports mapping dict directly.

    Returns:
        The external port number (HostPort) as an integer.

    Raises:
        RuntimeError: If no ComfyUI port mapping is found.

    Example:
        # Vast.ai returns ports like:
        # {"8188/tcp": [{"HostPort": "33526"}], "22/tcp": [{"HostPort": "22345"}]}
        # This function returns 33526 (the external port for ComfyUI)

        port = _extract_comfyui_port(instance_data)
        url = f"http://{instance_data['ssh_host']}:{port}"
    """
    # Handle both full instance dict and just ports dict
    if "ports" in instance_or_ports:
        ports = instance_or_ports.get("ports") or {}
    else:
        ports = instance_or_ports

    if not isinstance(ports, dict):
        raise RuntimeError(f"Invalid ports data type: {type(ports)}")

    def _get_host_port(key: str) -> int | None:
        """Extract HostPort from a port mapping entry."""
        entries = ports.get(key)
        if not entries:
            return None
        if not isinstance(entries, list) or not entries:
            return None
        host_port = entries[0].get("HostPort")
        if host_port is None:
            return None
        try:
            return int(host_port)
        except (ValueError, TypeError):
            logger.warning(f"Invalid HostPort value for {key}: {host_port}")
            return None

    # Try 8188 first - this is the standard ComfyUI API port
    # The official vastai/comfy template exposes this port
    port = _get_host_port("8188/tcp")
    if port is not None:
        logger.debug(f"Found ComfyUI port on 8188/tcp -> external port {port}")
        return port

    # Fallback to 8080 (jupyter_direc port, for legacy configurations)
    port = _get_host_port("8080/tcp")
    if port is not None:
        logger.debug(f"Found ComfyUI port on 8080/tcp (fallback) -> external port {port}")
        return port

    # No port found
    available_ports = list(ports.keys()) if ports else []
    raise RuntimeError(
        f"No ComfyUI port mapping found (tried 8080/tcp, 8188/tcp). "
        f"Available ports: {available_ports}"
    )


def build_comfyui_url(instance: "VastInstance", scheme: str = "http") -> str:
    """Build the ComfyUI API base URL from a VastInstance.

    Uses the instance's public_ip and api_port (external mapped port)
    to construct the URL that can be used to access the ComfyUI API.

    IMPORTANT: We use public_ip (public_ipaddr from API), NOT ssh_host.
    ssh_host is an SSH proxy address (e.g., ssh1.vast.ai) for SSH connections only.
    public_ip is the actual public IP for direct HTTP connections.

    Args:
        instance: VastInstance with public_ip and api_port populated
        scheme: URL scheme (http or https), defaults to http

    Returns:
        Base URL string like "http://78.83.187.54:17533"

    Raises:
        ValueError: If instance is missing public_ip or api_port

    Example:
        instance = await client.get_or_create_instance()
        url = build_comfyui_url(instance)
        response = await http.get(f"{url}/system_stats")
    """
    if not instance.public_ip:
        raise ValueError("Instance missing public_ip for ComfyUI URL")
    if not instance.api_port:
        raise ValueError("Instance missing api_port for ComfyUI URL")

    return f"{scheme}://{instance.public_ip}:{instance.api_port}"


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
    api_port: int | None = None  # ComfyUI API port (external mapped port)
    swarmui_port: int | None = None  # SwarmUI API port (7865 external, 17865 internal)
    public_ip: str | None = None  # Direct public IP for HTTP connections
    jupyter_token: str | None = None  # Auth token for API
    template_type: str = "comfyui"  # "comfyui" or "swarmui"
    webpage: str | None = None  # Cloudflare tunnel URL (vast.ai default)


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

        # Build query (vast.ai uses MB for GPU RAM, convert from GB)
        gpu_ram_min_mb = gpu_ram_min * 1024
        query = {
            "gpu_ram": {"gte": gpu_ram_min_mb},
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

    async def create_instance_from_template(
        self,
        offer_id: int,
        template_hash: str | None = None,
        disk_space: int = 50,
    ) -> VastInstance | None:
        """
        Create a vast.ai instance using the official ComfyUI template.

        This is the RECOMMENDED method for creating ComfyUI instances.
        Using a template hash tells Vast.ai to clone the exact configuration
        from their official template, including:
        - Correct Docker image (vastai/comfy:@vastai-automatic-tag)
        - Proper port exposure (8188 for ComfyUI API)
        - Correct startup script (entrypoint.sh)
        - All required environment variables

        Args:
            offer_id: The offer ID to rent
            template_hash: Template hash (defaults to official ComfyUI template)
            disk_space: Disk space in GB (minimum 50GB for models)

        Returns:
            VastInstance if successful, None otherwise
        """
        if not self.api_key:
            return None

        client = await self._get_client()

        # Use the official ComfyUI template hash
        if template_hash is None:
            template_hash = COMFYUI_TEMPLATE_HASH

        # Enforce minimum disk space for video models
        MIN_DISK_GB = 80
        if disk_space < MIN_DISK_GB:
            logger.info(f"Increasing disk space from {disk_space}GB to {MIN_DISK_GB}GB minimum")
            disk_space = MIN_DISK_GB

        # Generate onstart script for model downloads and SageAttention
        onstart_script = self._get_comfyui_onstart_script()

        payload = {
            "client_id": "i2v-app",
            "template_hash_id": template_hash,
            "disk": disk_space,
        }

        # Add onstart script for model downloads
        if onstart_script:
            payload["onstart"] = onstart_script
            logger.info("Added ComfyUI model download script to instance startup")

        logger.info(
            "Creating instance from template",
            offer_id=offer_id,
            template_hash=template_hash,
            disk_space=disk_space,
        )

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
                logger.error("Failed to create instance from template", response=data)
                return None

            logger.info("Created vast.ai instance from template", instance_id=instance_id)

            # Wait for instance to be ready
            instance = await self._wait_for_instance(instance_id)
            self._active_instance = instance
            return instance

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error creating instance from template",
                status_code=e.response.status_code,
                response_text=e.response.text[:500] if e.response.text else None,
            )
            return None
        except Exception as e:
            logger.error("Failed to create vast.ai instance from template", error=str(e))
            return None

    async def _wait_for_instance(
        self, instance_id: int, timeout: int = 300, template_type: str = "comfyui"
    ) -> VastInstance | None:
        """Wait for an instance to be ready.

        Args:
            instance_id: The instance ID to wait for
            timeout: Max seconds to wait
            template_type: "comfyui" or "swarmui" - determines which port to extract
        """
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
                    # Extract ports based on template type
                    api_port = None
                    swarmui_port = None

                    if template_type == "swarmui":
                        try:
                            swarmui_port = _extract_swarmui_port(data)
                        except RuntimeError as e:
                            logger.warning("SwarmUI port not found", error=str(e))
                    else:
                        try:
                            api_port = _extract_comfyui_port(data)
                        except RuntimeError as e:
                            logger.warning("ComfyUI port not found", error=str(e))

                    ssh_host = data.get("ssh_host")
                    public_ip = data.get("public_ipaddr")
                    webpage = data.get("webpage")  # Cloudflare tunnel URL
                    logger.info(
                        "Instance ready",
                        instance_id=instance_id,
                        public_ip=public_ip,
                        webpage=webpage,
                        api_port=api_port,
                        swarmui_port=swarmui_port,
                        template_type=template_type,
                    )

                    return VastInstance(
                        id=instance_id,
                        status=status,
                        gpu_name=data.get("gpu_name", "Unknown"),
                        gpu_ram=data.get("gpu_ram", 0),
                        cpu_cores=data.get("cpu_cores", 0),
                        ram=data.get("cpu_ram", 0),
                        disk_space=data.get("disk_space", 0),
                        dph_total=data.get("dph_total", 0),
                        ssh_host=ssh_host,
                        ssh_port=data.get("ssh_port"),
                        api_port=api_port,
                        swarmui_port=swarmui_port,
                        public_ip=public_ip,
                        jupyter_token=data.get("jupyter_token"),
                        template_type=template_type,
                        webpage=webpage,
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

            # Extract ports for running instances
            status = data.get("actual_status", "unknown")
            api_port = None
            swarmui_port = None
            if status == "running":
                try:
                    api_port = _extract_comfyui_port(data)
                except RuntimeError:
                    pass
                try:
                    swarmui_port = _extract_swarmui_port(data)
                except RuntimeError:
                    pass

            template_type = "swarmui" if swarmui_port else "comfyui"

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
                swarmui_port=swarmui_port,
                public_ip=data.get("public_ipaddr"),
                jupyter_token=data.get("jupyter_token"),
                template_type=template_type,
                webpage=data.get("webpage"),
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
                # Extract ComfyUI port for running instances
                status = inst.get("actual_status", "unknown")
                api_port = None
                swarmui_port = None
                if status == "running":
                    try:
                        api_port = _extract_comfyui_port(inst)
                    except RuntimeError:
                        pass
                    try:
                        swarmui_port = _extract_swarmui_port(inst)
                    except RuntimeError:
                        pass

                # Determine template type from ports
                template_type = "swarmui" if swarmui_port else "comfyui"

                instances.append(VastInstance(
                    id=inst.get("id"),
                    status=status,
                    gpu_name=inst.get("gpu_name", "Unknown"),
                    gpu_ram=inst.get("gpu_ram", 0),
                    cpu_cores=inst.get("cpu_cores", 0),
                    ram=inst.get("cpu_ram", 0),
                    disk_space=inst.get("disk_space", 0),
                    dph_total=inst.get("dph_total", 0),
                    ssh_host=inst.get("ssh_host"),
                    ssh_port=inst.get("ssh_port"),
                    api_port=api_port,
                    swarmui_port=swarmui_port,
                    public_ip=inst.get("public_ipaddr"),
                    jupyter_token=inst.get("jupyter_token"),
                    template_type=template_type,
                    webpage=inst.get("webpage"),
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

        Uses session-based authentication: First establishes a session by
        hitting the root URL with the jupyter_token, then uses the session
        cookie for API requests.

        Args:
            instance: The VastInstance to run on
            workflow: ComfyUI workflow JSON
            timeout: Timeout in seconds

        Returns:
            Result dict with output URLs if successful
        """
        if not instance.public_ip or not instance.api_port:
            logger.error("Instance not ready for API calls (missing public_ip or api_port)")
            return None

        if not instance.jupyter_token:
            logger.error("Instance missing jupyter_token for authentication")
            return None

        api_url = build_comfyui_url(instance)

        # Create a new client with cookie support for session-based auth
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                # Step 1: Establish session by hitting root with token
                logger.debug("Establishing ComfyUI session", url=api_url)
                session_response = await client.get(
                    f"{api_url}/?token={instance.jupyter_token}"
                )
                if session_response.status_code != 200:
                    logger.error("Failed to establish session", status=session_response.status_code)
                    return None

                # Step 2: Submit workflow (session cookie is automatically used)
                response = await client.post(
                    f"{api_url}/prompt",
                    json={"prompt": workflow},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                prompt_id = data.get("prompt_id")

                if not prompt_id:
                    # Check for node_errors in response
                    node_errors = data.get("node_errors", {})
                    if node_errors:
                        logger.error("Workflow validation errors", errors=node_errors)
                    else:
                        logger.error("No prompt_id in response", response=data)
                    return None

                logger.info("Submitted ComfyUI job", prompt_id=prompt_id)

                # Step 3: Poll for completion
                start = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start < timeout:
                    history_response = await client.get(
                        f"{api_url}/history/{prompt_id}",
                        timeout=10.0,
                    )
                    history = history_response.json()

                    if prompt_id in history:
                        # Check for execution errors
                        status_info = history[prompt_id].get("status", {})
                        if status_info.get("status_str") == "error":
                            logger.error("ComfyUI execution error", status=status_info)
                            return None

                        outputs = history[prompt_id].get("outputs", {})
                        if outputs:
                            # Extract output images/videos (pass client for auth)
                            result = await self._process_comfyui_outputs(
                                api_url, outputs, client
                            )
                            return result

                    await asyncio.sleep(2)

                logger.error("ComfyUI job timeout", prompt_id=prompt_id)
                return None

            except Exception as e:
                logger.error("ComfyUI job failed", error=str(e))
                return None

    async def _process_comfyui_outputs(
        self, api_url: str, outputs: dict, client: httpx.AsyncClient
    ) -> dict:
        """Process ComfyUI outputs and cache to R2.

        Args:
            api_url: ComfyUI API base URL
            outputs: ComfyUI outputs dict from history
            client: Authenticated httpx client with session cookie
        """
        result = {"images": [], "videos": []}

        for node_id, node_output in outputs.items():
            # Handle images
            for img in node_output.get("images", []):
                filename = img.get("filename")
                subfolder = img.get("subfolder", "")
                img_url = f"{api_url}/view?filename={filename}&subfolder={subfolder}&type=output"

                # Download using authenticated client, then cache to R2
                try:
                    img_response = await client.get(img_url, timeout=60.0)
                    img_response.raise_for_status()
                    # Cache to R2 using the downloaded bytes
                    cached_url = await cache_image(
                        img_url,
                        prefix="vast-outputs",
                        image_bytes=img_response.content
                    )
                    if cached_url:
                        result["images"].append(cached_url)
                    else:
                        result["images"].append(img_url)
                except Exception as e:
                    logger.error("Failed to fetch/cache image", url=img_url, error=str(e))
                    result["images"].append(img_url)

            # Handle videos/gifs
            for vid in node_output.get("gifs", []):
                filename = vid.get("filename")
                subfolder = vid.get("subfolder", "")
                vid_url = f"{api_url}/view?filename={filename}&subfolder={subfolder}&type=output"

                # Download using authenticated client, then cache to R2
                try:
                    vid_response = await client.get(vid_url, timeout=120.0)
                    vid_response.raise_for_status()
                    # Cache to R2 using the downloaded bytes
                    cached_url = await cache_video(vid_url, video_bytes=vid_response.content)
                    if cached_url:
                        result["videos"].append(cached_url)
                    else:
                        result["videos"].append(vid_url)
                except Exception as e:
                    logger.error("Failed to fetch/cache video", url=vid_url, error=str(e))
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
        Always uses the official Vast.ai ComfyUI template for reliability.

        Args:
            workload: Type of workload (affects GPU RAM and disk requirements)
            max_price: Maximum price per hour in USD

        Returns:
            VastInstance if successful, None otherwise
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

        disk_space = MIN_SPECS[workload]["disk_space"]

        # Use official Vast.ai ComfyUI template
        return await self.create_instance_from_template(
            offer_id=offer["id"],
            disk_space=disk_space,
        )

    async def get_or_create_swarmui_instance(
        self,
        max_price: float = 1.50,
        gpu_name: str = "RTX 5090",
    ) -> VastInstance | None:
        """
        Get an existing SwarmUI instance or create a new one.

        This is the main entry point for SwarmUI video generation on vast.ai.
        Uses the official Vast.ai SwarmUI template which includes:
        - SwarmUI with ComfyUI backend
        - Proper port exposure (7865 external, 17865 internal)
        - Pre-configured for video generation

        Args:
            max_price: Maximum price per hour in USD
            gpu_name: GPU to use (default RTX 5090 for speed)

        Returns:
            VastInstance with swarmui_port populated if successful
        """
        # Check for existing running SwarmUI instance
        instances = await self.list_instances()
        running_swarmui = [
            i for i in instances
            if i.status == "running" and i.template_type == "swarmui"
        ]

        if running_swarmui:
            instance = running_swarmui[0]
            logger.info("Using existing SwarmUI instance", instance_id=instance.id)
            self._active_instance = instance

            # Auto-configure GPU URL if instance has webpage
            if instance.webpage:
                from app.routers.gpu_config import set_swarmui_url
                set_swarmui_url(instance.webpage, instance.id)

            return instance

        # Find RTX 5090 offer (fastest for video gen)
        # Note: RTX 5090 reports ~31.8GB, so use 30GB min
        # Note: RTX 5090 is new, many aren't verified yet
        offers = await self.search_offers(
            gpu_ram_min=30,  # 5090 reports ~31.8GB
            disk_space_min=80,
            max_price=max_price,
            gpu_name=gpu_name,
            verified=False,  # RTX 5090s may not be verified yet
        )

        if not offers:
            logger.error(
                "No RTX 5090 offers found",
                max_price=max_price,
                gpu_name=gpu_name,
                hint="RTX 5090 may not be available at this price. Try increasing max_price.",
            )
            return None

        offer = offers[0]
        logger.info(
            "Creating SwarmUI instance",
            offer_id=offer["id"],
            gpu=offer.get("gpu_name"),
            price=offer.get("dph_total"),
        )

        # Create instance with SwarmUI template
        return await self.create_swarmui_instance(
            offer_id=offer["id"],
            disk_space=80,
        )

    def _get_comfyui_onstart_script(self) -> str:
        """Generate startup script for ComfyUI instances.

        This script:
        1. Downloads Wan 2.2 models from R2 (faster than CivitAI)
        2. Installs SageAttention for faster inference
        3. Installs any missing ComfyUI custom nodes
        """
        script = """#!/bin/bash
set -e
echo "===== i2v ComfyUI Instance Setup ====="

# Create ComfyUI model directories
mkdir -p /workspace/ComfyUI/models/unet
mkdir -p /workspace/ComfyUI/models/text_encoders
mkdir -p /workspace/ComfyUI/models/vae
mkdir -p /workspace/ComfyUI/models/loras
mkdir -p /workspace/ComfyUI/models/checkpoints

echo "===== Installing SageAttention 2 ====="
# Install SageAttention for faster attention (2-3x speedup)
pip install triton --quiet
pip install sageattention --quiet || {
    echo "SageAttention pip install failed, trying from source..."
    pip install git+https://github.com/thu-ml/SageAttention.git --quiet
}
python -c "import sageattention; print(f'SageAttention {sageattention.__version__} installed')" 2>/dev/null || echo "SageAttention install verification failed, continuing..."

echo "===== Downloading Wan 2.2 models from R2 ====="

# Download models in parallel for speed
echo "Starting parallel model downloads..."

# Download Wan 2.2 GGUF (9.6GB)
GGUF_PATH="/workspace/ComfyUI/models/unet/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
if [ ! -f "$GGUF_PATH" ]; then
    wget -q -O "$GGUF_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf" &
    PID1=$!
    echo "Downloading Wan 2.2 GGUF (9.6GB)..."
else
    echo "Wan 2.2 GGUF already exists"
    PID1=""
fi

# Download NSFW GGUF (15.4GB)
NSFW_PATH="/workspace/ComfyUI/models/unet/wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf"
if [ ! -f "$NSFW_PATH" ]; then
    wget -q -O "$NSFW_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf" &
    PID2=$!
    echo "Downloading NSFW GGUF (15.4GB)..."
else
    echo "NSFW GGUF already exists"
    PID2=""
fi

# Download LightX2V LoRA (1.2GB)
LORA_PATH="/workspace/ComfyUI/models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
if [ ! -f "$LORA_PATH" ]; then
    wget -q -O "$LORA_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" &
    PID3=$!
    echo "Downloading LightX2V LoRA (1.2GB)..."
else
    echo "LightX2V LoRA already exists"
    PID3=""
fi

# Wait for all downloads
[ -n "$PID1" ] && wait $PID1 && echo "Wan 2.2 GGUF download complete"
[ -n "$PID2" ] && wait $PID2 && echo "NSFW GGUF download complete"
[ -n "$PID3" ] && wait $PID3 && echo "LightX2V LoRA download complete"

echo "===== Model downloads complete! ====="
ls -la /workspace/ComfyUI/models/unet/
ls -la /workspace/ComfyUI/models/loras/

echo "===== i2v ComfyUI setup complete! ====="
"""
        return script

    def _get_model_download_script(self) -> str:
        """Generate startup script to download Wan 2.2 models from R2 (SwarmUI)."""
        script = """#!/bin/bash
set -e
echo "===== i2v SwarmUI Instance Setup ====="

# Create SwarmUI model directories
mkdir -p /workspace/SwarmUI/Models/diffusion_models
mkdir -p /workspace/SwarmUI/Models/Lora

echo "===== Installing SageAttention 2 ====="
pip install triton --quiet
pip install sageattention --quiet || {
    echo "SageAttention pip install failed, trying from source..."
    pip install git+https://github.com/thu-ml/SageAttention.git --quiet
}
python -c "import sageattention; print('SageAttention installed')" 2>/dev/null || echo "SageAttention check failed, continuing..."

echo "===== Installing xformers ====="
pip install xformers --quiet || echo "xformers install failed, continuing..."

echo "===== Downloading Wan 2.2 models from R2 (parallel) ====="

# Download models in parallel for speed
GGUF_PATH="/workspace/SwarmUI/Models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
NSFW_PATH="/workspace/SwarmUI/Models/diffusion_models/wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf"
LORA_PATH="/workspace/SwarmUI/Models/Lora/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"

# Start parallel downloads
if [ ! -f "$GGUF_PATH" ]; then
    wget -q -O "$GGUF_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf" &
    PID1=$!
    echo "Downloading Wan 2.2 GGUF (9.6GB)..."
else
    echo "Wan 2.2 GGUF already exists"
    PID1=""
fi

if [ ! -f "$NSFW_PATH" ]; then
    wget -q -O "$NSFW_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf" &
    PID2=$!
    echo "Downloading NSFW GGUF (15.4GB)..."
else
    echo "NSFW GGUF already exists"
    PID2=""
fi

if [ ! -f "$LORA_PATH" ]; then
    wget -q -O "$LORA_PATH" "https://pub-10a867f870e7439f8178cad5f323ef29.r2.dev/models/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" &
    PID3=$!
    echo "Downloading LightX2V LoRA (1.2GB)..."
else
    echo "LightX2V LoRA already exists"
    PID3=""
fi

# Wait for all downloads
[ -n "$PID1" ] && wait $PID1 && echo "Wan 2.2 GGUF complete"
[ -n "$PID2" ] && wait $PID2 && echo "NSFW GGUF complete"
[ -n "$PID3" ] && wait $PID3 && echo "LightX2V LoRA complete"

echo "===== Model downloads complete! ====="
ls -la /workspace/SwarmUI/Models/diffusion_models/
ls -la /workspace/SwarmUI/Models/Lora/

echo "===== i2v SwarmUI setup complete! ====="
"""
        return script

    async def create_swarmui_instance(
        self,
        offer_id: int,
        disk_space: int = 80,
        wait_for_healthy: bool = True,
    ) -> VastInstance | None:
        """
        Create a vast.ai instance with SwarmUI ready for video generation.

        Fully automatic flow:
        1. Create instance with SwarmUI Docker image
        2. Wait for instance to be "running"
        3. Extract SwarmUI URL from public_ip:port
        4. Auto-configure GPU URL in runtime config
        5. Wait for SwarmUI to be healthy (accessible)

        Args:
            offer_id: The offer ID to rent
            disk_space: Disk space in GB (80GB minimum for video models)
            wait_for_healthy: Wait for SwarmUI to be accessible (default True)

        Returns:
            VastInstance with swarmui_port if successful, ready for generation
        """
        if not self.api_key:
            return None

        client = await self._get_client()

        # Enforce minimum disk space for video models
        MIN_DISK_GB = 80
        if disk_space < MIN_DISK_GB:
            logger.info(f"Increasing disk space to {MIN_DISK_GB}GB for video models")
            disk_space = MIN_DISK_GB

        # Get model download script
        onstart_script = self._get_model_download_script()

        # Use SwarmUI Docker image directly (template_hash doesn't work)
        # VERIFIED WORKING: vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311
        # Must use jupyter_direct runtype for port exposure
        payload = {
            "client_id": "i2v-swarmui",
            "image": SWARMUI_DOCKER_IMAGE,
            "disk": disk_space,
            "runtype": "jupyter_direct",  # Exposes ports 7865 and 8080
            "onstart": onstart_script,
        }

        logger.info(
            "Creating SwarmUI instance",
            offer_id=offer_id,
            image=SWARMUI_DOCKER_IMAGE,
            disk_space=disk_space,
        )

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
                logger.error("Failed to create SwarmUI instance", response=data)
                return None

            logger.info("Created SwarmUI instance", instance_id=instance_id)

            # Wait for instance with SwarmUI template type
            instance = await self._wait_for_instance(
                instance_id, template_type="swarmui"
            )

            if not instance:
                return None

            self._active_instance = instance

            # Auto-configure GPU URL from public_ip:port or webpage
            swarmui_url = None
            if instance.public_ip and instance.swarmui_port:
                swarmui_url = f"http://{instance.public_ip}:{instance.swarmui_port}"
            elif instance.webpage:
                swarmui_url = instance.webpage

            if swarmui_url:
                from app.routers.gpu_config import set_swarmui_url
                set_swarmui_url(swarmui_url, instance.id)
                logger.info(
                    "Auto-configured SwarmUI URL",
                    url=swarmui_url,
                    instance_id=instance.id,
                )

            # Wait for SwarmUI to be healthy (accessible)
            if wait_for_healthy and swarmui_url:
                instance = await self._wait_for_swarmui_healthy(instance, swarmui_url)

            return instance

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error creating SwarmUI instance",
                status_code=e.response.status_code,
                response_text=e.response.text[:500] if e.response.text else None,
            )
            return None
        except Exception as e:
            logger.error("Failed to create SwarmUI instance", error=str(e))
            return None

    async def _wait_for_swarmui_healthy(
        self,
        instance: VastInstance,
        swarmui_url: str,
        timeout: int = 600,  # 10 minutes max for SwarmUI startup + model downloads
        poll_interval: int = 15,
    ) -> VastInstance:
        """
        Wait for SwarmUI to be accessible via HTTP.

        Polls every 15 seconds, logs status every minute.
        SwarmUI may take several minutes to start (model downloads, etc.)

        Args:
            instance: VastInstance that is already "running"
            swarmui_url: URL to health check
            timeout: Max seconds to wait (default 10 minutes)
            poll_interval: Seconds between health checks (default 15)

        Returns:
            Same instance (for chaining)
        """
        from app.services.swarmui_client import SwarmUIClient

        logger.info(
            "Waiting for SwarmUI to be healthy",
            url=swarmui_url,
            instance_id=instance.id,
            timeout=timeout,
        )

        start = asyncio.get_event_loop().time()
        last_log = 0
        attempts = 0

        while asyncio.get_event_loop().time() - start < timeout:
            elapsed = asyncio.get_event_loop().time() - start
            attempts += 1

            # Log status every minute
            if elapsed - last_log >= 60:
                logger.info(
                    "SwarmUI health check in progress",
                    instance_id=instance.id,
                    elapsed_seconds=int(elapsed),
                    attempts=attempts,
                )
                last_log = elapsed

            # Try health check
            try:
                swarmui_client = SwarmUIClient(base_url=swarmui_url, timeout=10.0)
                healthy = await swarmui_client.health_check()
                await swarmui_client.close()

                if healthy:
                    logger.info(
                        "SwarmUI is healthy and ready",
                        url=swarmui_url,
                        instance_id=instance.id,
                        startup_seconds=int(elapsed),
                    )
                    return instance

            except Exception as e:
                logger.debug(
                    "SwarmUI not yet accessible",
                    error=str(e)[:100],
                    attempt=attempts,
                )

            await asyncio.sleep(poll_interval)

        # Timeout - log warning but return instance anyway (user can retry)
        logger.warning(
            "SwarmUI health check timeout - instance may still be starting",
            instance_id=instance.id,
            timeout=timeout,
            url=swarmui_url,
        )
        return instance

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

    async def sync_model_to_instance(
        self,
        instance: VastInstance,
        r2_url: str,
        destination_path: str,
    ) -> bool:
        """
        Download a model from R2 directly to a running instance via SSH.

        This allows adding models dynamically without restarting the instance.

        Args:
            instance: Running VastInstance with SSH access
            r2_url: Public R2 URL for the model
            destination_path: Full path on instance (e.g., /workspace/SwarmUI/Models/diffusion_models/model.safetensors)

        Returns:
            True if successful
        """
        if not instance.ssh_host or not instance.ssh_port:
            logger.error("Instance missing SSH info")
            return False

        # Build wget command to run on instance
        wget_cmd = f'wget -q -O "{destination_path}" "{r2_url}"'
        mkdir_cmd = f'mkdir -p "$(dirname {destination_path})"'
        full_cmd = f'{mkdir_cmd} && {wget_cmd}'

        logger.info(
            "Syncing model to instance",
            r2_url=r2_url[:60],
            destination=destination_path,
            instance_id=instance.id,
        )

        # Use vast.ai execute endpoint (no SSH key needed)
        client = await self._get_client()
        try:
            response = await client.put(
                f"{VASTAI_API_URL}/instances/{instance.id}/",
                headers=self._headers(),
                json={"remote_cmd": full_cmd},
                timeout=300.0,  # Long timeout for large model downloads
            )
            response.raise_for_status()
            logger.info("Model sync command sent", instance_id=instance.id)
            return True
        except Exception as e:
            logger.error("Failed to sync model", error=str(e))
            return False

    async def add_model_from_url(
        self,
        source_url: str,
        model_name: str,
        model_type: str = "diffusion_models",
        instance: VastInstance | None = None,
    ) -> str | None:
        """
        Download a model from any URL, upload to R2, and sync to running instance.

        Args:
            source_url: URL to download from (CivitAI, HuggingFace, etc.)
            model_name: Filename to use (e.g., "my_model.safetensors")
            model_type: "diffusion_models" or "Lora" (SwarmUI folder)
            instance: Optional running instance to sync to

        Returns:
            R2 URL if successful
        """
        from app.services.r2_cache import get_s3_client, get_public_url, get_bucket

        client = get_s3_client()
        public_url = get_public_url()
        bucket = get_bucket()

        if not client or not public_url:
            logger.error("R2 not configured")
            return None

        key = f"models/{model_name}"

        # Check if already in R2
        try:
            client.head_object(Bucket=bucket, Key=key)
            r2_url = f"{public_url}/{key}"
            logger.info("Model already in R2", key=key)
        except Exception:
            # Download and upload to R2
            logger.info("Downloading model from source", url=source_url[:80])

            http = await self._get_client()
            try:
                # Stream download for large files
                async with http.stream("GET", source_url, timeout=600.0, follow_redirects=True) as response:
                    response.raise_for_status()
                    chunks = []
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunks.append(chunk)
                    model_data = b"".join(chunks)

                # Upload to R2
                logger.info("Uploading to R2", size_mb=len(model_data) / (1024 * 1024))
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=model_data,
                    ContentType="application/octet-stream",
                )
                r2_url = f"{public_url}/{key}"
                logger.info("Model uploaded to R2", url=r2_url)
            except Exception as e:
                logger.error("Failed to download/upload model", error=str(e))
                return None

        # Sync to running instance if provided
        if instance:
            if model_type == "Lora":
                dest_path = f"/workspace/SwarmUI/Models/Lora/{model_name}"
            else:
                dest_path = f"/workspace/SwarmUI/Models/diffusion_models/{model_name}"

            await self.sync_model_to_instance(instance, r2_url, dest_path)

        return r2_url

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
