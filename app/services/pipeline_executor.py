"""Pipeline execution engine."""

import asyncio
from typing import Optional, Callable, Awaitable
import structlog
from sqlalchemy.orm import Session

from app.models import Pipeline, PipelineStep, PipelineStatus, StepStatus, StepType
from app.services.prompt_enhancer import prompt_enhancer
from app.services.cost_calculator import cost_calculator
from app.services.thumbnail import generate_thumbnails_batch
from app.services.r2_cache import cache_videos_batch, cache_images_batch

logger = structlog.get_logger()


# Type for broadcast callback
BroadcastCallback = Callable[[int, str, dict], Awaitable[None]]


class PipelineExecutor:
    """Service for executing pipelines."""

    def __init__(self):
        self._broadcast_callback: Optional[BroadcastCallback] = None

    def set_broadcast_callback(self, callback: BroadcastCallback):
        """Set callback for broadcasting status updates."""
        self._broadcast_callback = callback

    async def _broadcast(self, pipeline_id: int, event: str, data: dict):
        """Broadcast event if callback is set."""
        if self._broadcast_callback:
            try:
                await self._broadcast_callback(pipeline_id, event, data)
            except Exception as e:
                logger.error("Broadcast failed", error=str(e))

    async def execute_pipeline(
        self,
        db: Session,
        pipeline_id: int,
        generate_images_fn: Optional[Callable] = None,
        generate_videos_fn: Optional[Callable] = None,
    ) -> Pipeline:
        """
        Execute a pipeline from start to finish.

        Args:
            db: Database session
            pipeline_id: Pipeline ID to execute
            generate_images_fn: Function to call for I2I generation
            generate_videos_fn: Function to call for I2V generation

        Returns:
            Updated pipeline
        """
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        logger.info("Starting pipeline execution", pipeline_id=pipeline_id, mode=pipeline.mode)

        # Update status to running
        pipeline.status = PipelineStatus.RUNNING.value
        db.commit()

        await self._broadcast(pipeline_id, "pipeline_status", {
            "id": pipeline_id,
            "status": "running",
            "current_step": None,
        })

        try:
            # Get ordered steps
            steps = sorted(pipeline.steps, key=lambda s: s.step_order)
            checkpoints = pipeline.get_checkpoints()

            for step in steps:
                # Skip completed steps (for resume)
                if step.status == StepStatus.COMPLETED.value:
                    continue

                # Check for checkpoint pause
                if pipeline.mode == "checkpoint" and step.step_type in checkpoints:
                    if step.status != StepStatus.REVIEW.value:
                        step.status = StepStatus.REVIEW.value
                        db.commit()

                        await self._broadcast(pipeline_id, "step_progress", {
                            "step_id": step.id,
                            "status": "review",
                            "message": f"Waiting for approval on {step.step_type}",
                        })

                        # Pause pipeline
                        pipeline.status = PipelineStatus.PAUSED.value
                        db.commit()

                        await self._broadcast(pipeline_id, "pipeline_status", {
                            "id": pipeline_id,
                            "status": "paused",
                            "current_step": step.id,
                        })

                        logger.info("Pipeline paused for review", pipeline_id=pipeline_id, step_id=step.id)
                        return pipeline

                # Execute step
                step.status = StepStatus.RUNNING.value
                db.commit()

                await self._broadcast(pipeline_id, "step_progress", {
                    "step_id": step.id,
                    "status": "running",
                    "progress_pct": 0,
                })

                try:
                    outputs = await self._execute_step(
                        step,
                        generate_images_fn,
                        generate_videos_fn,
                    )

                    step.set_outputs(outputs)
                    step.status = StepStatus.COMPLETED.value

                    # Calculate actual cost
                    cost_info = self._calculate_step_cost(step)
                    step.cost_actual = cost_info["total"]

                    db.commit()

                    await self._broadcast(pipeline_id, "step_progress", {
                        "step_id": step.id,
                        "status": "completed",
                        "progress_pct": 100,
                        "outputs_count": len(outputs.get("items", [])) if isinstance(outputs, dict) else 0,
                    })

                    await self._broadcast(pipeline_id, "output_ready", {
                        "step_id": step.id,
                        "output_type": step.step_type,
                        "outputs": outputs,
                    })

                    # Chain outputs to next step's inputs
                    next_step = self._get_next_step(steps, step)
                    if next_step:
                        self._chain_outputs_to_inputs(step, next_step)
                        db.commit()

                except Exception as e:
                    step.status = StepStatus.FAILED.value
                    step.error_message = str(e)
                    db.commit()

                    await self._broadcast(pipeline_id, "error", {
                        "step_id": step.id,
                        "error_message": str(e),
                        "retryable": True,
                    })

                    raise

            # All steps completed
            pipeline.status = PipelineStatus.COMPLETED.value
            db.commit()

            await self._broadcast(pipeline_id, "pipeline_status", {
                "id": pipeline_id,
                "status": "completed",
                "current_step": None,
            })

            logger.info("Pipeline completed", pipeline_id=pipeline_id)
            return pipeline

        except Exception as e:
            pipeline.status = PipelineStatus.FAILED.value
            db.commit()

            await self._broadcast(pipeline_id, "pipeline_status", {
                "id": pipeline_id,
                "status": "failed",
                "error": str(e),
            })

            logger.error("Pipeline failed", pipeline_id=pipeline_id, error=str(e))
            raise

    async def _execute_step(
        self,
        step: PipelineStep,
        generate_images_fn: Optional[Callable],
        generate_videos_fn: Optional[Callable],
    ) -> dict:
        """Execute a single pipeline step."""
        config = step.get_config()
        inputs = step.get_inputs()

        logger.info("Executing step", step_id=step.id, step_type=step.step_type)

        if step.step_type == StepType.PROMPT_ENHANCE.value:
            return await self._execute_prompt_enhance(config, inputs)

        elif step.step_type == StepType.I2I.value:
            if not generate_images_fn:
                raise ValueError("No image generation function provided")
            return await self._execute_i2i(config, inputs, generate_images_fn)

        elif step.step_type == StepType.I2V.value:
            if not generate_videos_fn:
                raise ValueError("No video generation function provided")
            return await self._execute_i2v(config, inputs, generate_videos_fn)

        else:
            raise ValueError(f"Unknown step type: {step.step_type}")

    async def _execute_prompt_enhance(self, config: dict, inputs: dict) -> dict:
        """Execute prompt enhancement step."""
        input_prompts = config.get("input_prompts", inputs.get("prompts", []))
        if not input_prompts:
            raise ValueError("No input prompts provided")

        variations_per = config.get("variations_per_prompt", 5)
        target = config.get("target_type", "i2i")
        style = config.get("style_hints", ["photorealistic"])[0] if config.get("style_hints") else "photorealistic"
        theme = config.get("theme_focus")

        enhanced = await prompt_enhancer.enhance_bulk(
            prompts=input_prompts,
            target=target,
            count=variations_per,
            style=style,
            theme_focus=theme,
        )

        # Flatten all enhanced prompts
        all_prompts = []
        for prompt_variations in enhanced:
            all_prompts.extend(prompt_variations)

        return {
            "prompts": all_prompts,
            "original_prompts": input_prompts,
            "enhanced_per_original": enhanced,
        }

    async def _execute_i2i(
        self,
        config: dict,
        inputs: dict,
        generate_fn: Callable,
    ) -> dict:
        """Execute I2I generation step."""
        image_urls = inputs.get("image_urls", [])
        prompts = inputs.get("prompts", [])

        if not image_urls:
            raise ValueError("No input images provided")
        if not prompts:
            raise ValueError("No prompts provided")

        model = config.get("model", "gpt-image-1.5")
        images_per = config.get("images_per_prompt", 1)
        aspect_ratio = config.get("aspect_ratio", "9:16")
        quality = config.get("quality", "high")

        # Handle set mode
        set_mode = config.get("set_mode", {})
        effective_prompts = prompts

        if set_mode.get("enabled"):
            effective_prompts = self._expand_prompts_for_set_mode(prompts, set_mode)

        # Generate all combinations
        results = []
        for image_url in image_urls:
            for prompt in effective_prompts:
                # Call the generation function
                result = await generate_fn(
                    source_image_url=image_url,
                    prompt=prompt,
                    model=model,
                    num_images=images_per,
                    aspect_ratio=aspect_ratio,
                    quality=quality,
                )
                results.extend(result if isinstance(result, list) else [result])

        # Cache full-res images to R2 for fast loading
        cached_image_urls = await cache_images_batch(results, prefix="images")
        final_image_urls = [cached or orig for cached, orig in zip(cached_image_urls, results)]

        # Generate thumbnails for grid preview (also goes to R2)
        thumbnail_urls = await generate_thumbnails_batch(results)

        return {
            "image_urls": final_image_urls,  # Full resolution cached on R2
            "thumbnail_urls": thumbnail_urls,  # Smaller previews for grid
            "items": [{"url": url, "type": "image"} for url in final_image_urls],
            "count": len(final_image_urls),
        }

    async def _execute_i2v(
        self,
        config: dict,
        inputs: dict,
        generate_fn: Callable,
    ) -> dict:
        """Execute I2V generation step."""
        image_urls = inputs.get("image_urls", [])
        prompts = inputs.get("prompts", [])

        if not image_urls:
            raise ValueError("No input images provided")

        model = config.get("model", "kling")
        videos_per = config.get("videos_per_image", 1)
        resolution = config.get("resolution", "1080p")
        duration = config.get("duration_sec", 5)
        enable_audio = config.get("enable_audio", False)

        # Generate videos
        results = []
        for image_url in image_urls:
            prompt = prompts[0] if prompts else ""
            for _ in range(videos_per):
                result = await generate_fn(
                    image_url=image_url,
                    motion_prompt=prompt,
                    model=model,
                    resolution=resolution,
                    duration_sec=duration,
                    enable_audio=enable_audio,
                )
                results.append(result)

        # Cache videos to R2 for fast loading
        cached_urls = await cache_videos_batch(results)
        # Use cached URL if available, otherwise original
        final_urls = [cached or orig for cached, orig in zip(cached_urls, results)]

        return {
            "video_urls": final_urls,
            "items": [{"url": url, "type": "video"} for url in final_urls],
            "count": len(final_urls),
        }

    def _expand_prompts_for_set_mode(self, prompts: list, set_mode: dict) -> list:
        """Expand prompts with set mode variations."""
        variations = set_mode.get("variations", [])
        count_per = set_mode.get("count_per_variation", 1)

        variation_suffixes = {
            "angles": ["front view", "side view", "three-quarter view", "back view"],
            "expressions": ["smiling", "serious expression", "laughing", "contemplative"],
            "poses": ["standing pose", "sitting pose", "walking", "action pose"],
            "outfits": ["casual outfit", "formal attire", "sporty look", "elegant dress"],
            "lighting": ["studio lighting", "natural light", "dramatic shadows", "soft glow"],
        }

        expanded = []
        for prompt in prompts:
            for var_type in variations:
                suffixes = variation_suffixes.get(var_type, [])
                for suffix in suffixes[:count_per]:
                    expanded.append(f"{prompt}, {suffix}")

        return expanded if expanded else prompts

    def _get_next_step(self, steps: list, current: PipelineStep) -> Optional[PipelineStep]:
        """Get the next step in the pipeline."""
        for i, step in enumerate(steps):
            if step.id == current.id and i + 1 < len(steps):
                return steps[i + 1]
        return None

    def _chain_outputs_to_inputs(self, from_step: PipelineStep, to_step: PipelineStep):
        """Chain outputs of one step to inputs of the next."""
        outputs = from_step.get_outputs()

        if from_step.step_type == StepType.PROMPT_ENHANCE.value:
            # Pass prompts to next step
            to_step.set_inputs({
                **to_step.get_inputs(),
                "prompts": outputs.get("prompts", []),
            })

        elif from_step.step_type == StepType.I2I.value:
            # Pass image URLs to next step
            to_step.set_inputs({
                **to_step.get_inputs(),
                "image_urls": outputs.get("image_urls", []),
            })

        elif from_step.step_type == StepType.I2V.value:
            # Video outputs typically don't chain further
            pass

    def _calculate_step_cost(self, step: PipelineStep) -> dict:
        """Calculate actual cost for a completed step."""
        config = step.get_config()
        outputs = step.get_outputs()

        if step.step_type == StepType.PROMPT_ENHANCE.value:
            prompts = outputs.get("prompts", [])
            return {"total": len(prompts) * 0.001}

        elif step.step_type == StepType.I2I.value:
            count = outputs.get("count", 0)
            return cost_calculator.calculate_i2i_cost(config, count)

        elif step.step_type == StepType.I2V.value:
            count = outputs.get("count", 0)
            return cost_calculator.calculate_i2v_cost(config, count)

        return {"total": 0}

    async def pause_pipeline(self, db: Session, pipeline_id: int) -> Pipeline:
        """Pause a running pipeline at the next checkpoint."""
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        if pipeline.status != PipelineStatus.RUNNING.value:
            raise ValueError(f"Pipeline is not running (status: {pipeline.status})")

        pipeline.status = PipelineStatus.PAUSED.value
        db.commit()

        await self._broadcast(pipeline_id, "pipeline_status", {
            "id": pipeline_id,
            "status": "paused",
        })

        return pipeline

    async def resume_pipeline(
        self,
        db: Session,
        pipeline_id: int,
        generate_images_fn: Optional[Callable] = None,
        generate_videos_fn: Optional[Callable] = None,
    ) -> Pipeline:
        """Resume a paused pipeline."""
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        if pipeline.status not in [PipelineStatus.PAUSED.value, PipelineStatus.PENDING.value]:
            raise ValueError(f"Pipeline cannot be resumed (status: {pipeline.status})")

        return await self.execute_pipeline(
            db, pipeline_id, generate_images_fn, generate_videos_fn
        )

    async def cancel_pipeline(self, db: Session, pipeline_id: int) -> Pipeline:
        """Cancel a running or paused pipeline."""
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        pipeline.status = PipelineStatus.FAILED.value
        db.commit()

        await self._broadcast(pipeline_id, "pipeline_status", {
            "id": pipeline_id,
            "status": "cancelled",
        })

        return pipeline

    async def approve_step(self, db: Session, step_id: int) -> PipelineStep:
        """Approve a step waiting for review."""
        step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
        if not step:
            raise ValueError(f"Step {step_id} not found")

        if step.status != StepStatus.REVIEW.value:
            raise ValueError(f"Step is not in review (status: {step.status})")

        step.status = StepStatus.COMPLETED.value
        db.commit()

        return step

    async def retry_step(self, db: Session, step_id: int) -> PipelineStep:
        """Retry a failed step."""
        step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
        if not step:
            raise ValueError(f"Step {step_id} not found")

        step.status = StepStatus.PENDING.value
        step.error_message = None
        db.commit()

        return step


# Singleton instance
pipeline_executor = PipelineExecutor()
