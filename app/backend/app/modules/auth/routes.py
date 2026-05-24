from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import Membership, Tenant, User
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _get_default_tenant(db: AsyncSession) -> Tenant:
    slug = get_settings().default_tenant_slug
    result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(slug=slug, name="Default Workspace")
        db.add(tenant)
        await db.flush()
    return tenant


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    tenant = await _get_default_tenant(db)

    result = await db.execute(
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant.id,
        )
        .limit(1)
    )
    if not result.scalar_one_or_none():
        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="member",
        )
        db.add(membership)
        await db.flush()

    token = create_access_token(user.id, user.email, tenant.id)
    return AuthResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        tenant_id=tenant.id,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email).limit(1))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    tenant = await _get_default_tenant(db)

    result = await db.execute(
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant.id,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="member",
        )
        db.add(membership)
        await db.flush()

    token = create_access_token(user.id, user.email, tenant.id)
    return AuthResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        tenant_id=tenant.id,
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _tenant = current_user
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.post("/google", response_model=AuthResponse)
async def google_login(
    body: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=400, detail="Google login not configured")

    import httpx

    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "code": body.code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": body.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange Google code")

        tokens = resp.json()
        access_token = tokens.get("access_token")

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Google user info")

        google_user = userinfo_resp.json()
        google_id = google_user["id"]
        email = google_user["email"]
        name = google_user.get("name", email.split("@")[0])

    result = await db.execute(
        select(User).where((User.google_id == google_id) | (User.email == email)).limit(1)
    )
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
    else:
        user = User(
            email=email,
            name=name,
            google_id=google_id,
        )
        db.add(user)
        await db.flush()

    tenant = await _get_default_tenant(db)

    result = await db.execute(
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant.id,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="member",
        )
        db.add(membership)
        await db.flush()

    token = create_access_token(user.id, user.email, tenant.id)
    return AuthResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        tenant_id=tenant.id,
    )
