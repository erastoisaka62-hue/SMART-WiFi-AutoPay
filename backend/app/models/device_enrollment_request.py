"""Table: device_enrollment_requests.

Requests to add an additional device to a customer's access.

The requested device details (MAC address, hostname, user agent) are
what the gateway reported, not proof of identity. The device row itself
is created only when the request is approved; device_id then points to
it.

Whether the customer still has device capacity is decided by the
backend (entitlement device limit), not by this table. Every decision
records who decided, when and why, so it can be audited. Requests are
never deleted.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ENROLLMENT_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED")


class DeviceEnrollmentRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "device_enrollment_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="status_valid",
        ),
        # Lowercase, colon-separated, same format as devices.mac_address.
        CheckConstraint(
            "requested_mac_address ~ '^([0-9a-f]{2}:){5}[0-9a-f]{2}$'",
            name="mac_format_valid",
        ),
        # An approved or rejected request must say who reviewed it and
        # when. A pending request has not been reviewed yet.
        CheckConstraint(
            "(status = 'PENDING' AND reviewed_at IS NULL AND reviewed_by IS NULL) "
            "OR status = 'CANCELLED' "
            "OR (status IN ('APPROVED', 'REJECTED') "
            "AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)",
            name="review_fields_consistent",
        ),
        # A device is linked only when the request was approved.
        CheckConstraint(
            "device_id IS NULL OR status = 'APPROVED'",
            name="device_only_when_approved",
        ),
        # The same customer cannot have two pending requests for the
        # same device at once.
        Index(
            "uq_device_enrollment_requests_pending_customer_mac",
            "customer_id",
            "requested_mac_address",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("ix_device_enrollment_requests_customer_id", "customer_id"),
        Index(
            "ix_device_enrollment_requests_site_id_status", "site_id", "status"
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

    # Requested device information (reported by the gateway).
    requested_mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    requested_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_user_agent: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="PENDING"
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Administrator decision.
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when the request is approved and the device record exists.
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=True,
  )
