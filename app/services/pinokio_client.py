"""Pinokio WAN GP client for video/image generation.

This client integrates with WAN GP running on Pinokio via Gradio client API.
Supports both I2V (image-to-video) and image generation models.

Source: .taskmaster/docs/pinokio-integration-prd.txt
Verified: 2026-01-13 against WAN GP v9.92
"""

import asyncio
import base64
import httpx
import structlog
import tempfile
import os
import json
from typing import Optional
from pathlib import Path
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.r2_cache import cache_video

logger = structlog.get_logger()


class PinokioAPIError(Exception):
    """Exception raised for Pinokio/WAN GP API errors."""
    pass


class PinokioClient:
    """Client for WAN GP via Pinokio Gradio API.

    Uses headless mode for reliable programmatic video generation.

    Source: WAN GP README - Headless Mode section
    Verified endpoint structure from wgp.py:5164 (generate_video function)
    """

    # Supported models (from WAN GP UI)
    MODELS = {
        "wan22-i2v": "wan2.2_image2video_14B",
        "flux-2": "flux2",
        "hunyuan-i2v": "hunyuan_video_1.5_i2v",
        "qwen-image": "qwen_image",
        "z-image": "z_image",
    }

    # Default generation parameters
    DEFAULTS = {
        "resolution": "832x480",  # 480p widescreen
        "video_length": 81,  # ~5 seconds at 16fps
        "num_inference_steps": 4,  # Distilled model
        "guidance_scale": 5.0,
        "seed": -1,  # Random
        "batch_size": 1,
    }

    def __init__(self, base_url: str, ssh_config: Optional[dict] = None):
        """Initialize the Pinokio client.

        Args:
            base_url: Cloudflare tunnel URL (e.g., https://xxx.trycloudflare.com)
            ssh_config: Optional SSH config for headless mode
                        {"host": "ssh9.vast.ai", "port": 28690, "user": "root"}

        Source: Gradio client docs https://www.gradio.app/docs/python-client
        """
        self.base_url = base_url.rstrip("/")
        self.ssh_config = ssh_config
        self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def health_check(self) -> bool:
        """Check if WAN GP is responsive.

        Uses Gradio API info endpoint which is always available.

        Returns:
            True if WAN GP is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/gradio_api/info",
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    # WAN GP has 372 endpoints
                    endpoints = data.get("named_endpoints", {})
                    if len(endpoints) > 100:
                        logger.info(
                            "Pinokio health check passed",
                            endpoints=len(endpoints)
                        )
                        return True

                logger.warning(
                    "Pinokio health check failed",
                    status=response.status_code
                )
                return False

        except Exception as e:
            logger.error("Pinokio health check exception", error=str(e))
            return False

    async def _download_image(
        self,
        client: httpx.AsyncClient,
        image_url: str,
        save_path: str
    ) -> str:
        """Download image from URL to local file.

        Args:
            client: HTTP client
            image_url: Source image URL
            save_path: Local path to save image

        Returns:
            Path to saved image file
        """
        response = await client.get(image_url, follow_redirects=True)

        if response.status_code != 200:
            raise PinokioAPIError(f"Failed to download image: {response.status_code}")

        # Determine extension from content type
        content_type = response.headers.get("content-type", "image/png")
        ext = ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "webp" in content_type:
            ext = ".webp"

        # Ensure proper extension
        if not save_path.endswith(ext):
            save_path = save_path.rsplit(".", 1)[0] + ext

        with open(save_path, "wb") as f:
            f.write(response.content)

        return save_path

    async def _call_gradio_predict(
        self,
        api_name: str,
        data: list,
        timeout: float = 600.0
    ) -> dict:
        """Call a Gradio predict endpoint.

        Args:
            api_name: API endpoint name (e.g., "/init_generate")
            data: List of parameters
            timeout: Request timeout in seconds

        Returns:
            Response data dict
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Gradio API call format
            payload = {
                "data": data,
                "fn_index": None,
                "api_name": api_name,
            }

            response = await client.post(
                f"{self.base_url}/api/predict",
                json=payload,
                timeout=timeout,
            )

            if response.status_code != 200:
                raise PinokioAPIError(
                    f"Gradio API call failed: {response.status_code} - {response.text[:200]}"
                )

            return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def generate_video(
        self,
        image_url: str,
        prompt: str,
        model: str = "wan22-i2v",
        frames: int = 81,
        steps: int = 4,
        seed: int = -1,
        resolution: str = "832x480",
        guidance_scale: float = 5.0,
    ) -> dict:
        """Generate video from image using WAN GP.

        Args:
            image_url: URL of input image
            prompt: Motion prompt describing the animation
            model: Model identifier (wan22-i2v, flux-2, hunyuan-i2v)
            frames: Number of video frames (default 81 = ~5sec)
            steps: Inference steps (4 for distilled models)
            seed: Random seed (-1 for random)
            resolution: Output resolution (e.g., "832x480")
            guidance_scale: CFG scale

        Returns dict with:
            - status: "completed" | "failed"
            - video_url: str | None (R2 URL for persistence)
            - error_message: str | None

        Source: wgp.py:5164 generate_video() function signature
        """
        logger.info(
            "Starting Pinokio video generation",
            prompt=prompt[:50],
            model=model,
            frames=frames,
            steps=steps,
        )

        # Map model name to WAN GP model type
        model_type = self.MODELS.get(model, "wan2.2_image2video_14B")

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Download input image to temp file
            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False
            ) as tmp:
                temp_image_path = tmp.name

            try:
                await self._download_image(client, image_url, temp_image_path)
                logger.info("Downloaded input image", path=temp_image_path)

                # Create settings JSON for headless mode
                settings = {
                    "prompt": prompt,
                    "image_start": [temp_image_path],
                    "model_type": model_type,
                    "resolution": resolution,
                    "video_length": frames,
                    "num_inference_steps": steps,
                    "seed": seed,
                    "batch_size": 1,
                    "guidance_scale": guidance_scale,
                    "image_mode": 1,  # I2V mode
                }

                # Try Gradio client approach first
                try:
                    # Use gradio_client for submission
                    from gradio_client import Client

                    # Connect to WAN GP
                    gradio_client = Client(self.base_url)

                    # The actual generation flow in WAN GP is complex
                    # and involves state management. For now, use a simpler
                    # approach via the init_generate trigger.

                    # Note: This may need refinement based on actual WAN GP
                    # Gradio API behavior. The headless mode is more reliable.

                    logger.info("Attempting Gradio client generation")

                    # WAN GP doesn't have a simple single-call generation endpoint
                    # The generation is triggered via UI state changes
                    # For reliable programmatic access, headless mode is recommended

                    raise NotImplementedError(
                        "Gradio client mode not fully implemented. "
                        "Use headless mode with SSH config."
                    )

                except ImportError:
                    logger.warning("gradio_client not installed, trying HTTP approach")
                    raise PinokioAPIError(
                        "gradio_client required. Install with: pip install gradio_client"
                    )
                except NotImplementedError as e:
                    # Fall back to SSH headless mode if configured
                    if self.ssh_config:
                        return await self._generate_via_ssh(
                            settings, temp_image_path, client
                        )
                    else:
                        raise PinokioAPIError(str(e))

            finally:
                # Cleanup temp file
                if os.path.exists(temp_image_path):
                    os.unlink(temp_image_path)

    async def _generate_via_ssh(
        self,
        settings: dict,
        image_path: str,
        client: httpx.AsyncClient
    ) -> dict:
        """Generate video via SSH headless mode.

        This method:
        1. Uploads image to Pinokio instance
        2. Creates settings.json
        3. Runs headless generation
        4. Downloads output video
        5. Uploads to R2

        Args:
            settings: Generation settings dict
            image_path: Local path to input image
            client: HTTP client for R2 upload

        Returns:
            Result dict with status, video_url, error_message
        """
        if not self.ssh_config:
            raise PinokioAPIError("SSH config required for headless mode")

        host = self.ssh_config.get("host", "ssh9.vast.ai")
        port = self.ssh_config.get("port", 28690)
        user = self.ssh_config.get("user", "root")

        import subprocess
        import uuid

        job_id = str(uuid.uuid4())[:8]
        remote_image = f"/tmp/pinokio_input_{job_id}.png"
        remote_settings = f"/tmp/pinokio_settings_{job_id}.json"
        wgp_path = "/root/pinokio/api/wan.git/app"
        output_dir = f"{wgp_path}/outputs"

        try:
            # 1. Upload image
            logger.info("Uploading image to Pinokio instance")
            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(port),
                image_path,
                f"{user}@{host}:{remote_image}"
            ]
            subprocess.run(scp_cmd, check=True, capture_output=True, timeout=30)

            # 2. Update settings with remote path
            settings["image_start"] = [remote_image]

            # 3. Upload settings
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False
            ) as f:
                json.dump(settings, f)
                local_settings = f.name

            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(port),
                local_settings,
                f"{user}@{host}:{remote_settings}"
            ]
            subprocess.run(scp_cmd, check=True, capture_output=True, timeout=30)
            os.unlink(local_settings)

            # 4. Get output file count before generation
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{user}@{host}",
                f"ls -1 {output_dir}/*.mp4 2>/dev/null | wc -l"
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            files_before = int(result.stdout.strip() or "0")

            # 5. Run headless generation
            logger.info("Running WAN GP headless generation")
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{user}@{host}",
                f"cd {wgp_path} && source env/bin/activate && python wgp.py --process {remote_settings}"
            ]

            # Run with timeout (10 minutes)
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                logger.error("Headless generation failed", stderr=result.stderr[:500])
                return {
                    "status": "failed",
                    "video_url": None,
                    "error_message": f"Generation failed: {result.stderr[:200]}"
                }

            # 6. Find new output file
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{user}@{host}",
                f"ls -1t {output_dir}/*.mp4 2>/dev/null | head -1"
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            output_file = result.stdout.strip()

            if not output_file:
                return {
                    "status": "failed",
                    "video_url": None,
                    "error_message": "No output video found"
                }

            # 7. Download video
            logger.info("Downloading generated video", path=output_file)
            with tempfile.NamedTemporaryFile(
                suffix='.mp4', delete=False
            ) as tmp:
                local_video = tmp.name

            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(port),
                f"{user}@{host}:{output_file}",
                local_video
            ]
            subprocess.run(scp_cmd, check=True, capture_output=True, timeout=60)

            # 8. Upload to R2
            with open(local_video, 'rb') as f:
                video_bytes = f.read()
            os.unlink(local_video)

            r2_url = await cache_video(
                source_url=output_file,
                video_bytes=video_bytes,
                content_type="video/mp4",
            )

            if r2_url:
                logger.info("Video cached to R2", r2_url=r2_url[:50])
                return {
                    "status": "completed",
                    "video_url": r2_url,
                    "error_message": None,
                }
            else:
                return {
                    "status": "completed",
                    "video_url": None,
                    "error_message": "Video generated but R2 upload failed",
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "video_url": None,
                "error_message": "Generation timed out (10 min limit)",
            }
        except Exception as e:
            logger.error("SSH generation failed", error=str(e))
            return {
                "status": "failed",
                "video_url": None,
                "error_message": str(e),
            }
        finally:
            # Cleanup remote files
            try:
                cleanup_cmd = [
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-p", str(port),
                    f"{user}@{host}",
                    f"rm -f {remote_image} {remote_settings}"
                ]
                subprocess.run(cleanup_cmd, capture_output=True, timeout=10)
            except Exception:
                pass

    async def generate_image(
        self,
        prompt: str,
        model: str = "flux-2",
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
        seed: int = -1,
    ) -> dict:
        """Generate image from prompt.

        Args:
            prompt: Image description
            model: Model identifier (flux-2, qwen-image, z-image)
            width: Image width
            height: Image height
            steps: Inference steps
            seed: Random seed

        Returns dict with:
            - status: "completed" | "failed"
            - image_url: str | None (R2 URL)
            - error_message: str | None

        Source: wgp.py model definitions for image generation
        """
        logger.info(
            "Starting Pinokio image generation",
            prompt=prompt[:50],
            model=model,
            width=width,
            height=height,
        )

        # Map model name
        model_type = self.MODELS.get(model, "flux2")

        settings = {
            "prompt": prompt,
            "model_type": model_type,
            "resolution": f"{width}x{height}",
            "num_inference_steps": steps,
            "seed": seed,
            "batch_size": 1,
            "image_mode": 0,  # Text-to-image mode
        }

        if self.ssh_config:
            # Use SSH headless mode
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Image generation doesn't need input image
                return await self._generate_image_via_ssh(settings, client)
        else:
            raise PinokioAPIError(
                "SSH config required for image generation. "
                "Set ssh_config in client initialization."
            )

    async def _generate_image_via_ssh(
        self,
        settings: dict,
        client: httpx.AsyncClient
    ) -> dict:
        """Generate image via SSH headless mode.

        Similar to video generation but for images.
        """
        if not self.ssh_config:
            raise PinokioAPIError("SSH config required for headless mode")

        host = self.ssh_config.get("host", "ssh9.vast.ai")
        port = self.ssh_config.get("port", 28690)
        user = self.ssh_config.get("user", "root")

        import subprocess
        import uuid

        job_id = str(uuid.uuid4())[:8]
        remote_settings = f"/tmp/pinokio_settings_{job_id}.json"
        wgp_path = "/root/pinokio/api/wan.git/app"
        output_dir = f"{wgp_path}/outputs"

        try:
            # 1. Upload settings
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False
            ) as f:
                json.dump(settings, f)
                local_settings = f.name

            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(port),
                local_settings,
                f"{user}@{host}:{remote_settings}"
            ]
            subprocess.run(scp_cmd, check=True, capture_output=True, timeout=30)
            os.unlink(local_settings)

            # 2. Run headless generation
            logger.info("Running WAN GP headless image generation")
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{user}@{host}",
                f"cd {wgp_path} && source env/bin/activate && python wgp.py --process {remote_settings}"
            ]

            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                logger.error("Headless generation failed", stderr=result.stderr[:500])
                return {
                    "status": "failed",
                    "image_url": None,
                    "error_message": f"Generation failed: {result.stderr[:200]}"
                }

            # 3. Find new output file (PNG for images)
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-p", str(port),
                f"{user}@{host}",
                f"ls -1t {output_dir}/*.png 2>/dev/null | head -1"
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            output_file = result.stdout.strip()

            if not output_file:
                return {
                    "status": "failed",
                    "image_url": None,
                    "error_message": "No output image found"
                }

            # 4. Download image
            logger.info("Downloading generated image", path=output_file)
            with tempfile.NamedTemporaryFile(
                suffix='.png', delete=False
            ) as tmp:
                local_image = tmp.name

            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(port),
                f"{user}@{host}:{output_file}",
                local_image
            ]
            subprocess.run(scp_cmd, check=True, capture_output=True, timeout=60)

            # 5. Upload to R2
            with open(local_image, 'rb') as f:
                image_bytes = f.read()
            os.unlink(local_image)

            # Use same cache function with image content type
            from app.services.r2_cache import cache_image

            r2_url = await cache_image(
                source_url=output_file,
                image_bytes=image_bytes,
                content_type="image/png",
            )

            if r2_url:
                logger.info("Image cached to R2", r2_url=r2_url[:50])
                return {
                    "status": "completed",
                    "image_url": r2_url,
                    "error_message": None,
                }
            else:
                return {
                    "status": "completed",
                    "image_url": None,
                    "error_message": "Image generated but R2 upload failed",
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "image_url": None,
                "error_message": "Generation timed out (5 min limit)",
            }
        except Exception as e:
            logger.error("SSH image generation failed", error=str(e))
            return {
                "status": "failed",
                "image_url": None,
                "error_message": str(e),
            }
        finally:
            # Cleanup remote files
            try:
                cleanup_cmd = [
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-p", str(port),
                    f"{user}@{host}",
                    f"rm -f {remote_settings}"
                ]
                subprocess.run(cleanup_cmd, capture_output=True, timeout=10)
            except Exception:
                pass
