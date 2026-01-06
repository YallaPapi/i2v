# Supported Models

## Video Generation Models

### WAN 2.1

- **ID**: `wan-2.1`
- **Description**: High-quality image-to-video generation
- **Output**: MP4 video

### Hunyuan

- **ID**: `hunyuan`
- **Description**: Alternative video generation model
- **Output**: MP4 video

### Kling

- **ID**: `kling-1.6-pro`
- **Description**: Kling video generation
- **Output**: MP4 video

## Image Generation Models

### Flux

- **ID**: `flux-pro`
- **Description**: High-quality image generation
- **Output**: PNG/JPG image

## Model Parameters

Each model accepts:

| Parameter | Type | Description |
|-----------|------|-------------|
| `image_url` | string | Source image URL |
| `prompt` | string | Motion/generation prompt |
| `negative_prompt` | string | What to avoid |
| `num_frames` | int | Video length (model-specific) |
