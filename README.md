# i2v - AI Image-to-Video Generation Platform

Full-stack platform for AI-powered video and image generation with multiple backend support.

## Features

- **Multi-model video generation:** Wan, Kling, Veo, Sora, Luma, CogVideoX
- **Multi-model image generation:** GPT-Image, Kling, Nano-Banana, Flux
- **Dual backend architecture:**
  - **fal.ai** - Cloud API (production, 20+ models)
  - **SwarmUI on Vast.ai** - Self-hosted GPU (bulk generation, NSFW support)
- **R2 caching** - Fast image/video delivery via Cloudflare CDN
- **Batch processing** - Process entire folders with multiple prompts
- **REST API** - Full job management via FastAPI
- **React frontend** - Playground, Jobs, Templates UI

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd i2v

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env - add FAL_API_KEY at minimum

# Run backend
uvicorn app.main:app --reload

# Run worker (separate terminal)
python -m app.worker

# Run frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Vite)                          │
│  Playground | VideoGeneration | Jobs | Templates                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                  │
│  /api/pipelines/* | /api/swarm/* | /api/vastai/* | /api/gpu/*          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌───────────┐   ┌───────────────┐   ┌─────────┐
             │  FAL.AI   │   │ SWARMUI/VAST  │   │   R2    │
             │  (Cloud)  │   │    (GPU)      │   │  (CDN)  │
             └───────────┘   └───────────────┘   └─────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed documentation.

## Environment Variables

### Required
```env
FAL_API_KEY=xxx                    # fal.ai API key
```

### GPU Backend (Optional - for Vast.ai)
```env
VASTAI_API_KEY=xxx                 # Vast.ai API key
SWARMUI_URL=http://localhost:7801  # SwarmUI URL
GPU_PROVIDER=none                  # "none" | "local" | "vastai"
```

### Storage (R2 - Optional but recommended)
```env
R2_ACCOUNT_ID=xxx
R2_BUCKET_NAME=i2v
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_PUBLIC_DOMAIN=pub-xxx.r2.dev
```

### Other
```env
ANTHROPIC_API_KEY=xxx              # For prompt enhancement
DATABASE_URL=postgresql://...      # Optional, SQLite by default
```

## Video Models & Pricing (fal.ai)

| Model | Cost | Duration | Best For |
|-------|------|----------|----------|
| `wan22` | $0.04-0.08/s | 5-10s | Budget |
| `wan` | $0.05-0.15/s | 5-10s | General |
| `kling` | $0.35/5s | 5-10s | Best quality/price |
| `kling-master` | $1.40/5s | 5-10s | Highest quality |
| `veo31` | $0.20-0.40/s | 4-8s | Google + audio |
| `sora-2` | $0.10/s | 4-12s | OpenAI |
| `luma-ray2` | $0.05/s | 5-9s | Fast |

### GPU Backend (SwarmUI on Vast.ai)

| Setup | Cost | Notes |
|-------|------|-------|
| RTX 4090 | ~$0.50/hr | Good for single videos |
| RTX 5090 | ~$1.00/hr | Fast bulk generation |
| A100 | ~$1.50/hr | Maximum throughput |

**When to use GPU:** Bulk generation (10+ videos), NSFW content, custom models.

## API Endpoints

### Video Generation
```bash
# Cloud generation (fal.ai)
curl -X POST http://localhost:8000/api/pipelines/run \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://...",
    "motion_prompt": "camera zooms in",
    "model": "kling",
    "resolution": "720p",
    "duration_sec": 5
  }'

# GPU generation (SwarmUI)
curl -X POST http://localhost:8000/api/swarm/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://...",
    "prompt": "camera zooms in",
    "num_frames": 81,
    "steps": 4
  }'
```

### GPU Management
```bash
# Get GPU config
curl http://localhost:8000/api/gpu/config

# Set SwarmUI URL (after getting from Vast.ai)
curl -X POST http://localhost:8000/api/gpu/config \
  -H "Content-Type: application/json" \
  -d '{"swarmui_url": "https://abc.trycloudflare.com"}'

# Health check
curl http://localhost:8000/api/gpu/health
```

### Vast.ai
```bash
# List instances
curl http://localhost:8000/api/vastai/instances

# Create SwarmUI instance
curl -X POST http://localhost:8000/api/vastai/swarmui/instances \
  -H "Content-Type: application/json" \
  -d '{"max_price": 1.50}'

# Destroy instance
curl -X DELETE http://localhost:8000/api/vastai/instances/{id}
```

## Project Structure

```
i2v/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Environment settings
│   ├── fal_client.py        # fal.ai video client
│   ├── image_client.py      # fal.ai image client
│   ├── worker.py            # Background worker
│   ├── routers/
│   │   ├── pipelines.py     # Pipeline endpoints
│   │   ├── swarmui.py       # SwarmUI endpoints
│   │   ├── vastai.py        # Vast.ai endpoints
│   │   └── gpu_config.py    # GPU config
│   └── services/
│       ├── swarmui_client.py   # SwarmUI client
│       ├── vastai_client.py    # Vast.ai client
│       ├── r2_cache.py         # R2 caching
│       └── ...
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Playground.tsx
│       │   ├── VideoGeneration.tsx
│       │   └── Jobs.tsx
│       └── ...
├── docker/
│   └── Dockerfile.swarmui   # Custom SwarmUI image
├── docs/
│   ├── ARCHITECTURE.md      # System architecture
│   ├── BACKENDS.md          # Backend documentation
│   ├── ROADMAP.md           # Development roadmap
│   └── GPU_SETUP.md         # GPU setup guide
├── scripts/
│   ├── bulk_generate.py     # Bulk generation script
│   └── download_models.sh   # Model download
├── CLAUDE.md                # AI agent instructions
├── requirements.txt
└── docker-compose.yml
```

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flow, key components |
| [BACKENDS.md](docs/BACKENDS.md) | Detailed backend client documentation |
| [ROADMAP.md](docs/ROADMAP.md) | Strategic direction, priorities, technical debt |
| [GPU_SETUP.md](docs/GPU_SETUP.md) | GPU setup guide for Vast.ai |
| [CLAUDE.md](CLAUDE.md) | AI agent instructions for development |

## Bulk Generation

```bash
# All combinations (3 images x 4 prompts = 12 videos)
python scripts/bulk_generate.py prompts.txt --images-dir ./images --model kling

# One-to-one pairing
python scripts/bulk_generate.py prompts.txt --images-dir ./images --one-to-one

# Dry run
python scripts/bulk_generate.py prompts.txt --images-dir ./images --dry-run
```

## Running Tests

```bash
pytest tests/ -v
```

## Development

### Adding a New Video Model

1. Add to `MODELS` dict in `app/fal_client.py`
2. Add to `ModelType` literal type
3. Add payload builder in `_build_payload()` if needed
4. Update frontend model selector

### GPU Development Flow

1. Start Vast.ai instance: `POST /api/vastai/swarmui/instances`
2. Wait for ready (~3-5 min)
3. Get tunnel URL from Vast.ai console
4. Set URL: `POST /api/gpu/config`
5. Generate: `POST /api/swarm/generate-video`
6. Destroy when done: `DELETE /api/vastai/instances/{id}`

## License

MIT

## Contributing

1. Read [CLAUDE.md](CLAUDE.md) for project context
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system overview
3. Check [docs/ROADMAP.md](docs/ROADMAP.md) for priorities
4. Submit PRs to `master` branch
