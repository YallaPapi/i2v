# i2v - Image to Video & Image Generation Service

Backend service for AI-powered image-to-video and image generation using Fal.ai.

## Features

- **Multi-model video generation**: Wan, Kling, Veo (Google), Sora (OpenAI)
- **Multi-model image generation**: GPT-Image, Kling, Nano-Banana, Flux
- **Local image upload**: Upload from local folders to Fal CDN
- **Upload caching**: SHA256 deduplication prevents re-uploading same images
- **Auto-download**: Completed videos/images automatically saved locally
- **Bulk generation**: Process entire folders with multiple prompts
- **REST API**: Full job management via FastAPI

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your FAL_API_KEY

# Run the API server
uvicorn app.main:app --reload

# In another terminal, run the worker
python -m app.worker
```

## Environment Variables

```env
FAL_API_KEY=your_fal_api_key_here
DB_PATH=wan_jobs.db
WORKER_POLL_INTERVAL_SECONDS=10
AUTO_DOWNLOAD_DIR=downloads
UPLOAD_CACHE_ENABLED=true
DEFAULT_RESOLUTION=1080p
DEFAULT_DURATION_SEC=5
```

## Video Generation

### API Endpoints

```bash
# Create a video job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "motion_prompt": "Camera slowly zooms in",
    "resolution": "1080p",
    "duration_sec": 5,
    "model": "kling"
  }'

# Get job status
curl http://localhost:8000/jobs/1

# List jobs (with optional filters)
curl "http://localhost:8000/jobs?status=completed&limit=10"
```

### Video Models & Pricing

#### Wan Models

| Model | Resolution | Per Second | 5s Video | 10s Video |
|-------|------------|------------|----------|-----------|
| `wan` | 480p | $0.05 | $0.25 | $0.50 |
| `wan` | 720p | $0.10 | $0.50 | $1.00 |
| `wan` | 1080p | $0.15 | $0.75 | $1.50 |
| `wan21` | 480p | flat | $0.20 | $0.20 |
| `wan21` | 720p | flat | $0.40 | $0.40 |
| `wan22` | 480p | $0.04 | $0.20 | $0.40 |
| `wan22` | 580p | $0.06 | $0.30 | $0.60 |
| `wan22` | 720p | $0.08 | $0.40 | $0.80 |
| `wan-pro` | 1080p | $0.16 | $0.80 | $1.60 |

#### Kling Models

| Model | Tier | 5s Video | 10s Video | Notes |
|-------|------|----------|-----------|-------|
| `kling` | v2.5 Turbo Pro | $0.35 | $0.70 | Best speed/quality balance |
| `kling-master` | v2.1 Master | $1.40 | $2.80 | Highest quality |
| `kling-standard` | v2.1 Standard | $0.25 | $0.50 | Budget option |

*Kling pricing: Base cost for 5s + $0.07/s (turbo), $0.28/s (master), $0.05/s (standard) for additional seconds.*

#### Google Veo Models

| Model | Audio | Per Second | 6s Video | 8s Video |
|-------|-------|------------|----------|----------|
| `veo2` | - | $0.50 | - | $4.00 |
| `veo31-fast` | Off | $0.10 | $0.60 | $0.80 |
| `veo31-fast` | On | $0.15 | $0.90 | $1.20 |
| `veo31` | Off | $0.20 | $1.20 | $1.60 |
| `veo31` | On | $0.40 | $2.40 | $3.20 |
| `veo31-flf` | Off | $0.20 | $1.20 | $1.60 |
| `veo31-fast-flf` | Off | $0.10 | $0.60 | $0.80 |

*Veo supports 4s, 6s, 8s durations. FLF = First-Last Frame (requires two images).*

#### OpenAI Sora Models

| Model | Resolution | Per Second | 4s Video | 8s Video | 12s Video |
|-------|------------|------------|----------|----------|-----------|
| `sora-2` | 720p | $0.10 | $0.40 | $0.80 | $1.20 |
| `sora-2-pro` | 720p | $0.30 | $1.20 | $2.40 | $3.60 |
| `sora-2-pro` | 1080p | $0.50 | $2.00 | $4.00 | $6.00 |

*Sora supports 4s, 8s, 12s durations.*

### Video Cost Comparison (5s, cheapest option)

| Rank | Model | Cost | Quality |
|------|-------|------|---------|
| 1 | `wan22` 480p | $0.20 | Good |
| 2 | `wan21` 480p | $0.20 | Good |
| 3 | `kling-standard` | $0.25 | Good |
| 4 | `wan` 480p | $0.25 | Good |
| 5 | `kling` | $0.35 | Great |
| 6 | `sora-2` 720p (4s) | $0.40 | Great |
| 7 | `veo31-fast` (6s) | $0.60 | Great |
| 8 | `wan-pro` 1080p | $0.80 | Excellent |
| 9 | `kling-master` | $1.40 | Excellent |

---

## Image Generation

### API Endpoints

```bash
# List available image models
curl http://localhost:8000/images/models

# Create an image job
curl -X POST http://localhost:8000/images \
  -H "Content-Type: application/json" \
  -d '{
    "source_image_url": "https://example.com/person.jpg",
    "prompt": "same person wearing a red dress in Paris",
    "model": "gpt-image-1.5",
    "aspect_ratio": "9:16",
    "num_images": 1
  }'

# Get image job status
curl http://localhost:8000/images/1

# List image jobs
curl "http://localhost:8000/images?status=completed"
```

### Image Models & Pricing

| Model | Price | Best For |
|-------|-------|----------|
| `gpt-image-1.5` | $0.009-$0.20/image | High-fidelity editing, strong prompt adherence |
| `kling-image` | $0.028/image | Multi-reference control, character consistency |
| `nano-banana` | $0.039/image | Budget Google model, general editing |
| `nano-banana-pro` | $0.15/image | Google's best, realistic, good typography |

### Image Parameters

| Parameter | Options | Default |
|-----------|---------|---------|
| `model` | See above | `gpt-image-1.5` |
| `aspect_ratio` | `1:1`, `9:16`, `16:9`, `4:3`, `3:4` | `9:16` |
| `quality` | `low`, `medium`, `high` | `high` |
| `num_images` | `1`, `2`, `3`, `4` | `1` |

---

## Bulk Generation

Generate videos from a folder of local images:

```bash
# All combinations (3 images x 4 prompts = 12 videos)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --model kling

# One-to-one pairing (3 images + 3 prompts = 3 videos)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --one-to-one

# Dry run (preview without submitting)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --dry-run

# With specific settings
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images \
  --model kling-master --resolution 720p --duration 10
```

Prompts file format (separate with `---` or blank lines):
```
Camera slowly zooms in on the subject
---
The subject turns and smiles
---
Gentle breeze moves through the scene
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      BULK GENERATION                        │
│  Local Images → Upload to Fal CDN → Create Jobs            │
│      (with SHA256 caching to avoid re-uploads)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        API SERVER                           │
│  POST /jobs → Video jobs     POST /images → Image jobs     │
│  GET /jobs → List videos     GET /images → List images     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     BACKGROUND WORKER                       │
│  Poll pending → Submit to Fal → Poll status → Download     │
│     (concurrent: 5 submits, 20 polls per cycle)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      AUTO-DOWNLOAD                          │
│  Videos → downloads/job_{id}_{model}_{prompt}.mp4          │
│  Images → downloads/images/img_{id}_{model}_{idx}.png      │
└─────────────────────────────────────────────────────────────┘
```

## Job Status Flow

```
pending → submitted → running → completed (+ auto-download)
                  ↘          ↘
                   → failed ←
```

## Project Structure

```
i2v/
├── app/
│   ├── main.py          # FastAPI application
│   ├── config.py        # Settings (pydantic-settings)
│   ├── database.py      # SQLAlchemy setup
│   ├── models.py        # Job, ImageJob, UploadCache models
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── fal_client.py    # Fal API client (video models)
│   ├── image_client.py  # Fal API client (image models)
│   ├── fal_upload.py    # Local image upload with caching
│   └── worker.py        # Background worker (video + image)
├── scripts/
│   ├── bulk_generate.py     # Bulk video generation
│   ├── download_videos.py   # Manual batch download
│   └── demo_create_jobs.py  # Demo script
├── downloads/
│   ├── *.mp4            # Downloaded videos
│   ├── images/          # Downloaded images
│   └── index.csv        # Video download index
├── requirements.txt
└── .env
```

## Running Tests

```bash
pytest tests/ -v
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Frontend Features

### Image Library Performance
- **Auto-thumbnail generation**: Small 150px JPEG previews automatically created for all generated images
- **Batch loading**: Library loads 100 images at a time with infinite scroll
- **Native lazy loading**: Browser-native deferred image loading
- **Background migration**: On startup, auto-generates thumbnails for existing images that don't have them

### Playground Settings
- **Default mode persistence**: Photos/Videos/Both mode saved to localStorage
- **GPT image quality default**: Low quality by default for faster/cheaper generation

### Jobs Page
- **Model badges with details**: Shows model name, resolution, and duration for each job

---

## Recent Changes (January 2026)

### Performance Improvements
- Image library now loads instantly with small thumbnails
- Thumbnails auto-generated on every i2i run (150px, 60% quality JPEG)
- Existing images get thumbnails on backend startup
- Frontend uses pagination + infinite scroll instead of loading all images

### UX Improvements
- GPT image quality defaults to "low"
- Mode selection (photos/videos/both) persists across sessions
- Audio toggle for Veo models (checkbox, not fancy toggle)
- Jobs page shows resolution and duration in model badges
- Download All button actually downloads files now (was broken)
- Recent prompts panel with Add/Copy buttons

### Backend Changes
- Parallel job processing increased to 20 concurrent
- Thumbnail service at `app/services/thumbnail.py`
- Auto-migration endpoint: `POST /api/pipelines/images/library/generate-thumbnails`
