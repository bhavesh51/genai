"""
Project 7 – Legal Document Analysis & Contract Intelligence
Q&A endpoint: POST /qa
Answer natural-language questions grounded in a specific document's clauses.
"""
import hashlib
import logging
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.redis_client import redis_client
from app.db.weaviate_client import weaviate_client
from app.processing.clause_extractor import _embed_batch

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Request / Response models ─────────────────────────────────────────────────


class QARequest(BaseModel):
    document_id: str = Field(..., description="ID of the previously analysed document")
    question: str = Field(..., min_length=5, max_length=1000, description="Natural-language question about the contract")


class SourceClause(BaseModel):
    clause_id: str
    text: str
    risk_category: str = ""
    risk_score: float = 0.0
    page: int = 0
    distance: float = Field(0.0, description="Cosine distance from query vector (lower = more relevant)")


class QAResponse(BaseModel):
    document_id: str
    question: str
    answer: str
    source_clauses: List[SourceClause]
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model-estimated answer confidence")
    cached: bool = False


# ── System prompt ─────────────────────────────────────────────────────────────

_QA_SYSTEM_PROMPT = """You are a senior legal analyst answering questions about a specific contract.
You will be given excerpts (clauses) from the contract and a question from the user.
Base your answer strictly on the provided clauses. Do not invent facts.
If the answer cannot be determined from the clauses, state that clearly.
Respond with a JSON object only:
{
  "answer": "<clear, concise answer>",
  "confidence": <float 0.0–1.0 reflecting certainty based on clause evidence>
}"""


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post(
    "/qa",
    response_model=QAResponse,
    status_code=status.HTTP_200_OK,
    summary="Answer a question about a specific legal document",
)
async def answer_question(req: QARequest) -> QAResponse:
    """
    Pipeline:
    1. Embed the question using InLegalBERT
    2. Retrieve top-5 most relevant clauses from Weaviate filtered by ``document_id``
    3. Call Llama 3 8B with the clause context + question
    4. Return structured answer with source traceability
    """
    # ── Cache check ──────────────────────────────────────────────────────────
    cache_key = hashlib.md5(
        f"{req.document_id}:{req.question}".encode()
    ).hexdigest()
    cached = await redis_client.get_qa_result(cache_key)
    if cached:
        return QAResponse(**cached, cached=True)

    # ── Embed question ────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            question_vectors = await _embed_batch(client, [req.question])
        question_vector = question_vectors[0]
    except Exception as exc:
        logger.exception("Failed to embed question for doc %s", req.document_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding service is unavailable.",
        ) from exc

    # ── Retrieve relevant clauses ─────────────────────────────────────────────
    relevant_clauses = await weaviate_client.search_clauses(
        query_vector=question_vector,
        top_k=5,
        document_id=req.document_id,
    )

    if not relevant_clauses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No clauses found for document '{req.document_id}'. "
                "Upload and analyse the document first via POST /api/v1/documents."
            ),
        )

    # ── Build context block ───────────────────────────────────────────────────
    context_parts: List[str] = []
    for i, clause in enumerate(relevant_clauses, start=1):
        context_parts.append(
            f"[Clause {i} – {clause.get('risk_category', 'unknown')} "
            f"(page {clause.get('page', '?')})]\n{clause['text']}"
        )
    context_block = "\n\n".join(context_parts)

    # ── Call LLM ──────────────────────────────────────────────────────────────
    payload: Dict[str, Any] = {
        "model": settings.LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": _QA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Contract clauses:\n\n{context_block}\n\n"
                    f"Question: {req.question}"
                ),
            },
        ],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            llm_response = await client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            llm_response.raise_for_status()
        raw_content = llm_response.json()["choices"][0]["message"]["content"]
        import json as _json
        llm_result = _json.loads(raw_content.strip())
        answer: str = llm_result.get("answer", "Unable to answer based on available clauses.")
        confidence: float = float(llm_result.get("confidence", 0.5))
    except httpx.HTTPStatusError as exc:
        logger.error(
            "LLM returned %d for Q&A on doc %s: %s",
            exc.response.status_code,
            req.document_id,
            exc.response.text[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM service returned an error.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during Q&A for doc %s", req.document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Q&A processing error.",
        ) from exc

    # ── Build and cache response ──────────────────────────────────────────────
    source_clauses = [
        SourceClause(
            clause_id=c.get("clause_id", ""),
            text=c.get("text", ""),
            risk_category=c.get("risk_category", ""),
            risk_score=float(c.get("risk_score", 0.0)),
            page=int(c.get("page", 0)),
            distance=float(c.get("distance") or 0.0),
        )
        for c in relevant_clauses
    ]

    response = QAResponse(
        document_id=req.document_id,
        question=req.question,
        answer=answer,
        source_clauses=source_clauses,
        confidence=max(0.0, min(1.0, confidence)),
    )

    await redis_client.set_qa_result(cache_key, response.model_dump())
    return response
