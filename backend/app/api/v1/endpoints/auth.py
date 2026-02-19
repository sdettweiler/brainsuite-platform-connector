from datetime import datetime, timedelta
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import hashlib
import uuid

from app.db.base import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.config import settings
from app.models.user import User, Organization, OrganizationRole, RefreshToken, OrganizationJoinRequest, Notification
from app.schemas.user import (
    LoginRequest, TokenResponse, UserCreate, UserResponse,
    RefreshRequest, SlugCheckResponse,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


def generate_slug(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'org'


@router.get("/check-slug/{slug}", response_model=SlugCheckResponse)
async def check_slug(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).where(Organization.slug == slug.lower()))
    org = result.scalar_one_or_none()
    return SlugCheckResponse(available=org is None, slug=slug.lower())


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org_action = payload.org_action or "create"
    org_id = payload.organization_id
    is_pending_join = False

    if org_action == "join" and payload.org_slug:
        result = await db.execute(
            select(Organization).where(Organization.slug == payload.org_slug.lower())
        )
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found. Please check the slug and try again.")
        org_id = org.id
        is_pending_join = True

    elif org_action == "create":
        org_name = payload.org_name or f"{payload.first_name or payload.email}'s Organization"
        org_currency = payload.org_currency or "USD"
        slug = generate_slug(org_name)

        existing_slug = await db.execute(select(Organization).where(Organization.slug == slug))
        if existing_slug.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(name=org_name, slug=slug, currency=org_currency)
        db.add(org)
        await db.flush()
        org_id = org.id

    elif not org_id:
        slug = payload.email.split("@")[0].lower().replace(".", "-") + "-org"
        org = Organization(
            name=f"{payload.first_name or payload.email}'s Organization",
            slug=slug,
            currency="USD",
        )
        db.add(org)
        await db.flush()
        org_id = org.id

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        business_unit=payload.business_unit,
        language=payload.language,
        organization_id=org_id,
        is_active=not is_pending_join,
    )
    db.add(user)
    await db.flush()

    if is_pending_join:
        join_req = OrganizationJoinRequest(
            organization_id=org_id,
            user_id=user.id,
            status="PENDING",
        )
        db.add(join_req)

        role = OrganizationRole(
            organization_id=org_id,
            user_id=user.id,
            role="STANDARD",
            permissions={},
        )
        db.add(role)

        admin_roles = await db.execute(
            select(OrganizationRole).where(
                OrganizationRole.organization_id == org_id,
                OrganizationRole.role == "ADMIN",
            )
        )
        for admin_role in admin_roles.scalars().all():
            notif = Notification(
                user_id=admin_role.user_id,
                type="JOIN_REQUEST",
                title="New Join Request",
                message=f"{user.full_name} ({user.email}) wants to join your organization.",
                data={"join_request_id": str(join_req.id), "user_id": str(user.id)},
            )
            db.add(notif)
    else:
        role = OrganizationRole(
            organization_id=org_id,
            user_id=user.id,
            role="ADMIN",
            permissions={},
        )
        db.add(role)

        from app.models.platform import BrainsuiteApp
        video_app = BrainsuiteApp(
            organization_id=org_id,
            name="Social Media Video",
            description="Brainsuite app for video creatives",
            app_type="VIDEO",
            is_default_for_video=True,
            is_default_for_image=False,
        )
        image_app = BrainsuiteApp(
            organization_id=org_id,
            name="Social Media Static",
            description="Brainsuite app for static/image creatives",
            app_type="IMAGE",
            is_default_for_video=False,
            is_default_for_image=True,
        )
        db.add(video_app)
        db.add(image_app)

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        pending = await db.execute(
            select(OrganizationJoinRequest).where(
                OrganizationJoinRequest.user_id == user.id,
                OrganizationJoinRequest.status == "PENDING",
            )
        )
        if pending.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Your request to join this organization is pending admin approval."
            )
        raise HTTPException(status_code=403, detail="Account disabled")

    if user.is_two_factor_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=400, detail="2FA code required")

    user.last_login = datetime.utcnow()
    db.add(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    from datetime import timezone
    now = datetime.now(timezone.utc)
    expires_at = stored.expires_at if stored.expires_at.tzinfo else stored.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    stored.is_revoked = True
    db.add(stored)

    user_id = token_data.get("sub")
    new_access = create_access_token({"sub": user_id})
    new_refresh = create_refresh_token({"sub": user_id})

    new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
    new_rt = RefreshToken(
        user_id=stored.user_id,
        token_hash=new_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.is_revoked = True
        db.add(stored)
        await db.commit()
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
