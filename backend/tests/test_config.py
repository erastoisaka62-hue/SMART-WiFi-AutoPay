# FILE: backend/tests/test_config.py

"""Tests for application and PostgreSQL configuration."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def make_settings(**overrides):
    """Build settings without reading the developer's local .env file."""
    return Settings(_env_file=None, **overrides)


# Default configuration

def test_default_application_settings():
    settings = make_settings()

    assert settings.app_name == "SMART Wi-Fi AutoPay"
    assert settings.app_version == "0.1.0"
    assert settings.app_env == "development"
    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 8000
    assert settings.log_level == "INFO"


def test_default_database_settings():
    settings = make_settings()

    assert settings.db_host == "127.0.0.1"
    assert settings.db_port == 5432
    assert settings.db_name == "smart_wifi_autopay"
    assert settings.db_user == "autopay_app"
    assert settings.db_password is None


# Valid application configuration

@pytest.mark.parametrize(
    "app_env",
    ["development", "testing", "production"],
)
def test_supported_application_environments(app_env):
    settings = make_settings(app_env=app_env)
    assert settings.app_env == app_env


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Production", "production"),
        (" TESTING ", "testing"),
        ("DEVELOPMENT", "development"),
    ],
)
def test_application_environment_is_normalized(value, expected):
    settings = make_settings(app_env=value)
    assert settings.app_env == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("debug", "DEBUG"),
        ("Info", "INFO"),
        (" warning ", "WARNING"),
        ("error", "ERROR"),
        ("critical", "CRITICAL"),
    ],
)
def test_log_level_is_normalized(value, expected):
    settings = make_settings(log_level=value)
    assert settings.log_level == expected


def test_text_settings_are_trimmed():
    settings = make_settings(
        app_name="  Test Application  ",
        app_version="  2.0.0  ",
        server_host="  192.168.1.10  ",
    )

    assert settings.app_name == "Test Application"
    assert settings.app_version == "2.0.0"
    assert settings.server_host == "192.168.1.10"


# Invalid application configuration

@pytest.mark.parametrize(
    "app_env",
    ["", "invalid", "staging", "production-mode"],
)
def test_invalid_application_environment_is_rejected(app_env):
    with pytest.raises(ValidationError):
        make_settings(app_env=app_env)


@pytest.mark.parametrize(
    "log_level",
    ["", "TRACE", "VERBOSE", "invalid"],
)
def test_invalid_log_level_is_rejected(log_level):
    with pytest.raises(ValidationError):
        make_settings(log_level=log_level)


@pytest.mark.parametrize(
    "server_port",
    [0, -1, 65536],
)
def test_invalid_server_port_is_rejected(server_port):
    with pytest.raises(ValidationError):
        make_settings(server_port=server_port)


@pytest.mark.parametrize(
    "db_port",
    [0, -1, 65536],
)
def test_invalid_database_port_is_rejected(db_port):
    with pytest.raises(ValidationError):
        make_settings(db_port=db_port)


@pytest.mark.parametrize(
    "field",
    [
        "app_name",
        "app_version",
        "server_host",
        "db_host",
        "db_name",
        "db_user",
    ],
)
def test_blank_required_text_settings_are_rejected(field):
    with pytest.raises(ValidationError):
        make_settings(**{field: "   "})


# PostgreSQL configuration

def test_database_password_can_be_missing():
    settings = make_settings(db_password=None)
    assert settings.db_password is None


def test_database_password_is_stored_as_secret():
    settings = make_settings(db_password="test-password-123")

    assert isinstance(settings.db_password, SecretStr)
    assert settings.db_password.get_secret_value() == "test-password-123"


def test_empty_database_password_becomes_missing():
    settings = make_settings(db_password="   ")
    assert settings.db_password is None


def test_database_password_is_not_exposed_in_string_representation():
    secret = "private-db-password-987"
    settings = make_settings(db_password=secret)

    assert secret not in str(settings)
    assert secret not in repr(settings)


def test_database_configuration_accepts_custom_values():
    settings = make_settings(
        db_host="192.168.1.20",
        db_port=5433,
        db_name="customer_database",
        db_user="database_user",
        db_password="private-password",
    )

    assert settings.db_host == "192.168.1.20"
    assert settings.db_port == 5433
    assert settings.db_name == "customer_database"
    assert settings.db_user == "database_user"
    assert settings.db_password.get_secret_value() == "private-password"


# Environment variable loading

def test_application_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Environment Test")
    monkeypatch.setenv("APP_ENV", "TESTING")
    monkeypatch.setenv("SERVER_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Environment Test"
    assert settings.app_env == "testing"
    assert settings.server_port == 9000
    assert settings.log_level == "DEBUG"


def test_database_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "test_database")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test-secret-password")

    settings = Settings(_env_file=None)

    assert settings.db_host == "localhost"
    assert settings.db_port == 5433
    assert settings.db_name == "test_database"
    assert settings.db_user == "test_user"
    assert isinstance(settings.db_password, SecretStr)
    assert settings.db_password.get_secret_value() == "test-secret-password"


def test_invalid_environment_port_is_rejected(monkeypatch):
    monkeypatch.setenv("SERVER_PORT", "not-a-number")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_database_environment_port_is_rejected(monkeypatch):
    monkeypatch.setenv("DB_PORT", "not-a-number")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
