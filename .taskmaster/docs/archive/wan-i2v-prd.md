# PRD: Wan 2.2 Image-to-Video Generation on Vast.ai

## Overview
Add Wan 2.2 image-to-video generation capability using self-hosted GPU instances on vast.ai. Use the Fast Wan 2.2 GGUF models for efficient generation.

## Current State
- Vast.ai integration exists (`app/services/vastai_client.py`)
- ComfyUI session-based auth works
- Image generation pipeline works (tested on RTX 3060)
- R2 caching for outputs works

## Goal
Generate videos from images using Wan 2.2 I2V models on vast.ai GPU instances.

## Required Models (to be downloaded to vast.ai instance)
Located in `/workspace/ComfyUI/models/`:
- `unet/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` - High noise GGUF model
- `unet/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf` - Low noise GGUF model
- `text_encoders/nsfw_wan_umt5-xxl_fp8_scaled.safetensors` - Text encoder
- `vae/wan_2.1_vae.safetensors` - VAE
- `loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors` - High noise LoRA
- `loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors` - Low noise LoRA

## Tasks

### Task 1: Create Wan 2.2 Workflow Builder
Create a function `build_wan22_i2v_workflow()` in `app/services/vastai_client.py` that builds a ComfyUI workflow JSON for Wan 2.2 I2V generation.

The workflow should use these ComfyUI nodes:
- `UnetLoaderGGUF` - Load GGUF unet models
- `CLIPLoader` with type "wan" - Load text encoder
- `VAELoader` - Load VAE
- `LoraLoaderModelOnly` - Load LightX2V LoRAs
- `LoadImage` - Load input image (must be uploaded first)
- `CLIPTextEncode` - Encode prompt
- `WanImageToVideo` - The main I2V sampling node
- `VHS_VideoCombine` - Combine frames to video

Parameters:
- image_filename: str (uploaded image name)
- prompt: str
- negative_prompt: str = ""
- num_frames: int = 81 (default ~3 seconds at 24fps)
- steps: int = 4 (LightX2V uses 4 steps)
- cfg_scale: float = 1.0
- seed: int = -1

### Task 2: Add Model Download Helper
Create `ensure_wan_models()` function that:
1. SSHs into the vast.ai instance
2. Checks if required models exist
3. Downloads missing models from HuggingFace URLs
4. Returns True when all models are ready

Model URLs:
- HighNoise GGUF: `https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf`
- LowNoise GGUF: `https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf`
- Text encoder: `https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors`
- VAE: `https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors`
- HighNoise LoRA: `https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors`
- LowNoise LoRA: `https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors`

### Task 3: Add Video Generation Endpoint
Add `/vastai/generate-video` endpoint to `app/routers/vastai.py`:

```python
class VideoGenerateRequest(BaseModel):
    image_url: str
    prompt: str
    negative_prompt: str = ""
    num_frames: int = 81
    steps: int = 4
    cfg_scale: float = 1.0
    seed: int = -1

@router.post("/generate-video")
async def generate_video(request: VideoGenerateRequest) -> dict:
    # 1. Get or create GPU instance (needs 24GB+ VRAM)
    # 2. Ensure Wan models are downloaded
    # 3. Upload input image to ComfyUI
    # 4. Build Wan 2.2 workflow
    # 5. Submit job and wait for result
    # 6. Cache video to R2 and return URL
```

### Task 4: Test End-to-End
1. Rent a 24GB+ GPU instance (RTX 4090/5090)
2. Call `/vastai/generate-video` with a test image
3. Verify video is generated and cached to R2
4. Clean up instance

## Success Criteria
- Can generate a video from an image URL using the API
- Video is cached to R2 with public URL returned
- Generation completes in under 2 minutes for 81 frames
