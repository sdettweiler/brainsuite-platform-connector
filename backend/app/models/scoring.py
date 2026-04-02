import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class CreativeScoreResult(Base):
    """Scoring result record for a creative asset from the BrainSuite API.

    Valid scoring_status values:
        UNSCORED    – asset has never been scored
        PENDING     – submitted to BrainSuite, awaiting job creation confirmation
        PROCESSING  – BrainSuite job is in progress
        COMPLETE    – score received and stored
        FAILED      – scoring attempt failed; see error_reason
        UNSUPPORTED – asset type not supported by any scoring endpoint (e.g. TikTok images)

    Valid endpoint_type values (see ScoringEndpointType enum):
        VIDEO        – ACE_VIDEO_SMV_API (video creatives)
        STATIC_IMAGE – ACE_STATIC_SOCIAL_STATIC_API (META image creatives)
        UNSUPPORTED  – no scoring endpoint available; asset excluded from scoring batch

    Diagnostic timestamps:
        pending_at   – set when status transitions to PENDING (batch claim time)
        submitted_at – set when brainsuite_job_id is written (job successfully submitted)
        scored_at    – set when status transitions to COMPLETE
    """
    __tablename__ = "creative_score_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creative_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creative_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    scoring_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNSCORED")
    endpoint_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    brainsuite_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    score_dimensions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pending_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creative_asset = relationship("CreativeAsset", back_populates="score_result")

    __table_args__ = (
        UniqueConstraint("creative_asset_id", name="uq_score_per_asset"),
    )
