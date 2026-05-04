import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, UniqueConstraint, Index, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class OrgBrainsuiteConfig(Base):
    """Per-org BrainSuite credentials and app name configuration.

    Stores Client ID and encrypted Client Secret for BrainSuite API access.
    for BrainSuite API access. App names are stored per-app on the brainsuite_apps table.

    Security note (T-11-01): client_secret_encrypted stores a Fernet-encrypted
    value using String(1000) — never Text — to prevent accidental plain-text
    leakage. The model never exposes a client_secret plain column.

    scoring_quota: maximum number of assets that can be scored for this org (NULL = unlimited).
    """

    __tablename__ = "org_brainsuite_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client_secret_encrypted: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    scoring_quota: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_org_brainsuite_config_org"),
    )


class OrgBrainsuiteFieldMapping(Base):
    """Per-app BrainSuite API field mapping configuration.

    Maps BrainSuite API field names to platform metadata fields for a specific
    BrainsuiteApp instance. Replaces the old per-org+app_type mapping with a
    direct FK to brainsuite_apps so each app has its own independent field mappings.

    Mandatory fields cause scoring to skip assets missing the required metadata value.
    Custom fields are user-defined beyond the standard BrainSuite API field set.
    """

    __tablename__ = "org_brainsuite_field_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainsuite_app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brainsuite_apps.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    app_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "VIDEO" or "STATIC" — denormalized for pipeline query efficiency (avoids JOIN)
    api_field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_field_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metadata_fields.id", ondelete="SET NULL"), nullable=True
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    brainsuite_app: Mapped["BrainsuiteApp"] = relationship("BrainsuiteApp")

    __table_args__ = (
        UniqueConstraint("brainsuite_app_id", "api_field_name", name="uq_brainsuite_field_mappings_app_field"),
    )
