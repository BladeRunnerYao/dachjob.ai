from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: UUID
    email: str
    name: str
    tenant_id: UUID | None = None
    password_needs_reset: bool = False


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str

    model_config = {"from_attributes": True}


class GoogleLoginRequest(BaseModel):
    code: str
    redirect_uri: str


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    prefix: str
    raw_key: str | None = None
    created_by: str | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyListItem(BaseModel):
    id: UUID
    name: str
    prefix: str
    created_by: str | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
