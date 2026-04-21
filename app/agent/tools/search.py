import json
from urllib.parse import quote_plus

import httpx

from app.config import get_settings


async def web_search_tool(query: str) -> str:
    settings = get_settings()

    if settings.serpapi_key:
        params = {
            "q": query,
            "api_key": settings.serpapi_key,
            "engine": "google",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get("https://serpapi.com/search.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for r in (data.get("organic_results") or [])[:5]:
                items.append(
                    {
                        "title": r.get("title"),
                        "url": r.get("link"),
                        "snippet": r.get("snippet"),
                    }
                )
            return json.dumps(items, ensure_ascii=False)

    url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, str | None]] = []

    abstract = data.get("AbstractText")
    abstract_url = data.get("AbstractURL")
    heading = data.get("Heading")
    if abstract:
        results.append({"title": heading or query, "url": abstract_url, "snippet": abstract})

    for t in (data.get("RelatedTopics") or [])[:5]:
        if isinstance(t, dict) and "Text" in t:
            results.append(
                {
                    "title": t.get("Text"),
                    "url": t.get("FirstURL"),
                    "snippet": t.get("Text"),
                }
            )

    for i in (data.get("Results") or [])[:5]:
        results.append(
            {
                "title": i.get("Title"),
                "url": i.get("FirstURL"),
                "snippet": i.get("Text"),
            }
        )

    deduped: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for r in results:
        key = str(r.get("url") or r.get("title") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(r)
        if len(deduped) >= 5:
            break

    lines = []
    for item in deduped:
        lines.append(f"- {item.get('title')}\n  {item.get('url')}\n  {item.get('snippet')}")
    return "\n".join(lines) if lines else "No results found."
