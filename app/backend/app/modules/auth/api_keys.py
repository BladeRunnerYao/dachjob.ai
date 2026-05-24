from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext, _extract_prefix, generate_api_key, hash_api_key
from app.core.tenant import get_tenant_context
from app.db.models import ApiKey
from app.db.session import get_db
from app.modules.auth.schemas import ApiKeyCreateRequest, ApiKeyListItem, ApiKeyResponse

router = APIRouter(prefix="/api/auth/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    prefix = _extract_prefix(raw_key)
    api_key = ApiKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        prefix=prefix,
        name=body.name,
        is_active=1,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        raw_key=raw_key,
        created_by=api_key.created_by,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant.id, ApiKey.is_active == 1)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [ApiKeyListItem.model_validate(k) for k in keys]


class DeleteResponse(BaseModel):
    success: bool = True


@router.delete("/{key_id}", response_model=DeleteResponse)
async def revoke_api_key(
    key_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = 0
    await db.flush()
    return DeleteResponse()
