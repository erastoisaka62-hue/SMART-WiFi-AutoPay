"""PostgreSQL connection handling.

- Builds the connection URL from validated settings. The password is
  passed to the driver as a structured value, so special characters need
  no escaping and the password never appears in a text URL or in logs.
- Refuses to connect when the password is missing or is the
  "CHANGE_ME" placeholder from .env.example.
- Creating an engine does not open a connection; the first query does.
- Sessions commit on success and roll back on any error.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

logger = logging.getLogger("app.db")

PLACEHOLDER_PASSWORD = "CHANGE_ME"


class DatabaseConfigurationError(RuntimeError):
    """Raised when database settings are missing or unsafe."""


def build_database_url(settings: Settings) -> URL:
    """Build the SQLAlchemy URL for the psycopg 3 PostgreSQL driver."""
    password = settings.db_password.get_secret_value() if settings.db_password else ""
    if not password.strip() or password.strip().upper() == PLACEHOLDER_PASSWORD:
        raise DatabaseConfigurationError(
            "DB_PASSWORD is missing or still the placeholder. "
            "Set a real password in your private .env file."
        )
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.db_user,
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def create_db_engine(settings: Settings) -> Engine:
    """Create a connection-pooled engine (no connection is opened yet)."""
    return create_engine(
        build_database_url(settings),
        pool_pre_ping=True,  # drop dead connections after a restart or outage
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": 5,
            "options": "-c timezone=UTC",  # every session works in UTC
            "application_name": "smart-wifi-autopay",
        },
    )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Run a unit of work: commit on success, roll back on any error."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        yield session


def check_database(engine: Engine) -> bool:
    """Return True if the database answers a trivial query.

    Only the error class is logged: driver messages can contain
    connection details that must not reach logs or API responses.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Database check failed: %s", type(exc).__name__)
        return False
