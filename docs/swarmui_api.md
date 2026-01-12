# SwarmUI API Documentation

## Overview

SwarmUI provides a session-based HTTP API for video generation. All API calls require a session ID.

## Base URL

```
https://{pod-id}-7801.proxy.runpod.net
```

Current pod: `https://lg1fxm4ygf09dq-7801.proxy.runpod.net`

## Authentication

SwarmUI uses session-based auth. Get a session first, then use it for all subsequent calls.

---

## Core Endpoints

### 1. Get New Session

**POST** `/API/GetNewSession`

```json
Request: {}
Response: {
  "session_id": "63d2649ed0fbcf9b62a198642e322a80855d62d5",
  "user_id": "local",
  "version": "0.9.7.4.GIT-a6e730b5",
  ...
}
```

### 2. List Models

**POST** `/API/ListModels`

```json
Request: {
  "session_id": "<session>",
  "path": "",
  "depth": 10
}
Response: {
  "folders": [],
  "files": [
    {
      "name": "wan2.1-i2v-14b-480p-Q5_K_M.gguf",
      "title": "wan2.1-i2v-14b-480p-Q5_K_M",
      "architecture": "wan-2_1-image2video-14b",
      "class": "Wan 2.2 Image2Video 14B",
      "resolution": "640x640",
      "loaded": false,
      ...
    }
  ]
}
```

### 3. Select/Load Model

**POST** `/API/SelectModel`

```json
Request: {
  "session_id": "<session>",
  "model": "wan2.1-i2v-14b-480p-Q5_K_M.gguf"
}
Response: {"success": true}
```

### 4. Generate Video (Text-to-Video)

**POST** `/API/GenerateText2Image`

```json
Request: {
  "session_id": "<session>",
  "images": 1,
  "prompt": "a beautiful sunset over the ocean",
  "model": "wan2.1-i2v-14b-480p-Q5_K_M.gguf",
  "width": 480,
  "height": 480,
  "steps": 20,
  "videoframes": 17,
  "videofps": 8
}
Response: {
  "images": ["View/local/raw/2026-01-11/1225002-prompt-model.mp4"]
}
```

### 5. Generate Video (Image-to-Video)

**POST** `/API/GenerateText2Image`

```json
Request: {
  "session_id": "<session>",
  "images": 1,
  "prompt": "camera slowly panning, gentle motion",
  "model": "wan2.1-i2v-14b-480p-Q5_K_M.gguf",
  "width": 480,
  "height": 480,
  "steps": 20,
  "videoframes": 17,
  "videofps": 8,
  "initimage": "<base64_or_url>",
  "initimagecreativestrength": 0.8
}
Response: {
  "images": ["View/local/raw/2026-01-11/filename.mp4"]
}
```

### 6. List Backends

**POST** `/API/ListBackends`

```json
Request: {"session_id": "<session>"}
Response: {
  "0": {
    "type": "comfyui_selfstart",
    "status": "running",
    "id": 0,
    "enabled": true,
    "can_load_models": true,
    ...
  }
}
```

### 7. Restart Backends

**POST** `/API/RestartBackends`

```json
Request: {"session_id": "<session>"}
Response: {"result": "Success.", "count": 1}
```

---

## File Access

Generated files are accessible at:
```
GET /Output/{path_from_response}
```

Example: `/Output/local/raw/2026-01-11/filename.mp4`

Or via View endpoint:
```
GET /View/{path_from_response}
```

---

## Model Configuration

### Wan 2.2 I2V Model

- **Model File**: `wan2.1-i2v-14b-480p-Q5_K_M.gguf`
- **Architecture**: `wan-2_1-image2video-14b`
- **Resolution**: 480x480 (native), up to 640x640
- **Format**: GGUF (quantized Q5_K_M)
- **VRAM**: ~12GB for generation

### Required ComfyUI Extensions

- **ComfyUI-GGUF**: Required for GGUF model loading
  - Install: `git clone https://github.com/city96/ComfyUI-GGUF.git` in `custom_nodes/`
  - Dependencies: `pip install gguf>=0.13.0`

---

## Error Responses

```json
{"error": "missing session id"}
{"error": "Model failed to load."}
{"error": "No backends match the settings..."}
```

---

## RunPod Configuration

| Variable | Value |
|----------|-------|
| `RUNPOD_POD_ID` | `lg1fxm4ygf09dq` |
| `RUNPOD_POD_URL` | `https://lg1fxm4ygf09dq-7801.proxy.runpod.net` |
| SSH | `ssh -i ~/.ssh/id_ed25519 root@82.221.170.242 -p 45118` |
