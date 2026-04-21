from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

BackendName = Literal["gemini", "cerebras", "anthropic", "openai"]


@dataclass
class LLMResponse:
    type: str  # "text" | "tool_call"
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _estimate_context_tokens_and_vision(messages: list[dict[str, Any]]) -> tuple[int, bool]:
    """Rough token estimate (~4 chars/token) and whether multimodal / image signals are present."""

    def scan_content(content: Any) -> tuple[int, bool]:
        if content is None:
            return 0, False
        if isinstance(content, str):
            est = max(1, len(content) // 4)
            vision = bool(
                re.search(r"data:image/[a-zA-Z0-9.+-]+;base64,", content)
                or re.search(r"!\[[^\]]*\]\(https?://[^\)]+\.(?:png|jpe?g|webp|gif|svg)\b", content, re.I)
            )
            return est, vision
        if isinstance(content, list):
            est = 0
            vision = False
            for part in content:
                if not isinstance(part, dict):
                    continue
                typ = str(part.get("type") or "")
                if typ == "text":
                    est += max(1, len(str(part.get("text", ""))) // 4)
                if typ in ("image_url", "input_image"):
                    vision = True
                    est += 256
            return est, vision
        return max(1, len(str(content)) // 4), False

    total = 0
    any_vision = False
    for m in messages:
        est, vis = scan_content(m.get("content"))
        total += est
        any_vision = any_vision or vis
    return total, any_vision


class LLMClient:
    """
    LLM abstraction with OpenAI-shaped `messages` for tool loops.

    Routing when provider is ``auto`` (default):
    - **Gemini 2.5 Flash** (Google AI Studio, OpenAI-compatible endpoint): vision / multimodal
      content, or estimated context **strictly above** ``llm_long_context_threshold_tokens``.
    - **Cerebras** (OpenAI-compatible API): short, text-only contexts within the threshold.
    """

    def __init__(
        self,
        provider: str,
        *,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        google_ai_api_key: str | None = None,
        cerebras_api_key: str | None = None,
        gemini_model: str = "gemini-2.5-flash",
        cerebras_model: str = "llama3.1-8b",
        gemini_openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
        cerebras_openai_base_url: str = "https://api.cerebras.ai/v1/",
        long_context_threshold_tokens: int = 8000,
    ) -> None:
        self._configured_provider = provider.lower().strip()
        self._anthropic_api_key = anthropic_api_key
        self._openai_api_key = openai_api_key
        self._google_ai_api_key = google_ai_api_key
        self._cerebras_api_key = cerebras_api_key
        self._gemini_model = gemini_model
        self._cerebras_model = cerebras_model
        self._gemini_openai_base_url = gemini_openai_base_url.rstrip("/") + "/"
        self._cerebras_openai_base_url = cerebras_openai_base_url.rstrip("/") + "/"
        self._long_context_threshold_tokens = long_context_threshold_tokens

        self._gemini_client: AsyncOpenAI | None = None
        if self._google_ai_api_key:
            self._gemini_client = AsyncOpenAI(
                api_key=self._google_ai_api_key,
                base_url=self._gemini_openai_base_url,
            )

        self._cerebras_client: AsyncOpenAI | None = None
        if self._cerebras_api_key:
            self._cerebras_client = AsyncOpenAI(
                api_key=self._cerebras_api_key,
                base_url=self._cerebras_openai_base_url,
            )

    def _pick_backend(
        self,
        messages: list[dict[str, Any]],
        *,
        explicit_attachments_have_images: bool,
    ) -> BackendName:
        prov = self._configured_provider
        if prov in ("anthropic", "openai"):
            return prov  # type: ignore[return-value]
        if prov == "gemini":
            return "gemini"
        if prov == "cerebras":
            return "cerebras"

        est_tokens, has_vision = _estimate_context_tokens_and_vision(messages)
        if explicit_attachments_have_images or has_vision:
            return "gemini"
        if est_tokens > self._long_context_threshold_tokens:
            return "gemini"
        return "cerebras"

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        explicit_attachments_have_images: bool = False,
    ) -> LLMResponse:
        backend = self._pick_backend(messages, explicit_attachments_have_images=explicit_attachments_have_images)

        if backend == "anthropic":
            return await self._anthropic(messages, tools)
        if backend == "openai":
            return await self._openai_chat(
                self._require_openai(),
                "gpt-4o",
                messages,
                tools,
            )
        if backend == "gemini":
            if self._gemini_client is None:
                raise RuntimeError("GOOGLE_AI_API_KEY is not configured (required for Gemini / vision / long context).")
            return await self._openai_chat(self._gemini_client, self._gemini_model, messages, tools)
        # cerebras
        if self._cerebras_client is None:
            raise RuntimeError("CEREBRAS_API_KEY is not configured (required for short-context routing).")
        return await self._openai_chat(self._cerebras_client, self._cerebras_model, messages, tools)

    def _require_openai(self) -> AsyncOpenAI:
        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return AsyncOpenAI(api_key=self._openai_api_key)

    async def _openai_chat(
        self,
        client: AsyncOpenAI,
        model: str,
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

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools

        completion = await client.chat.completions.create(**kwargs)

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

    async def _anthropic(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        if not self._anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        client = AsyncAnthropic(api_key=self._anthropic_api_key)

        anthropic_tools: list[dict[str, Any]] = []
        for tool in tools:
            anthropic_tools.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters") or {"type": "object", "properties": {}},
                }
            )

        system_text = ""
        msg_params: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_text = str(m.get("content") or "")
                continue

            if role == "user":
                content = m.get("content")
                if isinstance(content, list):
                    text_parts: list[str] = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(str(part.get("text", "")))
                        elif isinstance(part, dict) and part.get("type") == "image_url":
                            text_parts.append(f"[image] {part.get('image_url', {})}")
                    msg_params.append({"role": "user", "content": "\n".join(text_parts)})
                else:
                    msg_params.append({"role": "user", "content": str(content or "")})
                continue

            if role == "assistant":
                if m.get("tool_calls"):
                    blocks: list[dict[str, Any]] = []
                    for tc in m["tool_calls"]:
                        fn = tc["function"]
                        args_raw = fn.get("arguments") or "{}"
                        try:
                            args_obj = json.loads(args_raw)
                        except json.JSONDecodeError:
                            args_obj = {}
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": str(tc.get("id")),
                                "name": str(fn.get("name")),
                                "input": args_obj if isinstance(args_obj, dict) else {},
                            }
                        )
                    msg_params.append({"role": "assistant", "content": blocks})
                else:
                    msg_params.append({"role": "assistant", "content": str(m.get("content") or "")})
                continue

            if role == "tool":
                tool_call_id = str(m.get("tool_call_id") or "")
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": str(m.get("content") or ""),
                    "is_error": False,
                }
                msg_params.append({"role": "user", "content": [tool_result]})
                continue

        kwargs: dict[str, Any] = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "messages": msg_params,
        }
        if system_text:
            kwargs["system"] = system_text
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        resp = await client.messages.create(**kwargs)

        usage_in = int(getattr(resp.usage, "input_tokens", 0))
        usage_out = int(getattr(resp.usage, "output_tokens", 0))

        for block in getattr(resp, "content", []) or []:
            bdict = block.model_dump() if hasattr(block, "model_dump") else dict(block)
            typ = bdict.get("type")
            if typ == "text":
                return LLMResponse(
                    type="text",
                    text=str(bdict.get("text") or ""),
                    input_tokens=usage_in,
                    output_tokens=usage_out,
                )

            if typ == "tool_use":
                inp = bdict.get("input") or {}
                return LLMResponse(
                    type="tool_call",
                    tool_name=str(bdict.get("name")),
                    tool_input=inp if isinstance(inp, dict) else {},
                    input_tokens=usage_in,
                    output_tokens=usage_out,
                )

        return LLMResponse(type="text", text="", input_tokens=usage_in, output_tokens=usage_out)
