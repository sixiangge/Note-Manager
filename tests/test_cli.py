"""main.py CLI 的集成测试。

通过 monkeypatch 将数据路径重定向到临时目录，
端到端验证 index / search / teach / cleanup-cache 四个子命令。
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def run_cli(argv: list[str]) -> tuple[int, str]:
    """运行 main.main(argv)，返回 (退出码, 捕获的 stdout)。

    argparse 对参数错误会抛 SystemExit，一并捕获为退出码。
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            code = main.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    return code, buf.getvalue()


class TestCli(unittest.TestCase):
    """CLI 集成测试：所有数据路径重定向到临时目录。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # 重定向数据路径，避免污染真实 data/ 目录
        # BASE_DIR 必须与 NOTES_ROOT 同根，否则索引键 relative_to 会失败
        self.patches = [
            mock.patch.object(main, "BASE_DIR", self.tmp),
            mock.patch.object(main, "NOTES_ROOT", self.tmp / "notes"),
            mock.patch.object(main, "EXTERNAL_DIR", self.tmp / "external"),
            mock.patch.object(main, "INDEX_PATH", self.tmp / "index.json"),
            mock.patch.object(main, "MANIFEST_PATH", self.tmp / "manifest.json"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_help_lists_four_subcommands(self):
        """--help 应列出 index / search / teach / cleanup-cache 四个子命令。"""
        code, out = run_cli([])
        self.assertEqual(code, 0)
        for name in ("index", "search", "teach", "cleanup-cache"):
            self.assertIn(name, out)

    def test_index_generates_samples_and_index(self):
        """空仓 index 应生成 5 篇示例笔记并写出索引文件。"""
        code, out = run_cli(["index"])
        self.assertEqual(code, 0)
        self.assertEqual(len(list(self.tmp.joinpath("notes").rglob("*.md"))), 5)
        self.assertTrue(self.tmp.joinpath("index.json").exists())
        self.assertIn("5 篇笔记", out)

    def test_search_after_index(self):
        """index 后 search 应返回匹配结果。"""
        run_cli(["index"])
        code, out = run_cli(["search", "极限"])
        self.assertEqual(code, 0)
        self.assertIn("极限", out)
        self.assertIn("[期末]", out)  # 极限与连续是 exam 类型

    def test_search_type_filter(self):
        """--type 过滤应只返回对应类型。"""
        run_cli(["index"])
        code, out = run_cli(["search", "极限", "--type", "postgraduate"])
        self.assertEqual(code, 0)
        self.assertIn("[考研]", out)
        self.assertNotIn("[期末]", out)

    def test_search_before_index_fails_gracefully(self):
        """未建索引时 search 应提示错误并返回非零退出码。"""
        code, out = run_cli(["search", "极限"])
        self.assertEqual(code, 1)
        self.assertIn("python main.py index", out)

    def test_teach_placeholder(self):
        """teach 子命令应打印占位提示并正常退出（exit 0）。"""
        code, out = run_cli(["teach", "解释极限的定义",
                             "--files", "C:\\tmp\\课件.pdf"])
        self.assertEqual(code, 0)
        self.assertIn("Phase 3", out)
        self.assertIn("解释极限的定义", out)
        self.assertIn("课件.pdf", out)

    def test_cleanup_cache_dry_run(self):
        """cleanup-cache --dry-run 只预览不删除。"""
        self.tmp.joinpath("external").mkdir(parents=True)
        junk = self.tmp.joinpath("external") / "临时文件.pdf"
        junk.write_text("junk", encoding="utf-8")
        self.tmp.joinpath("manifest.json").write_text("{}", encoding="utf-8")

        code, out = run_cli(["cleanup-cache", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("dry-run", out)
        self.assertTrue(junk.exists())          # 未被删除
        self.assertTrue(self.tmp.joinpath("manifest.json").exists())

    def test_cleanup_cache_real(self):
        """cleanup-cache 实际删除缓存文件与清单。"""
        self.tmp.joinpath("external").mkdir(parents=True)
        junk = self.tmp.joinpath("external") / "临时文件.pdf"
        junk.write_text("junk", encoding="utf-8")
        self.tmp.joinpath("manifest.json").write_text("{}", encoding="utf-8")

        code, out = run_cli(["cleanup-cache"])
        self.assertEqual(code, 0)
        self.assertFalse(junk.exists())         # 已删除
        self.assertFalse(self.tmp.joinpath("manifest.json").exists())

    def test_unknown_command(self):
        """未识别的子命令应报错（argparse 行为，退出码 2）。"""
        code, _ = run_cli(["fly-to-moon"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
