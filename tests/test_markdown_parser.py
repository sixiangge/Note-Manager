"""markdown_parser 模块的单元测试。"""

import unittest


class TestMarkdownParser(unittest.TestCase):
    """测试 Markdown 解析与 Note 校验。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_parse_markdown_valid(self):
        """测试解析有效的 Markdown 文件。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_parse_markdown_missing_frontmatter(self):
        """测试解析缺少 Front-matter 的文件。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_validate_note_valid(self):
        """测试校验合法 Note。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_validate_note_invalid_type(self):
        """测试校验非法 note_type。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_validate_note_invalid_exam_freq(self):
        """测试校验超出范围的 exam_freq。"""


if __name__ == "__main__":
    unittest.main()
