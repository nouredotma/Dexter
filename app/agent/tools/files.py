from pathlib import Path

from app.config import get_settings


def _safe_path(path: str) -> Path:
    settings = get_settings()
    root = Path(settings.agent_files_root).resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes allowed directory") from exc
    return candidate


async def read_file_tool(path: str) -> str:
    try:
        target = _safe_path(path)
    except ValueError as exc:
        return f"error: {exc}"
    if not target.exists() or not target.is_file():
        return "error: file not found"
    return target.read_text(encoding="utf-8", errors="replace")[:200_000]


async def write_file_tool(path: str, content: str, mode: str = "w") -> str:
    try:
        target = _safe_path(path)
    except ValueError as exc:
        return f"error: {exc}"
    if mode not in {"w", "a"}:
        return "error: mode must be 'w' or 'a'"
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "w":
        target.write_text(content, encoding="utf-8")
    else:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
    return f"success: wrote {target}"
