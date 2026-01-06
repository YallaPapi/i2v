"""Job worker with file-based locking for safe concurrency.

Principle 4: File-Based Locking
Use file locks to prevent concurrent access to shared resources.
Database locks are unreliable (especially SQLite). File locks work.

Critical Race Condition Fixed:
    Before (UNSAFE):
        pending_jobs = db.query(Job).filter(status="pending").limit(N).all()
        # Two workers can fetch the same jobs here!
        for job in pending_jobs:
            job.status = "submitted"

    After (SAFE):
        with JobLock():
            pending_jobs = claim_pending_jobs(limit=N, worker_id=MY_ID)
        # Only one worker can claim at a time

Usage:
    worker = JobWorker(worker_id="worker-1")

    # Claim and process jobs
    await worker.process_pending_jobs(limit=5)

    # Run continuous loop
    await worker.run_forever(poll_interval=10.0)
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from dataclasses import dataclass
import structlog

from app.services.file_lock import JobLock, LockAcquisitionError
from app.services.checkpoint_manager import job_checkpoint
from app.services.flow_logger import FlowLogger
from app.services.cooldown_manager import job_cooldown
from app.services.job_orchestrator import job_orchestrator, JobResult

logger = structlog.get_logger()


@dataclass
class WorkerStats:
    """Statistics for a worker."""

    worker_id: str
    jobs_claimed: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    current_job: Optional[str] = None
    started_at: Optional[str] = None
    last_activity: Optional[str] = None


class JobWorker:
    """
    Production-hardened job worker.

    Uses file-based locking to safely claim jobs without race conditions.
    Integrates with the orchestrator for reliable processing.

    Attributes:
        worker_id: Unique identifier for this worker
        orchestrator: JobOrchestrator for job processing
        stats: WorkerStats tracking
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        lock_timeout: float = 30.0,
    ):
        """
        Initialize job worker.

        Args:
            worker_id: Unique ID for this worker (generates UUID if not provided)
            lock_timeout: Timeout for acquiring job lock
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.lock_timeout = lock_timeout
        self.orchestrator = job_orchestrator

        self._running = False
        self._current_job_id: Optional[str] = None

        self.stats = WorkerStats(
            worker_id=self.worker_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("JobWorker initialized", worker_id=self.worker_id)

    async def claim_pending_jobs(
        self,
        db_session,
        limit: int = 5,
    ) -> List[Any]:
        """
        Safely claim pending jobs with file lock.

        This is the critical section - only one worker can execute this
        at a time to prevent race conditions.

        Args:
            db_session: SQLAlchemy database session
            limit: Maximum jobs to claim

        Returns:
            List of claimed Job objects
        """
        from app.models import Job

        claimed = []

        try:
            # Acquire lock before querying
            with JobLock(timeout=self.lock_timeout):
                logger.debug(
                    "Job lock acquired",
                    worker_id=self.worker_id,
                    limit=limit,
                )

                # Query pending jobs that are not in cooldown
                pending_jobs = (
                    db_session.query(Job)
                    .filter(Job.wan_status == "pending")
                    .order_by(Job.created_at)
                    .limit(limit * 2)  # Get extra to filter cooldowns
                    .all()
                )

                # Filter out jobs in cooldown
                job_ids = [str(job.id) for job in pending_jobs]
                eligible_ids = job_cooldown.get_processable_jobs(job_ids)

                # Claim eligible jobs up to limit
                for job in pending_jobs:
                    if str(job.id) in eligible_ids and len(claimed) < limit:
                        # Mark as claimed by this worker
                        job.wan_status = "claimed"
                        job.error_message = f"Claimed by {self.worker_id}"
                        claimed.append(job)

                        # Write checkpoint
                        job_checkpoint.write(
                            id=str(job.id),
                            status="claimed",
                            worker_id=self.worker_id,
                            model=job.model,
                        )

                        self.stats.jobs_claimed += 1

                # Commit claims
                if claimed:
                    db_session.commit()
                    logger.info(
                        "Jobs claimed",
                        worker_id=self.worker_id,
                        count=len(claimed),
                        job_ids=[j.id for j in claimed],
                    )

        except LockAcquisitionError:
            logger.warning(
                "Could not acquire job lock",
                worker_id=self.worker_id,
                timeout=self.lock_timeout,
            )

        return claimed

    async def process_job(
        self,
        job,
        db_session,
    ) -> JobResult:
        """
        Process a single claimed job.

        Args:
            job: Job model instance
            db_session: Database session

        Returns:
            JobResult with processing outcome
        """
        self._current_job_id = str(job.id)
        self.stats.current_job = str(job.id)
        self.stats.last_activity = datetime.now(timezone.utc).isoformat()

        # Create flow logger
        flow = FlowLogger("worker", f"{self.worker_id}-{job.id}")
        flow.start()

        try:
            flow.log_step("process_start", "running", job_id=job.id, model=job.model)

            # Submit via orchestrator
            result = await self.orchestrator.submit_job(
                model=job.model,
                image_url=job.image_url,
                motion_prompt=job.motion_prompt,
                resolution=job.resolution,
                duration_sec=job.duration_sec,
                negative_prompt=job.negative_prompt,
                job_id=str(job.id),
            )

            if result.success:
                # Update job with request ID
                job.wan_request_id = result.request_id
                job.wan_status = "submitted"
                job.error_message = None
                self.stats.jobs_completed += 1

                flow.log_step(
                    "submit_success", "submitted", request_id=result.request_id
                )
                logger.info(
                    "Job submitted",
                    worker_id=self.worker_id,
                    job_id=job.id,
                    request_id=result.request_id,
                )
            else:
                # Update job with error
                job.wan_status = "failed"
                job.error_message = result.error_message
                self.stats.jobs_failed += 1

                flow.log_step("submit_failed", "failed", error=result.error_message)
                logger.warning(
                    "Job failed",
                    worker_id=self.worker_id,
                    job_id=job.id,
                    error=result.error_message,
                )

            db_session.commit()
            flow.end("completed" if result.success else "failed")

            return result

        except Exception as e:
            # Unexpected error
            job.wan_status = "failed"
            job.error_message = str(e)
            db_session.commit()

            flow.log_error(e)
            flow.end("error")

            self.stats.jobs_failed += 1
            logger.error(
                "Job processing error",
                worker_id=self.worker_id,
                job_id=job.id,
                error=str(e),
            )

            return JobResult(
                job_id=str(job.id),
                success=False,
                error_message=str(e),
            )

        finally:
            self._current_job_id = None
            self.stats.current_job = None

    async def process_pending_jobs(
        self,
        db_session,
        limit: int = 5,
    ) -> List[JobResult]:
        """
        Claim and process pending jobs.

        Args:
            db_session: Database session
            limit: Maximum jobs to process

        Returns:
            List of JobResult for processed jobs
        """
        # Claim jobs with lock
        claimed = await self.claim_pending_jobs(db_session, limit=limit)

        if not claimed:
            logger.debug("No jobs to process", worker_id=self.worker_id)
            return []

        # Process each claimed job
        results = []
        for job in claimed:
            result = await self.process_job(job, db_session)
            results.append(result)

        return results

    async def poll_submitted_jobs(
        self,
        db_session,
        limit: int = 10,
    ) -> List[JobResult]:
        """
        Poll for completion of submitted jobs.

        Args:
            db_session: Database session
            limit: Maximum jobs to poll

        Returns:
            List of JobResult for polled jobs
        """
        from app.models import Job

        # Get submitted jobs
        submitted_jobs = (
            db_session.query(Job)
            .filter(Job.wan_status == "submitted")
            .filter(Job.wan_request_id.isnot(None))
            .order_by(Job.updated_at)
            .limit(limit)
            .all()
        )

        results = []
        for job in submitted_jobs:
            result = await self.orchestrator.poll_job_status(
                job_id=str(job.id),
                request_id=job.wan_request_id,
                model=job.model,
                max_polls=1,  # Single poll per cycle
            )

            if result.success:
                job.wan_status = "completed"
                job.wan_video_url = result.video_url
                job.error_message = None
            elif result.error_type:
                if result.error_type == ErrorType.PERMANENT:
                    job.wan_status = "failed"
                    job.error_message = result.error_message
                # Transient errors: keep polling

            db_session.commit()
            results.append(result)

        return results

    async def run_once(
        self,
        db_session,
        submit_limit: int = 5,
        poll_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Run one cycle of the worker loop.

        Args:
            db_session: Database session
            submit_limit: Maximum jobs to submit
            poll_limit: Maximum jobs to poll

        Returns:
            Dict with cycle results
        """
        self.stats.last_activity = datetime.now(timezone.utc).isoformat()

        # Process pending jobs
        submit_results = await self.process_pending_jobs(db_session, limit=submit_limit)

        # Poll submitted jobs
        poll_results = await self.poll_submitted_jobs(db_session, limit=poll_limit)

        return {
            "worker_id": self.worker_id,
            "submitted": len(submit_results),
            "polled": len(poll_results),
            "submit_success": sum(1 for r in submit_results if r.success),
            "poll_complete": sum(1 for r in poll_results if r.success),
        }

    async def run_forever(
        self,
        db_session_factory,
        poll_interval: float = 10.0,
        submit_limit: int = 5,
        poll_limit: int = 10,
    ):
        """
        Run the worker continuously.

        Args:
            db_session_factory: Callable that returns a new DB session
            poll_interval: Seconds between cycles
            submit_limit: Maximum jobs to submit per cycle
            poll_limit: Maximum jobs to poll per cycle
        """
        self._running = True
        logger.info(
            "Worker starting",
            worker_id=self.worker_id,
            poll_interval=poll_interval,
        )

        try:
            while self._running:
                try:
                    db_session = db_session_factory()
                    try:
                        result = await self.run_once(
                            db_session,
                            submit_limit=submit_limit,
                            poll_limit=poll_limit,
                        )

                        if result["submitted"] > 0 or result["polled"] > 0:
                            logger.debug("Worker cycle completed", **result)

                    finally:
                        db_session.close()

                except Exception as e:
                    logger.error(
                        "Worker cycle error",
                        worker_id=self.worker_id,
                        error=str(e),
                    )

                await asyncio.sleep(poll_interval)

        finally:
            self._running = False
            logger.info("Worker stopped", worker_id=self.worker_id)

    def stop(self):
        """Signal the worker to stop."""
        self._running = False
        logger.info("Worker stop requested", worker_id=self.worker_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.stats.worker_id,
            "jobs_claimed": self.stats.jobs_claimed,
            "jobs_completed": self.stats.jobs_completed,
            "jobs_failed": self.stats.jobs_failed,
            "current_job": self.stats.current_job,
            "started_at": self.stats.started_at,
            "last_activity": self.stats.last_activity,
            "running": self._running,
        }


# Import ErrorType for reference
from app.services.error_classifier import ErrorType


async def start_worker(
    db_session_factory,
    worker_id: Optional[str] = None,
    poll_interval: float = 10.0,
) -> JobWorker:
    """
    Start a background job worker.

    Usage:
        from app.database import SessionLocal
        worker = await start_worker(SessionLocal)

    Args:
        db_session_factory: Callable returning new DB sessions
        worker_id: Optional worker ID
        poll_interval: Seconds between cycles

    Returns:
        The running JobWorker instance
    """
    worker = JobWorker(worker_id=worker_id)

    # Run in background task
    asyncio.create_task(
        worker.run_forever(db_session_factory, poll_interval=poll_interval)
    )

    return worker
