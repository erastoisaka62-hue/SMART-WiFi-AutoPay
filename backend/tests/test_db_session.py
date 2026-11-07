# FILE: backend/tests/test_db_session.py

"""Tests for PostgreSQL connection and session utilities."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import (
    DatabaseConfigurationError,
    build_database_url,
    check_database,
    create_db_engine,
    session_scope,
)


def make_settings(**overrides):
    """Build isolated settings without loading a local .env file."""
    values = {
        "app_env": "testing",
        "db_password": "test-db-password",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# Database URL construction


def test_database_url_uses_psycopg_driver():
    settings = make_settings()
    url = build_database_url(settings)

    assert url.drivername == "postgresql+psycopg"


def test_database_url_contains_expected_connection_details():
    settings = make_settings(
        db_host="192.168.1.20",
        db_port=5433,
        db_name="test_database",
        db_user="test_user",
    )

    url = build_database_url(settings)

    assert url.host == "192.168.1.20"
    assert url.port == 5433
    assert url.database == "test_database"
    assert url.username == "test_user"


def test_database_url_preserves_special_characters_in_password():
    password = "p@ss:/word%123"
    settings = make_settings(db_password=password)

    url = build_database_url(settings)

    assert url.password == password
    assert password not in url.render_as_string(hide_password=True)


@pytest.mark.parametrize(
    "password",
    [None, "", "   ", "CHANGE_ME", "change_me"],
)
def test_missing_or_placeholder_password_is_rejected(password):
    settings = make_settings(db_password=password)

    with pytest.raises(DatabaseConfigurationError):
        build_database_url(settings)


def test_database_configuration_error_does_not_expose_password():
    secret = "private-database-password"
    settings = make_settings(db_password=secret)

    with pytest.raises(DatabaseConfigurationError):
        build_database_url(
            make_settings(db_password="CHANGE_ME")
        )

    assert secret not in repr(settings)


# Engine creation


def test_engine_uses_postgresql_psycopg_dialect():
    engine = create_db_engine(make_settings())

    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


def test_engine_has_pre_ping_enabled():
    engine = create_db_engine(make_settings())

    try:
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


# Session transaction handling


def test_session_scope_commits_successful_transaction():
    engine = create_engine("sqlite:///:memory:")

    try:
        with session_scope(engine) as session:
            session.execute(
                text("CREATE TABLE test_items (id INTEGER PRIMARY KEY)")
            )
            session.execute(
                text("INSERT INTO test_items (id) VALUES (1)")
            )

        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT COUNT(*) FROM test_items")
            ).scalar_one()

        assert result == 1
    finally:
        engine.dispose()


def test_session_scope_rolls_back_failed_transaction():
    engine = create_engine("sqlite:///:memory:")

    try:
        with pytest.raises(RuntimeError):
            with session_scope(engine) as session:
                session.execute(
                    text(
                        "CREATE TABLE test_items "
                        "(id INTEGER PRIMARY KEY)"
                    )
                )
                session.execute(
                    text("INSERT INTO test_items (id) VALUES (1)")
                )
                raise RuntimeError("force rollback")

        with engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name='test_items'"
                )
            ).scalar_one()

        assert result == 0
    finally:
        engine.dispose()


# Database health check


def test_check_database_returns_true_when_query_succeeds():
    engine = create_engine("sqlite:///:memory:")

    try:
        assert check_database(engine) is True
    finally:
        engine.dispose()


def test_check_database_returns_false_when_query_fails():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect = SQLAlchemyError("database unavailable")

    assert check_database(engine) is False


def test_check_database_does_not_expose_database_error_details(caplog):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect = SQLAlchemyError(
        "secret connection details"
    )

    assert check_database(engine) is False
    assert "secret connection details" not in caplog.text
