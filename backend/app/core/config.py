"""Central application configuration.

All settings are read from environment variables (or a local ".env"
file) and validated once at startup. Invalid values stop the backend
with a clear error instead of being silently accepted.

Secrets must never be given defaults here or committed to Git.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings for SMART Wi-Fi AutoPay."""

    # ".env" is resolved relative to the directory the backend is
    # started from (documented: start the backend from "backend/").
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="SMART Wi-Fi AutoPay", min_length=1)
    app_version: str = Field(default="0.1.0", min_length=1)
    app_env: Literal["development", "testing", "production"] = "development"

    # 127.0.0.1 keeps the backend reachable from this machine only.
    server_host: str = Field(default="127.0.0.1", min_length=1)
    server_port: int = Field(default=8000, ge=1, le=65535)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("app_name", "app_version", "server_host", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        """Trim whitespace so blank-looking values are rejected."""
        return value.strip() if isinstance(value, str) else value

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_env(cls, value: object) -> object:
        """Accept 'Production', ' production ' etc."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        """Accept 'info', 'Info' etc."""
        return value.strip().upper() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    """Return the single validated Settings instance (loaded once)."""
    return Settings()
