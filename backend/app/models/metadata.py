import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class MetadataField(Base):
    """Custom metadata fields configurable per organization."""
    __tablename__ = "metadata_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), default="SELECT")  # SELECT, TEXT, NUMBER
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str] = mapped_column(String(500), nullable=True)  # NULL means "Not specified"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="metadata_fields")
    allowed_values: Mapped[list["MetadataFieldValue"]] = relationship(
        "MetadataFieldValue", back_populates="field", cascade="all, delete-orphan"
    )
    asset_values: Mapped[list["AssetMetadataValue"]] = relationship(
        "AssetMetadataValue", back_populates="field"
    )


class MetadataFieldValue(Base):
    """Pre-configured allowed values for metadata fields."""
    __tablename__ = "metadata_field_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("metadata_fields.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    field: Mapped["MetadataField"] = relationship("MetadataField", back_populates="allowed_values")
