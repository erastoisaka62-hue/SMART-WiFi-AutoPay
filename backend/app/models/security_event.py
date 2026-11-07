"""Table: security_events.

Records security-relevant incidents, for example a possible case of
unauthorized sharing.

Weak or unverified signals must NEVER count as confirmed sharing:
- every new event starts as PENDING_REVIEW;
- only an administrator can move it to CONFIRMED or DISMISSED, and the
  database requires the reviewer and review time for both;
- the confidence level only describes how strong the signal was, it
  does not confirm anything by itself.

Only a CONFIRMED event may later be linked to a sharing warning
(table sharing_warnings), and no suspension may be based on an event
that has not been confirmed. The backend must enforce that link rule.

evidence_description must be a safe text: no passwords, tokens, API
keys or payment credentials. Events are never deleted.
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SECURITY_REVIEW_STATUSES = ("PENDING_REVIEW", "CONFIRMED", "DISMISSED")
SECURITY_CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")


class SecurityEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('PENDING_REVIEW', 'CONFIRMED', 'DISMISSED')",
            name="review_status_valid",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence IN ('LOW', 'MEDIUM', 'HIGH')",
            name="confidence_valid",
        ),
        # Lowercase snake_case, e.g. possible_sharing. No fixed list is
        # imposed here: detection types are defined in a later task.
        CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="event_type_format_valid",
        ),
        CheckConstraint(
            "length(btrim(evidence_description)) > 0",
            name="evidence_not_blank",
        ),
        # A pending event has not been reviewed. CONFIRMED and DISMISSED
        # always record who reviewed it and when.
        CheckConstraint(
            "(review_status = 'PENDING_REVIEW' "
            "AND reviewed_at IS NULL AND reviewed_by IS NULL) "
            "OR (review_status IN ('CONFIRMED', 'DISMISSED') "
            "AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)",
            name="review_fields_consistent",
        ),
        Index(
            "ix_security_events_site_id_review_status_occurred_at",
            "site_id",
            "review_status",
            "occurred_at",
        ),
        Index("ix_security_events_customer_id", "customer_id"),
        Index("ix_security_events_device_id", "device_id"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Optional: some events concern a customer, a device, both or neither.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_description: Mapped[str] = mapped_column(Text, nullable=False)
    # Strength of the signal only; it never confirms an event.
    confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # When the incident happened (UTC).
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="PENDING_REVIEW"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="RESTRICT"),
        nullable=True,
  )
