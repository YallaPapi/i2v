import asyncio
import csv
import re
import signal
import sys
from pathlib import Path
import httpx
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Job
from app.fal_client import submit_job, get_job_result, FalAPIError

logger = structlog.get_logger()



def slugify_prompt(prompt: str, max_words: int = 5) -> str:
    """Convert prompt to filename-safe slug with first N words."""
    # Lowercase and keep only alphanumeric and spaces
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', prompt.lower())
    # Split into words and take first N
    words = clean.split()[:max_words]
    # Join with hyphens
    return '-'.join(words) if words else 'no-prompt'


def append_to_csv(job_id: int, model: str, resolution: str, prompt: str, filename: str):
    """Append job info to downloads index CSV."""
    csv_path = Path(settings.auto_download_dir) / "index.csv"
    file_exists = csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id", "model", "resolution", "filename", "prompt"])
        writer.writerow([job_id, model, resolution, filename, prompt])


async def download_video(job_id: int, model: str, video_url: str,
                         prompt: str = "", resolution: str = "") -> str | None:
    """Download a completed video to the auto-download directory.

    Returns the local file path if successful, None otherwise.
    """
    if not settings.auto_download_dir:
        return None

    download_dir = Path(settings.auto_download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Build filename: job_{id}_{model}_{prompt_slug}.mp4
    prompt_slug = slugify_prompt(prompt)
    filename = f"job_{job_id}_{model}_{prompt_slug}.mp4"
    output_path = download_dir / filename

    # Skip if already downloaded
    if output_path.exists():
        logger.debug("Video already downloaded", job_id=job_id, path=str(output_path))
        return str(output_path)

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", video_url) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        logger.info("Video downloaded", job_id=job_id, path=str(output_path))

        # Append to CSV index
        append_to_csv(job_id, model, resolution, prompt, filename)

        return str(output_path)
    except Exception as e:
        logger.error("Failed to download video", job_id=job_id, error=str(e))
        return None

# Graceful shutdown flag
shutdown_event = asyncio.Event()


def get_db_session() -> Session:
    """Create a new database session."""
    return SessionLocal()


async def submit_single_job(job_id: int, image_url: str, motion_prompt: str,
                            resolution: str, duration_sec: int, model: str) -> tuple[int, str | None, str | None]:
    """Submit a single job and return (job_id, request_id, error)."""
    try:
        request_id = await submit_job(
            model=model,
            image_url=image_url,
            motion_prompt=motion_prompt,
            resolution=resolution,
            duration_sec=duration_sec,
        )
        logger.info("Job submitted", job_id=job_id, model=model, request_id=request_id)
        return (job_id, request_id, None)
    except FalAPIError as e:
        logger.error("Job submission failed", job_id=job_id, model=model, error=str(e))
        return (job_id, None, str(e))
    except Exception as e:
        logger.exception("Unexpected error submitting job", job_id=job_id)
        return (job_id, None, f"Unexpected error: {str(e)}")


async def submit_pending_jobs():
    """Find pending jobs and submit them to Fal concurrently."""
    db = get_db_session()
    try:
        pending_jobs = (
            db.query(Job)
            .filter(Job.wan_status == "pending")
            .limit(settings.max_concurrent_submits)
            .all()
        )

        if not pending_jobs:
            return

        logger.info("Submitting pending jobs", count=len(pending_jobs))

        # Submit all jobs concurrently
        tasks = [
            submit_single_job(
                job.id, job.image_url, job.motion_prompt,
                job.resolution, job.duration_sec, job.model or "wan"
            )
            for job in pending_jobs
        ]
        results = await asyncio.gather(*tasks)

        # Update database with results
        job_map = {job.id: job for job in pending_jobs}
        for job_id, request_id, error in results:
            job = job_map[job_id]
            if request_id:
                job.wan_request_id = request_id
                job.wan_status = "submitted"
            else:
                job.wan_status = "failed"
                job.error_message = error

        db.commit()

    finally:
        db.close()


async def poll_single_job(job_id: int, model: str, request_id: str) -> tuple[int, dict]:
    """Poll a single job and return (job_id, result)."""
    try:
        result = await get_job_result(model, request_id)
        return (job_id, result)
    except FalAPIError as e:
        logger.warning("Error polling job, will retry", job_id=job_id, error=str(e))
        return (job_id, {"status": None, "video_url": None, "error_message": None})
    except Exception as e:
        logger.exception("Unexpected error polling job", job_id=job_id)
        return (job_id, {"status": None, "video_url": None, "error_message": None})


async def poll_submitted_jobs():
    """Poll submitted/running jobs for completion concurrently."""
    db = get_db_session()
    try:
        active_jobs = (
            db.query(Job)
            .filter(Job.wan_status.in_(["submitted", "running"]))
            .filter(Job.wan_request_id.isnot(None))
            .limit(settings.max_concurrent_polls)
            .all()
        )

        if not active_jobs:
            return

        logger.info("Polling active jobs", count=len(active_jobs))

        # Poll all jobs concurrently
        tasks = [
            poll_single_job(job.id, job.model or "wan", job.wan_request_id)
            for job in active_jobs
        ]
        results = await asyncio.gather(*tasks)

        # Update database with results
        job_map = {job.id: job for job in active_jobs}
        for job_id, result in results:
            if result["status"] is None:
                continue  # Skip failed polls

            job = job_map[job_id]
            old_status = job.wan_status
            job.wan_status = result["status"]

            if result["video_url"]:
                job.wan_video_url = result["video_url"]
                logger.info("Job completed", job_id=job.id, video_url=job.wan_video_url)
                # Auto-download if enabled
                if settings.auto_download_dir:
                    local_path = await download_video(
                        job.id,
                        job.model or "wan",
                        result["video_url"],
                        prompt=job.motion_prompt or "",
                        resolution=job.resolution or ""
                    )
                    if local_path:
                        job.local_video_path = local_path

            if result["error_message"]:
                job.error_message = result["error_message"]
                logger.error("Job failed", job_id=job.id, error=job.error_message)

            if old_status != job.wan_status:
                logger.info("Job status changed", job_id=job.id,
                           old_status=old_status, new_status=job.wan_status)

        db.commit()

    finally:
        db.close()


async def worker_loop():
    """Main worker loop."""
    logger.info(
        "Starting worker",
        poll_interval=settings.worker_poll_interval_seconds,
        max_submits=settings.max_concurrent_submits,
        max_polls=settings.max_concurrent_polls,
    )

    init_db()

    while not shutdown_event.is_set():
        try:
            # Run submit and poll concurrently
            await asyncio.gather(
                submit_pending_jobs(),
                poll_submitted_jobs(),
            )
        except Exception as e:
            logger.exception("Error in worker loop", error=str(e))

        # Wait for interval or shutdown
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=settings.worker_poll_interval_seconds,
            )
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue loop

    logger.info("Worker shutdown complete")


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal", signal=signum)
    shutdown_event.set()


def main():
    """Entry point for the worker."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
