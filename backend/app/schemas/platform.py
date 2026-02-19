from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class BrainsuiteAppBase(BaseModel):
    name: str
    description: Optional[str] = None
    app_type: str  # VIDEO, IMAGE
    is_default_for_video: bool = False
    is_default_for_image: bool = False


class BrainsuiteAppCreate(BrainsuiteAppBase):
    pass


class BrainsuiteAppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default_for_video: Optional[bool] = None
    is_default_for_image: Optional[bool] = None


class BrainsuiteAppResponse(BrainsuiteAppBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PlatformConnectionCreate(BaseModel):
    platform: str  # META, TIKTOK, YOUTUBE
    ad_account_id: str
    ad_account_name: Optional[str] = None
    brainsuite_app_id: Optional[uuid.UUID] = None
    default_metadata_values: Dict[str, Any] = {}


class PlatformConnectionUpdate(BaseModel):
    brainsuite_app_id: Optional[uuid.UUID] = None
    default_metadata_values: Optional[Dict[str, Any]] = None


class PlatformConnectionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    platform: str
    ad_account_id: str
    ad_account_name: Optional[str]
    currency: Optional[str]
    timezone: Optional[str]
    sync_status: str
    last_synced_at: Optional[datetime]
    initial_sync_completed: bool
    historical_sync_completed: bool
    is_active: bool
    created_at: datetime
    created_by_user_id: uuid.UUID
    brainsuite_app_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True


class OAuthInitRequest(BaseModel):
    platform: str  # META, TIKTOK, YOUTUBE


class OAuthCallbackRequest(BaseModel):
    platform: str
    code: str
    state: Optional[str] = None


class OAuthAuthorizedAccount(BaseModel):
    """Represents an ad account returned after OAuth completion."""
    id: str
    name: str
    currency: Optional[str] = None
    timezone: Optional[str] = None
    platform: str
    status: Optional[str] = None


class AdAccountSetup(BaseModel):
    ad_account_id: str
    ad_account_name: str
    brainsuite_app_id: Optional[uuid.UUID] = None
    default_metadata_values: Dict[str, Any] = {}


class AdAccountSelectionRequest(BaseModel):
    """User selects which ad accounts to connect after OAuth."""
    platform: str
    oauth_session_id: str
    selected_accounts: List[AdAccountSetup]
