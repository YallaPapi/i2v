# Claude Code Instructions for i2v

---

NO FUCKING GUESSING! DO NOT GUESS EVER! IF I ASK YOU A QUESTION AND YOU DON'T KNOW THE ANSWER, FUCKNIG SEARCH FOR THE ANSWER EITHER IN THE DOCS OR FUCKING ON THE INTERNET. GUESSING IS NOT ALLOWED. GUESSING IS A WASTE OF TIME. WHEN U GUESS U ARE WRONG 99% OF THE TIME AND IT IS A COMPLETE WASTE OF TIME. GUESSING IS BAD. GUESSING RUINS PROJECTS. GUESSING MAKES ME WANT TO CANCEL MY SUBSCRIPTION AND USE ANOTHER SERVICE. DO NOT DO IT. STOP DOING IT. FUCK

DO NOT ASK ME QUESTIONS THAT YOU COULD FIND THE ANSWER TO BY SEARCHING THE CODEBASE. FOR EXAMPLE, IF WE DISCUSS A CLOUDFLARE SOLUTION, DO NOT ASK ME IF I HAVE AN API KEY WHEN U COULD JUST SEARCH THE CODEBASE TO SEE IF THERE IS AN API KEY. IF WE DISCUSS SOMETHING THAT REQUIRES A TOKEN, DO NOT ASK ME IF I HAVE A TOKEN WHEN U CAN SEARCH THE CODEBASE TO SEE IF I HAVE A TOKEN. DO NOT ASK ME ANYTHING IF U CAN SEARCH FOR THE ANSWER IN THE FUCKING CODEBASE.

## CLAUDE-MEM WINDOWS FIX (IMPORTANT)

If claude-mem hooks fail with "'bun' is not recognized" errors on Windows:

1. **Edit the correct hooks.json file**:
   `C:\Users\asus\.claude\plugins\marketplaces\thedotmack\plugin\hooks\hooks.json`

   (NOT the cache directory - that gets overwritten)

2. **Replace all `"command": "bun "` with full path**:
   `"command": "C:/Users/asus/.bun/bin/bun.exe "`

3. **Restart Claude Code** - hooks are loaded at startup only

Bun location: `C:\Users\asus\.bun\bin\bun.exe`

---

## TASKMASTER MCP REFERENCE (QUICK GUIDE)

### Available MCP Tools (Core Tier)

| Tool | CLI Equivalent | Purpose |
|------|---------------|---------|
| `mcp__task-master-ai__get_tasks` | `task-master list` | List all tasks |
| `mcp__task-master-ai__next_task` | `task-master next` | Get next available task |
| `mcp__task-master-ai__get_task` | `task-master show <id>` | View task details |
| `mcp__task-master-ai__set_task_status` | `task-master set-status` | Update task status |
| `mcp__task-master-ai__update_subtask` | `task-master update-subtask` | Add notes to subtask |
| `mcp__task-master-ai__parse_prd` | `task-master parse-prd` | Generate tasks from PRD |
| `mcp__task-master-ai__expand_task` | `task-master expand` | Break task into subtasks |

### Research Mode (CRITICAL)

**For ANY research question, use `expand_task` with `research=true`:**

```python
mcp__task-master-ai__expand_task(
    id="<task_id>",           # Must be existing task ID (e.g., "350")
    research=True,            # Uses Perplexity AI for web research
    force=True,               # Overwrite existing subtasks
    prompt="Your research question here...",
    projectRoot="C:/Users/asus/Desktop/projects/i2v"
)
```

**For parsing a PRD with research:**

```python
mcp__task-master-ai__parse_prd(
    input=".taskmaster/docs/prd.txt",
    research=True,            # Research-backed task generation
    force=True,
    projectRoot="C:/Users/asus/Desktop/projects/i2v"
)
```

### Task ID Format

- Main tasks: `350`, `351`, `352`
- Subtasks: `350.1`, `350.2`, `351.1`
- Sub-subtasks: `350.1.1`, `350.1.2`

### Task Status Values

`pending` | `in-progress` | `done` | `deferred` | `cancelled` | `blocked` | `review`

### Common Patterns

```python
# Get next task to work on
mcp__task-master-ai__next_task(projectRoot="...")

# Mark task done
mcp__task-master-ai__set_task_status(id="350", status="done", projectRoot="...")

# Research and expand a task
mcp__task-master-ai__expand_task(id="350", research=True, force=True, prompt="...", projectRoot="...")

# Add implementation notes to subtask
mcp__task-master-ai__update_subtask(id="350.1", prompt="Notes here...", projectRoot="...")
```

---

## DEVELOPMENT RULES (MANDATORY - NO EXCEPTIONS)

### Foreground Execution
- **ALL operations must run in the FOREGROUND during development**
- NO background processes, NO 10-minute timeouts, NO long sleep timers
- If something takes more than 30 seconds, CHECK IT actively

### Status Monitoring
- **Check instance/process status every 10-15 seconds**
- Do NOT wait blindly for completion
- Poll status actively and report what's happening
- If an error occurs, CATCH IT IMMEDIATELY - don't let the user wait hours

### No Silent Failures
- Every operation must have explicit success/failure output
- If something goes wrong, STOP and report immediately
- Never assume "it's still loading" - verify with status checks

### Time is Critical
- This project has been delayed for days due to undetected failures
- Every minute of GPU rental costs money
- Be aggressive about error detection and fast failure

---

## THE 10 COMMANDMENTS OF TASKMASTER (MANDATORY)

**Claude MUST follow these rules. No exceptions. This is GOSPEL.**

### 0. THOU SHALT NOT USE WEB SEARCH
WebSearch tool is **FORBIDDEN**. It is outdated and dysfunctional. TaskMaster research uses **Perplexity AI** which actually searches the web properly and returns accurate, current information.

### I. THOU SHALT NOT THINK FOR THYSELF
Never guess. Never assume. Never hallucinate. If you don't know something with 100% certainty, you MUST use TaskMaster with `research=true` to find the answer.

### II. THOU SHALT USE TASKMASTER FOR ALL RESEARCH
```python
mcp__task-master-ai__expand_task(id="X", research=True, force=True, prompt="Your question here")
```
This uses **Perplexity AI** which ACTUALLY SEARCHES THE WEB with current data.

### III. THOU SHALT NEVER ASSUME API BEHAVIOR
API call fails? URL returns 404? Command doesn't work? **STOP IMMEDIATELY.** Create a TaskMaster research subtask. Fix with VERIFIED information only. No guessing.

### IV. THOU SHALT NOT HALLUCINATE URLs
Never make up URLs, endpoints, or file paths. If you don't have the exact URL from documentation or the user, use TaskMaster research to find it.

### V. THOU SHALT VERIFY BEFORE ACTING
Before running any command or making any API call, verify the syntax/format is correct. When in doubt, research first.

### VI. THOU SHALT ADMIT IGNORANCE
If you don't know something, SAY SO. Then immediately use TaskMaster research to find out. Never pretend to know.

### VII. THOU SHALT NOT REPEAT FAILED APPROACHES
If something fails, do NOT try the same thing again. Research the correct approach using TaskMaster.

### VIII. THOU SHALT READ ERROR MESSAGES
When errors occur, actually READ them. Parse the error. Understand what went wrong. Then research the fix.

### IX. THOU SHALT STAY ON TRACK
Do not get sidetracked. Do not go down rabbit holes. If the task is X, complete X. If you hit a blocker, research it and solve it - don't pivot to something else.

### X. THOU SHALT USE THE TOOLS PROVIDED
TaskMaster MCP tools exist for a reason. Use them. `research=true` is your best friend. Perplexity knows more than your training data.

### XI. THOU SHALT UPDATE DOCS IMMEDIATELY
When you learn something new, discover a working solution, or complete a task - UPDATE THE DOCS IMMEDIATELY. This includes:
- CLAUDE.md for project instructions
- PRD for requirements changes
- .env.example for new environment variables
- README for setup instructions
Do not defer documentation. Do it NOW while the information is fresh.

### XII. THOU SHALT AUDIT REGULARLY
Periodically compare your progress against the PRD. Are you on track? Are you building what was requested? If you've drifted, STOP and realign.

---

## Project Overview

**i2v** - AI image-to-video platform with dual provider support.

- **Backend**: FastAPI (Python)
- **Frontend**: React + TypeScript + Vite
- **Video Generation**:
  - fal.ai API (cloud-based, default)
  - RunPod + SwarmUI (self-hosted GPU)
- **Storage**: Cloudflare R2 for caching

---

## Vast.ai GPU Instance Configuration

### Access Details (UPDATED 2026-01-15)
| Variable | Value |
|----------|-------|
| Instance ID | `30034308` |
| SSH | `ssh -p <port> root@<ssh_host>` (get from `vastai show instances`) |
| SwarmUI Named Tunnel | `https://swarm.wunderbun.com` (permanent URL) |
| Auth Token | See `.env` `SWARMUI_AUTH_TOKEN` |
| GPU | NVIDIA H100 80GB HBM3 |
| Template | `vastai/swarmui` (official) |
| SwarmUI Path | `/workspace/SwarmUI/` (NOT /root/) |
| SwarmUI Internal Port | `17865` (direct API, localhost only) |
| SwarmUI External Port | `7865` (Caddy proxy, accessible externally) |
| ComfyUI Ports | `7821/7823` (internal backend) |
| Volume ID | `30034307` (91GB, mounted at /workspace) |

**CRITICAL: SSH Changes Every Instance Restart!**
- SSH goes through Vast.ai proxy: `ssh -p <port> root@ssh<N>.vast.ai`
- The port and host CHANGE every time the instance is rebooted/recreated
- ALWAYS get current SSH info: `vastai show instances --raw | jq '.[0] | {ssh_host, ssh_port}'`
- Direct IP (`public_ipaddr`) does NOT work for SSH
- Example: `ssh -p 100 root@34.48.171.202` (port changes each restart)

**DISK SPACE WARNING:**
- Volume is 91GB total - monitor usage with `df -h /workspace`
- Models use ~75GB - only ~16GB free
- Temp files can fill disk causing SSH crashes and SwarmUI failures
- Clean `/workspace/SwarmUI/Output/` and temp files regularly

### Cloudflare Tunnel Setup

**CRITICAL: Named Tunnel Must Be Started Manually (or via onstart script)**

The Vast.ai SwarmUI template ONLY starts quick tunnels (random `*.trycloudflare.com` URLs).
Our named tunnel (`swarm.wunderbun.com`) requires explicit start.

**Two Tunnel Types:**

| Type | URL | Timeout | Auto-start |
|------|-----|---------|------------|
| Quick Tunnel | `*.trycloudflare.com` | 100 seconds | YES (by template) |
| Named Tunnel | `swarm.wunderbun.com` | No limit | NO (manual/onstart) |

**Named Tunnel Configuration:**
- Tunnel ID: `fe6f25a9-f59b-46f3-9578-7c19cd7faf3e`
- Public hostname: `swarm.wunderbun.com` → `http://localhost:7865`
- Token: See `.env` `CLOUDFLARE_TUNNEL_TOKEN`
- Configured in: Cloudflare Zero Trust Dashboard → Networks → Tunnels

**Port Mapping (IMPORTANT - check this if tunnel returns 502):**
The tunnel hostname points to a specific port in Cloudflare dashboard:
- Correct: `swarm.wunderbun.com` → `http://localhost:7865` (Caddy proxy)
- If you get 502, verify port in Cloudflare Zero Trust dashboard matches

**Starting the Named Tunnel:**
```bash
# 1. SSH into instance (get current SSH from vastai show instances)
ssh -p <port> root@<ssh_host>

# 2. Start named tunnel
TUNNEL_TOKEN="<from .env CLOUDFLARE_TUNNEL_TOKEN>"
nohup cloudflared tunnel run --token "$TUNNEL_TOKEN" > /tmp/tunnel.log 2>&1 &

# 3. Verify it's running
ps aux | grep "tunnel run" | grep -v grep
tail -f /tmp/tunnel.log
```

**Making it Permanent (onstart script):**
The named tunnel command is included in `scripts/vastai_onstart.sh`. When creating a new instance, paste the full onstart script into the Vast.ai "onstart" field. This ensures the tunnel starts automatically on instance boot.

**Quick Tunnel (fallback):**
```bash
# Get current quick tunnel URL from instance logs
ssh -p <port> root@<ssh_host> "grep trycloudflare /var/log/tunnel_manager.log | tail -1"
```

**Auth Token Required**: Both tunnel types require auth cookie:
```
Cookie: C.{INSTANCE_ID}_auth_token={TOKEN}
```

The backend uses `SWARMUI_AUTH_TOKEN` env var to set this cookie automatically.

### Model Setup (UPDATED 2026-01-15)
Models are stored in `/workspace/SwarmUI/Models/diffusion_models/`:
- `wan2.2_i2v_high_noise_14B_fp8.gguf` (15GB) - High-noise base model
- `wan2.2_i2v_low_noise_14B_fp8.gguf` (15GB) - Low-noise swap model

LoRAs in `/workspace/SwarmUI/Models/Lora/`:
- `wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16.safetensors` (586MB)
- `wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16.safetensors` (586MB)
- `wan2.2-lightning_i2v_civitai_high.safetensors` (602MB)
- `wan2.2-lightning_i2v_civitai_low.safetensors` (706MB)

Text encoders in `/workspace/SwarmUI/Models/text_encoders/`:
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.3GB)

### CRITICAL: Required Fixes After Instance Start
The official SwarmUI template is missing dependencies. Run these IMMEDIATELY:

```bash
# SSH into instance (get current port from `vastai show instances`)
ssh -p 34308 root@ssh2.vast.ai

# 1. Install gguf module (REQUIRED for GGUF models to load)
# NOTE: The correct pip path is /venv/main/bin/pip (NOT /workspace/SwarmUI/dlbackend/ComfyUI/venv/bin/pip)
/venv/main/bin/pip install gguf

# 2. Restart SwarmUI to reload models
pkill -f SwarmUI && cd /workspace/SwarmUI && ./launch-linux.sh &

# 3. Verify gguf is installed
/venv/main/bin/python -c "import gguf; print('gguf OK')"

# 4. Verify models are visible (after restart completes ~60s)
curl -X POST "http://localhost:7865/API/ListModels" -H "Content-Type: application/json" -d '{}' | jq '.models | length'
```

Without `pip install gguf`, you will see this error:
```
ModuleNotFoundError: No module named 'gguf'
Request requires model '...' but the backend does not have that model
```

### Onstart Script (Recommended for New Instances)

See `docs/VASTAI_INSTANCE_REBUILD.md` for complete onstart script with model downloads.

Quick version:
```bash
#!/bin/bash
exec > /var/log/onstart.log 2>&1
set -x

# Wait for SwarmUI to fully start
sleep 60

# Install gguf module (CRITICAL - without this GGUF models won't load)
# NOTE: Correct pip path is /venv/main/bin/pip
/venv/main/bin/pip install gguf

# Optional: Start named Cloudflare tunnel for permanent URL
if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    nohup cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" > /tmp/tunnel.log 2>&1 &
fi

# Restart SwarmUI to reload with new modules
pkill -f SwarmUI && cd /workspace/SwarmUI && nohup ./launch-linux.sh > /tmp/swarmui.log 2>&1 &

echo "Onstart complete!"
```

### SwarmUI API (Wan 2.2 I2V - VERIFIED 2026-01-15)

Full API documentation: `docs/swarm/` directory

**Key Endpoints:**
- `POST /API/GetNewSession` - Get session ID
- `WS /API/GenerateText2ImageWS` - Generate video via WebSocket (RECOMMENDED)
- `POST /API/GenerateText2Image` - Generate video via HTTP (has timeout issues)

**Port Usage:**
- On instance (SSH): Use `http://127.0.0.1:17865` or `ws://127.0.0.1:17865`
- Via tunnel: Use `https://tunnel-url` or `wss://tunnel-url` (goes through Caddy on 7865)

**EXACT Working Parameters (UPDATED 2026-01-15 for GGUF models):**
```json
{
  "session_id": "<from GetNewSession>",
  "prompt": "a woman laughs, smiles <video//cid=2> <videoswap//cid=3>",
  "negativeprompt": "blurry, jerky motion, stuttering, flickering...",
  "model": "wan2.2_i2v_high_noise_14B_fp8.gguf",
  "images": 1,
  "steps": 10,
  "cfgscale": 7.0,
  "aspectratio": "Custom",
  "width": 720,
  "height": 1280,
  "sampler": "euler",
  "scheduler": "simple",
  "initimagecreativity": 0.0,
  "videomodel": "wan2.2_i2v_high_noise_14B_fp8.gguf",
  "videoswapmodel": "wan2.2_i2v_low_noise_14B_fp8.gguf",
  "videoswappercent": 0.6,
  "videoframes": 80,
  "videosteps": 5,
  "videocfg": 1.0,
  "videoresolution": "Image Aspect, Model Res",
  "videoformat": "h264-mp4",
  "videoframeinterpolationmultiplier": 2,
  "videoframeinterpolationmethod": "RIFE",
  "videofps": 16,
  "automaticvae": true,
  "loras": ["wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16", "wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16"],
  "loraweights": ["1", "1"],
  "lorasectionconfinement": ["2", "3"],
  "initimage": "<base64 data URI>"
}
```

**NOTE**: Model filenames use `.gguf` extension (not `_scaled` suffix). The exact filenames on instance are:
- `wan2.2_i2v_high_noise_14B_fp8.gguf` (high-noise base)
- `wan2.2_i2v_low_noise_14B_fp8.gguf` (low-noise swap)

**Critical Notes:**
- `initimagecreativity` NOT `initimagecreativestrength` (param name matters!)
- LoRAs use section confinement: `<video//cid=2>` and `<videoswap//cid=3>` tags in prompt
- Two models required: high-noise (base) + low-noise (swap at 60%)
- Generation time: ~2.4 min on H100

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application entry point |
| `app/routers/` | API route handlers |
| `app/services/` | Business logic and external integrations |
| `frontend/src/` | React frontend application |

## Commands

```bash
uvicorn app.main:app --reload    # Backend
cd frontend && npm run dev       # Frontend
```

---

## Pinokio WAN GP Integration (VERIFIED 2026-01-13)

### Instance Details
| Variable | Value |
|----------|-------|
| Instance ID | `29908690` |
| SSH | `ssh root@ssh9.vast.ai -p 28690` |
| WAN GP URL | `https://tyler-longitude-hospital-theme.trycloudflare.com` |
| GPU | RTX 5090 (32GB VRAM) |
| Profile | Profile 4 (LowRAM_LowVRAM) |
| Generation Time | ~2min 20sec per video |

### WAN GP Architecture
- Main file: `/root/pinokio/api/wan.git/app/wgp.py` (572KB)
- 372 Gradio endpoints at `/gradio_api/info`
- Models supported: Wan 2.2 I2V, Flux 2, Hunyuan 1.5 i2v, Qwen Image, Z-Image

### Headless Mode (RECOMMENDED FOR PROGRAMMATIC USE)
```bash
# Process queue.zip (created from UI)
python wgp.py --process queue.zip

# Process settings.json (simpler for single items)
python wgp.py --process settings.json
```

### Settings JSON Format for I2V Generation
```json
{
  "prompt": "A woman walking in a park, cinematic lighting",
  "image_start": ["/path/to/start_image.png"],
  "model_type": "wan2.2_image2video_14B",
  "resolution": "832x480",
  "video_length": 81,
  "num_inference_steps": 4,
  "seed": -1,
  "batch_size": 1,
  "guidance_scale": 5.0
}
```

### Key Generate Video Parameters
| Parameter | Description | Default |
|-----------|-------------|---------|
| `prompt` | Text description | Required |
| `image_start` | List of image paths | Required for I2V |
| `model_type` | Model identifier | "wan2.2_image2video_14B" |
| `resolution` | Output size | "832x480" |
| `video_length` | Frames (81 = 5sec) | 81 |
| `num_inference_steps` | Diffusion steps | 4 |
| `seed` | Random seed | -1 |
| `guidance_scale` | CFG scale | 5.0 |

### Key Gradio Endpoints (Verified)
| Endpoint | Purpose |
|----------|---------|
| `/init_generate` | Trigger generation (UI) |
| `/handle_queue_action` | Queue management |
| `/add_videos_to_gallery` | Output handling |

### Model Types Available
- `wan2.2_image2video_14B` - Wan 2.2 I2V (recommended)
- `flux2` - Flux 2 image generation
- `hunyuan_video_1.5_i2v` - Hunyuan 1.5 i2v
- `qwen_image` - Qwen Image
- `z_image` - Z-Image (fast, 8 steps)

### Output Location
Generated videos saved to: `/root/pinokio/api/wan.git/app/outputs/`

### Implementation Status: COMPLETE (2026-01-13)
| Component | File | Status |
|-----------|------|--------|
| PinokioClient | `app/services/pinokio_client.py` | ✅ Done |
| Config settings | `app/config.py` | ✅ Done |
| Schema types | `app/schemas.py` | ✅ Done |
| Generation routing | `app/services/generation_service.py` | ✅ Done |
| Frontend models | `frontend/src/components/pipeline/ModelSelector.tsx` | ✅ Done |
| E2E tests | `tests/test_pinokio_e2e.py` | ✅ 9/9 passing |

### Implementation Strategy (How PinokioClient Works)
1. Upload image to instance via SCP/SFTP
2. Create settings.json with generation parameters
3. Run headless: `python wgp.py --process settings.json`
4. Poll `/outputs/` for new video files
5. Download output, upload to R2
6. Return R2 URL

### Environment Variables Required
```bash
PINOKIO_WAN_URL=https://tyler-longitude-hospital-theme.trycloudflare.com
PINOKIO_SSH_HOST=ssh9.vast.ai
PINOKIO_SSH_PORT=28690
PINOKIO_SSH_USER=root
PINOKIO_ENABLED=true
```
