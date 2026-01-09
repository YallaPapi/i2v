# PRD: Fix Vast.ai GPU Integration (Revised)

## 1. Problem Statement

The vast.ai client (`app/services/vastai_client.py`) cannot successfully create and connect to GPU instances for ComfyUI-based image generation.

### Root Cause Analysis (from Research)

After extensive research of vast.ai documentation and API behavior:

1. **Wrong Docker Image**: Using `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` - a bare CUDA image with NO ComfyUI. Installing from scratch takes 10-15 minutes and often fails.

2. **Wrong Runtype**: Using `jupyter_direc ssh_direc ssh_proxy` which starts Jupyter on port 8080 as a managed service, conflicting with ComfyUI startup.

3. **No Port Exposure**: Not passing `-p 8188:8188` in docker options. Vast.ai only exposes ports that are either in the Dockerfile's EXPOSE or explicitly added via `-p`.

4. **Wrong URL Construction**: Using `ssh_host` (SSH proxy address like `ssh1.vast.ai`) instead of `public_ipaddr` (actual machine IP) for HTTP connections.

5. **Custom Startup Script Conflicts**: Large onstart script conflicts with the image's proper entrypoint.

### Vast.ai Networking Model (Research Findings)

- Internal container ports (e.g., 8188) are mapped to RANDOM external ports (e.g., 33526)
- API returns port mappings as: `{"8188/tcp": [{"HostPort": "33526"}]}`
- Access URL must be: `http://{public_ipaddr}:{external_port}`
- Environment variable `VAST_TCP_PORT_8188` contains the external port inside the container
- `ssh_host` is ONLY for SSH tunneling, NOT for HTTP access

---

## 2. Solution: Use Official vast.ai ComfyUI Image

### 2.1 Docker Image

**Use vast.ai's official ComfyUI image**: `vastai/comfy:cuda-12.6-auto`

This image:
- Has ComfyUI pre-installed and configured
- Exposes port 8188 correctly via EXPOSE directive
- Is maintained by vast.ai for their infrastructure
- Has fast cold start (no installation needed)
- Updated regularly (latest: cuda-12.9-auto)

Source: https://hub.docker.com/r/vastai/comfy

Alternative: `ghcr.io/ai-dock/comfyui:cuda-12.1.0-runtime-ubuntu22.04` (ai-dock image)

### 2.2 Instance Creation Parameters

```python
payload = {
    "client_id": "i2v-app",
    "image": "vastai/comfy:cuda-12.6-auto",
    "disk": 50,  # Minimum for models
    "runtype": "ssh_direc ssh_proxy",  # NO jupyter_direc
    "onstart": "",  # Empty - let image handle startup
    "env": {
        "-p 8188:8188": "",  # Explicit port exposure in docker options
        "PYTHONUNBUFFERED": "1",
    },
    "python_utf8": True,
    "lang_utf8": True,
}
```

### 2.3 URL Construction

```python
# CORRECT: Use public_ipaddr for HTTP access
api_url = f"http://{instance.public_ip}:{instance.api_port}"

# WRONG: ssh_host is for SSH tunneling only
# api_url = f"http://{instance.ssh_host}:{instance.api_port}"  # DON'T DO THIS
```

### 2.4 Port Parsing

Parse `8188/tcp` from the ports mapping to get the external HostPort:

```python
ports = instance_data.get("ports", {})
port_info = ports.get("8188/tcp", [])
if port_info:
    external_port = int(port_info[0]["HostPort"])
```

---

## 3. Implementation Tasks

### Task 1: Update Docker Image Configuration
**File**: `app/services/vastai_client.py`

Replace:
```python
COMFYUI_DOCKER_IMAGE = "nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04"
```

With:
```python
COMFYUI_DOCKER_IMAGE = os.getenv(
    "COMFYUI_DOCKER_IMAGE",
    "vastai/comfy:cuda-12.6-auto"
)
```

### Task 2: Remove Custom Startup Script
**File**: `app/services/vastai_client.py`

Remove or empty the `COMFYUI_STARTUP_SCRIPT` variable. The official image handles its own startup.

### Task 3: Fix Runtype Configuration
**File**: `app/services/vastai_client.py`

Change runtype from `"jupyter_direc ssh_direc ssh_proxy"` to `"ssh_direc ssh_proxy"`.

### Task 4: Add Explicit Port Exposure
**File**: `app/services/vastai_client.py`

Add `-p 8188:8188` to the env/docker options in the create_instance payload.

### Task 5: Fix URL Construction in submit_comfyui_job
**File**: `app/services/vastai_client.py`

Use the existing `build_comfyui_url()` helper which correctly uses `public_ip`:
```python
api_url = build_comfyui_url(instance)
```

### Task 6: Test Instance Creation and API Access
Run `test_gpu_pipeline.py` to verify:
1. Instance creates and reaches "running" status
2. Port 8188 is correctly mapped and parsed
3. ComfyUI API responds at the constructed URL
4. Image upload and workflow submission work

### Task 7: Handle Authentication (if using ai-dock image)
If using ai-dock instead of vastai/comfy, add:
```python
"WEB_ENABLE_AUTH": "false"  # Disable auth for API access
```

---

## 4. What NOT To Do

1. **Don't use jupyter_direc runtype** - It starts Jupyter on 8080 and conflicts
2. **Don't use bare CUDA images** - They have no ComfyUI, require long install
3. **Don't use ssh_host for HTTP** - It's the SSH proxy, not the HTTP endpoint
4. **Don't write custom startup scripts** - Official images handle startup properly
5. **Don't build custom Docker images yet** - Use official images first, optimize later

---

## 5. Success Criteria

1. **Instance Creation**: vast.ai instance creates and reaches `running` status within 5 minutes
2. **Port Detection**: API port is correctly parsed as the external mapped port from 8188/tcp
3. **API Access**: ComfyUI API responds at `http://{public_ip}:{external_port}/system_stats`
4. **Image Upload**: Can upload images to ComfyUI's /upload/image endpoint
5. **Workflow Submission**: Can submit workflows and get results back

---

## 6. Files to Modify

| File | Changes |
|------|---------|
| `app/services/vastai_client.py` | Docker image, remove startup script, fix runtype, fix URL construction |
| `app/routers/vastai.py` | Already correct (uses public_ip) |
| `test_gpu_pipeline.py` | Already correct (uses public_ip) |

---

## 7. Deprecated Tasks

The following tasks from the original PRD are now deprecated or modified:

- **Task 300 (Production Docker image)**: Deprioritized. Use official `vastai/comfy` image first. Custom image is optimization for later.
- **Tasks 304-311**: Partially implemented but with wrong approach. This PRD supersedes them.

---

## 8. Research Sources

- [Vast.ai Create Instance API](https://docs.vast.ai/api-reference/instances/create-instance)
- [Vast.ai Networking Guide](https://docs.vast.ai/networking)
- [vastai/comfy Docker Hub](https://hub.docker.com/r/vastai/comfy/)
- [ai-dock/comfyui GitHub](https://github.com/ai-dock/comfyui)
- [Vast.ai CLI Commands](https://docs.vast.ai/cli/commands)

---

## 9. Priority

**CRITICAL** - This blocks all vast.ai/self-hosted GPU functionality.
