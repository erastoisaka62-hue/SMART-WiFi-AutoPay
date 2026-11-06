"""Health-check endpoint.

GET /health reports that the backend process is running. It does not
check the database, router or payment provider (none exist yet) and it
never returns configuration secrets, file paths or stack traces.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Successful health-check response."""

    status: Literal["ok"] = Field(description="Always 'ok' when the backend is running.")
    service: str = Field(description="Configured application name.")
    version: str = Field(description="Configured application version.")
    timestamp: str = Field(
        description="Time of this request, UTC, ISO 8601 (generated per request)."
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Backend health check",
    description=(
        "Returns HTTP 200 with the service name, configured version and the "
        "current UTC time when the backend application is running. "
        "Unexpected failures return HTTP 500 with a generic error body."
    ),
    responses={500: {"description": "Unexpected internal error (generic message only)."}},
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
