"""SMART Wi-Fi AutoPay backend entry point.

Start from the "backend/" directory:

    python -m app.main

Interactive API documentation is served at /docs (disabled when
APP_ENV=production).
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health_routes import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application from validated settings."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info(
            "Starting %s v%s (env=%s, host=%s, port=%s)",
            settings.app_name,
            settings.app_version,
            settings.app_env,
            settings.server_host,
            settings.server_port,
        )
        yield
        logger.info("Shutting down %s", settings.app_name)

    is_production = settings.app_env == "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )

    # Routes and tests read the same settings object this app was built with.
    app.dependency_overrides[get_settings] = lambda: settings

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # The full traceback goes to the log only, never to the client.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health_router)
    return app


app = create_app()


def run() -> None:
    """Run the backend with Uvicorn using the configured host and port."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
