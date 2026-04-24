from __future__ import annotations

import base64
from io import BytesIO

from PIL import ImageGrab

from app.agent.llm import LLMClient
from app.config import get_settings


async def screen_vision_tool(question: str) -> str:
    if not question.strip():
        return "error: question cannot be empty"

    image = ImageGrab.grab()
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    settings = get_settings()
    llm = LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )

    messages = [
        {
            "role": "system",
            "content": "You are a screen analysis assistant. Answer the user's question from the screenshot.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        },
    ]

    response = await llm.call(messages=messages, tools=[])
    return response.text or "No analysis returned."
