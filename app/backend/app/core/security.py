from datetime import datetime, timedelta, timezone
import re
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[a-zA-Z]", password):
        errors.append("Password must contain at least one letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number")
    if not re.search(r"[^a-zA-Z0-9]", password):
        errors.append("Password must contain at least one special character")
    return errors


def create_access_token(user_id: UUID, email: str, tenant_id: UUID | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def create_reset_token(user_id: UUID, email: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "scope": "password_reset",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_reset_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "password_reset":
            return None
        return payload
    except JWTError:
        return None
