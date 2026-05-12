import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class JobListItem(BaseModel):
    id: uuid.UUID
    job_type: str
    org_id: uuid.UUID
    status: str
    progress_current: int
    progress_total: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    metadata_: Optional[dict] = None
    org_name: Optional[str] = None

    class Config:
        from_attributes = True


class JobDetail(JobListItem):
    output: Optional[dict] = None
    error: Optional[dict] = None
    connection_name: Optional[str] = None
    platform_ad_account_id: Optional[str] = None
    asset_name: Optional[str] = None
    asset_url: Optional[str] = None
    asset_format: Optional[str] = None
    thumbnail_url: Optional[str] = None

    class Config:
        from_attributes = True
