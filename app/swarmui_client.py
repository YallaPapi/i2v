"""SwarmUI client for video generation."""

import base64
import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.r2_cache import cache_video

logger = structlog.get_logger()


class SwarmUIAPIError(Exception):
    """Exception raised for SwarmUI API errors."""
    pass


class SwarmUIClient:
    """Client for a SwarmUI instance."""

    # Default model and LoRA for Wan 2.2 I2V
    DEFAULT_MODEL = "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"
    DEFAULT_LORA = "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session_id = None
        self.model_name = self.DEFAULT_MODEL

    async def _ensure_session(self, client: httpx.AsyncClient) -> str:
        """Get or create a SwarmUI session."""
        if self.session_id:
            return self.session_id

        response = await client.post(
            f"{self.base_url}/API/GetNewSession",
            json={},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise SwarmUIAPIError(f"Failed to get session: {response.text}")

        data = response.json()
        self.session_id = data.get("session_id")

        if not self.session_id:
            raise SwarmUIAPIError("No session_id in response")

        logger.info("SwarmUI session created", session_id=self.session_id[:16])
        return self.session_id

    async def _load_model(self, client: httpx.AsyncClient, session_id: str) -> bool:
        """Load the Wan model if not already loaded."""
        response = await client.post(
            f"{self.base_url}/API/SelectModel",
            json={
                "session_id": session_id,
                "model": self.model_name,
            },
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            logger.warning("Model selection failed", response=response.text)
            return False

        data = response.json()
        return data.get("success", False)

    async def _download_and_encode_image(self, client: httpx.AsyncClient, image_url: str) -> str:
        """Download image from URL and convert to base64 data URI."""
        response = await client.get(image_url, follow_redirects=True)

        if response.status_code != 200:
            raise SwarmUIAPIError(f"Failed to download image: {response.status_code}")

        content_type = response.headers.get("content-type", "image/jpeg")
        if ";" in content_type:
            content_type = content_type.split(";")[0].strip()

        b64_data = base64.b64encode(response.content).decode("utf-8")
        return f"data:{content_type};base64,{b64_data}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def generate_video(
        self,
        image_url: str,
        prompt: str,
        width: int = 480,
        height: int = 480,
        steps: int = 4,
        frames: int = 33,
        fps: int = 16,
        cfg_scale: float = 1.0,
        lora: str | None = None,
        lora_strength: float = 1.0,
        seed: int | None = None,
    ) -> dict:
        """
        Generate a video from an image using SwarmUI.

        Args:
            image_url: URL of input image
            prompt: Motion prompt describing the animation
            width: Video width in pixels
            height: Video height in pixels
            steps: Inference steps (4 with LoRA, 20+ without)
            frames: Number of video frames (17-81)
            fps: Output frames per second
            cfg_scale: CFG scale for guidance (1.0 recommended for Wan)
            lora: LoRA model name (without extension)
            lora_strength: LoRA strength 0.0-1.0
            seed: Random seed for reproducibility

        Returns dict with:
            - status: "completed" | "failed"
            - video_url: str | None (R2 URL for persistence)
            - video_data: bytes | None (raw video data)
            - error_message: str | None
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Get session
            session_id = await self._ensure_session(client)

            # Load model
            await self._load_model(client, session_id)

            # Download and encode input image
            logger.info("Downloading input image", url=image_url[:50])
            image_b64 = await self._download_and_encode_image(client, image_url)

            # Build LoRA specification if provided
            lora_spec = ""
            if lora and lora != "none":
                # SwarmUI format: <lora:name:strength>
                lora_name = lora if not lora.endswith(".safetensors") else lora[:-12]
                lora_spec = f"<lora:{lora_name}:{lora_strength}>"

            # Submit generation request
            logger.info(
                "Submitting I2V job to SwarmUI",
                prompt=prompt[:50],
                steps=steps,
                frames=frames,
                lora=lora,
            )

            payload = {
                "session_id": session_id,
                "images": 1,
                "prompt": f"{prompt} {lora_spec}".strip(),
                "model": self.model_name,
                "videomodel": self.model_name,
                "width": width,
                "height": height,
                "videosteps": steps,
                "videoframes": frames,
                "videofps": fps,
                "initimage": image_b64,
                "cfgscale": cfg_scale,
            }

            # Add seed if specified
            if seed is not None:
                payload["seed"] = seed

            response = await client.post(
                f"{self.base_url}/API/GenerateText2Image",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300.0,  # 5 minute timeout for generation
            )

            if response.status_code != 200:
                return {
                    "status": "failed",
                    "video_url": None,
                    "video_data": None,
                    "error_message": f"Generation failed: {response.text}",
                }

            data = response.json()

            if "error" in data:
                return {
                    "status": "failed",
                    "video_url": None,
                    "video_data": None,
                    "error_message": data["error"],
                }

            # Find the video file in response
            images = data.get("images", [])
            video_path = None

            for img in images:
                if img.endswith(".mp4") or img.endswith(".webm"):
                    video_path = img
                    break

            if not video_path:
                return {
                    "status": "failed",
                    "video_url": None,
                    "video_data": None,
                    "error_message": "No video file in response",
                }

            # Download the video
            logger.info("Downloading generated video", path=video_path)
            video_url = f"{self.base_url}/Output/{video_path.replace('View/', '')}"

            video_response = await client.get(video_url)

            if video_response.status_code != 200:
                # Try alternate path
                video_url = f"{self.base_url}/{video_path}"
                video_response = await client.get(video_url)

            if video_response.status_code == 200:
                video_bytes = video_response.content

                # Upload to R2 for persistent storage
                r2_url = await cache_video(
                    source_url=video_url,
                    video_bytes=video_bytes,
                    content_type="video/mp4",
                )

                if r2_url:
                    logger.info("Video cached to R2", r2_url=r2_url[:50])
                    return {
                        "status": "completed",
                        "video_url": r2_url,  # Return R2 URL for persistence
                        "video_data": video_bytes,
                        "error_message": None,
                    }
                else:
                    # R2 upload failed, fall back to pod URL (temporary)
                    logger.warning("R2 upload failed, using temporary pod URL")
                    return {
                        "status": "completed",
                        "video_url": video_url,
                        "video_data": video_bytes,
                        "error_message": "Video generated but R2 upload failed",
                    }
            else:
                return {
                    "status": "completed",
                    "video_url": video_url,
                    "video_data": None,
                    "error_message": f"Video generated but download failed: {video_response.status_code}",
                }

    async def check_health(self) -> bool:
        """Check if the SwarmUI instance is healthy."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # A simple health check could be trying to get a new session
                # or checking a specific health endpoint if SwarmUI provides one.
                response = await client.get(f"{self.base_url}/API/GetBackendTypes", timeout=5.0)
                if response.status_code == 200:
                    # Check if there's at least one backend type available
                    if response.json().get("types"):
                        logger.info("SwarmUI health check passed.")
                        return True
                
                logger.warning("SwarmUI health check failed.", status=response.status_code, response=response.text[:100])
                return False
        except Exception as e:
            logger.error("Health check failed with exception", error=str(e))
            return False
