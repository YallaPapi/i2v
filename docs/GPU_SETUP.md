# GPU Video Generation Setup Guide

This guide explains how to set up and use the self-hosted GPU option ("Wan 2.2 GPU") for video generation using vast.ai.

## Overview

The i2v platform supports two video generation modes:

1. **Cloud (fal.ai)** - Pay-per-generation pricing, no setup required
2. **Self-hosted GPU (vast.ai)** - Pay-per-hour pricing, requires setup

The self-hosted option uses Wan 2.2 with LightX2V acceleration on rented vast.ai GPUs.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GPU Generation Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Frontend (VideoGeneration.tsx)                                 │
│       │                                                          │
│       ▼                                                          │
│   POST /api/vastai/generate-video                                │
│       │                                                          │
│       ▼                                                          │
│   Backend checks GPU config                                      │
│       │                                                          │
│       ├── If comfyui_url configured → Use tunnel URL             │
│       │                                                          │
│       └── Otherwise → Try to create/use vast.ai instance         │
│           (may fail if direct ports not accessible)              │
│                                                                  │
│   ComfyUI on vast.ai (via Cloudflare tunnel)                    │
│       │                                                          │
│       ▼                                                          │
│   Wan 2.2 I2V generation with LightX2V LoRA                     │
│       │                                                          │
│       ▼                                                          │
│   Video cached to R2 → URL returned to frontend                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Instructions

### Step 1: Create a vast.ai Instance

The system can auto-create instances, but for best results:

1. Go to [vast.ai Console](https://cloud.vast.ai/templates/)
2. Select the **ComfyUI** template
3. Choose a GPU with 24GB+ VRAM (RTX 4090, RTX 5090, A100, etc.)
4. Start the instance

The instance will automatically download Wan 2.2 models from R2:
- `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` (9.6GB)
- `wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf` (15.4GB)
- `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors` (1.2GB)

### Step 2: Get the Tunnel URL

vast.ai templates use Cloudflare tunnels for access. To get your URL:

1. Go to [vast.ai Instances](https://cloud.vast.ai/instances/)
2. Find your running instance
3. Click the **Open** button
4. A new tab will open with your ComfyUI interface
5. Copy the URL from the browser (e.g., `https://abc123-18188.proxy.vast.ai`)

### Step 3: Configure the Backend

Set the tunnel URL via the GPU config API:

```bash
# Using curl
curl -X POST http://localhost:8000/api/gpu/config \
  -H "Content-Type: application/json" \
  -d '{
    "comfyui_url": "https://abc123-18188.proxy.vast.ai",
    "gpu_provider": "vastai"
  }'
```

Or via the Python SDK:

```python
import httpx

resp = httpx.post("http://localhost:8000/api/gpu/config", json={
    "comfyui_url": "https://abc123-18188.proxy.vast.ai",
    "gpu_provider": "vastai"
})
print(resp.json())
```

### Step 4: Use in Frontend

Once configured, select **Wan 2.2 (GPU)** in the model dropdown on the Video Generation page.

The frontend will automatically use the configured GPU instance for generation.

## API Reference

### GET /api/gpu/config

Get current GPU configuration and availability status.

**Response:**
```json
{
  "comfyui_url": "https://abc123-18188.proxy.vast.ai",
  "comfyui_available": true,
  "swarmui_url": "http://localhost:7801",
  "swarmui_available": false,
  "gpu_provider": "vastai",
  "vastai_instance_id": 29829389
}
```

### POST /api/gpu/config

Update GPU configuration.

**Request:**
```json
{
  "comfyui_url": "https://abc123-18188.proxy.vast.ai",
  "gpu_provider": "vastai"
}
```

**Parameters:**
- `comfyui_url` (optional): ComfyUI API URL
- `swarmui_url` (optional): SwarmUI API URL
- `gpu_provider` (optional): "none", "local", or "vastai"
- `vastai_instance_id` (optional): Active vast.ai instance ID

### POST /api/gpu/test-connection

Test connection to a GPU service URL.

**Request:**
```json
{
  "url": "https://abc123-18188.proxy.vast.ai"
}
```

**Response:**
```json
{
  "url": "https://abc123-18188.proxy.vast.ai",
  "reachable": true,
  "api_type": "comfyui",
  "details": { ... }
}
```

### GET /api/gpu/health

Get detailed GPU service health status.

**Response:**
```json
{
  "provider": "vastai",
  "comfyui_status": "available (API ready)",
  "comfyui_url": "https://abc123-18188.proxy.vast.ai",
  "swarmui_status": "unavailable",
  "swarmui_url": "http://localhost:7801",
  "models_available": ["GPU: NVIDIA RTX 5090"]
}
```

## Troubleshooting

### "Instance not ready" Error

The vast.ai instance may still be starting. Wait 2-5 minutes for:
1. Docker container to start
2. ComfyUI to initialize
3. Models to download from R2

### "Failed to authenticate" Error

The tunnel URL may have expired. Get a fresh URL from the vast.ai console.

### Connection Timeouts

1. Check that the instance is still running in vast.ai console
2. Verify the tunnel URL is correct (should include port like `-18188`)
3. Try the `/api/gpu/test-connection` endpoint to diagnose

### Models Not Found

The models should auto-download via the onstart script. Check instance logs:
1. SSH to the instance: `ssh -p PORT root@ssh.vast.ai`
2. Check logs: `cat /var/log/supervisor/*.log`
3. Verify models exist: `ls -la /workspace/ComfyUI/models/unet/`

## Cost Management

- vast.ai charges per hour while the instance is running
- Destroy instances when not in use via the API or console
- Current pricing: ~$0.28-0.50/hour for 24GB+ GPUs

### Auto-destroy (coming soon)

Future versions will support auto-destroying idle instances to minimize costs.

## Development Notes

### Key Files

- `app/routers/gpu_config.py` - Runtime GPU configuration API
- `app/routers/vastai.py` - vast.ai instance management and video generation
- `app/services/comfyui_workflows.py` - Wan 2.2 workflow definitions
- `frontend/src/api/client.ts` - GPU API client functions
- `frontend/src/pages/VideoGeneration.tsx` - GPU generation UI

### Adding New Models

1. Upload model to R2: `scripts/upload_models_to_r2.py`
2. Update workflow in `comfyui_workflows.py`
3. Add model paths to `WAN_MODEL_PATHS` dict
4. Update onstart script in `vastai_client.py`
