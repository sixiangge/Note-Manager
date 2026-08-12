"""倒排索引构建模块。

遍历 data/notes/ 下所有 .md 文件，构建关键词倒排索引。
不索引 data/external/ 中的外部资料。
"""

from pathlib import Path


def build_index(notes_root: Path | None = None) -> dict:
    """扫描笔记目录，构建倒排索引。"""
    raise NotImplementedError("build_index 将在后续 Phase 1 任务中实现")


def save_index(index: dict, output_path: Path) -> None:
    """将索引持久化为 JSON 文件。"""
    raise NotImplementedError("save_index 将在后续 Phase 1 任务中实现")


def load_index(index_path: Path) -> dict:
    """从 JSON 文件加载索引。"""
    raise NotImplementedError("load_index 将在后续 Phase 1 任务中实现")


def generate_sample_notes(notes_root: Path) -> None:
    """空仓启动时生成 5 篇示例笔记。"""
    raise NotImplementedError("generate_sample_notes 将在后续 Phase 1 任务中实现")
