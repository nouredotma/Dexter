from __future__ import annotations

from typing import Any

import httpx


class DexterAPIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def submit_task(self, prompt: str) -> dict[str, Any] | None:
        try:
            response = await self._client.post("/tasks/", json={"prompt": prompt})
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        try:
            response = await self._client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    async def get_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            response = await self._client.get("/tasks/", params={"page_size": limit, "page": 1})
            response.raise_for_status()
            data = response.json()
            return list(data.get("tasks") or [])
        except Exception:
            return []

    async def cancel_task(self, task_id: str) -> dict[str, Any] | None:
        try:
            response = await self._client.delete(f"/tasks/{task_id}")
            if response.status_code in {200, 204}:
                return {"ok": True}
            return response.json()
        except Exception:
            return None

    async def get_task_logs(self, task_id: str) -> list[dict[str, Any]]:
        try:
            response = await self._client.get(f"/tasks/{task_id}/logs")
            response.raise_for_status()
            return list(response.json())
        except Exception:
            return []

    async def get_memory(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            response = await self._client.get("/memory/")
            response.raise_for_status()
            rows = list(response.json())
            return rows[:limit]
        except Exception:
            return []

    async def clear_memory(self) -> dict[str, Any] | None:
        try:
            response = await self._client.delete("/memory/")
            if response.status_code in {200, 204}:
                return {"ok": True}
            return response.json()
        except Exception:
            return None

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "ok"
        except Exception:
            return False
