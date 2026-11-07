"""Table: session_devices.

Links devices to a session (and so to the entitlement behind it).

Rules enforced here:
- a device is linked at most once as ACTIVE to the same session;
- a device can be ACTIVE in only ONE session at a time, so the same
  physical device cannot use two sessions at once;
- connection and disconnection times are consistent with the status.

Rule the database CANNOT enforce and the backend must (it needs to count
rows and read the entitlement's device_limit from other tables): the
number of ACTIVE devices in a session must never exceed the device limit.
The backend must check this inside one transaction that locks the
session row, and the tests will cover it.

Rows are never deleted: they are the history of which device used
which session. A device leaving is recorded as DISCONNECTED or REVOKED.
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SESSION_DEVICE_STATUSES = ("ACTIVE", "DISCONNECTED", "REVOKED")


class SessionDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'DISCONNECTED', 'REVOKED')",
            name="status_valid",
        ),
        # ACTIVE means still connected: no disconnection time yet.
        # DISCONNECTED or REVOKED must record when it ended.
        CheckConstraint(
            "(status = 'ACTIVE') = (disconnected_at IS NULL)",
            name="disconnected_at_matches_status",
        ),
        CheckConstraint(
            "disconnected_at IS NULL OR disconnected_at >= connected_at",
            name="disconnect_not_before_connect",
        ),
        # One ACTIVE link per device per session.
        Index(
            "uq_session_devices_session_id_device_id_active",
            "session_id",
            "device_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        # A device is ACTIVE in at most one session at a time.
        Index(
            "uq_session_devices_device_id_active",
            "device_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_session_devices_session_id_status", "session_id", "status"),
        Index("ix_session_devices_device_id", "device_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
