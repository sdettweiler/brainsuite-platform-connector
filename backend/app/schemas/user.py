from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
import uuid


class OrganizationBase(BaseModel):
    name: str
    currency: str = "USD"


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None


class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    business_unit: Optional[str] = None
    language: str = "en"


class UserCreate(UserBase):
    password: str
    organization_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    business_unit: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    organization_id: Optional[uuid.UUID]
    last_login: Optional[datetime]
    created_at: datetime
    full_name: str

    class Config:
        from_attributes = True


class UserWithRole(UserResponse):
    role: Optional[str] = None


class RoleAssignment(BaseModel):
    user_id: uuid.UUID
    role: str  # ADMIN, STANDARD, READ_ONLY


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
