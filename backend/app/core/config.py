
"""Central application configuration.

All settings are read from environment variables or a local .env file.
Invalid application settings are rejected during validation.

Database credentials are optional at configuration time so the backend
can start even when PostgreSQL is not configured. Database connection
creation validates the password separately.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings for SMART Wi-Fi AutoPay."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application identity
    app_name: str = Field(default="SMART Wi-Fi AutoPay", min_length=1)
    app_version: str = Field(default="0.1.0", min_length=1)

    app_env: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    # Backend server
    server_host: str = Field(default="127.0.0.1", min_length=1)
    server_port: int = Field(default=8000, ge=1, le=65535)

    # Logging
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    # PostgreSQL configuration
    # Password is optional here so the backend can start without DB setup.
    db_host: str = Field(default="127.0.0.1", min_length=1)
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = Field(default="smart_wifi_autopay", min_length=1)
    db_user: str = Field(default="autopay_app", min_length=1)
    db_password: SecretStr | None = None

    @field_validator(
        "app_name",
        "app_version",
        "server_host",
        "db_host",
        "db_name",
        "db_user",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        """Trim text fields and reject blank values through validation."""
        return value.strip() if isinstance(value, str) else value

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> object:
        """Normalize environment names."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        """Normalize logging levels."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("db_password", mode="before")
    @classmethod
    def normalize_db_password(cls, value: object) -> object:
        """Treat an empty password as missing without exposing its value."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
    
