"""searcher 模块的单元测试。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.searcher import search

# 手工构造的索引：三篇笔记
# - 笔记A: 标题含"极限"，exam 类型
# - 笔记B: 正文含"极限"，postgraduate 类型，高频考点
# - 笔记C: 与"极限"无关
INDEX = {
    "documents": {
        "data/notes/微积分/极限与连续.md": {
            "title": "极限与连续",
            "subject": "微积分",
            "chapter": "第一章 极限",
            "tags": ["极限"],
            "note_type": "exam",
            "exam_freq": 5,
        },
        "data/notes/微积分/中值定理与泰勒展开.md": {
            "title": "中值定理与泰勒展开",
            "subject": "微积分",
            "chapter": "第三章",
            "tags": ["泰勒"],
            "note_type": "postgraduate",
            "exam_freq": 4,
        },
        "data/notes/数据结构/二叉树与遍历.md": {
            "title": "二叉树与遍历",
            "subject": "数据结构",
            "chapter": "第五章 树",
            "tags": ["二叉树"],
            "note_type": "exam",
            "exam_freq": 3,
        },
    },
    "inverted_index": {
        "极限": {
            "data/notes/微积分/极限与连续.md": {
                "title": 1, "subject": 0, "chapter": 1, "tags": 1, "body": 8,
            },
            "data/notes/微积分/中值定理与泰勒展开.md": {
                "title": 0, "subject": 0, "chapter": 0, "tags": 0, "body": 2,
            },
        },
        "二叉树": {
            "data/notes/数据结构/二叉树与遍历.md": {
                "title": 1, "subject": 0, "chapter": 0, "tags": 1, "body": 5,
            },
        },
    },
}


class TestSearch(unittest.TestCase):
    """测试关键词搜索、加权排序与过滤。"""

    def test_search_basic(self):
        """测试基本关键词搜索：标题命中排在正文命中之前。"""
        results = search("极限", INDEX)
        self.assertEqual(len(results), 2)
        # 标题+tags+chapter 命中的笔记A得分更高，排第一
        self.assertIn("极限与连续", results[0]["title"])
        # 笔记C 不应出现
        titles = [r["title"] for r in results]
        self.assertNotIn("二叉树与遍历", titles)

    def test_search_weight_title_beats_body(self):
        """测试字段权重：title 命中 1 次 > body 命中 2 次。"""
        results = search("极限", INDEX)
        scores = {r["title"]: r["score"] for r in results}
        self.assertGreater(scores["极限与连续"], scores["中值定理与泰勒展开"])
        # title(1×3) + chapter(1×2) + tags(1×2) + body(8×1) + freq(5/5×0.5=0.5) = 15.5
        self.assertEqual(scores["极限与连续"], 15.5)

    def test_search_filter_exam(self):
        """测试 --type exam 过滤。"""
        results = search("极限", INDEX, note_type="exam")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "极限与连续")

    def test_search_filter_postgraduate(self):
        """测试 --type postgraduate 过滤。"""
        results = search("极限", INDEX, note_type="postgraduate")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "中值定理与泰勒展开")

    def test_search_filter_no_match(self):
        """测试过滤后无匹配时返回空列表。"""
        results = search("二叉树", INDEX, note_type="postgraduate")
        self.assertEqual(results, [])

    def test_search_empty_query(self):
        """测试空查询返回空列表。"""
        self.assertEqual(search("", INDEX), [])
        self.assertEqual(search("   ", INDEX), [])

    def test_search_unknown_term(self):
        """测试索引中不存在的词项返回空列表。"""
        self.assertEqual(search("量子纠缠", INDEX), [])

    def test_search_top_k(self):
        """测试 top_k 截断。"""
        results = search("极限", INDEX, top_k=1)
        self.assertEqual(len(results), 1)

    def test_search_exam_freq_boost(self):
        """测试 exam_freq 加分：正文命中相同但 freq 更高者排前。"""
        freq_index = {
            "documents": {
                "a.md": {"title": "A", "subject": "s", "chapter": "", "tags": [],
                         "note_type": "exam", "exam_freq": 0},
                "b.md": {"title": "B", "subject": "s", "chapter": "", "tags": [],
                         "note_type": "exam", "exam_freq": 5},
            },
            "inverted_index": {
                "算法": {
                    "a.md": {"title": 0, "subject": 0, "chapter": 0, "tags": 0, "body": 1},
                    "b.md": {"title": 0, "subject": 0, "chapter": 0, "tags": 0, "body": 1},
                },
            },
        }
        results = search("算法", freq_index)
        self.assertEqual(results[0]["title"], "B")  # 1.0 + 0.5 > 1.0 + 0.0


if __name__ == "__main__":
    unittest.main()
