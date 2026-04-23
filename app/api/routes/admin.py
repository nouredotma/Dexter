from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, TaskStatus, User
from app.db.session import get_db
from app.dependencies import get_current_admin_user
from app.schemas.users import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    total_users = int((await db.execute(select(func.count()).select_from(User))).scalar_one())
    total_tasks = int((await db.execute(select(func.count()).select_from(Task))).scalar_one())
    pending_tasks = int(
        (
            await db.execute(
                select(func.count()).select_from(Task).where(Task.status == TaskStatus.pending)
            )
        ).scalar_one()
    )
    running_tasks = int(
        (
            await db.execute(
                select(func.count()).select_from(Task).where(Task.status == TaskStatus.running)
            )
        ).scalar_one()
    )
    return {
        "users_total": total_users,
        "tasks_total": total_tasks,
        "tasks_pending": pending_tasks,
        "tasks_running": running_tasks,
    }


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> dict:
    total = int((await db.execute(select(func.count()).select_from(User))).scalar_one())
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> None:
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot delete own account",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.commit()
