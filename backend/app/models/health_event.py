"""Table: health_events.

Records important system health events, for example "database became
unavailable" or "gateway recovered". It describes the local system, not
the ISP Internet connection.

Rules:
- append-only by design: there is no updated_at and rows are not edited;
- the description must be safe text: no passwords, tokens, API keys,
  connection strings or file paths. A CHECK rejects the most obvious
  "secret = value" patterns as a safety net, but the backend must still
  never put secrets or internal details here;
- no foreign keys: health events describe the system itself and must be
  writable even when other data is unavailable.

Unlike audit_logs, health events can grow quickly. A retention policy
(for example archiving after a number of months) is a later decision
and is not implemented in this task.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

HEALTH_STATUSES = ("OK", "DEGRADED", "DOWN")


class HealthEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "health_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OK', 'DEGRADED', 'DOWN')",
            name="status_valid",
        ),
        # Lowercase, e.g. database, backend, router_gateway, storage.
        # No fixed list: components are defined by later tasks.
        CheckConstraint(
            "component ~ '^[a-z][a-z0-9_]{1,47}$'",
            name="component_format_valid",
        ),
        # Lowercase, e.g. connection_lost or recovered.
        CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_.]{1,63}$'",
            name="event_type_format_valid",
        ),
        CheckConstraint(
            "length(btrim(description)) > 0 AND length(description) <= 1000",
            name="description_not_blank_and_short",
        ),
        # Safety net only: reject text that looks like "password=...".
        CheckConstraint(
            "description !~* "
            "'(password|passwd|secret|token|api[_-]?key|authorization)\\s*[=:]'",
            name="description_no_secret_pairs",
        ),
        Index("ix_health_events_component_occurred_at", "component", "occurred_at"),
        Index("ix_health_events_status_occurred_at", "status", "occurred_at"),
    )

    component: Mapped[str] = mapped_column(String(48), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # Safe text only: no secrets, connection strings or file paths.
    description: Mapped[str] = mapped_column(Text, nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
  )
