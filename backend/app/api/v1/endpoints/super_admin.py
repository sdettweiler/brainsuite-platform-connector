"""
SuperAdmin API endpoints.

Provides platform-wide administrative operations:
- YouTube cookie management (health check + update)
- SuperAdmin user management (list + promote)
- Organization read-only list with user counts
- Scoring controls: global toggle, per-org quota, reset to UNSCORED

All endpoints require SuperAdmin privileges (Depends(get_current_superadmin)).
Cookie content is NEVER returned in any response — only health status strings.

Security (T-14-05 through T-14-08):
- GET /youtube-cookies: health only, no decrypted content in response
- PUT /youtube-cookies: encrypts before storage, never logs decrypted values
- POST /users/promote: only existing SuperAdmins can call this endpoint

Scoring controls security:
- Reset endpoint supports FAILED, COMPLETE, PROCESSING, PENDING statuses
"""
import httpx
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.db.base import get_db
from app.models.system_config import SystemConfig
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.models.scoring import CreativeScoreResult
from app.models.user import User, Organization
from app.api.v1.deps import get_current_superadmin
from app.core.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CookieSlotHealth(BaseModel):
    status: Literal["valid", "expired", "missing"]


class CookieHealthResponse(BaseModel):
    primary: CookieSlotHealth
    backup: CookieSlotHealth


class UpdateCookiesRequest(BaseModel):
    primary: Optional[str] = None
    backup: Optional[str] = None


class ProxyConfigResponse(BaseModel):
    proxy_enabled: bool
    proxy_url_masked: Optional[str] = None


class UpdateProxyConfigRequest(BaseModel):
    proxy_enabled: Optional[bool] = None
    proxy_url: Optional[str] = None


class ConcurrencyConfigResponse(BaseModel):
    max_concurrent_downloads: int

    class Config:
        from_attributes = True


class ConcurrencyConfigRequest(BaseModel):
    max_concurrent_downloads: int = Field(ge=1, le=10)


class ProxyTestResponse(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class SuperAdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class PromoteRequest(BaseModel):
    email: EmailStr


class OrgListItem(BaseModel):
    id: str
    name: str
    slug: str
    user_count: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Cookie health helper (T-14-05: expiry parsing only, no live yt-dlp test)
# ---------------------------------------------------------------------------

def _check_cookie_health(cookie_data: str) -> str:
    """Parse Netscape cookie expiry timestamps. Returns 'valid', 'expired', or 'missing'.

    Replicates the logic from DV360SyncService._check_youtube_cookies but accepts
    a cookie string directly instead of reading from an env var.
    """
    if not cookie_data:
        return "missing"
    now_ts = datetime.now().timestamp()
    has_any_expiry = False
    has_valid = False
    for line in cookie_data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            try:
                expiry = int(parts[4])
                if expiry > 0:
                    has_any_expiry = True
                    if expiry > now_ts:
                        has_valid = True
            except (ValueError, IndexError):
                pass
    if not has_any_expiry:
        return "valid"
    return "valid" if has_valid else "expired"


# ---------------------------------------------------------------------------
# Proxy URL masking helper (T-21-01: credentials never returned in plaintext)
# ---------------------------------------------------------------------------

def _mask_proxy_url(url: str) -> str:
    """Parse http(s)://user:pass@host:port and mask credentials: http://••••••@host:port.

    Security (T-21-01): Only the host:port portion is returned. Credential
    portion is always replaced with bullet characters.
    """
    try:
        if "@" in url:
            scheme_and_auth, host_port = url.rsplit("@", 1)
            scheme = scheme_and_auth.split("://")[0] if "://" in scheme_and_auth else "http"
            return f"{scheme}://••••••@{host_port}"
        return url
    except Exception:
        return url


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/youtube-cookies", response_model=CookieHealthResponse)
async def get_youtube_cookies(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return health status for both YouTube cookie slots.

    Security (T-14-05): Response model contains ONLY status strings.
    Decrypted cookie content is never included in the response.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    primary_status = "missing"
    backup_status = "missing"

    if config:
        if config.youtube_cookies_encrypted:
            try:
                decrypted = decrypt_token(config.youtube_cookies_encrypted)
                primary_status = _check_cookie_health(decrypted)
            except Exception:
                primary_status = "missing"

        if config.youtube_cookies_backup_encrypted:
            try:
                decrypted = decrypt_token(config.youtube_cookies_backup_encrypted)
                backup_status = _check_cookie_health(decrypted)
            except Exception:
                backup_status = "missing"

        # Runtime expiry (rejected by YouTube) overrides timestamp-based status per slot
        if getattr(config, "youtube_cookies_runtime_expired", False) and primary_status != "missing":
            primary_status = "expired"
        if getattr(config, "youtube_cookies_backup_runtime_expired", False) and backup_status != "missing":
            backup_status = "expired"

    return CookieHealthResponse(
        primary=CookieSlotHealth(status=primary_status),
        backup=CookieSlotHealth(status=backup_status),
    )


@router.put("/youtube-cookies", response_model=CookieHealthResponse)
async def update_youtube_cookies(
    payload: UpdateCookiesRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update YouTube cookie slots (partial update supported).

    Security (T-14-06): Cookie values are encrypted before storage.
    Never logged at any level.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    if payload.primary is not None:
        config.youtube_cookies_encrypted = encrypt_token(payload.primary)
        logger.info("SuperAdmin updated primary YouTube cookie slot (cookie content not logged)")

    if payload.backup is not None:
        config.youtube_cookies_backup_encrypted = encrypt_token(payload.backup)
        logger.info("SuperAdmin updated backup YouTube cookie slot (cookie content not logged)")

    # Reset each slot's expiry flag independently; stats/refreshed_at only reset when primary is replaced
    if payload.primary is not None:
        config.youtube_cookies_runtime_expired = False
        config.youtube_cookies_download_count = 0
        config.youtube_cookies_refreshed_at = datetime.now(timezone.utc)
    if payload.backup is not None:
        config.youtube_cookies_backup_runtime_expired = False

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Return fresh health status after save
    primary_status = "missing"
    backup_status = "missing"

    if config.youtube_cookies_encrypted:
        try:
            decrypted = decrypt_token(config.youtube_cookies_encrypted)
            primary_status = _check_cookie_health(decrypted)
        except Exception:
            primary_status = "missing"

    if config.youtube_cookies_backup_encrypted:
        try:
            decrypted = decrypt_token(config.youtube_cookies_backup_encrypted)
            backup_status = _check_cookie_health(decrypted)
        except Exception:
            backup_status = "missing"

    # Apply runtime_expired override per slot (same logic as GET)
    if config.youtube_cookies_runtime_expired and primary_status != "missing":
        primary_status = "expired"
    if config.youtube_cookies_backup_runtime_expired and backup_status != "missing":
        backup_status = "expired"

    return CookieHealthResponse(
        primary=CookieSlotHealth(status=primary_status),
        backup=CookieSlotHealth(status=backup_status),
    )


# ---------------------------------------------------------------------------
# Proxy config endpoints (PROXY-05)
# ---------------------------------------------------------------------------

@router.get("/proxy-config", response_model=ProxyConfigResponse)
async def get_proxy_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return proxy config state (enabled flag + masked URL).

    Security (T-21-01): Response model never includes plaintext proxy URL.
    Only proxy_url_masked (bullet-obfuscated) is exposed.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    proxy_enabled = False
    masked_url = None

    if config:
        proxy_enabled = config.proxy_enabled
        if config.proxy_url_encrypted:
            try:
                decrypted = decrypt_token(config.proxy_url_encrypted)
                masked_url = _mask_proxy_url(decrypted)
            except Exception:
                masked_url = "[URL configured]"

    return ProxyConfigResponse(proxy_enabled=proxy_enabled, proxy_url_masked=masked_url)


@router.put("/proxy-config", response_model=ProxyConfigResponse)
async def update_proxy_config(
    payload: UpdateProxyConfigRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update proxy enabled flag and/or encrypted URL (partial update supported).

    Security (T-21-02): proxy_url is encrypted before storage and NEVER logged.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    if payload.proxy_enabled is not None:
        config.proxy_enabled = payload.proxy_enabled
        logger.info(f"SuperAdmin toggled proxy: {payload.proxy_enabled}")

    if payload.proxy_url is not None:
        config.proxy_url_encrypted = encrypt_token(payload.proxy_url)
        logger.info("SuperAdmin updated proxy URL (credentials not logged)")

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Return fresh state
    proxy_enabled = config.proxy_enabled
    masked_url = None
    if config.proxy_url_encrypted:
        try:
            decrypted = decrypt_token(config.proxy_url_encrypted)
            masked_url = _mask_proxy_url(decrypted)
        except Exception:
            masked_url = "[URL configured]"

    return ProxyConfigResponse(proxy_enabled=proxy_enabled, proxy_url_masked=masked_url)


@router.post("/proxy-config/test", response_model=ProxyTestResponse)
async def test_proxy_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Test proxy reachability by fetching https://www.youtube.com/ through configured proxy.

    Security (T-21-05): 5-second hard timeout prevents unbounded waits.
    Security (T-21-06): Error messages never include the decrypted proxy URL.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config or not config.proxy_enabled or not config.proxy_url_encrypted:
        raise HTTPException(status_code=400, detail="Proxy not configured or disabled")

    try:
        proxy_url = decrypt_token(config.proxy_url_encrypted)
    except Exception:
        return ProxyTestResponse(success=False, error="Failed to decrypt proxy URL")

    try:
        start = time.time()
        async with httpx.AsyncClient(proxies=proxy_url) as client:
            response = await client.get("https://www.youtube.com/", timeout=5.0)
        latency_ms = int((time.time() - start) * 1000)
        success = response.status_code == 200
        return ProxyTestResponse(
            success=success,
            latency_ms=latency_ms if success else None,
            error=None if success else f"HTTP {response.status_code}",
        )
    except httpx.ConnectError:
        return ProxyTestResponse(success=False, latency_ms=None, error="Connection timed out after 5s")
    except Exception as e:
        return ProxyTestResponse(success=False, latency_ms=None, error=str(e))


@router.get("/users", response_model=List[SuperAdminUserResponse])
async def get_superadmin_users(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """List all active SuperAdmin users."""
    result = await db.execute(
        select(User)
        .where(User.is_superuser == True, User.is_active == True)  # noqa: E712
        .order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        SuperAdminUserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users/promote", response_model=SuperAdminUserResponse)
async def promote_user(
    payload: PromoteRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Promote a user to SuperAdmin by email address.

    Security (T-14-08): Only existing SuperAdmins can call this endpoint.
    Returns 404 if user not found, 409 if already SuperAdmin.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_superuser:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a SuperAdmin")

    user.is_superuser = True
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("User %s promoted to SuperAdmin by %s", user.email, current_user.email)

    return SuperAdminUserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
    )


@router.get("/organizations", response_model=List[OrgListItem])
async def get_organizations(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations with active user counts (read-only)."""
    user_count_subq = (
        select(func.count(User.id))
        .where(User.organization_id == Organization.id, User.is_active == True)  # noqa: E712
        .correlate(Organization)
        .scalar_subquery()
    )
    result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            Organization.slug,
            user_count_subq.label("user_count"),
            Organization.created_at,
        ).order_by(Organization.name)
    )
    rows = result.all()
    return [
        OrgListItem(
            id=str(row.id),
            name=row.name,
            slug=row.slug,
            user_count=row.user_count or 0,
            created_at=row.created_at,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Scoring controls — Pydantic models
# ---------------------------------------------------------------------------

class ScoringOrgStats(BaseModel):
    org_id: str
    org_name: str
    quota: Optional[int]
    scored_count: int
    pending_count: int


class ScoringConfigResponse(BaseModel):
    scoring_enabled: bool
    organizations: List[ScoringOrgStats]


class UpdateScoringConfigRequest(BaseModel):
    scoring_enabled: bool


class UpdateOrgQuotaRequest(BaseModel):
    quota: Optional[int] = None


class ResetScoringRequest(BaseModel):
    statuses: List[str] = ["FAILED"]


class ResetScoringResponse(BaseModel):
    reset_count: int


# ---------------------------------------------------------------------------
# Scoring controls — Endpoints
# ---------------------------------------------------------------------------

_ALLOWED_RESET_STATUSES = {"FAILED", "COMPLETE", "PROCESSING", "PENDING"}


@router.get("/scoring/config", response_model=ScoringConfigResponse)
async def get_scoring_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return global scoring toggle and per-org scoring stats (quota + counts)."""
    cfg_result = await db.execute(select(SystemConfig).limit(1))
    system_cfg = cfg_result.scalar_one_or_none()
    scoring_enabled = system_cfg.scoring_enabled if system_cfg is not None else True

    # Fetch all orgs with their brainsuite config quota
    orgs_result = await db.execute(
        select(Organization.id, Organization.name, OrgBrainsuiteConfig.scoring_quota)
        .outerjoin(OrgBrainsuiteConfig, OrgBrainsuiteConfig.organization_id == Organization.id)
        .order_by(Organization.name)
    )
    org_rows = orgs_result.all()

    # Fetch scored counts per org (COMPLETE)
    scored_result = await db.execute(
        select(CreativeScoreResult.organization_id, func.count(CreativeScoreResult.id))
        .where(CreativeScoreResult.scoring_status == "COMPLETE")
        .group_by(CreativeScoreResult.organization_id)
    )
    scored_by_org = {str(row[0]): row[1] for row in scored_result.all()}

    # Fetch pending counts per org (PENDING + PROCESSING)
    pending_result = await db.execute(
        select(CreativeScoreResult.organization_id, func.count(CreativeScoreResult.id))
        .where(CreativeScoreResult.scoring_status.in_(["PENDING", "PROCESSING"]))
        .group_by(CreativeScoreResult.organization_id)
    )
    pending_by_org = {str(row[0]): row[1] for row in pending_result.all()}

    organizations = [
        ScoringOrgStats(
            org_id=str(row.id),
            org_name=row.name,
            quota=row.scoring_quota,
            scored_count=scored_by_org.get(str(row.id), 0),
            pending_count=pending_by_org.get(str(row.id), 0),
        )
        for row in org_rows
    ]

    return ScoringConfigResponse(scoring_enabled=scoring_enabled, organizations=organizations)


@router.put("/scoring/config", response_model=ScoringConfigResponse)
async def update_scoring_config(
    payload: UpdateScoringConfigRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update global auto-scoring toggle.

    Sets SystemConfig.scoring_enabled. When False, run_scoring_batch() returns
    immediately without processing any assets.
    """
    cfg_result = await db.execute(select(SystemConfig).limit(1))
    system_cfg = cfg_result.scalar_one_or_none()
    if system_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    system_cfg.scoring_enabled = payload.scoring_enabled
    db.add(system_cfg)
    await db.commit()

    logger.info(
        "SuperAdmin %s set scoring_enabled=%s",
        current_user.email,
        payload.scoring_enabled,
    )

    # Return refreshed config view (re-use GET logic)
    return await get_scoring_config(current_user=current_user, db=db)


@router.put("/scoring/orgs/{org_id}/quota", response_model=ScoringOrgStats)
async def update_org_scoring_quota(
    org_id: uuid.UUID,
    payload: UpdateOrgQuotaRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Set or clear the per-org scoring quota.

    quota=null removes the cap (unlimited).
    Returns 404 if the org has no BrainSuite config row.
    """
    cfg_result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == org_id
        )
    )
    org_cfg = cfg_result.scalar_one_or_none()
    if org_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No BrainSuite config found for this organization",
        )

    org_cfg.scoring_quota = payload.quota
    db.add(org_cfg)
    await db.commit()

    logger.info(
        "SuperAdmin %s set scoring_quota=%s for org %s",
        current_user.email,
        payload.quota,
        org_id,
    )

    # Fetch org name for response
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()

    scored_result = await db.execute(
        select(func.count(CreativeScoreResult.id))
        .where(CreativeScoreResult.organization_id == org_id, CreativeScoreResult.scoring_status == "COMPLETE")
    )
    scored_count = scored_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(CreativeScoreResult.id))
        .where(CreativeScoreResult.organization_id == org_id, CreativeScoreResult.scoring_status.in_(["PENDING", "PROCESSING"]))
    )
    pending_count = pending_result.scalar() or 0

    return ScoringOrgStats(
        org_id=str(org_id),
        org_name=org.name if org else str(org_id),
        quota=org_cfg.scoring_quota,
        scored_count=scored_count,
        pending_count=pending_count,
    )


@router.post("/scoring/orgs/{org_id}/reset", response_model=ResetScoringResponse)
async def reset_org_scoring(
    org_id: uuid.UUID,
    payload: ResetScoringRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Reset scoring for specified statuses back to UNSCORED.

    Allowed statuses: FAILED, COMPLETE, PROCESSING, PENDING.
    Clears: total_score, total_rating, score_dimensions, scored_at, error_reason, brainsuite_job_id.
    """
    # Validate requested statuses — reject any unknown values
    invalid = [s for s in payload.statuses if s not in _ALLOWED_RESET_STATUSES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid statuses: {invalid}. Allowed values: FAILED, COMPLETE, PROCESSING, PENDING.",
        )

    if not payload.statuses:
        return ResetScoringResponse(reset_count=0)

    # Find matching rows first so we can return the count
    count_result = await db.execute(
        select(func.count(CreativeScoreResult.id)).where(
            CreativeScoreResult.organization_id == org_id,
            CreativeScoreResult.scoring_status.in_(payload.statuses),
        )
    )
    reset_count = count_result.scalar() or 0

    if reset_count > 0:
        await db.execute(
            update(CreativeScoreResult)
            .where(
                CreativeScoreResult.organization_id == org_id,
                CreativeScoreResult.scoring_status.in_(payload.statuses),
            )
            .values(
                scoring_status="UNSCORED",
                total_score=None,
                total_rating=None,
                score_dimensions=None,
                scored_at=None,
                error_reason=None,
                brainsuite_job_id=None,
            )
        )
        await db.commit()

    logger.info(
        "SuperAdmin %s reset %d assets to UNSCORED for org %s (statuses=%s)",
        current_user.email,
        reset_count,
        org_id,
        payload.statuses,
    )

    return ResetScoringResponse(reset_count=reset_count)


# ===== Download concurrency config endpoints (PERF-02) =====

@router.get("/download-concurrency", response_model=ConcurrencyConfigResponse)
async def get_download_concurrency(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return current max_concurrent_downloads setting."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    return ConcurrencyConfigResponse(max_concurrent_downloads=config.max_concurrent_downloads or 3)


@router.put("/download-concurrency", response_model=ConcurrencyConfigResponse)
async def update_download_concurrency(
    payload: ConcurrencyConfigRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update max_concurrent_downloads setting (range 1–10).

    Pydantic Field(ge=1, le=10) rejects out-of-range values before the handler body runs.
    Changes take effect within 60 seconds (cache TTL). No explicit cache invalidation (D-04/D-05).
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    config.max_concurrent_downloads = payload.max_concurrent_downloads
    db.add(config)
    await db.commit()
    await db.refresh(config)

    logger.info(
        "SuperAdmin %s set max_concurrent_downloads=%s",
        current_user.email,
        payload.max_concurrent_downloads,
    )

    return ConcurrencyConfigResponse(max_concurrent_downloads=config.max_concurrent_downloads)
