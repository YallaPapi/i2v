# Architecture Overview

> **Note:** For comprehensive architecture documentation, see [../ARCHITECTURE.md](../ARCHITECTURE.md)

## System Architecture

```mermaid
graph TB
    subgraph Frontend
        A[React App]
    end

    subgraph Backend
        B[FastAPI]
        C[Job Orchestrator]
        D[Pipeline Executor]
        E[Rate Limiter]
        I[GPU Config]
    end

    subgraph CloudAPI[Cloud API]
        F[Fal.ai API]
    end

    subgraph SelfHosted[Self-Hosted GPU]
        J[vast.ai Instance]
        K[SwarmUI]
    end

    subgraph Storage
        G[Cloudflare R2]
        H[(SQLite DB)]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    D --> I
    I --> K
    J --> K
    F --> G
    K --> G
    B --> H
    G --> A
```

## Components

### Frontend (React + TypeScript + Vite)

- Playground UI for generation
- Job management
- Template management
- Real-time status updates

### Backend (FastAPI)

- RESTful API endpoints
- Async job processing
- Database management
- GPU configuration

### Services

- **Job Orchestrator**: Manages job lifecycle
- **Pipeline Executor**: Runs generation steps
- **Rate Limiter**: Prevents API quota exhaustion
- **R2 Cache**: CDN caching for outputs
- **SwarmUI Client**: Self-hosted GPU video generation
- **Vast.ai Client**: GPU instance management

## Data Flow

### Cloud Generation (Fal.ai)

1. User creates pipeline via frontend
2. Backend stores pipeline in SQLite
3. User triggers pipeline run
4. Job Orchestrator queues the job
5. Pipeline Executor calls Fal.ai
6. Results cached to R2 CDN
7. Frontend displays completed video

### Self-Hosted GPU Generation (SwarmUI on Vast.ai)

1. User selects "Wan 2.2 (GPU)" model in frontend
2. Frontend calls `/api/swarm/generate-video`
3. Backend checks runtime GPU config (set via `/api/gpu/config`)
4. If configured, uses SwarmUI REST API via tunnel URL
5. SwarmUI executes Wan 2.2 I2V with LightX2V 4-step LoRA
6. Generated video cached to R2
7. Video URL returned to frontend

**Important:** Vast.ai instances use Cloudflare tunnels. The tunnel URL must be obtained from the vast.ai console and configured via `/api/gpu/config`. See [GPU Setup Guide](../GPU_SETUP.md).

## GPU Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GPU Config System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   /api/gpu/config                                                │
│       │                                                          │
│       ├── swarmui_url: SwarmUI tunnel URL (primary)             │
│       ├── comfyui_url: ComfyUI URL (legacy, deprecated)         │
│       ├── gpu_provider: "none" | "local" | "vastai"             │
│       └── vastai_instance_id: Active instance ID                │
│                                                                  │
│   Runtime Config (in-memory)                                    │
│       │                                                          │
│       └── Used by /api/swarm/generate-video endpoint            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `app/routers/gpu_config.py` | Runtime GPU URL configuration API |
| `app/routers/swarmui.py` | SwarmUI video generation endpoints |
| `app/routers/vastai.py` | Vast.ai instance management |
| `app/services/swarmui_client.py` | SwarmUI REST API client |
| `app/services/vastai_client.py` | Vast.ai API client |
| `app/services/comfyui_workflows.py` | Legacy ComfyUI workflows (deprecated) |

### Supported Models

| Model | Backend | Notes |
|-------|---------|-------|
| Wan 2.2 (GPU) | SwarmUI on vast.ai | Self-hosted, ~$0.50-1.50/hr |
| Wan 2.5/2.6 | Fal.ai | Cloud, $0.05-0.15/s |
| Kling | Fal.ai | Cloud, $0.35/5s |
| Veo 2/3.1 | Fal.ai | Cloud, $0.20-0.50/s |
| Sora 2 | Fal.ai | Cloud, $0.10-0.30/s |
| Luma Ray2 | Fal.ai | Cloud, $0.05/s |

## Related Documentation

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Comprehensive system documentation
- [BACKENDS.md](../BACKENDS.md) - Backend client details
- [ROADMAP.md](../ROADMAP.md) - Development priorities
- [GPU_SETUP.md](../GPU_SETUP.md) - GPU setup guide
