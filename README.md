# i2v - Image to Video Generation Service

Backend service for AI image-to-video generation using Fal.ai (Wan 2.5 & Kling 2.5 Turbo).

## Features

- **Multi-model support**: Wan 2.5 and Kling 2.5 Turbo
- **Local image upload**: Upload from local folders to Fal CDN (avoids rate limiting)
- **Upload caching**: SHA256 deduplication prevents re-uploading same images
- **Auto-download**: Completed videos automatically saved to local folder
- **Bulk generation**: Process entire folders of images with multiple prompts
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

## Bulk Generation (Local Images)

Generate videos from a folder of images:

```bash
# All combinations (3 images x 4 prompts = 12 videos)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --model wan

# One-to-one pairing (3 images + 3 prompts = 3 videos)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --one-to-one

# Dry run (preview without submitting)
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images --dry-run

# With specific settings
python scripts/bulk_generate.py prompts.txt --images-dir ./my_images \
  --model kling --resolution 480p --duration 5
```

Prompts file format (separate prompts with `---` or blank lines):
```
Camera slowly zooms in on the subject
---
The subject turns and smiles
---
Gentle breeze moves through the scene
```

## API Endpoints

### Create a Job
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "motion_prompt": "Camera slowly zooms in",
    "resolution": "1080p",
    "duration_sec": 5,
    "model": "wan"
  }'
```

### Get Job Status
```bash
curl http://localhost:8000/jobs/1
```

### List Jobs
```bash
# All jobs
curl http://localhost:8000/jobs

# Filter by status
curl "http://localhost:8000/jobs?status=completed"

# Pagination
curl "http://localhost:8000/jobs?limit=10&offset=0"
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Models & Pricing

Run `python scripts/bulk_generate.py --list-models` for pricing summary.

### Wan Models

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

### Kling Model

| Model | Duration | Cost |
|-------|----------|------|
| `kling` | 5s | $0.35 |
| `kling` | 10s | $0.70 |
| `kling` | 15s | $1.05 |
| `kling` | 30s | $2.10 |

*Base $0.35 for 5s + $0.07/additional second. Resolution does not affect price.*

### Google Veo Models

| Model | Audio | Per Second | 4s | 6s | 8s |
|-------|-------|------------|-----|-----|-----|
| `veo2` | - | $0.50 | - | - | $4.00 |
| `veo31-fast` | Off | $0.10 | $0.40 | $0.60 | $0.80 |
| `veo31-fast` | On | $0.15 | $0.60 | $0.90 | $1.20 |
| `veo31` | Off | $0.20 | $0.80 | $1.20 | $1.60 |
| `veo31` | On | $0.40 | $1.60 | $2.40 | $3.20 |
| `veo31-flf` | Off | $0.20 | $0.80 | $1.20 | $1.60 |
| `veo31-fast-flf` | Off | $0.10 | $0.40 | $0.60 | $0.80 |

*Veo2: 720p only, 5-8s. Veo31: 720p/1080p, 4/6/8s. Resolution does not affect price.*

### Cost Comparison (5s video, cheapest resolution)

| Rank | Model | Cost |
|------|-------|------|
| 1 | `wan22` 480p | $0.20 |
| 2 | `wan21` 480p | $0.20 |
| 3 | `wan` 480p | $0.25 |
| 4 | `kling` | $0.35 |
| 5 | `veo31-fast` (no audio) | $0.60 |
| 6 | `wan` 1080p | $0.75 |
| 7 | `wan-pro` 1080p | $0.80 |
| 8 | `veo31` (no audio) | $1.20 |
| 9 | `veo2` | $2.50 |

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
│  POST /jobs → Database (pending)                           │
│  GET /jobs → List/filter jobs                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     BACKGROUND WORKER                       │
│  Poll pending → Submit to Fal → Poll status → Download     │
│     (concurrent: 5 submits, 20 polls)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      AUTO-DOWNLOAD                          │
│  Completed videos → downloads/job_{id}_{model}.mp4         │
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
│   ├── main.py         # FastAPI application
│   ├── config.py       # Settings (pydantic-settings)
│   ├── database.py     # SQLAlchemy setup
│   ├── models.py       # Job & UploadCache models
│   ├── schemas.py      # Pydantic schemas
│   ├── fal_client.py   # Fal API client (multi-model)
│   ├── fal_upload.py   # Local image upload with caching
│   └── worker.py       # Background worker
├── scripts/
│   ├── bulk_generate.py    # Bulk generation from local folder
│   ├── download_videos.py  # Manual batch download
│   └── demo_create_jobs.py # Demo script
├── downloads/          # Auto-downloaded videos
├── requirements.txt
└── .env
```

## Running Tests

```bash
pytest tests/ -v
```
