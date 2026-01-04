from contextlib import asynccontextmanager
from typing import Optional, List
import os
import structlog
import tempfile
from pathlib import Path
from datetime import datetime

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
    JobCreate, JobResponse, HealthResponse,
    ImageJobCreate, ImageJobResponse, ImageModelsResponse
)
from app.image_client import list_image_models
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

    yield

    # Shutdown
    logger.info("Shutting down i2v service")


app = FastAPI(
    title="i2v - Image to Video Service",
    description="Backend service for AI image-to-video and image generation via Fal API. Supports Wan, Kling, Veo, Sora models for video and GPT-Image, Kling, Nano-Banana, Flux models for images.",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            "completed": db.query(ImageJob).filter(ImageJob.status == "completed").count(),
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
                detail=f"Invalid status. Must be one of: {valid_statuses}"
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
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        query = query.filter(ImageJob.status == status)

    if model:
        query = query.filter(ImageJob.model == model)

    jobs = query.order_by(ImageJob.created_at.desc()).offset(offset).limit(limit).all()
    return jobs


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
            detail=f"Unsupported file format. Supported: {SUPPORTED_FORMATS}"
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

