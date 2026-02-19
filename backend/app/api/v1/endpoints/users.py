from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.base import get_db
from app.models.user import User, OrganizationRole, Organization
from app.schemas.user import UserResponse, UserUpdate, UserWithRole, RoleAssignment, OrganizationResponse, OrganizationUpdate
from app.api.v1.deps import get_current_user, get_current_admin
from app.core.security import get_password_hash

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/organization", response_model=OrganizationResponse)
async def get_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/organization", response_model=OrganizationResponse)
async def update_organization(
    payload: OrganizationUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("", response_model=list[UserWithRole])
async def list_users(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id)
    )
    users = result.scalars().all()

    users_with_roles = []
    for user in users:
        role_result = await db.execute(
            select(OrganizationRole).where(
                OrganizationRole.user_id == user.id,
                OrganizationRole.organization_id == current_user.organization_id,
            )
        )
        role = role_result.scalar_one_or_none()
        user_dict = UserWithRole.model_validate(user)
        user_dict.role = role.role if role else "READ_ONLY"
        users_with_roles.append(user_dict)

    return users_with_roles


@router.post("/invite", response_model=UserResponse, status_code=201)
async def invite_user(
    payload: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user in the same organization with a temporary password."""
    from app.schemas.user import UserCreate
    email = payload.get("email")
    role = payload.get("role", "STANDARD")
    temp_password = payload.get("password", "ChangeMe123!")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        email=email,
        password_hash=get_password_hash(temp_password),
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        organization_id=current_user.organization_id,
    )
    db.add(user)
    await db.flush()

    org_role = OrganizationRole(
        organization_id=current_user.organization_id,
        user_id=user.id,
        role=role,
    )
    db.add(org_role)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleAssignment,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationRole).where(
            OrganizationRole.user_id == user_id,
            OrganizationRole.organization_id == current_user.organization_id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="User not in organization")

    role.role = payload.role
    db.add(role)
    await db.commit()
    return {"detail": "Role updated"}


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user (e.g. toggle is_active)."""
    user = await db.get(User, user_id)
    if not user or user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="User not found")

    allowed = {"is_active", "first_name", "last_name"}
    for field, value in payload.items():
        if field in allowed:
            setattr(user, field, value)
    db.add(user)
    await db.commit()
    return {"detail": "User updated"}


@router.delete("/{user_id}")
async def remove_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(OrganizationRole).where(
            OrganizationRole.user_id == user_id,
            OrganizationRole.organization_id == current_user.organization_id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="User not in organization")

    await db.delete(role)
    # Deactivate user
    user = await db.get(User, user_id)
    if user:
        user.is_active = False
        db.add(user)

    await db.commit()
    return {"detail": "User removed from organization"}
