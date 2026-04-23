from pathlib import Path
import tempfile

from app.config import get_settings

_MAX_READ_CHARS = 200_000
_MAX_WRITE_CHARS = 500_000


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
    return target.read_text(encoding="utf-8", errors="replace")[:_MAX_READ_CHARS]


async def write_file_tool(path: str, content: str, mode: str = "w") -> str:
    try:
        target = _safe_path(path)
    except ValueError as exc:
        return f"error: {exc}"
    if mode not in {"w", "a"}:
        return "error: mode must be 'w' or 'a'"
    if len(content) > _MAX_WRITE_CHARS:
        return f"error: content too large (max {_MAX_WRITE_CHARS} chars)"
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "w":
        # Atomic overwrite to reduce risk of partial writes.
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        tmp_path.replace(target)
    else:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
    return f"success: wrote {target}"
