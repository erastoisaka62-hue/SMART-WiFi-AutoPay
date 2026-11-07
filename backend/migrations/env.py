"""Alembic environment for SMART Wi-Fi AutoPay.

- The database connection is built from the validated application
  settings (DB_* variables in the private .env file) through the same
  code the backend uses, so no password or connection string is stored
  in alembic.ini or Git.
- Only online migrations are supported. Offline mode (--sql) would have
  to print a connection and is deliberately disabled.
- Run from the "backend/" directory: python -m alembic upgrade head
- Migrations run inside a transaction (PostgreSQL supports transactional
  DDL), so a failed migration is rolled back instead of leaving a
  half-built schema.
"""

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import DatabaseConfigurationError, create_db_engine

# Importing the package registers all 16 tables on Base.metadata.
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # Keep the application's own loggers working.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against the configured PostgreSQL database."""
    # Tests can hand over an existing connection (to an isolated test
    # database); otherwise one is created from application settings.
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return

    try:
        engine = create_db_engine(get_settings())
    except DatabaseConfigurationError as exc:
        raise SystemExit(f"Migration aborted: {exc}") from exc

    try:
        with engine.connect() as new_connection:
            _migrate(new_connection)
    finally:
        engine.dispose()


def _migrate(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit(
        "Offline (--sql) migrations are not supported. "
        "Run migrations against a real database."
    )

run_migrations_online()
