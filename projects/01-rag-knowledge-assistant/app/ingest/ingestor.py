"""
Project 1 – RAG Knowledge Assistant
Document ingestion: parse → chunk → embed → upsert to Milvus
"""
import hashlib
import logging
import uuid
from pathlib import Path
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI

from app.core.config import settings
from app.db.milvus_client import milvus_client

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


class DocumentIngestor:
    def __init__(self):
        self._embedding_client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _extract_text(self, file_path: str, content_type: str) -> str:
        """Extract raw text from a document. For PDF use PyMuPDF / docling."""
        try:
            # Docling is the primary parser for complex formats
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(file_path)
            return result.document.export_to_markdown()
        except ImportError:
            # Fallback to plain text read
            return Path(file_path).read_text(encoding="utf-8", errors="replace")

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = await self._embedding_client.embeddings.create(
            model=settings.EMBEDDING_MODEL_NAME,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    async def ingest(
        self,
        file_path: str,
        source_name: str,
        tenant_id: str,
        content_type: str = "text/plain",
    ) -> int:
        """
        Full ingestion pipeline:
        1. Extract text from document
        2. Split into chunks
        3. Embed chunks in batches
        4. Upsert to Milvus
        Returns the number of chunks ingested.
        """
        raw_text = self._extract_text(file_path, content_type)
        chunks = self._splitter.split_text(raw_text)

        if not chunks:
            logger.warning("No text extracted from %s", source_name)
            return 0

        BATCH_SIZE = 32
        ids, sources, indices, texts = [], [], [], []
        embeddings = []

        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_start : batch_start + BATCH_SIZE]
            batch_embeddings = await self._embed_batch(batch)
            for i, (chunk, emb) in enumerate(zip(batch, batch_embeddings)):
                chunk_idx = batch_start + i
                chunk_id = hashlib.sha256(
                    f"{source_name}:{chunk_idx}:{chunk[:64]}".encode()
                ).hexdigest()[:64]
                ids.append(chunk_id)
                sources.append(source_name)
                indices.append(chunk_idx)
                texts.append(chunk)
                embeddings.append(emb)

        milvus_client.upsert_chunks(tenant_id, ids, sources, indices, texts, embeddings)
        logger.info(
            "Ingested %d chunks from %s into tenant=%s",
            len(chunks),
            source_name,
            tenant_id,
        )
        return len(chunks)


document_ingestor = DocumentIngestor()
