"""
Project 7 – Legal Document Analysis & Contract Intelligence
Async document text extraction for PDF, DOCX, and plain-text files
"""
import logging
import os
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum bytes derived from the configurable MB setting
MAX_UPLOAD_BYTES: int = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def parse_document(file_path: str) -> List[dict]:
    """
    Extract text from a document file and return a list of page chunks.

    Each element in the returned list has the shape::

        {"page": int, "text": str}

    Supported formats: ``.pdf``, ``.docx``, ``.txt``

    Parameters
    ----------
    file_path:
        Absolute or relative path to the saved temporary file.

    Returns
    -------
    list of dict
        Ordered list of page-level text chunks.

    Raises
    ------
    ValueError
        If the file size exceeds MAX_UPLOAD_SIZE_MB or the extension is unsupported.
    """
    # Guard: file size check
    size_bytes = os.path.getsize(file_path)
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File size {size_bytes / 1024 / 1024:.1f} MB exceeds the maximum "
            f"allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    ext = os.path.splitext(file_path)[1].lower()
    logger.info("Parsing document '%s' (extension=%s, size=%d bytes)", file_path, ext, size_bytes)

    if ext == ".pdf":
        return await _parse_pdf(file_path)
    elif ext == ".docx":
        return await _parse_docx(file_path)
    elif ext == ".txt":
        return await _parse_txt(file_path)
    else:
        raise ValueError(
            f"Unsupported file extension '{ext}'. Supported formats: .pdf, .docx, .txt"
        )


async def _parse_pdf(file_path: str) -> List[dict]:
    """Extract text page-by-page from a PDF using pypdf."""
    from pypdf import PdfReader  # lazy import – not needed for DOCX/TXT paths

    reader = PdfReader(file_path)
    chunks: List[dict] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            chunks.append({"page": page_num, "text": text})

    logger.info("PDF parsed: %d pages with text content", len(chunks))
    return chunks


async def _parse_docx(file_path: str) -> List[dict]:
    """
    Extract text from a DOCX file.

    DOCX has no native page-break concept accessible via python-docx, so we
    group paragraphs into logical "pages" of roughly 3 000 characters each to
    keep downstream chunking consistent with the PDF flow.
    """
    from docx import Document  # lazy import

    doc = Document(file_path)
    all_paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    chunks: List[dict] = []

    page_num = 1
    current_chars: List[str] = []
    current_len = 0
    page_size_target = 3000

    for para in all_paragraphs:
        current_chars.append(para)
        current_len += len(para)
        if current_len >= page_size_target:
            chunks.append({"page": page_num, "text": "\n".join(current_chars)})
            page_num += 1
            current_chars = []
            current_len = 0

    if current_chars:
        chunks.append({"page": page_num, "text": "\n".join(current_chars)})

    logger.info("DOCX parsed: %d logical page chunks", len(chunks))
    return chunks


async def _parse_txt(file_path: str) -> List[dict]:
    """
    Read a plain-text file and split it into page-sized chunks of ~3 000 chars.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        full_text = fh.read()

    page_size_target = 3000
    chunks: List[dict] = []
    page_num = 1
    start = 0

    while start < len(full_text):
        end = min(start + page_size_target, len(full_text))
        segment = full_text[start:end].strip()
        if segment:
            chunks.append({"page": page_num, "text": segment})
            page_num += 1
        start = end

    logger.info("TXT parsed: %d page chunks", len(chunks))
    return chunks
