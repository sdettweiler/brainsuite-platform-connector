"""
Platform connection management endpoints.
Handles OAuth flows, account listing, connection CRUD, and manual re-fetch.
"""
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.platform import PlatformConnection, BrainsuiteApp
from app.schemas.platform import (
    PlatformConnectionResponse, BrainsuiteAppCreate, BrainsuiteAppUpdate,
    BrainsuiteAppResponse, OAuthInitRequest, OAuthCallbackRequest,
    OAuthAuthorizedAccount, AdAccountSelectionRequest,
)
from app.api.v1.deps import get_current_user, get_current_admin
from app.core.security import encrypt_token, decrypt_token
from app.core.config import settings

router = APIRouter()

# In-memory OAuth session store (replace with Redis in production)
_oauth_sessions: dict = {}


# ─── Brainsuite Apps ───────────────────────────────────────────────────────────

@router.get("/apps", response_model=List[BrainsuiteAppResponse])
async def list_brainsuite_apps(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BrainsuiteApp).where(
            BrainsuiteApp.organization_id == current_user.organization_id,
            BrainsuiteApp.is_active == True,
        )
    )
    return result.scalars().all()


@router.post("/apps", response_model=BrainsuiteAppResponse, status_code=201)
async def create_brainsuite_app(
    payload: BrainsuiteAppCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = BrainsuiteApp(
        organization_id=current_user.organization_id,
        **payload.model_dump(),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.patch("/apps/{app_id}", response_model=BrainsuiteAppResponse)
async def update_brainsuite_app(
    app_id: uuid.UUID,
    payload: BrainsuiteAppUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/apps/{app_id}")
async def delete_brainsuite_app(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    app.is_active = False
    db.add(app)
    await db.commit()
    return {"detail": "App deleted"}


# Alias /brainsuite-apps to /apps for frontend convenience
@router.get("/brainsuite-apps", response_model=List[BrainsuiteAppResponse])
async def list_brainsuite_apps_alias(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BrainsuiteApp).where(
            BrainsuiteApp.organization_id == current_user.organization_id,
            BrainsuiteApp.is_active == True,
        )
    )
    return result.scalars().all()


@router.post("/brainsuite-apps", response_model=BrainsuiteAppResponse, status_code=201)
async def create_brainsuite_app_alias(
    payload: BrainsuiteAppCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = BrainsuiteApp(
        organization_id=current_user.organization_id,
        **payload.model_dump(),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.patch("/brainsuite-apps/{app_id}", response_model=BrainsuiteAppResponse)
async def update_brainsuite_app_alias(
    app_id: uuid.UUID,
    payload: BrainsuiteAppUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/brainsuite-apps/{app_id}")
async def delete_brainsuite_app_alias(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    app.is_active = False
    db.add(app)
    await db.commit()
    return {"detail": "App deleted"}


# ─── OAuth Flow ───────────────────────────────────────────────────────────────

@router.post("/oauth/init")
async def init_oauth(
    payload: OAuthInitRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate OAuth authorization URL for a platform."""
    from app.services.platform.meta_oauth import meta_oauth
    from app.services.platform.tiktok_oauth import tiktok_oauth
    from app.services.platform.google_ads_oauth import google_ads_oauth

    session_id = secrets.token_urlsafe(32)

    if not settings.META_APP_ID and payload.platform == "META":
        raise HTTPException(status_code=503, detail="Meta app credentials not configured")
    if not settings.TIKTOK_APP_ID and payload.platform == "TIKTOK":
        raise HTTPException(status_code=503, detail="TikTok app credentials not configured")
    if not settings.GOOGLE_CLIENT_ID and payload.platform == "GOOGLE_ADS":
        raise HTTPException(status_code=503, detail="Google app credentials not configured")

    _oauth_sessions[session_id] = {
        "platform": payload.platform,
        "user_id": str(current_user.id),
        "org_id": str(current_user.organization_id),
        "created_at": datetime.utcnow().isoformat(),
    }

    if payload.platform == "META":
        auth_url = meta_oauth.generate_auth_url(session_id)
    elif payload.platform == "TIKTOK":
        auth_url = tiktok_oauth.generate_auth_url(session_id)
    elif payload.platform == "GOOGLE_ADS":
        auth_url = google_ads_oauth.generate_auth_url(session_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown platform")

    return {"auth_url": auth_url, "session_id": session_id}


@router.post("/oauth/callback")
async def oauth_callback(
    payload: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
):
    """Exchange OAuth code for token and fetch available ad accounts."""
    from app.services.platform.meta_oauth import meta_oauth
    from app.services.platform.tiktok_oauth import tiktok_oauth
    from app.services.platform.google_ads_oauth import google_ads_oauth

    session_id = payload.state  # state doubles as session_id
    session = _oauth_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Invalid OAuth session")

    if session.get("platform") != payload.platform:
        raise HTTPException(status_code=400, detail="Platform mismatch")

    try:
        if payload.platform == "META":
            tokens = await meta_oauth.exchange_code_for_token(payload.code)
            accounts = await meta_oauth.fetch_ad_accounts(tokens["access_token"])
        elif payload.platform == "TIKTOK":
            tokens = await tiktok_oauth.exchange_code_for_token(payload.code)
            accounts = await tiktok_oauth.fetch_advertiser_accounts(tokens["access_token"])
        elif payload.platform == "GOOGLE_ADS":
            tokens = await google_ads_oauth.exchange_code_for_token(payload.code)
            accounts = await google_ads_oauth.fetch_accessible_customers(tokens["access_token"])
        else:
            raise HTTPException(status_code=400, detail="Unknown platform")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")

    # Store tokens temporarily in session
    _oauth_sessions[session_id]["tokens"] = tokens
    _oauth_sessions[session_id]["accounts"] = accounts

    return {
        "session_id": session_id,
        "platform": payload.platform,
        "accounts": accounts,
    }


@router.get("/oauth/session/{session_id}")
async def get_oauth_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll for OAuth session status after popup completes."""
    session = _oauth_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "session_id": session_id,
        "platform": session.get("platform"),
        "accounts": session.get("accounts", []),
        "ready": "accounts" in session,
    }


@router.post("/oauth/connect")
async def connect_accounts(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    After user selects which accounts to connect.
    Creates PlatformConnection records and kicks off initial sync.
    """
    from app.services.sync.scheduler import run_initial_sync, schedule_connection

    session_id = payload.get("session_id")
    session = _oauth_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="OAuth session expired")

    platform = session["platform"]
    tokens = session.get("tokens", {})
    # Support both account_ids list and selected_accounts objects
    account_ids = payload.get("account_ids", [])
    selected = payload.get("selected_accounts", [])

    # If account_ids provided, build selected from session accounts
    if account_ids and not selected:
        session_accounts = session.get("accounts", [])
        selected = [
            {"ad_account_id": a["id"], "ad_account_name": a.get("name", a["id"])}
            for a in session_accounts
            if a["id"] in account_ids
        ]

    connected = []

    for account_setup in selected:
        ad_account_id = account_setup.get("ad_account_id")
        ad_account_name = account_setup.get("ad_account_name")
        brainsuite_app_id = account_setup.get("brainsuite_app_id")
        default_metadata = account_setup.get("default_metadata_values", {})

        # Find account details from session
        accounts = session.get("accounts", [])
        account_info = next((a for a in accounts if a["id"] == ad_account_id), {})

        # Check for existing connection
        existing = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.organization_id == current_user.organization_id,
                PlatformConnection.platform == platform,
                PlatformConnection.ad_account_id == ad_account_id,
            )
        )
        existing_conn = existing.scalar_one_or_none()

        if existing_conn:
            # Reconnect — update tokens
            existing_conn.access_token_encrypted = encrypt_token(tokens.get("access_token", ""))
            if tokens.get("refresh_token"):
                existing_conn.refresh_token_encrypted = encrypt_token(tokens["refresh_token"])
            if tokens.get("expires_in"):
                existing_conn.token_expiry = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
            existing_conn.sync_status = "ACTIVE"
            db.add(existing_conn)
            conn = existing_conn
        else:
            # Create new connection
            conn = PlatformConnection(
                organization_id=current_user.organization_id,
                created_by_user_id=current_user.id,
                platform=platform,
                ad_account_id=ad_account_id,
                ad_account_name=ad_account_name,
                currency=account_info.get("currency", "USD"),
                timezone=account_info.get("timezone", "UTC"),
                access_token_encrypted=encrypt_token(tokens.get("access_token", "")),
                refresh_token_encrypted=encrypt_token(tokens.get("refresh_token", "")) if tokens.get("refresh_token") else None,
                token_expiry=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)) if tokens.get("expires_in") else None,
                brainsuite_app_id=uuid.UUID(brainsuite_app_id) if brainsuite_app_id else None,
                default_metadata_values=default_metadata,
                sync_status="ACTIVE",
            )
            db.add(conn)

        await db.flush()

        # Schedule daily sync
        schedule_connection(str(conn.id), conn.timezone or "UTC")

        # Trigger initial sync in background
        background_tasks.add_task(run_initial_sync, str(conn.id))

        connected.append(str(conn.id))

    await db.commit()

    # Clean up session
    del _oauth_sessions[session_id]

    return {
        "connected": connected,
        "message": f"Connected {len(connected)} account(s). Initial sync started.",
    }


# ─── OAuth Redirect URI handlers (called by platform after user auth) ─────────

from fastapi.responses import HTMLResponse

def _make_callback_html(session_id: str, success: bool, error: str = "") -> str:
    """Return HTML that posts a message to the opener and closes the popup."""
    if success:
        return f"""<html><body><script>
        window.opener && window.opener.postMessage({{type:"oauth_callback",session_id:"{session_id}"}}, "*");
        window.close();
        </script><p>Authentication successful. You can close this window.</p></body></html>"""
    return f"""<html><body><p>Authentication failed: {error}. Please close this window and try again.</p></body></html>"""


@router.get("/oauth/callback/{platform_key}", response_class=HTMLResponse)
async def platform_oauth_callback(
    platform_key: str,
    code: Optional[str] = None,
    auth_code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Redirect URI called by the platform after the user authorizes.
    Exchanges code for tokens and stores in session, then closes the popup.
    """
    from app.services.platform.meta_oauth import meta_oauth
    from app.services.platform.tiktok_oauth import tiktok_oauth
    from app.services.platform.google_ads_oauth import google_ads_oauth

    platform_map = {"meta": "META", "tiktok": "TIKTOK", "google": "GOOGLE_ADS"}
    platform = platform_map.get(platform_key.lower())

    if not platform or not state:
        return HTMLResponse(_make_callback_html("", False, error or "Invalid request"))

    session_id = state
    session = _oauth_sessions.get(session_id)
    if not session:
        return HTMLResponse(_make_callback_html(session_id, False, "Session expired"))

    if error:
        return HTMLResponse(_make_callback_html(session_id, False, error))

    effective_code = auth_code or code

    try:
        if platform == "META":
            tokens = await meta_oauth.exchange_code_for_token(effective_code)
            accounts = await meta_oauth.fetch_ad_accounts(tokens["access_token"])
        elif platform == "TIKTOK":
            tokens = await tiktok_oauth.exchange_code_for_token(effective_code)
            accounts = await tiktok_oauth.fetch_advertiser_accounts(tokens["access_token"])
        elif platform == "GOOGLE_ADS":
            tokens = await google_ads_oauth.exchange_code_for_token(effective_code)
            accounts = await google_ads_oauth.fetch_accessible_customers(tokens["access_token"])
        else:
            return HTMLResponse(_make_callback_html(session_id, False, "Unknown platform"))

        _oauth_sessions[session_id]["tokens"] = tokens
        _oauth_sessions[session_id]["accounts"] = accounts
        return HTMLResponse(_make_callback_html(session_id, True))

    except Exception as e:
        return HTMLResponse(_make_callback_html(session_id, False, str(e)))


# ─── Connection Management ────────────────────────────────────────────────────

@router.get("/connections")
async def list_connections(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(default="ad_account_name"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(PlatformConnection).where(
        PlatformConnection.organization_id == current_user.organization_id,
        PlatformConnection.is_active == True,
    )

    if platform:
        platforms_list = [p.strip().upper() for p in platform.split(",") if p.strip()]
        if platforms_list:
            base = base.where(PlatformConnection.platform.in_(platforms_list))

    if status:
        statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
        if statuses:
            base = base.where(PlatformConnection.sync_status.in_(statuses))

    if search:
        term = f"%{search}%"
        base = base.where(
            or_(
                PlatformConnection.ad_account_name.ilike(term),
                PlatformConnection.ad_account_id.ilike(term),
            )
        )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    status_counts_q = (
        select(
            PlatformConnection.sync_status,
            func.count().label("cnt"),
        )
        .where(
            PlatformConnection.organization_id == current_user.organization_id,
            PlatformConnection.is_active == True,
        )
        .group_by(PlatformConnection.sync_status)
    )
    status_rows = (await db.execute(status_counts_q)).all()
    status_summary = {r.sync_status: r.cnt for r in status_rows}

    sort_col_map = {
        "ad_account_name": PlatformConnection.ad_account_name,
        "name": PlatformConnection.ad_account_name,
        "platform": PlatformConnection.platform,
        "status": PlatformConnection.sync_status,
        "last_synced": PlatformConnection.last_synced_at,
        "currency": PlatformConnection.currency,
        "created": PlatformConnection.created_at,
    }
    col = sort_col_map.get(sort_by, PlatformConnection.ad_account_name)
    if sort_order.lower() == "desc":
        base = base.order_by(col.desc().nullslast())
    else:
        base = base.order_by(col.asc().nullsfirst())

    base = base.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(base)
    items = result.scalars().all()

    from app.schemas.platform import PlatformConnectionResponse
    return {
        "items": [PlatformConnectionResponse.model_validate(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_summary": status_summary,
    }


@router.patch("/connections/{connection_id}")
async def update_connection(
    connection_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update connection settings (e.g. brainsuite_app_id, default_metadata_values)."""
    conn = await db.get(PlatformConnection, connection_id)
    if not conn or conn.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    allowed = {"brainsuite_app_id", "brainsuite_app_id_image", "brainsuite_app_id_video", "default_metadata_values"}
    for field, value in payload.items():
        if field in allowed:
            if field in ("brainsuite_app_id", "brainsuite_app_id_image", "brainsuite_app_id_video"):
                setattr(conn, field, uuid.UUID(value) if value else None)
            else:
                setattr(conn, field, value)
    db.add(conn)
    await db.commit()
    return {"detail": "Connection updated"}


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(PlatformConnection, connection_id)
    if not conn or conn.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.is_active = False
    db.add(conn)

    from app.services.sync.scheduler import remove_connection_schedule
    remove_connection_schedule(str(connection_id))

    await db.commit()
    return {"detail": "Connection deactivated"}


@router.post("/connections/{connection_id}/resync")
async def manual_resync(
    connection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(PlatformConnection, connection_id)
    if not conn or conn.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    from app.services.sync.scheduler import run_initial_sync, run_historical_sync, run_daily_sync, run_full_resync
    if not conn.initial_sync_completed:
        background_tasks.add_task(run_initial_sync, str(connection_id))
        return {"detail": "Initial sync started (30-day fetch)"}
    elif not conn.historical_sync_completed:
        background_tasks.add_task(run_historical_sync, str(connection_id))
        return {"detail": "Historical sync started (24-month fetch)"}
    else:
        background_tasks.add_task(run_full_resync, str(connection_id))
        return {"detail": "Full resync started"}


@router.post("/connections/bulk-action")
async def bulk_action(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    action = payload.get("action")
    connection_ids = payload.get("connection_ids", [])
    extra = payload.get("payload", {})

    if not action or not connection_ids:
        raise HTTPException(status_code=400, detail="action and connection_ids required")

    uuids = [uuid.UUID(cid) for cid in connection_ids]
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.id.in_(uuids),
            PlatformConnection.organization_id == current_user.organization_id,
            PlatformConnection.is_active == True,
        )
    )
    conns = result.scalars().all()
    if not conns:
        raise HTTPException(status_code=404, detail="No matching connections found")

    affected = len(conns)

    if action == "resync":
        from app.services.sync.scheduler import run_full_resync, run_initial_sync, run_historical_sync
        for conn in conns:
            if not conn.initial_sync_completed:
                background_tasks.add_task(run_initial_sync, str(conn.id))
            elif not conn.historical_sync_completed:
                background_tasks.add_task(run_historical_sync, str(conn.id))
            else:
                background_tasks.add_task(run_full_resync, str(conn.id))

    elif action == "disconnect":
        from app.services.sync.scheduler import remove_connection_schedule
        for conn in conns:
            conn.is_active = False
            db.add(conn)
            remove_connection_schedule(str(conn.id))
        await db.commit()

    elif action in ("assign_image_app", "assign_video_app"):
        app_id = extra.get("app_id")
        field = "brainsuite_app_id_image" if action == "assign_image_app" else "brainsuite_app_id_video"
        for conn in conns:
            setattr(conn, field, uuid.UUID(app_id) if app_id else None)
            db.add(conn)
        await db.commit()

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    return {"detail": f"{action} applied to {affected} connection(s)", "affected": affected}


@router.get("/connections/{connection_id}/status")
async def connection_status(
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(PlatformConnection, connection_id)
    if not conn or conn.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {
        "id": str(conn.id),
        "sync_status": conn.sync_status,
        "last_synced_at": conn.last_synced_at,
        "initial_sync_completed": conn.initial_sync_completed,
        "historical_sync_completed": conn.historical_sync_completed,
    }
