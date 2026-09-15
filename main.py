"""NoteManager — 本地化计算机课程知识中台 CLI 入口。

用法:
    python main.py index              # 构建倒排索引
    python main.py search "关键词"     # 关键词搜索
    python main.py gui                # 启动图形界面
    python main.py teach "问题"        # 教学校验（Phase 3 远期）
    python main.py cleanup-cache      # 清空外部资料缓存
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

# 项目根目录。打包后以 PyInstaller 的运行目录为基准，确保随包资源可被定位。
BASE_DIR = (
    Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
NOTES_ROOT = BASE_DIR / "data" / "notes"
EXTERNAL_DIR = BASE_DIR / "data" / "external"
INDEX_PATH = BASE_DIR / "data" / "index" / "index.json"
MANIFEST_PATH = BASE_DIR / "data" / "index" / "external_manifest.json"

from src.oracle import teach as oracle_teach


def cmd_index(args: argparse.Namespace) -> int:
    """构建倒排索引。"""
    from src.indexer import build_index, generate_sample_notes, save_index
    from src.storage import sync_note_catalog

    if not NOTES_ROOT.exists() or not any(NOTES_ROOT.rglob("*.md")):
        print("笔记目录为空，正在生成示例笔记...")
        generate_sample_notes(NOTES_ROOT)

    print("正在构建倒排索引...")
    index = build_index(NOTES_ROOT, base_dir=BASE_DIR)
    save_index(index, INDEX_PATH)
    database_path = INDEX_PATH.with_name("notemanager.db")
    try:
        synced_count = sync_note_catalog(index, BASE_DIR, database_path)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"错误: SQLite 笔记目录同步失败: {exc}")
        return 1
    print(f"索引构建完成，共 {synced_count} 篇笔记，SQLite 目录已同步。")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """关键词搜索。"""
    from src.indexer import load_index
    from src.searcher import search

    if not INDEX_PATH.exists():
        print("错误: 尚未构建索引，请先运行: python main.py index")
        return 1

    index = load_index(INDEX_PATH)
    results = search(args.query, index, note_type=args.type,
                     top_k=args.top, subject=args.subject,
                     exclude_tag=args.exclude_tag)

    if not results:
        print(f"未找到与「{args.query}」相关的结果。")
        return 0

    print(f"\n搜索「{args.query}」的结果（共 {len(results)} 条）：\n")
    for i, r in enumerate(results, 1):
        type_label = "[期末]" if r["note_type"] == "exam" else "[考研]"
        print(f"  [{i}] {r['title']}  |  {type_label}  |  score: {r['score']:.1f}")
        print(f"      科目: {r['subject']}  |  章节: {r['chapter']}")
        print(f"      路径: {r['path']}\n")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    """启动 PyQt6 图形界面。"""
    from src.gui import run_gui

    try:
        return run_gui(BASE_DIR, NOTES_ROOT, INDEX_PATH)
    except RuntimeError as exc:
        print(f"错误: {exc}")
        return 1


def cmd_teach(args: argparse.Namespace) -> int:
    """Run an explicitly configured, read-only teaching request."""
    import os
    from src.teaching_config import TeachingConfig

    config = TeachingConfig(
        provider=args.model, model=args.model_name or os.getenv("NOTEMANAGER_MODEL", ""),
        base_url=args.base_url or os.getenv("NOTEMANAGER_BASE_URL", "") or (
            "https://api.openai.com/v1" if args.model == "api" else "http://localhost:11434"),
        timeout=args.timeout, top_k=args.top, include_samples=args.include_samples,
    )
    try:
        response = oracle_teach(question=args.question, files=args.files,
                                subject=args.subject, note_type=args.type, config=config,
                                notes_root=NOTES_ROOT,
                                cache_dir=EXTERNAL_DIR if args.keep_cache else None)
        print(response)
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"教学请求未完成: {exc}")
        return 1
    except Exception as exc:
        print(f"教学请求未完成（{type(exc).__name__}），请检查可选依赖与模型设置。")
        return 1


def cmd_cleanup_cache(args: argparse.Namespace) -> int:
    """清空外部资料缓存。"""
    # 收集将被清理的条目
    to_delete: list[Path] = []
    if EXTERNAL_DIR.exists():
        to_delete.extend(p for p in EXTERNAL_DIR.iterdir() if p.name != ".gitkeep")
    if MANIFEST_PATH.exists():
        to_delete.append(MANIFEST_PATH)

    if args.dry_run:
        print("缓存清理预览（--dry-run 模式，未实际删除）：")
        for f in to_delete:
            print(f"  将删除: {f}")
        print(f"共 {len(to_delete)} 个文件/目录将被清理。")
        return 0

    for f in to_delete:
        if f.is_dir():
            shutil.rmtree(f)
        else:
            f.unlink()
        print(f"  已删除: {f}")

    print(f"缓存清理完成，共删除 {len(to_delete)} 个文件/目录。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="NoteManager",
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
    sp_search.add_argument("--subject", type=str, default=None, help="按科目过滤")
    sp_search.add_argument("--exclude-tag", type=str, default=None,
                           help="排除带有该标签的笔记")
    sp_search.add_argument("--top", type=int, default=10, help="返回结果数（默认 10）")

    # gui
    subparsers.add_parser("gui", help="启动图形界面")

    # teach
    sp_teach = subparsers.add_parser("teach", help="教学校验（仅发送召回片段，远程 API 可能计费）")
    sp_teach.add_argument("question", type=str, help="问题文本")
    sp_teach.add_argument("--files", nargs="*", default=None, help="外部文件路径列表")
    sp_teach.add_argument("--subject", type=str, default=None, help="科目过滤")
    sp_teach.add_argument("--model", choices=["disabled", "local", "api"], default="disabled",
                          help="显式启用 Ollama(local) 或兼容 API(api)，默认关闭")
    sp_teach.add_argument("--model-name", help="模型名称，也可设置 NOTEMANAGER_MODEL")
    sp_teach.add_argument("--base-url", help="服务地址，也可设置 NOTEMANAGER_BASE_URL")
    sp_teach.add_argument("--timeout", type=int, default=60, help="请求超时秒数（5–300）")
    sp_teach.add_argument("--top", type=int, default=5, help="每类来源的召回片段数（1–20）")
    sp_teach.add_argument("--include-samples", action="store_true", help="允许引用示例笔记")
    sp_teach.add_argument("--keep-cache", action="store_true", help="保留附件提取的文本至手动清理")
    sp_teach.add_argument("--type", dest="type", choices=["exam", "postgraduate"],
                          default=None, help="笔记类型过滤")

    # cleanup-cache
    sp_cleanup = subparsers.add_parser("cleanup-cache", help="清空外部资料缓存")
    sp_cleanup.add_argument("--dry-run", action="store_true", default=False,
                            help="仅列出将被清理的文件，不实际删除")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "index": cmd_index,
        "search": cmd_search,
        "gui": cmd_gui,
        "teach": cmd_teach,
        "cleanup-cache": cmd_cleanup_cache,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
