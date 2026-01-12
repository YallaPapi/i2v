#!/bin/bash
# Vast.ai Onstart Script for SwarmUI + Wan 2.2 I2V
# This script runs on instance startup and sets up everything automatically.
#
# Usage: Include this script in the Vast.ai instance creation payload as "onstart"

set -e
exec > /var/log/onstart.log 2>&1

echo "=== $(date) Starting i2v SwarmUI setup ==="

# Step 1: Install system dependencies
echo "=== $(date) Installing system dependencies ==="
apt-get update -qq
apt-get install -y -qq git wget curl python3 python3-pip python3-venv

# Step 2: Install .NET 8 SDK (required for SwarmUI)
echo "=== $(date) Installing .NET 8 SDK ==="
wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet
ln -sf /usr/share/dotnet/dotnet /usr/bin/dotnet
dotnet --version

# Step 3: Clone SwarmUI
echo "=== $(date) Cloning SwarmUI ==="
cd /root
git clone https://github.com/mcmonkeyprojects/SwarmUI.git
cd /root/SwarmUI

# Step 4: Create model directories
echo "=== $(date) Creating model directories ==="
mkdir -p Models/diffusion_models Models/Lora

# Step 5: Download models from HuggingFace (parallel)
echo "=== $(date) Downloading models ==="
(
    wget -q --show-progress -O Models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf \
        "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
) &
(
    wget -q --show-progress -O Models/Lora/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
        "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
) &

# Step 6: Start SwarmUI (this will create venv and install ComfyUI)
echo "=== $(date) Starting SwarmUI initial setup ==="
# Run SwarmUI briefly to trigger install, then stop
timeout 120 ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none || true

# Step 7: Fix venv pip (needed for ComfyUI packages)
echo "=== $(date) Fixing venv pip ==="
if [ -d "/root/SwarmUI/dlbackend/ComfyUI/venv" ]; then
    /root/SwarmUI/dlbackend/ComfyUI/venv/bin/python -m ensurepip --upgrade
    /root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install torchsde torchaudio 'gguf>=0.13.0' sentencepiece protobuf
fi

# Step 8: Install ComfyUI-GGUF node
echo "=== $(date) Installing ComfyUI-GGUF node ==="
if [ -d "/root/SwarmUI/dlbackend/ComfyUI/custom_nodes" ]; then
    cd /root/SwarmUI/dlbackend/ComfyUI/custom_nodes
    git clone https://github.com/city96/ComfyUI-GGUF.git
fi

# Wait for model downloads to complete
echo "=== $(date) Waiting for model downloads ==="
wait

# Step 9: Install cloudflared
echo "=== $(date) Installing cloudflared ==="
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Step 10: Start SwarmUI properly
echo "=== $(date) Starting SwarmUI ==="
cd /root/SwarmUI
nohup ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none > /var/log/swarmui.log 2>&1 &

# Wait for SwarmUI to be ready
echo "=== $(date) Waiting for SwarmUI to start ==="
sleep 30

# Step 11: Start cloudflared tunnel
echo "=== $(date) Starting cloudflared tunnel ==="
nohup cloudflared tunnel --url http://localhost:7801 > /var/log/cloudflared.log 2>&1 &

# Wait for tunnel to be ready
sleep 10

# Get and log the public URL
echo "=== $(date) Setup complete ==="
PUBLIC_URL=$(strings /var/log/cloudflared.log | grep trycloudflare.com | tail -1)
echo "Public URL: $PUBLIC_URL"
echo "$PUBLIC_URL" > /root/public_url.txt

echo "=== $(date) SwarmUI ready for video generation ==="
echo "Check /var/log/swarmui.log for SwarmUI status"
echo "Check /var/log/cloudflared.log for tunnel status"
