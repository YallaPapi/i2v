# GPU Models Setup PRD

## Overview
Configure the vast.ai GPU instances with the best NSFW-capable image and video generation models. Models should be pre-downloaded or downloaded on instance startup for ComfyUI to use.

## Goals
1. Identify best models for realistic and anime NSFW content
2. Get Hugging Face download links for all models
3. Create Docker image or startup script that provisions models
4. Fix the image upload flow to ComfyUI

---

## Image Generation Models

### Tier 1: Primary Models (Must Have)

#### Pony Diffusion V6 XL
- **Use case**: Anime/stylized NSFW, best quality for illustrated content
- **HuggingFace**: https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl
- **File**: `ponyDiffusionV6XL_v6StartWithThisOne.safetensors` (~6.5GB)
- **Install path**: `/opt/ComfyUI/models/checkpoints/`

#### Pony Realism V2.1
- **Use case**: Photorealistic NSFW from Pony base
- **CivitAI**: https://civitai.com/models/372465/pony-realism (need direct link)
- **File**: `ponyRealism_v21MainVAE.safetensors` (~6.5GB)
- **Install path**: `/opt/ComfyUI/models/checkpoints/`

#### SDXL Base 1.0
- **Use case**: General purpose, good for SFW and light NSFW
- **HuggingFace**: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
- **File**: `sd_xl_base_1.0.safetensors` (~6.9GB)
- **Install path**: `/opt/ComfyUI/models/checkpoints/`

#### SDXL VAE
- **Use case**: Required VAE for all SDXL-based models (including Pony)
- **HuggingFace**: https://huggingface.co/stabilityai/sdxl-vae
- **File**: `sdxl_vae.safetensors` (~335MB)
- **Install path**: `/opt/ComfyUI/models/vae/`

### Tier 2: Enhanced Models (Nice to Have)

#### RealVisXL V4.0
- **Use case**: Photorealistic humans, good anatomy
- **HuggingFace**: https://huggingface.co/SG161222/RealVisXL_V4.0
- **File**: `RealVisXL_V4.0.safetensors` (~6.5GB)

#### Juggernaut XL V9
- **Use case**: Photorealistic, excellent skin textures
- **CivitAI/HF**: https://huggingface.co/RunDiffusion/Juggernaut-XL-v9
- **File**: `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors` (~6.5GB)

---

## Video Generation Models

### Tier 1: Primary Video Models

#### HunyuanVideo (Recommended)
- **Use case**: High quality video generation, open source
- **HuggingFace**: https://huggingface.co/tencent/HunyuanVideo
- **Requirements**: ~24GB VRAM minimum
- **Files**:
  - `hunyuan_video_720_cfgdistill_fp8_e4m3fn.safetensors` (~13GB)
  - `hunyuan_video_vae_bf16.safetensors` (~800MB)
  - Text encoder files (CLIP + LLaVA)
- **Install path**: `/opt/ComfyUI/models/diffusion_models/` (or custom nodes)

#### Wan 2.1 (i2v focused)
- **Use case**: Image-to-video, motion from still images
- **Note**: This is what we currently use via fal.ai API
- **Self-hosted option**: Requires custom ComfyUI nodes
- **HuggingFace**: https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P
- **Requirements**: 24GB+ VRAM, complex setup

#### CogVideoX
- **Use case**: Alternative video model, good quality
- **HuggingFace**: https://huggingface.co/THUDM/CogVideoX-5b
- **File**: Multiple files (~10GB total)
- **Requirements**: 24GB VRAM

### Tier 2: Lighter Video Options

#### AnimateDiff + SDXL
- **Use case**: Animate existing images, lower VRAM requirement
- **HuggingFace**: https://huggingface.co/guoyww/animatediff
- **Requirements**: 12GB VRAM
- **Simpler integration with existing SDXL workflow

#### SVD (Stable Video Diffusion)
- **Use case**: Image-to-video, stability.ai model
- **HuggingFace**: https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt
- **File**: `svd_xt.safetensors` (~9GB)
- **Requirements**: 16GB VRAM

---

## LoRA Support (User-Provided)

LoRAs will be downloaded separately from CivitAI links provided by user.

**Install path**: `/opt/ComfyUI/models/loras/`

Expected LoRA types:
- Character/face consistency LoRAs
- Style LoRAs (anime styles, photo styles)
- Pose/composition LoRAs
- NSFW-specific LoRAs

---

## Implementation Plan

### Phase 1: Fix Image Upload Flow
1. Add `upload_image_to_comfyui()` function in `vastai_client.py`
2. Download image from URL to memory
3. Upload to ComfyUI's `/upload/image` endpoint
4. Use returned filename in workflow

### Phase 2: Model Download Script
Create `download_models.sh` script that runs on instance startup:

```bash
#!/bin/bash
MODEL_DIR="/opt/ComfyUI/models"

# Checkpoints
wget -nc -P $MODEL_DIR/checkpoints/ "https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors"
wget -nc -P $MODEL_DIR/checkpoints/ "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"

# VAE
wget -nc -P $MODEL_DIR/vae/ "https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors"

# Video models (if VRAM >= 24GB)
# wget -nc -P $MODEL_DIR/diffusion_models/ "hunyuan_video..."
```

### Phase 3: Custom Docker Image (Production)
For faster cold starts, bake models into Docker image:

```dockerfile
FROM ai-dock/comfyui:latest

# Pre-download models during build
RUN wget -P /opt/ComfyUI/models/checkpoints/ ...
RUN wget -P /opt/ComfyUI/models/vae/ ...

# Include custom nodes for video
RUN cd /opt/ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    git clone https://github.com/kijai/ComfyUI-HunyuanVideoWrapper
```

### Phase 4: Video Workflow Integration
1. Add HunyuanVideo workflow to `comfyui_workflows.py`
2. Add video generation executor similar to image executor
3. Connect to existing fal.ai video pipeline as fallback

---

## Storage Requirements

| Model Type | Size | Priority |
|------------|------|----------|
| Pony V6 XL | 6.5GB | Must have |
| Pony Realism | 6.5GB | Must have |
| SDXL Base | 6.9GB | Must have |
| SDXL VAE | 335MB | Must have |
| RealVisXL | 6.5GB | Nice to have |
| HunyuanVideo | ~15GB | For video |
| **Total (minimum)** | **~21GB** | |
| **Total (full)** | **~50GB** | |

Recommend: 50GB disk space on vast.ai instances

---

## GPU Requirements

| Workload | Min VRAM | Recommended GPU |
|----------|----------|-----------------|
| Image (SDXL/Pony) | 12GB | RTX 3090, RTX 4090 |
| Video (HunyuanVideo) | 24GB | RTX 4090, A100 |
| Video (AnimateDiff) | 12GB | RTX 3090 |

---

## Success Criteria

1. Can generate NSFW images with Pony models on rented GPU
2. Cold start time < 5 minutes (with download script)
3. Cold start time < 2 minutes (with custom Docker image)
4. Video generation works with at least one model
5. LoRAs can be loaded dynamically

---

## Notes for User

Please provide CivitAI links for:
1. Pony Realism (if different version preferred)
2. Any specific LoRAs you want included
3. Any other models you've found useful

CivitAI links should be the direct download URL (click download, copy link).
