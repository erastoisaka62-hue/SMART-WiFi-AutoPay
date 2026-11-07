"""Table: customers.

Wi-Fi customers of one site. A phone number is optional because not
every customer will provide one, so it is never the only identity:
every customer has a system-generated customer_reference instead.

Customers are never deleted when inactive: payments, entitlements and
audit history must stay linked to them. The foreign key to sites uses
RESTRICT for the same reason.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

CUSTOMER_STATUSES = ("ACTIVE", "SUSPENDED", "INACTIVE")


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')", name="status_valid"
        ),
        CheckConstraint(
            "length(btrim(customer_reference)) > 0", name="reference_not_blank"
        ),
        # International format only, e.g. +255712345678. The application
        # must normalize numbers before inserting.
        CheckConstraint(
            "phone_number IS NULL OR phone_number ~ '^\\+[1-9][0-9]{7,14}$'",
            name="phone_format_valid",
        ),
        # One reference per site.
        # (uq_customers_site_id_customer_reference via naming convention)
        # A phone number identifies at most one customer per site, but
        # only when a phone number exists.
        Index(
            "uq_customers_site_id_phone_number",
            "site_id",
            "phone_number",
            unique=True,
            postgresql_where=text("phone_number IS NOT NULL"),
        ),
        Index("ix_customers_site_id_status", "site_id", "status"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
