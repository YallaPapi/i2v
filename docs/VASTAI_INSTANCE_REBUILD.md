# Vast.ai SwarmUI Instance Rebuild Guide

**Last Updated**: 2026-01-15
**Verified Working Instance**: 30034308

This document provides complete instructions for rebuilding a working SwarmUI instance for Wan 2.2 I2V video generation.

---

## Quick Start Checklist

- [ ] Create instance from `vastai/swarmui:v0.9.7-Beta` template
- [ ] Wait for SwarmUI to start (check port 7865)
- [ ] Install gguf module: `/venv/main/bin/pip install gguf`
- [ ] Download models to `/workspace/SwarmUI/Models/diffusion_models/`
- [ ] Download LoRAs to `/workspace/SwarmUI/Models/Lora/`
- [ ] Restart SwarmUI to load models
- [ ] Start Cloudflare tunnel for external access
- [ ] Update .env with tunnel URL and auth token

---

## Part 1: Instance Creation

### Template
Use: `vastai/swarmui:v0.9.7-Beta`

### Recommended GPU
- **H100 SXM (80GB)** - Fastest, ~2.4 min per video
- **RTX 5090 (32GB)** - Good alternative, ~3 min per video

### Ports Required
| Port | Service |
|------|---------|
| 7865 | SwarmUI (via Caddy proxy) |
| 17865 | SwarmUI internal |

---

## Part 2: Model Downloads

### GGUF Models (Required)

The instance needs **two models** - high-noise and low-noise experts.

**Files on working instance:**
```
/workspace/SwarmUI/Models/diffusion_models/
├── wan2.2_i2v_high_noise_14B_fp8.gguf    (15GB)
└── wan2.2_i2v_low_noise_14B_fp8.gguf     (15GB)
```

**Download Sources:**

| Source | File | Size | Notes |
|--------|------|------|-------|
| [Civitai Q8_0](https://civitai.com/models/1820829) | `Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf` | 14.35GB | Rename after download |
| [Civitai Q8_0](https://civitai.com/models/1820829) | `Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf` | 14.35GB | Rename after download |
| [bullerwins HF](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF) | Q8_0 variants | 15.4GB | Alternative source |
| [QuantStack HF](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF) | Various quants | Variable | Many options |

**Download Commands:**
```bash
cd /workspace/SwarmUI/Models/diffusion_models/

# Option A: From HuggingFace (bullerwins)
wget -O wan2.2_i2v_high_noise_14B_fp8.gguf \
  "https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF/resolve/main/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf"
wget -O wan2.2_i2v_low_noise_14B_fp8.gguf \
  "https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF/resolve/main/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf"

# Option B: From Civitai (requires login token)
# Get token from: https://civitai.com/user/account -> API Keys
wget --header="Authorization: Bearer YOUR_CIVITAI_TOKEN" \
  -O wan2.2_i2v_high_noise_14B_fp8.gguf \
  "https://civitai.com/api/download/models/2060527"
wget --header="Authorization: Bearer YOUR_CIVITAI_TOKEN" \
  -O wan2.2_i2v_low_noise_14B_fp8.gguf \
  "https://civitai.com/api/download/models/2060943"
```

### Lightning LoRAs (Required for 4-step generation)

Two LoRA sets are available - Kijai (default, well-tested) and Civitai (alternative style).

**Files on working instance:**
```
/workspace/SwarmUI/Models/Lora/
├── wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors    (614MB)  # Kijai
├── wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors     (614MB)  # Kijai
├── wan2.2-lightning_i2v_civitai_high.safetensors                  (630MB)  # Civitai
└── wan2.2-lightning_i2v_civitai_low.safetensors                   (739MB)  # Civitai
```

#### Option A: Kijai LoRAs (Recommended)
**Source:** [Kijai WanVideo LoRAs (old directory)](https://huggingface.co/Kijai/WanVideo_comfy/tree/main/LoRAs/Wan22-Lightning/old)

```bash
cd /workspace/SwarmUI/Models/Lora/

wget -O wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors"

wget -O wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors"
```

#### Option B: Civitai LoRAs (Alternative)
**Source:** [Civitai Lightning LoRA](https://civitai.com/models/1585622/lightning-lora-massive-speed-up-for-wan21-wan22-made-by-lightx2v-kijai)

```bash
cd /workspace/SwarmUI/Models/Lora/

# Civitai requires auth token - get from: https://civitai.com/user/account -> API Keys
wget --header="Authorization: Bearer YOUR_CIVITAI_TOKEN" \
  -O wan2.2-lightning_i2v_civitai_high.safetensors \
  "https://civitai.com/api/download/models/2056371"

wget --header="Authorization: Bearer YOUR_CIVITAI_TOKEN" \
  -O wan2.2-lightning_i2v_civitai_low.safetensors \
  "https://civitai.com/api/download/models/2058653"
```

**Frontend Selection:**
Users can switch between LoRA sets in the frontend dropdown:
- `kijai` - Kijai Lightning (default, recommended)
- `civitai` - Civitai Lightning (alternative style)
- `none` - No LoRA (slower, 20+ steps required)

---

## Part 3: Python Environment Fix

### The Problem
GGUF models require the `gguf` Python module. The Vast.ai template doesn't install it.

### Finding the Correct pip
```bash
# Find the venv used by ComfyUI
ls -la /venv/main/bin/pip*
```

### Install gguf Module
```bash
/venv/main/bin/pip install gguf
```

### Verify Installation
```bash
/venv/main/bin/python -c "import gguf; print('gguf installed successfully')"
```

---

## Part 4: SwarmUI Restart

After installing models and the gguf module, restart SwarmUI:

```bash
# Find and kill existing process
pkill -f "SwarmUI"

# Navigate to SwarmUI directory
cd /workspace/SwarmUI

# Start SwarmUI
./launch-linux.sh &

# Wait for startup (usually 30-60 seconds)
sleep 60

# Verify models are loaded
curl -s http://localhost:7865/API/ListModels | jq '.models | length'
```

---

## Part 5: Cloudflare Tunnel Setup

### Option A: Permanent Named Tunnel (Recommended)

Requires Cloudflare account and pre-configured tunnel.

```bash
# Get tunnel token from Cloudflare Zero Trust dashboard
export CLOUDFLARE_TUNNEL_TOKEN="eyJhI..."

# Start tunnel
nohup cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" > /tmp/tunnel.log 2>&1 &

# Verify
curl https://your-tunnel-domain.com/API/GetNewSession -H "Cookie: auth_token=YOUR_TOKEN"
```

### Option B: Quick Tunnel (Auto-created)

The Vast.ai template auto-creates a quick tunnel. Find it:

```bash
grep trycloudflare /var/log/tunnel_manager.log | tail -1
```

**Note:** Quick tunnels have a 100-second HTTP timeout. Use WebSocket API for long operations.

---

## Part 6: Complete Onstart Script

Add this to your Vast.ai instance's onstart field:

```bash
#!/bin/bash
exec > /var/log/onstart.log 2>&1
set -x
echo "Onstart script started at $(date)"

# Configuration
CLOUDFLARE_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"  # Set in Vast.ai env vars

# Wait for SwarmUI to be ready (template auto-starts it)
echo "Waiting for SwarmUI..."
for i in {1..60}; do
  if curl -s http://localhost:7865/API/GetNewSession > /dev/null 2>&1; then
    echo "SwarmUI is ready!"
    break
  fi
  sleep 5
done

# Install gguf module (required for GGUF models)
echo "Installing gguf module..."
/venv/main/bin/pip install gguf --quiet

# Download models if not present
MODELS_DIR="/workspace/SwarmUI/Models/diffusion_models"
if [ ! -f "$MODELS_DIR/wan2.2_i2v_high_noise_14B_fp8.gguf" ]; then
  echo "Downloading high-noise model..."
  wget -q -O "$MODELS_DIR/wan2.2_i2v_high_noise_14B_fp8.gguf" \
    "https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF/resolve/main/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf"
fi

if [ ! -f "$MODELS_DIR/wan2.2_i2v_low_noise_14B_fp8.gguf" ]; then
  echo "Downloading low-noise model..."
  wget -q -O "$MODELS_DIR/wan2.2_i2v_low_noise_14B_fp8.gguf" \
    "https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF/resolve/main/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf"
fi

# Download Kijai LoRAs if not present
LORA_DIR="/workspace/SwarmUI/Models/Lora"
if [ ! -f "$LORA_DIR/wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors" ]; then
  echo "Downloading Kijai high LoRA..."
  wget -q -O "$LORA_DIR/wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors" \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors"
fi

if [ ! -f "$LORA_DIR/wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors" ]; then
  echo "Downloading Kijai low LoRA..."
  wget -q -O "$LORA_DIR/wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors" \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors"
fi

# Download Civitai LoRAs if not present (optional - requires CIVITAI_TOKEN env var)
if [ -n "$CIVITAI_TOKEN" ]; then
  if [ ! -f "$LORA_DIR/wan2.2-lightning_i2v_civitai_high.safetensors" ]; then
    echo "Downloading Civitai high LoRA..."
    wget -q --header="Authorization: Bearer $CIVITAI_TOKEN" \
      -O "$LORA_DIR/wan2.2-lightning_i2v_civitai_high.safetensors" \
      "https://civitai.com/api/download/models/2056371"
  fi

  if [ ! -f "$LORA_DIR/wan2.2-lightning_i2v_civitai_low.safetensors" ]; then
    echo "Downloading Civitai low LoRA..."
    wget -q --header="Authorization: Bearer $CIVITAI_TOKEN" \
      -O "$LORA_DIR/wan2.2-lightning_i2v_civitai_low.safetensors" \
      "https://civitai.com/api/download/models/2058653"
  fi
fi

# Restart SwarmUI to load new models
echo "Restarting SwarmUI to load models..."
pkill -f "SwarmUI" || true
sleep 5
cd /workspace/SwarmUI && nohup ./launch-linux.sh > /tmp/swarmui.log 2>&1 &
sleep 60

# Start Cloudflare tunnel if token provided
if [ -n "$CLOUDFLARE_TOKEN" ]; then
  echo "Starting Cloudflare named tunnel..."
  nohup cloudflared tunnel run --token "$CLOUDFLARE_TOKEN" > /tmp/tunnel.log 2>&1 &
fi

# Verify models loaded
echo "Verifying models..."
MODEL_COUNT=$(curl -s http://localhost:7865/API/ListModels 2>/dev/null | jq '.models | length' 2>/dev/null || echo "0")
echo "Loaded $MODEL_COUNT models"

echo "Onstart script completed at $(date)"
```

---

## Part 7: Environment Variables (.env)

Update your local `.env` file:

```bash
# Vast.ai Instance
VAST_API_KEY=your_vast_api_key
VASTAI_INSTANCE_ID=30034308

# SwarmUI Connection
# Use the tunnel URL (goes through Caddy on port 7865)
# Find tunnel URL: ssh -p PORT root@IP "grep 7865 /var/log/tunnel_manager.log | grep trycloudflare | tail -1"
SWARMUI_URL=https://your-tunnel-url.trycloudflare.com
SWARMUI_AUTH_TOKEN=your_auth_token_from_portal

# Port reference:
# - 17865: SwarmUI internal (direct access on instance)
# - 7865: Caddy proxy (what tunnel connects to)
# - Backend code uses SWARMUI_URL which should be the tunnel URL

# Cloudflare Tunnel (for onstart script)
CLOUDFLARE_TUNNEL_TOKEN=eyJhI...

# Model names (should match files on instance)
# These are now correct in app/config.py
```

---

## Part 8: Verification Steps

### 1. Check SwarmUI is Running
```bash
ssh -p PORT root@IP "curl -s http://localhost:7865/API/GetNewSession | jq ."
```

### 2. Check Models are Loaded
```bash
ssh -p PORT root@IP "curl -s http://localhost:7865/API/ListModels | jq '.models[] | select(.name | contains(\"wan2.2\"))'"
```

Expected output should include:
- `wan2.2_i2v_high_noise_14B_fp8.gguf`
- `wan2.2_i2v_low_noise_14B_fp8.gguf`

### 3. Check LoRAs are Loaded
```bash
ssh -p PORT root@IP "curl -s http://localhost:7865/API/ListT2IParams | jq '.params.loras'"
```

### 4. Test Generation
```bash
# From your local machine with backend running
python -c "
import asyncio
from app.services.swarmui_client import SwarmUIClient

async def test():
    client = SwarmUIClient('https://your-tunnel.com', auth_token='...')
    print(await client.health_check())
    session = await client.get_session()
    print(f'Session: {session[:20]}...')

asyncio.run(test())
"
```

---

## Troubleshooting

### "No backends match the settings"
- GGUF module not installed: `/venv/main/bin/pip install gguf`
- Models not loaded: Restart SwarmUI after downloading
- Model names don't match: Check exact filenames in `/workspace/SwarmUI/Models/diffusion_models/`

### "ModuleNotFoundError: No module named 'gguf'"
```bash
/venv/main/bin/pip install gguf
pkill -f SwarmUI
cd /workspace/SwarmUI && ./launch-linux.sh &
```

### Tunnel Timeout (HTTP 524)
Use WebSocket API instead of HTTP for long-running generation. The code already uses `/API/GenerateText2ImageWS`.

### Models Not Visible
1. Check files exist: `ls -la /workspace/SwarmUI/Models/diffusion_models/`
2. Check file permissions: `chmod 644 /workspace/SwarmUI/Models/diffusion_models/*`
3. Check gguf is installed: `/venv/main/bin/python -c "import gguf"`
4. Restart SwarmUI

---

## Model/LoRA Reference

### Code Expects (app/config.py)
```python
swarmui_model = "wan2.2_i2v_high_noise_14B_fp8.gguf"
swarmui_swap_model = "wan2.2_i2v_low_noise_14B_fp8.gguf"
swarmui_lora_high = "wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16"
swarmui_lora_low = "wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16"
```

### File Locations on Instance
```
/workspace/SwarmUI/Models/
├── diffusion_models/
│   ├── wan2.2_i2v_high_noise_14B_fp8.gguf
│   └── wan2.2_i2v_low_noise_14B_fp8.gguf
├── Lora/
│   ├── wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors   # Kijai (default)
│   ├── wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors    # Kijai (default)
│   ├── wan2.2-lightning_i2v_civitai_high.safetensors                 # Civitai (optional)
│   └── wan2.2-lightning_i2v_civitai_low.safetensors                  # Civitai (optional)
└── text_encoders/
    └── umt5_xxl_fp8_e4m3fn_scaled.safetensors
```

---

## Sources

- [Civitai Wan2.2 I2V GGUF](https://civitai.com/models/1820829/wan22-i2v-a14b-gguf)
- [Civitai Lightning LoRAs](https://civitai.com/models/1585622/lightning-lora-massive-speed-up-for-wan21-wan22-made-by-lightx2v-kijai)
- [HuggingFace Kijai LoRAs](https://huggingface.co/Kijai/WanVideo_comfy/tree/main/LoRAs/Wan22-Lightning/old)
- [HuggingFace bullerwins GGUF](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF)
- [HuggingFace QuantStack GGUF](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF)
