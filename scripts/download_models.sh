#!/usr/bin/env bash
#
# Model Download Script for ComfyUI GPU Instances
# Downloads required checkpoints, VAEs, and video models to the correct directories.
#
# Usage:
#   bash download_models.sh
#
# Environment variables (optional):
#   PONY_REALISM_URL    - Direct download URL for Pony Realism (from CivitAI)
#   ENABLE_TIER2_IMAGE  - Set to 0 to skip Tier 2 image models (default: 1)
#   ENABLE_HUNYUANVIDEO - Set to 0 to skip HunyuanVideo (default: 1 if VRAM >= 24GB)
#   ENABLE_ANIMATEDIFF  - Set to 1 to download AnimateDiff (default: 0)
#   ENABLE_SVD          - Set to 1 to download Stable Video Diffusion (default: 0)
#   HF_TOKEN            - Hugging Face token for gated models (optional)
#
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/opt/ComfyUI/models}"
CHECKPOINTS_DIR="$MODEL_DIR/checkpoints"
VAE_DIR="$MODEL_DIR/vae"
VID_DIR="$MODEL_DIR/diffusion_models"
LORA_DIR="$MODEL_DIR/loras"
ANIMATEDIFF_DIR="$MODEL_DIR/animatediff_models"

# Create directories
mkdir -p "$CHECKPOINTS_DIR" "$VAE_DIR" "$VID_DIR" "$LORA_DIR" "$ANIMATEDIFF_DIR"

# wget options for reliable downloads
WGET_OPTS="--progress=dot:giga --retry-connrefused --tries=3 --continue"

# Add HF token header if provided
if [ -n "${HF_TOKEN:-}" ]; then
    WGET_OPTS="$WGET_OPTS --header='Authorization: Bearer $HF_TOKEN'"
fi

# Helper: download if file doesn't exist
dl_if_missing() {
    local url="$1"
    local dest_dir="$2"
    local fname="${3:-}"

    # Extract filename from URL if not provided
    if [ -z "$fname" ]; then
        fname=$(basename "${url%%\?*}")
    fi

    if [ -f "$dest_dir/$fname" ]; then
        echo "[download_models] Already exists: $dest_dir/$fname"
        return 0
    fi

    echo "[download_models] Downloading $fname to $dest_dir..."
    wget $WGET_OPTS -O "$dest_dir/$fname" "$url" || {
        echo "[download_models] FAILED: $fname"
        rm -f "$dest_dir/$fname"
        return 1
    }
    echo "[download_models] Done: $fname"
}

# Check disk space
echo "[download_models] Checking disk space..."
AVAIL_GB=$(df -BG "$MODEL_DIR" 2>/dev/null | awk 'NR==2 {gsub("G", "", $4); print $4}' || echo "0")
if [ "${AVAIL_GB:-0}" -lt 25 ]; then
    echo "[WARN] Less than 25GB free under $MODEL_DIR. Some models may fail to download."
fi
echo "[download_models] Available disk: ${AVAIL_GB}GB"

# Check GPU VRAM for video model decisions
VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo "0")
echo "[download_models] GPU VRAM: ${VRAM_MB}MB"

#
# ============================================================================
# TIER 1: ESSENTIAL IMAGE MODELS (Must Have)
# ============================================================================
#
echo ""
echo "========================================"
echo "[download_models] TIER 1: Essential Image Models"
echo "========================================"

# Pony Diffusion V6 XL - Best for anime/stylized NSFW
# HuggingFace: https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl
dl_if_missing \
    "https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors" \
    "$CHECKPOINTS_DIR" \
    "ponyDiffusionV6XL_v6.safetensors"

# SDXL Base 1.0 - General purpose foundation model
# HuggingFace: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
dl_if_missing \
    "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors" \
    "$CHECKPOINTS_DIR"

# SDXL VAE - Required for all SDXL-based models
# HuggingFace: https://huggingface.co/stabilityai/sdxl-vae
dl_if_missing \
    "https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors" \
    "$VAE_DIR"

# Pony Realism V2.1 - Photorealistic NSFW from Pony base
# User must provide CivitAI direct download URL via environment variable
if [ -n "${PONY_REALISM_URL:-}" ]; then
    dl_if_missing "$PONY_REALISM_URL" "$CHECKPOINTS_DIR" "ponyRealism_v21.safetensors"
else
    echo "[INFO] PONY_REALISM_URL not set - skipping Pony Realism"
    echo "[INFO] Get it from: https://civitai.com/models/372465/pony-realism"
fi

#
# ============================================================================
# TIER 2: ENHANCED IMAGE MODELS (Optional but recommended)
# ============================================================================
#
if [ "${ENABLE_TIER2_IMAGE:-1}" -eq 1 ]; then
    echo ""
    echo "========================================"
    echo "[download_models] TIER 2: Enhanced Image Models"
    echo "========================================"

    # RealVisXL V4.0 - Excellent photorealistic humans
    # HuggingFace: https://huggingface.co/SG161222/RealVisXL_V4.0
    dl_if_missing \
        "https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors" \
        "$CHECKPOINTS_DIR" || true

    # Juggernaut XL V9 - Great skin textures
    # HuggingFace: https://huggingface.co/RunDiffusion/Juggernaut-XL-v9
    dl_if_missing \
        "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors" \
        "$CHECKPOINTS_DIR" || true
else
    echo "[INFO] Skipping Tier 2 image models (ENABLE_TIER2_IMAGE=0)"
fi

#
# ============================================================================
# VIDEO MODELS (Based on VRAM availability)
# ============================================================================
#
echo ""
echo "========================================"
echo "[download_models] VIDEO MODELS"
echo "========================================"

if [ "${VRAM_MB:-0}" -ge 24000 ]; then
    echo "[download_models] VRAM >= 24GB - enabling primary video models"

    # HunyuanVideo - High quality open source video generation
    # Requires 24GB+ VRAM
    if [ "${ENABLE_HUNYUANVIDEO:-1}" -eq 1 ]; then
        echo "[download_models] Downloading HunyuanVideo..."

        # Main model (fp8 quantized for memory efficiency)
        dl_if_missing \
            "https://huggingface.co/tencent/HunyuanVideo/resolve/main/hunyuan_video_720_cfgdistill_fp8_e4m3fn.safetensors" \
            "$VID_DIR" || true

        # VAE for HunyuanVideo
        dl_if_missing \
            "https://huggingface.co/tencent/HunyuanVideo/resolve/main/hunyuan_video_vae_bf16.safetensors" \
            "$VID_DIR" || true
    fi

    # Also download AnimateDiff as a lighter alternative
    if [ "${ENABLE_ANIMATEDIFF:-1}" -eq 1 ]; then
        dl_if_missing \
            "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt" \
            "$ANIMATEDIFF_DIR" || true
    fi

elif [ "${VRAM_MB:-0}" -ge 16000 ]; then
    echo "[download_models] VRAM 16-24GB - using lighter video models"

    # Stable Video Diffusion XT - 16GB VRAM requirement
    if [ "${ENABLE_SVD:-0}" -eq 1 ]; then
        dl_if_missing \
            "https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt/resolve/main/svd_xt.safetensors" \
            "$VID_DIR" || true
    fi

    # AnimateDiff - Works well with 16GB cards
    if [ "${ENABLE_ANIMATEDIFF:-1}" -eq 1 ]; then
        dl_if_missing \
            "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt" \
            "$ANIMATEDIFF_DIR" || true
    fi

elif [ "${VRAM_MB:-0}" -ge 12000 ]; then
    echo "[download_models] VRAM 12-16GB - using AnimateDiff"

    # AnimateDiff - Works with 12GB VRAM (enabled by default for 12GB+ cards)
    if [ "${ENABLE_ANIMATEDIFF:-1}" -eq 1 ]; then
        dl_if_missing \
            "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt" \
            "$ANIMATEDIFF_DIR" || true
    fi
else
    echo "[WARN] VRAM < 12GB - video models may not work"
fi

#
# ============================================================================
# CURATED LORAS (Popular/Essential)
# ============================================================================
#
echo ""
echo "========================================"
echo "[download_models] CURATED LORAS"
echo "========================================"
echo "[INFO] LoRAs are typically added by users via CivitAI URLs"
echo "[INFO] Directory ready at: $LORA_DIR"

# Example curated LoRAs could be added here:
# dl_if_missing "CIVITAI_DIRECT_URL" "$LORA_DIR" "lora_name.safetensors"

#
# ============================================================================
# SUMMARY
# ============================================================================
#
echo ""
echo "========================================"
echo "[download_models] COMPLETE"
echo "========================================"
echo "Checkpoints:"
ls -lh "$CHECKPOINTS_DIR"/*.safetensors 2>/dev/null || echo "  (none)"
echo ""
echo "VAEs:"
ls -lh "$VAE_DIR"/*.safetensors 2>/dev/null || echo "  (none)"
echo ""
echo "Video Models:"
ls -lh "$VID_DIR"/*.safetensors 2>/dev/null || ls -lh "$VID_DIR"/*.ckpt 2>/dev/null || echo "  (none)"
echo ""
echo "LoRAs:"
ls -lh "$LORA_DIR"/*.safetensors 2>/dev/null || echo "  (none)"
echo ""
echo "[download_models] Script finished at $(date)"
