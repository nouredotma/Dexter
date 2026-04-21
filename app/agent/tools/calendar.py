from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones


def _parse_iso_or_common(value: str) -> datetime:
    """Parse ISO-8601 or a few common formats; naive datetimes are treated as UTC."""
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt: datetime | None = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(value.strip(), fmt)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(f"Unrecognized datetime format: {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def calendar_tool(
    action: str,
    datetime_str: str | None = None,
    datetime_str_b: str | None = None,
    timezone: str = "UTC",
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    pattern: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str:
    """
    Calendar and time utilities (internally normalized to UTC unless displaying in a zone).

    Actions:
    - now: current instant in `timezone` (IANA), formatted with `pattern`.
    - parse: parse `datetime_str` to ISO-8601 UTC.
    - to_timezone: convert parsed `datetime_str` to `timezone` for display with `pattern`.
    - add: add `days`/`hours`/`minutes` to `datetime_str`, return ISO UTC.
    - diff_minutes: whole minutes from `datetime_str` to `datetime_str_b`.
    - weekday: English weekday name for `datetime_str` (UTC calendar date).
    - list_timezones: optional filter substring in `datetime_str`; returns up to 50 IANA names (JSON array).
    """
    act = action.lower().strip()

    if act == "now":
        tz = ZoneInfo(timezone)
        now = datetime.now(tz=tz)
        return now.strftime(pattern)

    if act == "parse":
        if not datetime_str:
            return "error: datetime_str is required for parse"
        dt = _parse_iso_or_common(datetime_str)
        return dt.isoformat()

    if act == "to_timezone":
        if not datetime_str:
            return "error: datetime_str is required for to_timezone"
        dt = _parse_iso_or_common(datetime_str)
        tz = ZoneInfo(timezone)
        return dt.astimezone(tz).strftime(pattern)

    if act == "add":
        if not datetime_str:
            return "error: datetime_str is required for add"
        base = _parse_iso_or_common(datetime_str)
        delta = timedelta(days=days, hours=hours, minutes=minutes)
        return (base + delta).isoformat()

    if act == "diff_minutes":
        if not datetime_str or not datetime_str_b:
            return "error: datetime_str and datetime_str_b are required for diff_minutes"
        a = _parse_iso_or_common(datetime_str)
        b = _parse_iso_or_common(datetime_str_b)
        return str(int((b - a).total_seconds() // 60))

    if act == "weekday":
        if not datetime_str:
            return "error: datetime_str is required for weekday"
        dt = _parse_iso_or_common(datetime_str)
        return dt.strftime("%A")

    if act == "list_timezones":
        hint = (datetime_str or "").strip().lower()
        zones = sorted(available_timezones())
        if hint:
            zones = [z for z in zones if hint in z.lower()][:50]
        else:
            zones = zones[:50]
        return json.dumps(zones, ensure_ascii=False)

    return (
        f"error: unknown action {action!r}. "
        "Supported: now, parse, to_timezone, add, diff_minutes, weekday, list_timezones"
    )
