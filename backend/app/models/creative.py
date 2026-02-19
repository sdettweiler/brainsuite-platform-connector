import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class Project(Base):
    """Creative asset grouping."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    asset_mappings: Mapped[list["AssetProjectMapping"]] = relationship("AssetProjectMapping", back_populates="project")


class CreativeAsset(Base):
    """Canonical creative asset record, deduped across platforms and ad accounts."""
    __tablename__ = "creative_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)

    # Platform identifiers
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # META, TIKTOK, YOUTUBE
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_set_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # Creative details
    creative_id: Mapped[str] = mapped_column(String(255), nullable=True)
    asset_format: Mapped[str] = mapped_column(String(50), nullable=True)  # IMAGE, VIDEO, CAROUSEL
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    asset_url: Mapped[str] = mapped_column(Text, nullable=True)
    video_duration: Mapped[float] = mapped_column(Float, nullable=True)
    placement: Mapped[str] = mapped_column(String(255), nullable=True)

    # Platform-specific extra metadata
    platform_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Brainsuite dummy score fields
    ace_score: Mapped[float] = mapped_column(Float, nullable=True)
    ace_score_confidence: Mapped[str] = mapped_column(String(50), nullable=True)
    brainsuite_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    project_mappings: Mapped[list["AssetProjectMapping"]] = relationship("AssetProjectMapping", back_populates="asset")
    metadata_values: Mapped[list["AssetMetadataValue"]] = relationship("AssetMetadataValue", back_populates="asset", cascade="all, delete-orphan")
    harmonized_performance: Mapped[list["HarmonizedPerformance"]] = relationship("HarmonizedPerformance", back_populates="asset")

    __table_args__ = (
        UniqueConstraint("organization_id", "platform", "ad_id", "ad_account_id", name="uq_creative_asset"),
    )


class AssetProjectMapping(Base):
    __tablename__ = "asset_project_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creative_assets.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    asset: Mapped["CreativeAsset"] = relationship("CreativeAsset", back_populates="project_mappings")
    project: Mapped["Project"] = relationship("Project", back_populates="asset_mappings")

    __table_args__ = (
        UniqueConstraint("asset_id", "project_id", name="uq_asset_project"),
    )


class AssetMetadataValue(Base):
    """Stores the actual metadata value assigned to a creative asset."""
    __tablename__ = "asset_metadata_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creative_assets.id"), nullable=False)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("metadata_fields.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    asset: Mapped["CreativeAsset"] = relationship("CreativeAsset", back_populates="metadata_values")
    field: Mapped["MetadataField"] = relationship("MetadataField", back_populates="asset_values")

    __table_args__ = (
        UniqueConstraint("asset_id", "field_id", name="uq_asset_metadata_field"),
    )
