import asyncio
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, status
from sqlalchemy import select

from app.api.middleware.auth import verify_token
from app.config import get_settings
from app.db.models import Task, TaskStatus
from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["websocket"])


@router.websocket("/tasks/{task_id}")
async def task_progress(websocket: WebSocket, task_id: str, token: str | None = None) -> None:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="token is required")

    settings = get_settings()
    try:
        user_id_str = verify_token(token, settings, token_type="access")
    except HTTPException as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="invalid token") from exc

    await websocket.accept()

    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_uuid = uuid.UUID(user_id_str)

    try:
        while True:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Task).where(Task.id == tid))
                task = result.scalar_one_or_none()

            if task is None or task.user_id != user_uuid:
                await websocket.send_json({"error": "not_found"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            steps = task.steps or []
            payload = {
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "steps": steps,
                "step_count": len(steps),
            }
            await websocket.send_json(payload)

            if task.status in {TaskStatus.done, TaskStatus.failed, TaskStatus.cancelled}:
                await websocket.close()
                return

            await asyncio.sleep(1)
    except Exception:
        await websocket.close()
