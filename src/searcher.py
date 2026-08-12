"""关键词搜索引擎。

加载倒排索引，解析用户查询，按字段权重排序返回匹配笔记。
"""


def search(query: str, index: dict, note_type: str | None = None, top_k: int = 10) -> list[dict]:
    """关键词检索，按权重排序。"""
    raise NotImplementedError("search 将在后续 Phase 1 任务中实现")


def retrieve_for_rag(query: str, top_k: int = 5, include_external: bool = True) -> list[dict]:
    """Phase 3 — 为 RAG 检索上下文。Phase 1 返回空列表。"""
    print("[Phase 3] RAG 检索功能尚未实现")
    return []
