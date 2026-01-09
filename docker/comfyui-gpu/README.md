# ComfyUI GPU Docker Image

Pre-configured ComfyUI image with NSFW-capable models for vast.ai deployment.

## Pre-baked Models

| Model | Size | Description |
|-------|------|-------------|
| Pony Diffusion V6 XL | 6.5GB | Best for anime/stylized NSFW |
| SDXL Base 1.0 | 6.9GB | General purpose foundation |
| SDXL VAE | 335MB | Required for all SDXL models |
| RealVisXL V4.0 | 6.5GB | Photorealistic humans |
| Juggernaut XL V9 | 6.5GB | Excellent skin textures |

**Total image size: ~30GB**

## Building

```bash
# From this directory
docker build -t comfyui-nsfw:latest .

# Build takes 30-60 minutes to download all models
# Requires ~60GB disk space during build
```

## Running Locally

```bash
docker run --gpus all -p 8188:8188 comfyui-nsfw:latest
```

## Running on vast.ai

1. Push to Docker Hub:
   ```bash
   docker tag comfyui-nsfw:latest yourusername/comfyui-nsfw:latest
   docker push yourusername/comfyui-nsfw:latest
   ```

2. Create vast.ai instance with:
   - Docker image: `yourusername/comfyui-nsfw:latest`
   - GPU: RTX 3090 or better (12GB+ VRAM)
   - Disk: 50GB+
   - Expose port: 8188

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PONY_REALISM_URL` | CivitAI direct download URL for Pony Realism model |
| `LORA_URLS` | Comma-separated CivitAI URLs for LoRAs to download |

Example:
```bash
docker run --gpus all -p 8188:8188 \
  -e PONY_REALISM_URL="https://civitai.com/api/download/..." \
  -e LORA_URLS="https://civitai.com/api/download/...,https://civitai.com/api/download/..." \
  comfyui-nsfw:latest
```

## API Access

ComfyUI API is available at `http://localhost:8188`:

- `POST /prompt` - Submit workflow
- `GET /history/{prompt_id}` - Check status
- `GET /view?filename=...` - Download result
- `POST /upload/image` - Upload input image

## Adding LoRAs at Runtime

```bash
# SSH into running container
docker exec -it <container_id> bash

# Download a LoRA
/opt/scripts/download_lora.sh "https://civitai.com/api/download/models/123456"
```
