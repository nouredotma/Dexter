from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import AgentMemory
from app.api.middleware.auth import get_current_user
from app.db.models import UsageLog, User
from app.db.session import get_db
from app.schemas.users import MemoryEntryResponse, UsageResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_me(current: User = Depends(get_current_user)) -> User:
    return current


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> User:
    if payload.full_name is not None:
        current.full_name = payload.full_name
    if payload.llm_provider is not None:
        current.llm_provider = payload.llm_provider
    await db.commit()
    await db.refresh(current)
    return current


@router.get("/me/memory", response_model=list[MemoryEntryResponse])
async def list_memory(
    current: User = Depends(get_current_user),
) -> list[MemoryEntryResponse]:
    memory = AgentMemory()
    rows = await memory.list_recent(str(current.id), limit=20)
    out: list[MemoryEntryResponse] = []
    for pl in rows:
        ts_raw = pl.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now()
        else:
            ts = datetime.now()
        out.append(
            MemoryEntryResponse(
                prompt=str(pl.get("prompt", "")),
                result=str(pl.get("result", "")),
                timestamp=ts,
            )
        )
    return out


@router.delete("/me/memory", status_code=status.HTTP_204_NO_CONTENT)
async def clear_memory(current: User = Depends(get_current_user)) -> None:
    memory = AgentMemory()
    await memory.delete_all_for_user(str(current.id))


@router.get("/me/usage")
async def usage_logs(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> dict:
    count_stmt = select(func.count()).select_from(UsageLog).where(UsageLog.user_id == current.id)
    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())

    cost_stmt = select(func.coalesce(func.sum(UsageLog.cost_usd), Decimal("0"))).where(
        UsageLog.user_id == current.id
    )
    cost_result = await db.execute(cost_stmt)
    total_cost = cost_result.scalar_one()

    stmt = (
        select(UsageLog)
        .where(UsageLog.user_id == current.id)
        .order_by(UsageLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return {
        "items": [UsageResponse.model_validate(l) for l in logs],
        "total": total,
        "total_cost_usd": total_cost,
        "page": page,
        "page_size": page_size,
    }
