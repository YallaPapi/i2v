"""
Orchestrator for managing a persistent Vast.ai SwarmUI instance.
"""
import asyncio
import structlog

from app.config import settings
from app.models import BatchJobItem
from app.services.vastai_client import VastAIClient
from app.services.swarmui_client import SwarmUIClient, SwarmUIGenerationError

logger = structlog.get_logger()


class VastAIOrchestrator:
    """
    Manages the lifecycle of a single, persistent SwarmUI instance on Vast.ai.
    """

    def __init__(self):
        self.vast_client = VastAIClient(settings.vast_api_key)
        self.swarm_client: SwarmUIClient | None = None
        self.instance_id: int | None = None
        self.instance_url: str | None = None
        self._lock = asyncio.Lock()

    async def get_or_create_client(self) -> SwarmUIClient:
        """
        Gets a SwarmUIClient for the active instance, creating the instance if necessary.
        This function is the core of the persistent instance logic.
        """
        async with self._lock:
            if self.swarm_client and await self.swarm_client.health_check():
                logger.info("Reusing existing healthy SwarmUI client.")
                return self.swarm_client

            logger.info("No healthy SwarmUI client found. Attempting to find or create one.")
            
            # TODO: Implement logic to find existing instance on vast.ai
            # For now, we will focus on creation.

            try:
                logger.info("Creating new SwarmUI instance on Vast.ai...")
                # In the future, this should pull template from config
                instance = await self.vast_client.create_swarmui_instance(
                    template_hash="a385f05c754713214555f5436329a43e" 
                )
                self.instance_id = instance.get("instance_id")
                self.instance_url = instance.get("url")

                if not self.instance_id or not self.instance_url:
                    raise ValueError("Failed to get instance_id or url from vast.ai")

                logger.info(
                    "Successfully created new Vast.ai instance.",
                    instance_id=self.instance_id,
                    url=self.instance_url,
                )
                
                # Wait for the instance to become ready
                # TODO: Implement a more robust readiness check
                await asyncio.sleep(60) # Simple wait for startup

                self.swarm_client = SwarmUIClient(base_url=self.instance_url)
                
                if await self.swarm_client.health_check():
                    logger.info("New SwarmUI instance is healthy.")
                    return self.swarm_client
                else:
                    raise SwarmUIGenerationError("Newly created SwarmUI instance is not healthy.")

            except Exception as e:
                logger.error("Failed to create or verify new instance", error=str(e))
                self.instance_id = None
                self.instance_url = None
                self.swarm_client = None
                raise

    async def generation_fn(self, item: BatchJobItem, **config) -> dict:
        """
        The generation function compatible with the BatchQueue, adapted for VastAI.
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
        resolution = config.get("resolution", "480p")
        if resolution == "720p":
            width, height = 720, 720  # Base for 1:1
        elif resolution == "1080p":
            width, height = 1080, 1080
        else:
            width, height = 480, 480

        # Adjust for aspect ratio if specified
        aspect_ratio = config.get("aspect_ratio")
        if aspect_ratio == "9:16":
            height = int(width * 16 / 9)
        elif aspect_ratio == "16:9":
            width = int(height * 16 / 9)

        # Extract VastaiVideoConfig parameters with defaults
        steps = vastai_config.get("steps", config.get("videosteps", 4))
        frames = vastai_config.get("frames", config.get("videoframes", 33))
        fps = vastai_config.get("fps", config.get("videofps", 16))
        cfg_scale = vastai_config.get("cfg_scale", 1.0)
        lora = vastai_config.get("lora")
        lora_strength = vastai_config.get("lora_strength", 1.0)
        seed = vastai_config.get("seed")

        logger.info(
            "VastAI generation params",
            item_id=item.id,
            resolution=resolution,
            width=width,
            height=height,
            steps=steps,
            frames=frames,
            fps=fps,
            cfg_scale=cfg_scale,
            lora=lora,
        )

        try:
            client = await self.get_or_create_client()

            # Upload image to SwarmUI first
            logger.info("Uploading image to SwarmUI", image_url=image_url[:50])
            image_path = await client.upload_image(image_url)

            # Generate video using the uploaded image
            result = await client.generate_video(
                image_path=image_path,
                prompt=prompt,
                model="Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
                num_frames=frames,
                fps=fps,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed if seed else -1,
                lora=lora,
                lora_strength=lora_strength,
            )

            # Get the video URL from result
            video_url = result.get("video_url")

            if video_url:
                return {
                    "status": "completed",
                    "video_url": video_url,
                    "video_data": None,
                    "error_message": None,
                }
            else:
                return {
                    "status": "failed",
                    "video_url": None,
                    "video_data": None,
                    "error_message": "No video URL in result",
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
