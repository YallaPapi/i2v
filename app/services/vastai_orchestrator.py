"""
Orchestrator for managing a persistent Vast.ai SwarmUI instance.

Uses the permanent Cloudflare tunnel at swarm.wunderbun.com for reliable access.
"""
import os
import asyncio
import tempfile
from pathlib import Path
import structlog

from app.config import settings
from app.models import BatchJobItem
from app.services.swarmui_client import (
    SwarmUIClient,
    SwarmUIGenerationError,
    get_swarmui_client,
)

logger = structlog.get_logger()

# Import post-processing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "caption_overlay"))
from post_process import post_process_video


class VastAIOrchestrator:
    """
    Manages video generation on the persistent SwarmUI instance.

    Uses the permanent Cloudflare tunnel configured in settings.swarmui_url
    instead of creating new instances.
    """

    def __init__(self):
        self.swarm_client: SwarmUIClient | None = None
        self._lock = asyncio.Lock()

    async def get_or_create_client(self) -> SwarmUIClient:
        """
        Gets a SwarmUIClient for the persistent instance.

        Uses settings.swarmui_url (permanent Cloudflare tunnel) instead of
        creating new Vast.ai instances on demand.
        """
        async with self._lock:
            if self.swarm_client and await self.swarm_client.health_check():
                logger.info("Reusing existing healthy SwarmUI client.")
                return self.swarm_client

            # Use the singleton client configured with settings
            swarmui_url = settings.swarmui_url or "http://localhost:7801"
            logger.info("Connecting to persistent SwarmUI instance", url=swarmui_url)

            self.swarm_client = get_swarmui_client(
                base_url=swarmui_url,
                auth_token=settings.swarmui_auth_token,
            )

            if await self.swarm_client.health_check():
                logger.info("SwarmUI instance is healthy.")
                return self.swarm_client
            else:
                raise SwarmUIGenerationError(
                    f"SwarmUI instance at {swarmui_url} is not healthy. "
                    "Check if the instance is running and tunnel is active."
                )

    async def generation_fn(self, item: BatchJobItem, **config) -> dict:
        """
        The generation function compatible with the BatchQueue, adapted for VastAI.

        Uses WebSocket API with LoRAs embedded in prompt (not as separate params).
        Supports VastaiVideoConfig parameters from frontend.
        """
        logger.info("VastAI Orchestrator: Received job.", item_id=item.id, config=config)

        # Extract arguments for generate_video from item and config
        variation_params = item.get_variation_params()
        image_url = variation_params.get("image_url")
        if not image_url:
            raise ValueError("VastAI job requires an image_url in variation_params")

        prompt = item.prompt or "A gentle breeze"

        # Get vastai_config if present
        vastai_config = config.get("vastai_config", {}) or {}

        # Resolution parsing - map resolution string to width/height
        # Default to 9:16 portrait for I2V
        resolution = config.get("resolution", "720p")
        if resolution == "720p":
            width, height = 720, 1280  # 9:16 portrait
        elif resolution == "1080p":
            width, height = 1080, 1920
        else:
            width, height = 480, 848

        # Adjust for aspect ratio if specified
        aspect_ratio = config.get("aspect_ratio")
        if aspect_ratio == "16:9":
            width, height = height, width  # Swap for landscape

        # Extract VastaiVideoConfig parameters with config defaults
        steps = vastai_config.get("steps", settings.swarmui_default_steps)
        frames = vastai_config.get("frames", settings.swarmui_default_frames)
        fps = vastai_config.get("fps", settings.swarmui_default_fps)
        cfg_scale = vastai_config.get("cfg_scale", settings.swarmui_default_cfg)
        seed = vastai_config.get("seed", -1)

        # Model selection - use config defaults
        model = vastai_config.get("model") or settings.swarmui_model
        swap_model = vastai_config.get("swap_model") or settings.swarmui_swap_model

        # LoRA selection - use config defaults (embedded in prompt by client)
        lora_high = vastai_config.get("lora_high") or settings.swarmui_lora_high
        lora_low = vastai_config.get("lora_low") or settings.swarmui_lora_low

        # Advanced Wan 2.2 parameters
        video_steps = vastai_config.get("video_steps", settings.swarmui_video_steps)
        video_cfg = vastai_config.get("video_cfg", settings.swarmui_video_cfg)
        swap_percent = vastai_config.get("swap_percent", settings.swarmui_swap_percent)
        interpolation_method = vastai_config.get("interpolation_method", "RIFE")
        interpolation_multiplier = vastai_config.get("interpolation_multiplier", 2)

        # Negative prompt
        negative_prompt = config.get("negative_prompt") or vastai_config.get("negative_prompt")

        # Post-processing options
        caption = config.get("caption") or vastai_config.get("caption")
        apply_spoof = config.get("apply_spoof", False) or vastai_config.get("apply_spoof", False)

        logger.info(
            "VastAI generation params",
            item_id=item.id,
            resolution=resolution,
            width=width,
            height=height,
            model=model,
            steps=steps,
            frames=frames,
            fps=fps,
            video_steps=video_steps,
            video_cfg=video_cfg,
            caption=caption[:30] if caption else None,
        )

        try:
            client = await self.get_or_create_client()

            # Upload image to SwarmUI first (converts to base64 data URI)
            logger.info("Uploading image to SwarmUI", image_url=image_url[:50])
            image_path = await client.upload_image(image_url)

            # Generate video via WebSocket with Wan 2.2 dual-model setup
            # LoRAs are embedded in prompt: <video> <lora:high> <videoswap> <lora:low>
            result = await client.generate_video(
                image_path=image_path,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=model,
                num_frames=frames,
                fps=fps,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed if seed else -1,
                # Wan 2.2 I2V specific
                video_steps=video_steps,
                video_cfg=video_cfg,
                swap_model=swap_model,
                swap_percent=swap_percent,
                interpolation_method=interpolation_method,
                interpolation_multiplier=interpolation_multiplier,
                width=width,
                height=height,
                # LoRAs (embedded in prompt by client)
                lora_high=lora_high,
                lora_low=lora_low,
            )

            # Get the video URL from result
            video_url = result.get("video_url")

            if not video_url:
                return {
                    "status": "failed",
                    "video_url": None,
                    "video_data": None,
                    "error_message": "No video URL in result",
                }

            # Download video for post-processing or caching
            video_bytes = await client.get_video_bytes(result["video_path"])

            # Post-processing (caption overlay + spoof) if requested
            if caption or apply_spoof:
                logger.info(
                    "Applying post-processing",
                    caption=bool(caption),
                    spoof=apply_spoof,
                )

                # Save raw video to temp file
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as raw_file:
                    raw_file.write(video_bytes)
                    raw_path = raw_file.name

                processed_path = tempfile.mktemp(suffix="_processed.mp4")

                try:
                    # Run post-processing in thread pool
                    loop = asyncio.get_event_loop()
                    pp_result = await loop.run_in_executor(
                        None,
                        lambda: post_process_video(
                            input_path=raw_path,
                            output_path=processed_path,
                            caption=caption,
                            apply_spoof=apply_spoof,
                            use_nvenc=False,
                        )
                    )

                    if pp_result.get("success"):
                        with open(processed_path, "rb") as f:
                            video_bytes = f.read()
                        logger.info("Post-processing complete")
                    else:
                        logger.warning("Post-processing failed", error=pp_result.get("error"))

                finally:
                    try:
                        os.remove(raw_path)
                    except:
                        pass
                    try:
                        os.remove(processed_path)
                    except:
                        pass

            # Cache to R2
            from app.services.r2_cache import cache_video
            cached_url = await cache_video(video_url, video_bytes=video_bytes)
            if cached_url:
                video_url = cached_url

            return {
                "status": "completed",
                "video_url": video_url,
                "video_data": None,
                "error_message": None,
            }

        except Exception as e:
            logger.error("VastAI job failed", item_id=item.id, error=str(e))
            return {
                "status": "failed",
                "video_url": None,
                "video_data": None,
                "error_message": str(e),
            }


# Singleton instance for the orchestrator
_orchestrator = None

def get_vastai_orchestrator() -> "VastAIOrchestrator":
    """Get or create the VastAIOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VastAIOrchestrator()
    return _orchestrator
