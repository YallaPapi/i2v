# Vast.ai + SwarmUI Setup Progress

## COMPLETE SETUP GUIDE (Start from Scratch)

This document contains everything needed to recreate the Vast.ai + SwarmUI setup from nothing.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (i2v)                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  VastAIClient (app/services/vastai_client.py)                │  │
│  │  - Reads CLOUDFLARE_TUNNEL_TOKEN from .env                   │  │
│  │  - Generates dynamic onstart script with injected token      │  │
│  │  - Creates H100 instance via Vast.ai API                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Vast.ai H100 Instance                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SwarmUI + ComfyUI Backend                                   │  │
│  │  - Port 7801 (internal)                                      │  │
│  │  - Wan 2.2 I2V model (9.6GB GGUF)                           │  │
│  │  - SageAttention for fast inference                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Cloudflared (tunnel connector)                              │  │
│  │  - Reads token injected at instance creation                 │  │
│  │  - Connects to Cloudflare Zero Trust                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 Cloudflare Zero Trust Tunnel                         │
│  - Fixed URL: $SWARMUI_URL (e.g., https://swarm.yourdomain.com)     │
│  - Routes traffic to instance port 7801                              │
│  - Token configured in dashboard, stored in .env                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables Required

All configuration is via environment variables in `.env`. **NO hardcoded values.**

```bash
# Vast.ai API Key (required)
VASTAI_API_KEY=your_vastai_api_key

# Cloudflare Zero Trust Tunnel (for persistent URL)
CLOUDFLARE_TUNNEL_TOKEN=eyJ...  # Token from Cloudflare dashboard
SWARMUI_URL=https://swarm.yourdomain.com  # Fixed URL configured in dashboard

# Optional: Cloudflare API for dynamic tunnel management
CLOUDFLARE_API_KEY=your_cloudflare_api_key
```

---

## Current Instance (as of 2026-01-15)

| Property | Value |
|----------|-------|
| Instance ID | `30034308` |
| GPU | H100 80GB HBM3 |
| SSH | `ssh -p <port> root@<ssh_host>` (CHANGES each restart - run `vastai show instances`) |
| Volume ID | `30034307` (91GB at /workspace) |
| Price | ~$1.50/hr |
| Template | `vastai/swarmui` (official) |
| SwarmUI Path | `/workspace/SwarmUI/` |
| SwarmUI Internal | `http://localhost:17865` |
| SwarmUI External | Port 7865 (via Caddy proxy) |

### Access URLs
- **Persistent Tunnel**: `https://swarm.wunderbun.com` (Named tunnel - must start manually or via onstart)
- **Quick Tunnels**: Random `*.trycloudflare.com` URLs (auto-created by template)

### CRITICAL NOTES
1. **SSH changes every restart** - always get current from `vastai show instances`
2. **Named tunnel must be started** - template only starts quick tunnels
3. **91GB disk fills up fast** - monitor with `df -h /workspace`, clean outputs regularly
4. **Disk full causes SSH crashes** - if SSH stops working, disk may be full

---

## PART 1: Instance Creation via VastAIClient

The `VastAIClient` automatically handles instance creation with proper configuration.

### 1.1 How It Works

```python
# VastAIClient reads settings at script generation time
from app.config import settings

# Token is read from .env and injected into the script
tunnel_token = settings.cloudflare_tunnel_token  # From CLOUDFLARE_TUNNEL_TOKEN

# If token exists: use persistent tunnel
# If no token: fallback to quick tunnel with random URL
```

### 1.2 Search for GPU Offers

```python
from app.services.vastai_client import VastAIClient

client = VastAIClient()

# Search for H100 GPUs
offers = await client.search_offers(
    gpu_name="H100",           # or "H100 SXM", "RTX 5090"
    min_gpu_ram=40,            # GB
    min_disk=100,              # GB
    max_price=2.00             # $/hr
)
```

### 1.3 Create Instance

```python
# Creates instance with full setup (SwarmUI, cloudflared, models, SageAttention)
result = await client.create_swarmui_instance(
    offer_id=29062718,
    disk_space=150
)
# Returns: instance_id, public_ip, etc.
```

---

## PART 2: Onstart Script (Auto-Generated)

The VastAIClient generates a complete onstart script dynamically. The tunnel token is read from `.env` at generation time and injected into the script.

### 2.1 Script Sections

1. **Base Dependencies**: git, wget, curl, python3
2. **.NET 8 SDK**: Required for SwarmUI
3. **Cloudflared Binary**: Tunnel connector
4. **libcuda Symlink**: Required for SageAttention
5. **SwarmUI Clone & Setup**: Creates venv, installs deps
6. **SageAttention Install**: Faster attention for modern GPUs
7. **Model Download**: Wan 2.2 I2V 14B (9.6GB GGUF)
8. **Cloudflare Tunnel Start**: Uses token from .env OR quick tunnel fallback

### 2.2 Tunnel Configuration Logic

```python
# In _get_swarmui_full_onstart_script():
if settings.cloudflare_tunnel_token:
    # Persistent tunnel with fixed URL
    tunnel_cmd = f'cloudflared tunnel run --token "{tunnel_token}"'
else:
    # Quick tunnel with random URL (fallback)
    tunnel_cmd = 'cloudflared tunnel --url http://localhost:7801'
```

---

## PART 3: Cloudflare Zero Trust Setup

### 3.1 Create Persistent Tunnel (One-Time Setup)

1. Go to Cloudflare Zero Trust Dashboard: https://one.dash.cloudflare.com/
2. Navigate to: **Networks > Tunnels > Create a tunnel**
3. Choose "Cloudflared" connector
4. Name your tunnel (e.g., "swarm-vast-tunnel")
5. Copy the token (starts with `eyJ...`)
6. Add to `.env`:
   ```bash
   CLOUDFLARE_TUNNEL_TOKEN=eyJ...your_token_here
   ```

### 3.2 Configure Public Hostname

In Cloudflare Dashboard, add a Public Hostname:
- **Subdomain**: `swarm` (or your choice)
- **Domain**: Select your domain
- **Service Type**: HTTP
- **URL**: `http://localhost:7801`

Then add to `.env`:
```bash
SWARMUI_URL=https://swarm.yourdomain.com
```

### 3.3 Why Persistent vs Quick Tunnel

| Feature | Persistent Tunnel | Quick Tunnel |
|---------|-------------------|--------------|
| URL | Fixed (your domain) | Random (trycloudflare.com) |
| Survives restart | Yes | No (new URL each time) |
| Setup | One-time dashboard config | None |
| Use case | Production | Testing only |

---

## PART 4: SwarmUI Installation Wizard (Programmatic)

Fresh SwarmUI installations require completing the Install wizard. This can be done via **WebSocket API** (not HTTP POST).

### 4.1 WebSocket API Endpoint

```
wss://{SWARMUI_URL}/API/InstallConfirmWS
```

### 4.2 Installation Parameters

```json
{
  "session_id": "<from GetNewSession>",
  "theme": "modern_dark",
  "installed_for": "just_self",
  "backend": "comfyui",
  "models": "",
  "install_amd": false,
  "language": "en",
  "make_shortcut": false
}
```

| Parameter | Description | Values |
|-----------|-------------|--------|
| `theme` | UI theme | `modern_dark`, `dark`, `light` |
| `installed_for` | Network mode | `just_self`, `local_network`, `public` |
| `backend` | Backend to install | `comfyui`, `none` |
| `models` | Models to pre-download | Empty string to skip |
| `install_amd` | AMD GPU mode | `false` for NVIDIA |
| `language` | UI language | `en` |

### 4.3 Python Script to Complete Install

```python
import asyncio
import aiohttp
import json

async def complete_swarmui_install(base_url):
    ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/API/InstallConfirmWS'

    async with aiohttp.ClientSession() as session:
        # Get session ID
        async with session.post(f'{base_url}/API/GetNewSession', json={}) as resp:
            session_id = (await resp.json()).get('session_id')

        # Connect WebSocket and send config
        async with session.ws_connect(ws_url, ssl=True) as ws:
            await ws.send_json({
                'session_id': session_id,
                'theme': 'modern_dark',
                'installed_for': 'just_self',
                'backend': 'comfyui',
                'models': '',
                'install_amd': False,
                'language': 'en',
                'make_shortcut': False
            })

            # Read progress until complete
            while True:
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    response = json.loads(msg.data)
                    print(response)
                    if response.get('success'):
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

# Usage: asyncio.run(complete_swarmui_install('https://swarm.wunderbun.com'))
```

### 4.4 Progress Response Format

```json
{"info": "Installation request received, processing..."}
{"info": "Setting theme to modern_dark."}
{"info": "Configuring settings as 'just yourself' install."}
{"progress": 0, "total": 0, "steps": 2, "total_steps": 6, "per_second": 0}
{"info": "Downloading ComfyUI backend... please wait..."}
{"success": true}  // Final message when complete
```

### 4.5 After Wizard Completion
- SwarmUI API becomes available at `$SWARMUI_URL/API/`
- Session management via `/API/GetNewSession`
- Video generation via `/API/GenerateText2Image`

---

## PART 5: Software Stack Details

### 5.1 Base Dependencies
```bash
apt-get update -qq
apt-get install -y -qq git wget curl python3 python3-pip python3-venv
```

### 5.2 .NET 8 SDK (Required for SwarmUI)
```bash
wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet
ln -sf /usr/share/dotnet/dotnet /usr/bin/dotnet
```

### 5.3 Cloudflared (Tunnel Client)
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

### 5.4 libcuda Symlink (Required for SageAttention)
```bash
ln -sf /usr/lib/x86_64-linux-gnu/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so
```

### 5.5 SageAttention
```bash
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install sageattention
```

---

## PART 6: Model Downloads

### 6.1 Default Model (Auto-Downloaded)
```bash
cd /root/SwarmUI/Models/diffusion_models
wget -O Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf \
  "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
```

### 6.2 Model Directories
```
/root/SwarmUI/Models/diffusion_models/   # Main models (.gguf, .safetensors)
/root/SwarmUI/Models/Lora/                # LoRA files
/root/SwarmUI/Models/text_encoders/       # Text encoders
```

### 6.3 Optional: Civitai Models
```bash
# Requires Civitai API key
VERSION_ID="2367702"
wget -O "wan22-model-${VERSION_ID}.gguf" \
  "https://civitai.com/api/download/models/${VERSION_ID}?token=$CIVITAI_KEY"
```

---

## PART 7: API Usage

### 7.1 Get Session ID
```bash
# Use $SWARMUI_URL from .env
SESSION=$(curl -s -X POST "$SWARMUI_URL/API/GetNewSession" \
  -H "Content-Type: application/json" -d '{}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo $SESSION
```

### 7.2 Generate Video
```bash
curl -X POST "$SWARMUI_URL/API/GenerateText2Image" \
  -H "Content-Type: application/json" -d "{
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

### 7.3 Check Generation Status
```bash
curl -s "$SWARMUI_URL/API/ListImages?session_id=$SESSION"
```

---

## PART 8: Troubleshooting

### 8.1 Check Tunnel Status
```bash
# On the instance (via SSH if needed):
ps aux | grep cloudflared

# Check logs
cat /tmp/cloudflared.log
```

### 8.2 SwarmUI Not Starting
```bash
tail -50 /var/log/swarmui.log
lsof -i :7801
```

### 8.3 ComfyUI Backend Issues
```bash
ps aux | grep ComfyUI
grep -i "comfyui\|error" /var/log/swarmui.log
```

### 8.3.1 Backend Configuration via API

After installation, the ComfyUI backend must be configured:

```bash
# 1. Get session
SESSION=$(curl -s -X POST "$SWARMUI_URL/API/GetNewSession" -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 2. Add ComfyUI backend
curl -s -X POST "$SWARMUI_URL/API/AddNewBackend" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\", \"type_id\": \"comfyui_selfstart\"}"

# 3. Configure backend settings
curl -s -X POST "$SWARMUI_URL/API/EditBackend" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\", \"backend_id\": 0, \"title\": \"ComfyUI-Local\", \"settings\": {\"StartScript\": \"dlbackend/ComfyUI/main.py\", \"ExtraArgs\": \"--use-sage-attention\", \"GPU_ID\": \"0\"}}"

# 4. Verify backend
curl -s -X POST "$SWARMUI_URL/API/ListBackends" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\"}"
```

Backend status values: `waiting`, `loading`, `running`, `errored`

### 8.4 SageAttention Not Working
```bash
ls -la /usr/lib/x86_64-linux-gnu/libcuda.so
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/python3 -c "from sageattention import sageattn; print('OK')"
```

### 8.5 GPU Issues
```bash
nvidia-smi
nvcc --version
```

---

## PART 9: File Reference

| File | Purpose |
|------|---------|
| `/var/log/onstart.log` | Onstart script output |
| `/var/log/swarmui.log` | SwarmUI main log |
| `/tmp/cloudflared.log` | Cloudflared tunnel log |
| `/root/SwarmUI/Data/Settings.fds` | SwarmUI settings |
| `/root/SwarmUI/Data/Backends.fds` | ComfyUI backend config |

---

## PART 10: R2 Upload (Optional)

### 10.1 Configuration
```bash
# In .env
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_BUCKET_NAME=i2v
R2_PUBLIC_DOMAIN=pub-xxx.r2.dev
```

### 10.2 Upload Script
```bash
python3 /root/upload_to_r2.py /path/to/video.mp4
# Output: https://pub-xxx.r2.dev/videos/<hash>.mp4
```

---

## PART 11: Creating a Reusable Template

Once you have a working instance, save it as a template so future instances boot up pre-configured.

### 11.1 Take Snapshot via CLI

```bash
# Save running instance as Docker image
vastai take snapshot <instance_id>

# This pushes to your configured container registry
# Then use that image in future templates
```

### 11.2 Create Instance from Existing

```bash
# Clone an existing instance's disk state
vastai create instance --create-from <existing_instance_id> <offer_id>
```

### 11.3 Recommended Workflow

1. **Set up instance manually** (SwarmUI, models, backend configured)
2. **Verify everything works** via the tunnel URL
3. **Take snapshot**: `vastai take snapshot <instance_id>`
4. **Push to Docker Hub**: `docker push yourusername/swarmui-ready:latest`
5. **Create template** in Vast.ai dashboard using your image
6. **Set minimal onstart**:
   ```bash
   #!/bin/bash
   cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"
   ```

### 11.4 Result

| Without Template | With Template |
|------------------|---------------|
| Install SwarmUI from scratch | Already installed |
| Download 10GB+ models | Already downloaded |
| Configure backend | Already configured |
| 15-20 minutes setup | 30 seconds (just cloudflared) |
| Many failure points | Single command, reliable |

---

## Last Updated: 2026-01-15

### Changes on 2026-01-15:
1. **Fixed disk full issue** - deleted 6GB stuck temp file, freed space
2. **Documented SSH behavior** - port/host changes every restart, must check `vastai show instances`
3. **Documented named tunnel setup** - must be started manually or via onstart script
4. **Clarified port mapping** - tunnel should point to 7865 (Caddy), not 17865 (direct)
5. **Updated CLAUDE.md** with comprehensive tunnel and SSH documentation
6. **Verified swarm.wunderbun.com** - working after starting named tunnel

### Changes on 2026-01-14:
1. Switched from RTX 5090 to H100 SXM (80GB VRAM)
2. Implemented Cloudflare Zero Trust tunnel with token injection from `.env`
3. Created flexible onstart script generator (`_get_swarmui_full_onstart_script()`)
4. Removed all hardcoded tokens - everything via environment variables
5. Fixed broken gpu_config.py imports in vastai_client.py
6. SwarmUI accessible at persistent URL

### Known Issues:
1. **Disk space** - 91GB volume fills up fast, need larger disk or regular cleanup
2. **SSH instability** - Vast.ai proxy sometimes closes connections
3. **Named tunnel not auto-start** - must start manually or include in onstart script

### Next Steps:
1. Expand storage to 300GB+ (clone volume or use `vastai copy`)
2. Test end-to-end video generation via backend
3. Wire generation to frontend
