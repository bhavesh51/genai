"""
Project 4 – Document Intelligence
Documents endpoint
"""
import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.core.config import settings
from app.kafka.producer import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter()


class UploadResponse(BaseModel):
    status: str
    document_id: str
    filename: str
    message: str


@router.post("/upload", response_model=UploadResponse, summary="Upload document for async processing")
async def upload_document(
    file: UploadFile = File(...),
    metadata: str = Form("{}", description="JSON metadata string"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    if len(content) > settings.DOCLING_MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.DOCLING_MAX_FILE_SIZE_MB} MB")

    doc_id = str(uuid.uuid4())
    s3_key = f"incoming/{doc_id}/{file.filename}"

    # Upload to ODF S3
    import boto3, io
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    s3.upload_fileobj(io.BytesIO(content), settings.S3_BUCKET_DOCUMENTS, s3_key)

    # Publish event to Kafka
    event = {
        "document_id": doc_id,
        "filename": file.filename,
        "s3_key": s3_key,
        "content_type": file.content_type,
    }
    await kafka_producer.send_document(event)

    return UploadResponse(
        status="accepted",
        document_id=doc_id,
        filename=file.filename,
        message="Document queued for processing. Poll /api/v1/documents/{document_id}/status for results.",
    )


@router.get("/{document_id}/status", summary="Get document processing status")
async def get_document_status(document_id: str):
    # In production: query PostgreSQL for processing status
    return {"document_id": document_id, "status": "processing", "note": "Poll again in a few seconds"}
