"""Health-check endpoints.

GET /health        Liveness: the backend process is running. It does not
                   look at the database, so it stays 200 even when the
                   database is down.
GET /health/ready  Readiness: the application is running AND the
                   database answers. Returns 503 when the database is
                   unavailable, so the system is never reported as
                   ready without its database.

Neither endpoint returns configuration secrets, connection strings,
file paths, driver error messages or stack traces.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from app.core.config import Settings, get_settings
from app.db.session import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Successful liveness response."""

    status: Literal["ok"] = Field(description="Always 'ok' when the backend is running.")
    service: str = Field(description="Configured application name.")
    version: str = Field(description="Configured application version.")
    timestamp: str = Field(
        description="Time of this request, UTC, ISO 8601 (generated per request)."
    )


class ReadinessChecks(BaseModel):
    """Result of each readiness check."""

    application: Literal["ok"] = Field(description="The backend process is running.")
    database: Literal["ok", "unavailable"] = Field(
        description="'ok' when the database answers a query, otherwise 'unavailable'."
    )


class ReadinessResponse(BaseModel):
    """Readiness response (HTTP 200 when ready, HTTP 503 when not)."""

    status: Literal["ready", "not_ready"] = Field(
        description="'ready' only when every check is ok."
    )
    service: str = Field(description="Configured application name.")
    version: str = Field(description="Configured application version.")
    timestamp: str = Field(description="Time of this request, UTC, ISO 8601.")
    checks: ReadinessChecks


def get_db_engine(request: Request) -> Engine | None:
    """Return the database engine created at startup, or None.

    None means the database could not be configured (for example a
    missing password). The reason is logged at startup, never returned.
    """
    return getattr(request.app.state, "db_engine", None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Backend health check (liveness)",
    description=(
        "Returns HTTP 200 with the service name, configured version and the "
        "current UTC time when the backend application is running. It does "
        "not check the database. Unexpected failures return HTTP 500 with a "
        "generic error body."
    ),
    responses={500: {"description": "Unexpected internal error (generic message only)."}},
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=_utc_now(),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Backend readiness check (application and database)",
    description=(
        "Returns HTTP 200 when the application is running and the database "
        "answers a query. Returns HTTP 503 with status 'not_ready' and "
        "database 'unavailable' when the database cannot be reached or is "
        "not configured. No connection details or error messages are "
        "returned."
    ),
    responses={
        503: {
            "model": ReadinessResponse,
            "description": "Application is running but the database is unavailable.",
        },
        500: {"description": "Unexpected internal error (generic message only)."},
    },
)
def readiness(
    settings: Settings = Depends(get_settings),
    engine: Engine | None = Depends(get_db_engine),
):
    database_ok = engine is not None and check_database(engine)
    body = ReadinessResponse(
        status="ready" if database_ok else "not_ready",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=_utc_now(),
        checks=ReadinessChecks(
            application="ok",
            database="ok" if database_ok else "unavailable",
        ),
    )
    if database_ok:
        return body
    return JSONResponse(status_code=503, content=body.model_dump())
