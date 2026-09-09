"""PDF text extraction; image-only pages require external OCR."""

from pathlib import Path

from src.models import ExternalDocument
from src.parsers.external import document_from_text


def parse_pdf(file_path: Path, chunk_size: int = 500) -> ExternalDocument:
    """Extract page-labelled text into chunks.

    Args:
        file_path: PDF path.
        chunk_size: Maximum characters per chunk.

    Returns:
        Parsed document; raises ValueError for empty or locked PDFs.
    """
    from pypdf import PdfReader

    path = Path(file_path)
    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("PDF 已加密，请先解密后上传。")
    pages = []
    for number, page in enumerate(reader.pages, 1):
        content = (page.extract_text() or "").strip()
        if content:
            pages.append(f"[第 {number} 页]\n{content}")
    return document_from_text(path, "\n\n".join(pages), chunk_size)
