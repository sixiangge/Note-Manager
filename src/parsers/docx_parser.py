"""DOCX 解析器（Phase 3 远期占位）。

Phase 1-2 不实现，调用时抛出 NotImplementedError。
"""

from pathlib import Path

from src.models import ExternalDocument


def parse_docx(file_path: Path, chunk_size: int = 500) -> ExternalDocument:
    """解析 DOCX 文件，提取纯文本并分块（按段落）。"""
    raise NotImplementedError("DOCX 解析将在 Phase 3 实现")
