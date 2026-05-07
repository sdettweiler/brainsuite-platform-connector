import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, UniqueConstraint, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class SystemConfig(Base):
    """Singleton table for platform-wide configuration (system-global, not per-org).

    Unique constraint on singleton_guard ensures exactly one row.
    Uses Text type for cookie columns since YouTube cookies are multi-KB strings.
    Encryption uses the same Fernet key as Phase 12 (TOKEN_ENCRYPTION_KEY).

    Security note (T-14-02): UNIQUE constraint on singleton_guard enforced at DB level
    prevents any INSERT of a second row.
    """

    __tablename__ = "system_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_guard: Mapped[str] = mapped_column(String(1), unique=True, default='X', nullable=False)
    youtube_cookies_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_cookies_backup_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    youtube_cookies_runtime_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    youtube_cookies_download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    youtube_cookies_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("singleton_guard", name="uq_system_config_singleton"),
    )
