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
from sqlalchemy import select, update, func, delete

from app.db.base import get_db
from app.models.user import User
from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
from app.models.platform import BrainsuiteApp
from app.models.metadata import MetadataField
from app.models.scoring import CreativeScoreResult
from app.schemas.brainsuite_config import (
    CredentialsResponse,
    CredentialsUpdate,
    CredentialsSaveResponse,
    TestConnectionResponse,
    SystemAppNameUpdate,
    RescoreRequest,
)
from app.schemas.brainsuite_field_mappings import (
    FieldMappingResponse,
    FieldMappingUpdate,
    FieldMappingRow,
    MetadataFieldOption,
)
from app.api.v1.deps import get_current_admin
from app.core.security import encrypt_token, decrypt_token
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

STANDARD_VIDEO_FIELDS = [
    "projectName", "assetName", "assetStage", "assetLanguage",
    "brandNames", "voiceOver", "voiceOverLanguage", "intendedMessages",
    "intendedMessagesLanguage", "brandValues", "brandValuesLanguage",
]

STANDARD_STATIC_FIELDS = [
    "projectName", "assetLanguage", "iconicColorScheme",
    "intendedMessages", "intendedMessagesLanguage", "brandValues",
    "brandValuesLanguage",
]

# D-06: Auto-match hints — map standard API field names to metadata field slugs
# Note: "channel" is excluded — it is auto-derived from asset.platform + asset.placement
AUTO_MATCH_HINTS: dict[str, str] = {
    "brandValues": "brainsuite_brand_values",
    "brandValuesLanguage": "brainsuite_brand_values_language",
    "assetLanguage": "brainsuite_asset_language",
    "voiceOverLanguage": "brainsuite_voice_over_language",
    "assetName": "brainsuite_asset_name",
}


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


@router.get("/apps/{app_id}/field-mappings", response_model=FieldMappingResponse)
async def get_field_mappings(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Fetch field mappings + metadata options for a BrainsuiteApp.

    If the app has zero saved mappings, standard fields are returned with
    auto-matched metadata_field_ids based on name similarity (D-06).
    Auto-matched values are NOT persisted until the admin clicks Save.
    """
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")

    # Fetch existing mappings for this app
    result = await db.execute(
        select(OrgBrainsuiteFieldMapping).where(
            OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id
        )
    )
    mappings = result.scalars().all()

    # Fetch org metadata fields for dropdown
    result = await db.execute(
        select(MetadataField).where(
            MetadataField.organization_id == current_user.organization_id,
            MetadataField.is_active == True,
        ).order_by(MetadataField.sort_order)
    )
    metadata_fields = result.scalars().all()

    # Build metadata slug lookup for auto-matching
    slug_to_id: dict[str, uuid.UUID] = {f.name: f.id for f in metadata_fields}

    # Determine standard fields for this app type
    standard_names = STANDARD_VIDEO_FIELDS if app.app_type == "VIDEO" else STANDARD_STATIC_FIELDS

    # Build mapping lookup by api_field_name
    mapping_by_name: dict[str, OrgBrainsuiteFieldMapping] = {m.api_field_name: m for m in mappings}
    has_saved_mappings = len(mappings) > 0

    # Build standard field rows
    standard_rows: list[FieldMappingRow] = []
    for field_name in standard_names:
        existing = mapping_by_name.get(field_name)
        if existing:
            standard_rows.append(FieldMappingRow(
                api_field_name=field_name,
                metadata_field_id=existing.metadata_field_id,
                is_mandatory=existing.is_mandatory,
                is_custom=False,
            ))
        else:
            # D-06: auto-match if no saved mappings exist
            auto_id = slug_to_id.get(AUTO_MATCH_HINTS.get(field_name, "")) if not has_saved_mappings else None
            standard_rows.append(FieldMappingRow(
                api_field_name=field_name,
                metadata_field_id=auto_id,
                is_mandatory=False,
                is_custom=False,
            ))

    # Build custom field rows (only from saved mappings)
    custom_rows: list[FieldMappingRow] = [
        FieldMappingRow(
            api_field_name=m.api_field_name,
            metadata_field_id=m.metadata_field_id,
            is_mandatory=m.is_mandatory,
            is_custom=True,
        )
        for m in mappings if m.is_custom
    ]

    return FieldMappingResponse(
        app_id=app_id,
        app_name=app.name,
        app_type=app.app_type,
        standard_fields=standard_rows,
        custom_fields=custom_rows,
        metadata_options=[
            MetadataFieldOption(id=f.id, name=f.name, label=f.label, field_type=f.field_type)
            for f in metadata_fields
        ],
    )


@router.put("/apps/{app_id}/field-mappings")
async def upsert_field_mappings(
    app_id: uuid.UUID,
    payload: FieldMappingUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist all field mappings atomically. Deletes old, inserts new (D-10)."""
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")

    # Validate standard field count
    max_standard = 12 if app.app_type == "VIDEO" else 8
    if len(payload.standard_fields) > max_standard:
        raise HTTPException(
            status_code=400,
            detail=f"Too many standard fields for {app.app_type} app (max {max_standard})",
        )

    # Validate: custom field names must not duplicate standard names
    standard_names_set = {f.api_field_name for f in payload.standard_fields}
    custom_names_seen: set[str] = set()
    for cf in payload.custom_fields:
        if cf.api_field_name in standard_names_set:
            raise HTTPException(
                status_code=400,
                detail=f"Custom field '{cf.api_field_name}' conflicts with a standard field name",
            )
        if cf.api_field_name in custom_names_seen:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate custom field name: '{cf.api_field_name}'",
            )
        custom_names_seen.add(cf.api_field_name)

    # Validate: metadata_field_ids belong to this org (if set)
    all_metadata_ids = set()
    for f in payload.standard_fields:
        if f.metadata_field_id:
            all_metadata_ids.add(f.metadata_field_id)
    for f in payload.custom_fields:
        if f.metadata_field_id:
            all_metadata_ids.add(f.metadata_field_id)

    if all_metadata_ids:
        result = await db.execute(
            select(func.count()).select_from(MetadataField).where(
                MetadataField.id.in_(all_metadata_ids),
                MetadataField.organization_id == current_user.organization_id,
            )
        )
        valid_count = result.scalar() or 0
        if valid_count != len(all_metadata_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more metadata_field_id values do not belong to this organization",
            )

    # Atomic replace: delete all existing mappings for this app
    await db.execute(
        delete(OrgBrainsuiteFieldMapping).where(
            OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id
        )
    )

    # Insert standard fields
    for field in payload.standard_fields:
        mapping = OrgBrainsuiteFieldMapping(
            brainsuite_app_id=app_id,
            organization_id=current_user.organization_id,
            api_field_name=field.api_field_name,
            metadata_field_id=field.metadata_field_id,
            is_mandatory=field.is_mandatory,
            is_custom=False,
            app_type=app.app_type,
        )
        db.add(mapping)

    # Insert custom fields
    for field in payload.custom_fields:
        mapping = OrgBrainsuiteFieldMapping(
            brainsuite_app_id=app_id,
            organization_id=current_user.organization_id,
            api_field_name=field.api_field_name,
            metadata_field_id=field.metadata_field_id,
            is_mandatory=field.is_mandatory,
            is_custom=True,
            app_type=app.app_type,
        )
        db.add(mapping)

    await db.commit()
    return {"success": True}
