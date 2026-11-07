"""Table: pricing_rules.

Administrator-controlled rules for custom customer-entered amounts.

The customer only proposes an AMOUNT. The backend alone calculates the
resulting duration from the active rule, so a customer can never choose
their own duration by changing values in the browser.

Calculation policy (PROPORTIONAL):
    duration = amount / price_per_hour * 60 minutes
    then rounded using rounding_policy to a multiple of
    rounding_step_minutes, and accepted only if it is between
    min_duration_minutes and max_duration_minutes.

Every purchase must keep a snapshot of the rule that was applied; the
payments/entitlements tables will store that copy, so editing a rule
later never changes past purchases. Rules are deactivated, not deleted.
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
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status_valid"),
        CheckConstraint(
            "duration_policy IN ('PROPORTIONAL')", name="duration_policy_valid"
        ),
        CheckConstraint(
            "rounding_policy IN ('DOWN', 'NEAREST', 'UP')",
            name="rounding_policy_valid",
        ),
        CheckConstraint("min_amount > 0", name="min_amount_positive"),
        CheckConstraint("max_amount >= min_amount", name="max_amount_not_below_min"),
        CheckConstraint("price_per_hour > 0", name="price_per_hour_positive"),
        CheckConstraint("rounding_step_minutes >= 1", name="rounding_step_positive"),
        CheckConstraint("min_duration_minutes > 0", name="min_duration_positive"),
        CheckConstraint(
            "max_duration_minutes >= min_duration_minutes",
            name="max_duration_not_below_min",
        ),
        CheckConstraint("device_limit >= 1", name="device_limit_at_least_one"),
        # At most ONE active rule per site, so the backend never has to
        # guess which rule applies. Any number of inactive rules is fine.
        Index(
            "uq_pricing_rules_site_id_active",
            "site_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_pricing_rules_site_id_status", "site_id", "status"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="INACTIVE"
    )

    # Allowed range of custome
