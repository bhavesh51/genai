"""
Project 5 – Observability & Guardrails
Guardrails engine: PII, toxicity, prompt injection checks
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Models ──────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    pii_detected: bool = False
    toxicity_score: float = 0.0
    injection_score: float = 0.0
    redacted_text: Optional[str] = None


# ─── Prompt Injection Patterns (heuristic pre-filter) ─────────────────────────

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+DAN", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"disregard\s+(your\s+)?(guidelines|rules|instructions)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions", re.IGNORECASE),
]

# Simple PII regexes (augmented by ML model in production)
PII_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "PHONE": re.compile(r"\b(\+?1?\s?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b"),
}


class GuardrailsEngine:
    def __init__(self):
        self._loaded = False

    async def load(self):
        self._loaded = True
        logger.info("Guardrails engine loaded")

    async def unload(self):
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def _check_prompt_injection(self, text: str) -> float:
        """Heuristic prompt injection score (0-1)."""
        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                return 1.0
        return 0.0

    def _detect_pii(self, text: str) -> tuple[bool, str]:
        """Detect and redact PII. Returns (detected, redacted_text)."""
        detected = False
        redacted = text
        for label, pattern in PII_PATTERNS.items():
            if pattern.search(redacted):
                detected = True
                redacted = pattern.sub(f"[{label}_REDACTED]", redacted)
        return detected, redacted

    async def _call_toxicity_model(self, text: str) -> float:
        """Call RHOAI-hosted toxicity classifier."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    settings.TOXICITY_MODEL_URL,
                    json={"inputs": [{"name": "text", "shape": [1, 1], "datatype": "BYTES", "data": [text]}]},
                )
                resp.raise_for_status()
                data = resp.json()
                outputs = data.get("outputs", [{}])
                score = outputs[0].get("data", [0.0])[0] if outputs else 0.0
                return float(score)
        except Exception as exc:
            logger.warning("Toxicity model unavailable: %s", exc)
            return 0.0

    async def check(self, text: str) -> GuardrailResult:
        """Run all guardrail checks on input text."""
        violations: list[str] = []

        # 1. Prompt injection heuristic
        injection_score = self._check_prompt_injection(text)
        if injection_score >= settings.PROMPT_INJECTION_THRESHOLD:
            violations.append(f"Prompt injection detected (score={injection_score:.2f})")

        # 2. PII detection + redaction
        pii_detected, redacted = self._detect_pii(text)
        if pii_detected:
            violations.append("PII detected and redacted")

        # 3. Toxicity (async ML model call)
        toxicity_score = await self._call_toxicity_model(text)
        if toxicity_score >= settings.TOXICITY_THRESHOLD:
            violations.append(f"Toxic content detected (score={toxicity_score:.2f})")

        passed = len(violations) == 0
        return GuardrailResult(
            passed=passed,
            violations=violations,
            pii_detected=pii_detected,
            toxicity_score=toxicity_score,
            injection_score=injection_score,
            redacted_text=redacted if pii_detected else None,
        )


guardrails_engine = GuardrailsEngine()
