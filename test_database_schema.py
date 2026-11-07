"""Schema tests for the 16 core tables of SMART Wi-Fi AutoPay.

These tests inspect the REAL SQLAlchemy metadata registered by the models
in app/models. They need NO database connection, so they are fast and
deterministic and can run anywhere.

LIMITATIONS (metadata only). These tests do NOT prove:
- that the Alembic migration runs on PostgreSQL;
- that the tables really exist in a database;
- that foreign keys, unique constraints/indexes or CHECK constraints are
  enforced at runtime (that rows violating them are rejected);
- transaction rollback behaviour.
Those need separate integration tests against a real, isolated PostgreSQL
test database. Nothing here connects to or modifies any database.

Run from the "backend/" directory:

    python -m pytest tests/test_database_schema.py -v

The expected structure below is written out explicitly on purpose. If a
model changes, the matching entry here must change in the same commit, so
an accidental schema change cannot go unnoticed.
"""

import re

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Importing the package registers all 16 tables on Base.metadata.
import app.models  # noqa: F401
from app.db.base import Base

metadata = Base.metadata

EXPECTED_NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(column_0_label)s",
}

POSTGRES_IDENTIFIER_LIMIT = 63


def ix(columns, unique=False, where=None):
    """Describe an expected index: (columns, unique, partial-index WHERE)."""
    return (list(columns), unique, where)


# Expected structure of every table. "fks" are (column, referred table);
# every foreign key must be ON DELETE RESTRICT and point at the "id" column.
# "uniques" are unique CONSTRAINTS; "indexes" include partial unique indexes.
# "checks" are the CHECK constraint names without the "ck_<table>_" prefix.
SCHEMA = {
    "sites": {
        "fks": [],
        "uniques": {"uq_sites_name": ["name"]},
        "indexes": {},
        "checks": ["status_valid", "name_not_blank", "timezone_not_blank"],
    },
    "admin_users": {
        "fks": [],
        "uniques": {"uq_admin_users_username": ["username"]},
        "indexes": {},
        "checks": [
            "status_valid",
            "username_min_length",
            "username_lowercase",
            "password_hash_not_trivial",
        ],
    },
    "customers": {
        "fks": [("site_id", "sites")],
        "uniques": {
            "uq_customers_site_id_customer_reference": ["site_id", "customer_reference"]
        },
        "indexes": {
            "uq_customers_site_id_phone_number": ix(
                ["site_id", "phone_number"], True, "phone_number IS NOT NULL"
            ),
            "ix_customers_site_id_status": ix(["site_id", "status"]),
        },
        "checks": ["status_valid", "reference_not_blank", "phone_format_valid"],
    },
    "packages": {
        "fks": [("site_id", "sites")],
        "uniques": {"uq_packages_site_id_name": ["site_id", "name"]},
        "indexes": {"ix_packages_site_id_status": ix(["site_id", "status"])},
        "checks": [
            "status_valid",
            "name_not_blank",
            "price_positive",
            "duration_positive",
            "device_limit_at_least_one",
        ],
    },
    "pricing_rules": {
        "fks": [("site_id", "sites")],
        "uniques": {},
        "indexes": {
            "uq_pricing_rules_site_id_active": ix(
                ["site_id"], True, "status = 'ACTIVE'"
            ),
            "ix_pricing_rules_site_id_status": ix(["site_id", "status"]),
        },
        "checks": [
            "status_valid",
            "duration_policy_valid",
            "rounding_policy_valid",
            "min_amount_positive",
            "max_amount_not_below_min",
            "price_per_hour_positive",
            "rounding_step_positive",
            "min_duration_positive",
            "max_duration_not_below_min",
            "device_limit_at_least_one",
        ],
    },
    "devices": {
        "fks": [("site_id", "sites"), ("customer_id", "customers")],
        "uniques": {},
        "indexes": {
            "uq_devices_site_id_mac_address_not_revoked": ix(
                ["site_id", "mac_address"], True, "status <> 'REVOKED'"
            ),
            "ix_devices_customer_id": ix(["customer_id"]),
            "ix_devices_site_id_status": ix(["site_id", "status"]),
        },
        "checks": ["status_valid", "mac_format_valid"],
    },
    "device_enrollment_requests": {
        "fks": [
            ("site_id", "sites"),
            ("customer_id", "customers"),
            ("reviewed_by", "admin_users"),
            ("device_id", "devices"),
        ],
        "uniques": {},
        "indexes": {
            "uq_device_enrollment_requests_pending_customer_mac": ix(
                ["customer_id", "requested_mac_address"], True, "status = 'PENDING'"
            ),
            "ix_device_enrollment_requests_customer_id": ix(["customer_id"]),
            "ix_device_enrollment_requests_site_id_status": ix(["site_id", "status"]),
        },
        "checks": [
            "status_valid",
            "mac_format_valid",
            "review_fields_consistent",
            "device_only_when_approved",
        ],
    },
    "payments": {
        "fks": [
            ("site_id", "sites"),
            ("customer_id", "customers"),
            ("package_id", "packages"),
        ],
        "uniques": {"uq_payments_internal_reference": ["internal_reference"]},
        "indexes": {
            "uq_payments_provider_provider_reference_active": ix(
                ["provider", "provider_reference"],
                True,
                "provider_reference IS NOT NULL AND status <> 'DUPLICATE'",
            ),
            "ix_payments_customer_id": ix(["customer_id"]),
            "ix_payments_site_id_status_created_at": ix(
                ["site_id", "status", "created_at"]
            ),
            "ix_payments_package_id": ix(["package_id"]),
        },
        "checks": [
            "status_valid",
            "amount_positive",
            "verified_amount_positive",
            "currency_format_valid",
            "provider_lowercase_not_blank",
            "internal_reference_not_blank",
            "provider_reference_not_blank",
            "confirmed_requires_verification",
            "verification_only_when_confirmed",
            "pricing_snapshot_is_object",
        ],
    },
    "entitlements": {
        "fks": [
            ("site_id", "sites"),
            ("customer_id", "customers"),
            ("payment_id", "payments"),
            ("package_id", "packages"),
        ],
        "uniques": {"uq_entitlements_payment_id": ["payment_id"]},
        "indexes": {
            "ix_entitlements_customer_id_status": ix(["customer_id", "status"]),
            "ix_entitlements_active_expires_at": ix(
                ["expires_at"], False, "status = 'ACTIVE'"
            ),
            "ix_entitlements_site_id_status": ix(["site_id", "status"]),
            "ix_entitlements_package_id": ix(["package_id"]),
        },
        "checks": [
            "status_valid",
            "granted_amount_positive",
            "granted_duration_positive",
            "device_limit_at_least_one",
            "expiry_after_start",
        ],
    },
    "sessions": {
        "fks": [
            ("site_id", "sites"),
            ("customer_id", "customers"),
            ("entitlement_id", "entitlements"),
        ],
        "uniques": {},
        "indexes": {
            "uq_sessions_entitlement_id_live": ix(
                ["entitlement_id"],
                True,
                "status IN ('PENDING', 'ACTIVE', 'SUSPENDED')",
            ),
            "ix_sessions_site_id_status": ix(["site_id", "status"]),
            "ix_sessions_customer_id": ix(["customer_id"]),
            "ix_sessions_active_expires_at": ix(
                ["expires_at"], False, "status = 'ACTIVE'"
            ),
        },
        "checks": [
            "status_valid",
            "times_set_when_started",
            "expiry_after_start",
            "revoked_at_matches_status",
            "gateway_reference_not_blank",
        ],
    },
    "session_devices": {
        "fks": [("session_id", "sessions"), ("device_id", "devices")],
        "uniques": {},
        "indexes": {
            "uq_session_devices_session_id_device_id_active": ix(
                ["session_id", "device_id"], True, "status = 'ACTIVE'"
            ),
            "uq_session_devices_device_id_active": ix(
                ["device_id"], True, "status = 'ACTIVE'"
            ),
            "ix_session_devices_session_id_status": ix(["session_id", "status"]),
            "ix_session_devices_device_id": ix(["device_id"]),
        },
        "checks": [
            "status_valid",
            "disconnected_at_matches_status",
            "disconnect_not_before_connect",
        ],
    },
    "security_events": {
        "fks": [
            ("site_id", "sites"),
            ("customer_id", "customers"),
            ("device_id", "devices"),
            ("reviewed_by", "admin_users"),
        ],
        "uniques": {},
        "indexes": {
            "ix_security_events_site_id_review_status_occurred_at": ix(
                ["site_id", "review_status", "occurred_at"]
            ),
            "ix_security_events_customer_id": ix(["customer_id"]),
            "ix_security_events_device_id": ix(["device_id"]),
        },
        "checks": [
            "review_status_valid",
            "confidence_valid",
            "event_type_format_valid",
            "evidence_not_blank",
            "review_fields_consistent",
        ],
    },
    "sharing_warnings": {
        "fks": [
            ("customer_id", "customers"),
            ("security_event_id", "security_events"),
            ("decided_by", "admin_users"),
        ],
        "uniques": {
            "uq_sharing_warnings_security_event_id": ["security_event_id"],
            "uq_sharing_warnings_customer_id_warning_number": [
                "customer_id",
                "warning_number",
            ],
        },
        "indexes": {
            "ix_sharing_warnings_customer_id": ix(["customer_id"]),
            "ix_sharing_warnings_pending_review": ix(
                ["warned_at"], False, "status = 'SUSPENSION_PENDING_REVIEW'"
            ),
        },
        "checks": [
            "status_valid",
            "warning_number_valid",
            "policy_and_decision_consistent",
        ],
    },
    "audit_logs": {
        "fks": [("site_id", "sites")],
        "uniques": {},
        "indexes": {
            "ix_audit_logs_site_id_occurred_at": ix(["site_id", "occurred_at"]),
            "ix_audit_logs_actor_type_actor_id": ix(["actor_type", "actor_id"]),
            "ix_audit_logs_affected_record": ix(
                ["affected_record_type", "affected_record_id"]
            ),
            "ix_audit_logs_action_occurred_at": ix(["action", "occurred_at"]),
        },
        "checks": [
            "actor_type_valid",
            "actor_id_matches_actor_type",
            "action_format_valid",
            "record_type_format_valid",
            "record_type_and_id_together",
            "safe_metadata_is_object",
            "safe_metadata_no_secret_keys",
        ],
    },
    "system_settings": {
        "fks": [("site_id", "sites")],
        "uniques": {},
        "indexes": {
            "uq_system_settings_site_id_setting_key": ix(
                ["site_id", "setting_key"], True, "site_id IS NOT NULL"
            ),
            "uq_system_settings_setting_key_global": ix(
                ["setting_key"], True, "site_id IS NULL"
            ),
        },
        "checks": [
            "data_type_valid",
            "setting_key_format_valid",
            "setting_key_not_secret",
            "value_matches_data_type",
        ],
    },
    "health_events": {
        "fks": [],
        "uniques": {},
        "indexes": {
            "ix_health_events_component_occurred_at": ix(
                ["component", "occurred_at"]
            ),
            "ix_health_events_status_occurred_at": ix(["status", "occurred_at"]),
        },
        "checks": [
            "status_valid",
            "component_format_valid",
            "event_type_format_valid",
            "description_not_blank_and_short",
            "description_no_secret_pairs",
        ],
    },
}

EXPECTED_TABLES = sorted(SCHEMA)

# Exact decimal money columns: NUMERIC(12, 2), never floating point.
MONEY_COLUMNS = {
    "packages": ["price"],
    "pricing_rules": ["min_amount", "max_amount", "price_per_hour"],
    "payments": ["amount", "verified_amount"],
    "entitlements": ["granted_amount"],
}

# Append-only tables are designed without an update timestamp.
APPEND_ONLY_TABLES = {"audit_logs", "health_events"}


def table_of(name: str) -> sa.Table:
    assert name in metadata.tables, f"Table '{name}' is not registered in metadata"
    return metadata.tables[name]


def normalize(text) -> str:
    """Collapse whitespace so SQL text compares reliably."""
    return " ".join(str(text).split())


def check_constraints_of(table: sa.Table) -> dict[str, str]:
    return {
        str(c.name): normalize(c.sqltext)
        for c in table.constraints
        if isinstance(c, sa.CheckConstraint)
    }


def unique_constraints_of(table: sa.Table) -> dict[str, list[str]]:
    return {
        str(c.name): [col.name for col in c.columns]
        for c in table.constraints
        if isinstance(c, sa.UniqueConstraint)
    }


def indexes_of(table: sa.Table) -> dict[str, tuple]:
    result = {}
    for index in table.indexes:
        where = index.dialect_options["postgresql"]["where"]
        result[str(index.name)] = (
            [col.name for col in index.columns],
            bool(index.unique),
            normalize(where) if where is not None else None,
        )
    return result


# ------------------------------------------------------------- tables
def test_naming_convention_is_the_required_one():
    assert dict(metadata.naming_convention) == EXPECTED_NAMING_CONVENTION, (
        "Base.metadata.naming_convention differs from the required convention"
    )


def test_exactly_the_16_expected_tables_are_registered():
    registered = set(metadata.tables)
    expected = set(EXPECTED_TABLES)
    assert len(expected) == 16, "The test itself must list exactly 16 tables"
    assert registered == expected, (
        f"Missing tables: {sorted(expected - registered)}; "
        f"unexpected tables: {sorted(registered - expected)}"
    )


def test_tables_are_ordered_after_the_tables_they_reference():
    position = {t.name: i for i, t in enumerate(metadata.sorted_tables)}
    for table in metadata.sorted_tables:
        for fk in table.foreign_keys:
            referred = fk.column.table.name
            assert referred == table.name or position[referred] < position[table.name], (
                f"'{table.name}' is sorted before the table it references: '{referred}'"
            )


# ------------------------------------------------------- primary keys
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_primary_key_is_a_single_uuid_id_column(table_name):
    table = table_of(table_name)
    pk = table.primary_key
    assert [c.name for c in pk.columns] == ["id"], (
        f"{table_name}: primary key must be exactly ['id']"
    )
    assert str(pk.name) == f"pk_{table_name}", (
        f"{table_name}: primary key is named '{pk.name}', expected 'pk_{table_name}'"
    )
    id_column = table.c.id
    assert isinstance(id_column.type, postgresql.UUID), (
        f"{table_name}.id must be a PostgreSQL UUID, got {id_column.type!r}"
    )
    assert id_column.nullable is False, f"{table_name}.id must be NOT NULL"
    assert id_column.server_default is not None, (
        f"{table_name}.id needs a server default"
    )
    assert "gen_random_uuid()" in normalize(id_column.server_default.arg), (
        f"{table_name}.id must default to gen_random_uuid()"
    )


# ------------------------------------------------------- foreign keys
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_foreign_keys_match_the_design(table_name):
    table = table_of(table_name)
    actual = {}
    for fk in table.foreign_keys:
        # Accessing fk.column fails loudly if the target table/column is missing.
        target = fk.column
        assert target.name == "id", (
            f"{table_name}.{fk.parent.name} must reference an 'id' column, "
            f"got '{target.table.name}.{target.name}'"
        )
        assert target.table.name in metadata.tables, (
            f"{table_name}.{fk.parent.name} references unknown table "
            f"'{target.table.name}'"
        )
        actual[fk.parent.name] = (
            target.table.name,
            fk.ondelete,
            str(fk.constraint.name),
        )

    expected = {
        column: (
            referred,
            "RESTRICT",
            f"fk_{table_name}_{column}_{referred}",
        )
        for column, referred in SCHEMA[table_name]["fks"]
    }
    assert actual == expected, (
        f"{table_name}: foreign keys differ. "
        f"Expected {expected}, found {actual}. "
        "History must be protected: every foreign key is ON DELETE RESTRICT."
    )


def test_foreign_key_columns_used_for_lookups_are_indexed():
    """Each foreign key column must start an index or a unique constraint."""
    # Columns that are deliberately NOT indexed: they are only read when a
    # single row is opened (reviewer/decision references and the device
    # created by an approved request), never searched in bulk.
    not_indexed_on_purpose = {
        ("device_enrollment_requests", "reviewed_by"),
        ("device_enrollment_requests", "device_id"),
        ("security_events", "reviewed_by"),
        ("sharing_warnings", "decided_by"),
    }
    for table in metadata.sorted_tables:
        leading = {cols[0] for cols, _, _ in indexes_of(table).values()}
        leading |= {cols[0] for cols in unique_constraints_of(table).values()}
        for fk in table.foreign_keys:
            column = fk.parent.name
            if (table.name, column) in not_indexed_on_purpose:
                continue
            assert column in leading, (
                f"{table.name}.{column} is a foreign key with no index or "
                "unique constraint starting at that column"
            )


# ---------------------------------------------------- unique constraints
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_unique_constraints_match_the_design(table_name):
    actual = unique_constraints_of(table_of(table_name))
    expected = SCHEMA[table_name]["uniques"]
    assert actual == expected, (
        f"{table_name}: unique constraints differ. Expected {expected}, found {actual}"
    )


# ------------------------------------------------------------- indexes
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_indexes_match_the_design(table_name):
    actual = indexes_of(table_of(table_name))
    expected = SCHEMA[table_name]["indexes"]
    assert actual == expected, (
        f"{table_name}: indexes differ.\n"
        f"Missing: {sorted(set(expected) - set(actual))}\n"
        f"Unexpected: {sorted(set(actual) - set(expected))}\n"
        f"Different: "
        f"{sorted(n for n in set(actual) & set(expected) if actual[n] != expected[n])}"
    )


# ---------------------------------------------------- check constraints
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_check_constraints_match_the_design(table_name):
    actual = check_constraints_of(table_of(table_name))
    expected_names = {f"ck_{table_name}_{n}" for n in SCHEMA[table_name]["checks"]}
    
