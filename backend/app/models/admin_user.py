"""Table: admin_users.

Administrator accounts. Only a password HASH is stored, never the
password itself. The login workflow is not part of TASK 02.

Administrators are global (not tied to one site) in this first schema;
per-site administrator access can be added later with a link table
without changing this one.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ADMIN_STATUSES = ("ACTIVE", "DISABLED")


class AdminUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="status_valid"),
        CheckConstraint("length(btrim(username)) >= 3", name="username_min_length"),
        # Usernames are stored lowercase so "Admin" and "admin" cannot
        # both exist. The application must normalize before inserting.
        CheckConstraint("username = lower(username)", name="username_lowercase"),
        # Guard against storing a short plaintext by mistake. Real
        # argon2/bcrypt hashes are far longer than this.
        CheckConstraint("length(password_hash) >= 20", name="password_hash_not_trivial"),
    )

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ACTIVE"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
  )
