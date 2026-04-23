import asyncio
import base64
from urllib.parse import urlparse

from playwright.async_api import async_playwright

_browser = None
_playwright = None
_page_by_host: dict[str, object] = {}
_lock = asyncio.Lock()


async def _get_page(url: str):
    global _browser, _playwright
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("invalid url host")
    async with _lock:
        if _playwright is None:
            _playwright = await async_playwright().start()
        if _browser is None:
            _browser = await _playwright.chromium.launch(headless=True)
        page = _page_by_host.get(host)
        if page is None or page.is_closed():
            ctx = await _browser.new_context()
            page = await ctx.new_page()
            _page_by_host[host] = page
        return page


async def browser_tool(
    url: str,
    action: str,
    selector: str | None = None,
    text: str | None = None,
) -> str:
    action_norm = action.lower().strip()
    try:
        page = await _get_page(url)
        if action_norm == "navigate":
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            content = await page.inner_text("body")
            return content[:50_000]

        if page.url == "about:blank":
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        if action_norm == "click":
            if not selector:
                return "error: selector required for click"
            await page.click(selector, timeout=30_000)
            return "clicked"

        if action_norm == "fill":
            if not selector or text is None:
                return "error: selector and text required for fill"
            await page.fill(selector, text, timeout=30_000)
            return "filled"

        if action_norm == "extract":
            content = await page.inner_text("body")
            return content[:50_000]

        if action_norm == "wait_for":
            if not selector:
                return "error: selector required for wait_for"
            await page.wait_for_selector(selector, timeout=30_000)
            return "ready"

        if action_norm == "screenshot":
            png = await page.screenshot(full_page=True)
            b64 = base64.b64encode(png).decode("ascii")
            return b64[:50_000]

        return f"error: unknown action '{action}'"
    except Exception as exc:
        return f"error: browser action failed: {exc}"
