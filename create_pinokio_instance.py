"""
Create Vast.ai instance with Pinokio on RTX 5090.
Fully automated setup that works from scratch.

Based on create_swarm_instance.py pattern.
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

# Complete onstart script for Pinokio
# Pinokio is an Electron app - requires display (Xvfb + noVNC)
onstart_script = '''#!/bin/bash
# Vast.ai Onstart Script for Pinokio
set -e
exec > /var/log/onstart.log 2>&1

echo "=== $(date) Starting Pinokio setup ==="

# Step 1: Install system dependencies
echo "=== $(date) Installing system dependencies ==="
apt-get update -qq
apt-get install -y -qq git wget curl python3 python3-pip

# Step 2: Install display dependencies for Electron app
echo "=== $(date) Installing display dependencies ==="
apt-get install -y -qq xvfb x11vnc novnc websockify \\
    libgtk-3-0 libnotify4 libnss3 libxss1 libasound2 libxtst6 xauth \\
    libgbm1 libdrm2 libxkbcommon0 fonts-liberation

# Step 3: Install cloudflared for tunnel
echo "=== $(date) Installing cloudflared ==="
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Step 4: Start Xvfb virtual display
echo "=== $(date) Starting Xvfb ==="
Xvfb :0 -screen 0 1920x1080x24 -ac &
sleep 2
export DISPLAY=:0

# Step 5: Start x11vnc server
echo "=== $(date) Starting x11vnc ==="
x11vnc -display :0 -forever -shared -rfbport 5900 -noxdamage -bg
sleep 2

# Step 6: Start noVNC websocket proxy on port 1111
echo "=== $(date) Starting noVNC ==="
websockify --web=/usr/share/novnc/ 1111 localhost:5900 &
sleep 2

# Step 7: Download Pinokio
echo "=== $(date) Downloading Pinokio ==="
cd /root
wget -q https://github.com/pinokiocomputer/pinokio/releases/latest/download/Pinokio-linux.AppImage -O Pinokio.AppImage
chmod +x Pinokio.AppImage

# Step 8: Start Pinokio
echo "=== $(date) Starting Pinokio ==="
DISPLAY=:0 ./Pinokio.AppImage --no-sandbox > /var/log/pinokio.log 2>&1 &
sleep 5

# Step 9: Start cloudflared tunnel to noVNC port
echo "=== $(date) Starting cloudflared tunnel ==="
nohup cloudflared tunnel --url http://localhost:1111 > /var/log/cloudflared.log 2>&1 &
sleep 10

# Get the public URL
PUBLIC_URL=$(strings /var/log/cloudflared.log 2>/dev/null | grep trycloudflare.com | tail -1 || echo "Check /var/log/cloudflared.log")
echo "=== $(date) Setup complete ==="
echo "Public URL: $PUBLIC_URL"
echo "$PUBLIC_URL" > /root/public_url.txt

# Verify processes are running
echo "=== Process check ==="
ps aux | grep -E "(Xvfb|x11vnc|websockify|Pinokio)" | grep -v grep

echo "=== GPU check ==="
nvidia-smi

echo "=== $(date) Pinokio ready ==="
echo "Access via: $PUBLIC_URL/vnc.html"
'''

payload = {
    "client_id": "i2v-pinokio",
    "image": "nvidia/cuda:12.8.0-runtime-ubuntu22.04",
    "disk": 100,
    "runtype": "ssh_direc",  # Direct SSH access
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
public_ip = None

for i in range(60):
    time.sleep(10)
    r = httpx.get(f"{VASTAI_API_URL}/instances/{instance_id}/", headers=headers, timeout=30)
    inst = r.json()
    if "instances" in inst:
        inst = inst["instances"]

    status = inst.get("actual_status", "unknown")
    status_msg = (inst.get("status_msg") or "")[:60]

    print(f"[{(i+1)*10}s] Status: {status} | Msg: {status_msg}")

    if status == "running":
        ssh_host = inst.get('ssh_host')
        ssh_port = inst.get('ssh_port')
        public_ip = inst.get('public_ipaddr')
        print("\n" + "="*50)
        print("INSTANCE RUNNING!")
        print("="*50)
        print(f"Instance ID: {instance_id}")
        print(f"Public IP: {public_ip}")
        print(f"SSH Command: ssh root@{ssh_host} -p {ssh_port}")
        print("\nThe onstart script is now running. It will:")
        print("  1. Install Xvfb, x11vnc, noVNC")
        print("  2. Download Pinokio AppImage")
        print("  3. Start virtual display + VNC")
        print("  4. Start cloudflared tunnel")
        print("\nMonitor progress with:")
        print(f"  ssh root@{ssh_host} -p {ssh_port} 'tail -f /var/log/onstart.log'")
        print("\nGet public URL when ready:")
        print(f"  ssh root@{ssh_host} -p {ssh_port} 'cat /root/public_url.txt'")
        print("\nDirect noVNC access (if port 1111 exposed):")
        print(f"  http://{public_ip}:1111/vnc.html")
        break

    if status in ("exited", "error"):
        print(f"\nERROR: Instance failed with status: {status}")
        print(f"Message: {status_msg}")
        break
else:
    print("\nTIMEOUT: Instance did not reach running status in 10 minutes")

print(f"\nTo destroy: python -c \"import httpx; httpx.delete('{VASTAI_API_URL}/instances/{instance_id}/', headers={{'Authorization': 'Bearer {api_key[:10]}...'}})\"")
