"""向量检索器（Phase 3 远期占位）。

Phase 1-2 不实现 ChromaDB 依赖，调用时抛出 NotImplementedError。
"""


class VectorRetriever:
    """基于 ChromaDB 的向量检索器。Phase 1 占位。"""

    def __init__(self, collection_name: str = "nju_notes"):
        raise NotImplementedError("VectorRetriever 将在 Phase 3 实现")

    def index_notes(self, notes: list) -> None:
        raise NotImplementedError("Phase 3")

    def index_external(self, docs: list) -> None:
        raise NotImplementedError("Phase 3")

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError("Phase 3")
