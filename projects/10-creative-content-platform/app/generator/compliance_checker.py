"""
Project 10 – Creative Content Generation Platform
Compliance checker: term-based prohibition scan (synchronous) and
LLM tone-verification (async) for generated creative content.
"""
import logging
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Prohibited terms list ──────────────────────────────────────────────────────
PROHIBITED_TERMS: List[str] = [
    "guaranteed returns",
    "risk-free",
    "100% safe",
    "miracle",
    "cure",
    "unlimited",
    "free money",
    "no risk",
    "instant results",
    "secret formula",
]

_TONE_CHECK_SYSTEM = """You are a professional brand compliance reviewer.
You will be given a piece of text and an expected tone.
Analyse the text and respond ONLY with valid JSON — no markdown fences — using exactly these keys:
{
  "tone_match": <true or false>,
  "detected_tone": "<one-word or short phrase describing the actual tone>",
  "confidence": <float between 0.0 and 1.0>
}"""

_TONE_CHECK_USER = """Expected tone: {expected_tone}

Text to analyse:
{text}

Return the JSON now."""


class ComplianceChecker:
    """
    Validates generated content for regulatory and brand compliance.

    * `check` – synchronous, no LLM: scans for prohibited terms and computes a score.
    * `check_tone` – async, calls Llama 3 8B to verify the detected tone matches expectation.
    """

    def check(self, text: str) -> dict:
        """
        Scan text for prohibited terms.

        Args:
            text: The content to check.

        Returns:
            dict with keys:
                - compliant (bool): True if no prohibited terms found.
                - violations (list[str]): List of matched prohibited terms.
                - score (float): Compliance score in [0.0, 1.0].
                  1.0 = fully compliant; decreases by 1/len(PROHIBITED_TERMS) per violation.
        """
        text_lower = text.lower()
        violations: List[str] = [term for term in PROHIBITED_TERMS if term in text_lower]
        score = max(0.0, 1.0 - len(violations) / len(PROHIBITED_TERMS))
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "score": round(score, 4),
        }

    async def check_tone(self, text: str, expected_tone: str) -> dict:
        """
        Call Llama 3 8B to verify the tone of the text matches the expected tone.

        Args:
            text:          The generated content to evaluate.
            expected_tone: The tone that was requested (e.g. formal, casual, playful, professional).

        Returns:
            dict with keys:
                - tone_match (bool): Whether the detected tone matches the expected tone.
                - detected_tone (str): What tone the LLM detected.
                - confidence (float): LLM-reported confidence [0.0, 1.0].
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                    json={
                        "model": settings.LLM_MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": _TONE_CHECK_SYSTEM},
                            {
                                "role": "user",
                                "content": _TONE_CHECK_USER.format(
                                    expected_tone=expected_tone,
                                    text=text[:2000],  # truncate to avoid token overflow
                                ),
                            },
                        ],
                        "max_tokens": 256,
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                import json  # local import to keep top-level imports clean
                raw = response.json()["choices"][0]["message"]["content"]
                result = json.loads(raw)
                return {
                    "tone_match": bool(result.get("tone_match", False)),
                    "detected_tone": str(result.get("detected_tone", "unknown")),
                    "confidence": float(result.get("confidence", 0.0)),
                }

        except Exception as exc:
            logger.warning("Tone check LLM call failed (%s) – returning inconclusive result", exc)
            return {
                "tone_match": False,
                "detected_tone": "unknown",
                "confidence": 0.0,
            }


compliance_checker = ComplianceChecker()
