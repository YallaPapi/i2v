"""Batch jobs router for bulk content generation."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models import User, BatchJob, BatchJobItem, BatchJobStatus
from app.core.security import get_current_user
from app.services.batch_queue import get_batch_queue, JobState
from app.services.credits import InsufficientCreditsError, calculate_job_cost

logger = structlog.get_logger()

router = APIRouter(prefix="/batch-jobs", tags=["batch-jobs"])


# ============== Schemas ==============


class BatchJobConfig(BaseModel):
    """Configuration for batch generation."""
    model: str = Field(..., description="Model to use for generation")
    quality: Optional[str] = Field("high", description="Quality level")
    aspect_ratio: Optional[str] = Field("9:16", description="Aspect ratio")
    duration_sec: Optional[int] = Field(5, description="Video duration (for video output)")
    nsfw: Optional[bool] = Field(False, description="Whether this is NSFW content")


class ItemSpec(BaseModel):
    """Specification for a single item in the batch."""
    prompt: Optional[str] = None
    caption: Optional[str] = None
    variation_params: Optional[dict] = None


class CreateBatchJobRequest(BaseModel):
    """Request to create a new batch job."""
    output_type: str = Field(..., description="Type: image, video, carousel, pipeline")
    quantity: int = Field(..., ge=1, le=500, description="Number of items to generate")
    config: BatchJobConfig
    template_id: Optional[str] = Field(None, description="Template to use")
    model_profile_id: Optional[int] = Field(None, description="Model profile for face consistency")
    item_specs: Optional[List[ItemSpec]] = Field(None, description="Per-item specifications")


class BatchJobResponse(BaseModel):
    """Response for a batch job."""
    job_id: str
    user_id: int
    template_id: Optional[str]
    model_profile_id: Optional[int]
    output_type: str
    quantity: int
    config: dict
    status: str
    completed_items: int
    failed_items: int
    pending_items: int
    progress_percent: float
    credits_charged: int
    estimated_completion: Optional[str]
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error_message: Optional[str]


class BatchJobListResponse(BaseModel):
    """Response for batch job list."""
    jobs: List[BatchJobResponse]
    total: int


class BatchJobItemResponse(BaseModel):
    """Response for a batch job item."""
    id: int
    item_index: int
    prompt: Optional[str]
    caption: Optional[str]
    status: str
    result_url: Optional[str]
    thumbnail_url: Optional[str]
    error_message: Optional[str]
    duration_ms: Optional[int]


class CostPreviewResponse(BaseModel):
    """Preview of job cost before creation."""
    output_type: str
    quantity: int
    credits_per_item: int
    total_credits: int
    current_balance: int
    sufficient: bool


# ============== Endpoints ==============


@router.post("/preview-cost", response_model=CostPreviewResponse)
async def preview_job_cost(
    request: CreateBatchJobRequest,
    user: User = Depends(get_current_user),
):
    """Preview the credit cost for a batch job before creating it."""
    config_dict = request.config.model_dump()
    total = calculate_job_cost(request.output_type, request.quantity, config_dict)
    credits_per = total // request.quantity if request.quantity > 0 else 0

    return CostPreviewResponse(
        output_type=request.output_type,
        quantity=request.quantity,
        credits_per_item=credits_per,
        total_credits=total,
        current_balance=user.credits_balance,
        sufficient=user.credits_balance >= total,
    )


@router.post("", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_job(
    request: CreateBatchJobRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new batch generation job.

    - Validates user has sufficient credits
    - Checks concurrent job limits based on tier
    - Charges credits upfront
    - Starts processing in background
    """
    queue = get_batch_queue()

    # Convert to dict for config
    config_dict = request.config.model_dump()
    item_specs_list = [spec.model_dump() for spec in request.item_specs] if request.item_specs else None

    try:
        job_id = await queue.submit_job(
            user_id=user.id,
            output_type=request.output_type,
            quantity=request.quantity,
            config=config_dict,
            template_id=request.template_id,
            model_profile_id=request.model_profile_id,
            item_specs=item_specs_list,
        )

        # Fetch the created job
        job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=500, detail="Job created but not found")

        return BatchJobResponse(
            job_id=job.job_id,
            user_id=job.user_id,
            template_id=job.template_id,
            model_profile_id=job.model_profile_id,
            output_type=job.output_type,
            quantity=job.quantity,
            config=job.get_config(),
            status=job.status,
            completed_items=job.completed_items,
            failed_items=job.failed_items,
            pending_items=job.pending_items,
            progress_percent=job.progress_percent,
            credits_charged=job.credits_charged,
            estimated_completion=job.estimated_completion.isoformat() if job.estimated_completion else None,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            error_message=job.error_message,
        )

    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits: need {e.required}, have {e.available}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=BatchJobListResponse)
async def list_batch_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all batch jobs for the current user."""
    query = db.query(BatchJob).filter(BatchJob.user_id == user.id)

    if status_filter:
        query = query.filter(BatchJob.status == status_filter)

    total = query.count()
    jobs = query.order_by(BatchJob.created_at.desc()).offset(offset).limit(limit).all()

    return BatchJobListResponse(
        jobs=[
            BatchJobResponse(
                job_id=job.job_id,
                user_id=job.user_id,
                template_id=job.template_id,
                model_profile_id=job.model_profile_id,
                output_type=job.output_type,
                quantity=job.quantity,
                config=job.get_config(),
                status=job.status,
                completed_items=job.completed_items,
                failed_items=job.failed_items,
                pending_items=job.pending_items,
                progress_percent=job.progress_percent,
                credits_charged=job.credits_charged,
                estimated_completion=job.estimated_completion.isoformat() if job.estimated_completion else None,
                created_at=job.created_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                finished_at=job.finished_at.isoformat() if job.finished_at else None,
                error_message=job.error_message,
            )
            for job in jobs
        ],
        total=total,
    )


@router.get("/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific batch job."""
    job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Try to get live state from in-memory queue
    queue = get_batch_queue()
    state = queue.get_state(job_id)

    # Use in-memory state if available and fresher
    completed = state.completed if state else job.completed_items
    failed = state.failed if state else job.failed_items
    pending = state.pending if state else job.pending_items
    current_status = state.status if state else job.status

    return BatchJobResponse(
        job_id=job.job_id,
        user_id=job.user_id,
        template_id=job.template_id,
        model_profile_id=job.model_profile_id,
        output_type=job.output_type,
        quantity=job.quantity,
        config=job.get_config(),
        status=current_status,
        completed_items=completed,
        failed_items=failed,
        pending_items=pending,
        progress_percent=round((completed + failed) / job.quantity * 100, 1) if job.quantity > 0 else 100,
        credits_charged=job.credits_charged,
        estimated_completion=job.estimated_completion.isoformat() if job.estimated_completion else None,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        error_message=job.error_message,
    )


@router.get("/{job_id}/items", response_model=List[BatchJobItemResponse])
async def get_batch_job_items(
    job_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get items for a specific batch job."""
    job = db.query(BatchJob).filter(BatchJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(BatchJobItem).filter(BatchJobItem.batch_job_id == job.id)

    if status_filter:
        query = query.filter(BatchJobItem.status == status_filter)

    items = query.order_by(BatchJobItem.item_index).offset(offset).limit(limit).all()

    return [
        BatchJobItemResponse(
            id=item.id,
            item_index=item.item_index,
            prompt=item.prompt,
            caption=item.caption,
            status=item.status,
            result_url=item.result_url,
            thumbnail_url=item.thumbnail_url,
            error_message=item.error_message,
            duration_ms=item.duration_ms,
        )
        for item in items
    ]


@router.post("/{job_id}/cancel")
async def cancel_batch_job(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Cancel a running or queued batch job."""
    queue = get_batch_queue()

    try:
        cancelled = await queue.cancel_job(job_id, user.id)
        if not cancelled:
            raise HTTPException(
                status_code=400,
                detail="Job cannot be cancelled (not found or already finished)",
            )
        return {"success": True, "message": "Job cancelled"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
