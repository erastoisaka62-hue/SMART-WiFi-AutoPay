"""Table: entitlements.

An entitlement is the customer's purchased right to use the Internet.
It lives in the database, so it does not depend on any browser timer
and survives backend restarts and power failures.

Rules:
- Only an authoritative backend process may create or activate an
  entitlement, and only after the payment was verified as CONFIRMED.
  A database CHECK cannot look into another table, so the backend must
  enforce this (and the tests will cover it).
- One payment can grant at most one entitlement (unique payment_id).
  This stops a repeated payment notification from granting access twice.
- granted_amount, granted_duration_minutes and device_limit are a copy
  of what the customer bought. Editing a package or pricing rule later
  never changes an existing entitlement.
- Entitlements are never deleted (all foreign keys use RESTRICT).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, TimestampMixin, UUIDPrimaryKeyMixin

ENTITLEMENT_STATUSES = ("ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED")


class Entitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'EXPIRED', 'REVOKED')",
            name="status_valid",
        ),
        CheckConstraint("granted_amount > 0", name="granted_amount_positive"),
        CheckConstraint(
            "granted_duration_minutes > 0", name="granted_duration_positive"
        ),
        CheckConstraint("device_limit >= 1", name="device_limit_at_least_one"),
        CheckConstraint("expires_at > valid_from", name="expiry_after_start"),
        # One entitlement per payment (idempotency).
        UniqueConstraint("payment_id"),
        Index("ix_entitlements_customer_id_status", "customer_id", "status"),
        # Lets the expiry check find ACTIVE entitlements that are due.
        Index(
            "ix_entitlements_active_expires_at",
            "expires_at",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_entitlements_site_id_status", "site_id", "status"),
        Index("ix_entitlements_package_id", "package_id"),
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
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Set for fixed packages, empty for custom-amount purchases.
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("packages.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Copy of what was purchased (independent of later package edits).
    granted_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    granted_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    # All times are UTC. The expiry is stored, not recalculated, so a
    # restart can never reset the remaining time.
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
