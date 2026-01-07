"""Pipeline management API endpoints."""

from typing import Optional, List
from decimal import Decimal
import structlog
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func

from app.database import get_db
from app.models import Pipeline, PipelineStep, PipelineStatus, StepStatus
from app.schemas import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineSummary,
    PipelineSummaryListResponse,
    PipelineStepResponse,
    PromptEnhanceRequest,
    PromptEnhanceResponse,
    CostEstimateRequest,
    CostEstimateResponse,
    BulkPipelineCreate,
    BulkPipelineResponse,
    BulkCostEstimateResponse,
    BulkCostBreakdown,
    BulkPipelineTotals,
    SourceGroupOutput,
    AnimateSelectedRequest,
)
from app.services.prompt_enhancer import prompt_enhancer
from app.services.cost_calculator import cost_calculator
from app.services.pipeline_executor import pipeline_executor
from app.services.generation_service import generate_image, generate_video
from app.services.thumbnail import generate_thumbnails_batch
from app.services.cache import (
    cache_get,
    cache_set,
    invalidate_pipelines_cache,
    make_cache_key,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# ============== Pipeline CRUD ==============


@router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    pipeline_data: PipelineCreate,
    db: Session = Depends(get_db),
):
    """Create a new pipeline with steps."""
    # Create pipeline
    pipeline = Pipeline(
        name=pipeline_data.name,
        mode=pipeline_data.mode,
        status=PipelineStatus.PENDING.value,
        description=pipeline_data.description,
    )

    if pipeline_data.checkpoints:
        pipeline.set_checkpoints(pipeline_data.checkpoints)

    if pipeline_data.tags:
        pipeline.set_tags(pipeline_data.tags)

    db.add(pipeline)
    db.flush()  # Get pipeline ID

    # Create steps
    for step_data in pipeline_data.steps:
        step = PipelineStep(
            pipeline_id=pipeline.id,
            step_type=step_data.step_type,
            step_order=step_data.step_order,
            status=StepStatus.PENDING.value,
        )
        step.set_config(step_data.config)
        if step_data.inputs:
            step.set_inputs(step_data.inputs)

        # Calculate cost estimate
        cost_info = _calculate_step_cost_estimate(step_data.step_type, step_data.config)
        step.cost_estimate = cost_info.get("total", 0)

        db.add(step)

    db.commit()
    db.refresh(pipeline)

    await invalidate_pipelines_cache()
    logger.info("Pipeline created", pipeline_id=pipeline.id, steps=len(pipeline.steps))
    return pipeline


@router.get("", response_model=PipelineSummaryListResponse)
async def list_pipelines(
    status: Optional[str] = Query(None, description="Filter by status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    favorites: bool = Query(False, description="Show only favorites"),
    hidden: bool = Query(False, description="Include hidden pipelines"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all pipelines with lightweight summaries (no steps/outputs loaded)."""
    import json

    # Check Redis cache first
    cache_key = make_cache_key(
        "pipelines",
        status=status,
        tag=tag,
        favorites=favorites,
        hidden=hidden,
        limit=limit,
        offset=offset,
    )
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Cache hit", key=cache_key)
        return json.loads(cached)

    # Base query - only load pipeline columns, NOT relationships
    query = db.query(Pipeline).options(
        load_only(
            Pipeline.id,
            Pipeline.name,
            Pipeline.status,
            Pipeline.created_at,
            Pipeline.updated_at,
            Pipeline.tags,
            Pipeline.is_favorite,
            Pipeline.is_hidden,
        )
    )

    if status:
        valid_statuses = ["pending", "running", "paused", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )
        query = query.filter(Pipeline.status == status)

    # Filter by tag (search in JSON array)
    if tag:
        query = query.filter(Pipeline.tags.like(f'%"{tag}"%'))

    # Filter favorites
    if favorites:
        query = query.filter(Pipeline.is_favorite == 1)

    # Hide hidden unless explicitly requested
    if not hidden:
        query = query.filter(Pipeline.is_hidden == 0)

    total = query.count()
    pipelines = (
        query.order_by(Pipeline.created_at.desc()).offset(offset).limit(limit).all()
    )

    # Get step counts and summary info efficiently
    pipeline_ids = [p.id for p in pipelines]

    step_summaries = {}
    if pipeline_ids:
        # Query step counts, cost, and output counts using SQLite JSON function
        from sqlalchemy import text

        # Step counts and costs (fast aggregation)
        step_query = (
            db.query(
                PipelineStep.pipeline_id,
                func.count(PipelineStep.id).label("step_count"),
                func.sum(PipelineStep.cost_actual).label("total_cost"),
            )
            .filter(PipelineStep.pipeline_id.in_(pipeline_ids))
            .group_by(PipelineStep.pipeline_id)
            .all()
        )

        for row in step_query:
            step_summaries[row.pipeline_id] = {
                "step_count": row.step_count,
                "total_cost": float(row.total_cost) if row.total_cost else None,
                "output_count": 0,
            }

        # Count outputs using SQL JSON function (much faster than loading all JSON)
        # Use raw connection for SQLite-specific JSON functions
        # Note: pipeline_ids are integers from DB query, safe to format directly
        # Using numbered params for explicit parameterization
        params = {f"id_{i}": pid for i, pid in enumerate(pipeline_ids)}
        placeholders = ",".join([f":id_{i}" for i in range(len(pipeline_ids))])
        output_count_sql = f"""
            SELECT pipeline_id,
                   SUM(COALESCE(json_array_length(json_extract(outputs, '$.items')), 0)) as output_count
            FROM pipeline_steps
            WHERE pipeline_id IN ({placeholders}) AND outputs IS NOT NULL
            GROUP BY pipeline_id
        """
        output_counts = db.execute(text(output_count_sql), params).fetchall()
        for row in output_counts:
            if row[0] in step_summaries:
                step_summaries[row[0]]["output_count"] = row[1] or 0

        # Get ONLY first step (step_order == 0) for model/prompt/thumbnail - single query
        first_steps = (
            db.query(PipelineStep)
            .options(
                load_only(
                    PipelineStep.id,
                    PipelineStep.pipeline_id,
                    PipelineStep.config,
                    PipelineStep.inputs,
                    PipelineStep.outputs,
                )
            )
            .filter(
                PipelineStep.pipeline_id.in_(pipeline_ids), PipelineStep.step_order == 0
            )
            .all()
        )

        for step in first_steps:
            config = step.get_config()
            inputs = step.get_inputs()
            outputs = step.get_outputs()
            items = outputs.get("items", [])
            thumbnail_urls = outputs.get("thumbnail_urls", [])

            model = config.get("model", "")
            quality = config.get("quality", "")
            resolution = config.get("resolution", "")
            duration = config.get("duration_sec", "")

            # Build model_info with relevant details
            info_parts = [model]
            if resolution:
                info_parts.append(resolution)
            if duration:
                info_parts.append(f"{duration}s")
            # Only show quality for gpt-image models
            if quality and model.startswith("gpt-image"):
                info_parts.append(quality)
            model_info = " • ".join(info_parts)

            prompts = inputs.get("prompts", [])
            first_prompt = (
                prompts[0][:80] + "..."
                if prompts and len(prompts[0]) > 80
                else (prompts[0] if prompts else None)
            )
            first_thumb = (
                thumbnail_urls[0]
                if thumbnail_urls
                else (items[0].get("url") if items else None)
            )

            if step.pipeline_id not in step_summaries:
                step_summaries[step.pipeline_id] = {}

            step_summaries[step.pipeline_id].update(
                {
                    "model_info": model_info,
                    "first_prompt": first_prompt,
                    "first_thumbnail_url": first_thumb,
                }
            )

    # Build lightweight response
    summaries = []
    for p in pipelines:
        summary_data = step_summaries.get(p.id, {})
        summaries.append(
            PipelineSummary(
                id=p.id,
                name=p.name,
                status=p.status,
                created_at=p.created_at,
                updated_at=p.updated_at,
                tags=json.loads(p.tags) if p.tags else None,
                is_favorite=bool(p.is_favorite),
                is_hidden=bool(p.is_hidden),
                step_count=summary_data.get("step_count", 0),
                total_cost=summary_data.get("total_cost"),
                model_info=summary_data.get("model_info"),
                first_prompt=summary_data.get("first_prompt"),
                first_thumbnail_url=summary_data.get("first_thumbnail_url"),
                output_count=summary_data.get("output_count", 0),
            )
        )

    # Cache response before returning
    response = {"pipelines": summaries, "total": total}
    await cache_set(cache_key, json.dumps(response, default=str))
    return response


# ============== Download Proxy ==============
# NOTE: This must come BEFORE /{pipeline_id} routes to avoid route conflict


@router.get("/download")
async def download_file(url: str = Query(..., description="URL of file to download")):
    """Proxy download to avoid CORS issues with external CDNs."""
    from urllib.parse import urlparse

    # Validate URL is from allowed domains
    allowed_domains = ["fal.media", "fal.ai", "r2.dev", "r2.cloudflarestorage.com"]
    parsed = urlparse(url)

    if not any(domain in parsed.netloc for domain in allowed_domains):
        raise HTTPException(status_code=400, detail="URL not from allowed domain")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get(
                "content-type", "application/octet-stream"
            )
            filename = parsed.path.split("/")[-1] or "download"

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except httpx.HTTPError as e:
        logger.error("Download proxy failed", url=url, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch file: {str(e)}")


# ============== Server Restart ==============
# NOTE: This must come BEFORE /{pipeline_id} routes to avoid route conflict


@router.post("/restart")
async def restart_server():
    """Restart the server by touching main.py to trigger uvicorn reload."""
    from pathlib import Path
    import app.main
    main_file = Path(app.main.__file__)
    main_file.touch()
    logger.info("Server restart triggered via API")
    return {"status": "restarting", "message": "Server will restart in ~1 second"}


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific pipeline by ID."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    update_data: PipelineUpdate,
    db: Session = Depends(get_db),
):
    """Update a pipeline's configuration."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipeline.status == PipelineStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot update a running pipeline")

    if update_data.name is not None:
        pipeline.name = update_data.name
    if update_data.mode is not None:
        pipeline.mode = update_data.mode
    if update_data.checkpoints is not None:
        pipeline.set_checkpoints(update_data.checkpoints)
    if update_data.tags is not None:
        pipeline.set_tags(update_data.tags)
    if update_data.is_favorite is not None:
        pipeline.is_favorite = 1 if update_data.is_favorite else 0
    if update_data.is_hidden is not None:
        pipeline.is_hidden = 1 if update_data.is_hidden else 0
    if update_data.description is not None:
        pipeline.description = update_data.description

    db.commit()
    db.refresh(pipeline)

    await invalidate_pipelines_cache()
    return pipeline


@router.put("/{pipeline_id}/favorite", response_model=PipelineResponse)
async def toggle_favorite(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Toggle favorite status for a pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline.is_favorite = 0 if pipeline.is_favorite else 1
    db.commit()
    db.refresh(pipeline)

    await invalidate_pipelines_cache()
    return pipeline


@router.put("/{pipeline_id}/hide", response_model=PipelineResponse)
async def toggle_hidden(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Toggle hidden status for a pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline.is_hidden = 0 if pipeline.is_hidden else 1
    db.commit()
    db.refresh(pipeline)

    await invalidate_pipelines_cache()
    return pipeline


@router.put("/{pipeline_id}/tags", response_model=PipelineResponse)
async def update_tags(
    pipeline_id: int,
    tags: List[str],
    db: Session = Depends(get_db),
):
    """Update tags for a pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline.set_tags(tags)
    db.commit()
    db.refresh(pipeline)

    await invalidate_pipelines_cache()
    return pipeline


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Delete a pipeline and all its steps."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipeline.status == PipelineStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete a running pipeline")

    db.delete(pipeline)
    db.commit()
    await invalidate_pipelines_cache()

    logger.info("Pipeline deleted", pipeline_id=pipeline_id)


# ============== Pipeline Execution ==============


async def _execute_pipeline_task(pipeline_id: int):
    """Background task to execute a pipeline."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # Define generation functions that match executor's expected signatures
        async def image_generator(
            source_image_url: str,
            prompt: str,
            model: str,
            num_images: int = 1,
            aspect_ratio: str = "9:16",
            quality: str = "high",
            negative_prompt: str = None,
            # FLUX-specific parameters
            flux_strength: float = None,
            flux_guidance_scale: float = None,
            flux_num_inference_steps: int = None,
            flux_seed: int = None,
            flux_scheduler: str = None,
        ):
            urls = await generate_image(
                image_url=source_image_url,
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                quality=quality,
                num_images=num_images,
                negative_prompt=negative_prompt,
                flux_strength=flux_strength,
                flux_guidance_scale=flux_guidance_scale,
                flux_num_inference_steps=flux_num_inference_steps,
                flux_seed=flux_seed,
                flux_scheduler=flux_scheduler,
            )
            return urls

        async def video_generator(
            image_url: str,
            motion_prompt: str,
            model: str,
            resolution: str = "1080p",
            duration_sec: int = 5,
            enable_audio: bool = False,
        ):
            url = await generate_video(
                image_url=image_url,
                prompt=motion_prompt,
                model=model,
                resolution=resolution,
                duration_sec=duration_sec,
                enable_audio=enable_audio,
            )
            return url

        await pipeline_executor.execute_pipeline(
            db=db,
            pipeline_id=pipeline_id,
            generate_images_fn=image_generator,
            generate_videos_fn=video_generator,
        )
    except Exception as e:
        logger.error("Pipeline execution failed", pipeline_id=pipeline_id, error=str(e))
        # Update status to failed
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if pipeline:
            pipeline.status = PipelineStatus.FAILED.value
            db.commit()
    finally:
        db.close()


@router.post("/{pipeline_id}/run", response_model=PipelineResponse)
async def run_pipeline(
    pipeline_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start or resume a pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipeline.status == PipelineStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    if pipeline.status == PipelineStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Pipeline is already completed")

    # Update status immediately
    pipeline.status = PipelineStatus.RUNNING.value
    db.commit()

    logger.info("Pipeline execution starting", pipeline_id=pipeline_id)

    # Execute in background
    background_tasks.add_task(_execute_pipeline_task, pipeline_id)

    db.refresh(pipeline)
    return pipeline


@router.post("/{pipeline_id}/pause", response_model=PipelineResponse)
async def pause_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Pause a running pipeline at the next checkpoint."""
    try:
        pipeline = await pipeline_executor.pause_pipeline(db, pipeline_id)
        return pipeline
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{pipeline_id}/cancel", response_model=PipelineResponse)
async def cancel_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Cancel a running or paused pipeline."""
    try:
        pipeline = await pipeline_executor.cancel_pipeline(db, pipeline_id)
        return pipeline
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Step Management ==============


@router.get("/{pipeline_id}/steps", response_model=List[PipelineStepResponse])
async def list_steps(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """List all steps for a pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    steps = sorted(pipeline.steps, key=lambda s: s.step_order)
    return steps


@router.get("/{pipeline_id}/steps/{step_id}", response_model=PipelineStepResponse)
async def get_step(
    pipeline_id: int,
    step_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific step."""
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.id == step_id, PipelineStep.pipeline_id == pipeline_id)
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    return step


@router.put("/{pipeline_id}/steps/{step_id}", response_model=PipelineStepResponse)
async def update_step(
    pipeline_id: int,
    step_id: int,
    config: dict,
    db: Session = Depends(get_db),
):
    """Update a step's configuration (only in pending/review status)."""
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.id == step_id, PipelineStep.pipeline_id == pipeline_id)
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if step.status not in [StepStatus.PENDING.value, StepStatus.REVIEW.value]:
        raise HTTPException(
            status_code=400, detail="Can only update pending or review steps"
        )

    step.set_config(config)

    # Recalculate cost estimate
    cost_info = _calculate_step_cost_estimate(step.step_type, config)
    step.cost_estimate = cost_info.get("total", 0)

    db.commit()
    db.refresh(step)

    return step


@router.post(
    "/{pipeline_id}/steps/{step_id}/approve", response_model=PipelineStepResponse
)
async def approve_step(
    pipeline_id: int,
    step_id: int,
    db: Session = Depends(get_db),
):
    """Approve a step waiting for review and continue pipeline."""
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.id == step_id, PipelineStep.pipeline_id == pipeline_id)
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    try:
        step = await pipeline_executor.approve_step(db, step_id)
        return step
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{pipeline_id}/steps/{step_id}/retry", response_model=PipelineStepResponse
)
async def retry_step(
    pipeline_id: int,
    step_id: int,
    db: Session = Depends(get_db),
):
    """Retry a failed step."""
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.id == step_id, PipelineStep.pipeline_id == pipeline_id)
        .first()
    )

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    try:
        step = await pipeline_executor.retry_step(db, step_id)
        return step
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Prompt Enhancement ==============


@router.post("/prompts/enhance", response_model=PromptEnhanceResponse)
async def enhance_prompts(
    request: PromptEnhanceRequest,
):
    """Enhance prompts using AI."""
    try:
        # Handle raw mode - return original prompts as-is
        if request.mode == "raw":
            return {
                "original_prompts": request.prompts,
                "enhanced_prompts": [[p] for p in request.prompts],
                "total_count": len(request.prompts),
            }

        enhanced = await prompt_enhancer.enhance_bulk(
            prompts=request.prompts,
            target=request.target,
            count=request.count,
            style=request.style,
            theme_focus=request.theme_focus,
            mode=request.mode,
            categories=request.categories,
        )

        total_count = sum(len(variations) for variations in enhanced)

        return {
            "original_prompts": request.prompts,
            "enhanced_prompts": enhanced,
            "total_count": total_count,
        }
    except Exception as e:
        logger.error("Prompt enhancement failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Prompt enhancement failed: {str(e)}"
        )


@router.get("/prompts/recent")
async def get_recent_prompts(
    limit: int = Query(20, ge=1, le=100),
    step_type: Optional[str] = Query(
        None, description="Filter by step type (i2i, i2v)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get recently used prompts from pipeline steps.

    Returns unique prompts ordered by most recently used.
    """
    # Query recent steps with prompts
    query = (
        db.query(PipelineStep)
        .filter(PipelineStep.inputs.isnot(None))
        .order_by(PipelineStep.created_at.desc())
    )

    if step_type:
        if step_type not in ["i2i", "i2v"]:
            raise HTTPException(
                status_code=400, detail="step_type must be 'i2i' or 'i2v'"
            )
        query = query.filter(PipelineStep.step_type == step_type)

    # Get more steps to deduplicate
    steps = query.limit(200).all()

    # Extract unique prompts
    seen_prompts = set()
    prompts = []

    for step in steps:
        inputs = step.get_inputs()
        if inputs and inputs.get("prompts"):
            for prompt in inputs["prompts"]:
                if prompt and prompt.strip() and prompt not in seen_prompts:
                    seen_prompts.add(prompt)
                    prompts.append(
                        {
                            "prompt": prompt,
                            "step_type": step.step_type,
                            "model": step.get_config().get("model", "unknown"),
                            "used_at": (
                                step.created_at.isoformat() if step.created_at else None
                            ),
                        }
                    )
                    if len(prompts) >= limit:
                        break
        if len(prompts) >= limit:
            break

    return {
        "prompts": prompts,
        "total": len(prompts),
    }


# ============== Cost Estimation ==============


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_cost(
    request: CostEstimateRequest,
):
    """Estimate cost for a pipeline configuration."""
    steps_data = [
        {
            "step_type": step.step_type,
            "step_order": step.step_order,
            "config": step.config,
        }
        for step in request.steps
    ]

    estimate = cost_calculator.estimate_pipeline_cost(steps_data)

    return estimate


# ============== Helper Functions ==============


def _calculate_step_cost_estimate(step_type: str, config: dict) -> dict:
    """Calculate cost estimate for a single step."""
    if step_type == "prompt_enhance":
        return cost_calculator.calculate_prompt_enhance_cost(config)
    elif step_type == "i2i":
        return cost_calculator.calculate_i2i_cost(config)
    elif step_type == "i2v":
        return cost_calculator.calculate_i2v_cost(config)
    return {"total": 0}


# ============== Bulk Pipeline ==============


@router.post("/bulk/estimate", response_model=BulkCostEstimateResponse)
async def estimate_bulk_cost(
    request: BulkPipelineCreate,
):
    """Estimate cost for a bulk pipeline configuration."""
    num_sources = len(request.source_images)

    # Calculate I2I outputs
    i2i_count = 0
    i2i_cost_per_image = 0.0
    i2i_total = 0.0

    if request.i2i_config and request.i2i_config.enabled:
        i2i_prompts = len(request.i2i_config.prompts)
        images_per = request.i2i_config.images_per_prompt
        i2i_count = num_sources * i2i_prompts * images_per

        i2i_cost_info = cost_calculator.calculate_i2i_cost(
            {
                "model": request.i2i_config.model,
                "quality": request.i2i_config.quality,
                "images_per_prompt": 1,
            },
            num_inputs=1,
        )
        i2i_cost_per_image = i2i_cost_info["unit_price"]
        i2i_total = i2i_count * i2i_cost_per_image

    # Calculate I2V outputs
    # If I2I is enabled, videos are created from I2I outputs
    # Otherwise, from source images directly
    i2v_input_count = i2i_count if i2i_count > 0 else num_sources
    i2v_prompts = len(request.i2v_config.prompts)
    i2v_count = i2v_input_count * i2v_prompts

    i2v_cost_info = cost_calculator.calculate_i2v_cost(
        {
            "model": request.i2v_config.model,
            "resolution": request.i2v_config.resolution,
            "duration_sec": request.i2v_config.duration_sec,
            "videos_per_image": 1,
        },
        num_inputs=1,
    )
    i2v_cost_per_video = i2v_cost_info["unit_price"]
    i2v_total = i2v_count * i2v_cost_per_video

    grand_total = i2i_total + i2v_total

    return {
        "breakdown": BulkCostBreakdown(
            i2i_count=i2i_count,
            i2i_cost_per_image=i2i_cost_per_image,
            i2i_total=i2i_total,
            i2v_count=i2v_count,
            i2v_cost_per_video=i2v_cost_per_video,
            i2v_total=i2v_total,
            grand_total=grand_total,
        ),
        "combinations": {
            "sources": num_sources,
            "i2i_prompts": len(request.i2i_config.prompts) if request.i2i_config else 0,
            "i2v_prompts": i2v_prompts,
            "total_images": i2i_count,
            "total_videos": i2v_count,
        },
        "currency": "USD",
    }


@router.post("/bulk", response_model=BulkPipelineResponse, status_code=201)
async def create_bulk_pipeline(
    request: BulkPipelineCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create and start a bulk pipeline."""
    # Log incoming FLUX params for debugging
    if request.i2i_config:
        logger.info("Bulk pipeline FLUX params received",
                    model=request.i2i_config.model,
                    flux_strength=request.i2i_config.flux_strength,
                    flux_guidance_scale=request.i2i_config.flux_guidance_scale,
                    flux_num_inference_steps=request.i2i_config.flux_num_inference_steps,
                    flux_seed=request.i2i_config.flux_seed,
                    flux_scheduler=request.i2i_config.flux_scheduler,
                    prompts_count=len(request.i2i_config.prompts) if request.i2i_config.prompts else 0)

    # Validate inputs
    if not request.source_images:
        raise HTTPException(
            status_code=400, detail="At least one source image is required"
        )
    if len(request.source_images) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 source images allowed")

    # Check that at least one mode has prompts
    has_i2i = (
        request.i2i_config and request.i2i_config.enabled and request.i2i_config.prompts
    )
    has_i2v = request.i2v_config and request.i2v_config.prompts
    if not has_i2i and not has_i2v:
        raise HTTPException(
            status_code=400, detail="At least one prompt is required (photo or video)"
        )

    # Create pipeline
    pipeline = Pipeline(
        name=request.name,
        mode="auto",
        status=PipelineStatus.PENDING.value,
        description=request.description,
    )
    if request.tags:
        pipeline.set_tags(request.tags)

    db.add(pipeline)
    db.flush()

    step_order = 0

    # Create I2I steps for each source × prompt combination
    i2i_outputs_map = {}  # source_idx -> list of step IDs

    if request.i2i_config and request.i2i_config.enabled:
        for src_idx, source_url in enumerate(request.source_images):
            i2i_outputs_map[src_idx] = []
            for prompt_idx, prompt in enumerate(request.i2i_config.prompts):
                step = PipelineStep(
                    pipeline_id=pipeline.id,
                    step_type="i2i",
                    step_order=step_order,
                    status=StepStatus.PENDING.value,
                )
                step.set_config(
                    {
                        "model": request.i2i_config.model,
                        "images_per_prompt": request.i2i_config.images_per_prompt,
                        "aspect_ratio": request.i2i_config.aspect_ratio,
                        "quality": request.i2i_config.quality,
                        "negative_prompt": request.i2i_config.negative_prompt,
                        # FLUX-specific parameters
                        "flux_strength": request.i2i_config.flux_strength,
                        "flux_guidance_scale": request.i2i_config.flux_guidance_scale,
                        "flux_num_inference_steps": request.i2i_config.flux_num_inference_steps,
                        "flux_seed": request.i2i_config.flux_seed,
                        "flux_scheduler": request.i2i_config.flux_scheduler,
                    }
                )
                step.set_inputs(
                    {
                        "image_urls": [source_url],
                        "prompts": [prompt],
                        "source_image_index": src_idx,
                        "prompt_index": prompt_idx,
                    }
                )

                # Calculate cost estimate
                cost_info = cost_calculator.calculate_i2i_cost(step.get_config(), 1)
                step.cost_estimate = cost_info["total"]

                db.add(step)
                db.flush()
                i2i_outputs_map[src_idx].append(step.id)
                step_order += 1

    # Create I2V steps (only if we have video prompts)
    if has_i2v:
        if request.i2i_config and request.i2i_config.enabled:
            # I2V steps will be created dynamically after I2I completes
            # Store the config for the executor to use
            pipeline.set_checkpoints(
                []
            )  # Use checkpoints field to store bulk config temporarily
        else:
            # No I2I, create I2V steps directly from source images
            for src_idx, source_url in enumerate(request.source_images):
                for prompt_idx, prompt in enumerate(request.i2v_config.prompts):
                    step = PipelineStep(
                        pipeline_id=pipeline.id,
                        step_type="i2v",
                        step_order=step_order,
                        status=StepStatus.PENDING.value,
                    )
                    step.set_config(
                        {
                            "model": request.i2v_config.model,
                            "videos_per_image": 1,
                            "resolution": request.i2v_config.resolution,
                            "duration_sec": request.i2v_config.duration_sec,
                            "negative_prompt": request.i2v_config.negative_prompt,
                            "enable_audio": request.i2v_config.enable_audio,
                        }
                    )
                    step.set_inputs(
                        {
                            "image_urls": [source_url],
                            "prompts": [prompt],
                            "source_image_index": src_idx,
                            "prompt_index": prompt_idx,
                        }
                    )

                    cost_info = cost_calculator.calculate_i2v_cost(step.get_config(), 1)
                    step.cost_estimate = cost_info["total"]

                    db.add(step)
                    step_order += 1

    db.commit()
    db.refresh(pipeline)

    logger.info(
        "Bulk pipeline created", pipeline_id=pipeline.id, steps=len(pipeline.steps)
    )

    # Start execution in background
    background_tasks.add_task(_execute_bulk_pipeline_task, pipeline.id, request)

    # Return initial response
    return {
        "pipeline_id": pipeline.id,
        "name": pipeline.name,
        "status": pipeline.status,
        "groups": [
            SourceGroupOutput(
                source_image=url,
                source_index=idx,
                i2i_outputs=[],
                i2i_thumbnails=[],
                i2v_outputs=[],
            )
            for idx, url in enumerate(request.source_images)
        ],
        "totals": BulkPipelineTotals(
            source_images=len(request.source_images),
            i2i_generated=0,
            i2v_generated=0,
            total_cost=0.0,
        ),
        "created_at": pipeline.created_at,
    }


async def _execute_bulk_pipeline_task(pipeline_id: int, request: BulkPipelineCreate):
    """Background task to execute a bulk pipeline with concurrency control."""
    from app.database import SessionLocal
    import asyncio

    db = SessionLocal()
    MAX_CONCURRENT = 20
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    try:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            return

        pipeline.status = PipelineStatus.RUNNING.value
        db.commit()

        # Get all steps
        steps = sorted(pipeline.steps, key=lambda s: s.step_order)

        # Separate I2I and I2V steps
        i2i_steps = [s for s in steps if s.step_type == "i2i"]
        i2v_steps = [s for s in steps if s.step_type == "i2v"]

        async def execute_step_with_semaphore(step: PipelineStep):
            async with semaphore:
                step.status = StepStatus.RUNNING.value
                db.commit()

                try:
                    config = step.get_config()
                    inputs = step.get_inputs()

                    # Log extracted config for debugging
                    if step.step_type == "i2i":
                        logger.info("I2I step config extracted",
                                    step_id=step.id,
                                    model=config.get("model"),
                                    flux_strength=config.get("flux_strength"),
                                    flux_guidance=config.get("flux_guidance_scale"),
                                    flux_steps=config.get("flux_num_inference_steps"),
                                    flux_scheduler=config.get("flux_scheduler"),
                                    prompt=inputs.get("prompts", [""])[0][:50] if inputs.get("prompts") else "NO PROMPT")

                    if step.step_type == "i2i":
                        result = await generate_image(
                            image_url=inputs["image_urls"][0],
                            prompt=inputs["prompts"][0],
                            model=config["model"],
                            aspect_ratio=config.get("aspect_ratio", "9:16"),
                            quality=config.get("quality", "high"),
                            num_images=config.get("images_per_prompt", 1),
                            negative_prompt=config.get("negative_prompt"),
                            # FLUX-specific parameters
                            flux_strength=config.get("flux_strength"),
                            flux_guidance_scale=config.get("flux_guidance_scale"),
                            flux_num_inference_steps=config.get("flux_num_inference_steps"),
                            flux_seed=config.get("flux_seed"),
                            flux_scheduler=config.get("flux_scheduler"),
                        )
                        image_urls = result if isinstance(result, list) else [result]
                        # Generate thumbnails for fast library loading
                        thumbnail_urls = await generate_thumbnails_batch(image_urls)
                        step.set_outputs(
                            {
                                "image_urls": image_urls,
                                "thumbnail_urls": thumbnail_urls,
                                "items": [
                                    {"url": url, "type": "image"} for url in image_urls
                                ],
                                "count": len(image_urls),
                            }
                        )

                    elif step.step_type == "i2v":
                        result = await generate_video(
                            image_url=inputs["image_urls"][0],
                            prompt=inputs["prompts"][0],
                            model=config["model"],
                            resolution=config.get("resolution", "1080p"),
                            duration_sec=config.get("duration_sec", 5),
                            negative_prompt=config.get("negative_prompt"),
                            enable_audio=config.get("enable_audio", False),
                        )
                        step.set_outputs(
                            {
                                "video_urls": [result],
                                "items": [{"url": result, "type": "video"}],
                                "count": 1,
                            }
                        )

                    step.status = StepStatus.COMPLETED.value

                    # Calculate actual cost
                    if step.step_type == "i2i":
                        cost_info = cost_calculator.calculate_i2i_cost(config, 1)
                    else:
                        cost_info = cost_calculator.calculate_i2v_cost(config, 1)
                    step.cost_actual = cost_info["total"]

                except Exception as e:
                    step.status = StepStatus.FAILED.value
                    step.error_message = str(e)
                    logger.error("Step failed", step_id=step.id, error=str(e))

                db.commit()
                return step

        # Execute I2I steps concurrently
        if i2i_steps:
            await asyncio.gather(*[execute_step_with_semaphore(s) for s in i2i_steps])

            # If there are I2I steps and I2V config, create I2V steps for each I2I output
            if request.i2v_config:
                step_order = len(i2i_steps)
                for i2i_step in i2i_steps:
                    if i2i_step.status != StepStatus.COMPLETED.value:
                        continue

                    outputs = i2i_step.get_outputs()
                    inputs = i2i_step.get_inputs()
                    src_idx = inputs.get("source_image_index", 0)

                    for output_url in outputs.get("image_urls", []):
                        for prompt_idx, prompt in enumerate(request.i2v_config.prompts):
                            step = PipelineStep(
                                pipeline_id=pipeline.id,
                                step_type="i2v",
                                step_order=step_order,
                                status=StepStatus.PENDING.value,
                            )
                            step.set_config(
                                {
                                    "model": request.i2v_config.model,
                                    "videos_per_image": 1,
                                    "resolution": request.i2v_config.resolution,
                                    "duration_sec": request.i2v_config.duration_sec,
                                    "negative_prompt": request.i2v_config.negative_prompt,
                                    "enable_audio": request.i2v_config.enable_audio,
                                }
                            )
                            step.set_inputs(
                                {
                                    "image_urls": [output_url],
                                    "prompts": [prompt],
                                    "source_image_index": src_idx,
                                    "prompt_index": prompt_idx,
                                    "from_i2i_step": i2i_step.id,
                                }
                            )

                            cost_info = cost_calculator.calculate_i2v_cost(
                                step.get_config(), 1
                            )
                            step.cost_estimate = cost_info["total"]

                            db.add(step)
                            step_order += 1

                db.commit()

                # Get newly created I2V steps
                i2v_steps = [s for s in pipeline.steps if s.step_type == "i2v"]

        # Execute I2V steps concurrently
        if i2v_steps:
            await asyncio.gather(*[execute_step_with_semaphore(s) for s in i2v_steps])

        # Check if all steps completed
        db.refresh(pipeline)
        all_steps = pipeline.steps
        if all(s.status == StepStatus.COMPLETED.value for s in all_steps):
            pipeline.status = PipelineStatus.COMPLETED.value
        elif any(s.status == StepStatus.FAILED.value for s in all_steps):
            pipeline.status = PipelineStatus.FAILED.value

        db.commit()
        logger.info("Bulk pipeline completed", pipeline_id=pipeline_id)

    except Exception as e:
        logger.error(
            "Bulk pipeline execution failed", pipeline_id=pipeline_id, error=str(e)
        )
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if pipeline:
            pipeline.status = PipelineStatus.FAILED.value
            db.commit()
    finally:
        db.close()


@router.get("/bulk/{pipeline_id}", response_model=BulkPipelineResponse)
async def get_bulk_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
):
    """Get bulk pipeline status with grouped outputs."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Group outputs by source image
    groups: dict = {}
    total_cost = Decimal("0")

    for step in pipeline.steps:
        inputs = step.get_inputs()
        outputs = step.get_outputs()
        src_idx = inputs.get("source_image_index", 0)
        src_url = inputs.get("image_urls", [""])[0] if inputs.get("image_urls") else ""

        if src_idx not in groups:
            groups[src_idx] = SourceGroupOutput(
                source_image=src_url,
                source_index=src_idx,
                i2i_outputs=[],
                i2i_thumbnails=[],
                i2v_outputs=[],
            )

        if step.status == StepStatus.COMPLETED.value and outputs:
            if step.step_type == "i2i":
                groups[src_idx].i2i_outputs.extend(outputs.get("image_urls", []))
                groups[src_idx].i2i_thumbnails.extend(outputs.get("thumbnail_urls", []))
            elif step.step_type == "i2v":
                groups[src_idx].i2v_outputs.extend(outputs.get("video_urls", []))

        if step.cost_actual:
            total_cost += step.cost_actual

    # Count totals
    i2i_generated = sum(len(g.i2i_outputs) for g in groups.values())
    i2v_generated = sum(len(g.i2v_outputs) for g in groups.values())

    return {
        "pipeline_id": pipeline.id,
        "name": pipeline.name,
        "status": pipeline.status,
        "groups": list(groups.values()),
        "totals": BulkPipelineTotals(
            source_images=len(groups),
            i2i_generated=i2i_generated,
            i2v_generated=i2v_generated,
            total_cost=float(total_cost),
        ),
        "created_at": pipeline.created_at,
    }


# ============== Animate Selected Images ==============


@router.post("/animate", response_model=BulkPipelineResponse)
async def animate_selected_images(
    request: AnimateSelectedRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create videos from selected images.

    This endpoint takes a list of image URLs and motion prompts,
    and generates videos for each combination (or 1:1 pairing).
    """
    import asyncio

    if not request.image_urls:
        raise HTTPException(
            status_code=400, detail="At least one image URL is required"
        )
    if not request.prompts:
        raise HTTPException(
            status_code=400, detail="At least one motion prompt is required"
        )

    # Create pipeline
    pipeline = Pipeline(
        name=request.name,
        status=PipelineStatus.PENDING.value,
        mode="auto",
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    # Create i2v steps - each image × each prompt
    step_order = 0
    for img_idx, image_url in enumerate(request.image_urls):
        for prompt_idx, prompt in enumerate(request.prompts):
            step = PipelineStep(
                pipeline_id=pipeline.id,
                step_type="i2v",
                step_order=step_order,
                status=StepStatus.PENDING.value,
            )
            step.set_config(
                {
                    "model": request.model,
                    "resolution": request.resolution,
                    "duration_sec": request.duration_sec,
                    "negative_prompt": request.negative_prompt,
                    "enable_audio": request.enable_audio,
                }
            )
            step.set_inputs(
                {
                    "image_urls": [image_url],
                    "prompts": [prompt],
                    "source_image_index": img_idx,
                    "prompt_index": prompt_idx,
                }
            )

            cost_info = cost_calculator.calculate_i2v_cost(step.get_config(), 1)
            step.cost_estimate = cost_info["total"]

            db.add(step)
            step_order += 1

    db.commit()

    # Start execution in background
    pipeline.status = PipelineStatus.RUNNING.value
    db.commit()

    pipeline_id = pipeline.id

    async def execute_animate():
        """Execute all i2v steps concurrently."""
        session = next(get_db())
        try:
            pipeline = (
                session.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
            )
            if not pipeline:
                return

            steps = [s for s in pipeline.steps if s.step_type == "i2v"]

            semaphore = asyncio.Semaphore(20)  # Max 20 concurrent

            async def execute_step(step):
                async with semaphore:
                    try:
                        step.status = StepStatus.RUNNING.value
                        session.commit()

                        config = step.get_config()
                        inputs = step.get_inputs()

                        result = await generate_video(
                            image_url=inputs["image_urls"][0],
                            prompt=inputs["prompts"][0],
                            model=config["model"],
                            resolution=config.get("resolution", "1080p"),
                            duration_sec=config.get("duration_sec", 5),
                            negative_prompt=config.get("negative_prompt"),
                            enable_audio=config.get("enable_audio", False),
                        )

                        if result.get("video_url"):
                            step.set_outputs({"video_urls": [result["video_url"]]})
                            step.status = StepStatus.COMPLETED.value
                            step.cost_actual = Decimal(str(result.get("cost", 0)))
                        else:
                            step.status = StepStatus.FAILED.value
                            step.error_message = result.get("error", "Unknown error")

                    except Exception as e:
                        step.status = StepStatus.FAILED.value
                        step.error_message = str(e)
                        logger.error(
                            "Animate step failed", step_id=step.id, error=str(e)
                        )
                    finally:
                        session.commit()

            await asyncio.gather(*[execute_step(s) for s in steps])

            # Update pipeline status
            session.refresh(pipeline)
            if all(s.status == StepStatus.COMPLETED.value for s in pipeline.steps):
                pipeline.status = PipelineStatus.COMPLETED.value
            elif any(s.status == StepStatus.FAILED.value for s in pipeline.steps):
                pipeline.status = PipelineStatus.FAILED.value
            session.commit()

        except Exception as e:
            logger.error(
                "Animate pipeline failed", pipeline_id=pipeline_id, error=str(e)
            )
            pipeline = (
                session.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
            )
            if pipeline:
                pipeline.status = PipelineStatus.FAILED.value
                session.commit()
        finally:
            session.close()

    background_tasks.add_task(asyncio.create_task, execute_animate())

    # Return initial response with empty groups
    groups = {}
    for idx, image_url in enumerate(request.image_urls):
        groups[idx] = SourceGroupOutput(
            source_image=image_url,
            source_index=idx,
            i2i_outputs=[],
            i2i_thumbnails=[],
            i2v_outputs=[],
        )

    return {
        "pipeline_id": pipeline.id,
        "name": pipeline.name,
        "status": pipeline.status,
        "groups": list(groups.values()),
        "totals": BulkPipelineTotals(
            source_images=len(request.image_urls),
            i2i_generated=0,
            i2v_generated=0,
            total_cost=0.0,
        ),
        "created_at": pipeline.created_at,
    }


# ============== Image Library ==============


@router.get("/images/library")
async def get_image_library(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get recently generated images from i2i steps.

    Returns a list of images that can be selected for video generation.
    """
    # Get all completed i2i steps with outputs
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.step_type == "i2i")
        .filter(PipelineStep.status == StepStatus.COMPLETED.value)
        .order_by(PipelineStep.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    images = []
    for step in steps:
        outputs = step.get_outputs()
        inputs = step.get_inputs()
        config = step.get_config()

        if outputs and outputs.get("image_urls"):
            image_urls = outputs["image_urls"]
            thumbnail_urls = outputs.get("thumbnail_urls", [])

            for i, url in enumerate(image_urls):
                # Get corresponding thumbnail if available
                thumbnail_url = thumbnail_urls[i] if i < len(thumbnail_urls) else None

                images.append(
                    {
                        "url": url,
                        "thumbnail_url": thumbnail_url,
                        "step_id": step.id,
                        "pipeline_id": step.pipeline_id,
                        "source_image": (
                            inputs.get("image_urls", [""])[0]
                            if inputs.get("image_urls")
                            else None
                        ),
                        "prompt": (
                            inputs.get("prompts", [""])[0]
                            if inputs.get("prompts")
                            else None
                        ),
                        "model": config.get("model", "unknown"),
                        "created_at": (
                            step.updated_at.isoformat() if step.updated_at else None
                        ),
                    }
                )

    # Get total count
    total = (
        db.query(PipelineStep)
        .filter(PipelineStep.step_type == "i2i")
        .filter(PipelineStep.status == StepStatus.COMPLETED.value)
        .count()
    )

    return {
        "images": images,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/images/library/generate-thumbnails")
async def generate_library_thumbnails(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Generate thumbnails for existing images that don't have them.

    Call this to backfill thumbnails for images created before thumbnail support.
    """
    # Get i2i steps that have images but no thumbnails
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.step_type == "i2i")
        .filter(PipelineStep.status == StepStatus.COMPLETED.value)
        .order_by(PipelineStep.updated_at.desc())
        .limit(limit)
        .all()
    )

    processed = 0
    skipped = 0

    for step in steps:
        outputs = step.get_outputs()
        if not outputs or not outputs.get("image_urls"):
            continue

        # Skip if thumbnails already exist
        existing_thumbs = outputs.get("thumbnail_urls", [])
        if existing_thumbs and len(existing_thumbs) == len(outputs["image_urls"]):
            skipped += 1
            continue

        # Generate thumbnails
        image_urls = outputs["image_urls"]
        thumbnail_urls = await generate_thumbnails_batch(image_urls)

        # Update outputs
        outputs["thumbnail_urls"] = thumbnail_urls
        step.set_outputs(outputs)
        db.commit()
        processed += 1

    return {
        "processed": processed,
        "skipped": skipped,
        "message": f"Generated thumbnails for {processed} steps, skipped {skipped} (already had thumbnails)",
    }
