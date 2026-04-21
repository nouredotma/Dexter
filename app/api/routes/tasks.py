from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user
from app.api.middleware.rate_limit import rate_limit
from app.db.models import Task, TaskStatus, User
from app.db.session import get_db
from app.schemas.tasks import TaskCreate, TaskListResponse, TaskLog, TaskResponse
from app.workers.agent_task import run_agent_task

router = APIRouter(prefix="/tasks", tags=["tasks"])
RateLimited = Annotated[None, Depends(rate_limit)]


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    _: RateLimited,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    llm_provider = payload.llm_provider or user.llm_provider
    task = Task(
        user_id=user.id,
        prompt=payload.prompt,
        attachments=payload.attachments,
        status=TaskStatus.pending,
        llm_provider=llm_provider,
        steps=[],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    await run_agent_task.kiq(str(task.id))
    return task


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    _: RateLimited,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: TaskStatus | None = Query(None, alias="status"),
) -> TaskListResponse:
    stmt = select(Task).where(Task.user_id == user.id)
    count_stmt = select(func.count()).select_from(Task).where(Task.user_id == user.id)

    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
        count_stmt = select(func.count()).select_from(Task).where(
            Task.user_id == user.id,
            Task.status == status_filter,
        )

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())

    stmt = stmt.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = await db.execute(stmt)
    tasks = rows.scalars().all()

    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    _: RateLimited,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: UUID,
    _: RateLimited,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != TaskStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending tasks can be cancelled")
    task.status = TaskStatus.cancelled
    task.completed_at = datetime.now(tz=UTC)
    await db.commit()


@router.get("/{task_id}/logs", response_model=list[TaskLog])
async def task_logs(
    task_id: UUID,
    _: RateLimited,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TaskLog]:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    raw_steps = task.steps or []
    logs: list[TaskLog] = []
    for step in raw_steps:
        ts_raw = step.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now(tz=UTC)
        else:
            ts = datetime.now(tz=UTC)
        logs.append(
            TaskLog(
                step=int(step.get("step") or 0),
                tool=str(step.get("tool") or ""),
                input=dict(step.get("input") or {}),
                output=str(step.get("output") or ""),
                timestamp=ts,
            )
        )
    return logs
