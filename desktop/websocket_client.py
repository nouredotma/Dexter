from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

TERMINAL_STATES = {"done", "failed", "cancelled"}


class TaskWebSocketClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url.rstrip("/")
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def connect(
        self,
        task_id: str,
        on_update: Callable[[dict[str, Any]], Awaitable[None] | None],
    ) -> None:
        await self.disconnect()
        self._running = True
        self._task = asyncio.create_task(self._listen(task_id, on_update))

    async def disconnect(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _emit(
        self,
        on_update: Callable[[dict[str, Any]], Awaitable[None] | None],
        data: dict[str, Any],
    ) -> None:
        result = on_update(data)
        if asyncio.iscoroutine(result):
            await result

    async def _listen(
        self,
        task_id: str,
        on_update: Callable[[dict[str, Any]], Awaitable[None] | None],
    ) -> None:
        ws_url = f"{self._base_url.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/tasks/{task_id}"
        try:
            async with websockets.connect(ws_url) as ws:
                while self._running:
                    raw = await ws.recv()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    await self._emit(on_update, data)
                    if str(data.get("status", "")).lower() in TERMINAL_STATES:
                        break
        except Exception as exc:  # noqa: BLE001
            await self._emit(on_update, {"status": "failed", "error": str(exc), "result": None, "steps": []})
