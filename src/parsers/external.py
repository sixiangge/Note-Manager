"""Bounded extraction, dispatch and optional content-addressed text cache."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4
import zipfile

from src.models import ExternalDocument

MAX_TEXT_CHARS = 2_000_000


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into overlapping chunks without dropping characters.

    Args:
        text: Extracted text.
        chunk_size: Maximum characters per chunk.

    Returns:
        Ordered nonempty chunks.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size 必须为正数")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("文本超过两百万字符，请拆分文档。")
    step = max(1, chunk_size - min(50, chunk_size // 10))
    return [text[start:start + chunk_size].strip()
            for start in range(0, len(text), step)
            if text[start:start + chunk_size].strip()]


def validate_file(path: Path, max_file_mb: int = 20) -> Path:
    """Validate an attachment without copying or modifying it."""
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > max_file_mb * 1024 * 1024:
        raise ValueError(f"文件无效或超过 {max_file_mb} MB：{path.name}")
    if path.suffix.lower() in {".pptx", ".docx"}:
        with zipfile.ZipFile(path) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("Office 文档解压后超过 100 MB，请拆分。")
    return path


def document_from_text(path: Path, text: str, chunk_size: int) -> ExternalDocument:
    """Identify extracted text using filename and content hash."""
    chunks = chunk_text(text, chunk_size)
    if not chunks:
        raise ValueError("未提取到文本；扫描件/图片需先 OCR，本项目不自动 OCR。")
    digest = hashlib.sha256(path.name.encode("utf-8") + path.read_bytes()).hexdigest()
    return ExternalDocument(digest, path, chunks=chunks,
                            doc_type="PPT" if path.suffix.lower() == ".pptx" else "其他")


def parse_external(path: Path, chunk_size: int = 500, max_file_mb: int = 20,
                   allowed_types: str = ".pdf,.pptx,.docx,.txt",
                   cache_dir: Path | None = None) -> ExternalDocument:
    """Parse one attachment; cache text only when explicitly enabled."""
    path = validate_file(path, max_file_mb)
    suffix = path.suffix.lower()
    if suffix not in allowed_types.lower().replace(" ", "").split(","):
        raise ValueError(f"不允许上传此类型：{suffix}")
    cache_path = None
    if cache_dir is not None:
        digest = hashlib.sha256(path.name.encode("utf-8") + path.read_bytes()).hexdigest()
        cache_path = Path(cache_dir) / f"parsed-v1-{digest}-{chunk_size}.json"
        try:
            chunks = json.loads(cache_path.read_text(encoding="utf-8"))
            if (isinstance(chunks, list) and chunks and
                    all(isinstance(chunk, str) and 0 < len(chunk) <= chunk_size for chunk in chunks) and
                    sum(map(len, chunks)) <= MAX_TEXT_CHARS * 2):
                return ExternalDocument(digest, path, chunks=chunks,
                                        doc_type="PPT" if suffix == ".pptx" else "其他")
        except (OSError, ValueError):
            pass
    if suffix == ".txt":
        doc = document_from_text(path, path.read_text(encoding="utf-8-sig"), chunk_size)
    else:
        from src.parsers.pdf_parser import parse_pdf
        from src.parsers.pptx_parser import parse_pptx
        from src.parsers.docx_parser import parse_docx
        parsers = {".pdf": parse_pdf, ".pptx": parse_pptx, ".docx": parse_docx}
        if suffix not in parsers:
            raise ValueError(f"不支持的类型：{suffix}")
        doc = parsers[suffix](path, chunk_size)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(doc.chunks, ensure_ascii=False), encoding="utf-8")
            temporary.replace(cache_path)
        finally:
            temporary.unlink(missing_ok=True)
    return doc
