"""Pipeline and production hardening services for i2v.

Production Hardening Components (8 Principles):
    1. Separation of Concerns - JobOrchestrator, JobWorker
    2. Error Classification - ErrorClassifier, ErrorType
    3. State Persistence - CheckpointManager
    4. File-Based Locking - FileLock, JobLock, PipelineLock
    5. Defense in Depth - InputValidator
    6. Retry with Backoff - RetryManager
    7. Flow Logging - FlowLogger
    8. Cooldown and Rate Limiting - CooldownManager, RateLimiter
"""

# Pipeline services
from app.services.prompt_enhancer import PromptEnhancer
from app.services.cost_calculator import CostCalculator
from app.services.pipeline_executor import PipelineExecutor

# Production Hardening - Error Classification
from app.services.error_classifier import (
    ErrorType,
    ErrorClassifier,
    ClassifiedError,
    error_classifier,
)

# Production Hardening - State Persistence
from app.services.checkpoint_manager import (
    CheckpointManager,
    CheckpointEntry,
    job_checkpoint,
    pipeline_checkpoint,
)

# Production Hardening - File Locking
from app.services.file_lock import (
    FileLock,
    JobLock,
    PipelineLock,
    LockAcquisitionError,
    file_lock,
)

# Production Hardening - Retry Logic
from app.services.retry_manager import (
    RetryManager,
    RetryConfig,
    RetryResult,
    retry,
    retry_sync,
    retry_manager,
)

# Production Hardening - Flow Logging
from app.services.flow_logger import (
    FlowLogger,
    JobFlowLogger,
    PipelineFlowLogger,
    flow_log,
    read_flow_log,
)

# Production Hardening - Input Validation
from app.services.input_validator import (
    InputValidator,
    ValidationError,
    ValidationErrorCollection,
    input_validator,
    validate_job_input,
    validate_bulk_pipeline_input,
)

# Production Hardening - Cooldown Management
from app.services.cooldown_manager import (
    CooldownManager,
    CooldownState,
    JobCooldownManager,
    ModelCooldownManager,
    job_cooldown,
    model_cooldown,
    api_cooldown,
)

# Production Hardening - Rate Limiting
from app.services.rate_limiter import (
    SlidingWindowRateLimiter,
    TokenBucketRateLimiter,
    MultiRateLimiter,
    RateLimitExceeded,
    rate_limit,
    rate_limit_sync,
    fal_rate_limiter,
    api_rate_limiter,
)

# Production Hardening - Orchestration
from app.services.job_orchestrator import (
    JobOrchestrator,
    JobResult,
    JobSubmission,
    job_orchestrator,
    submit_job_with_hardening,
    recover_jobs_on_startup,
)

# Production Hardening - Worker
from app.services.job_worker import (
    JobWorker,
    WorkerStats,
    start_worker,
)

__all__ = [
    # Pipeline services
    "PromptEnhancer",
    "CostCalculator",
    "PipelineExecutor",
    # Error Classification
    "ErrorType",
    "ErrorClassifier",
    "ClassifiedError",
    "error_classifier",
    # Checkpoint/State
    "CheckpointManager",
    "CheckpointEntry",
    "job_checkpoint",
    "pipeline_checkpoint",
    # File Locking
    "FileLock",
    "JobLock",
    "PipelineLock",
    "LockAcquisitionError",
    "file_lock",
    # Retry Logic
    "RetryManager",
    "RetryConfig",
    "RetryResult",
    "retry",
    "retry_sync",
    "retry_manager",
    # Flow Logging
    "FlowLogger",
    "JobFlowLogger",
    "PipelineFlowLogger",
    "flow_log",
    "read_flow_log",
    # Input Validation
    "InputValidator",
    "ValidationError",
    "ValidationErrorCollection",
    "input_validator",
    "validate_job_input",
    "validate_bulk_pipeline_input",
    # Cooldown
    "CooldownManager",
    "CooldownState",
    "JobCooldownManager",
    "ModelCooldownManager",
    "job_cooldown",
    "model_cooldown",
    "api_cooldown",
    # Rate Limiting
    "SlidingWindowRateLimiter",
    "TokenBucketRateLimiter",
    "MultiRateLimiter",
    "RateLimitExceeded",
    "rate_limit",
    "rate_limit_sync",
    "fal_rate_limiter",
    "api_rate_limiter",
    # Orchestration
    "JobOrchestrator",
    "JobResult",
    "JobSubmission",
    "job_orchestrator",
    "submit_job_with_hardening",
    "recover_jobs_on_startup",
    # Worker
    "JobWorker",
    "WorkerStats",
    "start_worker",
]
