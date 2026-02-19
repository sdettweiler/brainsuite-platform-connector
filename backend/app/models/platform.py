import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class BrainsuiteApp(Base):
    """Brainsuite scoring apps that ad accounts are mapped to."""
    __tablename__ = "brainsuite_apps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    app_type: Mapped[str] = mapped_column(String(50), nullable=False)  # VIDEO, IMAGE
    is_default_for_video: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default_for_image: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="brainsuite_apps")
    platform_connections: Mapped[list["PlatformConnection"]] = relationship("PlatformConnection", back_populates="brainsuite_app")


class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    brainsuite_app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brainsuite_apps.id"), nullable=True)

    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # META, TIKTOK, YOUTUBE
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_account_name: Mapped[str] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g. "America/New_York"

    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    connection_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_metadata_values: Mapped[dict] = mapped_column(JSONB, default=dict)

    sync_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, EXPIRED, ERROR, PENDING
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_sync_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    historical_sync_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    historical_sync_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="platform_connections")
    created_by_user: Mapped["User"] = relationship("User", back_populates="platform_connections")
    brainsuite_app: Mapped["BrainsuiteApp"] = relationship("BrainsuiteApp", back_populates="platform_connections")

    __table_args__ = (
        # Allow multiple connections per platform if different ad accounts
        # Unique on org + platform + ad_account_id
    )
