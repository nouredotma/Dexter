import time

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis

from app.api.middleware.auth import get_current_user
from app.dependencies import get_redis
from app.db.models import User


async def rate_limit(
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> None:
    requests_per_minute = 60
    window = int(time.time()) // 60
    key = f"ratelimit:user:{user.id}:{window}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)

    if count > requests_per_minute:
        ttl = await redis.ttl(key)
        retry_after = ttl if ttl and ttl > 0 else 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
