"""关键词搜索引擎。

加载倒排索引，解析用户查询，按字段权重排序返回匹配笔记。
权重规则见 plan.md §4.2。
"""

import jieba

# 字段权重：title 最高，body 最低
FIELD_WEIGHTS = {
    "title": 3.0,
    "subject": 2.0,
    "chapter": 2.0,
    "tags": 2.0,
    "body": 1.0,
}


def _tokenize_query(query: str) -> list[str]:
    """对查询进行 jieba 分词（搜索引擎模式），保序去重。

    Args:
        query: 查询文本

    Returns:
        词项列表
    """
    if not query or not query.strip():
        return []
    tokens = [t.strip() for t in jieba.cut_for_search(query) if t.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def search(query: str, index: dict, note_type: str | None = None,
           top_k: int = 10) -> list[dict]:
    """关键词检索，按权重排序。

    Args:
        query: 搜索关键词
        index: 倒排索引字典（结构见 plan.md §4.1）
        note_type: 过滤条件，None=全部, 'exam' 或 'postgraduate'
        top_k: 返回前 K 个结果

    Returns:
        [{path, title, subject, chapter, tags, note_type, exam_freq, score}]，
        按 score 降序

    算法：
        score(d, t) = title_tf×3 + subject_tf×2 + chapter_tf×2
                    + tags_tf×2 + body_tf×1
        total = Σ score(d, t) + (exam_freq / 5) × 0.5
    """
    tokens = _tokenize_query(query)
    if not tokens:
        return []

    documents: dict = index.get("documents", {})
    inverted_index: dict = index.get("inverted_index", {})

    # 累加每个匹配文档的得分
    scores: dict[str, float] = {}
    for token in tokens:
        postings = inverted_index.get(token, {})
        for path, field_tfs in postings.items():
            doc_score = 0.0
            for field, tf in field_tfs.items():
                doc_score += tf * FIELD_WEIGHTS.get(field, 1.0)
            scores[path] = scores.get(path, 0.0) + doc_score

    # 构造结果并应用 exam_freq 加分与类型过滤
    results: list[dict] = []
    for path, score in scores.items():
        doc = documents.get(path)
        if doc is None:
            continue
        if note_type is not None and doc.get("note_type") != note_type:
            continue
        score += (doc.get("exam_freq", 0) / 5.0) * 0.5
        results.append({
            "path": path,
            "title": doc.get("title", ""),
            "subject": doc.get("subject", ""),
            "chapter": doc.get("chapter", ""),
            "tags": doc.get("tags", []),
            "note_type": doc.get("note_type", "exam"),
            "exam_freq": doc.get("exam_freq", 0),
            "score": round(score, 2),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def retrieve_for_rag(query: str, top_k: int = 5, include_external: bool = True) -> list[dict]:
    """🔮 Phase 3 — 为 RAG 检索上下文。

    Phase 1 行为：打印提示并返回空列表。保留完整类型注解。

    Args:
        query: 用户问题
        top_k: 返回片段数
        include_external: 是否包含外部资料

    Returns:
        [{source_type: 'note'|'external', content, metadata}]
    """
    print("[Phase 3] RAG 检索功能尚未实现")
    return []
