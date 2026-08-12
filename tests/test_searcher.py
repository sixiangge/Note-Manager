"""searcher 模块的单元测试。"""

import unittest


class TestSearcher(unittest.TestCase):
    """测试关键词搜索与排序。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_search_basic(self):
        """测试基本关键词搜索。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_search_filter_exam(self):
        """测试 --type exam 过滤。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_search_filter_postgraduate(self):
        """测试 --type postgraduate 过滤。"""

    @unittest.skip("Phase 1 后续任务实现")
    def test_search_empty_query(self):
        """测试空查询。"""


if __name__ == "__main__":
    unittest.main()
