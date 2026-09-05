"""markdown_parser 模块的单元测试。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parsers.markdown_parser import (
    Note,
    extract_metadata_from_frontmatter,
    parse_markdown,
    validate_note,
)

VALID_FRONTMATTER = """---
title: "极限与连续"
subject: "微积分"
chapter: "第一章 极限与连续"
tags: ["极限", "ε-δ定义", "连续函数"]
note_type: "postgraduate"
exam_freq: 5
---
"""


def make_note_file(content: str) -> Path:
    """在临时目录中创建一篇笔记，返回文件路径。"""
    tmp_dir = tempfile.mkdtemp()
    path = Path(tmp_dir) / "测试笔记.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestParseMarkdown(unittest.TestCase):
    """测试 parse_markdown 的解析与异常路径。"""

    def test_parse_markdown_valid(self):
        """测试解析有效的 Markdown 文件。"""
        path = make_note_file(VALID_FRONTMATTER + "\n## 正文\n\n极限的定义是...\n")
        note = parse_markdown(path)
        self.assertEqual(note.title, "极限与连续")
        self.assertEqual(note.subject, "微积分")
        self.assertEqual(note.chapter, "第一章 极限与连续")
        self.assertEqual(note.tags, ["极限", "ε-δ定义", "连续函数"])
        self.assertEqual(note.note_type, "postgraduate")
        self.assertEqual(note.exam_freq, 5)
        self.assertIn("极限的定义", note.body)

    def test_parse_markdown_missing_frontmatter(self):
        """测试解析缺少 Front-matter 的文件时抛出 ValueError。"""
        path = make_note_file("没有 frontmatter 的纯正文\n")
        with self.assertRaises(ValueError):
            parse_markdown(path)

    def test_parse_markdown_missing_file(self):
        """测试解析不存在的文件时抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            parse_markdown(Path(tempfile.mkdtemp()) / "不存在.md")

    def test_parse_markdown_invalid_type(self):
        """测试 note_type 非法时抛出 ValueError。"""
        content = VALID_FRONTMATTER.replace('note_type: "postgraduate"',
                                            'note_type: "weekly"')
        path = make_note_file(content + "正文\n")
        with self.assertRaises(ValueError):
            parse_markdown(path)

    def test_parse_markdown_invalid_exam_freq(self):
        """测试 exam_freq 超出范围时抛出 ValueError。"""
        content = VALID_FRONTMATTER.replace("exam_freq: 5", "exam_freq: 9")
        path = make_note_file(content + "正文\n")
        with self.assertRaises(ValueError):
            parse_markdown(path)

    def test_parse_markdown_empty_body(self):
        """测试正文为空时抛出 ValueError。"""
        path = make_note_file(VALID_FRONTMATTER + "\n")
        with self.assertRaises(ValueError):
            parse_markdown(path)

    def test_parse_markdown_tags_as_string(self):
        """测试 tags 为逗号分隔字符串时的兼容解析。"""
        content = VALID_FRONTMATTER.replace('tags: ["极限", "ε-δ定义", "连续函数"]',
                                            'tags: "极限, ε-δ定义"')
        path = make_note_file(content + "正文\n")
        note = parse_markdown(path)
        self.assertEqual(note.tags, ["极限", "ε-δ定义"])

    def test_parse_markdown_default_fields(self):
        """测试 Front-matter 省略可选字段时使用默认值。"""
        content = """---
title: "最小笔记"
subject: "微积分"
---
正文内容
"""
        path = make_note_file(content)
        note = parse_markdown(path)
        self.assertEqual(note.note_type, "exam")
        self.assertEqual(note.exam_freq, 0)
        self.assertEqual(note.chapter, "")
        self.assertEqual(note.tags, [])


class TestValidateNote(unittest.TestCase):
    """测试 validate_note 的校验规则。"""

    def _make_note(self, **overrides) -> Note:
        kwargs = dict(
            title="测试笔记", subject="微积分", chapter="第一章",
            tags=[], note_type="exam", exam_freq=0, body="正文",
        )
        kwargs.update(overrides)
        return Note(**kwargs)

    def test_validate_note_valid(self):
        """测试校验合法 Note 返回空列表。"""
        self.assertEqual(validate_note(self._make_note()), [])

    def test_validate_note_empty_title(self):
        """测试 title 为空时报错。"""
        errors = validate_note(self._make_note(title=""))
        self.assertTrue(any("title" in e for e in errors))

    def test_validate_note_empty_subject(self):
        """测试 subject 为空时报错。"""
        errors = validate_note(self._make_note(subject=""))
        self.assertTrue(any("subject" in e for e in errors))

    def test_validate_note_invalid_type(self):
        """测试非法 note_type 报错。"""
        errors = validate_note(self._make_note(note_type="weekly"))
        self.assertTrue(any("note_type" in e for e in errors))

    def test_validate_note_invalid_exam_freq(self):
        """测试 exam_freq 越界报错（上界与下界）。"""
        for freq in (-1, 6):
            errors = validate_note(self._make_note(exam_freq=freq))
            self.assertTrue(any("exam_freq" in e for e in errors), f"freq={freq}")

    def test_validate_note_empty_body(self):
        """测试正文为空报错。"""
        errors = validate_note(self._make_note(body=""))
        self.assertTrue(any("正文" in e for e in errors))


class TestExtractMetadata(unittest.TestCase):
    """测试 extract_metadata_from_frontmatter 的容错性。"""

    def test_exam_freq_non_numeric(self):
        """测试 exam_freq 非数字时记录为非法值。"""
        note = extract_metadata_from_frontmatter(
            {"title": "t", "subject": "s", "exam_freq": "abc"}, Path("x.md")
        )
        self.assertNotIn(note.exam_freq, (0, 1, 2, 3, 4, 5))

    def test_exam_freq_numeric_string(self):
        """测试 exam_freq 为数字字符串时正常转换。"""
        note = extract_metadata_from_frontmatter(
            {"title": "t", "subject": "s", "exam_freq": "4"}, Path("x.md")
        )
        self.assertEqual(note.exam_freq, 4)


if __name__ == "__main__":
    unittest.main()
