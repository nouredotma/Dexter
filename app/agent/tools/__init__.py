from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.agent.tools.browser import browser_tool
from app.agent.tools.calendar import calendar_tool
from app.agent.tools.email import read_email_tool, send_email_tool
from app.agent.tools.files import read_file_tool, write_file_tool
from app.agent.tools.http_request import http_request_tool
from app.agent.tools.search import web_search_tool

TOOLS_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "browser_tool": browser_tool,
    "calendar_tool": calendar_tool,
    "web_search_tool": web_search_tool,
    "read_file_tool": read_file_tool,
    "write_file_tool": write_file_tool,
    "send_email_tool": send_email_tool,
    "read_email_tool": read_email_tool,
    "http_request_tool": http_request_tool,
}


def get_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "browser_tool",
            "description": "Use a headless Chromium browser to navigate/extract/modify pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["navigate", "click", "fill", "extract"],
                        "description": "navigate loads URL and returns text; click/fill/extract operate on current page",
                    },
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["url", "action"],
            },
        },
        {
            "name": "calendar_tool",
            "description": (
                "Date/time helpers: now, parse, to_timezone, add, diff_minutes, weekday, list_timezones. "
                "Use IANA timezone names (e.g. Europe/Berlin). datetime_str uses ISO-8601 or common date formats."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "now",
                            "parse",
                            "to_timezone",
                            "add",
                            "diff_minutes",
                            "weekday",
                            "list_timezones",
                            "calendar_read",
                            "calendar_create",
                        ],
                    },
                    "datetime_str": {"type": "string"},
                    "datetime_str_b": {"type": "string"},
                    "text": {"type": "string"},
                    "timezone": {"type": "string", "default": "UTC"},
                    "days": {"type": "integer", "default": 0},
                    "hours": {"type": "integer", "default": 0},
                    "minutes": {"type": "integer", "default": 0},
                    "pattern": {"type": "string", "default": "%Y-%m-%d %H:%M:%S %Z"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "web_search_tool",
            "description": "Search the public web (DuckDuckGo instant answers by default).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "read_file_tool",
            "description": "Read a UTF-8 text file under the configured agent workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "write_file_tool",
            "description": "Write or append UTF-8 text under the configured agent workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["w", "a"], "default": "w"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "send_email_tool",
            "description": "Send email via SMTP using server-configured credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "read_email_tool",
            "description": "Read recent inbox emails via IMAP using server-configured credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 5},
                },
            },
        },
        {
            "name": "http_request_tool",
            "description": "Perform an HTTP GET or POST request with optional JSON body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                },
                "required": ["url"],
            },
        },
    ]
