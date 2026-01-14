# Claude Code Instructions for i2v

---

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

### Access Details
| Variable | Value |
|----------|-------|
| Instance ID | `29996148` |
| SSH | `ssh -p 25797 root@115.124.123.238` |
| SwarmUI URL | `https://light-curious-idol-msg.trycloudflare.com` |
| Auth Token | See .env `SWARMUI_AUTH_TOKEN` |
| GPU | H100 SXM (80GB VRAM) |
| Template | `vastai/swarmui:v0.9.7-Beta` |

### Cloudflare Tunnel Access
The Vast.ai SwarmUI template auto-creates a quick tunnel on startup. Get the URL and token:
```bash
ssh -p 25797 root@115.124.123.238 "grep trycloudflare /var/log/tunnel_manager.log | tail -1"
```

**Auth Token Required**: The tunnel URL requires a token cookie. Visit `URL?token=XXX` first, or set the cookie:
```
Cookie: C.{INSTANCE_ID}_auth_token={TOKEN}
```

The backend uses `SWARMUI_AUTH_TOKEN` env var to set this cookie automatically.

### Model Setup
Models are stored in `/root/SwarmUI/Models/diffusion_models/`:
- `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` (9GB) - Default I2V model
- `wan22-model-2367702.gguf` (14GB) - Civitai model
- `wan22-model-2367780.gguf` (14GB) - Civitai model
- `wan22-nsfw-v2-q8-high.gguf` (15GB) - Enhanced NSFW model

Text encoders in `/root/SwarmUI/Models/text_encoders/`:
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.3GB)

### Required Fixes (Apply on Instance Start)
These MUST be applied after instance creation/restart:

1. **libcuda.so symlink** (required for SageAttention):
```bash
ln -sf /usr/lib/x86_64-linux-gnu/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so
```

2. **SageAttention** (faster attention for RTX 50 series):
```bash
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install sageattention
```

3. **SwarmUI Backend Config** (`/root/SwarmUI/Data/Backends.fds`):
Set `ExtraArgs: --use-sage-attention` in the ComfyUI backend settings.

4. **Cloudflare Tunnel** (for external access):
```bash
nohup cloudflared tunnel --url http://localhost:7801 > /tmp/cloudflared.log 2>&1 &
```

### Onstart Script Template
Add this to the Vast.ai instance onstart to automate setup:
```bash
#!/bin/bash
exec > /var/log/onstart.log 2>&1
set -x

apt-get update -qq
apt-get install -y -qq git wget curl python3 python3-pip

# Install .NET for SwarmUI
wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet
ln -sf /usr/share/dotnet/dotnet /usr/bin/dotnet

# Install Cloudflare tunnel
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Fix libcuda symlink for SageAttention
ln -sf /usr/lib/x86_64-linux-gnu/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so

# Clone SwarmUI if not exists
if [ ! -d "/root/SwarmUI" ]; then
    cd /root && git clone https://github.com/mcmonkeyprojects/SwarmUI.git
fi

# Install SageAttention
cd /root/SwarmUI
./launch-linux.sh --help > /dev/null 2>&1  # This installs venv
/root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install sageattention

# Configure backend for SageAttention
sed -i 's/ExtraArgs: .*/ExtraArgs: --use-sage-attention/' /root/SwarmUI/Data/Backends.fds 2>/dev/null

# Start SwarmUI
nohup ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none > /var/log/swarmui.log 2>&1 &
sleep 10

# Start Cloudflare tunnel
nohup cloudflared tunnel --url http://localhost:7801 > /tmp/cloudflared.log 2>&1 &

echo "Setup complete! Check /tmp/cloudflared.log for tunnel URL"
```

### SwarmUI API (Wan 2.2 I2V - VERIFIED 2026-01-14)

Full API documentation: `docs/swarm/` directory

**Key Endpoints:**
- `POST /API/GetNewSession` - Get session ID
- `POST /API/GenerateText2Image` - Generate video (I2V with init image)

**EXACT Working Parameters (from verified generation):**
```json
{
  "session_id": "<from GetNewSession>",
  "prompt": "a woman laughs, smiles <video//cid=2> <videoswap//cid=3>",
  "negativeprompt": "blurry, jerky motion, stuttering, flickering...",
  "model": "wan2.2_i2v_high_noise_14B_fp8_scaled",
  "images": 1,
  "steps": 10,
  "cfgscale": 7.0,
  "aspectratio": "Custom",
  "width": 720,
  "height": 1280,
  "sampler": "euler",
  "scheduler": "simple",
  "initimagecreativity": 0.0,
  "videomodel": "wan2.2_i2v_high_noise_14B_fp8_scaled",
  "videoswapmodel": "wan2.2_i2v_low_noise_14B_fp8_scaled",
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
