"""SwarmUI API client for image-to-video generation."""

import io
import json
import asyncio
from typing import Optional, Callable
import httpx
import websockets
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
        auth_token: Optional[str] = None,
    ) -> None:
        """
        Initialize SwarmUI client.

        Args:
            base_url: SwarmUI server URL (default localhost:7801)
            timeout: Request timeout in seconds (default 5 minutes for video gen)
            auth_token: Auth token for Vast.ai tunnels (sets cookie)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
        self._session_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            # Build cookies dict if auth_token provided
            cookies = None
            if self.auth_token:
                # Vast.ai portal uses cookie format: C.{instance_id}_auth_token
                # We use a generic cookie name that works across instances
                cookies = {"auth_token": self.auth_token}
                # Also try the numbered format if instance_id is in env
                import os
                instance_id = os.getenv("VASTAI_INSTANCE_ID")
                if instance_id:
                    cookies[f"C.{instance_id}_auth_token"] = self.auth_token

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True,
                cookies=cookies,
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
        Download image from URL and convert to base64 data URI for SwarmUI.

        SwarmUI accepts base64 data URIs directly in the initimage parameter,
        which is more reliable than the file upload endpoint.

        Args:
            image_url: Public URL of the source image

        Returns:
            Base64 data URI string (data:image/jpeg;base64,...)
        """
        import base64

        # Download image from URL
        logger.debug("Downloading image for SwarmUI", url=image_url[:80])

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

        # Convert to base64 data URI
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        data_uri = f"data:{content_type};base64,{b64_data}"

        logger.info("Image prepared for SwarmUI", size_kb=len(image_bytes) // 1024)
        return data_uri

    async def generate_video(
        self,
        image_path: str,
        prompt: str,
        # GGUF model names (updated 2026-01-15 to match instance)
        model: str = "wan2.2_i2v_high_noise_14B_fp8.gguf",
        width: int = 720,
        height: int = 1280,
        num_frames: int = 80,
        fps: int = 16,
        steps: int = 10,
        cfg_scale: float = 7.0,
        seed: int = -1,
        # Video-specific params (exact from working metadata)
        video_steps: int = 5,
        video_cfg: float = 1.0,
        swap_model: str = "wan2.2_i2v_low_noise_14B_fp8.gguf",
        swap_percent: float = 0.6,
        # Frame interpolation (exact from working metadata)
        interpolation_method: str = "RIFE",
        interpolation_multiplier: int = 2,
        video_resolution: str = "Image Aspect, Model Res",
        video_format: str = "h264-mp4",
        # LoRAs - embedded in prompt using <video> <lora:name> <videoswap> <lora:name> syntax
        lora_high: str = "wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16",
        lora_low: str = "wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16",
        # Negative prompt (exact from working metadata)
        negative_prompt: str = "blurry, jerky motion, stuttering, flickering, frame skipping, ghosting, motion blur, extra fingers, extra hands, extra limbs, missing fingers, missing limbs, deformed hands, mutated hands, fused fingers, bad anatomy, disfigured, malformed, distorted face, ugly, low quality, worst quality, logo, duplicate frames, static, frozen, morphing, warping, glitching, plastic skin",
        # Progress callback
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> dict:
        """
        Generate video from image using SwarmUI with Wan 2.2 I2V via WebSocket.

        Uses WebSocket API for reliable long-running generation without HTTP timeouts.
        LoRAs are embedded in the prompt using SwarmUI's <video> and <videoswap> syntax.

        Args:
            image_path: Init image (base64 data URI)
            prompt: Motion description (LoRAs will be auto-appended)
            model: High-noise model (wan2.2_i2v_high_noise_14B_fp8.gguf)
            width: Output width (720)
            height: Output height (1280)
            num_frames: Video frames (80)
            fps: Video FPS (16)
            steps: Image gen steps (10)
            cfg_scale: Image CFG (7.0)
            seed: Random seed (-1 for random)
            video_steps: Video diffusion steps (5)
            video_cfg: Video CFG (1.0)
            swap_model: Low-noise model to swap to at swap_percent
            swap_percent: When to swap (0.6 = 60%)
            interpolation_method: Frame interpolation (RIFE)
            interpolation_multiplier: Interpolation factor (2)
            video_resolution: Resolution mode ("Image Aspect, Model Res")
            video_format: Output format ("h264-mp4")
            lora_high: Lightning LoRA for video model
            lora_low: Lightning LoRA for swap model
            negative_prompt: Negative prompt for generation
            on_progress: Optional callback for progress updates (0.0-1.0)

        Returns:
            Dict with video_path, video_url, seed, model, frames
        """
        import os
        session_id = await self.get_session()

        # Build prompt with LoRAs embedded using SwarmUI syntax
        # <video> section applies to video model, <videoswap> to swap model
        full_prompt = f"{prompt} <video> <lora:{lora_high}> <videoswap> <lora:{lora_low}>"

        # Build payload - NO loras/loraweights params, they're in the prompt
        payload = {
            "session_id": session_id,
            "prompt": full_prompt,
            "negativeprompt": negative_prompt,
            "model": model,
            "images": 1,
            "seed": seed if seed >= 0 else -1,
            "steps": steps,
            "cfgscale": cfg_scale,
            "aspectratio": "Custom",
            "width": width,
            "height": height,
            "sampler": "euler",
            "scheduler": "simple",
            "initimagecreativity": 0.0,
            "videomodel": model,
            "videoswapmodel": swap_model,
            "videoswappercent": swap_percent,
            "videoframes": num_frames,
            "videosteps": video_steps,
            "videocfg": video_cfg,
            "videoresolution": video_resolution,
            "videoformat": video_format,
            "videoframeinterpolationmultiplier": interpolation_multiplier,
            "videoframeinterpolationmethod": interpolation_method,
            "videofps": fps,
            "automaticvae": True,
            "initimage": image_path,
        }

        logger.info(
            "Submitting video generation via WebSocket",
            model=model,
            swap_model=swap_model,
            frames=num_frames,
            video_steps=video_steps,
        )

        # Build WebSocket URL and auth headers
        ws_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/API/GenerateText2ImageWS"

        headers = {}
        if self.auth_token:
            instance_id = os.getenv("VASTAI_INSTANCE_ID", "")
            if instance_id:
                headers["Cookie"] = f"C.{instance_id}_auth_token={self.auth_token}"
            else:
                headers["Cookie"] = f"auth_token={self.auth_token}"

        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                await ws.send(json.dumps(payload))

                video_path = None
                result_seed = seed

                async for msg in ws:
                    data = json.loads(msg)

                    if "gen_progress" in data:
                        progress = data["gen_progress"].get("overall_percent", 0)
                        if on_progress:
                            on_progress(progress)
                        logger.debug("Generation progress", percent=f"{progress*100:.0f}%")

                    elif "image" in data:
                        img = data["image"]
                        if isinstance(img, dict):
                            video_path = img.get("image", "")
                        else:
                            video_path = str(img)
                        logger.info("Generation complete", path=video_path)
                        break

                    elif "error" in data:
                        raise SwarmUIGenerationError(f"Generation failed: {data['error']}")

                if not video_path:
                    raise SwarmUIGenerationError("No output received from generation")

                return {
                    "video_path": video_path,
                    "video_url": f"{self.base_url}/{video_path}",
                    "seed": result_seed,
                    "model": model,
                    "frames": num_frames,
                }

        except websockets.exceptions.WebSocketException as e:
            raise SwarmUIGenerationError(f"WebSocket error: {e}")

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


def get_swarmui_client(base_url: Optional[str] = None, auth_token: Optional[str] = None) -> SwarmUIClient:
    """
    Get SwarmUI client singleton.

    Args:
        base_url: Override base URL (default from env or localhost:7801)
        auth_token: Override auth token (default from env SWARMUI_AUTH_TOKEN)

    Returns:
        SwarmUIClient instance
    """
    global _swarmui_client

    import os
    if base_url is None:
        base_url = os.getenv("SWARMUI_URL", "http://localhost:7801")
    if auth_token is None:
        auth_token = os.getenv("SWARMUI_AUTH_TOKEN")

    if _swarmui_client is None or _swarmui_client.base_url != base_url:
        _swarmui_client = SwarmUIClient(base_url=base_url, auth_token=auth_token)

    return _swarmui_client
