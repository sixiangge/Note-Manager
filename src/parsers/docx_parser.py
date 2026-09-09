"""Read Word text without Office or extracting attachment images."""

from pathlib import Path

from src.models import ExternalDocument
from src.parsers.external import document_from_text


def parse_docx(file_path: Path, chunk_size: int = 500) -> ExternalDocument:
    """Extract paragraphs and tables.

    Args:
        file_path: Word document path.
        chunk_size: Maximum characters per chunk.

    Returns:
        Parsed external document.
    """
    import docx2txt

    path = Path(file_path)
    return document_from_text(path, docx2txt.process(str(path)), chunk_size)
