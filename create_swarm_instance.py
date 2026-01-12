"""
Create Vast.ai instance with SwarmUI + Wan 2.2 I2V model.
Fully automated setup that works from scratch.
"""
import os
import json
import time
import httpx

VASTAI_API_URL = "https://console.vast.ai/api/v0"

# Read API key from .env file directly
env_path = os.path.join(os.path.dirname(__file__), '.env')
api_key = None
with open(env_path) as f:
    for line in f:
        if line.startswith('VASTAI_API_KEY='):
            api_key = line.strip().split('=', 1)[1]
            break

if not api_key:
    print("ERROR: VASTAI_API_KEY not found in .env")
    exit(1)

headers = {'Authorization': f'Bearer {api_key}'}

# Search for RTX 5090 offers
print("Searching for RTX 5090 offers...")
query = {
    "gpu_name": {"eq": "RTX 5090"},
    "gpu_ram": {"gte": 30 * 1024},
    "disk_space": {"gte": 80},
    "dph_total": {"lte": 1.50},
    "rentable": {"eq": True},
}
r = httpx.get(f"{VASTAI_API_URL}/bundles/", headers=headers, params={"q": json.dumps(query)}, timeout=60)
offers = r.json().get("offers", [])
offers.sort(key=lambda x: x.get("dph_total", 999))

if not offers:
    print("No RTX 5090 offers found!")
    exit(1)

print(f"Found {len(offers)} offers, cheapest: ${offers[0]['dph_total']:.2f}/hr")
offer_id = offers[0]["id"]

# Complete onstart script - all steps verified working
onstart_script = '''#!/bin/bash
# Vast.ai Onstart Script for SwarmUI + Wan 2.2 I2V
set -e
exec > /var/log/onstart.log 2>&1

echo "=== $(date) Starting i2v SwarmUI setup ==="

# Step 1: Install system dependencies (including python3-venv!)
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
mkdir -p Models/diffusion_models Models/Lora

# Step 5: Download models from HuggingFace (parallel, in background)
echo "=== $(date) Downloading models ==="
(
    wget -q -O Models/diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf \
        "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
    echo "=== $(date) Main model downloaded ==="
) &
MODEL_PID=$!

(
    wget -q -O Models/Lora/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
        "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
    echo "=== $(date) LoRA downloaded ==="
) &

# Step 6: Start SwarmUI briefly to trigger ComfyUI install
echo "=== $(date) Initial SwarmUI setup (creates venv, installs ComfyUI) ==="
timeout 180 ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none || true

# Step 7: Fix venv pip (CRITICAL - without this, pip installs fail)
echo "=== $(date) Fixing venv pip ==="
if [ -d "/root/SwarmUI/dlbackend/ComfyUI/venv" ]; then
    /root/SwarmUI/dlbackend/ComfyUI/venv/bin/python -m ensurepip --upgrade
    /root/SwarmUI/dlbackend/ComfyUI/venv/bin/pip install torchsde torchaudio 'gguf>=0.13.0' sentencepiece protobuf -q
fi

# Step 8: Install ComfyUI-GGUF node (required for GGUF models)
echo "=== $(date) Installing ComfyUI-GGUF node ==="
if [ -d "/root/SwarmUI/dlbackend/ComfyUI/custom_nodes" ]; then
    cd /root/SwarmUI/dlbackend/ComfyUI/custom_nodes
    git clone https://github.com/city96/ComfyUI-GGUF.git
    cd /root/SwarmUI
fi

# Step 9: Install cloudflared for public access
echo "=== $(date) Installing cloudflared ==="
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Wait for model downloads
echo "=== $(date) Waiting for model downloads to complete ==="
wait $MODEL_PID
wait

# Step 10: Start SwarmUI properly
echo "=== $(date) Starting SwarmUI ==="
cd /root/SwarmUI
nohup ./launch-linux.sh --host 0.0.0.0 --port 7801 --launch_mode none > /var/log/swarmui.log 2>&1 &

# Wait for SwarmUI to be ready
sleep 30

# Step 11: Start cloudflared tunnel
echo "=== $(date) Starting cloudflared tunnel ==="
nohup cloudflared tunnel --url http://localhost:7801 > /var/log/cloudflared.log 2>&1 &
sleep 10

# Get the public URL
PUBLIC_URL=$(strings /var/log/cloudflared.log 2>/dev/null | grep trycloudflare.com | tail -1 || echo "Check /var/log/cloudflared.log")
echo "=== $(date) Setup complete ==="
echo "Public URL: $PUBLIC_URL"
echo "$PUBLIC_URL" > /root/public_url.txt

# Verify SwarmUI is responding
if curl -s -X POST http://localhost:7801/API/GetNewSession -H "Content-Type: application/json" -d '{}' | grep -q session_id; then
    echo "=== SwarmUI API verified working ==="
else
    echo "=== WARNING: SwarmUI API not responding yet, may need more time ==="
fi
'''

payload = {
    "client_id": "i2v-swarmui",
    "image": "nvidia/cuda:12.8.0-runtime-ubuntu22.04",
    "disk": 100,
    "runtype": "ssh_direc",  # Direct SSH access (jupyter_direct has issues)
    "onstart": onstart_script,
}

print(f"Creating instance on offer {offer_id}...")
r = httpx.put(f"{VASTAI_API_URL}/asks/{offer_id}/", headers=headers, json=payload, timeout=60)
print(f"Status: {r.status_code}")
data = r.json()
instance_id = data.get("new_contract")

if not instance_id:
    print(f"ERROR: Failed to create instance: {data}")
    exit(1)

print(f"Instance ID: {instance_id}")
print("\nWaiting for instance to start (checking every 10s)...")

ssh_host = None
ssh_port = None

for i in range(60):
    time.sleep(10)
    r = httpx.get(f"{VASTAI_API_URL}/instances/{instance_id}/", headers=headers, timeout=30)
    inst = r.json()
    if "instances" in inst:
        inst = inst["instances"]

    status = inst.get("actual_status", "unknown")
    status_msg = inst.get("status_msg", "")[:60]

    print(f"[{(i+1)*10}s] Status: {status} | Msg: {status_msg}")

    if status == "running":
        ssh_host = inst.get('ssh_host')
        ssh_port = inst.get('ssh_port')
        print("\n" + "="*50)
        print("INSTANCE RUNNING!")
        print("="*50)
        print(f"Instance ID: {instance_id}")
        print(f"SSH Command: ssh root@{ssh_host} -p {ssh_port}")
        print("\nThe onstart script is now running. It will:")
        print("  1. Install dependencies")
        print("  2. Download Wan 2.2 model (~9.6GB)")
        print("  3. Install SwarmUI + ComfyUI")
        print("  4. Start cloudflared tunnel")
        print("\nMonitor progress with:")
        print(f"  ssh root@{ssh_host} -p {ssh_port} 'tail -f /var/log/onstart.log'")
        print("\nGet public URL when ready:")
        print(f"  ssh root@{ssh_host} -p {ssh_port} 'cat /root/public_url.txt'")
        break

    if status in ("exited", "error"):
        print(f"\nERROR: Instance failed with status: {status}")
        print(f"Message: {status_msg}")
        break
else:
    print("\nTIMEOUT: Instance did not reach running status in 10 minutes")

print(f"\nTo destroy: python -c \"import httpx; httpx.delete('{VASTAI_API_URL}/instances/{instance_id}/', headers={{'Authorization': 'Bearer {api_key[:10]}...'}})\"")
