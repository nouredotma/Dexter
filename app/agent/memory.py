from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from fastembed import TextEmbedding

from app.config import get_settings


class AgentMemory:
    """Qdrant-backed episodic memory per user."""

    _model: TextEmbedding | None = None

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = AsyncQdrantClient(url=self._settings.qdrant_url)

    @classmethod
    async def _get_model(cls) -> TextEmbedding:
        if cls._model is None:

            def _load() -> TextEmbedding:
                return TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

            cls._model = await asyncio.to_thread(_load)
        return cls._model

    async def _ensure_collection(self, vector_size: int) -> None:
        collections = await self._client.get_collections()
        names = {c.name for c in collections.collections}
        if self._settings.qdrant_collection_name not in names:
            await self._client.create_collection(
                collection_name=self._settings.qdrant_collection_name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
            )

    async def load(self, user_id: str, query: str) -> list[str]:
        model = await self._get_model()
        
        def _embed() -> list[float]:
            embeddings = list(model.embed([query]))
            v = embeddings[0]
            return v.tolist() if hasattr(v, "tolist") else list(v)

        vector = await asyncio.to_thread(_embed)
        await self._ensure_collection(len(vector))

        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id),
                )
            ]
        )

        results = await self._client.search(
            collection_name=self._settings.qdrant_collection_name,
            query_vector=vector,
            query_filter=filt,
            limit=5,
            with_payload=True,
        )
        texts: list[str] = []
        for hit in results:
            payload = hit.payload or {}
            prompt = str(payload.get("prompt", ""))
            result = str(payload.get("result", ""))
            texts.append(f"Past interaction:\nUser: {prompt}\nAssistant: {result}")
        return texts

    async def save(self, user_id: str, prompt: str, result: str) -> None:
        model = await self._get_model()

        def _embed() -> list[float]:
            embeddings = list(model.embed([prompt]))
            v = embeddings[0]
            return v.tolist() if hasattr(v, "tolist") else list(v)

        vector = await asyncio.to_thread(_embed)
        await self._ensure_collection(len(vector))

        point_id = hash((user_id, prompt, datetime.now(tz=UTC).isoformat())) & ((1 << 63) - 1)

        payload = {
            "user_id": user_id,
            "prompt": prompt,
            "result": result,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        await self._client.upsert(
            collection_name=self._settings.qdrant_collection_name,
            points=[
                qmodels.PointStruct(id=point_id, vector=vector, payload=payload),
            ],
        )

    async def list_recent(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return recent memory payloads for a user (best-effort ordering)."""
        await self._ensure_collection(384)
        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id),
                )
            ]
        )

        entries: list[dict] = []
        offset = None
        while len(entries) < limit:
            scroll_res = await self._client.scroll(
                collection_name=self._settings.qdrant_collection_name,
                scroll_filter=filt,
                limit=min(64, limit - len(entries)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if isinstance(scroll_res, tuple):
                points, next_offset = scroll_res
            else:
                points = getattr(scroll_res, "points", []) or []
                next_offset = getattr(scroll_res, "next_page_offset", None)

            for p in points:
                pl = p.payload or {}
                entries.append(pl)
            if next_offset is None:
                break
            offset = next_offset

        def _ts(pl: dict) -> str:
            return str(pl.get("timestamp") or "")

        entries.sort(key=_ts, reverse=True)
        return entries[:limit]

    async def delete_all_for_user(self, user_id: str) -> None:
        await self._ensure_collection(384)
        await self._client.delete(
            collection_name=self._settings.qdrant_collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="user_id",
                            match=qmodels.MatchValue(value=user_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted Qdrant memory for user {}", user_id)
