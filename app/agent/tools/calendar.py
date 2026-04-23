from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

import httpx

from app.config import get_settings


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
    text: str | None = None,
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
    - calendar_read: reads upcoming Google Calendar events (uses GOOGLE_CALENDAR_ACCESS_TOKEN).
    - calendar_create: creates Google Calendar event; requires datetime_str(start), datetime_str_b(end), text(summary).
    - calendar_update: updates an existing event; requires text(event_id), datetime_str(start), datetime_str_b(end).
    - calendar_delete: deletes an event by id in text.
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

    if act.startswith("calendar_"):
        settings = get_settings()
        if not settings.google_calendar_access_token:
            return "error: GOOGLE_CALENDAR_ACCESS_TOKEN is not configured"
        headers = {"Authorization": f"Bearer {settings.google_calendar_access_token}"}

    if act == "calendar_read":
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 10,
            "timeMin": datetime.now(tz=UTC).isoformat(),
        }
        url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.google_calendar_id}/events"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params=params)
        if resp.status_code in {401, 403}:
            return "error: calendar read unauthorized (check GOOGLE_CALENDAR_ACCESS_TOKEN)"
        if resp.status_code >= 400:
            return f"error: calendar read failed ({resp.status_code}) {resp.text[:500]}"
        items = (resp.json() or {}).get("items", [])
        if not items:
            return "No upcoming events."
        lines: list[str] = []
        for item in items[:10]:
            start = (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date")
            lines.append(f"- {item.get('summary', '(no title)')} @ {start}")
        return "\n".join(lines)

    if act == "calendar_create":
        if not datetime_str or not datetime_str_b or not text:
            return "error: datetime_str(start), datetime_str_b(end), and text(summary) are required"
        start_iso = _parse_iso_or_common(datetime_str).isoformat()
        end_iso = _parse_iso_or_common(datetime_str_b).isoformat()
        headers["Content-Type"] = "application/json"
        body = {
            "summary": text,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.google_calendar_id}/events"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code in {401, 403}:
            return "error: calendar create unauthorized (check GOOGLE_CALENDAR_ACCESS_TOKEN)"
        if resp.status_code >= 400:
            return f"error: calendar create failed ({resp.status_code}) {resp.text[:500]}"
        event = resp.json() or {}
        return f"success: event created id={event.get('id')} link={event.get('htmlLink')}"

    if act == "calendar_update":
        if not text:
            return "error: text(event_id) is required for calendar_update"
        if not datetime_str or not datetime_str_b:
            return "error: datetime_str(start) and datetime_str_b(end) are required"
        start_iso = _parse_iso_or_common(datetime_str).isoformat()
        end_iso = _parse_iso_or_common(datetime_str_b).isoformat()
        headers["Content-Type"] = "application/json"
        body = {"start": {"dateTime": start_iso}, "end": {"dateTime": end_iso}}
        url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.google_calendar_id}/events/{text}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(url, headers=headers, json=body)
        if resp.status_code in {401, 403}:
            return "error: calendar update unauthorized (check GOOGLE_CALENDAR_ACCESS_TOKEN)"
        if resp.status_code == 404:
            return "error: calendar event not found"
        if resp.status_code >= 400:
            return f"error: calendar update failed ({resp.status_code}) {resp.text[:500]}"
        event = resp.json() or {}
        return f"success: event updated id={event.get('id')}"

    if act == "calendar_delete":
        if not text:
            return "error: text(event_id) is required for calendar_delete"
        url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.google_calendar_id}/events/{text}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers=headers)
        if resp.status_code in {401, 403}:
            return "error: calendar delete unauthorized (check GOOGLE_CALENDAR_ACCESS_TOKEN)"
        if resp.status_code == 404:
            return "error: calendar event not found"
        if resp.status_code >= 400:
            return f"error: calendar delete failed ({resp.status_code}) {resp.text[:500]}"
        return "success: event deleted"

    return (
        f"error: unknown action {action!r}. "
        "Supported: now, parse, to_timezone, add, diff_minutes, weekday, list_timezones, calendar_read, calendar_create, calendar_update, calendar_delete"
    )
