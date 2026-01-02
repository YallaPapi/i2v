from contextlib import asynccontextmanager
from typing import Optional, List
import structlog

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import Job
from app.schemas import JobCreate, JobResponse, HealthResponse

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
    yield
    # Shutdown
    logger.info("Shutting down i2v service")


app = FastAPI(
    title="i2v - Image to Video Service",
    description="Backend service for Wan 2.5 image-to-video generation via Fal API",
    version="1.0.0",
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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new video generation job."""
    job = Job(
        image_url=job_data.image_url,
        motion_prompt=job_data.motion_prompt,
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
