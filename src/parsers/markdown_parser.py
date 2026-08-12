"""Markdown 笔记解析器。

解析 .md 文件，分离 YAML Front-matter 元数据与正文，构造 Note 对象。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal


@dataclass
class Note:
    """笔记数据模型。"""
    title: str
    subject: str
    chapter: str
    tags: List[str] = field(default_factory=list)
    note_type: Literal["exam", "postgraduate"] = "exam"
    exam_freq: int = 0
    body: str = ""
    file_path: Path | None = None


def parse_markdown(file_path: Path) -> Note:
    """解析 .md 文件，提取 Front-matter 和正文。"""
    raise NotImplementedError("parse_markdown 将在后续 Phase 1 任务中实现")


def validate_note(note: Note) -> list[str]:
    """校验 Note 对象字段合法性，返回错误信息列表。"""
    raise NotImplementedError("validate_note 将在后续 Phase 1 任务中实现")
