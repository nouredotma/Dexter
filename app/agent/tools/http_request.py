from typing import Any

import httpx


async def http_request_tool(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> str:
    method_u = method.upper()
    if method_u not in {"GET", "POST"}:
        return f"error: unsupported method {method}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method_u == "GET":
            resp = await client.get(url, headers=headers or None)
        else:
            resp = await client.post(url, headers=headers or None, json=body)

    text = resp.text
    if len(text) > 50_000:
        text = text[:50_000] + "\n...(truncated)"

    return f"status={resp.status_code}\n{text}"
