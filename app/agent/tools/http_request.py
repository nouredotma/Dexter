from typing import Any
from urllib.parse import urlparse
import ipaddress

import httpx


def _is_private_host(host: str) -> bool:
    h = host.strip().lower()
    if h in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return h.endswith(".local")


async def http_request_tool(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "error: url must be http(s) with a valid host"
    if _is_private_host(parsed.hostname):
        return "error: private/internal hosts are blocked"

    method_u = method.upper()
    if method_u not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return f"error: unsupported method {method}"

    attempts = 3
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                if method_u == "GET":
                    resp = await client.get(url, headers=headers or None)
                elif method_u == "POST":
                    resp = await client.post(url, headers=headers or None, json=body)
                elif method_u == "PUT":
                    resp = await client.put(url, headers=headers or None, json=body)
                elif method_u == "PATCH":
                    resp = await client.patch(url, headers=headers or None, json=body)
                else:
                    resp = await client.delete(url, headers=headers or None, json=body)
            break
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt == attempts:
                return f"error: request failed after retries: {exc}"
    else:
        return f"error: request failed: {last_exc}"

    text = resp.text
    if len(text) > 50_000:
        text = text[:50_000] + "\n...(truncated)"

    return f"status={resp.status_code}\n{text}"
