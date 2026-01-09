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
