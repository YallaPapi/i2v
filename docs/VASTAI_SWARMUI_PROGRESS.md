# Vast.ai + SwarmUI Setup Progress

## SETUP COMPLETE

All steps verified working. Video generation tested and confirmed.

## Current Instance
- **Instance ID**: 29898989
- **GPU**: RTX 5090 (32GB VRAM)
- **SSH**: `ssh root@ssh9.vast.ai -p 18988`
- **Price**: ~$0.17/hr
- **Public URL**: https://turning-treatment-oct-component.trycloudflare.com
- **Docker Image**: `nvidia/cuda:12.8.0-runtime-ubuntu22.04`

## What Worked

### Step 1: Instance Creation ✅
```python
# Search for RTX 5090 offers
query = {
    "gpu_name": {"eq": "RTX 5090"},
    "gpu_ram": {"gte": 30 * 1024},
    "disk_space": {"gte": 80},
    "dph_total": {"lte": 1.50},
    "rentable": {"eq": True},
}
# PUT /api/v0/asks/{offer_id}/ with payload
```

### Step 2: SSH Key Setup ✅
- SSH keys are account-level on Vast.ai
- Must be added BEFORE instance creation (injected at boot)
- POST to `/api/v0/ssh/` with public key

### Step 3: Onstart Script Installs ✅
The onstart script successfully installed:
- git, wget, curl, python3, python3-pip
- .NET 8 SDK (required for SwarmUI)
- SwarmUI cloned to /root/SwarmUI

### Step 4: SwarmUI Installation via WebSocket ✅
```
1. GET session: POST /API/GetNewSession
2. Connect WebSocket: /API/InstallConfirmWS?session_id={session}
3. Send: {"theme": "dark", "installed_for": "just_self", "backend": "comfyui", "models": []}
4. Wait for install to complete
```

### Step 5: Fix python3-venv ✅
**ROOT CAUSE**: Ubuntu's python3 package doesn't include venv support.
When SwarmUI creates its venv at `/root/SwarmUI/dlbackend/ComfyUI/venv/`, pip is missing.

**FIX**: Install python3-venv BEFORE running SwarmUI:
```bash
apt-get install -y python3-venv
```

Then install pip in the existing venv:
```bash
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/python -m ensurepip --upgrade
```

### Step 6: Install torchsde ✅
SwarmUI's auto-installer missed torchsde. Install manually:
```bash
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install torchsde torchaudio
```

### Step 7: Start SwarmUI ✅
```bash
cd /root/SwarmUI && nohup ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none > /var/log/swarmui.log 2>&1 &
```

**VERIFIED WORKING:**
- SwarmUI on port 7801
- ComfyUI backend on port 7821
- API returns session ID

### Step 8: Cloudflared Tunnel ✅
```bash
pkill cloudflared 2>/dev/null
nohup cloudflared tunnel --url http://localhost:7801 > /var/log/cloudflared.log 2>&1 &
grep -i 'trycloudflare.com' /var/log/cloudflared.log
```

## Current Status ✅ (ALL WORKING)
- **Instance**: 29898989 (RTX 5090, ~$0.17/hr)
- **SwarmUI**: Running on port 7801
- **ComfyUI**: Running on port 7821
- **Public URL**: https://turning-treatment-oct-component.trycloudflare.com
- **API**: Working
- **Model**: Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf (9.0GB) loaded
- **Video Generation**: TESTED AND WORKING

## Verified API Call
```bash
SESSION=$(curl -s -X POST "$URL/API/GetNewSession" -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -X POST "$URL/API/GenerateText2Image" -H "Content-Type: application/json" -d "{
  \"session_id\":\"$SESSION\",
  \"images\":1,
  \"prompt\":\"a cat walking\",
  \"model\":\"Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf\",
  \"width\":480,\"height\":480,
  \"steps\":4,
  \"videoframes\":17,
  \"videofps\":8
}"
```

## Model Download URLs (HuggingFace - FASTER)

### Main Model
```bash
# Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf (9.6GB)
wget -O /root/SwarmUI/Models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf \
  "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
```

### LoRA (4-step acceleration)
```bash
# wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors (1.2GB)
wget -O /root/SwarmUI/Models/Lora/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
```

### Optional NSFW Model (Civitai only)
```bash
# wan22EnhancedNSFWCameraPrompt (15.4GB) - Must download from Civitai
# https://civitai.com/models/2053259/wan-22-enhanced-nsfw-or-camera-prompt-adherence-lightning-edition-i2v-and-t2v-fp8-gguf
```

## Files
- `create_swarm_instance.py` - Instance creation script
- `test_vastai_instance.py` - Test script
- `Dockerfile.swarmui` - Docker build (not currently used)
