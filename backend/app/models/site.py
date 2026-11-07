"""Table: sites.

A site is one Wi-Fi installation / customer location managed by the
system. Almost every other table references a site, so the product can
manage several locations later without a schema redesign.
"""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SITE_STATUSES = ("ACTIVE", "INACTIVE")


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status_valid"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(btrim(timezone)) > 0", name="timezone_not_blank"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
    # IANA time zone name. Records are stored in UTC; this is only used
    # for display and for day boundaries in reports.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Africa/Dar_es_Salaam"
  )
