from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import gettempdir

from PIL import ImageGrab


async def screenshot_tool(save_path: str | None = None) -> str:
    image = ImageGrab.grab()

    if save_path:
        output = Path(save_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = (Path(gettempdir()) / f"dexter_screenshot_{ts}.png").resolve()

    image.save(output, format="PNG")
    width, height = image.size
    return f"saved: {output} (width={width}, height={height})"
