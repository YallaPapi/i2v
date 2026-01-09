#!/bin/bash
#
# ComfyUI Startup Script
# Downloads additional models if URLs are provided via environment variables,
# then starts ComfyUI.
#
set -e

MODEL_DIR="${MODEL_DIR:-/opt/ComfyUI/models}"
CHECKPOINTS_DIR="$MODEL_DIR/checkpoints"
LORA_DIR="$MODEL_DIR/loras"

echo "[startup] ComfyUI GPU Instance Starting..."
echo "[startup] Model directory: $MODEL_DIR"

# Download Pony Realism if URL provided (CivitAI requires direct link)
if [ -n "${PONY_REALISM_URL:-}" ]; then
    DEST="$CHECKPOINTS_DIR/ponyRealism_v21.safetensors"
    if [ ! -f "$DEST" ]; then
        echo "[startup] Downloading Pony Realism..."
        wget --progress=dot:giga -O "$DEST" "$PONY_REALISM_URL" || {
            echo "[startup] WARNING: Failed to download Pony Realism"
            rm -f "$DEST"
        }
    else
        echo "[startup] Pony Realism already exists"
    fi
fi

# Download any additional LoRAs specified (comma-separated URLs)
if [ -n "${LORA_URLS:-}" ]; then
    echo "[startup] Downloading additional LoRAs..."
    IFS=',' read -ra URLS <<< "$LORA_URLS"
    for url in "${URLS[@]}"; do
        url=$(echo "$url" | xargs)  # trim whitespace
        if [ -n "$url" ]; then
            /opt/scripts/download_lora.sh "$url" || true
        fi
    done
fi

# List available models
echo ""
echo "[startup] Available checkpoints:"
ls -lh "$CHECKPOINTS_DIR"/*.safetensors 2>/dev/null || echo "  (none)"
echo ""
echo "[startup] Available LoRAs:"
ls -lh "$LORA_DIR"/*.safetensors 2>/dev/null || echo "  (none)"
echo ""

# Start ComfyUI
echo "[startup] Starting ComfyUI on port 8188..."
cd /opt/ComfyUI
exec python main.py --listen 0.0.0.0 --port 8188 "$@"
