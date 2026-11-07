"""Table: sessions.

Actual Internet access sessions, created from an entitlement.

The start and expiry times are STORED in UTC, never recalculated from a
running timer, so a backend restart or power failure can never reset the
remaining time. After a restart the backend reads this table and
continues from the stored expiry.

All devices of one customer entitlement share one live session (and
therefore one expiry). Which devices belong to it is recorded in
session_devices.

Rules the database cannot check (it cannot compare two tables) and the
backend must enforce: a session must not expire later than its
entitlement, and must only be created for an ACTIVE entitlement.

Sessions are never deleted (all foreign keys use RESTRICT).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SESSION_STATUSES = ("PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED")


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'EXPIRED', 'REVOKED')",
            name="status_valid",
        ),
        # Only a PENDING session may still lack its start and expiry.
        CheckConstraint(
            "status = 'PENDING' OR (started_at IS NOT NULL AND expires_at IS NOT NULL)",
            name="times_set_when_started",
        ),
        CheckConstraint(
            "started_at IS NULL OR expires_at IS NULL OR expires_at > started_at",
            name="expiry_after_start",
        ),
        # revoked_at is set if and only if the status is REVOKED.
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL)",
            name="revoked_at_matches_status",
        ),
        CheckConstraint(
            "gateway_reference IS NULL OR length(btrim(gateway_reference)) > 0",
            name="gateway_reference_not_blank",
        ),
        # At most ONE live session per entitlement, so devices share a
        # single session and expiry. Ended sessions are not counted.
        Index(
            "uq_sessions_entitlement_id_live",
            "entitlement_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'ACTIVE', 'SUSPENDED')"),
        ),
        Index("ix_sessions_site_id_status", "site_id", "status"),
        Index("ix_sessions_customer_id", "customer_id"),
        # Lets the expiry check find ACTIVE sessions that are due.
        Index(
            "ix_sessions_active_expires_at",
            "expires_at",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entitlements.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Identifier of the gateway/router that enforces this session, when
    # known. No specific router is assumed.
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="PENDING"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
  )
