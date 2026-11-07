"""Table: packages.

Internet packages created by the administrator (fixed price, duration
and device limit). Package prices and durations are NOT hard-coded here:
every value is entered by the administrator.

Changing a package later must never alter purchases already made: the
entitlements table stores its own copy (price, duration, device limit)
of what the customer bought. Packages are deactivated, never deleted.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, TimestampMixin, UUIDPrimaryKeyMixin

PACKAGE_STATUSES = ("ACTIVE", "INACTIVE")


class Package(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "packages"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status_valid"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("device_limit >= 1", name="device_limit_at_least_one"),
        # Package names are unique within a site.
        UniqueConstraint("site_id", "name"),
        Index("ix_packages_site_id_status", "site_id", "status"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Exact decimal amount in the site's currency (TZS at first).
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Duration is stored in one normalized unit (minutes) so that
    # comparisons and expiry calculations are never ambiguous.
    # Example: 1 hour = 60, 1 day = 1440.
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Number of devices one purchase of this package may use.
    device_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
