from playwright.async_api import async_playwright


async def browser_tool(
    url: str,
    action: str,
    selector: str | None = None,
    text: str | None = None,
) -> str:
    action_norm = action.lower().strip()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            if action_norm == "navigate":
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                content = await page.inner_text("body")
                return content[:50_000]

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

            return f"error: unknown action '{action}'"
        finally:
            await browser.close()
