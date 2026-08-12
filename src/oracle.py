"""教学校验引擎（Phase 3 远期核心模块）。

Phase 1 仅提供完整函数签名和 docstring，不引入 LLM 依赖。
Phase 3 实现差异分析 + Prompt 构造 + LLM 调用的完整教学流程。
"""


def teach(question: str, files: list[str] | None = None,
          subject: str | None = None, note_type: str | None = None,
          model: str = "local") -> str:
    """🔮 Phase 3 — 教学校验引擎入口。

    Phase 1 行为：打印占位提示，正常退出，不抛出异常。
    """
    print("🔮 教学功能将在 Phase 3 实现。")
    print(f"输入问题: {question}")
    if files:
        print(f"附件文件: {files}")
    if subject:
        print(f"科目过滤: {subject}")
    if note_type:
        print(f"笔记类型过滤: {note_type}")
    return "[Phase 3 占位] 教学功能尚未实现"


def _build_teach_prompt(question: str, note_contexts: list[dict],
                        external_contexts: list[dict]) -> str:
    """构造教学 Prompt。Phase 1 占位。"""
    return ""


def _analyze_discrepancies(note_contexts: list[dict],
                           external_contexts: list[dict]) -> list[str]:
    """差异分析：对比笔记与外部资料，返回冲突/遗漏清单。Phase 1 占位。"""
    return []
