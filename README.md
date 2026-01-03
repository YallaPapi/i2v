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

Run `python scripts/bulk_generate.py --list-models` for current pricing.

| Model | Pricing | Notes |
|-------|---------|-------|
| `wan` | 480p=$0.05/s, 720p=$0.10/s, 1080p=$0.15/s | Wan 2.5 Preview |
| `wan21` | 480p=$0.20/vid, 720p=$0.40/vid | Wan 2.1 |
| `wan22` | 480p=$0.04/s, 720p=$0.08/s | Wan 2.2 A14B |
| `wan-pro` | $0.16/s (1080p) | Wan Pro, premium quality |
| `kling` | $0.35/5s + $0.07/extra sec | Kling 2.5 Turbo Pro |
| `veo2` | $0.50/s (720p only) | Google Veo 2 |
| `veo31-fast` | $0.10/s (no audio) | Google Veo 3.1 Fast |
| `veo31` | $0.20/s (no audio) | Google Veo 3.1 |
| `veo31-flf` | $0.20/s | First/Last Frame (2 images) |
| `veo31-fast-flf` | $0.10/s | First/Last Frame Fast (2 images) |

**Cost examples (5s video):**
- Cheapest: `wan22` 480p = $0.20
- Mid-range: `wan` 1080p = $0.75, `kling` = $0.35
- Premium: `veo2` = $2.50, `veo31` = $1.00

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
