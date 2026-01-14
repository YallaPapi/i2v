from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required
    fal_api_key: str

    # Optional - for prompt enhancement
    anthropic_api_key: Optional[str] = None

    # RunPod GPU pod settings
    runpod_api_key: Optional[str] = None
    vast_api_key: Optional[str] = None
    runpod_pod_id: Optional[str] = None
    runpod_pod_url: Optional[str] = None
    runpod_enabled: bool = False

    # Cloudflare Zero Trust Tunnel (for SwarmUI access)
    cloudflare_tunnel_token: Optional[str] = None
    swarmui_url: Optional[str] = None  # Tunnel URL (e.g., https://xxx.trycloudflare.com)
    swarmui_auth_token: Optional[str] = None  # Auth token from tunnel URL ?token=xxx
    vastai_instance_id: Optional[str] = None  # Vast.ai instance ID

    # SwarmUI generation defaults (EXACT from working metadata 2026-01-14)
    swarmui_model: str = "wan2.2_i2v_high_noise_14B_fp8_scaled"
    swarmui_swap_model: str = "wan2.2_i2v_low_noise_14B_fp8_scaled"
    swarmui_default_steps: int = 10
    swarmui_default_cfg: float = 7.0
    swarmui_default_frames: int = 80
    swarmui_default_fps: int = 16
    swarmui_video_steps: int = 5
    swarmui_video_cfg: float = 1.0
    swarmui_swap_percent: float = 0.6
    # LoRAs with section confinement (high_fp16 for video model, low_fp16 for swap model)
    swarmui_lora_high: str = "wan2.2-lightning_i2v-a14b-4steps-lora_high_fp16"
    swarmui_lora_low: str = "wan2.2-lightning_i2v-a14b-4steps-lora_low_fp16"

    # Pinokio WAN GP settings (Vast.ai self-hosted)
    pinokio_wan_url: Optional[str] = None  # Cloudflare tunnel URL
    pinokio_ssh_host: Optional[str] = None  # SSH host (e.g., ssh9.vast.ai)
    pinokio_ssh_port: int = 28690  # SSH port
    pinokio_ssh_user: str = "root"  # SSH user
    pinokio_max_concurrent: int = 1  # WAN GP processes sequentially
    pinokio_enabled: bool = False  # Enable Pinokio backend

    @property
    def pinokio_ssh_config(self) -> Optional[dict]:
        """Get SSH config dict for PinokioClient if configured."""
        if self.pinokio_ssh_host:
            return {
                "host": self.pinokio_ssh_host,
                "port": self.pinokio_ssh_port,
                "user": self.pinokio_ssh_user,
            }
        return None

    # Database - SQLite (default for local dev) or PostgreSQL (production)
    db_path: str = "wan_jobs.db"  # SQLite path (used when database_url not set)
    database_url: Optional[str] = None  # PostgreSQL URL: postgresql+asyncpg://user:pass@host/db

    # Auth & Security
    jwt_secret_key: str = secrets.token_urlsafe(32)  # Auto-generate if not set (set in prod!)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days default
    refresh_token_expire_minutes: int = 60 * 24 * 30  # 30 days

    # User defaults
    default_user_tier: str = "starter"  # starter, pro, agency
    default_user_credits: int = 0

    # Rate limiting (enforced at nginx/cloudflare, but defined here for reference)
    login_rate_limit_per_minute: int = 10
    signup_rate_limit_per_minute: int = 5

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"  # Comma-separated

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL."""
        return self.database_url is not None and self.database_url.startswith("postgresql")

    # Worker
    worker_poll_interval_seconds: int = 10
    worker_max_concurrency: int = 5
    max_concurrent_submits: int = 20
    max_concurrent_polls: int = 20

    # Auto-download
    auto_download_dir: str = "downloads"

    # Upload cache
    upload_cache_enabled: bool = True

    # Defaults
    default_resolution: str = "1080p"
    default_duration_sec: int = 5

    def ensure_download_dir(self) -> Path:
        """Ensure download directory exists and return Path."""
        path = Path(self.auto_download_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
