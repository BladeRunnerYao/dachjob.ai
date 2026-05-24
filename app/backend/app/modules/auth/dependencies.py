from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import validate_bearer_token
from app.db.models import Tenant, User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_tenant_slug: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Tenant]:
    return await validate_bearer_token(credentials, db, tenant_slug=x_tenant_slug)
