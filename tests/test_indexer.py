"""indexer 模块的单元测试。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.indexer import (
    build_index,
    generate_sample_notes,
    load_index,
    save_index,
)

NOTE_CONTENT = """---
title: "极限与连续"
subject: "微积分"
chapter: "第一章 极限与连续"
tags: ["极限", "ε-δ定义"]
note_type: "postgraduate"
exam_freq: 5
---

# 极限的定义

极限是微积分的基础概念，数列极限与函数极限都需要掌握。
函数极限的 ε-δ 定义是期末考试的重点内容。
"""

NOTE_BAD = """没有 frontmatter 的坏文件
"""

NOTE_EXAM = """---
title: "二叉树与遍历"
subject: "数据结构"
chapter: "第五章"
tags: ["二叉树"]
note_type: "exam"
exam_freq: 3
---

二叉树的四种遍历方式：前序、中序、后序与层序遍历。
"""


def _make_notes_dir(files: dict[str, str]) -> Path:
    """创建临时笔记目录，files 为 {相对路径: 内容}。"""
    tmp = Path(tempfile.mkdtemp()) / "data" / "notes"
    tmp.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


class TestBuildIndex(unittest.TestCase):
    """测试倒排索引构建。"""

    def test_build_index_empty_dir(self):
        """测试空目录下构建索引返回空索引。"""
        notes = _make_notes_dir({})
        index = build_index(notes)
        self.assertEqual(index["documents"], {})
        self.assertEqual(index["inverted_index"], {})

    def test_build_index_nonexistent_dir(self):
        """测试目录不存在时抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            build_index(Path(tempfile.mkdtemp()) / "不存在")

    def test_build_index_with_notes(self):
        """测试有笔记时构建索引：文档条目与词项统计正确。"""
        notes = _make_notes_dir({"微积分/极限与连续.md": NOTE_CONTENT,
                                 "数据结构/二叉树.md": NOTE_EXAM})
        index = build_index(notes)

        # 文档条目
        docs = index["documents"]
        self.assertEqual(len(docs), 2)
        keys = sorted(docs.keys())
        self.assertTrue(keys[0].endswith("微积分/极限与连续.md"))
        self.assertEqual(docs[keys[0]]["note_type"], "postgraduate")
        self.assertEqual(docs[keys[0]]["exam_freq"], 5)
        self.assertEqual(docs[keys[1]]["note_type"], "exam")

        # 倒排索引：title 中的"极限"应命中 title 字段
        inv = index["inverted_index"]
        self.assertIn("极限", inv)
        target = keys[0]
        self.assertIn(target, inv["极限"])
        self.assertEqual(inv["极限"][target]["title"], 1)
        self.assertGreater(inv["极限"][target]["body"], 0)

        # "二叉树" 只出现在第二篇
        self.assertNotIn(keys[0], inv.get("二叉树", {}))

    def test_build_index_skips_bad_files(self):
        """测试解析失败的文件被跳过，不中断索引构建。"""
        notes = _make_notes_dir({"好的/正常笔记.md": NOTE_EXAM,
                                 "坏的/无元数据.md": NOTE_BAD})
        index = build_index(notes)
        self.assertEqual(len(index["documents"]), 1)


class TestSaveLoadIndex(unittest.TestCase):
    """测试索引的持久化与加载。"""

    def test_round_trip(self):
        """测试 save → load 往返一致。"""
        notes = _make_notes_dir({"微积分/极限.md": NOTE_CONTENT})
        index = build_index(notes)
        out = Path(tempfile.mkdtemp()) / "index.json"
        save_index(index, out)

        # 文件为 UTF-8 JSON，中文未转义
        raw = out.read_text(encoding="utf-8")
        self.assertIn("极限", raw)

        loaded = load_index(out)
        self.assertEqual(loaded, index)

    def test_load_missing_file(self):
        """测试加载不存在的索引抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            load_index(Path(tempfile.mkdtemp()) / "none.json")


class TestGenerateSampleNotes(unittest.TestCase):
    """测试示例笔记生成。"""

    def test_generate_sample_notes(self):
        """测试生成 5 篇示例笔记，覆盖 3 门科目与两种 note_type。"""
        notes = Path(tempfile.mkdtemp())
        generate_sample_notes(notes)

        md_files = sorted(notes.rglob("*.md"))
        self.assertEqual(len(md_files), 5)

        index = build_index(notes)
        docs = index["documents"].values()
        subjects = {d["subject"] for d in docs}
        types = {d["note_type"] for d in docs}
        self.assertEqual(subjects, {"微积分", "数据结构", "机器学习导论"})
        self.assertEqual(types, {"exam", "postgraduate"})

        # 每篇正文不少于 200 字
        for f in md_files:
            body = f.read_text(encoding="utf-8").split("---", 2)[2]
            self.assertGreaterEqual(len(body), 200, f"正文过短: {f}")

    def test_generate_sample_notes_idempotent(self):
        """测试已存在的笔记不会被覆盖。"""
        notes = Path(tempfile.mkdtemp())
        generate_sample_notes(notes)

        target = notes / "微积分" / "[示例]极限与连续.md"
        original = target.read_text(encoding="utf-8")
        target.write_text("用户自己的内容\n", encoding="utf-8")

        generate_sample_notes(notes)
        self.assertEqual(target.read_text(encoding="utf-8"), "用户自己的内容\n")


if __name__ == "__main__":
    unittest.main()
