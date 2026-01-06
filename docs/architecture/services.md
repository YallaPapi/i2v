# Services Architecture

## Service Layer

```
app/services/
├── job_orchestrator.py    # Job lifecycle management
├── pipeline_executor.py   # Pipeline step execution
├── generation_service.py  # Video generation logic
├── rate_limiter.py        # API rate limiting
├── retry_manager.py       # Retry logic with backoff
├── r2_cache.py           # R2 CDN caching
├── thumbnail.py          # Thumbnail generation
├── cost_calculator.py    # Usage cost tracking
└── error_classifier.py   # Error categorization
```

## Job Orchestrator

Manages the complete job lifecycle:

- Job creation and queuing
- Status transitions
- Completion handling
- Error recovery

## Pipeline Executor

Executes pipeline steps:

- Step sequencing
- Input/output handling
- Progress tracking

## Rate Limiter

Prevents Fal.ai quota exhaustion:

- Per-model rate limits
- Token bucket algorithm
- Queue management

## Retry Manager

Handles transient failures:

- Exponential backoff
- Configurable retry counts
- Error classification

## R2 Cache

CDN caching for fast delivery:

- Image caching
- Video caching
- Thumbnail generation
