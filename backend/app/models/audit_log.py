"""Table: audit_logs.

Records important administrator and system actions.

Rules:
- append-only by design: there is no updated_at and rows are never
  edited or deleted (the foreign key uses RESTRICT; a database trigger
  against UPDATE/DELETE is added with the migrations);
- safe_metadata must never contain passwords, tokens, API keys or
  payment credentials. A CHECK rejects the most obvious secret keys as a
  safety net, but the backend must still never put secrets in it;
- the actor is polymorphic (administrator, system or customer), so
  actor_id has no foreign key: audit history must outlive any account.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

AUDIT_ACTOR_TYPES = ("ADMIN", "SYSTEM", "CUSTOMER")


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('ADMIN', 'SYSTEM', 'CUSTOMER')",
            name="actor_type_valid",
        ),
        # SYSTEM actions have no actor id; ADMIN and CUSTOMER always do.
        CheckConstraint(
            "(actor_type = 'SYSTEM') = (actor_id IS NULL)",
            name="actor_id_matches_actor_type",
        ),
        # Lowercase, e.g. payment.confirmed or admin.login_failed.
        CheckConstraint(
            "action ~ '^[a-z][a-z0-9_.]{1,95}$'",
            name="action_format_valid",
        ),
        CheckConstraint(
            "affected_record_type IS NULL "
            "OR affected_record_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="record_type_format_valid",
        ),
        # Record type and record id are given together or not at all.
        CheckConstraint(
            "(affected_record_type IS NULL) = (affected_record_id IS NULL)",
            name="record_type_and_id_together",
        ),
        CheckConstraint(
            "jsonb_typeof(safe_metadata) = 'object'",
            name="safe_metadata_is_object",
        ),
        # Safety net only: reject metadata that has an obviously secret key.
        CheckConstraint(
            "NOT (safe_metadata::text ~* "
            "'\"(password|passwd|secret|token|api[_-]?key|authorization"
            "|pin|cvv|card_number)\"\\s*:')",
            name="safe_metadata_no_secret_keys",
        ),
        Index("ix_audit_logs_site_id_occurred_at", "site_id", "occurred_at"),
        Index("ix_audit_logs_actor_type_actor_id", "actor_type", "actor_id"),
        Index(
            "ix_audit_logs_affected_record",
            "affected_record_type",
            "affected_record_id",
        ),
        Index("ix_audit_logs_action_occurred_at", "action", "occurred_at"),
    )

    # Empty for actions that belong to no single site.
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=True,
    )

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Id of the administrator or customer. No foreign key on purpose.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    action: Mapped[str] = mapped_column(String(96), nullable=False)

    # Which record was affected (table name and its id), when applicable.
    affected_record_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    affected_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Safe, non-secret details (for example old and new status, reason).
    safe_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
