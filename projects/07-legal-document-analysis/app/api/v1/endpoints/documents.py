"""
Project 7 – Legal Document Analysis & Contract Intelligence
Documents endpoints:
  POST /documents               — upload & analyse a legal document
  GET  /documents/{doc_id}      — retrieve cached analysis
  GET  /documents/{doc_id}/clauses — list all clauses for a document
"""
import logging
import os
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.redis_client import redis_client
from app.db.weaviate_client import weaviate_client
from app.processing.parser import parse_document
from app.processing.clause_extractor import extract_clauses
from app.processing.risk_scorer import score_clauses, RISK_CATEGORIES

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Response models ───────────────────────────────────────────────────────────


class RiskItem(BaseModel):
    clause_id: str
    text: str
    risk_category: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    page: int = 0


class DocumentAnalysisResponse(BaseModel):
    doc_id: str
    filename: str
    clause_count: int
    risk_summary: Dict[str, int] = Field(
        ..., description="Map of risk_category → number of clauses"
    )
    top_risks: List[RiskItem] = Field(
        ..., description="Top-5 highest-risk clauses"
    )
    status: str = "analysed"


class ClauseListResponse(BaseModel):
    doc_id: str
    clauses: List[RiskItem]
    total: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/documents",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and analyse a legal document (PDF / DOCX / TXT)",
)
async def upload_document(
    file: UploadFile = File(..., description="Legal document file (PDF, DOCX, or TXT)"),
) -> DocumentAnalysisResponse:
    """
    Full analysis pipeline:
    1. Save uploaded file to ``/tmp``
    2. Parse text → page chunks
    3. Segment into clauses & embed via InLegalBERT
    4. Classify each clause into 15 risk categories via Llama 3 8B
    5. Persist clauses + embeddings in Weaviate
    6. Cache analysis result in Redis
    7. Return ``DocumentAnalysisResponse``
    """
    # Validate content type
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    content_type = file.content_type or ""
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in (".pdf", ".docx", ".txt"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: .pdf, .docx, .txt",
        )

    # Check file size before full read
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {len(contents) / 1024 / 1024:.1f} MB exceeds the "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB limit."
            ),
        )

    # Generate document ID and write to /tmp
    doc_id = str(uuid.uuid4())
    tmp_path = f"/tmp/{doc_id}{ext}"
    with open(tmp_path, "wb") as fh:
        fh.write(contents)

    logger.info(
        "Document received: doc_id=%s filename=%s size=%d bytes",
        doc_id,
        file.filename,
        len(contents),
    )

    try:
        # 1. Parse
        page_chunks = await parse_document(tmp_path)
        if not page_chunks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not extract any text from the uploaded document.",
            )

        # 2. Extract + embed clauses
        clauses = await extract_clauses(page_chunks)
        if not clauses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No clauses could be extracted from the document.",
            )

        # 3. Score risks
        scored = await score_clauses(clauses)

        # 4. Persist clauses to Weaviate
        for clause in scored:
            await weaviate_client.upsert_clause(
                clause_id=clause["clause_id"],
                document_id=doc_id,
                text=clause["text"],
                char_start=clause.get("char_start", 0),
                vector=clause.get("embedding", []),
                risk_category=clause.get("risk_category", ""),
                risk_score=clause.get("risk_score", 0.0),
                explanation=clause.get("explanation", ""),
                page=clause.get("page", 0),
            )

        # 5. Build risk summary and top-5 risks
        risk_summary: Dict[str, int] = Counter(
            c["risk_category"] for c in scored
        )
        # Ensure every category appears in summary (0 if absent)
        for cat in RISK_CATEGORIES:
            if cat not in risk_summary:
                risk_summary[cat] = 0

        top_risks = sorted(scored, key=lambda c: c.get("risk_score", 0.0), reverse=True)[:5]
        top_risk_items = [
            RiskItem(
                clause_id=c["clause_id"],
                text=c["text"],
                risk_category=c.get("risk_category", ""),
                risk_score=c.get("risk_score", 0.0),
                explanation=c.get("explanation", ""),
                page=c.get("page", 0),
            )
            for c in top_risks
        ]

        # 6. Build cacheable analysis payload (strip large embeddings)
        analysis_payload: Dict[str, Any] = {
            "doc_id": doc_id,
            "filename": file.filename or "",
            "clause_count": len(scored),
            "risk_summary": dict(risk_summary),
            "top_risks": [item.model_dump() for item in top_risk_items],
            "status": "analysed",
        }

        # Store clauses list (without embeddings) in Redis
        clauses_for_cache = [
            {
                "clause_id": c["clause_id"],
                "text": c["text"],
                "risk_category": c.get("risk_category", ""),
                "risk_score": c.get("risk_score", 0.0),
                "explanation": c.get("explanation", ""),
                "page": c.get("page", 0),
            }
            for c in scored
        ]
        await redis_client.set_document(doc_id, analysis_payload)
        await redis_client.set_document_clauses(doc_id, clauses_for_cache)

        logger.info(
            "Analysis complete: doc_id=%s clauses=%d", doc_id, len(scored)
        )

        return DocumentAnalysisResponse(**analysis_payload)

    finally:
        # Always remove temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get(
    "/documents/{doc_id}",
    response_model=DocumentAnalysisResponse,
    summary="Retrieve a previously analysed document by ID",
)
async def get_document(doc_id: str) -> DocumentAnalysisResponse:
    """Return the cached document analysis result from Redis."""
    cached = await redis_client.get_document(doc_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for document '{doc_id}'. "
                   "It may have expired from cache or was never processed.",
        )
    return DocumentAnalysisResponse(**cached)


@router.get(
    "/documents/{doc_id}/clauses",
    response_model=ClauseListResponse,
    summary="List all clauses extracted from a document",
)
async def list_clauses(doc_id: str) -> ClauseListResponse:
    """
    Return all clauses for a document.  Redis is checked first; on a cache miss
    the clauses are fetched from Weaviate.
    """
    cached = await redis_client.get_document_clauses(doc_id)
    if cached:
        return ClauseListResponse(
            doc_id=doc_id,
            clauses=[RiskItem(**c) for c in cached],
            total=len(cached),
        )

    # Fallback: fetch directly from Weaviate
    raw = await weaviate_client.search_by_document_id(doc_id)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No clauses found for document '{doc_id}'.",
        )
    clauses = [
        RiskItem(
            clause_id=c.get("clause_id", ""),
            text=c.get("text", ""),
            risk_category=c.get("risk_category", ""),
            risk_score=c.get("risk_score", 0.0),
            explanation=c.get("explanation", ""),
            page=c.get("page", 0),
        )
        for c in raw
    ]
    return ClauseListResponse(doc_id=doc_id, clauses=clauses, total=len(clauses))
