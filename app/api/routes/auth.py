import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_api_key,
    hash_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.config import Settings, get_settings
from app.db.models import ApiKey, RefreshToken as RefreshTokenModel, User
from app.db.session import get_db
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyCreated,
    RefreshToken,
    Token,
    UserLogin,
    UserRegister,
)
from app.schemas.users import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


async def _persist_refresh_token(
    db: AsyncSession,
    *,
    user_id: UUID,
    refresh_token: str,
    settings: Settings,
) -> None:
    token_row = RefreshTokenModel(
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_expire_days),
        revoked_at=None,
    )
    db.add(token_row)
    await db.commit()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    settings = get_settings()
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_admin=False,
        llm_provider=settings.default_llm_provider,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/token", response_model=Token)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Token:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    access = create_access_token(subject=str(user.id), settings=settings)
    refresh = create_refresh_token(subject=str(user.id), settings=settings)
    await _persist_refresh_token(db, user_id=user.id, refresh_token=refresh, settings=settings)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    body: RefreshToken,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Token:
    sub = verify_token(body.refresh_token, settings, token_type="refresh")
    token_hash = hash_refresh_token(body.refresh_token)
    token_row_result = await db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
    )
    token_row = token_row_result.scalar_one_or_none()
    now = datetime.now(tz=UTC)
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid")
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if token_row.revoked_at is not None or expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid")

    token_row.revoked_at = now
    access = create_access_token(subject=sub, settings=settings)
    refresh = create_refresh_token(subject=sub, settings=settings)
    token_row_new = RefreshTokenModel(
        user_id=token_row.user_id,
        token_hash=hash_refresh_token(refresh),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        revoked_at=None,
    )
    db.add(token_row_new)
    await db.commit()
    return Token(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshToken,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    token_hash = hash_refresh_token(body.refresh_token)
    token_row_result = await db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
    )
    token_row = token_row_result.scalar_one_or_none()
    if token_row is None:
        return
    if token_row.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke another user's token")
    if token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(tz=UTC)
        await db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == current.id,
            RefreshTokenModel.revoked_at.is_(None),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return
    now = datetime.now(tz=UTC)
    for row in rows:
        row.revoked_at = now
    await db.commit()


@router.post("/api-keys", response_model=ApiKeyCreated)
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ApiKeyCreated:
    raw_key = f"svet_{secrets.token_urlsafe(32)}"
    api_key = ApiKey(
        user_id=current.id,
        key_hash=hash_api_key(raw_key),
        name=payload.name,
        expires_at=payload.expires_at,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        key=raw_key,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current.id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = False
    await db.commit()
