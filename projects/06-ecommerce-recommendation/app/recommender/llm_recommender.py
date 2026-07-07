"""
Project 6 – E-commerce Product Recommendation Engine
LLM-based reranker: calls Llama 3 8B on RHOAI vLLM to rerank and
optionally explain recommendations given user context.
"""
import json
import logging
from typing import Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a personalised e-commerce recommendation assistant.
Given a user profile and a list of candidate products, return a JSON object with:
- "ranked_ids": list of product_ids ordered best → worst match
- "rationale": one short sentence explaining the top pick

Respond ONLY with valid JSON. No markdown fences."""

_USER_TEMPLATE = """User profile:
{user_profile}

Candidate products:
{candidates_json}

Return the JSON now."""


class LLMReranker:
    """
    Uses Llama 3 8B (OpenAI-compatible vLLM endpoint) to semantically
    rerank a short list of candidates based on the user's natural-language profile.
    """

    async def rerank(
        self,
        user_profile: str,
        candidates: List[dict],
        top_n: int = 10,
    ) -> Dict:
        """
        Returns {"ranked_ids": [...], "rationale": "..."}.
        Falls back to original order on any error.
        """
        # Truncate candidate list to avoid context overflow
        limited = candidates[:20]
        candidates_json = json.dumps(
            [{"product_id": c["product_id"], "title": c.get("title", ""), "category": c.get("category", "")}
             for c in limited],
            indent=2,
        )
        user_msg = _USER_TEMPLATE.format(
            user_profile=user_profile,
            candidates_json=candidates_json,
        )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                    json={
                        "model": settings.LLM_MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_tokens": settings.LLM_MAX_TOKENS,
                        "temperature": settings.LLM_TEMPERATURE,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                # Ensure only the top_n ranked IDs are returned
                result["ranked_ids"] = result.get("ranked_ids", [])[:top_n]
                return result

        except Exception as exc:
            logger.warning("LLM reranker failed (%s) – falling back to hybrid order", exc)
            return {
                "ranked_ids": [c["product_id"] for c in limited[:top_n]],
                "rationale": "Recommended based on your browsing history.",
            }


llm_reranker = LLMReranker()
