"""Pydantic schemas for BrainSuite configuration endpoints (Phase 12)."""
from pydantic import BaseModel
from typing import Optional


class CredentialsResponse(BaseModel):
    """GET /credentials response. NEVER includes the raw secret (T-12-04)."""
    client_id: Optional[str] = None
    has_secret: bool = False          # True if client_secret_encrypted is non-null in DB
    has_scored_assets: bool = False    # True if org has any COMPLETE score results

    class Config:
        from_attributes = True


class CredentialsUpdate(BaseModel):
    """PUT /credentials request. Per D-07: empty client_secret means keep existing."""
    client_id: str
    client_secret: str = ""           # empty string = keep existing secret


class CredentialsSaveResponse(BaseModel):
    """PUT /credentials response. changed flag drives re-score dialog (D-11)."""
    changed: bool
    has_scored_assets: bool = False


class TestConnectionResponse(BaseModel):
    """POST /test-connection response."""
    success: bool
    message: str


class SystemAppNameUpdate(BaseModel):
    """PATCH /apps/{app_id}/system-app-name request."""
    system_app_name: Optional[str] = None
