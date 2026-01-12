"""
Service to dispatch generation jobs to the correct provider (Fal, Vast.ai, etc.).
Provider is determined automatically based on model selection.
"""
import asyncio
import structlog

from app.models import BatchJobItem
from app.services.vastai_orchestrator import get_vastai_orchestrator
from app.services import fal_client
from app.schemas import is_vastai_model

logger = structlog.get_logger()

async def _run_fal_job_and_wait(item: BatchJobItem, config: dict) -> str:
    """
    Runs a job on Fal.ai and polls until completion.
    Returns the final video URL.
    """
    logger.info("Dispatching job to Fal.ai", item_id=item.id, config=config)

    # Extract parameters for fal_client
    # This part needs to be robust to handle different expected keys
    # For now, we assume a simple mapping.
    # TODO: Create a more robust mapping from generic config to provider-specific params.
    model = config.get("model", "kling")
    # A default image_url is needed if not in the item
    # This might come from a parent job or a template in a real scenario
    image_url = item.get_variation_params().get("image_url", "https://example.com/placeholder.jpg")
    motion_prompt = item.prompt or "A gentle breeze"
    
    # These might not always be present, provide defaults
    resolution = config.get("resolution", "1080p")
    duration_sec = config.get("duration_sec", 5)
    negative_prompt = config.get("negative_prompt")
    enable_audio = config.get("enable_audio", False)

    try:
        request_id = await fal_client.submit_job(
            model=model,
            image_url=image_url,
            motion_prompt=motion_prompt,
            resolution=resolution,
            duration_sec=duration_sec,
            negative_prompt=negative_prompt,
            enable_audio=enable_audio,
        )

        # Poll for completion
        for _ in range(120):  # Max wait time of 10 minutes (120 * 5s)
            await asyncio.sleep(5)
            result = await fal_client.get_job_result(model=model, request_id=request_id)
            
            if result["status"] == "completed":
                if result.get("video_url"):
                    logger.info("Fal.ai job completed", item_id=item.id, video_url=result["video_url"])
                    return result["video_url"]
                else:
                    raise Exception("Fal.ai job completed but no video URL was returned.")
            
            elif result["status"] == "failed":
                error_message = result.get("error_message", "Unknown error from Fal.ai")
                raise Exception(f"Fal.ai job failed: {error_message}")
        
        raise TimeoutError("Fal.ai job timed out after 10 minutes.")

    except Exception as e:
        logger.error("Fal.ai job processing failed", item_id=item.id, error=str(e))
        raise


async def dispatch_generation(item: BatchJobItem, config: dict) -> str:
    """
    The main generation_fn for the BatchQueue.
    Provider is determined automatically based on the model name.
    Models starting with 'vastai-' go to Vast.ai, others go to fal.ai.
    """
    model = config.get("model", "kling")

    # Determine provider based on model (not from config)
    provider = "vastai" if is_vastai_model(model) else "fal"
    logger.info("Dispatching generation job", item_id=item.id, provider=provider, model=model)

    if provider == "vastai":
        orchestrator = get_vastai_orchestrator()
        # The orchestrator's function needs to return the URL string
        result_dict = await orchestrator.generation_fn(item=item, **config)
        if result_dict.get("status") == "completed" and result_dict.get("video_url"):
            return result_dict["video_url"]
        else:
            error_msg = result_dict.get("error_message", "Unknown error from VastAI")
            raise Exception(f"Vast.ai job failed: {error_msg}")

    else:  # fal.ai (default)
        return await _run_fal_job_and_wait(item, config)