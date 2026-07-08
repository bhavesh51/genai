"""
Project 7 – Legal Document Analysis & Contract Intelligence
Clause extractor: segments document pages into individual clauses and embeds
each clause using the RHOAI ModelMesh InLegalBERT embeddings endpoint.
"""
import logging
import uuid
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def extract_clauses(page_chunks: List[dict]) -> List[dict]:
    """
    Segment page text into individual clauses and obtain their embeddings.

    Segmentation rule:
    * Split on double-newlines (``\\n\\n``) or ``\\r\\n\\r\\n``.
    * Discard segments shorter than ``settings.MIN_CLAUSE_LENGTH`` characters.

    Each returned element has the shape::

        {
            "clause_id": str,    # unique UUID string
            "text":      str,    # raw clause text
            "char_start": int,   # character offset within the *page* text
            "page":      int,    # 1-based source page number
            "embedding": list[float],  # 768-dim InLegalBERT vector
        }

    Parameters
    ----------
    page_chunks:
        Output of :func:`app.processing.parser.parse_document`.

    Returns
    -------
    list of dict
    """
    raw_clauses: List[dict] = []

    for chunk in page_chunks:
        page_num: int = chunk["page"]
        page_text: str = chunk["text"]
        segments = _split_into_segments(page_text)
        for seg_text, char_start in segments:
            if len(seg_text) < settings.MIN_CLAUSE_LENGTH:
                continue
            raw_clauses.append(
                {
                    "clause_id": str(uuid.uuid4()),
                    "text": seg_text,
                    "char_start": char_start,
                    "page": page_num,
                }
            )

    if not raw_clauses:
        logger.warning("No clauses extracted from %d page chunks", len(page_chunks))
        return []

    logger.info("Segmented %d raw clauses; requesting embeddings…", len(raw_clauses))

    # Embed in batches of 32 to avoid oversized requests
    batch_size = 32
    texts = [c["text"] for c in raw_clauses]
    all_embeddings: List[List[float]] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_start in range(0, len(texts), batch_size):
            batch = texts[batch_start : batch_start + batch_size]
            embeddings = await _embed_batch(client, batch)
            all_embeddings.extend(embeddings)

    # Attach embeddings back to clause dicts
    for clause, emb in zip(raw_clauses, all_embeddings):
        clause["embedding"] = emb

    logger.info("Embedding complete for %d clauses", len(raw_clauses))
    return raw_clauses


def _split_into_segments(text: str) -> List[tuple]:
    """
    Split text on double-newline boundaries and return (segment, char_offset) pairs.
    """
    results: List[tuple] = []
    # Normalise Windows line endings
    normalised = text.replace("\r\n", "\n")
    offset = 0
    for segment in normalised.split("\n\n"):
        stripped = segment.strip()
        if stripped:
            # Find actual start of stripped text within full text
            local_start = text.find(stripped, offset)
            char_start = local_start if local_start != -1 else offset
            results.append((stripped, char_start))
        offset += len(segment) + 2  # account for the "\n\n" delimiter
    return results


async def _embed_batch(client: httpx.AsyncClient, texts: List[str]) -> List[List[float]]:
    """
    Call the RHOAI ModelMesh OpenAI-compatible embeddings endpoint for a batch
    of texts and return the list of embedding vectors.
    """
    payload = {
        "model": settings.EMBEDDING_MODEL_NAME,
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = await client.post(
            f"{settings.EMBEDDING_BASE_URL}/embeddings",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        # OpenAI-compatible format: {"data": [{"embedding": [...], "index": int}, ...]}
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_items]
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Embedding endpoint returned %d: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        raise
    except Exception as exc:
        logger.exception("Unexpected error calling embedding endpoint: %s", exc)
        raise
