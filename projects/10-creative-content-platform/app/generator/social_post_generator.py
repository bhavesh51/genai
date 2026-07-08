"""
Project 10 – Creative Content Generation Platform
Social post generator: produces platform-optimised social media posts in JSON mode.
Enforces per-platform character limits and returns structured metadata.
"""
import json
import logging
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Platform character constraints
_PLATFORM_LIMITS = {
    "twitter": 280,
    "linkedin": 3000,
    "instagram": 2200,
}
_DEFAULT_LIMIT = 2000

_SYSTEM_TEMPLATE = """You are an expert social media copywriter specialising in {platform}.
You MUST write in a {tone} tone and follow the brand guidelines exactly.

Brand Guidelines:
{brand_context}

Platform constraints:
- Platform: {platform}
- Maximum characters for post_text + hashtags combined: {char_limit}
- Twitter posts must be punchy and concise (≤280 chars total)
- LinkedIn posts may be longer and more professional
- Instagram posts should be visual-first with strong emoji use where appropriate

Respond ONLY with a single valid JSON object — no markdown fences, no extra text — with these exact keys:
{{
  "platform": "<platform name>",
  "post_text": "<the body of the post>",
  "hashtags": ["<tag1>", "<tag2>", ...],
  "char_count": <integer: len(post_text)>,
  "cta": "<a concise call-to-action string>"
}}"""

_USER_TEMPLATE = """Brief:
{brief}

Generate the {platform} post JSON now."""


class SocialPostGenerator:
    """
    Generates structured social media posts for Twitter, LinkedIn, and Instagram
    using Llama 3 8B JSON mode with brand-context RAG injection.
    """

    async def generate(
        self,
        brief: str,
        platform: str,
        tone: str,
        brand_context: List[str],
    ) -> dict:
        """
        Generate a social post for the specified platform.

        Args:
            brief:         Short creative brief describing the post goal.
            platform:      One of: twitter, linkedin, instagram.
            tone:          One of: formal, casual, playful, professional.
            brand_context: List of brand guideline text chunks from Weaviate RAG.

        Returns:
            dict with keys: platform, post_text, hashtags, char_count, cta
        """
        platform_lower = platform.lower()
        char_limit = _PLATFORM_LIMITS.get(platform_lower, _DEFAULT_LIMIT)

        context_block = (
            "\n\n".join(f"- {chunk}" for chunk in brand_context)
            if brand_context
            else "No specific brand guidelines provided. Use professional tone."
        )

        system_msg = _SYSTEM_TEMPLATE.format(
            platform=platform_lower,
            tone=tone,
            brand_context=context_block,
            char_limit=char_limit,
        )
        user_msg = _USER_TEMPLATE.format(brief=brief, platform=platform_lower)

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
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                raw_content = response.json()["choices"][0]["message"]["content"]
                result: dict = json.loads(raw_content)

        except json.JSONDecodeError as exc:
            logger.error("SocialPostGenerator failed to parse JSON response: %s", exc)
            raise RuntimeError("LLM returned non-JSON response for social post") from exc
        except Exception as exc:
            logger.exception(
                "SocialPostGenerator LLM call failed for platform=%s tone=%s", platform, tone
            )
            raise RuntimeError(f"Social post generation failed: {exc}") from exc

        # Normalise / fill defaults so callers always receive all required keys
        post_text = result.get("post_text", "")
        return {
            "platform": result.get("platform", platform_lower),
            "post_text": post_text,
            "hashtags": result.get("hashtags", []),
            "char_count": result.get("char_count", len(post_text)),
            "cta": result.get("cta", ""),
        }


social_post_generator = SocialPostGenerator()
