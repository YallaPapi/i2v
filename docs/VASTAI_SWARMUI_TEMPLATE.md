# Vast.ai SwarmUI Template Documentation

**Source:** https://cloud.vast.ai/template/readme/8e5e6ab1fceb9db3f813e815907b3390

## Key Information

- **Template Hash:** `8e5e6ab1fceb9db3f813e815907b3390`
- **Docker Image:** `vastai/swarmui` (built and maintained by Vast.ai)
- **Installation Directory:** `/workspace/SwarmUI`
- **No models included** - SwarmUI downloads them on startup

## Port Configuration

| Service | External Port | Internal Port |
|---------|---------------|---------------|
| Instance Portal | 1111 | 11111 |
| SwarmUI | 7865 | 17865 |
| Syncthing | 8384 | 18384 |
| Jupyter | 8080 | 8080 |

**Important:** SwarmUI runs on internal port 17865, proxied to external port 7865.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| WORKSPACE | /workspace | Workspace directory |
| ENABLE_AUTH | true | Enable token-based and basic auth |
| AUTH_EXCLUDE | | Disable auth for specific ports (e.g., 7865) |
| ENABLE_HTTPS | true | Enable TLS |
| SWARMUI_ARGS | --launch_mode none --port 17865 | Startup options for launch-linux.sh |
| PROVISIONING_SCRIPT | | URL to shell script for custom setup |
| PORTAL_CONFIG | | Configures Instance Portal and app startup |

## Connecting to SwarmUI

### Via Open Button (Recommended)
1. Click "Open" button on instance card
2. Sets auth cookie using OPEN_BUTTON_TOKEN
3. Access SwarmUI through Instance Portal dashboard

### Via SSH Port Forward
```bash
ssh root@INSTANCE_IP -p SSH_PORT -L 7865:localhost:17865
```
Then access at http://localhost:7865 (no auth needed through tunnel)

### Via Cloudflare Tunnel
- Instance Portal can create Cloudflare tunnels
- Access via `webpage` field in API response
- Tunnels tab shows direct mapping between local and tunnel addresses

## Dynamic Provisioning (onstart script)

Host a shell script and set URL in `PROVISIONING_SCRIPT`:

```bash
#!/bin/bash
set -eo pipefail

# Activate virtual environment
. /venv/main/bin/activate

# Install packages
pip install your-packages

# Download models
wget -P "${WORKSPACE}/SwarmUI/Models/" https://example.com/model.safetensors
```

## Upgrading SwarmUI

```bash
cd /workspace/SwarmUI
git checkout master
git fetch --tags
git checkout [desired_ref]
./update-linuxmac.sh
supervisorctl restart swarmui
```

## Application Management

Uses Supervisor for process management:

```bash
supervisorctl status          # View all processes
supervisorctl start swarmui   # Start SwarmUI
supervisorctl stop swarmui    # Stop SwarmUI
supervisorctl restart swarmui # Restart SwarmUI
supervisorctl tail -f swarmui # Follow logs
```

Config files: `/etc/supervisor/conf.d/`
Startup scripts: `/opt/supervisor-scripts/`

## API Usage

When creating instance via vast.ai API:
- Use `template_hash_id: "8e5e6ab1fceb9db3f813e815907b3390"`
- Or use `image: "vastai/swarmui"` directly
- The `webpage` field in response contains Cloudflare tunnel URL

## Model Directories (SwarmUI)

```
/workspace/SwarmUI/Models/
├── diffusion_models/   # Main models (GGUF, safetensors)
├── Lora/               # LoRA models
├── VAE/                # VAE models
├── Stable-Diffusion/   # SD checkpoints
├── text_encoders/      # Text encoders
└── clip/               # CLIP models
```
