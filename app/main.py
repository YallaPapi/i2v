from contextlib import asynccontextmanager
from typing import Optional, List
import os
import structlog
import tempfile
from pathlib import Path

# Set FAL_KEY before any fal_client imports happen anywhere in the app
from app.config import settings

if settings.fal_api_key:
    os.environ["FAL_KEY"] = settings.fal_api_key

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import get_db, init_db
from app.models import Job, ImageJob
from app.schemas import (
    JobCreate,
    JobResponse,
    HealthResponse,
    ImageJobCreate,
    ImageJobResponse,
    ImageModelsResponse,
    FaceSwapCreate,
    FaceSwapResponse,
    FaceSwapModelsResponse,
)
from app.image_client import list_image_models
from app.face_swap_client import (
    submit_face_swap_job,
    get_face_swap_result,
    list_face_swap_models,
)
from app.fal_upload import upload_image, SUPPORTED_FORMATS
from app.routers.pipelines import router as pipelines_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info(
        "Starting i2v service",
        db_path=settings.db_path,
        poll_interval=settings.worker_poll_interval_seconds,
    )
    init_db()

    # Recover interrupted jobs from previous crash (Production Hardening Principle 3)
    try:
        from app.services import recover_jobs_on_startup

        recovered_jobs = await recover_jobs_on_startup()
        if recovered_jobs:
            logger.info(
                "Recovered interrupted jobs from previous session",
                count=len(recovered_jobs),
            )
    except Exception as e:
        logger.warning("Failed to recover jobs on startup", error=str(e))

    # Auto-generate thumbnails for existing images that don't have them
    try:
        import asyncio

        asyncio.create_task(_generate_missing_thumbnails())
    except Exception as e:
        logger.warning("Failed to start thumbnail generation", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down i2v service")


async def _generate_missing_thumbnails():
    """Background task to generate thumbnails for images that don't have them."""
    import asyncio
    from app.database import SessionLocal
    from app.models import PipelineStep, StepStatus
    from app.services.thumbnail import generate_thumbnails_batch

    # Wait a bit for app to fully start
    await asyncio.sleep(2)

    logger.info("Starting background thumbnail generation for existing images")

    db = SessionLocal()
    try:
        # Get all i2i steps
        steps = (
            db.query(PipelineStep)
            .filter(PipelineStep.step_type == "i2i")
            .filter(PipelineStep.status == StepStatus.COMPLETED.value)
            .all()
        )

        processed = 0
        for step in steps:
            outputs = step.get_outputs()
            if not outputs or not outputs.get("image_urls"):
                continue

            # Skip if thumbnails already exist
            existing_thumbs = outputs.get("thumbnail_urls", [])
            image_urls = outputs["image_urls"]
            if existing_thumbs and len(existing_thumbs) == len(image_urls):
                continue

            # Generate thumbnails
            try:
                thumbnail_urls = await generate_thumbnails_batch(image_urls)
                outputs["thumbnail_urls"] = thumbnail_urls
                step.set_outputs(outputs)
                db.commit()
                processed += 1

                # Don't overwhelm the system
                if processed % 10 == 0:
                    logger.info(f"Generated thumbnails for {processed} steps so far...")
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail for step {step.id}: {e}")
                continue

        logger.info(f"Thumbnail generation complete. Processed {processed} steps.")

    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
    finally:
        db.close()


app = FastAPI(
    title="i2v - Image to Video Service",
    description="Backend service for AI image-to-video and image generation via Fal API. Supports Wan, Kling, Veo, Sora models for video and GPT-Image, Kling, Nano-Banana, Flux models for images.",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS middleware - configure allowed origins for production
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
# Add production frontend URL if configured
if os.getenv("FRONTEND_URL"):
    CORS_ORIGINS.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if os.getenv("PRODUCTION") else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Include routers
app.include_router(pipelines_router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """Health check endpoint for frontend (under /api prefix)."""
    return {"status": "ok"}


@app.get("/api/status")
async def get_api_status(db: Session = Depends(get_db)):
    """Get service status with job counts by status."""
    # Get orchestrator stats for production hardening visibility
    try:
        from app.services import job_orchestrator

        orchestrator_stats = job_orchestrator.get_stats()
    except Exception:
        orchestrator_stats = None

    return {
        "status": "ok",
        "jobs": {
            "pending": db.query(Job).filter(Job.wan_status == "pending").count(),
            "submitted": db.query(Job).filter(Job.wan_status == "submitted").count(),
            "running": db.query(Job).filter(Job.wan_status == "running").count(),
            "completed": db.query(Job).filter(Job.wan_status == "completed").count(),
            "failed": db.query(Job).filter(Job.wan_status == "failed").count(),
        },
        "image_jobs": {
            "pending": db.query(ImageJob).filter(ImageJob.status == "pending").count(),
            "completed": db.query(ImageJob)
            .filter(ImageJob.status == "completed")
            .count(),
            "failed": db.query(ImageJob).filter(ImageJob.status == "failed").count(),
        },
        "hardening": orchestrator_stats,
    }


@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new video generation job."""
    job = Job(
        image_url=job_data.image_url,
        motion_prompt=job_data.motion_prompt,
        negative_prompt=job_data.negative_prompt,
        resolution=job_data.resolution,
        duration_sec=job_data.duration_sec,
        model=job_data.model,
        wan_status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Job created", job_id=job.id, status=job.wan_status)
    return job


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job by ID."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by wan_status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all jobs with optional filtering and pagination."""
    query = db.query(Job)

    if status:
        valid_statuses = ["pending", "submitted", "running", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )
        query = query.filter(Job.wan_status == status)

    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    return jobs


# ============== Image Generation Endpoints ==============


@app.get("/images/models", response_model=ImageModelsResponse)
async def get_image_models():
    """List available image generation models with pricing."""
    return {"models": list_image_models()}


@app.post("/images", response_model=ImageJobResponse, status_code=201)
async def create_image_job(job_data: ImageJobCreate, db: Session = Depends(get_db)):
    """Create a new image generation job."""
    job = ImageJob(
        source_image_url=job_data.source_image_url,
        prompt=job_data.prompt,
        negative_prompt=job_data.negative_prompt,
        model=job_data.model,
        aspect_ratio=job_data.aspect_ratio,
        quality=job_data.quality,
        num_images=job_data.num_images,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Image job created", job_id=job.id, model=job.model, status=job.status)
    return job


@app.get("/images/{job_id}", response_model=ImageJobResponse)
async def get_image_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific image job by ID."""
    job = db.query(ImageJob).filter(ImageJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Image job not found")
    return job


@app.get("/images", response_model=List[ImageJobResponse])
async def list_image_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    model: Optional[str] = Query(None, description="Filter by model"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all image jobs with optional filtering and pagination."""
    query = db.query(ImageJob)

    if status:
        valid_statuses = ["pending", "submitted", "running", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )
        query = query.filter(ImageJob.status == status)

    if model:
        query = query.filter(ImageJob.model == model)

    jobs = query.order_by(ImageJob.created_at.desc()).offset(offset).limit(limit).all()
    return jobs


# ============== Face Swap Endpoints ==============


@app.post("/face-swap", response_model=FaceSwapResponse, status_code=201)
async def create_face_swap(swap_data: FaceSwapCreate):
    """
    Create a face swap job.

    Takes a face from face_image_url and swaps it onto target_image_url.

    - **face_image_url**: Image containing the face to swap FROM
    - **target_image_url**: Image to swap the face TO
    - **gender**: Gender of person in face image (male/female/non-binary)
    - **workflow_type**: 'target_hair' keeps target's hair, 'user_hair' keeps source's hair
    - **upscale**: Apply 2x upscale (default True)
    - **detailer**: Apply detail enhancement (default False)

    Returns request_id for polling status.
    """
    try:
        request_id = await submit_face_swap_job(
            face_image_url=swap_data.face_image_url,
            target_image_url=swap_data.target_image_url,
            gender=swap_data.gender,
            workflow_type=swap_data.workflow_type,
            upscale=swap_data.upscale,
            detailer=swap_data.detailer,
            face_image_url_2=swap_data.face_image_url_2,
            gender_2=swap_data.gender_2,
        )

        logger.info("Face swap job created", request_id=request_id)
        return FaceSwapResponse(
            request_id=request_id,
            status="pending",
            model="easel-advanced",
            cost=0.05,
        )
    except Exception as e:
        logger.error("Face swap submission failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Face swap failed: {str(e)}")


@app.get("/face-swap/{request_id}", response_model=FaceSwapResponse)
async def get_face_swap_status(request_id: str):
    """Get the status of a face swap job."""
    try:
        result = await get_face_swap_result(request_id)

        return FaceSwapResponse(
            request_id=request_id,
            status=result["status"],
            result_image_url=result.get("image_url"),
            error_message=result.get("error_message"),
            model="easel-advanced",
            cost=0.05,
        )
    except Exception as e:
        logger.error("Face swap status check failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.get("/face-swap-models", response_model=FaceSwapModelsResponse)
async def get_face_swap_models():
    """List available face swap models with pricing."""
    return FaceSwapModelsResponse(models=list_face_swap_models())


# ============== Upload Endpoints ==============


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload an image file to Fal CDN and return the URL."""
    import traceback

    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {SUPPORTED_FORMATS}",
        )

    # Save to temp file and upload
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        fal_url = await upload_image(tmp_path)

        # Clean up temp file
        try:
            tmp_path.unlink()
        except Exception:
            pass

        logger.info("File uploaded", filename=file.filename, url=fal_url[:60])
        return {"url": fal_url, "filename": file.filename}

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error("Upload failed", error=str(e), traceback=error_details)
        # Clean up on error
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
