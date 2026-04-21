from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
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
from app.models.metadata import MetadataField, MetadataFieldValue
from app.schemas.user import (
    LoginRequest, TokenResponse, UserCreate, UserResponse,
    RefreshRequest, SlugCheckResponse,
)
from typing import Optional
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

        # Seed all default metadata fields for new org
        _LANGUAGES = [
            ("ar", "Arabic"), ("bg", "Bulgarian"), ("cs", "Czech"), ("da", "Danish"),
            ("de", "German"), ("el", "Greek"), ("en", "English"), ("es", "Spanish"),
            ("fi", "Finnish"), ("fr", "French"), ("he", "Hebrew"), ("hi", "Hindi"),
            ("hr", "Croatian"), ("hu", "Hungarian"), ("id", "Indonesian"), ("it", "Italian"),
            ("ja", "Japanese"), ("ko", "Korean"), ("ms", "Malay"), ("nl", "Dutch"),
            ("no", "Norwegian"), ("pl", "Polish"), ("pt", "Portuguese"), ("ro", "Romanian"),
            ("sk", "Slovak"), ("sl", "Slovenian"), ("sv", "Swedish"), ("th", "Thai"),
            ("tr", "Turkish"), ("vi", "Vietnamese"), ("zh", "Chinese"),
        ]

        # Simple text/select fields with no child values
        for name, label, ftype, required, default, sort in [
            ("brainsuite_brand_names",        "Brand Names",       "TEXT",   True,  None,             1),
            ("brainsuite_project_name",        "Project Name",      "TEXT",   False, "Spring Campaign 2026", 3),
            ("brainsuite_asset_name",          "Asset Name",        "TEXT",   False, None,             4),
            ("brainsuite_voice_over",          "Voice Over",        "TEXT",   False, None,             6),
            ("brainsuite_intended_messages",   "Intended Messages", "TEXT",   False, None,             8),
            ("brainsuite_brand_values",        "Brand Values",      "TEXT",   False, None,            10),
        ]:
            db.add(MetadataField(
                organization_id=org_id, name=name, label=label, field_type=ftype,
                is_required=required, default_value=default, is_active=True, sort_order=sort,
            ))

        # SELECT fields that need child values — flush each to get its id
        asset_lang_field = MetadataField(
            organization_id=org_id, name="brainsuite_asset_language", label="Asset Language",
            field_type="SELECT", is_required=True, default_value=None, is_active=True, sort_order=2,
        )
        db.add(asset_lang_field)

        asset_stage_field = MetadataField(
            organization_id=org_id, name="brainsuite_asset_stage", label="Asset Stage",
            field_type="SELECT", is_required=False, default_value="finalVersion", is_active=True, sort_order=5,
        )
        db.add(asset_stage_field)

        vo_lang_field = MetadataField(
            organization_id=org_id, name="brainsuite_voice_over_language", label="Voice Over Language",
            field_type="SELECT", is_required=False, default_value=None, is_active=True, sort_order=7,
        )
        db.add(vo_lang_field)

        iconic_color_field = MetadataField(
            organization_id=org_id, name="brainsuite_iconic_color_scheme", label="Iconic Color Scheme",
            field_type="SELECT", is_required=False, default_value="manufactory", is_active=True, sort_order=9,
        )
        db.add(iconic_color_field)

        brand_values_lang_field = MetadataField(
            organization_id=org_id, name="brainsuite_brand_values_language", label="Brand Values Language",
            field_type="SELECT", is_required=False, default_value=None, is_active=True, sort_order=11,
        )
        db.add(brand_values_lang_field)

        intended_messages_lang_field = MetadataField(
            organization_id=org_id, name="brainsuite_intended_messages_language", label="Intended Messages Language",
            field_type="SELECT", is_required=False, default_value=None, is_active=True, sort_order=12,
        )
        db.add(intended_messages_lang_field)

        await db.flush()

        for idx, (val, lbl) in enumerate(_LANGUAGES):
            db.add(MetadataFieldValue(field_id=asset_lang_field.id, value=val, label=lbl, sort_order=idx))
            db.add(MetadataFieldValue(field_id=vo_lang_field.id, value=val, label=lbl, sort_order=idx))
            db.add(MetadataFieldValue(field_id=brand_values_lang_field.id, value=val, label=lbl, sort_order=idx))
            db.add(MetadataFieldValue(field_id=intended_messages_lang_field.id, value=val, label=lbl, sort_order=idx))

        for val, lbl, sort in [("firstVersion", "First Version", 1), ("iteration", "Iteration", 2), ("finalVersion", "Final Version", 3)]:
            db.add(MetadataFieldValue(field_id=asset_stage_field.id, value=val, label=lbl, sort_order=sort))

        db.add(MetadataFieldValue(field_id=iconic_color_field.id, value="manufactory", label="Manufactory", sort_order=0))

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
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
        import pyotp
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(payload.totp_code):
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    user.last_login = datetime.now(timezone.utc)
    db.add(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.commit()

    # Set refresh token as httpOnly cookie (not in response body)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_data = decode_token(refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
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
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)
    await db.commit()

    # Rotate: issue new httpOnly cookie with the new refresh token
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(access_token=new_access)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()
        if stored:
            stored.is_revoked = True
            db.add(stored)
            await db.commit()

    # Clear the httpOnly cookie
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import Organization
    org = await db.get(Organization, current_user.organization_id) if current_user.organization_id else None
    user_data = UserResponse.model_validate(current_user).model_dump()
    user_data["organization_currency"] = org.currency if org else "USD"
    return user_data
