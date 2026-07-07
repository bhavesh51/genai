"""
Project 1 – RAG Knowledge Assistant
Document ingestion endpoint
"""
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.ingest.ingestor import document_ingestor

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/markdown",
    "text/html",
}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class IngestResponse(BaseModel):
    status: str
    source_name: str
    tenant_id: str
    chunks_ingested: int


@router.post("", response_model=IngestResponse, summary="Ingest a document into the knowledge base")
async def ingest_document(
    tenant_id: str = Form(..., description="Tenant identifier"),
    file: UploadFile = File(..., description="Document to ingest"),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}. Allowed: {ALLOWED_CONTENT_TYPES}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 100 MB limit")

    with tempfile.NamedTemporaryFile(
        suffix=Path(file.filename).suffix, delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        chunks = await document_ingestor.ingest(
            file_path=tmp_path,
            source_name=file.filename,
            tenant_id=tenant_id,
            content_type=file.content_type,
        )
    except Exception as exc:
        logger.exception("Ingestion failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return IngestResponse(
        status="success",
        source_name=file.filename,
        tenant_id=tenant_id,
        chunks_ingested=chunks,
    )
