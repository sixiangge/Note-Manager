"""Markdown 笔记解析器。

解析 .md 文件，分离 YAML Front-matter 元数据与正文，构造 Note 对象。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal

import frontmatter

VALID_NOTE_TYPES = ("exam", "postgraduate")
VALID_EXAM_FREQ = (0, 1, 2, 3, 4, 5)


@dataclass
class Note:
    """笔记数据模型。"""

    title: str                                      # 笔记标题
    subject: str                                    # 所属科目，如"微积分"
    chapter: str                                    # 章节，如"第一章 极限与连续"
    tags: List[str] = field(default_factory=list)   # 标签列表
    note_type: Literal["exam", "postgraduate"] = "exam"  # 笔记类型
    exam_freq: int = 0                              # 考点频率 0-5
    body: str = ""                                  # Markdown 正文（不含 Front-matter）
    file_path: Path | None = None                   # 源文件路径


def parse_markdown(file_path: Path) -> Note:
    """解析 .md 文件，提取 Front-matter 和正文。

    Args:
        file_path: Markdown 文件的路径

    Returns:
        Note 对象，包含元数据和正文

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: Front-matter 格式错误或缺少必填字段
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with file_path.open(encoding="utf-8") as f:
        post = frontmatter.load(f)

    if not post.metadata:
        raise ValueError(f"缺少 YAML Front-matter: {file_path}")

    note = extract_metadata_from_frontmatter(post.metadata, file_path)
    note.body = post.content.strip()
    errors = validate_note(note)
    if errors:
        raise ValueError(f"笔记校验失败 {file_path}: {'; '.join(errors)}")
    return note


def extract_metadata_from_frontmatter(metadata: dict, file_path: Path) -> Note:
    """从 python-frontmatter 解析出的元数据字典构造 Note 对象。

    Args:
        metadata: Front-matter 元数据字典
        file_path: 源文件路径

    Returns:
        Note 对象（body 留空，由调用方填充）
    """
    # tags 兼容两种写法：列表 ["a", "b"] 或字符串 "a, b"
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
    if not isinstance(tags, list):
        tags = []

    note_type = metadata.get("note_type", "exam")
    if not isinstance(note_type, str):
        note_type = str(note_type)

    # exam_freq 非法值记为 -1，交由 validate_note 报告
    try:
        exam_freq = int(metadata.get("exam_freq", 0))
    except (TypeError, ValueError):
        exam_freq = -1

    return Note(
        title=str(metadata.get("title", "")).strip(),
        subject=str(metadata.get("subject", "")).strip(),
        chapter=str(metadata.get("chapter", "")).strip(),
        tags=tags,
        note_type=note_type,
        exam_freq=exam_freq,
        file_path=Path(file_path),
    )


def validate_note(note: Note) -> list[str]:
    """校验 Note 对象字段合法性，返回错误信息列表。

    校验规则：
      - title 非空
      - subject 非空
      - note_type ∈ {exam, postgraduate}
      - exam_freq ∈ {0, 1, 2, 3, 4, 5}
      - body 非空

    Args:
        note: 待校验的 Note 对象

    Returns:
        错误信息列表，空列表表示校验通过
    """
    errors: list[str] = []
    if not note.title:
        errors.append("title 不能为空")
    if not note.subject:
        errors.append("subject 不能为空")
    if note.note_type not in VALID_NOTE_TYPES:
        errors.append(f"note_type 必须为 {VALID_NOTE_TYPES} 之一，实际为 {note.note_type!r}")
    if note.exam_freq not in VALID_EXAM_FREQ:
        errors.append(f"exam_freq 必须在 0-5 之间，实际为 {note.exam_freq}")
    if not note.body:
        errors.append("正文不能为空")
    return errors
