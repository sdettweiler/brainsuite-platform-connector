from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
import uuid

from app.db.base import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.config import settings
from app.models.user import User, Organization, OrganizationRole, RefreshToken
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse, RefreshRequest
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create org if not provided
    org_id = payload.organization_id
    if not org_id:
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
    )
    db.add(user)
    await db.flush()

    # Assign ADMIN role for first user in org
    role = OrganizationRole(
        organization_id=org_id,
        user_id=user.id,
        role="ADMIN",
        permissions={},
    )
    db.add(role)

    # Seed default Brainsuite Apps
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
        raise HTTPException(status_code=403, detail="Account disabled")

    # 2FA check (stub — verify TOTP if enabled)
    if user.is_two_factor_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=400, detail="2FA code required")
        # TODO: verify pyotp.TOTP(user.two_factor_secret).verify(payload.totp_code)

    # Update last login
    user.last_login = datetime.utcnow()
    db.add(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Store hashed refresh token
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

    # Rotate tokens
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
