"""In-memory async batch queue for bulk content generation.

MVP implementation using asyncio. Can be swapped to Redis/Celery later.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
import structlog

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    BatchJob,
    BatchJobItem,
    BatchJobStatus,
    BatchJobItemStatus,
    User,
)
from app.services.credits import deduct_credits, refund_credits, InsufficientCreditsError

logger = structlog.get_logger()


@dataclass
class JobState:
    """In-memory state for fast status reads."""
    job_id: str
    status: str
    quantity: int
    completed: int = 0
    failed: int = 0
    pending: int = 0
    eta_seconds: Optional[int] = None
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    avg_duration_ms: Optional[int] = None


class BatchQueue:
    """Async batch job queue with in-memory state tracking.

    Usage:
        queue = BatchQueue(max_concurrency=10)
        await queue.start()

        job_id = await queue.submit_job(user_id, config)
        state = queue.get_state(job_id)

        await queue.stop()
    """

    def __init__(
        self,
        max_concurrency: int = 10,
        generation_fn: Optional[Callable[[BatchJobItem, dict], Awaitable[str]]] = None,
    ):
        """
        Args:
            max_concurrency: Max concurrent item generations
            generation_fn: Async function to generate a single item.
                           Signature: async def fn(item: BatchJobItem, config: dict) -> result_url: str
        """
        self.max_concurrency = max_concurrency
        self.generation_fn = generation_fn or self._default_generation
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._jobs: Dict[str, JobState] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._model_durations: Dict[str, list] = {}  # model_type -> [duration_ms, ...]
        self._started = False

    async def start(self):
        """Start the batch queue."""
        self._started = True
        logger.info("BatchQueue started", max_concurrency=self.max_concurrency)

    async def stop(self):
        """Stop the batch queue and cancel running jobs."""
        self._started = False
        for task in self._running_tasks.values():
            task.cancel()
        logger.info("BatchQueue stopped")

    def get_state(self, job_id: str) -> Optional[JobState]:
        """Get in-memory state for a job (fast read)."""
        return self._jobs.get(job_id)

    def get_all_states(self) -> Dict[str, JobState]:
        """Get all in-memory job states."""
        return self._jobs.copy()

    async def submit_job(
        self,
        user_id: int,
        output_type: str,
        quantity: int,
        config: dict,
        template_id: Optional[str] = None,
        model_profile_id: Optional[int] = None,
        item_specs: Optional[list] = None,
    ) -> str:
        """Submit a new batch job.

        Args:
            user_id: User submitting the job
            output_type: Type of output (image, video, carousel, pipeline)
            quantity: Number of items to generate
            config: Generation config (model, quality, etc.)
            template_id: Optional template reference
            model_profile_id: Optional model profile for face consistency
            item_specs: Optional list of per-item specifications

        Returns:
            job_id (UUID string)

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
            ValueError: If user has too many concurrent jobs
        """
        job_id = str(uuid.uuid4())

        db = SessionLocal()
        try:
            # Check user and tier limits
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Check concurrent job limit based on tier
            tier_limits = {"free": 1, "starter": 2, "pro": 5, "agency": 10}
            max_concurrent = tier_limits.get(user.tier, 2)
            active_jobs = (
                db.query(BatchJob)
                .filter(BatchJob.user_id == user_id)
                .filter(BatchJob.status.in_([BatchJobStatus.QUEUED.value, BatchJobStatus.RUNNING.value]))
                .count()
            )
            if active_jobs >= max_concurrent:
                raise ValueError(f"Max concurrent jobs ({max_concurrent}) reached for {user.tier} tier")

            # Calculate and charge credits
            from app.services.credits import calculate_job_cost
            credits_needed = calculate_job_cost(output_type, quantity, config)

            if user.credits_balance < credits_needed:
                raise InsufficientCreditsError(credits_needed, user.credits_balance)

            # Charge credits
            deduct_credits(
                db=db,
                user_id=user_id,
                amount=credits_needed,
                description=f"Batch job: {quantity} {output_type}(s)",
                source="job",
                reference_id=job_id,
            )

            # Create batch job
            batch_job = BatchJob(
                job_id=job_id,
                user_id=user_id,
                template_id=template_id,
                model_profile_id=model_profile_id,
                output_type=output_type,
                quantity=quantity,
                status=BatchJobStatus.QUEUED.value,
                pending_items=quantity,
                credits_charged=credits_needed,
            )
            batch_job.set_config(config)
            db.add(batch_job)
            db.flush()

            # Create batch job items
            for i in range(quantity):
                item_spec = item_specs[i] if item_specs and i < len(item_specs) else {}
                item = BatchJobItem(
                    batch_job_id=batch_job.id,
                    item_index=i,
                    prompt=item_spec.get("prompt"),
                    caption=item_spec.get("caption"),
                    status=BatchJobItemStatus.PENDING.value,
                )
                if item_spec.get("variation_params"):
                    item.set_variation_params(item_spec["variation_params"])
                db.add(item)

            db.commit()

            # Initialize in-memory state
            self._jobs[job_id] = JobState(
                job_id=job_id,
                status=BatchJobStatus.QUEUED.value,
                quantity=quantity,
                pending=quantity,
            )

            logger.info(
                "Batch job submitted",
                job_id=job_id,
                user_id=user_id,
                quantity=quantity,
                output_type=output_type,
                credits_charged=credits_needed,
            )

            # Start processing in background
            task = asyncio.create_task(self._process_job(job_id))
            self._running_tasks[job_id] = task

            return job_id

        except Exception as e:
            db.rollback()
            logger.error("Failed to submit batch job", error=str(e))
            raise
        finally:
            db.close()

    async def cancel_job(self, job_id: str, user_id: int) -> bool:
        """Cancel a running or queued job.

        Args:
            job_id: Job to cancel
            user_id: User requesting cancellation (for authorization)

        Returns:
            True if cancelled, False if job not found or already finished
        """
        db = SessionLocal()
        try:
            job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
            if not job:
                return False

            if job.user_id != user_id:
                raise PermissionError("Cannot cancel another user's job")

            if job.status in [BatchJobStatus.COMPLETED.value, BatchJobStatus.FAILED.value, BatchJobStatus.CANCELED.value]:
                return False

            # Cancel the asyncio task
            if job_id in self._running_tasks:
                self._running_tasks[job_id].cancel()
                del self._running_tasks[job_id]

            # Update job status
            job.status = BatchJobStatus.CANCELED.value
            job.finished_at = datetime.now(timezone.utc)

            # Calculate refund for incomplete items
            if job.pending_items > 0 and job.credits_charged > 0:
                refund_amount = int(job.credits_charged * (job.pending_items / job.quantity))
                if refund_amount > 0:
                    refund_credits(
                        db=db,
                        user_id=user_id,
                        amount=refund_amount,
                        description=f"Refund for cancelled job {job_id[:8]}",
                        reference_id=job_id,
                    )
                    job.credits_refunded = refund_amount

            db.commit()

            # Update in-memory state
            if job_id in self._jobs:
                self._jobs[job_id].status = BatchJobStatus.CANCELED.value

            logger.info("Batch job cancelled", job_id=job_id, refunded=job.credits_refunded)
            return True

        except Exception as e:
            db.rollback()
            logger.error("Failed to cancel job", job_id=job_id, error=str(e))
            raise
        finally:
            db.close()

    async def _process_job(self, job_id: str):
        """Process all items in a batch job."""
        db = SessionLocal()
        try:
            job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
            if not job:
                logger.error("Job not found for processing", job_id=job_id)
                return

            # Update status to running
            job.status = BatchJobStatus.RUNNING.value
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            if job_id in self._jobs:
                self._jobs[job_id].status = BatchJobStatus.RUNNING.value

            config = job.get_config()
            items = db.query(BatchJobItem).filter(BatchJobItem.batch_job_id == job.id).all()

            # Process items with concurrency control
            tasks = []
            for item in items:
                task = asyncio.create_task(self._process_item(job_id, item.id, config))
                tasks.append(task)

            # Wait for all items
            await asyncio.gather(*tasks, return_exceptions=True)

            # Finalize job
            await self._finalize_job(job_id)

        except asyncio.CancelledError:
            logger.info("Job processing cancelled", job_id=job_id)
        except Exception as e:
            logger.error("Job processing failed", job_id=job_id, error=str(e))
            await self._mark_job_failed(job_id, str(e))
        finally:
            db.close()
            if job_id in self._running_tasks:
                del self._running_tasks[job_id]

    async def _process_item(self, job_id: str, item_id: int, config: dict):
        """Process a single item with semaphore-controlled concurrency."""
        async with self._semaphore:
            db = SessionLocal()
            try:
                item = db.query(BatchJobItem).filter(BatchJobItem.id == item_id).first()
                if not item:
                    return

                # Mark as running
                item.status = BatchJobItemStatus.RUNNING.value
                item.started_at = datetime.now(timezone.utc)
                db.commit()

                start_time = datetime.now(timezone.utc)

                try:
                    # Call generation function
                    result_url = await self.generation_fn(item, config)

                    # Mark as completed
                    item.status = BatchJobItemStatus.COMPLETED.value
                    item.result_url = result_url
                    item.finished_at = datetime.now(timezone.utc)
                    item.duration_ms = int((item.finished_at - start_time).total_seconds() * 1000)
                    db.commit()

                    # Update job progress
                    await self._update_progress(job_id, success=True, duration_ms=item.duration_ms, model_type=config.get("model"))

                except Exception as e:
                    # Mark as failed
                    item.status = BatchJobItemStatus.FAILED.value
                    item.error_message = str(e)[:500]
                    item.finished_at = datetime.now(timezone.utc)
                    db.commit()

                    await self._update_progress(job_id, success=False)
                    logger.warning("Item generation failed", job_id=job_id, item_id=item_id, error=str(e))

            except Exception as e:
                logger.error("Item processing error", job_id=job_id, item_id=item_id, error=str(e))
            finally:
                db.close()

    async def _update_progress(
        self,
        job_id: str,
        success: bool,
        duration_ms: Optional[int] = None,
        model_type: Optional[str] = None,
    ):
        """Update job progress and ETA."""
        db = SessionLocal()
        try:
            job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
            if not job:
                return

            if success:
                job.completed_items += 1
            else:
                job.failed_items += 1
            job.pending_items = job.quantity - job.completed_items - job.failed_items

            # Update moving average duration
            if duration_ms and model_type:
                if model_type not in self._model_durations:
                    self._model_durations[model_type] = []
                self._model_durations[model_type].append(duration_ms)
                # Keep last 50 samples
                self._model_durations[model_type] = self._model_durations[model_type][-50:]
                avg_duration = sum(self._model_durations[model_type]) / len(self._model_durations[model_type])
                job.avg_item_duration_ms = int(avg_duration)

                # Calculate ETA
                if job.pending_items > 0 and job.avg_item_duration_ms:
                    eta_ms = job.pending_items * job.avg_item_duration_ms
                    job.estimated_completion = datetime.now(timezone.utc) + timedelta(milliseconds=eta_ms)

            db.commit()

            # Update in-memory state
            if job_id in self._jobs:
                state = self._jobs[job_id]
                state.completed = job.completed_items
                state.failed = job.failed_items
                state.pending = job.pending_items
                state.avg_duration_ms = job.avg_item_duration_ms
                if job.estimated_completion:
                    state.eta_seconds = int((job.estimated_completion - datetime.now(timezone.utc)).total_seconds())
                state.last_update = datetime.now(timezone.utc)

        except Exception as e:
            logger.error("Progress update failed", job_id=job_id, error=str(e))
        finally:
            db.close()

    async def _finalize_job(self, job_id: str):
        """Mark job as completed or failed based on item results."""
        db = SessionLocal()
        try:
            job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
            if not job:
                return

            job.finished_at = datetime.now(timezone.utc)

            if job.failed_items == job.quantity:
                job.status = BatchJobStatus.FAILED.value
            else:
                job.status = BatchJobStatus.COMPLETED.value

            db.commit()

            if job_id in self._jobs:
                self._jobs[job_id].status = job.status

            logger.info(
                "Batch job finalized",
                job_id=job_id,
                status=job.status,
                completed=job.completed_items,
                failed=job.failed_items,
            )

        except Exception as e:
            logger.error("Job finalization failed", job_id=job_id, error=str(e))
        finally:
            db.close()

    async def _mark_job_failed(self, job_id: str, error: str):
        """Mark job as failed with error message."""
        db = SessionLocal()
        try:
            job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
            if job:
                job.status = BatchJobStatus.FAILED.value
                job.error_message = error[:500]
                job.finished_at = datetime.now(timezone.utc)
                db.commit()

            if job_id in self._jobs:
                self._jobs[job_id].status = BatchJobStatus.FAILED.value

        except Exception as e:
            logger.error("Failed to mark job as failed", job_id=job_id, error=str(e))
        finally:
            db.close()

    async def _default_generation(self, item: BatchJobItem, config: dict) -> str:
        """Default placeholder generation function.

        Replace with actual generation backend integration.
        """
        # Simulate generation time
        await asyncio.sleep(0.5)

        # Return placeholder URL
        return f"https://placeholder.com/generated/{item.batch_job_id}/{item.item_index}.png"


# Global singleton instance
_batch_queue: Optional[BatchQueue] = None


def get_batch_queue() -> BatchQueue:
    """Get the global batch queue instance."""
    global _batch_queue
    if _batch_queue is None:
        _batch_queue = BatchQueue(max_concurrency=10)
    return _batch_queue


async def init_batch_queue(
    max_concurrency: int = 10,
    generation_fn: Optional[Callable] = None,
) -> BatchQueue:
    """Initialize and start the global batch queue."""
    global _batch_queue
    _batch_queue = BatchQueue(
        max_concurrency=max_concurrency,
        generation_fn=generation_fn,
    )
    await _batch_queue.start()
    return _batch_queue
