"""PPTX 解析器（Phase 3 远期占位）。

Phase 1-2 不实现，调用时抛出 NotImplementedError。
"""

from pathlib import Path

from src.models import ExternalDocument


def parse_pptx(file_path: Path, chunk_size: int = 500) -> ExternalDocument:
    """解析 PPTX 文件，提取纯文本并分块（按幻灯片）。"""
    raise NotImplementedError("PPTX 解析将在 Phase 3 实现")
