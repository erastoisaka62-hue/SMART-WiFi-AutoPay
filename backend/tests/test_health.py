"""Tests for the backend entry point and GET /health.

These tests run the real application through FastAPI's TestClient.
The health endpoint itself is never mocked.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

SETTING_ENV_VARS = (
    "APP_NAME",
    "APP_VERSION",
    "APP_ENV",
    "SERVER_HOST",
    "SERVER_PORT",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Stop the developer's real environment from changing test results."""
    for name in SETTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides) -> Settings:
    """Build Settings for tests, ignoring any local .env file."""
    values = {"app_env": "testing", **overrides}
    return Settings(_env_file=None, **values)


@pytest.fixture
def client():
    # Using the client as a context manager runs startup and shutdown.
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


def test_application_can_be_initialized():
    app = create_app(make_settings())
    assert isinstance(app, FastAPI)
    assert app.title == "SMART Wi-Fi AutoPay"


def test_backend_starts_and_logs_startup_and_shutdown(caplog):
    settings = make_settings(app_version="1.2.3")
    with caplog.at_level("INFO", logger="app"):
        with TestClient(create_app(settings)):
            pass
    assert "Starting SMART Wi-Fi AutoPay v1.2.3" in caplog.text
    assert "Shutting down SMART Wi-Fi AutoPay" in caplog.text


def test_health_returns_200_with_required_fields(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "service", "version", "timestamp"}
    assert body["status"] == "ok"


def test_service_name_is_correct(client):
    assert client.get("/health").json()["service"] == "SMART Wi-Fi AutoPay"


def test_version_comes_from_configuration():
    app = create_app(make_settings(app_version="9.9.9-test"))
    with TestClient(app) as test_client:
        assert test_client.get("/health").json()["version"] == "9.9.9-test"


def test_timestamp_is_valid_utc_iso8601(client):
    raw = client.get("/health").json()["timestamp"]
    parsed = datetime.fromisoformat(raw)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    assert abs(datetime.now(timezone.utc) - parsed) < timedelta(seconds=5)


def test_timestamp_is_generated_per_request(client):
    first = datetime.fromisoformat(client.get("/health").json()["timestamp"])
    time.sleep(0.01)
    second = datetime.fromisoformat(client.get("/health").json()["timestamp"])
    assert second > first


def test_sensitive_values_are_not_exposed(monkeypatch):
    monkeypatch.setenv("API_KEY", "super-secret-value-123")
    monkeypatch.setenv("DATABASE_PASSWORD", "another-secret-456")
    app = create_app(make_settings(server_host="10.99.88.77"))
    with TestClient(app) as test_client:
        text = test_client.get("/health").text
    for forbidden in (
        "super-secret-value-123",
        "another-secret-456",
        "10.99.88.77",
        "Traceback",
        "/home",
    ):
        assert forbidden not in text


def test_unexpected_error_returns_generic_500():
    app = create_app(make_settings())

    @app.get("/_boom")
    def boom():
        raise RuntimeError("secret-detail-xyz")

    test_client = TestClient(app, raise_server_exceptions=False)
    response = test_client.get("/_boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret-detail-xyz" not in response.text


def test_health_only_allows_get(client):
    assert client.post("/health").status_code == 405


def test_docs_are_available_outside_production(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/health"]


def test_docs_are_disabled_in_production():
    app = create_app(make_settings(app_env="production"))
    with TestClient(app) as test_client:
        assert test_client.get("/docs").status_code == 404
        assert test_client.get("/openapi.json").status_code == 404
