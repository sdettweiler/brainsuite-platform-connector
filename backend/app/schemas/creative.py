from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import uuid


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    asset_count: Optional[int] = 0

    class Config:
        from_attributes = True


class MetadataFieldCreate(BaseModel):
    name: str
    label: str
    field_type: str = "SELECT"
    is_required: bool = False
    default_value: Optional[str] = None
    allowed_values: List[Dict[str, str]] = []  # [{value, label}]


class MetadataFieldResponse(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    field_type: str
    is_required: bool
    default_value: Optional[str]
    allowed_values: List[Dict[str, Any]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class AssetMetadataUpdate(BaseModel):
    metadata: Dict[str, Optional[str]]  # field_id -> value


class CreativeAssetSummary(BaseModel):
    id: uuid.UUID
    platform: str
    ad_id: str
    ad_name: Optional[str]
    campaign_name: Optional[str]
    campaign_objective: Optional[str]
    asset_format: Optional[str]
    thumbnail_url: Optional[str]
    ace_score: Optional[float]
    ace_score_confidence: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class PerformanceSummary(BaseModel):
    spend: Optional[Decimal]
    impressions: Optional[int]
    clicks: Optional[int]
    ctr: Optional[float]
    cpm: Optional[Decimal]
    conversions: Optional[int]
    cvr: Optional[float]
    roas: Optional[float]
    video_views: Optional[int]
    vtr: Optional[float]


class CreativeAssetResponse(CreativeAssetSummary):
    ad_account_id: Optional[str]
    ad_set_id: Optional[str]
    ad_set_name: Optional[str]
    campaign_id: Optional[str]
    creative_id: Optional[str]
    asset_url: Optional[str]
    video_duration: Optional[float]
    placement: Optional[str]
    platform_metadata: Dict[str, Any] = {}
    metadata_values: Dict[str, Optional[str]] = {}
    projects: List[str] = []
    first_seen_at: Optional[datetime]
    last_seen_at: Optional[datetime]
    performance: Optional[PerformanceSummary] = None
    performer_tag: Optional[str] = None  # Top Performer, Average, Below Average


class DashboardFilterParams(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    platforms: Optional[List[str]] = None
    formats: Optional[List[str]] = None
    objectives: Optional[List[str]] = None
    project_ids: Optional[List[uuid.UUID]] = None
    metadata_filters: Optional[Dict[str, str]] = None
    spend_min: Optional[float] = None
    spend_max: Optional[float] = None
    cpm_min: Optional[float] = None
    cpm_max: Optional[float] = None
    ctr_min: Optional[float] = None
    ctr_max: Optional[float] = None
    vtr_min: Optional[float] = None
    vtr_max: Optional[float] = None
    cvr_min: Optional[float] = None
    cvr_max: Optional[float] = None
    roas_min: Optional[float] = None
    roas_max: Optional[float] = None
    ace_score_min: Optional[float] = None
    ace_score_max: Optional[float] = None
    sort_by: str = "spend"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 50


class DashboardStats(BaseModel):
    total_spend: Decimal
    total_impressions: int
    avg_roas: Optional[float]
    total_active_assets: int
    new_assets_in_period: int
    prev_total_spend: Optional[Decimal]
    prev_total_impressions: Optional[int]
    prev_avg_roas: Optional[float]
    prev_total_active_assets: Optional[int]


class AssetTimeseriesPoint(BaseModel):
    date: date
    value: float


class AssetDetailResponse(CreativeAssetResponse):
    campaigns_count: int
    campaigns: List[Dict[str, Any]] = []
    timeseries: Optional[Dict[str, List[AssetTimeseriesPoint]]] = None


class ComparisonRequest(BaseModel):
    asset_ids: List[uuid.UUID]  # 2-4 assets
    date_from: date
    date_to: date


class ExportRequest(BaseModel):
    use_dashboard_settings: bool = True
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    filters: Optional[DashboardFilterParams] = None
    fields: List[str]  # ordered list of fields to include
    format: str = "excel"  # pdf, excel, csv
