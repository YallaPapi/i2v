# Design Pattern Identification Report

Generated: 2026-01-06

## Executive Summary

The i2v codebase employs several well-known design patterns that contribute to its maintainability and extensibility. This report identifies and documents these patterns with implementation details.

## Creational Patterns

### 1. Singleton Pattern

**Usage**: Module-level singleton instances for stateful services.

**Locations**:
- `app/services/cost_calculator.py:233` - `cost_calculator`
- `app/services/prompt_enhancer.py:381` - `prompt_enhancer`
- `app/services/pipeline_executor.py:586` - `pipeline_executor`
- `app/services/job_orchestrator.py:533` - `job_orchestrator`
- `app/services/error_classifier.py:248` - `error_classifier`
- `app/services/input_validator.py:808` - `input_validator`
- `app/services/retry_manager.py:296` - `retry_manager`
- `app/services/checkpoint_manager.py:503` - `jobs_checkpoint_manager`
- `app/services/cooldown_manager.py:470` - `model_cooldown`, `job_cooldown`

**Implementation**:
```python
# Module-level singleton
class CostCalculator:
    def __init__(self):
        ...

# Singleton instance
cost_calculator = CostCalculator()
```

**Benefits**:
- Shared state across application
- Lazy initialization
- Easy to import and use

**Consideration**: Python module-level singletons are thread-safe for reads but may need locking for writes.

### 2. Factory Pattern (Implicit)

**Usage**: Configuration-driven object creation via dictionaries.

**Locations**:
- `app/fal_client.py:17` - `MODELS` dictionary
- `app/image_client.py:19` - `IMAGE_MODELS` dictionary

**Implementation**:
```python
MODELS = {
    "kling": {
        "submit_url": "https://queue.fal.run/fal-ai/kling-video/v1.5/pro/image-to-video",
        "status_url": "https://queue.fal.run/fal-ai/kling-video/v1.5/pro/image-to-video",
    },
    "minimax": { ... },
    "wan": { ... },
}

# Factory-like usage
config = MODELS[model]
url = config["submit_url"]
```

**Benefits**:
- Easy to add new models
- Configuration-driven behavior
- No subclass explosion

### 3. Builder Pattern (Data Classes)

**Usage**: Structured construction of complex objects.

**Locations**:
- `app/services/job_orchestrator.py:53` - `JobSubmission`
- `app/services/job_orchestrator.py:66` - `JobResult`
- `app/services/checkpoint_manager.py:60` - `CheckpointEntry`

**Implementation**:
```python
@dataclass
class JobSubmission:
    model: str
    image_url: str
    motion_prompt: str
    resolution: str
    duration_sec: int
    negative_prompt: Optional[str] = None
    enable_audio: bool = False
```

**Benefits**:
- Clear parameter documentation
- Default values
- Type safety

## Structural Patterns

### 4. Facade Pattern

**Usage**: JobOrchestrator provides simplified interface to complex subsystem.

**Location**: `app/services/job_orchestrator.py`

**Architecture**:
```
JobOrchestrator (Facade)
    ├── Worker (execution)
    ├── CheckpointManager (state)
    ├── RetryManager (resilience)
    ├── FlowLogger (observability)
    ├── CooldownManager (failure tracking)
    ├── RateLimiter (API protection)
    ├── ErrorClassifier (error handling)
    └── InputValidator (validation)
```

**Implementation**:
```python
class JobOrchestrator:
    def __init__(self):
        self.checkpoint_manager = CheckpointManager("jobs")
        self.retry_manager = RetryManager()
        self.flow_logger = JobFlowLogger("orchestrator")
        self.cooldown_manager = JobCooldownManager()
        self.rate_limiter = SlidingWindowRateLimiter(max_per_minute=60)
        self.input_validator = InputValidator()

    async def submit_job(self, ...):
        # Coordinates all subsystems
        self.input_validator.validate(...)
        await self.rate_limiter.acquire()
        result = await self.retry_manager.with_retry(...)
        self.checkpoint_manager.write(...)
```

**Benefits**:
- Simplified client interface
- Hides complexity
- Single entry point for job operations

### 5. Adapter Pattern

**Usage**: Fal API response mapping to internal status.

**Location**: `app/fal_client.py:317-325`

**Implementation**:
```python
# Map Fal statuses to internal statuses
fal_status = data.get("status", "").upper()
status_map = {
    "IN_QUEUE": "pending",
    "IN_PROGRESS": "running",
    "COMPLETED": "completed",
    "FAILED": "failed",
}
status = status_map.get(fal_status, "pending")
```

**Benefits**:
- Decouples external API from internal representation
- Easy to change external provider
- Consistent internal status handling

### 6. Composite Pattern (Implicit)

**Usage**: Pipeline composed of steps.

**Location**: `app/models.py` - Pipeline/PipelineStep relationship

**Implementation**:
```python
class Pipeline(Base):
    steps = relationship(
        "PipelineStep",
        back_populates="pipeline",
        order_by="PipelineStep.step_order",
        cascade="all, delete-orphan",
    )

class PipelineStep(Base):
    pipeline_id = Column(Integer, ForeignKey("pipelines.id"))
    pipeline = relationship("Pipeline", back_populates="steps")
```

**Benefits**:
- Treat individual steps and pipeline uniformly
- Recursive structure for complex workflows
- Cascading operations

## Behavioral Patterns

### 7. Strategy Pattern

**Usage**: Different generation strategies (video vs image).

**Locations**:
- `app/fal_client.py` - Video generation
- `app/image_client.py` - Image generation

**Implementation**:
```python
# Strategy selection based on step type
if step.step_type == StepType.I2V:
    result = await fal_client.submit_job(...)
elif step.step_type == StepType.I2I:
    result = await image_client.submit_image_job(...)
```

**Recommendation**: Extract common interface:
```python
class GenerationStrategy(Protocol):
    async def submit(self, config: dict) -> str: ...
    async def get_result(self, request_id: str) -> dict: ...

class VideoGenerationStrategy(GenerationStrategy): ...
class ImageGenerationStrategy(GenerationStrategy): ...
```

### 8. Template Method Pattern

**Usage**: Retry logic with customizable behavior.

**Location**: `app/services/retry_manager.py`

**Implementation**:
```python
class RetryManager:
    async def with_retry(self, operation, config=None):
        for attempt in range(max_attempts):
            try:
                return await operation()
            except Exception as e:
                if not self._should_retry(e, attempt):
                    raise
                delay = self._calculate_delay(attempt, config)
                await asyncio.sleep(delay)
```

**Benefits**:
- Reusable retry logic
- Customizable via config
- Consistent error handling

### 9. Observer Pattern (Implicit)

**Usage**: WebSocket updates for pipeline status.

**Location**: `app/services/pipeline_executor.py`

**Implementation**:
```python
class PipelineExecutor:
    async def _broadcast_update(self, pipeline_id: int, data: dict):
        if self.websocket_callback:
            await self.websocket_callback(pipeline_id, data)
```

**Benefits**:
- Decoupled status updates
- Real-time UI updates
- Multiple observers possible

### 10. State Pattern (Implicit)

**Usage**: Job status transitions.

**Locations**:
- `app/models.py` - PipelineStatus, StepStatus enums
- `app/worker.py` - Status transitions

**Implementation**:
```python
class PipelineStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
```

**State Transitions**:
```
PENDING → RUNNING → COMPLETED
    ↓         ↓
  FAILED    PAUSED → RUNNING
```

### 11. Chain of Responsibility

**Usage**: Input validation chain.

**Location**: `app/services/input_validator.py`

**Implementation**:
```python
class InputValidator:
    def validate_video_job(self, ...):
        self._validate_url(image_url)
        self._validate_prompt(motion_prompt)
        self._validate_model(model)
        self._validate_resolution(resolution)
        self._validate_duration(duration_sec)
```

**Benefits**:
- Sequential validation
- Early exit on failure
- Composable validators

## Pattern Distribution

| Pattern | Category | Count | Locations |
|---------|----------|-------|-----------|
| Singleton | Creational | 9 | services/*.py |
| Factory | Creational | 2 | fal_client, image_client |
| Builder | Creational | 3 | dataclasses |
| Facade | Structural | 1 | job_orchestrator |
| Adapter | Structural | 2 | status mapping |
| Composite | Structural | 1 | Pipeline/Steps |
| Strategy | Behavioral | 2 | generation clients |
| Template Method | Behavioral | 1 | retry_manager |
| Observer | Behavioral | 1 | WebSocket updates |
| State | Behavioral | 2 | status enums |
| Chain of Responsibility | Behavioral | 1 | input_validator |

## Recommendations

### 1. Formalize Strategy Pattern

Extract common client interface:
```python
# app/services/generation_strategy.py
from abc import ABC, abstractmethod

class GenerationStrategy(ABC):
    @abstractmethod
    async def submit(self, config: dict) -> str: ...

    @abstractmethod
    async def get_result(self, request_id: str) -> dict: ...

class VideoStrategy(GenerationStrategy): ...
class ImageStrategy(GenerationStrategy): ...
```

### 2. Add Repository Pattern

For database operations:
```python
# app/repositories/pipeline_repository.py
class PipelineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: int) -> Pipeline | None: ...
    def list_with_filters(self, filters: dict) -> list[Pipeline]: ...
    def create(self, data: PipelineCreate) -> Pipeline: ...
```

### 3. Implement Unit of Work

For transaction management:
```python
class UnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()
        return self

    async def __aexit__(self, *args):
        await self.session.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()
```

## Extensibility Benefits

The current pattern usage provides:

1. **Easy model addition**: Add to MODELS/IMAGE_MODELS dict
2. **New step types**: Add enum value and strategy
3. **Custom retry logic**: Configure RetryConfig
4. **Additional validation**: Extend InputValidator
5. **Alternative storage**: Implement Repository interface

---
*Report generated as part of Task 223: Design Pattern Identification*
