"""SwarmUI API client for image-to-video generation."""

import io
import json
import asyncio
from uuid import uuid4
from typing import Optional
import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger()


class SwarmUIError(Exception):
    """Base exception for SwarmUI errors."""
    pass


class SwarmUISessionError(SwarmUIError):
    """Session-related errors."""
    pass


class SwarmUIGenerationError(SwarmUIError):
    """Generation-related errors."""
    pass


class SwarmUIClient:
    """
    Client for SwarmUI API - local or remote.

    SwarmUI provides a REST API for image/video generation.
    API docs: https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7801",
        timeout: float = 300.0,
    ) -> None:
        """
        Initialize SwarmUI client.

        Args:
            base_url: SwarmUI server URL (default localhost:7801)
            timeout: Request timeout in seconds (default 5 minutes for video gen)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def get_session(self) -> str:
        """
        Get or refresh SwarmUI session.

        SwarmUI requires a session_id for all API calls.
        Sessions are obtained via POST /API/GetNewSession.

        Returns:
            Session ID string
        """
        if self._session_id is not None:
            return self._session_id

        client = await self._get_client()

        try:
            resp = await client.post("/API/GetNewSession", json={})
            resp.raise_for_status()
            data = resp.json()

            # SwarmUI returns session_id in the response
            session_id = data.get("session_id") or data.get("session")
            if not session_id:
                logger.error("Invalid session response", data=data)
                raise SwarmUISessionError(f"No session_id in response: {data}")

            self._session_id = session_id
            logger.info("Got SwarmUI session", session_id=session_id[:16] + "...")
            return session_id

        except httpx.HTTPStatusError as e:
            raise SwarmUISessionError(f"Failed to get session: HTTP {e.response.status_code}")

    async def refresh_session(self) -> str:
        """Force fetch a new session."""
        self._session_id = None
        return await self.get_session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def upload_image(self, image_url: str) -> str:
        """
        Download image from URL and upload to SwarmUI.

        Args:
            image_url: Public URL of the source image

        Returns:
            SwarmUI internal path for the uploaded image
        """
        client = await self._get_client()
        session_id = await self.get_session()

        # Step 1: Download image from URL
        logger.debug("Downloading image for SwarmUI upload", url=image_url[:80])

        async with httpx.AsyncClient(timeout=60.0) as dl_client:
            resp = await dl_client.get(image_url, follow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "image/png")
            content_type = content_type.split(";")[0].strip().lower()

            if not content_type.startswith("image/"):
                raise ValueError(f"URL does not point to an image: {content_type}")

            image_bytes = resp.content

            # Limit to 50MB
            if len(image_bytes) > 50 * 1024 * 1024:
                raise ValueError(f"Image too large: {len(image_bytes) / 1024 / 1024:.1f}MB")

        # Step 2: Upload to SwarmUI
        ext_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        ext = ext_map.get(content_type, ".png")
        filename = f"upload_{uuid4().hex[:8]}{ext}"

        # SwarmUI upload endpoint
        files = {"file": (filename, io.BytesIO(image_bytes), content_type)}
        data = {"session_id": session_id}

        logger.debug("Uploading image to SwarmUI", filename=filename)

        try:
            upload_resp = await client.post(
                "/API/UploadImage",
                data=data,
                files=files,
            )
            upload_resp.raise_for_status()
            result = upload_resp.json()

            # Extract path from response
            image_path = result.get("path") or result.get("image_path") or result.get("image")
            if not image_path:
                # Some versions return just the filename
                image_path = result.get("name") or filename

            logger.info("Image uploaded to SwarmUI", path=image_path)
            return image_path

        except httpx.HTTPStatusError as e:
            raise SwarmUIError(f"Failed to upload image: HTTP {e.response.status_code}")

    async def generate_video(
        self,
        image_path: str,
        prompt: str,
        model: str = "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
        num_frames: int = 81,
        fps: int = 24,
        steps: int = 4,
        cfg_scale: float = 1.0,
        seed: int = -1,
        lora: Optional[str] = None,
        lora_strength: float = 1.0,
    ) -> dict:
        """
        Generate video from image using SwarmUI.

        Args:
            image_path: SwarmUI internal path from upload_image()
            prompt: Motion/content description
            model: Video model name (as shown in SwarmUI)
            num_frames: Number of frames (81 = ~3.4s at 24fps)
            fps: Output frame rate
            steps: Sampling steps (4 for LightX2V)
            cfg_scale: CFG scale (1.0-3.5 for Wan I2V)
            seed: Random seed (-1 for random)
            lora: Optional LoRA name
            lora_strength: LoRA strength if using LoRA

        Returns:
            Dict with video_path and other generation info
        """
        client = await self._get_client()
        session_id = await self.get_session()

        # Build generation payload
        # SwarmUI uses GenerateText2Image for both images and videos
        # Video is triggered by specifying a video model
        payload = {
            "session_id": session_id,
            "prompt": prompt,
            "negativeprompt": "low quality, blurry, distorted, watermark",
            "images": 1,
            "model": model,  # The video model
            "initimage": image_path,
            "initimagecreativity": 0.0,  # 0 = pure I2V, no image gen
            "steps": steps,
            "cfgscale": cfg_scale,
            "seed": seed if seed >= 0 else -1,
            "videoframes": num_frames,
            "videofps": fps,
            "videoformat": "mp4",
        }

        # Add LoRA if specified
        if lora:
            payload["loras"] = f"{lora}:{lora_strength}"

        logger.info(
            "Submitting video generation to SwarmUI",
            model=model,
            frames=num_frames,
            steps=steps,
        )

        try:
            # Use sync endpoint for simplicity (can upgrade to WebSocket later)
            resp = await client.post(
                "/API/GenerateText2Image",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()

            # Check for errors
            if "error" in result:
                raise SwarmUIGenerationError(f"Generation failed: {result['error']}")

            # Extract output path(s)
            images = result.get("images", [])
            if not images:
                raise SwarmUIGenerationError("No output in generation result")

            # SwarmUI returns paths like "View/local/raw/2026-01-09/filename.mp4"
            video_path = images[0] if images else None

            logger.info("Video generation complete", path=video_path)

            return {
                "video_path": video_path,
                "video_url": f"{self.base_url}/{video_path}" if video_path else None,
                "seed": result.get("seed", seed),
                "model": model,
                "frames": num_frames,
            }

        except httpx.HTTPStatusError as e:
            error_text = e.response.text[:500] if e.response.text else "Unknown error"
            raise SwarmUIGenerationError(f"Generation failed: HTTP {e.response.status_code} - {error_text}")
        except httpx.TimeoutException:
            raise SwarmUIGenerationError(f"Generation timed out after {self.timeout}s")

    async def get_video_bytes(self, video_path: str) -> bytes:
        """
        Download video bytes from SwarmUI.

        Args:
            video_path: Path returned from generate_video()

        Returns:
            Video file bytes
        """
        client = await self._get_client()

        # Video path is relative, like "View/local/raw/2026-01-09/file.mp4"
        url = f"/{video_path}" if not video_path.startswith("/") else video_path

        resp = await client.get(url, timeout=120.0)
        resp.raise_for_status()

        return resp.content

    async def health_check(self) -> bool:
        """
        Check if SwarmUI is running and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            resp = await client.get("/", timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Module-level client instance (singleton pattern)
_swarmui_client: Optional[SwarmUIClient] = None


def get_swarmui_client(base_url: Optional[str] = None) -> SwarmUIClient:
    """
    Get SwarmUI client singleton.

    Args:
        base_url: Override base URL (default from env or localhost:7801)

    Returns:
        SwarmUIClient instance
    """
    global _swarmui_client

    if base_url is None:
        import os
        base_url = os.getenv("SWARMUI_URL", "http://localhost:7801")

    if _swarmui_client is None or _swarmui_client.base_url != base_url:
        _swarmui_client = SwarmUIClient(base_url=base_url)

    return _swarmui_client
