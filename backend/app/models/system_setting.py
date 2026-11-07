"""Table: system_settings.

Controlled system configuration stored in the database, either for the
whole system (site_id empty) or for one site.

Do NOT store secrets here. Passwords, API keys, tokens and provider
credentials belong in the private .env file (or a secrets mechanism
approved later), never in this table. A CHECK rejects keys whose name
looks secret, as a safety net only: the backend must still never put
secrets here.

The value is stored as text; data_type says how to read it, and the
database checks that INTEGER, DECIMAL and BOOLEAN values are well
formed. Money-like settings must use DECIMAL, never float.

Settings are changed in place (updated_at records when). The audit log
must record every change made by an administrator.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SETTING_DATA_TYPES = ("STRING", "INTEGER", "DECIMAL", "BOOLEAN")


class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        CheckConstraint(
            "data_type IN ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN')",
            name="data_type_valid",
        ),
        # Lowercase, e.g. portal.default_language or session.grace_minutes.
        CheckConstraint(
            "setting_key ~ '^[a-z][a-z0-9_.]{1,95}$'",
            name="setting_key_format_valid",
        ),
        # Safety net: refuse keys that look like they hold a secret.
        CheckConstraint(
            "setting_key !~* "
            "'(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)'",
            name="setting_key_not_secret",
        ),
        # The stored text must match its declared type.
        CheckConstraint(
            "(data_type = 'STRING') "
            "OR (data_type = 'INTEGER' AND setting_value ~ '^-?[0-9]+$') "
            "OR (data_type = 'DECIMAL' AND setting_value ~ '^-?[0-9]+(\\.[0-9]+)?$') "
            "OR (data_type = 'BOOLEAN' AND setting_value IN ('true', 'false'))",
            name="value_matches_data_type",
        ),
        # A key is unique per site, and unique among global settings.
        # (Two partial indexes, because NULL site_id values never
        # collide in a normal unique constraint.)
        Index(
            "uq_system_settings_site_id_setting_key",
            "site_id",
            "setting_key",
            unique=True,
            postgresql_where=text("site_id IS NOT NULL"),
        ),
        Index(
            "uq_system_settings_setting_key_global",
            "setting_key",
            unique=True,
            postgresql_where=text("site_id IS NULL"),
        ),
    )

    # Empty for settings that apply to the whole system.
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=True,
    )

    setting_key: Mapped[str] = mapped_column(String(96), nullable=False)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="STRING"
    )
