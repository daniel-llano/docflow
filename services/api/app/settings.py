from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_SECRET = "local-development-signing-key-not-for-production"
_LOCAL_INTERNAL_KEY = "local-internal-key"


class Settings(BaseSettings):
    """Everything comes from environment variables (or a .env file next to the service)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./docflow.db"
    redis_url: str = ""
    jwt_secret: str = _LOCAL_SECRET
    jwt_minutes: int = 480
    internal_key: str = _LOCAL_INTERNAL_KEY
    cors_origins: str = "http://localhost:3006"
    webhook_url: str = ""
    webhook_secret: str = ""
    inline_worker: bool | None = None
    max_attempts: int = 3
    max_upload_mb: int = 5
    bootstrap_email: str = ""
    bootstrap_password: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters.")
        if self.is_production:
            if self.jwt_secret == _LOCAL_SECRET:
                raise ValueError("Set JWT_SECRET before running with APP_ENV=production.")
            if self.internal_key == _LOCAL_INTERNAL_KEY or len(self.internal_key) < 24:
                raise ValueError("Set INTERNAL_KEY (24+ characters) before running with APP_ENV=production.")
            if self.webhook_url and len(self.webhook_secret) < 24:
                raise ValueError("Set WEBHOOK_SECRET (24+ characters) when WEBHOOK_URL is set in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
