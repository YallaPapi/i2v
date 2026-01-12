# Vast.ai + Pinokio Setup Progress

## Overview

Setting up Pinokio on Vast.ai RTX 5090 with `nvidia/cuda:12.8.0-runtime-ubuntu22.04` base image.

**Status**: ✅ Complete - Pinokio running via supervisord with XFCE desktop

---

## Current Instance

| Property | Value |
|----------|-------|
| Instance ID | `29908690` |
| GPU | RTX 5090 (32GB VRAM) |
| SSH | `ssh root@ssh9.vast.ai -p 28690` |
| Public IP | `75.172.120.12` |
| Docker Image | `nvidia/cuda:12.8.0-runtime-ubuntu22.04` |
| Price | ~$0.18/hr |

---

## Verified Working Steps

*Only commands that have been tested and confirmed working are listed below.*

### Step 1: Instance Creation

Instance created with:
- Offer ID: 28142622
- Image: `nvidia/cuda:12.8.0-runtime-ubuntu22.04`
- Runtype: `ssh_direc`

### Step 2: SSH Access Verified

```bash
ssh root@ssh9.vast.ai -p 28690
```

GPU confirmed: `NVIDIA GeForce RTX 5090, 32607 MiB, Driver 580.65.06`

### Step 3: Base Dependencies

```bash
apt-get update -qq
apt-get install -y -qq git wget curl
```

### Step 4: Display Stack (Xvfb, x11vnc, noVNC)

```bash
apt-get install -y -qq xvfb x11vnc novnc websockify
```

Verified: `/usr/bin/Xvfb`, `/usr/bin/x11vnc`, `/usr/bin/websockify` exist

### Step 5: Start Xvfb

```bash
Xvfb :0 -screen 0 1920x1080x24 -ac &
```

Verified running: `ps aux | grep Xvfb` shows process

### Step 6: Start x11vnc

```bash
x11vnc -display :0 -forever -shared -rfbport 5900 -noxdamage -bg
```

Verified: Listening on TCP port 5900

### Step 7: Start websockify (noVNC proxy)

```bash
websockify --web=/usr/share/novnc/ 1111 localhost:5900 &
```

Verified: Listening on :1111, proxying to localhost:5900

### Step 8: Install cloudflared

```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

Verified: `cloudflared version 2025.11.1`

### Step 9: Start cloudflared tunnel

```bash
nohup cloudflared tunnel --url http://localhost:1111 > /tmp/cloudflared.log 2>&1 &
sleep 10
grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -1
```

**Tunnel URL**: `https://housewives-occupations-pocket-conf.trycloudflare.com`

Verified: `curl https://housewives-occupations-pocket-conf.trycloudflare.com/vnc.html` returns noVNC HTML

### Step 10: Install Electron Dependencies

```bash
apt-get install -y -qq libgtk-3-0 libnotify4 libnss3 libxss1 libasound2 libxtst6 xauth libgbm1 libdrm2 libxkbcommon0 fonts-liberation
```

### Step 11: Install XFCE Desktop Environment (CRITICAL)

**Root cause of Pinokio crashes**: Electron apps require a proper desktop session, not just bare Xvfb.

```bash
apt-get install -y -qq xfce4 xfce4-session xfce4-terminal dbus-x11
```

### Step 12: Set Up Environment and Start XFCE Session

```bash
# Set up environment
mkdir -p /dev/shm
chmod 1777 /dev/shm
export XDG_RUNTIME_DIR=/tmp/xdg-runtime
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR

# Start dbus
service dbus start 2>/dev/null || dbus-daemon --system --fork 2>/dev/null

# Start XFCE session on :0
export DISPLAY=:0
nohup startxfce4 > /var/log/startxfce4.log 2>&1 &
sleep 5
```

Verified: `xfce4-session`, `xfwm4`, `xfce4-panel` all running

### Step 13: Install Pinokio

```bash
cd /opt
wget -q "https://github.com/pinokiocomputer/pinokio/releases/download/4.0.5/Pinokio-4.0.5-linux-x86_64.AppImage" -O Pinokio.AppImage
chmod +x Pinokio.AppImage
./Pinokio.AppImage --appimage-extract
mv squashfs-root Pinokio
```

### Step 14: Create Pinokio Launcher Script

```bash
cat > /root/start-pinokio.sh << 'SCRIPT'
#!/usr/bin/env bash
set -e

export DISPLAY=:0
export ELECTRON_OZONE_PLATFORM_HINT=x11
export ELECTRON_DISABLE_GPU=1
export LIBGL_ALWAYS_SOFTWARE=1
export TMPDIR=/tmp
export XDG_RUNTIME_DIR=/tmp/xdg-runtime

mkdir -p /dev/shm
chmod 1777 /dev/shm
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

cd /opt/Pinokio
exec ./pinokio-bin --no-sandbox \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-gpu-compositing \
  --disable-gpu-sandbox
SCRIPT
chmod +x /root/start-pinokio.sh
```

**Note**: The `--disable-gpu` flags only disable Electron's UI GPU acceleration, NOT CUDA compute. Your 5090 remains fully available for ML workloads.

### Step 15: Configure Supervisord

```bash
cat > /etc/supervisor/conf.d/pinokio.conf << 'CONF'
[program:pinokio]
command=/root/start-pinokio.sh
autostart=true
autorestart=true
stdout_logfile=/var/log/pinokio.out.log
stderr_logfile=/var/log/pinokio.err.log
user=root
CONF

supervisord -c /etc/supervisor/supervisord.conf
supervisorctl reread
supervisorctl update
supervisorctl status pinokio
```

Verified: `pinokio RUNNING pid XXXX, uptime 0:00:XX`

---

## Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Xvfb :0 | ✅ Running | 1920x1080x24 |
| x11vnc | ✅ Running | Port 5900 |
| noVNC | ✅ Running | Port 1111 via websockify |
| Cloudflare Tunnel | ✅ Running | Quick tunnel URL active |
| XFCE Session | ✅ Running | xfce4-session, xfwm4, xfce4-panel |
| Pinokio | ✅ Running | Port 42000, managed by supervisord |

---

## Access URLs

- **noVNC**: Get current tunnel URL with:
  ```bash
  ssh root@ssh9.vast.ai -p 28690 "grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -1"
  ```
- **Pinokio Web**: Internal port 42000 (access via noVNC desktop)

---

## Key Learnings

1. **Electron apps need a real desktop session** - bare Xvfb causes segfaults
2. **XFCE is lightweight and works well** - much better than trying X11 hacks
3. **Supervisord manages Pinokio** - auto-restarts on crash
4. **GPU flags are UI-only** - `--disable-gpu` doesn't affect CUDA compute

