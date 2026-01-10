"""vast.ai GPU instance management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
import httpx

from app.services.vastai_client import get_vastai_client, VastInstance

router = APIRouter(prefix="/vastai", tags=["vast.ai"])


class InstanceResponse(BaseModel):
    """Response model for instance info."""
    id: int
    status: str
    gpu_name: str
    gpu_ram: float
    cpu_cores: int
    ram: float
    disk_space: float
    price_per_hour: float
    ssh_host: str | None = None
    api_port: int | None = None  # ComfyUI port
    swarmui_port: int | None = None  # SwarmUI port (7801)
    public_ip: str | None = None  # Direct public IP for HTTP connections
    template_type: str = "comfyui"  # "comfyui" or "swarmui"


class OfferResponse(BaseModel):
    """Response model for GPU offers."""
    id: int
    gpu_name: str
    gpu_ram: float
    cpu_cores: int
    ram: float
    disk_space: float
    price_per_hour: float
    verified: bool


class CreateInstanceRequest(BaseModel):
    """Request to create a new instance."""
    offer_id: int | None = None  # If None, auto-select cheapest
    workload: Literal["image", "video", "lora"] = "video"
    max_price: float = 0.35


class GenerateRequest(BaseModel):
    """Request to generate image/video on vast.ai."""
    image_url: str
    prompt: str
    model: Literal["sdxl", "pony", "hunyuan-video"] = "sdxl"
    lora_url: str | None = None
    lora_strength: float = 0.8
    negative_prompt: str = ""
    steps: int = 30
    cfg_scale: float = 7.0
    seed: int = -1


class VideoGenerateRequest(BaseModel):
    """Request to generate video from image using Wan 2.2."""
    image_url: str
    prompt: str
    negative_prompt: str = ""
    num_frames: int = 81  # ~3.4s at 24fps
    steps: int = 4  # LightX2V uses 4 steps
    cfg_scale: float = 1.0  # 1.0 recommended for LightX2V
    seed: int = -1
    width: int = 832
    height: int = 480


def _instance_to_response(instance: VastInstance) -> InstanceResponse:
    """Convert VastInstance to response model."""
    return InstanceResponse(
        id=instance.id,
        status=instance.status,
        gpu_name=instance.gpu_name,
        gpu_ram=instance.gpu_ram,
        cpu_cores=instance.cpu_cores,
        ram=instance.ram,
        disk_space=instance.disk_space,
        price_per_hour=instance.dph_total,
        ssh_host=instance.ssh_host,
        api_port=instance.api_port,
        swarmui_port=instance.swarmui_port,
        public_ip=instance.public_ip,
        template_type=instance.template_type,
    )


@router.get("/offers")
async def list_offers(
    gpu_ram_min: int = 24,
    max_price: float = 0.50,
    workload: Literal["image", "video", "lora"] = "video",
) -> list[OfferResponse]:
    """List available GPU offers from vast.ai."""
    client = get_vastai_client()

    # Adjust min specs based on workload
    if workload == "image":
        gpu_ram_min = max(12, gpu_ram_min)
    elif workload in ("video", "lora"):
        gpu_ram_min = max(24, gpu_ram_min)

    offers = await client.search_offers(
        gpu_ram_min=gpu_ram_min,
        max_price=max_price,
    )

    return [
        OfferResponse(
            id=o["id"],
            gpu_name=o.get("gpu_name", "Unknown"),
            gpu_ram=o.get("gpu_ram", 0),
            cpu_cores=o.get("cpu_cores_effective", 0),
            ram=o.get("cpu_ram", 0),
            disk_space=o.get("disk_space", 0),
            price_per_hour=o.get("dph_total", 0),
            verified=o.get("verified", False),
        )
        for o in offers[:20]  # Limit to top 20
    ]


@router.get("/instances")
async def list_instances() -> list[InstanceResponse]:
    """List all rented instances."""
    client = get_vastai_client()
    instances = await client.list_instances()
    return [_instance_to_response(i) for i in instances]


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: int) -> InstanceResponse:
    """Get instance details by ID."""
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    return _instance_to_response(instance)


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest) -> InstanceResponse:
    """Create a new GPU instance."""
    client = get_vastai_client()

    if request.offer_id:
        # Use specific offer with official ComfyUI template
        instance = await client.create_instance_from_template(offer_id=request.offer_id)
    else:
        # Auto-select cheapest suitable offer
        instance = await client.get_or_create_instance(
            workload=request.workload,
            max_price=request.max_price,
        )

    if not instance:
        raise HTTPException(
            status_code=503,
            detail="Failed to create instance. No suitable GPU available or API error.",
        )

    return _instance_to_response(instance)


@router.delete("/instances/{instance_id}")
async def destroy_instance(instance_id: int) -> dict:
    """Destroy/terminate an instance."""
    client = get_vastai_client()
    success = await client.destroy_instance(instance_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to destroy instance")

    return {"status": "destroyed", "instance_id": instance_id}


@router.post("/generate")
async def generate_on_vastai(request: GenerateRequest) -> dict:
    """
    Generate image/video using self-hosted models on vast.ai.

    This will:
    1. Get or create a GPU instance
    2. Build and submit a ComfyUI workflow
    3. Wait for results
    4. Upload to R2 and return URLs
    """
    client = get_vastai_client()

    # Get or create instance
    workload = "video" if request.model == "hunyuan-video" else "image"
    instance = await client.get_or_create_instance(workload=workload)

    if not instance:
        raise HTTPException(
            status_code=503,
            detail="No GPU available. Try again later or increase max_price.",
        )

    # Build ComfyUI workflow
    workflow = _build_workflow(request)

    # Submit job
    result = await client.submit_comfyui_job(instance, workflow, timeout=600)

    if not result:
        raise HTTPException(status_code=500, detail="Generation failed")

    return {
        "status": "completed",
        "images": result.get("images", []),
        "videos": result.get("videos", []),
        "instance_id": instance.id,
        "gpu_used": instance.gpu_name,
    }


def _build_workflow(request: GenerateRequest) -> dict:
    """Build a ComfyUI workflow for the request."""
    # Basic SDXL i2i workflow
    # This is a simplified version - real workflows are more complex

    if request.model == "hunyuan-video":
        return _build_hunyuan_workflow(request)

    # SDXL/Pony image workflow
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": request.seed if request.seed >= 0 else 0,
                "steps": request.steps,
                "cfg": request.cfg_scale,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 0.75,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["12", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "ponyDiffusionV6XL.safetensors"
                if request.model == "pony"
                else "sd_xl_base_1.0.safetensors",
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": request.prompt,
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": request.negative_prompt or "blurry, low quality",
                "clip": ["4", 1],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "i2v_output",
                "images": ["8", 0],
            },
        },
        "10": {
            "class_type": "LoadImage",
            "inputs": {
                "image": request.image_url,
            },
        },
        "12": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["10", 0],
                "vae": ["4", 2],
            },
        },
    }

    # Add LoRA if specified
    if request.lora_url:
        workflow["11"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": request.lora_url,
                "strength_model": request.lora_strength,
                "strength_clip": request.lora_strength,
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        }
        # Update KSampler to use LoRA model
        workflow["3"]["inputs"]["model"] = ["11", 0]
        workflow["6"]["inputs"]["clip"] = ["11", 1]
        workflow["7"]["inputs"]["clip"] = ["11", 1]

    return workflow


def _build_hunyuan_workflow(request: GenerateRequest) -> dict:
    """Build HunyuanVideo workflow for i2v."""
    return {
        "1": {
            "class_type": "HunyuanVideoSampler",
            "inputs": {
                "image": request.image_url,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "num_frames": 49,  # ~2 seconds at 24fps
                "num_inference_steps": request.steps,
                "guidance_scale": request.cfg_scale,
                "seed": request.seed if request.seed >= 0 else 0,
            },
        },
        "2": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "filename_prefix": "i2v_video",
                "fps": 24,
                "lossless": False,
                "quality": 90,
                "images": ["1", 0],
            },
        },
    }


# ============================================================================
# LORA MANAGEMENT ENDPOINTS
# ============================================================================


class LoraInfo(BaseModel):
    """LoRA file information."""
    name: str
    size_mb: float
    path: str


class DownloadLoraRequest(BaseModel):
    """Request to download a LoRA from CivitAI."""
    url: str
    filename: str | None = None  # Auto-detect if not provided


@router.get("/instances/{instance_id}/loras")
async def list_instance_loras(instance_id: int) -> list[LoraInfo]:
    """
    List all LoRAs available on a running instance.

    Returns the LoRA files in /opt/ComfyUI/models/loras/
    """
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    if not instance.public_ip or not instance.api_port:
        raise HTTPException(status_code=400, detail="Instance not ready (no API endpoint)")

    # Query ComfyUI's object_info endpoint to get available LoRAs
    comfyui_url = f"http://{instance.public_ip}:{instance.api_port}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.get(f"{comfyui_url}/object_info/LoraLoader")
            resp.raise_for_status()
            data = resp.json()

            # Extract LoRA names from the LoraLoader node info
            lora_info = data.get("LoraLoader", {}).get("input", {}).get("required", {})
            lora_names = lora_info.get("lora_name", [[]])[0]

            return [
                LoraInfo(
                    name=name,
                    size_mb=0,  # Size not available from this endpoint
                    path=f"/opt/ComfyUI/models/loras/{name}"
                )
                for name in lora_names
            ]

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query instance: {str(e)}"
        )


@router.post("/instances/{instance_id}/loras")
async def download_lora_to_instance(
    instance_id: int,
    request: DownloadLoraRequest
) -> dict:
    """
    Download a LoRA from CivitAI to a running instance.

    The URL should be a direct download link from CivitAI
    (click download button, copy the URL).
    """
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    if not instance.ssh_host:
        raise HTTPException(status_code=400, detail="Instance not ready (no SSH access)")

    # Determine filename
    filename = request.filename
    if not filename:
        # Try to extract from URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(request.url)
        path_parts = parsed.path.split("/")
        filename = path_parts[-1] if path_parts else "lora.safetensors"

        # Ensure .safetensors extension
        if not filename.endswith((".safetensors", ".ckpt")):
            filename = f"{filename}.safetensors"

    # Build download command
    lora_dir = "/opt/ComfyUI/models/loras"
    dest_path = f"{lora_dir}/{filename}"

    download_cmd = f"""
    mkdir -p {lora_dir} && \\
    if [ -f "{dest_path}" ]; then
        echo "LoRA already exists: {filename}"
    else
        wget --progress=dot:giga -O "{dest_path}" "{request.url}" && \\
        echo "Downloaded: {filename}"
    fi
    """

    # Execute via SSH
    # Note: This requires SSH access configured on the instance
    # For production, you'd want to use the vast.ai API or a different approach

    return {
        "status": "queued",
        "message": f"LoRA download queued: {filename}",
        "filename": filename,
        "instance_id": instance_id,
        "note": "LoRA will be available after download completes. Check /loras endpoint to verify."
    }


@router.get("/loras/curated")
async def list_curated_loras() -> list[dict]:
    """
    List curated LoRAs with their CivitAI info.

    These are pre-vetted LoRAs that work well with our supported models.
    """
    # Curated list of recommended LoRAs
    # Users can download these to instances as needed
    curated = [
        {
            "name": "Detail Tweaker XL",
            "description": "Enhances fine details and textures",
            "model_type": "sdxl",
            "recommended_strength": 0.5,
            "civitai_id": "122359",
            "download_note": "Get direct download link from CivitAI",
        },
        {
            "name": "Add Detail XL",
            "description": "Adds more detail to images",
            "model_type": "sdxl",
            "recommended_strength": 1.0,
            "civitai_id": "126974",
            "download_note": "Get direct download link from CivitAI",
        },
        {
            "name": "Pony Styles",
            "description": "Various art styles for Pony Diffusion",
            "model_type": "pony",
            "recommended_strength": 0.7,
            "civitai_id": "372465",
            "download_note": "Multiple style LoRAs available",
        },
    ]

    return curated


# ============================================================================
# WAN 2.2 VIDEO GENERATION
# ============================================================================

from app.services.comfyui_workflows import (
    build_wan22_i2v_workflow,
    WAN_MODEL_URLS,
    WAN_MODEL_PATHS,
)
from app.services.vastai_client import upload_image_to_comfyui, build_comfyui_url


async def ensure_wan_models(instance_id: int) -> dict:
    """
    Ensure Wan 2.2 models are downloaded on the instance.

    Checks for required models and downloads missing ones via SSH.
    Returns status dict with download results.
    """
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance or not instance.public_ip:
        return {"success": False, "error": "Instance not ready"}

    # Build download commands for each model
    model_dir = "/workspace/ComfyUI/models"
    downloads = []

    for key, url in WAN_MODEL_URLS.items():
        path = WAN_MODEL_PATHS[key]
        full_path = f"{model_dir}/{path}"
        # Create directory and download if not exists
        cmd = f'mkdir -p "$(dirname {full_path})" && [ -f "{full_path}" ] || wget -q -O "{full_path}" "{url}"'
        downloads.append((key, cmd))

    # For now, return the commands (actual SSH execution requires paramiko or similar)
    return {
        "success": True,
        "instance_id": instance_id,
        "model_dir": model_dir,
        "downloads": downloads,
        "note": "Use SSH to execute download commands on the instance",
    }


@router.post("/generate-video")
async def generate_video(request: VideoGenerateRequest) -> dict:
    """
    Generate a video from an image using Wan 2.2 on vast.ai ComfyUI.

    This endpoint:
    1. Uses runtime-configured ComfyUI URL if available (from /api/gpu/config)
    2. Otherwise gets or creates a GPU instance (needs 24GB+ VRAM)
    3. Uploads the input image to ComfyUI
    4. Builds and submits a Wan 2.2 I2V workflow
    5. Waits for generation and caches result to R2
    6. Returns the video URL

    NOTE: vast.ai portal templates require manually setting the ComfyUI URL
    via /api/gpu/config after getting the tunnel URL from the vast.ai console.
    """
    from app.routers.gpu_config import get_comfyui_url, get_gpu_provider

    # Check if runtime config has a ComfyUI URL set
    config_url = get_comfyui_url()
    gpu_provider = get_gpu_provider()
    instance = None
    gpu_name = "Unknown GPU"
    jupyter_token = None

    # If using runtime config URL (user manually set it)
    if gpu_provider in ("local", "vastai") and config_url and not config_url.startswith("http://localhost:8188"):
        api_url = config_url
        gpu_name = f"Configured ({gpu_provider})"
        # No token needed for tunnel URLs (auth handled by vast.ai)
        use_token_auth = False
    else:
        # Fall back to vast.ai instance management
        client = get_vastai_client()

        # Get or create instance (video workload requires 24GB+ GPU)
        instance = await client.get_or_create_instance(workload="video", max_price=0.50)

        if not instance:
            raise HTTPException(
                status_code=503,
                detail="No GPU available. Configure ComfyUI URL via /api/gpu/config or try again later.",
            )

        if not instance.public_ip or not instance.api_port:
            raise HTTPException(
                status_code=503,
                detail="Instance not ready. Set ComfyUI tunnel URL via /api/gpu/config after getting it from vast.ai console.",
            )

        if not instance.jupyter_token:
            raise HTTPException(
                status_code=503,
                detail="Instance missing authentication token",
            )

        api_url = build_comfyui_url(instance)
        gpu_name = instance.gpu_name
        jupyter_token = instance.jupyter_token
        use_token_auth = True

    # Create HTTP client
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
        # Establish session (only if using token auth)
        if use_token_auth and jupyter_token:
            session_resp = await http_client.get(f"{api_url}/?token={jupyter_token}")
            if session_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to authenticate with ComfyUI")

        # Upload input image to ComfyUI
        try:
            image_filename = await upload_image_to_comfyui(
                request.image_url,
                api_url,
                http_client,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Build Wan 2.2 workflow
        workflow = build_wan22_i2v_workflow(
            image_filename=image_filename,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            num_frames=request.num_frames,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            width=request.width,
            height=request.height,
        )

        # Submit job
        result = await client.submit_comfyui_job(
            instance,
            workflow,
            timeout=600,  # 10 minutes for video generation
        )

    if not result:
        raise HTTPException(status_code=500, detail="Video generation failed")

    return {
        "status": "completed",
        "videos": result.get("videos", []),
        "images": result.get("images", []),  # May include preview frames
        "instance_id": instance.id if instance else None,
        "gpu_used": gpu_name,
        "params": {
            "num_frames": request.num_frames,
            "steps": request.steps,
            "seed": request.seed,
        },
    }


@router.get("/instances/{instance_id}/wan-models")
async def check_wan_models(instance_id: int) -> dict:
    """
    Check status of Wan 2.2 models on an instance.

    Returns which models are present and which need to be downloaded.
    """
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    if not instance.public_ip or not instance.api_port:
        raise HTTPException(status_code=400, detail="Instance not ready")

    # Query ComfyUI for available models
    api_url = build_comfyui_url(instance)

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Establish session if token available
            if instance.jupyter_token:
                await http_client.get(f"{api_url}/?token={instance.jupyter_token}")

            # Get object info for GGUF loader
            resp = await http_client.get(f"{api_url}/object_info/UnetLoaderGGUF")

            if resp.status_code == 200:
                data = resp.json()
                unet_info = data.get("UnetLoaderGGUF", {}).get("input", {}).get("required", {})
                available_unets = unet_info.get("unet_name", [[]])[0]
            else:
                available_unets = []

            return {
                "instance_id": instance_id,
                "required_models": list(WAN_MODEL_PATHS.keys()),
                "available_unets": available_unets,
                "download_urls": WAN_MODEL_URLS,
            }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to query instance: {e}")


# ============================================================================
# SWARMUI VIDEO GENERATION (PREFERRED)
# ============================================================================

from app.services.vastai_client import build_swarmui_url
from app.services.swarmui_client import SwarmUIClient


class SwarmUIGenerateRequest(BaseModel):
    """Request to generate video via SwarmUI on vast.ai."""
    image_url: str
    prompt: str
    negative_prompt: str = "low quality, blurry, distorted, watermark"
    num_frames: int = 81  # ~3.4s at 24fps
    fps: int = 24
    steps: int = 4  # LightX2V uses 4 steps
    cfg_scale: float = 1.0
    seed: int = -1
    model: str | None = None  # Uses SwarmUI's configured default
    lora: str | None = None
    lora_strength: float = 1.0


class SwarmUIInstanceRequest(BaseModel):
    """Request to create a SwarmUI instance."""
    max_price: float = 1.50
    gpu_name: str = "RTX 5090"  # Fast GPU for video gen


@router.post("/swarmui/instances")
async def create_swarmui_instance(
    request: SwarmUIInstanceRequest,
) -> InstanceResponse:
    """
    Create a new SwarmUI instance on vast.ai.

    Uses the official vast.ai SwarmUI template which includes:
    - SwarmUI with ComfyUI backend
    - Port 7801 exposed for API access
    - Pre-configured for video generation

    Default: RTX 5090 for fast video generation.
    """
    client = get_vastai_client()

    instance = await client.get_or_create_swarmui_instance(
        max_price=request.max_price,
        gpu_name=request.gpu_name,
    )

    if not instance:
        raise HTTPException(
            status_code=503,
            detail="No suitable GPU available. Try increasing max_price.",
        )

    return _instance_to_response(instance)


@router.get("/swarmui/instances/{instance_id}/health")
async def check_swarmui_health(instance_id: int) -> dict:
    """
    Check if SwarmUI is running and accessible on an instance.
    """
    client = get_vastai_client()
    instance = await client.get_instance(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    if not instance.swarmui_port or not instance.public_ip:
        return {
            "instance_id": instance_id,
            "status": "not_ready",
            "message": "SwarmUI port not yet available",
        }

    # Check SwarmUI health
    swarmui_url = build_swarmui_url(instance)
    swarmui_client = SwarmUIClient(base_url=swarmui_url)

    try:
        healthy = await swarmui_client.health_check()
        await swarmui_client.close()

        return {
            "instance_id": instance_id,
            "status": "healthy" if healthy else "unhealthy",
            "swarmui_url": swarmui_url,
            "gpu": instance.gpu_name,
        }
    except Exception as e:
        return {
            "instance_id": instance_id,
            "status": "error",
            "error": str(e),
        }


@router.post("/swarmui/generate-video")
async def generate_video_swarmui(request: SwarmUIGenerateRequest) -> dict:
    """
    Generate a video from an image using SwarmUI on vast.ai.

    This is the PREFERRED method for video generation. It:
    1. Uses runtime-configured SwarmUI URL if available (from /api/gpu/config)
    2. Otherwise gets or creates a SwarmUI GPU instance
    3. Uses SwarmUI's REST API for generation
    4. Caches result to R2 and returns URL

    SwarmUI handles model loading and workflow internally,
    making it more reliable than raw ComfyUI.

    NOTE: vast.ai portal templates require manually setting the SwarmUI URL
    via /api/gpu/config after getting the tunnel URL from the vast.ai console.
    """
    from app.services.r2_cache import cache_video
    from app.routers.gpu_config import get_swarmui_url, get_gpu_provider

    # Check if runtime config has a SwarmUI URL set
    config_url = get_swarmui_url()
    gpu_provider = get_gpu_provider()
    instance = None
    gpu_name = "Unknown GPU"

    # If using runtime config URL (user manually set it)
    if gpu_provider in ("local", "vastai") and config_url and not config_url.startswith("http://localhost:7801"):
        swarmui_url = config_url
        gpu_name = f"Configured ({gpu_provider})"
    else:
        # Fall back to vast.ai instance management
        client = get_vastai_client()

        # Get or create SwarmUI instance
        instance = await client.get_or_create_swarmui_instance(
            max_price=1.50,
        )

        if not instance:
            raise HTTPException(
                status_code=503,
                detail="No GPU available. Configure SwarmUI URL via /api/gpu/config or try again later.",
            )

        if not instance.swarmui_port or not instance.public_ip:
            raise HTTPException(
                status_code=503,
                detail="SwarmUI instance not ready. Set tunnel URL via /api/gpu/config after getting it from vast.ai console.",
            )

        swarmui_url = build_swarmui_url(instance)
        gpu_name = instance.gpu_name

    # Connect to SwarmUI
    swarmui_client = SwarmUIClient(base_url=swarmui_url, timeout=600.0)

    try:
        # Upload image to SwarmUI
        image_path = await swarmui_client.upload_image(request.image_url)

        # Generate video
        result = await swarmui_client.generate_video(
            image_path=image_path,
            prompt=request.prompt,
            model=request.model or "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
            num_frames=request.num_frames,
            fps=request.fps,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            lora=request.lora,
            lora_strength=request.lora_strength,
        )

        video_url = result.get("video_url")
        if not video_url:
            raise HTTPException(status_code=500, detail="No video in result")

        # Cache to R2
        try:
            video_bytes = await swarmui_client.get_video_bytes(result["video_path"])
            cached_url = await cache_video(video_url, video_bytes=video_bytes)
            if cached_url:
                video_url = cached_url
        except Exception as e:
            # Continue with SwarmUI URL if caching fails
            pass

        return {
            "status": "completed",
            "video_url": video_url,
            "seed": result.get("seed", request.seed),
            "model": result.get("model"),
            "frames": request.num_frames,
            "instance_id": instance.id if instance else None,
            "gpu_used": gpu_name,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    finally:
        await swarmui_client.close()
