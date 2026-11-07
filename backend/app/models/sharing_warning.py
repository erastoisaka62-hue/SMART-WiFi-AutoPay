"""Table: sharing_warnings.

Records the two-warning policy for confirmed unauthorized sharing:

- warning 1: first confirmed violation (status ISSUED);
- warning 2: second confirmed violation, which puts the customer in
  SUSPENSION_PENDING_REVIEW;
- an administrator then either releases the suspension
  (SUSPENSION_RELEASED) or keeps it (SUSPENSION_MAINTAINED), and must
  record who decided, when and why.

Rules enforced here:
- every warning is tied to exactly one security event, and one event can
  produce only one warning;
- a customer can have warning number 1 and number 2 only once each;
- warning 1 can only be ISSUED, warning 2 can only be one of the three
  suspension statuses;
- a release or maintain decision requires the administrator, the review
  time and a non-blank reason.

Rules the database CANNOT enforce (they need to read other tables) and
the backend must enforce, inside one transaction:
- the linked security event must be CONFIRMED by an administrator and
  must belong to the same customer (weak or unverified signals never
  create a warning);
- creating warning 2 must also set the customer to SUSPENDED, and a
  release must restore it;
- every decision must also be written to audit_logs.

Warnings are never deleted: they are the customer's security history.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SHARING_WARNING_STATUSES = (
    "ISSUED",
    "SUSPENSION_PENDING_REVIEW",
    "SUSPENSION_RELEASED",
    "SUSPENSION_MAINTAINED",
)


class SharingWarning(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sharing_warnings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ISSUED', 'SUSPENSION_PENDING_REVIEW', "
            "'SUSPENSION_RELEASED', 'SUSPENSION_MAINTAINED')",
            name="status_valid",
        ),
        CheckConstraint("warning_number IN (1, 2)", name="warning_number_valid"),
        # Warning 1 is only ISSUED. Warning 2 is a suspension status.
        # No administrator decision exists until a suspension is decided.
        CheckConstraint(
            "(status = 'ISSUED' AND warning_number = 1 "
            "AND reviewed_at IS NULL AND decided_by IS NULL "
            "AND decision_reason IS NULL) "
            "OR (status = 'SUSPENSION_PENDING_REVIEW' AND warning_number = 2 "
            "AND reviewed_at IS NULL AND decided_by IS NULL "
            "AND decision_reason IS NULL) "
            "OR (status IN ('SUSPENSION_RELEASED', 'SUSPENSION_MAINTAINED') "
            "AND warning_number = 2 "
            "AND reviewed_at IS NOT NULL AND decided_by IS NOT NULL "
            "AND decision_reason IS NOT NULL "
            "AND length(btrim(decision_reason)) > 0)",
            name="policy_and_decision_consistent",
        ),
        # Each security event produces at most one warning.
        UniqueConstraint("security_event_id"),
        # Each customer has warning 1 and warning 2 at most once.
        UniqueConstraint("customer_id", "warning_number"),
        Index("ix_sharing_warnings_customer_id", "customer_id"),
        # Lets the administrator queue find suspensions awaiting a decision.
        Index(
            "ix_sharing_warnings_pending_review",
            "warned_at",
            postgresql_where=text("status = 'SUSPENSION_PENDING_REVIEW'"),
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # The confirmed event that justifies this warning (never empty).
    security_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_events.id", ondelete="RESTRICT"),
        nullable=False,
    )

    warning_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    # When the warning was issued (UTC).
    warned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Administrator decision on a suspension.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
