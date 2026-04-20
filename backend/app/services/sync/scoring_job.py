"""BrainSuite scoring batch job — runs via APScheduler every 15 minutes.

Public API:
  run_scoring_batch()   — batch scheduler entry point (called by APScheduler)
  score_asset_now(score_id) — score a single asset immediately (called by rescore endpoint)
"""
import asyncio
import logging
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select, and_

from app.db.base import get_session_factory
from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
from app.models.platform import BrainsuiteApp
from app.models.creative import CreativeAsset, AssetMetadataValue
from app.models.scoring import CreativeScoreResult
from app.models.metadata import MetadataField
from app.core.security import decrypt_token
from app.services.brainsuite_score import (
    brainsuite_score_service,
    build_scoring_payload,
    extract_score_data,
    persist_and_replace_visualizations,
)
from app.services.brainsuite_exceptions import BrainSuiteJobError
from app.services.brainsuite_static_score import (
    brainsuite_static_score_service,
    build_static_scoring_payload,
)
from app.services.object_storage import get_object_storage
from app.services.notifications import create_org_notification

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


async def run_scoring_batch() -> None:
    """Process up to BATCH_SIZE UNSCORED VIDEO and IMAGE assets and submit to BrainSuite.

    Routes each asset to the correct BrainSuite service based on endpoint_type:
      - VIDEO        → BrainSuiteScoreService (ACE_VIDEO_SMV_API)
      - STATIC_IMAGE → BrainSuiteStaticScoreService (ACE_STATIC_SOCIAL_STATIC_API)
      - UNSUPPORTED  → excluded from query (scoring_status=UNSUPPORTED, not UNSCORED)

    Phase 1: Query batch in one DB session, mark PENDING, release session.
    Phase 2: For each asset, download from internal storage, submit via the
             announce→upload→start flow, poll, store result.
             NO DB session is held during HTTP calls.
    Phase 3.5: Emit per-org SCORING_BATCH_COMPLETE notifications.
    """
    logger.info("Starting scoring batch run")

    # -----------------------------------------------------------------------
    # Phase 1: Fetch batch and mark PENDING (single DB session, then release)
    # -----------------------------------------------------------------------
    batch = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult, CreativeAsset)
            .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
            .order_by(CreativeScoreResult.created_at.asc())
            .limit(BATCH_SIZE)
        )
        rows = result.all()

        if not rows:
            logger.info("Scoring batch: no UNSCORED VIDEO or STATIC_IMAGE assets found, exiting")
            return

        for score_row, asset_row in rows:
            batch.append({
                "score_id": score_row.id,
                "asset_id": asset_row.id,
                "asset": asset_row,
                "endpoint_type": score_row.endpoint_type,
            })
            score_row.scoring_status = "PENDING"

        await db.commit()
        db.expunge_all()  # detach all objects while attributes are still loaded — prevents DetachedInstanceError in Phase 2/3.5

    logger.info("Scoring batch: found %d assets to score, marked PENDING", len(batch))

    # -----------------------------------------------------------------------
    # Phase 2: Process each asset — NO session held during HTTP calls
    # -----------------------------------------------------------------------
    for item in batch:
        await _process_asset(item["score_id"], item["asset"], item["endpoint_type"])

    # -----------------------------------------------------------------------
    # Phase 3.5: Emit per-org SCORING_BATCH_COMPLETE notifications
    # -----------------------------------------------------------------------
    score_ids = [item["score_id"] for item in batch]
    org_id_by_score: dict = {str(item["score_id"]): str(item["asset"].organization_id) for item in batch}

    # Query final statuses for all processed assets
    org_complete: Counter = Counter()
    org_failed: Counter = Counter()
    async with get_session_factory()() as db:
        rows = await db.execute(
            select(CreativeScoreResult.id, CreativeScoreResult.scoring_status)
            .where(CreativeScoreResult.id.in_(score_ids))
        )
        for row_id, status in rows:
            org_id = org_id_by_score.get(str(row_id))
            if not org_id:
                continue
            if status == "COMPLETE":
                org_complete[org_id] += 1
            else:
                org_failed[org_id] += 1

    all_orgs = set(org_complete.keys()) | set(org_failed.keys())
    if all_orgs:
        for org_id in all_orgs:
            complete = org_complete[org_id]
            failed = org_failed[org_id]
            total = complete + failed

            if failed == 0:
                title = "Scoring Complete"
                message = f"{complete} creative{'s' if complete != 1 else ''} scored successfully."
            elif complete == 0:
                title = "Scoring Failed"
                message = f"{failed} creative{'s' if failed != 1 else ''} failed to score."
            else:
                title = "Scoring Complete"
                message = f"{complete} of {total} creatives scored successfully, {failed} failed."

            asyncio.create_task(create_org_notification(
                org_id=org_id,
                type="SCORING_BATCH_COMPLETE",
                title=title,
                message=message,
                data={"scored_count": complete, "failed_count": failed, "total_count": total},
            ))


async def score_asset_now(score_id: uuid.UUID) -> None:
    """Score a single asset immediately — called by the rescore endpoint.

    Loads the score row + asset from DB, marks PENDING, then delegates to
    _process_asset(). Designed to run as a FastAPI BackgroundTask.
    """
    logger.info("score_asset_now: loading score_id=%s", score_id)
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult, CreativeAsset)
            .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
            .where(CreativeScoreResult.id == score_id)
        )
        row = result.one_or_none()
        if row:
            db.expunge_all()  # detach while attributes are still loaded — prevents DetachedInstanceError

    if not row:
        logger.error("score_asset_now: score_id=%s not found", score_id)
        return

    score_row, asset = row
    endpoint_type = score_row.endpoint_type

    if endpoint_type == "UNSUPPORTED":
        logger.warning(
            "score_asset_now: asset %s is UNSUPPORTED, skipping",
            score_row.creative_asset_id,
        )
        return

    if endpoint_type not in ("VIDEO", "STATIC_IMAGE"):
        logger.error(
            "score_asset_now: unknown endpoint_type=%s for score_id=%s",
            endpoint_type,
            score_id,
        )
        return

    # Mark PENDING before handing off (same as batch does before processing)
    async with get_session_factory()() as db:
        row2 = await db.get(CreativeScoreResult, score_id)
        if row2:
            row2.scoring_status = "PENDING"
            row2.error_reason = None
            await db.commit()

    await _process_asset(score_id, asset, endpoint_type)


async def _process_asset(score_id, asset: CreativeAsset, endpoint_type: str) -> None:
    """Core per-asset scoring logic — shared by batch and immediate paths."""
    asset_id = asset.id

    logger.info(
        "Scoring asset %s: endpoint_type=%s platform=%s format=%s",
        asset_id,
        endpoint_type,
        getattr(asset, "platform", "?"),
        getattr(asset, "asset_format", "?"),
    )
    try:
        # [Phase 11 / PIPE-01] Load org BrainSuite config — graceful UNSCORED on missing/incomplete (D-02)
        org_config = None
        async with get_session_factory()() as db:
            config_result = await db.execute(
                select(OrgBrainsuiteConfig).where(
                    OrgBrainsuiteConfig.organization_id == asset.organization_id
                )
            )
            org_config = config_result.scalar_one_or_none()

            # Phase 12: resolve BrainsuiteApp row to get system_app_name
            brainsuite_app = None
            if asset.brainsuite_app_id:
                brainsuite_app = await db.get(BrainsuiteApp, asset.brainsuite_app_id)

        required_app_name = brainsuite_app.system_app_name if brainsuite_app else None

        # [Phase 13 / PIPE-02] Guard: incomplete config blocks scoring (silent — no notification per D-13)
        if (
            not org_config
            or not org_config.client_id
            or not org_config.client_secret_encrypted
            or not required_app_name
        ):
            missing = "no config row" if not org_config else (
                "client_id" if not org_config.client_id else
                "client_secret" if not org_config.client_secret_encrypted else
                "app_name"
            )
            logger.warning(
                "Scoring skipped for asset %s (org %s): incomplete BrainSuite config (missing %s)",
                asset_id, asset.organization_id, missing,
            )
            await _mark_unscored(score_id, f"No BrainSuite configuration for this organization (missing {missing}).")
            return

        # [Phase 13 / FMAP-07] Guard: check mandatory fields have mappings + values
        if brainsuite_app:
            is_valid, missing_fields = await _check_mandatory_fields(
                asset_id=asset_id,
                app_id=brainsuite_app.id,
                organization_id=asset.organization_id,
            )
            if not is_valid and missing_fields:
                logger.warning(
                    "Scoring skipped for asset %s: mandatory field(s) missing: %s",
                    asset_id, ", ".join(missing_fields),
                )
                # D-12: Create MANDATORY_FIELD_MISSING notification
                asyncio.create_task(create_org_notification(
                    org_id=str(asset.organization_id),
                    type="MANDATORY_FIELD_MISSING",
                    title="Scoring skipped \u2014 mandatory field missing",
                    message=(
                        f"Asset \"{asset.ad_name or str(asset_id)}\" was not scored. "
                        f"Missing field(s): {', '.join(missing_fields)}."
                    ),
                    data={
                        "asset_id": str(asset_id),
                        "asset_name": asset.ad_name or str(asset_id),
                        "missing_fields": missing_fields,
                    },
                ))
                await _mark_unscored(
                    score_id,
                    f"Mandatory field(s) missing: {', '.join(missing_fields)}",
                )
                return

        client_secret = decrypt_token(org_config.client_secret_encrypted)
        org_id_str = str(asset.organization_id)

        asset_url = asset.asset_url
        if not asset_url:
            raise ValueError("No S3 asset URL available")

        s3_key = asset_url.lstrip("/")
        if s3_key.startswith("objects/"):
            s3_key = s3_key[len("objects/"):]
        logger.info("Scoring asset %s: downloading from s3_key=%s", asset_id, s3_key)

        file_bytes, _ = get_object_storage().download_blob(s3_key)
        if not file_bytes:
            raise ValueError(f"Asset not found in object storage: {s3_key}")
        logger.info("Scoring asset %s: downloaded %d bytes", asset_id, len(file_bytes))

        metadata_dict: dict[str, str] = {}
        async with get_session_factory()() as db:
            # LEFT JOIN so fields with no asset-specific value still appear;
            # fall back to MetadataField.default_value in that case.
            meta_result = await db.execute(
                select(MetadataField.name, AssetMetadataValue.value, MetadataField.default_value)
                .outerjoin(
                    AssetMetadataValue,
                    and_(
                        AssetMetadataValue.field_id == MetadataField.id,
                        AssetMetadataValue.asset_id == asset_id,
                    ),
                )
                .where(
                    MetadataField.organization_id == asset.organization_id,
                    MetadataField.name.like("brainsuite_%"),
                    MetadataField.is_active.is_(True),
                )
            )
            for field_name, field_value, default_value in meta_result.all():
                effective = field_value if field_value is not None else default_value
                if effective is not None:
                    # Convert stored xx_XX locale format to BS API xx-XX (BCP 47)
                    effective = re.sub(r'^([a-z]{2})_([A-Z]{2})$', r'\1-\2', effective)
                    metadata_dict[field_name] = effective

        filename = os.path.basename(s3_key) or (asset.ad_name or f"{asset_id}")
        logger.info(
            "Scoring asset %s: filename=%s metadata_keys=%s",
            asset_id,
            filename,
            list(metadata_dict.keys()),
        )

        if endpoint_type == "VIDEO":
            briefing_data = build_scoring_payload(
                asset_name=filename,
                platform=asset.platform,
                placement=asset.placement,
                metadata=metadata_dict,
            )
            job_id = await brainsuite_score_service.submit_job_with_upload(
                file_bytes=file_bytes,
                filename=filename,
                briefing_data=briefing_data,
                org_id=org_id_str,
                client_id=org_config.client_id,
                client_secret=client_secret,
                app_name=required_app_name,
            )
        elif endpoint_type == "STATIC_IMAGE":
            announce_payload = build_static_scoring_payload(
                asset_name=filename,
                platform=asset.platform,
                placement=asset.placement,
                metadata=metadata_dict,
            )
            job_id = await brainsuite_static_score_service.submit_job_with_upload(
                file_bytes=file_bytes,
                filename=filename,
                announce_payload=announce_payload,
                org_id=org_id_str,
                client_id=org_config.client_id,
                client_secret=client_secret,
                app_name=required_app_name,
            )
        else:
            logger.warning("Unexpected endpoint_type %s for asset %s, skipping", endpoint_type, asset_id)
            return

        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.brainsuite_job_id = str(job_id)
                score_row.scoring_status = "PROCESSING"
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info("Scoring job submitted for asset %s, job_id=%s endpoint_type=%s", asset_id, job_id, endpoint_type)

        if endpoint_type == "VIDEO":
            result_data = await brainsuite_score_service.poll_job_status(
                str(job_id),
                org_id=org_id_str,
                client_id=org_config.client_id,
                client_secret=client_secret,
                app_name=required_app_name,
            )
        else:
            result_data = await brainsuite_static_score_service.poll_job_status(
                str(job_id),
                org_id=org_id_str,
                client_id=org_config.client_id,
                client_secret=client_secret,
                app_name=required_app_name,
            )

        raw_output = result_data.get("output", {})
        stored_output = await persist_and_replace_visualizations(raw_output, str(asset_id))
        result_data = {**result_data, "output": stored_output}

        score_data = extract_score_data(result_data, strip_viz=False)

        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.total_score = score_data["total_score"]
                score_row.total_rating = score_data["total_rating"]
                score_row.score_dimensions = score_data["score_dimensions"]
                score_row.scoring_status = "COMPLETE"
                score_row.scored_at = datetime.now(timezone.utc)
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            "Scoring complete for asset %s: score=%.1f rating=%s",
            asset_id,
            score_data["total_score"],
            score_data["total_rating"],
        )

    except BrainSuiteJobError as exc:
        error_reason = str(exc)[:500]
        logger.warning("BrainSuite job error for asset %s (endpoint_type=%s): %s", asset_id, endpoint_type, error_reason)
        await _mark_failed(score_id, error_reason)

    except Exception as exc:
        error_reason = f"{type(exc).__name__}: {str(exc)[:500]}"
        logger.error(
            "Unexpected error scoring asset %s (endpoint_type=%s): %s",
            asset_id, endpoint_type, error_reason,
            exc_info=True,
        )
        await _mark_failed(score_id, error_reason)


async def run_backfill_task() -> None:
    """Queue all UNSCORED VIDEO and STATIC_IMAGE assets cross-tenant via score_asset_now().

    Designed to run as a FastAPI BackgroundTask.
    Fetches all UNSCORED score IDs in a single session (then releases),
    then iterates without holding a DB connection during HTTP calls.
    """
    logger.info("Backfill task started")

    score_ids: list[uuid.UUID] = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult.id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
            .order_by(CreativeScoreResult.created_at.asc())
        )
        score_ids = list(result.scalars().all())

    logger.info("Backfill task: found %d UNSCORED assets to score", len(score_ids))

    scored = 0
    failed = 0
    for score_id in score_ids:
        try:
            await score_asset_now(score_id)
            scored += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "Backfill: unexpected error for score_id=%s: %s",
                score_id,
                exc,
                exc_info=True,
            )

    logger.info(
        "Backfill task complete: %d scored, %d failed out of %d total",
        scored,
        failed,
        len(score_ids),
    )


async def _check_mandatory_fields(
    asset_id: uuid.UUID,
    app_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> tuple[bool, list[str]]:
    """Check if asset has values for all mandatory field mappings.

    Reads mandatory mappings for the given BrainsuiteApp, then checks
    whether the asset has an AssetMetadataValue row with a non-empty
    value for each mandatory field's metadata_field_id.

    Returns:
        (is_valid, missing_field_names) — is_valid is True if all mandatory
        fields have values; missing_field_names lists the api_field_name of
        any field that is unmapped or has no asset value.
    """
    async with get_session_factory()() as db:
        # Fetch mandatory field mappings for this app
        result = await db.execute(
            select(OrgBrainsuiteFieldMapping).where(
                OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id,
                OrgBrainsuiteFieldMapping.is_mandatory == True,
            )
        )
        mandatory_mappings = result.scalars().all()

        if not mandatory_mappings:
            return (True, [])  # No mandatory fields configured — all clear

        missing_fields: list[str] = []
        for mapping in mandatory_mappings:
            if not mapping.metadata_field_id:
                # Field is mandatory but not mapped to any metadata field
                missing_fields.append(mapping.api_field_name)
                continue

            # Check if asset has a non-empty value for this metadata field
            # NOTE: AssetMetadataValue uses column "field_id" (not "metadata_field_id")
            value_result = await db.execute(
                select(AssetMetadataValue).where(
                    AssetMetadataValue.asset_id == asset_id,
                    AssetMetadataValue.field_id == mapping.metadata_field_id,
                )
            )
            value_row = value_result.scalar_one_or_none()

            if not value_row or not value_row.value:
                missing_fields.append(mapping.api_field_name)

    return (len(missing_fields) == 0, missing_fields)


async def _mark_unscored(score_id, error_reason: str) -> None:
    """Mark a CreativeScoreResult as UNSCORED (only from PENDING state).

    Per project rule: never reset PROCESSING assets (they have live BrainSuite job IDs).
    This helper only transitions rows currently in PENDING status.
    """
    logger.info("Marking score_id=%s as UNSCORED: %s", score_id, error_reason[:200])
    try:
        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row and score_row.scoring_status == "PENDING":
                score_row.scoring_status = "UNSCORED"
                score_row.error_reason = error_reason
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to mark score record %s as UNSCORED: %s", score_id, exc)


async def _mark_failed(score_id, error_reason: str) -> None:
    """Mark a CreativeScoreResult as FAILED with the given error_reason."""
    logger.info("Marking score_id=%s as FAILED: %s", score_id, error_reason[:200])
    try:
        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.scoring_status = "FAILED"
                score_row.error_reason = error_reason
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as exc:
        logger.error(
            "Failed to mark score record %s as FAILED: %s",
            score_id,
            exc,
        )
