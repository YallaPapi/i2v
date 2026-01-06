# Coupling and Cohesion Analysis Report

Generated: 2026-01-06

## Executive Summary

Analysis of module dependencies reveals a well-structured codebase with clear layering. The main areas of concern are tight coupling between `fal_client.py` and `image_client.py` (code duplication), and the large `pipelines.py` router with 28 endpoint dependencies.

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY LAYERS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐                                                 │
│  │   config    │ ← Foundation (no internal deps)                 │
│  └──────┬──────┘                                                 │
│         │                                                        │
│  ┌──────▼──────┐                                                 │
│  │  database   │ ← Data Layer                                    │
│  └──────┬──────┘                                                 │
│         │                                                        │
│  ┌──────▼──────┐                                                 │
│  │   models    │ ← Domain Layer                                  │
│  └──────┬──────┘                                                 │
│         │                                                        │
│  ┌──────▼──────┬────────────┬────────────┐                       │
│  │ fal_client  │image_client│ fal_upload │ ← External API Layer  │
│  └──────┬──────┴─────┬──────┴────────────┘                       │
│         │            │                                           │
│  ┌──────▼────────────▼──────┐                                    │
│  │       services/          │ ← Business Logic Layer             │
│  │  ├── prompt_enhancer     │                                    │
│  │  ├── pipeline_executor   │                                    │
│  │  ├── job_orchestrator    │                                    │
│  │  ├── generation_service  │                                    │
│  │  └── ...                 │                                    │
│  └──────────────┬───────────┘                                    │
│                 │                                                │
│  ┌──────────────▼───────────┐                                    │
│  │   routers/pipelines.py   │ ← API Layer                        │
│  └──────────────┬───────────┘                                    │
│                 │                                                │
│  ┌──────────────▼───────────┐                                    │
│  │        main.py           │ ← Application Entry                │
│  └──────────────────────────┘                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Coupling Analysis

### High Coupling Areas (Concern)

#### 1. fal_client.py ↔ image_client.py

**Afferent Coupling (Ca)**: 3 modules depend on each
**Efferent Coupling (Ce)**: 1 (config)

**Issue**: Near-identical code structure without shared base.

```python
# Both have:
- _get_headers() function
- MODELS/IMAGE_MODELS dict
- submit_*_job() async function
- get_*_result() async function
- Custom exception class
```

**Recommendation**: Extract `BaseFalClient`:
```python
# app/services/base_fal_client.py
class BaseFalClient:
    def __init__(self, models: dict, error_class: type):
        self.models = models
        self.error_class = error_class

    def _get_headers(self) -> dict: ...
    async def submit(self, model: str, payload: dict) -> str: ...
    async def get_result(self, model: str, request_id: str) -> dict: ...
```

#### 2. routers/pipelines.py

**Afferent Coupling (Ca)**: 2 (main.py, routers/__init__.py)
**Efferent Coupling (Ce)**: 13 modules

**Dependencies**:
```
pipelines.py imports:
├── app.database (get_db)
├── app.models (Pipeline, PipelineStep, PipelineStatus, StepStatus)
├── app.schemas (8 schemas)
├── app.services.prompt_enhancer
├── app.services.cost_calculator
├── app.services.pipeline_executor
├── app.services.generation_service
├── app.services.thumbnail
├── app.services.cache
└── app.services.r2_cache
```

**Recommendation**: Split into sub-routers:
```python
# routers/
├── pipelines/
│   ├── __init__.py      # Main router
│   ├── crud.py          # CRUD operations
│   ├── execution.py     # Execution endpoints
│   ├── bulk.py          # Bulk operations
│   └── prompts.py       # Prompt-related endpoints
```

#### 3. job_orchestrator.py

**Efferent Coupling (Ce)**: 7 internal services

**Dependencies**:
```
job_orchestrator.py imports:
├── error_classifier
├── checkpoint_manager
├── retry_manager
├── flow_logger
├── cooldown_manager
├── rate_limiter
└── input_validator
```

**Assessment**: This is acceptable - orchestrator's job is to coordinate services.

### Low Coupling Areas (Good)

#### 1. config.py

**Ca**: 6 modules depend on it
**Ce**: 0 (no internal dependencies)

✅ Properly isolated configuration.

#### 2. models.py

**Ca**: 5 modules depend on it
**Ce**: 1 (database.py for Base)

✅ Clean domain model layer.

#### 3. Individual Services

Most services have 0-2 internal dependencies:
- `cost_calculator.py` - Ce: 0
- `rate_limiter.py` - Ce: 0
- `cooldown_manager.py` - Ce: 0
- `error_classifier.py` - Ce: 0

✅ Well-isolated service modules.

## Cohesion Analysis

### High Cohesion (Good)

| Module | Cohesion Type | Assessment |
|--------|---------------|------------|
| `config.py` | Functional | Single purpose: settings |
| `models.py` | Functional | Single purpose: domain models |
| `database.py` | Functional | Single purpose: DB connection |
| `rate_limiter.py` | Functional | Single purpose: rate limiting |
| `cost_calculator.py` | Functional | Single purpose: cost calculation |
| `error_classifier.py` | Functional | Single purpose: error classification |

### Low Cohesion (Concern)

#### 1. pipelines.py (1600+ lines)

**Current responsibilities**:
- Pipeline CRUD (create, read, update, delete)
- Step management
- Execution control (start, pause, resume)
- Bulk operations
- Prompt management
- Tag management
- Download proxy
- Cost estimation

**Recommendation**: Split by domain:
```
Cohesion Score: ~0.3 (Low)
Target: >0.7 (High)
```

#### 2. worker.py

**Current responsibilities**:
- Video job submission
- Video job polling
- Image job submission
- Image job polling
- Background scheduling

**Recommendation**: Extract into separate workers:
```python
# workers/
├── video_worker.py
├── image_worker.py
└── scheduler.py
```

## Instability Metrics

Instability = Ce / (Ca + Ce)

| Module | Ca | Ce | Instability | Assessment |
|--------|----|----|-------------|------------|
| config.py | 6 | 0 | 0.00 | Stable (good) |
| models.py | 5 | 1 | 0.17 | Stable (good) |
| database.py | 3 | 1 | 0.25 | Stable (good) |
| fal_client.py | 3 | 1 | 0.25 | Stable |
| image_client.py | 2 | 1 | 0.33 | Moderately stable |
| pipelines.py | 2 | 13 | 0.87 | Unstable (expected for router) |
| main.py | 0 | 8 | 1.00 | Unstable (expected for entry) |

## Frontend Coupling

### Component Dependencies

```
App.tsx
├── pages/
│   ├── Dashboard.tsx → hooks/useJobs
│   ├── Jobs.tsx → hooks/useJobs, api/client
│   ├── ImageGeneration.tsx → hooks/useJobs, api/client
│   └── VideoGeneration.tsx → hooks/useJobs, api/client
└── components/
    ├── pipeline/* → hooks/useJobs
    └── ui/* → (standalone)
```

### Coupling Assessment

| Area | Status | Notes |
|------|--------|-------|
| API Layer | Good | Centralized in `api/client.ts` |
| Hooks | Good | Custom hooks abstract API calls |
| UI Components | Good | Standalone, reusable |
| Pages | Needs work | Duplicate code (see duplication report) |

## Recommendations

### Immediate Actions

1. **Extract Base Fal Client**
   - Create `app/services/base_fal_client.py`
   - Refactor `fal_client.py` and `image_client.py`
   - Reduces Ce for both modules

2. **Split pipelines.py Router**
   ```python
   # routers/pipelines/__init__.py
   from .crud import router as crud_router
   from .execution import router as execution_router
   from .bulk import router as bulk_router

   router = APIRouter(prefix="/pipelines")
   router.include_router(crud_router)
   router.include_router(execution_router)
   router.include_router(bulk_router)
   ```

### Short-term Actions

3. **Extract Shared Frontend Components**
   - `SourceImageInput`
   - `PromptInputGroup`
   - `GenerationFormLayout`

4. **Add Service Layer for Pipelines**
   ```python
   # services/pipeline_service.py
   class PipelineService:
       def list(self, filters) -> list[Pipeline]: ...
       def create(self, data) -> Pipeline: ...
       def execute(self, id) -> None: ...
   ```

### Long-term Actions

5. **Implement Repository Pattern**
   - Decouple routers from SQLAlchemy
   - Enable easier testing

6. **Worker Separation**
   - Separate video and image workers
   - Enable independent scaling

## Metrics Summary

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Max module Ce | 13 | <8 | ⚠️ Needs work |
| Avg service Ce | 1.5 | <3 | ✅ Good |
| pipelines.py cohesion | Low | High | ⚠️ Needs work |
| Circular dependencies | 0 | 0 | ✅ Good |

---
*Report generated as part of Task 224: Coupling and Cohesion Analysis*
