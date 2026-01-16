import asyncio
import csv
import json
import re
import signal
import sys
from pathlib import Path
import httpx
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Job, ImageJob
from app.fal_client import submit_job, get_job_result, FalAPIError
from app.image_client import submit_image_job, get_image_result, ImageAPIError
from app.schemas import is_vastai_model
from app.services.vastai_orchestrator import get_vastai_orchestrator
from app.services.r2_cache import cache_video

logger = structlog.get_logger()


def slugify_prompt(prompt: str, max_words: int = 5) -> str:
    """Convert prompt to filename-safe slug with first N words."""
    # Lowercase and keep only alphanumeric and spaces
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower())
    # Split into words and take first N
    words = clean.split()[:max_words]
    # Join with hyphens
    return "-".join(words) if words else "no-prompt"


def append_to_csv(job_id: int, model: str, resolution: str, prompt: str, filename: str):
    """Append job info to downloads index CSV."""
    csv_path = Path(settings.auto_download_dir) / "index.csv"
    file_exists = csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id", "model", "resolution", "filename", "prompt"])
        writer.writerow([job_id, model, resolution, filename, prompt])


async def download_video(
    job_id: int, model: str, video_url: str, prompt: str = "", resolution: str = ""
) -> str | None:
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


async def submit_single_job(
    job_id: int,
    image_url: str,
    motion_prompt: str,
    resolution: str,
    duration_sec: int,
    model: str,
    negative_prompt: str | None = None,
) -> tuple[int, str | None, str | None]:
    """Submit a single job to fal.ai and return (job_id, request_id, error)."""
    try:
        request_id = await submit_job(
            model=model,
            image_url=image_url,
            motion_prompt=motion_prompt,
            resolution=resolution,
            duration_sec=duration_sec,
            negative_prompt=negative_prompt,
        )
        logger.info("Job submitted to fal.ai", job_id=job_id, model=model, request_id=request_id)
        return (job_id, request_id, None)
    except FalAPIError as e:
        logger.error("Job submission failed", job_id=job_id, model=model, error=str(e))
        return (job_id, None, str(e))
    except Exception as e:
        logger.exception("Unexpected error submitting job", job_id=job_id)
        return (job_id, None, f"Unexpected error: {str(e)}")


async def process_vastai_job(job: Job, db: Session) -> bool:
    """
    Process a single vastai job synchronously via SwarmUI WebSocket.
    Returns True on success, False on failure.

    VastAI jobs are processed ONE AT A TIME to avoid multiple WebSocket connections.
    """
    logger.info("Processing vastai job", job_id=job.id, model=job.model)
    job.wan_status = "running"
    db.commit()

    try:
        orchestrator = get_vastai_orchestrator()
        client = await orchestrator.get_or_create_client()

        # Upload image to SwarmUI
        image_path = await client.upload_image(job.image_url)

        # Map resolution to width/height (9:16 portrait default)
        if job.resolution == "720p":
            width, height = 720, 1280
        elif job.resolution == "1080p":
            width, height = 1080, 1920
        else:
            width, height = 480, 848

        # Generate video via WebSocket
        result = await client.generate_video(
            image_path=image_path,
            prompt=job.motion_prompt or "gentle motion",
            negative_prompt=job.negative_prompt,
            model=settings.swarmui_model,
            width=width,
            height=height,
            num_frames=settings.swarmui_default_frames,
            fps=settings.swarmui_default_fps,
            steps=settings.swarmui_default_steps,
            cfg_scale=settings.swarmui_default_cfg,
            video_steps=settings.swarmui_video_steps,
            video_cfg=settings.swarmui_video_cfg,
            swap_model=settings.swarmui_swap_model,
            swap_percent=settings.swarmui_swap_percent,
            lora_high=settings.swarmui_lora_high,
            lora_low=settings.swarmui_lora_low,
        )

        video_url = result.get("video_url")
        if not video_url:
            raise Exception("No video_url in SwarmUI result")

        # Cache to R2 if available
        video_path = result.get("video_path")
        if video_path:
            try:
                video_bytes = await client.get_video_bytes(video_path)
                cached_url = await cache_video(video_url, video_bytes=video_bytes)
                if cached_url:
                    video_url = cached_url
            except Exception as e:
                logger.warning("R2 cache failed, using direct URL", error=str(e))

        job.wan_status = "completed"
        job.wan_video_url = video_url
        db.commit()

        logger.info("Vastai job completed", job_id=job.id, video_url=video_url[:50])
        return True

    except Exception as e:
        logger.error("Vastai job failed", job_id=job.id, error=str(e))
        job.wan_status = "failed"
        job.error_message = str(e)
        db.commit()
        return False


async def submit_pending_jobs():
    """Find pending jobs and route to appropriate provider."""
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

        # Separate vastai jobs from fal.ai jobs
        vastai_jobs = [j for j in pending_jobs if is_vastai_model(j.model or "")]
        fal_jobs = [j for j in pending_jobs if not is_vastai_model(j.model or "")]

        logger.info(
            "Submitting pending jobs",
            total=len(pending_jobs),
            vastai=len(vastai_jobs),
            fal=len(fal_jobs),
        )

        # Process vastai jobs ONE AT A TIME (sequential, not concurrent)
        # This avoids multiple WebSocket connections to SwarmUI
        for job in vastai_jobs:
            await process_vastai_job(job, db)

        # Submit fal.ai jobs concurrently (they handle queuing)
        if fal_jobs:
            tasks = [
                submit_single_job(
                    job.id,
                    job.image_url,
                    job.motion_prompt,
                    job.resolution,
                    job.duration_sec,
                    job.model or "wan",
                    job.negative_prompt,
                )
                for job in fal_jobs
            ]
            results = await asyncio.gather(*tasks)

            # Update database with results
            job_map = {job.id: job for job in fal_jobs}
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
    except Exception:
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
                        resolution=job.resolution or "",
                    )
                    if local_path:
                        job.local_video_path = local_path

            if result["error_message"]:
                job.error_message = result["error_message"]
                logger.error("Job failed", job_id=job.id, error=job.error_message)

            if old_status != job.wan_status:
                logger.info(
                    "Job status changed",
                    job_id=job.id,
                    old_status=old_status,
                    new_status=job.wan_status,
                )

        db.commit()

    finally:
        db.close()


# ============== Image Job Processing ==============


async def download_image(
    job_id: int, model: str, image_url: str, index: int, prompt: str = ""
) -> str | None:
    """Download a generated image to the auto-download directory."""
    if not settings.auto_download_dir:
        return None

    download_dir = Path(settings.auto_download_dir) / "images"
    download_dir.mkdir(parents=True, exist_ok=True)

    prompt_slug = slugify_prompt(prompt)
    filename = f"img_{job_id}_{model}_{index}_{prompt_slug}.png"
    output_path = download_dir / filename

    if output_path.exists():
        return str(output_path)

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", image_url) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        logger.info("Image downloaded", job_id=job_id, path=str(output_path))
        return str(output_path)
    except Exception as e:
        logger.error("Failed to download image", job_id=job_id, error=str(e))
        return None


async def submit_single_image_job(
    job_id: int,
    source_image_url: str,
    prompt: str,
    model: str,
    negative_prompt: str | None,
    num_images: int,
    aspect_ratio: str,
    quality: str,
) -> tuple[int, str | None, str | None]:
    """Submit a single image job and return (job_id, request_id, error)."""
    try:
        request_id = await submit_image_job(
            model=model,
            image_url=source_image_url,
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_images=num_images,
            aspect_ratio=aspect_ratio,
            quality=quality,
        )
        logger.info(
            "Image job submitted", job_id=job_id, model=model, request_id=request_id
        )
        return (job_id, request_id, None)
    except ImageAPIError as e:
        logger.error(
            "Image job submission failed", job_id=job_id, model=model, error=str(e)
        )
        return (job_id, None, str(e))
    except Exception as e:
        logger.exception("Unexpected error submitting image job", job_id=job_id)
        return (job_id, None, f"Unexpected error: {str(e)}")


async def submit_pending_image_jobs():
    """Find pending image jobs and submit them to Fal."""
    db = get_db_session()
    try:
        pending_jobs = (
            db.query(ImageJob)
            .filter(ImageJob.status == "pending")
            .limit(settings.max_concurrent_submits)
            .all()
        )

        if not pending_jobs:
            return

        logger.info("Submitting pending image jobs", count=len(pending_jobs))

        tasks = [
            submit_single_image_job(
                job.id,
                job.source_image_url,
                job.prompt,
                job.model,
                job.negative_prompt,
                job.num_images,
                job.aspect_ratio,
                job.quality,
            )
            for job in pending_jobs
        ]
        results = await asyncio.gather(*tasks)

        job_map = {job.id: job for job in pending_jobs}
        for job_id, request_id, error in results:
            job = job_map[job_id]
            if request_id:
                job.request_id = request_id
                job.status = "submitted"
            else:
                job.status = "failed"
                job.error_message = error

        db.commit()

    finally:
        db.close()


async def poll_single_image_job(
    job_id: int, model: str, request_id: str
) -> tuple[int, dict]:
    """Poll a single image job and return (job_id, result)."""
    try:
        result = await get_image_result(model, request_id)
        return (job_id, result)
    except ImageAPIError as e:
        logger.warning(
            "Error polling image job, will retry", job_id=job_id, error=str(e)
        )
        return (job_id, {"status": None, "image_urls": None, "error_message": None})
    except Exception:
        logger.exception("Unexpected error polling image job", job_id=job_id)
        return (job_id, {"status": None, "image_urls": None, "error_message": None})


async def poll_submitted_image_jobs():
    """Poll submitted/running image jobs for completion."""
    db = get_db_session()
    try:
        active_jobs = (
            db.query(ImageJob)
            .filter(ImageJob.status.in_(["submitted", "running"]))
            .filter(ImageJob.request_id.isnot(None))
            .limit(settings.max_concurrent_polls)
            .all()
        )

        if not active_jobs:
            return

        logger.info("Polling active image jobs", count=len(active_jobs))

        tasks = [
            poll_single_image_job(job.id, job.model, job.request_id)
            for job in active_jobs
        ]
        results = await asyncio.gather(*tasks)

        job_map = {job.id: job for job in active_jobs}
        for job_id, result in results:
            if result["status"] is None:
                continue

            job = job_map[job_id]
            old_status = job.status
            job.status = result["status"]

            if result["image_urls"]:
                job.result_image_urls = json.dumps(result["image_urls"])
                logger.info(
                    "Image job completed",
                    job_id=job.id,
                    num_images=len(result["image_urls"]),
                )

                # Auto-download images
                if settings.auto_download_dir:
                    local_paths = []
                    for i, img_url in enumerate(result["image_urls"]):
                        local_path = await download_image(
                            job.id, job.model, img_url, i, job.prompt
                        )
                        if local_path:
                            local_paths.append(local_path)
                    if local_paths:
                        job.local_image_paths = json.dumps(local_paths)

            if result["error_message"]:
                job.error_message = result["error_message"]
                logger.error("Image job failed", job_id=job.id, error=job.error_message)

            if old_status != job.status:
                logger.info(
                    "Image job status changed",
                    job_id=job.id,
                    old_status=old_status,
                    new_status=job.status,
                )

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
            # Run submit and poll for both video and image jobs concurrently
            await asyncio.gather(
                submit_pending_jobs(),
                poll_submitted_jobs(),
                submit_pending_image_jobs(),
                poll_submitted_image_jobs(),
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
