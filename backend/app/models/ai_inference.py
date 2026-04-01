import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class AIInferenceTracking(Base):
    """Tracks AI metadata auto-fill inference status per creative asset.

    One row per asset. Status values: PENDING | COMPLETE | FAILED.
    COMPLETE guard prevents re-inference on already-processed assets (AI-06).
    FAILED status resets to PENDING on next sync to allow retry (D-12).
    """
    __tablename__ = "ai_inference_tracking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creative_assets.id"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    ai_inference_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_ai_inference_asset"),
        Index("ix_ai_inference_status", "ai_inference_status"),
    )
