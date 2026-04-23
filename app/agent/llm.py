from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI


@dataclass
class LLMResponse:
    type: str  # "text" | "tool_call"
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    """Single OpenAI-compatible provider client (Gemini by default)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = "gemini-2.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
    ) -> None:
        if not api_key:
            raise RuntimeError("LLM_API_KEY is not configured.")
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url.rstrip("/") + "/")

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "parameters",
                            {"type": "object", "additionalProperties": True},
                        ),
                    },
                }
            )

        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools

        completion = await self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0].message

        usage_in = int(completion.usage.prompt_tokens if completion.usage else 0)
        usage_out = int(completion.usage.completion_tokens if completion.usage else 0)

        tool_calls = getattr(choice, "tool_calls", None)
        if tool_calls:
            call = tool_calls[0]
            fn = call.function
            args_raw = getattr(fn, "arguments", "{}") or "{}"
            try:
                parsed = json.loads(args_raw)
            except json.JSONDecodeError:
                parsed = {}

            return LLMResponse(
                type="tool_call",
                tool_name=str(getattr(fn, "name")),
                tool_input=parsed if isinstance(parsed, dict) else {},
                input_tokens=usage_in,
                output_tokens=usage_out,
            )

        content_text = getattr(choice, "content", None)
        text = "" if content_text is None else str(content_text)
        return LLMResponse(type="text", text=text, input_tokens=usage_in, output_tokens=usage_out)
