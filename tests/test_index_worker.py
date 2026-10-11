"""Index rebuild failures must not escape a Qt worker or hang its thread."""

import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import IndexWorker, MainWindow
from src.indexer import build_index, save_index
from tests.test_indexer import NOTE_EXAM


class TestIndexWorker(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.notes = self.root / "notes"
        self.notes.mkdir()
        self.worker = IndexWorker(
            self.notes, self.root, self.root / "index.json",
            self.root / "notemanager.db", self.root, False,
        )
        self.results = []
        self.errors = []
        self.worker.finished.connect(self.results.append)
        self.worker.failed.connect(self.errors.append)

    def test_malformed_yaml_reports_failure_and_preserves_previous_index(self):
        (self.notes / "good.md").write_text(NOTE_EXAM, encoding="utf-8")
        (self.notes / "bad.md").write_text(
            "---\ntitle: bad\nsubject: test\ntags: [a, b\n---\nbody", encoding="utf-8"
        )
        self.worker.index_path.write_text('{"old": true}', encoding="utf-8")
        self.worker.database_path.write_bytes(b"previous database")
        self.worker.run()
        self.assertFalse(self.results)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("bad.md", self.errors[0])
        self.assertIn("YAML", self.errors[0])
        self.assertIn("行", self.errors[0])
        self.assertEqual(self.worker.index_path.read_text(), '{"old": true}')
        self.assertEqual(self.worker.database_path.read_bytes(), b"previous database")

    def test_unexpected_exception_emits_failure_instead_of_escaping_slot(self):
        with patch("src.gui.main_window.build_index", side_effect=RuntimeError("fixture")):
            self.worker.run()
        self.assertFalse(self.results)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("RuntimeError", self.errors[0])

    def test_catalog_failure_does_not_replace_json_or_leave_temporary_file(self):
        (self.notes / "good.md").write_text(NOTE_EXAM, encoding="utf-8")
        self.worker.index_path.write_text('{"old": true}', encoding="utf-8")
        with patch("src.gui.main_window.sync_note_catalog", side_effect=OSError("read-only")):
            self.worker.run()
        self.assertFalse(self.results)
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.worker.index_path.read_text(), '{"old": true}')
        self.assertIn("SQLite", self.errors[0])
        self.assertFalse(list(self.root.glob(".rebuild-*")))


class TestRebuildGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_failure_dialog_thread_cleanup_and_successful_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / "notes"
            notes.mkdir()
            good = notes / "good.md"
            good.write_text(NOTE_EXAM, encoding="utf-8")
            index_path = root / "index.json"
            index = build_index(notes, base_dir=root)
            save_index(index, index_path)
            original_index = index_path.read_bytes()
            bad = notes / "应用层.md"
            bad.write_text(
                '---\ntitle: bad\nsubject: test\ntags: [a, b\n---\nbody', encoding="utf-8"
            )
            original_note = bad.read_bytes()
            window = MainWindow(root, notes, index_path, preloaded_index=index, preloaded_settings={})
            window.show()
            QTest.qWait(20)

            def wait_finished():
                deadline = time.monotonic() + 8
                while window._index_thread is not None and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertIsNone(window._index_thread)
                self.assertIsNone(window._index_worker)
                self.assertTrue(window.rebuild_button.isEnabled())
                self.assertEqual(window.rebuild_button.text(), "重建索引")

            try:
                with patch("src.gui.main_window.QMessageBox.critical") as dialog:
                    for number in range(3):
                        QTest.mouseClick(window.rebuild_button, Qt.MouseButton.LeftButton)
                        wait_finished()
                        self.assertEqual(dialog.call_count, number + 1)
                        message = dialog.call_args.args[2]
                        self.assertIn("应用层.md", message)
                        self.assertIn("YAML", message)
                        self.assertIn("行", message)
                        self.assertIn("修正", message)
                        self.assertEqual(index_path.read_bytes(), original_index)
                        self.assertEqual(window.index, index)
                        self.assertEqual(bad.read_bytes(), original_note)
                    with patch("src.gui.main_window.build_index", side_effect=RuntimeError("fixture")):
                        window.rebuild_button.click()
                        wait_finished()
                    self.assertIn("RuntimeError", dialog.call_args.args[2])
                    bad.write_text(NOTE_EXAM.replace("二叉树与遍历", "Fixed"), encoding="utf-8")
                    dialog.reset_mock()
                    window.rebuild_button.click()
                    wait_finished()
                    dialog.assert_not_called()
                    self.assertEqual(window.library_list.count(), 2)
                    self.assertNotEqual(index_path.read_bytes(), original_index)
            finally:
                if window._index_thread is not None:
                    window._index_thread.quit()
                    window._index_thread.wait(8000)
                    self.app.processEvents()
                window.close()
                window.deleteLater()
                self.app.processEvents()
