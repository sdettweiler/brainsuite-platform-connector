"""BrainSuite configuration endpoints (Phase 12).

Provides credentials CRUD, test-connection, system-app-name PATCH, and rescore-all.
All mutating endpoints require admin role (D-06, D-07, D-08, D-09, D-11, D-13).
"""
import logging
import base64
from datetime import datetime, timezone

import httpx
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.base import get_db
from app.models.user import User
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.models.platform import BrainsuiteApp
from app.models.scoring import CreativeScoreResult
from app.schemas.brainsuite_config import (
    CredentialsResponse,
    CredentialsUpdate,
    CredentialsSaveResponse,
    TestConnectionResponse,
    SystemAppNameUpdate,
    RescoreRequest,
)
from app.api.v1.deps import get_current_admin
from app.core.security import encrypt_token, decrypt_token
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def _has_scored_assets(db: AsyncSession, organization_id: uuid.UUID) -> bool:
    """Check if org has any COMPLETE score results (for re-score dialog trigger)."""
    result = await db.execute(
        select(func.count()).select_from(CreativeScoreResult).where(
            CreativeScoreResult.organization_id == organization_id,
            CreativeScoreResult.scoring_status == "COMPLETE",
        )
    )
    return (result.scalar() or 0) > 0


@router.get("/credentials", response_model=CredentialsResponse)
async def get_credentials(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return current org credentials (client_id + has_secret flag). Never returns raw secret."""
    result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == current_user.organization_id
        )
    )
    config = result.scalar_one_or_none()

    has_scored = await _has_scored_assets(db, current_user.organization_id)

    if not config:
        return CredentialsResponse(client_id=None, has_secret=False, has_scored_assets=has_scored)

    return CredentialsResponse(
        client_id=config.client_id,
        has_secret=config.client_secret_encrypted is not None,
        has_scored_assets=has_scored,
    )


@router.put("/credentials", response_model=CredentialsSaveResponse)
async def upsert_credentials(
    payload: CredentialsUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Save credentials. Per D-07: empty client_secret means keep existing."""
    result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == current_user.organization_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = OrgBrainsuiteConfig(
            organization_id=current_user.organization_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(config)

    old_client_id = config.client_id
    config.client_id = payload.client_id

    secret_changed = False
    if payload.client_secret:  # D-07: non-empty = new secret
        config.client_secret_encrypted = encrypt_token(payload.client_secret)
        secret_changed = True

    config.updated_at = datetime.now(timezone.utc)
    await db.commit()

    changed = (old_client_id != payload.client_id) or secret_changed
    has_scored = await _has_scored_assets(db, current_user.organization_id)

    return CredentialsSaveResponse(changed=changed, has_scored_assets=has_scored)


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Test BrainSuite auth using stored credentials. Per D-08: requires stored credentials."""
    result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == current_user.organization_id
        )
    )
    config = result.scalar_one_or_none()

    if not config or not config.client_id or not config.client_secret_encrypted:
        raise HTTPException(status_code=400, detail="No credentials configured")

    try:
        client_secret = decrypt_token(config.client_secret_encrypted)
        credentials = f"{config.client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.BRAINSUITE_AUTH_URL,
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )

        # Pitfall 5: Check both status AND response body for access_token
        if resp.status_code == 200:
            try:
                body = resp.json()
                if "access_token" in body:
                    return TestConnectionResponse(success=True, message="Connection successful")
                else:
                    error_detail = body.get("error", "no access_token in response")
                    return TestConnectionResponse(
                        success=False,
                        message=f"Authentication failed: {error_detail}",
                    )
            except Exception:
                return TestConnectionResponse(
                    success=False,
                    message="Authentication failed: invalid response from BrainSuite",
                )
        else:
            return TestConnectionResponse(
                success=False,
                message=f"Authentication failed (HTTP {resp.status_code})",
            )

    except httpx.ConnectError:
        return TestConnectionResponse(
            success=False,
            message="Could not reach BrainSuite — check your network connection",
        )
    except Exception as exc:
        logger.warning("Test connection failed for org %s: %s", current_user.organization_id, exc)
        return TestConnectionResponse(
            success=False,
            message=f"Connection error: {str(exc)[:200]}",
        )


@router.patch("/apps/{app_id}/system-app-name")
async def update_system_app_name(
    app_id: uuid.UUID,
    payload: SystemAppNameUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update system_app_name on a BrainsuiteApp. Per D-04: accordion save."""
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")

    old_name = app.system_app_name
    app.system_app_name = payload.system_app_name
    app.updated_at = datetime.now(timezone.utc)
    db.add(app)
    await db.commit()
    await db.refresh(app)

    changed = old_name != payload.system_app_name
    has_scored = await _has_scored_assets(db, current_user.organization_id)

    return {"changed": changed, "has_scored_assets": has_scored}


@router.post("/rescore-all")
async def rescore_all(
    payload: RescoreRequest = RescoreRequest(),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reset COMPLETE assets to UNSCORED. Scoped by app_type when provided.
    VIDEO  → only endpoint_type='VIDEO'
    IMAGE  → only endpoint_type='STATIC_IMAGE'
    MIXED or absent → all endpoint types (used when credentials change)
    IMPORTANT: Never touches PROCESSING (live job IDs) or PENDING.
    """
    # Map BrainsuiteApp.app_type to CreativeScoreResult.endpoint_type
    ENDPOINT_TYPE_MAP = {"VIDEO": "VIDEO", "IMAGE": "STATIC_IMAGE"}
    endpoint_filter = ENDPOINT_TYPE_MAP.get(payload.app_type) if payload.app_type else None

    conditions = [
        CreativeScoreResult.organization_id == current_user.organization_id,
        CreativeScoreResult.scoring_status == "COMPLETE",
    ]
    if endpoint_filter:
        conditions.append(CreativeScoreResult.endpoint_type == endpoint_filter)

    result = await db.execute(
        update(CreativeScoreResult)
        .where(*conditions)
        .values(scoring_status="UNSCORED", updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    count = result.rowcount
    logger.info(
        "Rescore-all: reset %d COMPLETE assets to UNSCORED for org %s (app_type=%s)",
        count, current_user.organization_id, payload.app_type or "ALL",
    )
    return {"reset_count": count}
