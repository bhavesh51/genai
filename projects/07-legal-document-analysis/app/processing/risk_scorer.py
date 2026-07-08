"""
Project 7 – Legal Document Analysis & Contract Intelligence
Risk scorer: classifies each clause into one of 15 legal risk categories using
the RHOAI-hosted Llama 3 8B-Instruct model in JSON mode.
"""
import json
import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Risk category registry ────────────────────────────────────────────────────

RISK_CATEGORIES: List[str] = [
    "indemnification",
    "liability_cap",
    "ip_ownership",
    "termination",
    "governing_law",
    "dispute_resolution",
    "confidentiality",
    "data_protection",
    "non_compete",
    "force_majeure",
    "limitation_of_liability",
    "warranty",
    "payment_terms",
    "auto_renewal",
    "assignment",
]

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior legal analyst specialising in contract risk assessment.
You will be given a clause from a legal contract.
Your task is to classify the clause into exactly ONE of the following risk categories and
assign a risk score between 0.0 (no risk) and 1.0 (maximum risk).

Risk categories:
{categories}

Respond with a JSON object only, no preamble, no markdown fences:
{{
  "risk_category": "<one of the categories above>",
  "risk_score": <float 0.0–1.0>,
  "explanation": "<concise 1–2 sentence rationale>"
}}

If the clause does not fit any category, use the closest one and explain why.""".format(
    categories="\n".join(f"- {c}" for c in RISK_CATEGORIES)
)


# ── Public interface ──────────────────────────────────────────────────────────


async def score_clauses(clauses: List[dict]) -> List[dict]:
    """
    Classify and risk-score every clause in the list.

    Parameters
    ----------
    clauses:
        List of clause dicts as returned by
        :func:`app.processing.clause_extractor.extract_clauses`.
        Each dict must have at least ``clause_id`` and ``text``.

    Returns
    -------
    list of dict
        Original clause fields plus ``risk_category``, ``risk_score``,
        and ``explanation``.
    """
    scored: List[dict] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for clause in clauses:
            result = await _classify_clause(client, clause)
            scored.append(result)

    logger.info("Risk scoring complete: %d clauses scored", len(scored))
    return scored


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _classify_clause(client: httpx.AsyncClient, clause: dict) -> dict:
    """
    Call the LLM to classify a single clause and return enriched dict.
    Falls back to ``{"risk_category": "governing_law", "risk_score": 0.0,
    "explanation": "classification unavailable"}`` on error.
    """
    payload: Dict[str, Any] = {
        "model": settings.LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Clause to classify:\n\n{clause['text'][:2000]}",
            },
        ],
        "max_tokens": 256,
        "temperature": settings.LLM_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = await client.post(
            f"{settings.LLM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        raw_content = response.json()["choices"][0]["message"]["content"]
        classification = _safe_parse_json(raw_content)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "LLM returned %d for clause %s: %s",
            exc.response.status_code,
            clause.get("clause_id"),
            exc.response.text[:200],
        )
        classification = _fallback_classification()
    except Exception as exc:
        logger.warning(
            "Error classifying clause %s: %s", clause.get("clause_id"), exc
        )
        classification = _fallback_classification()

    return {
        **clause,
        "risk_category": classification.get("risk_category", "governing_law"),
        "risk_score": float(classification.get("risk_score", 0.0)),
        "explanation": classification.get("explanation", ""),
    }


def _safe_parse_json(raw: str) -> dict:
    """Parse LLM JSON output, stripping any accidental markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Strip leading/trailing fence lines
        lines = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM JSON output: %s", raw[:200])
        return _fallback_classification()


def _fallback_classification() -> dict:
    return {
        "risk_category": "governing_law",
        "risk_score": 0.0,
        "explanation": "Classification unavailable.",
    }
