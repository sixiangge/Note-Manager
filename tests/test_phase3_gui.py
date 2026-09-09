"""Offscreen GUI regression tests with temporary data and fake teaching results."""

from importlib.util import find_spec
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_GUI = find_spec("PyQt6") is not None
if HAS_GUI:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import QUrl, Qt, QMimeData, QPointF
    from PyQt6.QtGui import QCloseEvent, QDropEvent, QFontDatabase, QFont
    from PyQt6.QtTest import QTest
    from src.gui.teaching_page import TeachingPage
    from src.gui.main_window import MainWindow

from src.app_settings import normalized_settings
from src.models import TeachSession


@unittest.skipUnless(HAS_GUI, "PyQt6 not installed")
class TestTeachingGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # The Windows offscreen plugin does not enumerate system fonts itself.
        if cls.app.platformName() == "offscreen" and os.name == "nt":
            for filename in ("segoeui.ttf", "msyh.ttc", "msyhbd.ttc"):
                font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
                if font.exists():
                    QFontDatabase.addApplicationFont(str(font))
            cls.app.setFont(QFont("Microsoft YaHei", 9))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.settings = normalized_settings({"teach_provider": "local", "teach_model": "fake"}, self.root)
        self.deps = patch("src.gui.teaching_page.find_spec", return_value=True)
        self.deps.start()
        self.page = TeachingPage(lambda: self.settings, lambda: self.root,
                                 self.root / "external", lambda: None)
        self.page.resize(750, 750)
        self.page.show()

    def tearDown(self):
        if self.page.worker is not None:
            self.page.cancel()
            self.page.worker.wait(5000)
            self.app.processEvents()
        self.page.close()
        self.page.deleteLater()
        self.app.processEvents()
        self.deps.stop()
        self.directory.cleanup()

    def wait_finished(self):
        deadline = time.monotonic() + 8
        while self.page.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.page.is_busy())

    def test_disabled_placeholder_and_upload_validation(self):
        self.settings["teach_provider"] = "disabled"
        self.page.refresh_settings()
        self.assertFalse(self.page.send_button.isEnabled())
        self.assertFalse(self.page.attach_button.isEnabled())
        self.settings["teach_provider"] = "local"
        self.page.refresh_settings()
        path = self.root / "课件.txt"
        path.write_text("fixture", encoding="utf-8")
        self.page.add_files([str(path), str(path), str(self.root / "missing.pdf")])
        self.assertEqual(self.page.attachments.count(), 1)
        self.assertIn("missing.pdf", self.page.status.text())

    def test_send_render_history_sources_and_clear(self):
        source = {"id": "N1", "content": "极限原文", "path": "note.md",
                  "metadata": {"title": "极限", "chunk": 1}}
        response = TeachSession("解释极限", [source], final_answer="根据 [N1]，**极限**是… <img src='file:///secret'>",
                                discrepancies=["【补充】原文的 **额外观点** [N1]"])
        self.page.question.setPlainText("解释极限")
        with patch("src.gui.teaching_page.teach_session", return_value=response) as teach:
            self.page.send()
            self.assertFalse(self.page.send_button.isEnabled())
            self.wait_finished()
        self.assertEqual(teach.call_args.kwargs["notes_root"], self.root)
        self.assertTrue(self.page.send_button.isEnabled())
        self.assertIn("课程助教", self.page.browser.toPlainText())
        self.assertIn("额外观点", self.page.browser.toPlainText())
        self.assertTrue(self.page.browser.extraSelections())
        self.assertIsNone(self.page.browser.loadResource(2, QUrl("file:///secret")))
        self.page.sources.setChecked(True)
        self.assertIn("极限原文", self.page.browser.toPlainText())
        self.assertEqual(len(self.page.history), 2)
        self.page.clear_session()
        self.assertFalse(self.page.history)
        self.assertFalse(self.page.transcript)

    def test_failed_request_retains_input_and_enables_retry(self):
        self.page.question.setPlainText("问题")
        with patch("src.gui.teaching_page.teach_session", side_effect=ValueError("测试失败")):
            self.page.send()
            self.wait_finished()
        self.assertIn("测试失败", self.page.status.text())
        self.assertEqual(self.page.question.toPlainText(), "问题")
        self.assertTrue(self.page.send_button.isEnabled())

    @unittest.skipUnless(find_spec("chromadb"), "Chroma not installed")
    def test_worker_runs_real_parsing_and_retrieval(self):
        path = self.root / "课件.txt"
        path.write_text("极限定义 epsilon delta", encoding="utf-8")
        self.page.add_files([str(path)])
        self.page.question.setPlainText("极限定义")
        with patch("src.oracle.generate", return_value={"answer": "课件 [E1] 的解释", "discrepancies": []}):
            self.page.send()
            self.wait_finished()
        self.assertIn("课件 [E1] 的解释", self.page.browser.toPlainText())
        self.assertEqual(self.page.attachments.count(), 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "极限定义 epsilon delta")

    def test_local_file_drop(self):
        path = self.root / "拖入.txt"
        path.write_text("fixture", encoding="utf-8")
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(path))])
        event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, data,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.page.dropEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(self.page.attachments.count(), 1)

    def test_cooperative_cancel_does_not_emit_late_answer(self):
        def operation(*args, **kwargs):
            deadline = time.monotonic() + 4
            while not kwargs["cancelled"]() and time.monotonic() < deadline:
                time.sleep(0.01)
            return TeachSession("问题", final_answer="should not appear")
        self.page.question.setPlainText("问题")
        with patch("src.gui.teaching_page.teach_session", side_effect=operation):
            self.page.send()
            self.page.cancel()
            self.wait_finished()
        self.assertIn("取消", self.page.status.text())
        self.assertNotIn("should not appear", self.page.browser.toPlainText())

    def test_remote_confirmation_can_prevent_sending(self):
        self.settings["teach_base_url"] = "https://example.org"
        self.page.refresh_settings()
        self.page.question.setPlainText("问题")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
                patch("src.gui.teaching_page.teach_session") as teach:
            self.page.send()
        teach.assert_not_called()
        self.assertFalse(self.page.is_busy())

    def test_main_window_integration_light_dark_and_busy_close(self):
        window = MainWindow(self.root, self.root / "notes", self.root / "index" / "index.json",
                            preloaded_settings=self.settings,
                            preloaded_index={"documents": {}, "inverted_index": {}}, preloaded_history=[])
        try:
            window.show()
            window._switch_page(2)
            self.app.processEvents()
            self.assertIsInstance(window.teaching_page, TeachingPage)
            window.teaching_page.transcript = [("user", "请结合课件解释极限定义，并检查我的笔记。"),
                ("assistant", TeachSession("解释极限", final_answer="根据外部课件 [E1]，应先指定误差范围，再选择自变量的邻域。\n\n这是测试资料生成的界面预览，不是对真实笔记的校验。",
                    discrepancies=["【冲突】笔记与课件的条件顺序不同，请复核原文。[N1] [E1]"],
                    recalled_notes=[{"id": "N1", "content": "测试笔记片段", "metadata": {"title": "极限与连续", "chunk": 1}}],
                    external_chunks=[{"id": "E1", "content": "测试课件片段", "metadata": {"title": "第一章课件.pdf", "chunk": 2}}]))]
            with patch.object(window.teaching_page, "is_busy", return_value=True), \
                    patch.object(window.teaching_page, "cancel") as cancel:
                event = QCloseEvent()
                window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                cancel.assert_called_once()
            for theme in ("light", "dark"):
                window.settings["theme"] = theme
                window._apply_appearance_settings()
                self.app.processEvents()
                self.assertTrue(window.teaching_page.send_button.isEnabled())
                screenshot_dir = os.getenv("NOTEMANAGER_TEST_SCREENSHOTS")
                if screenshot_dir:
                    destination = Path(screenshot_dir)
                    destination.mkdir(parents=True, exist_ok=True)
                    window.grab().save(str(destination / f"teaching-{theme}.png"))
            window._switch_page(3)
            window.settings_page.categories.setCurrentRow(4)
            self.app.processEvents()
            self.assertIn("teach_model", window.settings_page._controls)
            if os.getenv("NOTEMANAGER_TEST_SCREENSHOTS"):
                window.grab().save(str(Path(os.environ["NOTEMANAGER_TEST_SCREENSHOTS"]) / "model-settings.png"))
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()
