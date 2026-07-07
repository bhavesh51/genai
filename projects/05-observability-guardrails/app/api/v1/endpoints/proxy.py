"""
Project 5 – Observability & Guardrails
Inline guardrails proxy endpoint — wraps RHOAI LLM endpoints
"""
import logging
import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.guardrails.engine import guardrails_engine, GuardrailResult
from app.metrics.prometheus import (
    GUARDRAIL_VIOLATIONS,
    GUARDRAIL_CHECK_DURATION,
    REQUESTS_TOTAL,
    REQUEST_LATENCY,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ProxyChatRequest(BaseModel):
    model: str
    messages: List[dict]
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = 0.3
    stream: Optional[bool] = False
    tenant_id: Optional[str] = "default"


@router.post("/chat/completions", summary="Guardrails-wrapped LLM chat completions proxy")
async def proxy_chat_completions(request: ProxyChatRequest):
    """
    1. Run guardrail checks on the last user message
    2. If passed → forward to RHOAI vLLM endpoint
    3. Run output guardrails on the response
    4. Return (optionally sanitized) response
    """
    start = time.perf_counter()

    # Extract last user message for input guardrails
    user_messages = [m["content"] for m in request.messages if m.get("role") == "user"]
    last_input = user_messages[-1] if user_messages else ""

    # Input guardrails
    t0 = time.perf_counter()
    input_result: GuardrailResult = await guardrails_engine.check(last_input)
    GUARDRAIL_CHECK_DURATION.labels(service="input").observe(time.perf_counter() - t0)

    if not input_result.passed:
        for v in input_result.violations:
            GUARDRAIL_VIOLATIONS.labels(violation_type=v.split(" ")[0].lower(), service="input").inc()
        logger.warning("Input guardrail violation: %s", input_result.violations)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Guardrail violation",
                "violations": input_result.violations,
            },
        )

    # Redact PII in input if detected
    messages = request.messages
    if input_result.pii_detected and input_result.redacted_text:
        messages = list(messages)
        messages[-1] = {"role": "user", "content": input_result.redacted_text}

    # Forward to upstream RHOAI LLM
    payload = {
        "model": request.model,
        "messages": messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": request.stream,
    }
    headers = {
        "Authorization": f"Bearer {settings.UPSTREAM_LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.UPSTREAM_LLM_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        REQUESTS_TOTAL.labels(
            service="guardrails-proxy", model=request.model,
            tenant=request.tenant_id, status="error"
        ).inc()
        raise HTTPException(status_code=exc.response.status_code, detail=str(exc)) from exc

    # Output guardrails
    output_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    t0 = time.perf_counter()
    output_result = await guardrails_engine.check(output_text)
    GUARDRAIL_CHECK_DURATION.labels(service="output").observe(time.perf_counter() - t0)

    if not output_result.passed:
        for v in output_result.violations:
            GUARDRAIL_VIOLATIONS.labels(violation_type=v.split(" ")[0].lower(), service="output").inc()
        # Sanitize output instead of blocking
        if output_result.redacted_text:
            data["choices"][0]["message"]["content"] = output_result.redacted_text
        data["_guardrails"] = {"violations": output_result.violations}

    REQUEST_LATENCY.labels(service="guardrails-proxy", model=request.model).observe(
        time.perf_counter() - start
    )
    REQUESTS_TOTAL.labels(
        service="guardrails-proxy", model=request.model,
        tenant=request.tenant_id, status="success"
    ).inc()

    return data
