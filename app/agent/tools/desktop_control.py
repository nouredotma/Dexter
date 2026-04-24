from __future__ import annotations

import asyncio
import os
import subprocess

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


async def desktop_control_tool(
    action: str,
    x: int | None = None,
    y: int | None = None,
    text: str | None = None,
    key: str | None = None,
    app_name: str | None = None,
) -> str:
    if os.getenv("ENABLE_DESKTOP_CONTROL", "false").lower() != "true":
        raise RuntimeError("desktop_control_tool is disabled. Set ENABLE_DESKTOP_CONTROL=true to enable it.")

    action_norm = action.lower().strip()
    await asyncio.sleep(0.1)

    if action_norm == "move":
        if x is None or y is None:
            return "error: x and y are required for move"
        pyautogui.moveTo(x, y)
        return f"moved mouse to ({x}, {y})"

    if action_norm == "click":
        pyautogui.click(x=x, y=y)
        return f"clicked at ({x}, {y})" if x is not None and y is not None else "clicked current position"

    if action_norm == "right_click":
        pyautogui.rightClick(x=x, y=y)
        return f"right-clicked at ({x}, {y})" if x is not None and y is not None else "right-clicked current position"

    if action_norm == "double_click":
        pyautogui.doubleClick(x=x, y=y)
        return f"double-clicked at ({x}, {y})" if x is not None and y is not None else "double-clicked current position"

    if action_norm == "type":
        if text is None:
            return "error: text is required for type"
        pyautogui.write(text)
        return f"typed text ({len(text)} chars)"

    if action_norm == "press":
        if key is None:
            return "error: key is required for press"
        pyautogui.press(key)
        return f"pressed key '{key}'"

    if action_norm == "scroll":
        amount = int(text) if text is not None else 0
        pyautogui.scroll(amount)
        return f"scrolled {amount}"

    if action_norm == "open_app":
        if not app_name:
            return "error: app_name is required for open_app"
        subprocess.Popen(app_name, shell=True)
        return f"opened app '{app_name}'"

    return "error: unknown action. use move|click|right_click|double_click|type|press|scroll|open_app"
