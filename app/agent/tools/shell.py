from __future__ import annotations

import os
import subprocess

BLOCKED_COMMANDS = [
    "rm -rf",
    "rmdir /s",
    "format",
    "mkfs",
    "dd if",
    "del /f",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "curl | bash",
    "wget | bash",
]

CONFIRMATION_REQUIRED = ["rm ", "del ", "uninstall", "pip uninstall"]


async def shell_tool(command: str) -> str:
    if os.getenv("ENABLE_SHELL_TOOL", "false").lower() != "true":
        raise RuntimeError("shell_tool is disabled. Set ENABLE_SHELL_TOOL=true to enable it.")

    command_norm = command.strip().lower()
    if not command_norm:
        return "error: command cannot be empty"

    for blocked in BLOCKED_COMMANDS:
        if blocked in command_norm:
            return f"error: blocked command pattern detected: {blocked}"

    for confirm in CONFIRMATION_REQUIRED:
        if confirm in command_norm:
            return (
                "confirmation_required: This command may be destructive. "
                "Please confirm explicit execution first."
            )

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30 seconds"
    except Exception as exc:  # noqa: BLE001
        return f"error: failed to execute command: {exc}"

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        return stdout
    if stderr:
        return stderr
    return f"command finished with exit code {completed.returncode}"
