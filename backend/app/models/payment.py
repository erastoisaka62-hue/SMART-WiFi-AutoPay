"""Table: payments.

Payment transactions. This is a security-sensitive table:

- Only the backend, after verifying with the payment provider, may set
  a payment to CONFIRMED. A browser message, screenshot or SMS is never
  proof of payment.
- Duplicate processing is blocked by unique constraints: one internal
  reference, and one provider transaction reference per provider.
- Money is exact NUMERIC, never float.
- Payments are never deleted (all foreign keys use RESTRICT).

amount is the EXPECTED amount; verified_amount is what the provider
confirmed. A payment can be CONFIRMED only when both are equal.

pricing_snapshot keeps an exact copy of the package or pricing rule
applied at purchase time, so later edits never change past purchases.

No provider credentials or payer secrets are stored here.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, TimestampMixin, UUIDPrimaryKeyMixin

PAYMENT_STATUSES = (
    "CREATED",
    "PENDING",
    "CONFIRMED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
    "DUPLICATE",
    "REVERSED",
)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'CONFIRMED', 'FAILED', "
            "'CANCELLED', 'EXPIRED', 'DUPLICATE', 'REVERSED')",
            name="status_valid",
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "verified_amount IS NULL OR verified_amount > 0",
            name="verified_amount_positive",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format_valid"),
        CheckConstraint(
            "length(btrim(provider)) > 0 AND provider = lower(provider)",
            name="provider_lowercase_not_blank",
        ),
        CheckConstraint(
            "length(btrim(internal_reference)) > 0",
            name="internal_reference_not_blank",
        ),
        CheckConstraint(
            "provider_reference IS NULL OR length(btrim(provider_reference)) > 0",
            name="provider_reference_not_blank",
        ),
        # A confirmed (or later reversed) payment must be fully verified:
        # provider reference, verification time, and a verified amount
        # equal to the expected amount.
        CheckConstraint(
            "status NOT IN ('CONFIRMED', 'REVERSED') OR ("
            "provider_reference IS NOT NULL "
            "AND verified_at IS NOT NULL "
            "AND verified_amount IS NOT NULL "
            "AND verified_amount = amount)",
            name="confirmed_requires_verification",
        ),
        # A payment that has not been confirmed has no verification time.
        CheckConstraint(
            "status IN ('CONFIRMED', 'REVERSED') OR verified_at IS NULL",
            name="verification_only_when_confirmed",
        ),
        CheckConstraint(
            "jsonb_typeof(pricing_snapshot) = 'object'",
            name="pricing_snapshot_is_object",
        ),
        # Idempotency 1: every internal reference is unique.
        UniqueConstraint("internal_reference"),
        # Idempotency 2: one provider transaction reference per provider.
        # Rows marked DUPLICATE are excluded so a repeated notification
        # can still be recorded for audit without breaking the rule.
        Index(
            "uq_payments_provider_provider_reference_active",
            "provider",
            "provider_reference",
            unique=True,
            postgresql_where=text(
                "provider_reference IS NOT NULL AND status <> 'DUPLICATE'"
            ),
        ),
        Index("ix_payments_customer_id", "customer_id"),
        Index("ix_payments_site_id_status_created_at", "site_id", "status", "created_at"),
        Index("ix_payments_package_id", "package_id"),
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
    # Set for fixed packages, empty for custom-amount purchases.
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("packages.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Expected amount, and the amount the provider actually confirmed.
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    verified_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="TZS"
    )

    # Provider adapter name in lowercase. No provider is assumed here.
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    internal_reference: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="CREATED"
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Exact copy of the package / pricing rule applied at purchase time.
    pricing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
