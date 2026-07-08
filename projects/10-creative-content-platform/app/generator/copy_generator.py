"""
Project 10 – Creative Content Generation Platform
Copy generator: produces long-form marketing copy using Llama 3 8B.
Brand context chunks retrieved from Weaviate RAG are injected into the system prompt
to enforce on-brand voice, terminology, and compliance constraints.
"""
import logging
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """You are an expert marketing copywriter.
You MUST write in a {tone} tone and follow the brand guidelines provided below exactly.
Do not contradict, ignore, or deviate from the brand voice described in the guidelines.

Brand Guidelines:
{brand_context}

Content type: {content_type}
Produce only the final copy text — no preamble, no meta-commentary, no markdown fences."""

_USER_TEMPLATE = """Brief:
{brief}

Write the {content_type} copy now."""


class CopyGenerator:
    """
    Generates long-form marketing copy (blog posts, emails, ads, landing pages)
    by calling Llama 3 8B on the RHOAI vLLM endpoint with brand-context RAG injection.
    """

    async def generate(
        self,
        brief: str,
        content_type: str,
        tone: str,
        brand_context: List[str],
    ) -> str:
        """
        Generate marketing copy for the given brief.

        Args:
            brief:         Short creative brief describing the copy goal.
            content_type:  One of: blog, email, ad, landing.
            tone:          One of: formal, casual, playful, professional.
            brand_context: List of brand guideline text chunks from Weaviate RAG.

        Returns:
            Generated copy as a plain string.
        """
        context_block = (
            "\n\n".join(f"- {chunk}" for chunk in brand_context)
            if brand_context
            else "No specific brand guidelines provided. Use professional tone."
        )

        system_msg = _SYSTEM_TEMPLATE.format(
            tone=tone,
            brand_context=context_block,
            content_type=content_type,
        )
        user_msg = _USER_TEMPLATE.format(brief=brief, content_type=content_type)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                    json={
                        "model": settings.LLM_MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_tokens": settings.LLM_MAX_TOKENS,
                        "temperature": settings.LLM_TEMPERATURE,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return content.strip()

        except Exception as exc:
            logger.exception(
                "CopyGenerator LLM call failed for content_type=%s tone=%s", content_type, tone
            )
            raise RuntimeError(f"Copy generation failed: {exc}") from exc


copy_generator = CopyGenerator()
