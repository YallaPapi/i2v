#!/bin/bash
# Vast.ai Onstart Script - SwarmUI Model Downloader
# Uses SwarmUI's ModelsAPI for reliable model registration
# Updated: 2026-01-16
exec > /var/log/onstart.log 2>&1
set -x
echo "Onstart script started at $(date)"

# Configuration (with fallback defaults)
export CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-eyJhIjoiNmU4YWNhOWI4MDEyYjE5YmYwMmZlMDBiNWJiMGQxNjUiLCJ0IjoiZmU2ZjI1YTktZjU5Yi00NmYzLTk1NzgtN2MxOWNkN2ZhZjNlIiwicyI6Ik16WXdPR1kxTjJJdE1HUmxPUzAwT1dOaExUaGlZVE10WXpBM09XVmxOamxoTnpKbCJ9}"
export CIVITAI_TOKEN="${CIVITAI_TOKEN:-1fce15bca33db94cda6daab75f21de79}"

PIP_CACHE="/workspace/pip_cache"
mkdir -p "$PIP_CACHE"

#==============================================================================
# INSTALL PYTHON DEPENDENCIES
#==============================================================================
echo "Installing Python packages..."
/venv/main/bin/pip install --cache-dir="$PIP_CACHE" gguf sageattention triton websockets --quiet

#==============================================================================
# WAIT FOR SWARMUI TO BE READY
#==============================================================================
echo "Waiting for SwarmUI on port 17865..."
for i in {1..120}; do
    if nc -z localhost 17865 2>/dev/null; then
        echo "SwarmUI is ready!"
        break
    fi
    if [ $i -eq 120 ]; then
        echo "ERROR: SwarmUI failed to start after 10 minutes"
        exit 1
    fi
    sleep 5
done

# Give SwarmUI a moment to fully initialize
sleep 10

#==============================================================================
# DOWNLOAD MODELS VIA SWARMUI API
#==============================================================================
echo "Downloading models via SwarmUI ModelsAPI..."

# Copy the downloader script to SwarmUI directory
cat > /workspace/SwarmUI/download_models.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Download models via SwarmUI's ModelsAPI WebSocket endpoint."""

import asyncio
import json
import os
import sys

CIVITAI_MODEL_IDS = [
    # Diffusion models
    2060527, 2060943, 2584698, 2584707, 2367702, 2367780,
    290640, 923681, 501240, 915814,
    # LoRAs
    2090326, 2090344, 2079658, 2079614, 1776890, 984672,
    1301668, 2546506, 263005, 87153, 556208, 2074888, 1071060,
    # Embeddings
    775151, 772342, 145996,
]

MAX_CONCURRENT = 4

async def download_model(model_id, token, host, semaphore):
    import websockets
    url = f"https://civitai.com/api/download/models/{model_id}?token={token}"
    ws_url = f"{host}/API/DoModelDownloadWS"

    async with semaphore:
        print(f"[{model_id}] Starting download...")
        try:
            async with websockets.connect(ws_url, close_timeout=10) as ws:
                await ws.send(json.dumps({"url": url}))
                async for msg in ws:
                    data = json.loads(msg)
                    if "progress" in data:
                        print(f"[{model_id}] {data.get('progress', 0):.0%}")
                    elif "success" in data:
                        print(f"[{model_id}] SUCCESS")
                        return True
                    elif "error" in data:
                        print(f"[{model_id}] ERROR: {data['error']}")
                        return False
                return False
        except Exception as e:
            print(f"[{model_id}] Error: {e}")
            return False

async def main():
    token = os.environ.get("CIVITAI_TOKEN")
    if not token:
        print("ERROR: CIVITAI_TOKEN not set")
        sys.exit(1)

    host = os.environ.get("SWARM_HOST", "ws://localhost:17865")
    print(f"Downloading {len(CIVITAI_MODEL_IDS)} models via {host}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [download_model(mid, token, host, semaphore) for mid in CIVITAI_MODEL_IDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if r is True)
    print(f"Complete: {success}/{len(CIVITAI_MODEL_IDS)} succeeded")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON_SCRIPT

chmod +x /workspace/SwarmUI/download_models.py
/venv/main/bin/python /workspace/SwarmUI/download_models.py

#==============================================================================
# START CLOUDFLARE TUNNEL
#==============================================================================
if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "Starting Cloudflare named tunnel..."
    nohup cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" > /tmp/tunnel.log 2>&1 &
fi

#==============================================================================
# VERIFY
#==============================================================================
echo "Verifying models loaded..."
sleep 5
curl -s http://localhost:17865/API/ListModels -X POST -H "Content-Type: application/json" -d '{"path":"","depth":10}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Models found: {len(d.get(\"files\",[]))}')" 2>/dev/null || echo "Could not query model list"

echo "Onstart script completed at $(date)"
