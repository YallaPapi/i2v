#!/usr/bin/env bash
#
# Download a LoRA from CivitAI to the ComfyUI loras directory
#
# Usage:
#   LORA_URL="https://civitai.com/api/download/models/123456" bash download_lora.sh
#   # or
#   bash download_lora.sh "https://civitai.com/api/download/models/123456" "my_lora.safetensors"
#
# The URL should be the DIRECT download link from CivitAI (click download, copy link)
#
set -euo pipefail

LORA_DIR="${LORA_DIR:-/opt/ComfyUI/models/loras}"

# Get URL from argument or environment
LORA_URL="${1:-${LORA_URL:-}}"
LORA_NAME="${2:-}"

if [ -z "$LORA_URL" ]; then
    echo "Usage: LORA_URL=<url> bash download_lora.sh"
    echo "   or: bash download_lora.sh <url> [filename.safetensors]"
    exit 1
fi

mkdir -p "$LORA_DIR"

# Extract filename from URL if not provided
if [ -z "$LORA_NAME" ]; then
    # Try to get filename from Content-Disposition header
    LORA_NAME=$(wget --spider --server-response "$LORA_URL" 2>&1 | grep -i "Content-Disposition" | sed -n 's/.*filename="\?\([^"]*\)"\?.*/\1/p' | head -1 || true)

    # Fall back to URL basename
    if [ -z "$LORA_NAME" ]; then
        LORA_NAME=$(basename "${LORA_URL%%\?*}")
    fi

    # Ensure .safetensors extension
    if [[ ! "$LORA_NAME" =~ \.safetensors$ ]] && [[ ! "$LORA_NAME" =~ \.ckpt$ ]]; then
        LORA_NAME="${LORA_NAME}.safetensors"
    fi
fi

DEST_PATH="$LORA_DIR/$LORA_NAME"

if [ -f "$DEST_PATH" ]; then
    echo "[download_lora] Already exists: $DEST_PATH"
    exit 0
fi

echo "[download_lora] Downloading: $LORA_NAME"
echo "[download_lora] From: $LORA_URL"
echo "[download_lora] To: $DEST_PATH"

wget --progress=dot:giga --retry-connrefused --tries=3 -O "$DEST_PATH" "$LORA_URL" || {
    echo "[download_lora] FAILED"
    rm -f "$DEST_PATH"
    exit 1
}

echo "[download_lora] Success: $LORA_NAME ($(du -h "$DEST_PATH" | cut -f1))"
