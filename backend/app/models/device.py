"""Table: devices.

Devices registered to customers.

A MAC address is NOT proof of identity: phones can randomize it and it
can be spoofed. It is stored only as the identifier reported by the
gateway, never as a permanent or spoof-proof identity, and it must not
be typed in by the customer as proof. Extra observations (hostname,
user agent) are optional hints for administrators, not trusted facts.

Devices are never deleted: sessions, security events and audit history
must stay linked to them. A device is REVOKED instead.
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

DEVICE_STATUSES = ("PENDING", "ACTIVE", "REVOKED", "BLOCKED")


class Device(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'REVOKED', 'BLOCKED')",
            name="status_valid",
        ),
        # Lowercase, colon-separated, e.g. 3c:5a:b4:01:02:03.
        # The application must normalize before inserting.
        CheckConstraint(
            "mac_address ~ '^([0-9a-f]{2}:){5}[0-9a-f]{2}$'",
            name="mac_format_valid",
        ),
        # One non-revoked record per MAC address per site, so the same
        # physical device cannot be attached to two customers at once.
        # A revoked record frees the address for a later registration.
        Index(
            "uq_devices_site_id_mac_address_not_revoked",
            "site_id",
            "mac_address",
            unique=True,
            postgresql_where=text("status <> 'REVOKED'"),
        ),
        Index("ix_devices_customer_id", "customer_id"),
        Index("ix_devices_site_id_status", "site_id", "status"),
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

    # Identifier reported by the gateway (not a proof of identity).
    mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    # Optional hints for administrators (untrusted, may be missing).
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="PENDING"
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
