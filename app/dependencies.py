from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import AsyncSessionLocal, get_db


async def get_redis() -> AsyncGenerator[Redis, None]:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


__all__ = [
    "AsyncSessionLocal",
    "get_db",
    "get_current_user",
    "get_current_admin_user",
    "get_redis",
    "get_settings",
    "Settings",
    "AsyncSession",
]
