"""NJUCSKeeper — 本地化计算机课程知识中台 CLI 入口。

用法:
    python main.py index              # 构建倒排索引
    python main.py search "关键词"     # 关键词搜索
    python main.py teach "问题"        # 教学校验（Phase 3 远期）
    python main.py cleanup-cache      # 清空外部资料缓存
"""

import argparse
import sys

from src.oracle import teach as oracle_teach


def cmd_index(args: argparse.Namespace) -> int:
    """构建倒排索引。"""
    from src.indexer import build_index, save_index, generate_sample_notes
    from pathlib import Path

    notes_root = Path("data/notes")
    if not notes_root.exists() or not any(notes_root.iterdir()):
        print("📝 未检测到笔记文件，正在生成示例笔记...")
        generate_sample_notes(notes_root)

    print("🔍 正在构建倒排索引...")
    index = build_index(notes_root)
    save_index(index, Path("data/index/index.json"))
    print("✅ 索引构建完成。")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """关键词搜索。"""
    from src.searcher import search
    from src.indexer import load_index
    from pathlib import Path

    index_path = Path("data/index/index.json")
    if not index_path.exists():
        print("❌ 尚未构建索引，请先运行: python main.py index")
        return 1

    index = load_index(index_path)
    results = search(args.query, index, note_type=args.type, top_k=args.top)

    if not results:
        print(f"未找到与「{args.query}」相关的结果。")
        return 0

    print(f"\n搜索「{args.query}」的结果（共 {len(results)} 条）：\n")
    for i, r in enumerate(results, 1):
        type_label = "📗 期末" if r["note_type"] == "exam" else "📘 考研"
        print(f"  [{i}] {r['title']}  |  {type_label}  |  score: {r['score']:.1f}")
        print(f"      科目: {r['subject']}  |  章节: {r['chapter']}")
        print(f"      路径: {r['path']}\n")
    return 0


def cmd_teach(args: argparse.Namespace) -> int:
    """教学校验（Phase 3 远期占位）。"""
    response = oracle_teach(
        question=args.question,
        files=args.files,
        subject=args.subject,
        note_type=args.type,
    )
    if response:
        print(response)
    return 0


def cmd_cleanup_cache(args: argparse.Namespace) -> int:
    """清空外部资料缓存。"""
    from pathlib import Path
    import shutil
    import json

    external_dir = Path("data/external")
    manifest_path = Path("data/index/external_manifest.json")

    # 收集将要清理的文件
    to_delete = []
    if external_dir.exists():
        to_delete.extend(
            str(p) for p in external_dir.iterdir() if p.name != ".gitkeep"
        )
    if manifest_path.exists():
        to_delete.append(str(manifest_path))

    if args.dry_run:
        print(f"🔍 缓存清理预览（--dry-run 模式，未实际删除）：")
        for f in to_delete:
            print(f"  将删除: {f}")
        print(f"共 {len(to_delete)} 个文件/目录将被清理。")
        return 0

    for f in to_delete:
        path = Path(f)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"  已删除: {f}")

    print(f"✅ 缓存清理完成，共删除 {len(to_delete)} 个文件/目录。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="NJUCSKeeper",
        description="本地化计算机课程知识中台 — 笔记管理与教学校验",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # index
    subparsers.add_parser("index", help="构建倒排索引（空仓时自动生成示例笔记）")

    # search
    sp_search = subparsers.add_parser("search", help="关键词搜索笔记")
    sp_search.add_argument("query", type=str, help="搜索关键词")
    sp_search.add_argument("--type", dest="type", choices=["exam", "postgraduate"],
                           default=None, help="按笔记类型过滤")
    sp_search.add_argument("--top", type=int, default=10, help="返回结果数（默认 10）")

    # teach
    sp_teach = subparsers.add_parser("teach", help="教学校验（Phase 3 远期占位）")
    sp_teach.add_argument("question", type=str, help="问题文本")
    sp_teach.add_argument("--files", nargs="*", default=None, help="外部文件路径列表")
    sp_teach.add_argument("--subject", type=str, default=None, help="科目过滤")
    sp_teach.add_argument("--type", dest="type", choices=["exam", "postgraduate"],
                          default=None, help="笔记类型过滤")

    # cleanup-cache
    sp_cleanup = subparsers.add_parser("cleanup-cache", help="清空外部资料缓存")
    sp_cleanup.add_argument("--dry-run", action="store_true", default=False,
                            help="仅列出将被清理的文件，不实际删除")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "index": cmd_index,
        "search": cmd_search,
        "teach": cmd_teach,
        "cleanup-cache": cmd_cleanup_cache,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
