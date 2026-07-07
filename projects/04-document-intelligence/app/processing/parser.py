"""
Project 4 – Document Intelligence
IBM Docling-based document parser + chunker
"""
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Uses IBM Docling for rich PDF/DOCX/PPTX/HTML parsing.
    Falls back to plain text for unsupported formats.
    """

    SUPPORTED_FORMATS = {"pdf", "docx", "pptx", "html", "xlsx", "txt", "md"}

    def parse(self, file_path: str, filename: str) -> str:
        """Parse a document and return its text content."""
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {suffix}")

        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.pipeline_options import PipelineOptions, OcrOptions

            options = PipelineOptions()
            options.do_ocr = True
            options.do_table_structure = True

            converter = DocumentConverter()
            result = converter.convert(file_path)
            text = result.document.export_to_markdown()
            logger.info("Parsed %s via Docling (%d chars)", filename, len(text))
            return text
        except ImportError:
            logger.warning("Docling not installed, falling back to plain text for %s", filename)
            return Path(file_path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.exception("Docling parse error for %s: %s", filename, exc)
            raise

    def chunk_text(
        self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100
    ) -> List[str]:
        """Simple recursive character text splitter."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)


document_parser = DocumentParser()
