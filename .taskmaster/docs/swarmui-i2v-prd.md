# PRD: SwarmUI-Based Image-to-Video Generation

## Overview

Integrate SwarmUI as our self-hosted image-to-video backend, replacing the failed raw ComfyUI approach. SwarmUI provides a user-friendly GUI for local development/testing while exposing a full REST API for programmatic integration with our existing FastAPI backend.

**Development Strategy:** Build and test locally first, then deploy to vast.ai GPU instances.

## Current State

- **Working:** fal.ai Wan 2.5 integration (`fal_client.py`, `prd.txt`)
- **Working:** vast.ai instance management (`vastai_client.py`)
- **Working:** R2 caching for outputs (`r2_cache.py`)
- **Failed:** Raw ComfyUI workflow approach (wrong node names, missing custom nodes)

## Goals

1. Set up SwarmUI locally on Windows for development
2. Configure Wan 2.2 I2V models with LightX2V LoRA (fast 4-step generation)
3. Build `swarmui_client.py` service to integrate with existing backend
4. Test I2V generation works via API (not GUI clicks)
5. Deploy SwarmUI to vast.ai for production

## Tech Stack

- **Local Dev:** SwarmUI on Windows (RTX 5060, 8GB VRAM - test only)
- **Production:** SwarmUI on vast.ai (RTX 4090/5090, 24GB+ VRAM)
- **Backend:** Existing FastAPI app
- **Storage:** R2 for output caching (already working)

---

## Phase 1: Local SwarmUI Setup

### 1.1 Install SwarmUI on Windows

SwarmUI installation on Windows:
- Download from https://github.com/mcmonkeyprojects/SwarmUI/releases
- Run installer or use `launch-windows.bat`
- Default port: 7801
- ComfyUI backend auto-configured

### 1.2 Download Wan 2.2 I2V Models

Models go in `SwarmUI/Models/` subfolders:

**Diffusion Models** (`diffusion_models/Wan/`):
- `Wan2.2-I2V-14B-High.safetensors` - High noise model
- `Wan2.2-I2V-14B-Low.safetensors` - Low noise model (refiner)
- Or GGUF quantized versions for lower VRAM

**LoRAs** (`Loras/`):
- `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`
- `wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`

**VAE** (auto-downloads or manual):
- `wan_2.1_vae.safetensors`

**Text Encoder** (auto-downloads or manual):
- UMT5-XXL encoder

### 1.3 Verify Local Setup

1. Open SwarmUI GUI at http://localhost:7801
2. Load Wan 2.2 I2V model
3. Upload test image via "Init Image"
4. Set "Init Image Creativity" to 0
5. Generate video - confirm it starts (even if slow on 8GB VRAM)

---

## Phase 2: SwarmUI API Integration

### 2.1 Create `swarmui_client.py`

New service file following the pattern of `fal_client.py`:

```python
# app/services/swarmui_client.py

class SwarmUIClient:
    """Client for SwarmUI API - local or remote."""

    def __init__(self, base_url: str = "http://localhost:7801"):
        self.base_url = base_url
        self.session_id: str | None = None

    async def get_session(self) -> str:
        """Get or refresh SwarmUI session."""
        # POST /API/GetNewSession
        pass

    async def upload_image(self, image_url: str) -> str:
        """Download image from URL and upload to SwarmUI."""
        # Similar to upload_image_to_comfyui but for SwarmUI
        pass

    async def generate_video(
        self,
        image_path: str,  # SwarmUI internal path after upload
        prompt: str,
        num_frames: int = 81,
        fps: int = 24,
        steps: int = 4,  # LightX2V uses 4 steps
        cfg_scale: float = 3.5,  # Wan I2V recommended
        seed: int = -1,
    ) -> str:
        """Generate video from image using Wan 2.2 I2V."""
        # POST /API/GenerateText2ImageWS with video params
        pass

    async def get_result(self, generation_id: str) -> dict:
        """Poll for generation result."""
        pass
```

### 2.2 API Endpoints

SwarmUI API reference:
- `POST /API/GetNewSession` - Get session_id (required for all calls)
- `POST /API/GenerateText2Image` - Sync generation
- `WS /API/GenerateText2ImageWS` - Async with progress updates
- `GET /View/{path}` - Retrieve generated outputs

Key parameters for I2V:
- `session_id` - Required
- `prompt` - Motion/content description
- `model` - Base model (can be placeholder for I2V)
- `initimage` - Path to uploaded image
- `initimagecreativity` - Set to 0 for pure I2V
- `videomodel` - Wan 2.2 I2V model
- `videoframes` - Number of frames
- `videocfg` - CFG scale for video (3.5 for Wan I2V)
- `videosteps` - Sampling steps (4 with LightX2V)

### 2.3 Add Router Endpoint

Add to `app/routers/swarmui.py` or extend `vastai.py`:

```python
@router.post("/swarm/generate-video")
async def generate_video_swarm(request: VideoGenerateRequest) -> dict:
    """Generate video using local/remote SwarmUI."""
    client = get_swarmui_client()

    # Upload image
    image_path = await client.upload_image(request.image_url)

    # Generate video
    result = await client.generate_video(
        image_path=image_path,
        prompt=request.prompt,
        num_frames=request.num_frames,
        # ...
    )

    # Cache to R2
    cached_url = await cache_video(result["video_url"])

    return {"video_url": cached_url}
```

---

## Phase 3: vast.ai Deployment

### 3.1 SwarmUI Docker/Template

Options for running SwarmUI on vast.ai:
1. **Custom Docker image** with SwarmUI + models pre-installed
2. **Startup script** that installs SwarmUI on instance boot
3. **Find existing SwarmUI template** on vast.ai marketplace

Research needed: Best approach for SwarmUI on vast.ai (Docker image vs startup script)

### 3.2 Update `vastai_client.py`

Changes needed:
- Different Docker image or template hash for SwarmUI
- Port 7801 instead of 8188
- SwarmUI-specific health check endpoint
- Model download paths for SwarmUI structure

### 3.3 Environment Configuration

```bash
# .env additions
SWARMUI_URL=http://localhost:7801  # Local dev
# SWARMUI_URL=http://{vast_ip}:{port}  # Production (set dynamically)

SWARMUI_MODEL=Wan/Wan2.2-I2V-14B  # Model path in SwarmUI
SWARMUI_LORA=wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise
```

---

## Phase 4: Testing & Validation

### 4.1 Local Testing

1. Start SwarmUI locally
2. Run FastAPI backend
3. Call `/swarm/generate-video` endpoint with test image
4. Verify video is generated and cached to R2

### 4.2 Integration Testing

1. Test with existing frontend
2. Verify same UX as fal.ai integration
3. Compare generation quality/speed

### 4.3 vast.ai Testing

1. Deploy SwarmUI to vast.ai instance
2. Update SWARMUI_URL to point to instance
3. Run same tests against remote SwarmUI
4. Verify R2 caching works with remote outputs

---

## Model Downloads

### Wan 2.2 I2V Models (HuggingFace URLs)

```
# High noise GGUF (for lower VRAM)
https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf

# Low noise GGUF (refiner)
https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf

# LightX2V LoRAs (4-step fast generation)
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors

# VAE
https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors
```

---

## Success Criteria

1. Can generate video from image via SwarmUI API (no GUI interaction)
2. Integration works with existing FastAPI backend
3. Videos are cached to R2 with public URLs
4. Local dev workflow: edit code -> test locally -> works
5. Production deployment: same code works on vast.ai
6. Generation time: <2 minutes for 81 frames with LightX2V

---

## Out of Scope

- SwarmUI GUI customization
- Text-to-video (T2V) - focus on I2V only
- Multiple video model support (just Wan 2.2 for now)
- Real-time progress updates to frontend (can add later)

---

## References

- SwarmUI GitHub: https://github.com/mcmonkeyprojects/SwarmUI
- SwarmUI API Docs: https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md
- Video Model Support: https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/Video%20Model%20Support.md
- Wan 2.2 on HuggingFace: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged
