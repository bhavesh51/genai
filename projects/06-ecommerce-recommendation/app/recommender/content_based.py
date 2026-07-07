"""
Project 6 – E-commerce Product Recommendation Engine
Content-based recommender: embeds the user preference text and retrieves
semantically similar products from Qdrant.
"""
import hashlib
import logging
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.db.qdrant_client import qdrant_client
from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)


async def _embed_text(text: str) -> List[float]:
    """Call the RHOAI ModelMesh E5-large endpoint to obtain a dense vector."""
    cache_key = "emb:" + hashlib.md5(text.encode()).hexdigest()
    cached = await redis_client.get_json(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.EMBEDDING_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={"model": settings.EMBEDDING_MODEL_NAME, "input": text},
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]

    # Cache embedding for 24 h
    await redis_client.set_json(cache_key, vector, ttl=86400)
    return vector


class ContentBasedScorer:
    """
    Builds a user preference query from their recent browsing history and
    retrieved product descriptions, then ranks candidates by cosine similarity
    in Qdrant.
    """

    async def get_candidates(
        self,
        preference_text: str,
        top_k: int = 50,
        category_filter: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Embed the preference text and search Qdrant.
        Returns a list of product dicts with a `content_score` key.
        """
        vector = await _embed_text(f"query: {preference_text}")
        results = await qdrant_client.search_similar(
            query_vector=vector,
            top_k=top_k,
            category_filter=category_filter,
            exclude_ids=exclude_ids,
        )
        for r in results:
            r["content_score"] = r.pop("score", 0.0)
        return results

    async def score_candidates(
        self,
        preference_text: str,
        candidate_ids: List[str],
    ) -> Dict[str, float]:
        """Score a fixed list of product IDs by similarity to preference text."""
        vector = await _embed_text(f"query: {preference_text}")
        results = await qdrant_client.search_similar(
            query_vector=vector,
            top_k=len(candidate_ids) + 10,
        )
        score_map = {r["product_id"]: r["score"] for r in results}
        return {pid: score_map.get(pid, 0.0) for pid in candidate_ids}

    async def embed_and_store_product(
        self,
        product_id: str,
        title: str,
        description: str,
        attributes: dict,
        category: str,
    ) -> None:
        """Embed a product and upsert into Qdrant (called on catalogue ingestion)."""
        text = f"passage: {title}. {description}. " + " ".join(
            f"{k}: {v}" for k, v in attributes.items()
        )
        vector = await _embed_text(text)
        payload = {
            "product_id": product_id,
            "title": title,
            "category": category,
            "description": description[:500],
        }
        await qdrant_client.upsert_product(product_id, vector, payload)
        logger.info("Upserted product embedding for %s", product_id)


content_scorer = ContentBasedScorer()
