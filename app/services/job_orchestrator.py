"""Job orchestration with production hardening.

Principle 1: Separation of Concerns
Orchestrator coordinates. Workers execute. Logger observes.
Each component has ONE job.

Architecture:
    JobOrchestrator (coordination)
        ├── Worker (execution via fal_client)
        ├── CheckpointManager (state persistence)
        ├── RetryManager (resilience)
        ├── FlowLogger (observability)
        ├── CooldownManager (failure tracking)
        ├── RateLimiter (API protection)
        ├── ErrorClassifier (intelligent error handling)
        └── InputValidator (defense in depth)

Usage:
    orchestrator = JobOrchestrator()

    # Submit and process a job
    result = await orchestrator.submit_job(
        model="kling",
        image_url="https://...",
        motion_prompt="A gentle breeze...",
        resolution="1080p",
        duration_sec=5,
    )

    # Process pending jobs from database
    processed = await orchestrator.process_pending_jobs(limit=5)

    # Recover interrupted jobs on startup
    recovered = await orchestrator.recover_interrupted_jobs()
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import structlog

from app.services.error_classifier import ErrorClassifier, ErrorType, ClassifiedError, error_classifier
from app.services.checkpoint_manager import CheckpointManager
from app.services.retry_manager import RetryManager, RetryConfig, RetryResult
from app.services.flow_logger import FlowLogger, JobFlowLogger
from app.services.cooldown_manager import CooldownManager, JobCooldownManager
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.services.file_lock import FileLock, JobLock
from app.services.input_validator import InputValidator, ValidationError

logger = structlog.get_logger()


@dataclass
class JobSubmission:
    """A job submission request."""
    model: str
    image_url: str
    motion_prompt: str
    resolution: str
    duration_sec: int
    negative_prompt: Optional[str] = None
    enable_audio: bool = False


@dataclass
class JobResult:
    """Result of job processing."""
    job_id: str
    success: bool
    request_id: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[ErrorType] = None
    attempts: int = 0
    total_time_seconds: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)


class JobOrchestrator:
    """
    Production-hardened job orchestrator.

    Coordinates job processing with:
    - State persistence for crash recovery
    - Intelligent retry with exponential backoff
    - Error classification for proper handling
    - Flow logging for debugging
    - Cooldown for repeatedly failing jobs
    - Rate limiting for API protection
    - File locking for safe concurrency

    Attributes:
        checkpoint: CheckpointManager for state persistence
        retry_manager: RetryManager for intelligent retries
        cooldown: CooldownManager for failure tracking
        rate_limiter: Rate limiter for API protection
        validator: InputValidator for defense-in-depth
    """

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        rate_limit_per_minute: int = 60,
        enable_validation: bool = True,
    ):
        """
        Initialize the job orchestrator.

        Args:
            checkpoint_dir: Directory for checkpoint files
            rate_limit_per_minute: API rate limit
            enable_validation: Whether to enable input validation
        """
        # Core components
        self.checkpoint = CheckpointManager("jobs", checkpoint_dir=checkpoint_dir)
        self.retry_manager = RetryManager()
        self.classifier = error_classifier
        self.cooldown = JobCooldownManager()
        self.rate_limiter = SlidingWindowRateLimiter(max_per_minute=rate_limit_per_minute)
        self.validator = InputValidator() if enable_validation else None

        # Configuration
        self.enable_validation = enable_validation

        # Stats
        self._stats = {
            "jobs_submitted": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_retries": 0,
            "total_errors": 0,
        }

        logger.info(
            "JobOrchestrator initialized",
            checkpoint_dir=checkpoint_dir,
            rate_limit=rate_limit_per_minute,
        )

    async def submit_job(
        self,
        model: str,
        image_url: str,
        motion_prompt: str,
        resolution: str,
        duration_sec: int,
        negative_prompt: Optional[str] = None,
        enable_audio: bool = False,
        job_id: Optional[str] = None,
    ) -> JobResult:
        """
        Submit and process a video generation job.

        This is the main entry point for job processing. It:
        1. Validates input (defense in depth)
        2. Creates checkpoint (state persistence)
        3. Acquires rate limit slot
        4. Submits to Fal API with retry
        5. Logs flow for debugging
        6. Updates checkpoint on completion

        Args:
            model: Video model to use
            image_url: Source image URL
            motion_prompt: Motion description
            resolution: Output resolution
            duration_sec: Video duration
            negative_prompt: Optional negative prompt
            enable_audio: Enable audio (Veo 3.1 only)
            job_id: Optional job ID (generates UUID if not provided)

        Returns:
            JobResult with success/failure status and details
        """
        import uuid
        from time import time

        start_time = time()
        job_id = job_id or str(uuid.uuid4())

        # Create flow logger for this job
        flow = JobFlowLogger(job_id, model=model)
        flow.start()

        result = JobResult(
            job_id=job_id,
            success=False,
            context={"model": model, "resolution": resolution},
        )

        try:
            # Step 1: Validate input (defense in depth)
            if self.validator:
                flow.log_step("validate", "validating")
                try:
                    self.validator.validate_image_url(image_url)
                    self.validator.validate_prompt(motion_prompt)
                    self.validator.validate_model_resolution(model, resolution)
                    self.validator.validate_model_duration(model, duration_sec)
                except ValidationError as e:
                    flow.log_error(e, error_type="ValidationError")
                    result.error_message = str(e)
                    result.error_type = ErrorType.INVALID_INPUT
                    return result

            # Step 2: Check cooldown
            if not self.cooldown.should_process_job(job_id):
                flow.log_step("cooldown_check", "in_cooldown")
                result.error_message = "Job is in cooldown period"
                result.error_type = ErrorType.TRANSIENT
                return result

            # Step 3: Write checkpoint (before processing)
            flow.log_step("checkpoint", "writing")
            self.checkpoint.write(
                id=job_id,
                status="started",
                model=model,
                image_url=image_url,
                prompt=motion_prompt,
                resolution=resolution,
            )

            # Step 4: Acquire rate limit slot
            flow.log_step("rate_limit", "acquiring")
            if not await self.rate_limiter.acquire(timeout=30.0):
                flow.log_step("rate_limit", "timeout")
                result.error_message = "Rate limit timeout"
                result.error_type = ErrorType.RATE_LIMIT
                return result

            # Step 5: Submit job with retry
            flow.log_step("submit", "submitting")

            async def submit_operation():
                from app.fal_client import submit_job
                return await submit_job(
                    model=model,
                    image_url=image_url,
                    motion_prompt=motion_prompt,
                    resolution=resolution,
                    duration_sec=duration_sec,
                    negative_prompt=negative_prompt,
                    enable_audio=enable_audio,
                )

            retry_config = RetryConfig(
                max_attempts=3,
                base_delay_seconds=2.0,
                retryable_errors={ErrorType.NETWORK, ErrorType.TRANSIENT, ErrorType.RATE_LIMIT},
            )

            submit_result = await self.retry_manager.execute_with_retry(
                operation=submit_operation,
                config=retry_config,
                context={"job_id": job_id, "model": model},
            )

            if not submit_result.success:
                flow.log_error(submit_result.error, error_type=submit_result.classified_error.error_type.name if submit_result.classified_error else "UNKNOWN")
                self.cooldown.job_failed(job_id, str(submit_result.error))
                self.checkpoint.mark_failed(job_id, str(submit_result.error))

                result.error_message = str(submit_result.error)
                result.error_type = submit_result.classified_error.error_type if submit_result.classified_error else ErrorType.UNKNOWN
                result.attempts = submit_result.attempts
                self._stats["jobs_failed"] += 1
                self._stats["total_errors"] += 1
                return result

            request_id = submit_result.value
            result.request_id = request_id
            result.attempts = submit_result.attempts
            self._stats["total_retries"] += submit_result.attempts - 1

            # Step 6: Update checkpoint with request ID
            flow.log_submit(request_id)
            self.checkpoint.write(
                id=job_id,
                status="submitted",
                request_id=request_id,
                model=model,
            )

            # Step 7: Success
            self.cooldown.job_succeeded(job_id)
            flow.log_step("complete", "success", request_id=request_id)
            flow.end("success")

            result.success = True
            result.total_time_seconds = time() - start_time
            self._stats["jobs_submitted"] += 1

            logger.info(
                "Job submitted successfully",
                job_id=job_id,
                request_id=request_id,
                model=model,
                attempts=result.attempts,
                time_seconds=round(result.total_time_seconds, 2),
            )

            return result

        except Exception as e:
            # Unexpected error - log and update state
            flow.log_error(e)
            flow.end("failed")

            classified = self.classifier.classify(e)
            self.cooldown.job_failed(job_id, str(e))
            self.checkpoint.mark_failed(job_id, str(e))

            result.error_message = str(e)
            result.error_type = classified.error_type
            result.total_time_seconds = time() - start_time
            self._stats["jobs_failed"] += 1
            self._stats["total_errors"] += 1

            logger.error(
                "Job submission failed",
                job_id=job_id,
                error=str(e),
                error_type=classified.error_type.name,
            )

            return result

    async def poll_job_status(
        self,
        job_id: str,
        request_id: str,
        model: str,
        max_polls: int = 120,
        poll_interval: float = 5.0,
    ) -> JobResult:
        """
        Poll for job completion.

        Polls the Fal API until job completes or fails, with:
        - Intelligent retry on network errors
        - Progress logging
        - Checkpoint updates

        Args:
            job_id: Internal job ID
            request_id: Fal request ID
            model: Model used for the job
            max_polls: Maximum polling attempts
            poll_interval: Seconds between polls

        Returns:
            JobResult with final status
        """
        from time import time
        from app.fal_client import get_job_result

        start_time = time()
        flow = JobFlowLogger(job_id, model=model)
        flow.start()

        result = JobResult(
            job_id=job_id,
            success=False,
            request_id=request_id,
            context={"model": model},
        )

        try:
            for poll_num in range(max_polls):
                flow.log_poll(f"poll_{poll_num}")

                # Poll with retry
                async def poll_operation():
                    return await get_job_result(model, request_id)

                retry_config = RetryConfig(
                    max_attempts=3,
                    base_delay_seconds=1.0,
                    retryable_errors={ErrorType.NETWORK, ErrorType.TRANSIENT},
                )

                poll_result = await self.retry_manager.execute_with_retry(
                    operation=poll_operation,
                    config=retry_config,
                )

                if not poll_result.success:
                    continue  # Try next poll

                status_data = poll_result.value
                status = status_data.get("status", "pending")

                if status == "completed":
                    video_url = status_data.get("video_url")
                    flow.log_complete(video_url=video_url)
                    flow.end("success")

                    self.checkpoint.mark_complete(
                        job_id,
                        result={"video_url": video_url, "request_id": request_id},
                    )
                    self.cooldown.job_succeeded(job_id)

                    result.success = True
                    result.video_url = video_url
                    result.total_time_seconds = time() - start_time
                    self._stats["jobs_completed"] += 1

                    return result

                elif status == "failed":
                    error_msg = status_data.get("error_message", "Job failed")
                    flow.log_error(Exception(error_msg))
                    flow.end("failed")

                    self.checkpoint.mark_failed(job_id, error_msg)
                    self.cooldown.job_failed(job_id, error_msg)

                    result.error_message = error_msg
                    result.error_type = ErrorType.PERMANENT
                    result.total_time_seconds = time() - start_time
                    self._stats["jobs_failed"] += 1

                    return result

                # Still running - wait and continue
                flow.log_progress(
                    progress_pct=(poll_num / max_polls) * 100,
                    message=f"Status: {status}",
                )
                await asyncio.sleep(poll_interval)

            # Max polls exceeded
            flow.log_error(Exception("Polling timeout"))
            flow.end("timeout")

            result.error_message = f"Polling timeout after {max_polls} attempts"
            result.error_type = ErrorType.TRANSIENT
            result.total_time_seconds = time() - start_time

            return result

        except Exception as e:
            flow.log_error(e)
            flow.end("failed")

            classified = self.classifier.classify(e)
            result.error_message = str(e)
            result.error_type = classified.error_type
            result.total_time_seconds = time() - start_time

            return result

    async def recover_interrupted_jobs(self) -> List[str]:
        """
        Recover jobs that were interrupted by a crash.

        On startup, finds jobs with status "started" or "submitted"
        and marks them for reprocessing.

        Returns:
            List of job IDs that were recovered
        """
        recovered = self.checkpoint.recover()

        if recovered:
            logger.info(
                "Recovered interrupted jobs",
                count=len(recovered),
                job_ids=recovered[:10],  # Log first 10
            )

        return recovered

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a job from checkpoint.

        Args:
            job_id: The job ID to look up

        Returns:
            Dict with job status or None if not found
        """
        entry = self.checkpoint.read(job_id)
        if entry:
            return {
                "job_id": entry.id,
                "status": entry.status,
                "timestamp": entry.timestamp,
                "step": entry.step,
                "result": entry.result,
                "error": entry.error,
            }
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        cooldown_stats = self.cooldown.get_stats()
        rate_limit_stats = self.rate_limiter.get_stats()

        return {
            **self._stats,
            "cooldown": cooldown_stats,
            "rate_limit": {
                "current_usage": rate_limit_stats.current_usage,
                "max_allowed": rate_limit_stats.max_allowed,
            },
        }


# Singleton instance
job_orchestrator = JobOrchestrator()


async def submit_job_with_hardening(
    model: str,
    image_url: str,
    motion_prompt: str,
    resolution: str,
    duration_sec: int,
    negative_prompt: Optional[str] = None,
    enable_audio: bool = False,
) -> JobResult:
    """
    Convenience function for submitting jobs with full hardening.

    This is the recommended entry point for job submission.
    """
    return await job_orchestrator.submit_job(
        model=model,
        image_url=image_url,
        motion_prompt=motion_prompt,
        resolution=resolution,
        duration_sec=duration_sec,
        negative_prompt=negative_prompt,
        enable_audio=enable_audio,
    )


async def recover_jobs_on_startup():
    """
    Call this on application startup to recover interrupted jobs.

    Usage:
        @app.on_event("startup")
        async def startup():
            await recover_jobs_on_startup()
    """
    recovered = await job_orchestrator.recover_interrupted_jobs()
    if recovered:
        logger.warning(
            "Found interrupted jobs on startup",
            count=len(recovered),
            action="These jobs should be requeued for processing",
        )
    return recovered
