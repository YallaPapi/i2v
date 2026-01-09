"""
NSFW Image Generation Executor.

Orchestrates the full pipeline:
1. Get/create GPU instance via vast.ai
2. Upload source image to ComfyUI
3. Build and execute workflow
4. Download result
5. Upload to R2 storage
6. Return URL
"""

import httpx
import structlog
import asyncio
from typing import Optional, Literal
from datetime import datetime
import uuid

from app.services.vastai_client import get_vastai_client, VastAIClient, VastInstance, upload_image_to_comfyui
from app.services.comfyui_workflows import (
    build_i2i_workflow,
    build_i2i_workflow_with_lora,
    enhance_prompt_for_model,
    DEFAULT_NEGATIVE_PROMPTS,
    NSFW_PRESETS,
)
from app.services.r2_cache import cache_image

logger = structlog.get_logger()


# NSFW model configurations
# Filenames match what download_models.sh creates
NSFW_MODELS = {
    "pony-v6": {
        "base": "pony",
        "checkpoint": "ponyDiffusionV6XL_v6.safetensors",
        "vae": "sdxl_vae.safetensors",
        "pricing": "~$0.15-0.30/image (GPU time)",
        "description": "Pony V6 XL - Best for anime/stylized NSFW",
    },
    "pony-realistic": {
        "base": "pony",
        "checkpoint": "ponyRealism_v21.safetensors",
        "vae": "sdxl_vae.safetensors",
        "pricing": "~$0.15-0.30/image (GPU time)",
        "description": "Pony Realism - Photorealistic NSFW",
    },
    "sdxl-base": {
        "base": "sdxl",
        "checkpoint": "sd_xl_base_1.0.safetensors",
        "vae": "sdxl_vae.safetensors",
        "pricing": "~$0.10-0.20/image (GPU time)",
        "description": "SDXL Base - General purpose",
    },
    "realvis-xl": {
        "base": "sdxl",
        "checkpoint": "RealVisXL_V4.0.safetensors",
        "vae": "sdxl_vae.safetensors",
        "pricing": "~$0.10-0.20/image (GPU time)",
        "description": "RealVisXL V4 - Photorealistic humans",
    },
    "juggernaut-xl": {
        "base": "sdxl",
        "checkpoint": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "vae": "sdxl_vae.safetensors",
        "pricing": "~$0.10-0.20/image (GPU time)",
        "description": "Juggernaut XL V9 - Great skin textures",
    },
}

NSFWModelType = Literal["pony-v6", "pony-realistic", "sdxl-base", "realvis-xl", "juggernaut-xl"]


class NSFWImageExecutor:
    """
    Executor for NSFW image generation jobs.

    Handles the full pipeline from source image to generated result.
    """

    def __init__(self, vast_client: VastAIClient | None = None):
        self.vast_client = vast_client or get_vastai_client()

    async def generate_image(
        self,
        source_image_url: str,
        prompt: str,
        model: NSFWModelType = "pony-v6",
        negative_prompt: str | None = None,
        preset: str | None = None,
        denoise: float = 0.65,
        steps: int = 25,
        cfg: float = 7.0,
        width: int = 832,
        height: int = 1216,
        lora_name: str | None = None,
        lora_strength: float = 0.8,
        seed: int = -1,
    ) -> dict:
        """
        Generate an NSFW image from a source image.

        Args:
            source_image_url: URL of the source image
            prompt: Generation prompt
            model: NSFW model to use
            negative_prompt: Negative prompt (uses default if None)
            preset: Preset configuration name (overrides other params)
            denoise: Denoising strength for img2img
            steps: Number of sampling steps
            cfg: CFG scale
            width: Output width
            height: Output height
            lora_name: Optional LoRA to apply
            lora_strength: LoRA strength
            seed: Random seed (-1 for random)

        Returns:
            dict with:
                - status: "completed" | "failed"
                - result_url: URL of generated image (if completed)
                - error_message: Error message (if failed)
                - generation_time: Time taken in seconds
        """
        start_time = datetime.utcnow()
        job_id = str(uuid.uuid4())[:8]

        logger.info(
            "Starting NSFW image generation",
            job_id=job_id,
            model=model,
            preset=preset,
        )

        try:
            # Get model config
            model_config = NSFW_MODELS.get(model)
            if not model_config:
                raise ValueError(f"Unknown model: {model}")

            checkpoint = model_config["checkpoint"]
            vae = model_config["vae"]

            # Apply preset if specified
            model_type = "pony"  # Default
            if preset and preset in NSFW_PRESETS:
                preset_config = NSFW_PRESETS[preset]
                steps = preset_config.get("steps", steps)
                cfg = preset_config.get("cfg", cfg)
                denoise = preset_config.get("denoise", denoise)
                model_type = preset_config.get("model_type", "pony")
                if "checkpoint" in preset_config:
                    checkpoint = preset_config["checkpoint"]

            # Enhance prompt with model-specific tags
            enhanced_prompt = enhance_prompt_for_model(prompt, model_type)

            # Use default negative prompt if none provided
            if negative_prompt is None:
                negative_prompt = DEFAULT_NEGATIVE_PROMPTS.get(model_type, "")

            # Step 1: Get or create GPU instance
            logger.info("Getting GPU instance", job_id=job_id)
            instance = await self.vast_client.get_or_create_instance(
                workload="image",
                max_price=0.50,
            )

            if not instance:
                raise RuntimeError("No GPU instance available. Try again later.")

            # Step 2: Upload source image to ComfyUI
            # ComfyUI's LoadImage node only reads from its local input folder,
            # so we need to upload the image first
            if not instance.ssh_host or not instance.api_port:
                raise RuntimeError("GPU instance not ready - missing API endpoint")

            comfyui_base_url = f"http://{instance.ssh_host}:{instance.api_port}"
            logger.info("Uploading source image to ComfyUI", job_id=job_id, url=source_image_url[:60])

            input_image_filename = await upload_image_to_comfyui(
                image_url=source_image_url,
                comfyui_base_url=comfyui_base_url,
            )

            # Step 3: Build workflow with uploaded filename
            logger.info("Building workflow", job_id=job_id, has_lora=bool(lora_name), input_image=input_image_filename)

            if lora_name:
                workflow = build_i2i_workflow_with_lora(
                    checkpoint=checkpoint,
                    vae=vae,
                    lora_name=lora_name,
                    lora_strength=lora_strength,
                    input_image=input_image_filename,
                    prompt=enhanced_prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg=cfg,
                    denoise=denoise,
                    seed=seed,
                )
            else:
                workflow = build_i2i_workflow(
                    checkpoint=checkpoint,
                    vae=vae,
                    input_image=input_image_filename,
                    prompt=enhanced_prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg=cfg,
                    denoise=denoise,
                    seed=seed,
                )

            # Step 4: Submit job to ComfyUI
            logger.info("Submitting job to ComfyUI", job_id=job_id)
            result = await self.vast_client.submit_comfyui_job(
                instance=instance,
                workflow=workflow,
                timeout=300,
            )

            if not result or not result.get("images"):
                raise RuntimeError("No images generated")

            # Get the result URL (already cached to R2 by vastai_client)
            result_url = result["images"][0]

            generation_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                "NSFW image generation completed",
                job_id=job_id,
                generation_time=generation_time,
            )

            return {
                "status": "completed",
                "result_url": result_url,
                "error_message": None,
                "generation_time": generation_time,
                "model": model,
                "seed": seed,
            }

        except Exception as e:
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            logger.exception(
                "NSFW image generation failed",
                job_id=job_id,
                error=str(e),
            )
            return {
                "status": "failed",
                "result_url": None,
                "error_message": str(e),
                "generation_time": generation_time,
                "model": model,
                "seed": seed,
            }


# Singleton executor instance
_executor: NSFWImageExecutor | None = None


def get_nsfw_executor() -> NSFWImageExecutor:
    """Get the global NSFW executor instance."""
    global _executor
    if _executor is None:
        _executor = NSFWImageExecutor()
    return _executor


async def generate_nsfw_image(
    source_image_url: str,
    prompt: str,
    model: NSFWModelType = "pony-v6",
    **kwargs,
) -> dict:
    """
    Convenience function for generating NSFW images.

    See NSFWImageExecutor.generate_image for full parameter list.
    """
    executor = get_nsfw_executor()
    return await executor.generate_image(
        source_image_url=source_image_url,
        prompt=prompt,
        model=model,
        **kwargs,
    )
