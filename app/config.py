from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database
    db_path: str = "wan_jobs.db"

    # Worker
    worker_poll_interval_seconds: int = 10
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
