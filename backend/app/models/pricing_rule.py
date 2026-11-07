
"""Table: pricing_rules.

Administrator-controlled rules for customer-entered custom amounts.

The customer proposes an amount only. The backend calculates the
duration using the active pricing rule.

PROPORTIONAL calculation:
    raw_duration = amount / price_per_hour * 60

The result is rounded according to rounding_policy and
rounding_step_minutes, then checked against the minimum and
maximum allowed duration.

Every purchase must store a snapshot of the applied pricing rule.
Editing a rule later must never change an existing purchase.

Rules are deactivated, not deleted.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MONEY, Base, TimestampMixin, UUIDPrimaryKeyMixin


PRICING_RULE_STATUSES = ("ACTIVE", "INACTIVE")
DURATION_POLICIES = ("PROPORTIONAL",)
ROUNDING_POLICIES = ("DOWN", "NEAREST", "UP")


class PricingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pricing_rules"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        CheckConstraint(
            "duration_policy IN ('PROPORTIONAL')",
            name="duration_policy_valid",
        ),
        CheckConstraint(
            "rounding_policy IN ('DOWN', 'NEAREST', 'UP')",
            name="rounding_policy_valid",
        ),
        CheckConstraint(
            "min_amount > 0",
            name="min_amount_positive",
        ),
        CheckConstraint(
            "max_amount >= min_amount",
            name="max_amount_not_below_min",
        ),
        CheckConstraint(
            "price_per_hour > 0",
            name="price_per_hour_positive",
        ),
        CheckConstraint(
            "rounding_step_minutes >= 1",
            name="rounding_step_positive",
        ),
        CheckConstraint(
            "min_duration_minutes > 0",
            name="min_duration_positive",
        ),
        CheckConstraint(
            "max_duration_minutes >= min_duration_minutes",
            name="max_duration_not_below_min",
        ),
        CheckConstraint(
            "device_limit >= 1",
            name="device_limit_at_least_one",
        ),
        # One active pricing rule per site.
        Index(
            "uq_pricing_rules_site_id_active",
            "site_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_pricing_rules_site_id_status",
            "site_id",
            "status",
        ),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="INACTIVE",
    )

    min_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
    )

    max_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
    )

    duration_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="PROPORTIONAL",
    )

    price_per_hour: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
    )

    rounding_policy: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="DOWN",
    )

    rounding_step_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )

    min_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    max_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    device_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
)
    
