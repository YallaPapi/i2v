# GPU Video Generation Setup Guide

This guide explains how to set up and use the self-hosted GPU option ("Wan 2.2 GPU") for video generation using vast.ai with SwarmUI.

## Overview

The i2v platform supports two video generation modes:

1. **Cloud (fal.ai)** - Pay-per-generation pricing, no setup required
2. **Self-hosted GPU (vast.ai)** - Pay-per-hour pricing, requires setup

The self-hosted option uses SwarmUI with Wan 2.2 and LightX2V acceleration on rented vast.ai GPUs.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GPU Generation Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Frontend (VideoGeneration.tsx)                                 │
│       │                                                          │
│       ▼                                                          │
│   POST /api/swarmui/generate-video                               │
│       │                                                          │
│       ▼                                                          │
│   Backend checks GPU config                                      │
│       │                                                          │
│       ├── If swarmui_url configured → Use tunnel URL             │
│       │                                                          │
│       └── Otherwise → Try to create/use vast.ai instance         │
│                                                                  │
│   SwarmUI on vast.ai (via Cloudflare tunnel)                    │
│       │                                                          │
│       ▼                                                          │
│   Wan 2.2 I2V generation with LightX2V LoRA (4 steps)           │
│       │                                                          │
│       ▼                                                          │
│   Video cached to R2 → URL returned to frontend                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Instructions

### Step 1: Create a vast.ai Instance

1. Go to [vast.ai Console](https://cloud.vast.ai/templates/)
2. Select the **SwarmUI** template (hash: `7a42a1fc4f8062a63bbcdbbc9cd65b42`)
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
3. Click the **Open** button next to SwarmUI
4. A new tab will open with your SwarmUI interface
5. Copy the URL from the browser (e.g., `https://abc123.trycloudflare.com`)

### Step 3: Configure the Backend

Set the tunnel URL via the GPU config API:

```bash
curl -X POST http://localhost:8000/api/gpu/config \
  -H "Content-Type: application/json" \
  -d '{
    "swarmui_url": "https://abc123.trycloudflare.com",
    "gpu_provider": "vastai"
  }'
```

### Step 4: Use in Frontend

Once configured, select **Wan 2.2 (GPU)** in the model dropdown on the Video Generation page.

## SwarmUI API Reference

SwarmUI exposes a REST API on port 7801:

### Session Management
- `POST /API/GetNewSession` - Get session_id (required for all calls)

### Generation
- `POST /API/GenerateText2Image` - Sync generation
- `WS /API/GenerateText2ImageWS` - Async with progress updates

### Output Retrieval
- `GET /View/{path}` - Retrieve generated outputs

### Key Parameters for I2V

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `session_id` | Required for all calls | From GetNewSession |
| `prompt` | Motion/content description | User input |
| `initimage` | Path to uploaded image | From upload |
| `initimagecreativity` | 0 for pure I2V | 0 |
| `videomodel` | Wan 2.2 I2V model path | Wan/Wan2.2-I2V-14B |
| `videoframes` | Number of frames | 81 |
| `videocfg` | CFG scale for video | 3.5 |
| `videosteps` | Sampling steps | 4 (with LightX2V) |

## Backend API Reference

### GET /api/gpu/config

Get current GPU configuration and availability status.

**Response:**
```json
{
  "swarmui_url": "https://abc123.trycloudflare.com",
  "swarmui_available": true,
  "gpu_provider": "vastai",
  "vastai_instance_id": 29829389
}
```

### POST /api/gpu/config

Update GPU configuration.

**Request:**
```json
{
  "swarmui_url": "https://abc123.trycloudflare.com",
  "gpu_provider": "vastai"
}
```

### POST /api/gpu/test-connection

Test connection to SwarmUI.

**Request:**
```json
{
  "url": "https://abc123.trycloudflare.com"
}
```

### POST /api/swarmui/generate-video

Generate video using SwarmUI.

**Request:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "prompt": "camera slowly zooms in",
  "num_frames": 81,
  "steps": 4,
  "cfg_scale": 3.5,
  "seed": -1
}
```

## Troubleshooting

### "Instance not ready" Error

Wait 3-5 minutes for:
1. Docker container to start
2. SwarmUI to initialize
3. Models to download from R2 (~2-3 min on datacenter internet)

### Connection Timeouts

1. Check instance is running in vast.ai console
2. Get fresh tunnel URL (they can expire)
3. Test with `/api/gpu/test-connection`

### Models Not Found

Check instance terminal:
```bash
ls -la /workspace/SwarmUI/Models/diffusion_models/
ls -la /workspace/SwarmUI/Models/Lora/
```

## Cost Management

- vast.ai charges per hour while instance is running
- Destroy instances when not in use
- Pricing: ~$0.50-1.50/hour for RTX 5090

## Key Files

| File | Purpose |
|------|---------|
| `app/routers/swarmui.py` | SwarmUI API endpoints |
| `app/routers/gpu_config.py` | Runtime GPU configuration |
| `app/services/swarmui_client.py` | SwarmUI API client |
| `app/services/vastai_client.py` | vast.ai instance management |
| `docker/Dockerfile.swarmui` | Custom SwarmUI image with SageAttention |

## Adding New Models

1. Upload model to R2: `scripts/upload_models_to_r2.py`
2. Update `_get_model_download_script()` in `vastai_client.py`
3. Add to SwarmUI model paths
