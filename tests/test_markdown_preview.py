"""Regression tests for Markdown preview preprocessing."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QBuffer, QEventLoop, QIODevice, QTimer, QUrl
from PyQt6.QtGui import QColor, QImage, QTextDocument
from PyQt6.QtNetwork import QHostAddress, QTcpServer
from PyQt6.QtWidgets import QApplication

from src.gui.markdown_preview import (
    MarkdownPreview,
    _decode_network_image,
    _normalize_table_breaks,
    _render_formula,
    _replace_math,
)


class TestMarkdownPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_display_math_with_cjk_text_command_renders(self):
        markdown = "$$\\text{中文说明}+x$$"
        processed, images = _replace_math(markdown, "#202123", 0)
        self.assertNotIn("$$", processed)
        self.assertEqual(len(images), 1)
        self.assertFalse(next(iter(images.values())).isNull())

    def test_display_math_with_cjk_subscript_renders(self):
        image = _render_formula("x_{中文}", True, "#202123", 0)
        self.assertFalse(image.isNull())

    def test_multiline_cases_environment_renders(self):
        expression = r"""
        \hat{\delta}(q,x)=
        \begin{cases}
        \{q\}, & \text{if }x=\varepsilon \\
        \displaystyle\bigcup_{p\in\hat{\delta}(q,w)}\delta(p,a),
        & \text{if }x=wa
        \end{cases}
        """
        image = _render_formula(expression, True, "#202123", 0)
        self.assertFalse(image.isNull())

    def test_inline_math_with_unbraced_cjk_subscript_renders(self):
        markdown = "$N×(2RTT + T_传)$ 和 $2RTT + N×T_传$"
        processed, images = _replace_math(markdown, "#202123", 0)
        self.assertNotIn("$N×", processed)
        self.assertNotIn("$2RTT", processed)
        self.assertEqual(len(images), 2)
        self.assertTrue(all(not image.isNull() for image in images.values()))

    def test_bare_br_in_table_does_not_swallow_following_content(self):
        markdown = (
            "| 列一 | 列二 |\n"
            "| --- | --- |\n"
            "| 第一行<br>第二行 | 内容 |\n\n"
            "文件结尾仍然显示"
        )
        normalized = _normalize_table_breaks(markdown)
        self.assertIn("<br />", normalized)
        document = QTextDocument()
        document.setMarkdown(normalized)
        self.assertIn("文件结尾仍然显示", document.toPlainText())

    def test_br_inside_fenced_code_is_not_changed(self):
        markdown = "```html\n<table><br>\n```"
        self.assertEqual(_normalize_table_breaks(markdown), markdown)

    def test_bare_img_does_not_swallow_following_markdown(self):
        markdown = (
            '<img src="https://example.com/diagram.png" alt="图">\n\n'
            "- 图片后的列表项\n\n## 后续章节"
        )
        normalized = _normalize_table_breaks(markdown)
        self.assertIn('alt="图" />', normalized)
        document = QTextDocument()
        document.setMarkdown(normalized)
        plain_text = document.toPlainText()
        self.assertIn("图片后的列表项", plain_text)
        self.assertIn("后续章节", plain_text)

    def test_img_inside_fenced_code_is_not_changed(self):
        markdown = '```html\n<img src="example.png">\n```'
        self.assertEqual(_normalize_table_breaks(markdown), markdown)

    @staticmethod
    def _png_bytes() -> bytes:
        image = QImage(24, 16, QImage.Format.Format_ARGB32)
        image.fill(QColor("#176b5b"))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(buffer.data())

    def test_network_image_decoder_rejects_non_images(self):
        self.assertTrue(_decode_network_image(b"<html></html>", "text/html").isNull())
        self.assertFalse(
            _decode_network_image(self._png_bytes(), "image/png").isNull()
        )

    def test_markdown_images_are_shown_at_two_thirds_size(self):
        preview = MarkdownPreview()
        preview.resize(400, 240)
        image = QImage(300, 150, QImage.Format.Format_ARGB32)
        fitted = preview._fit_image(image, "test-image")
        self.assertEqual((fitted.width(), fitted.height()), (200, 100))
        self.assertEqual(
            preview._fit_image(image, "test-image").cacheKey(),
            fitted.cacheKey(),
        )
        self.assertEqual(len(preview._scaled_image_cache), 1)

    def test_network_image_disk_cache_survives_preview_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory) / "image-cache"
            url = "https://example.com/diagram.png"
            first = MarkdownPreview(image_cache_dir=cache_dir)
            first._store_disk_image(url, self._png_bytes())

            second = MarkdownPreview(image_cache_dir=cache_dir)
            loaded = second.loadResource(
                QTextDocument.ResourceType.ImageResource,
                QUrl(url),
            )
            self.assertIsInstance(loaded, QImage)
            self.assertFalse(loaded.isNull())
            self.assertFalse(second._pending_images)

    def test_local_image_resource_loads_from_unicode_path(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "状态转换图.png"
            image = QImage(24, 16, QImage.Format.Format_ARGB32)
            image.fill(QColor("#176b5b"))
            self.assertTrue(image.save(str(image_path), "PNG"))
            preview = MarkdownPreview()
            preview.set_markdown("", Path(directory))
            loaded = preview.loadResource(
                QTextDocument.ResourceType.ImageResource,
                QUrl(image_path.name),
            )
            self.assertIsInstance(loaded, QImage)
            self.assertFalse(loaded.isNull())

    def test_http_image_is_downloaded_and_cached(self):
        payload = self._png_bytes()
        server = QTcpServer()
        self.assertTrue(server.listen(QHostAddress("127.0.0.1"), 0))

        def send_response() -> None:
            socket = server.nextPendingConnection()

            def respond() -> None:
                socket.readAll()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n"
                    + f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
                    + payload
                )
                socket.write(response)
                socket.disconnectFromHost()

            socket.readyRead.connect(respond)

        server.newConnection.connect(send_response)
        url = f"http://127.0.0.1:{server.serverPort()}/diagram.png"
        preview = MarkdownPreview()
        preview.resize(400, 240)
        preview.show()
        preview.set_markdown(f"![状态转换图]({url})")
        # QTextDocument can defer resource lookup until a later paint on some
        # Qt platforms; invoke the same resource path deterministically here.
        preview.loadResource(
            QTextDocument.ResourceType.ImageResource,
            QUrl(url),
        )

        loop = QEventLoop()

        def check_cache() -> None:
            if url in preview._image_cache:
                loop.quit()
            else:
                QTimer.singleShot(20, check_cache)

        QTimer.singleShot(0, check_cache)
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        self.assertIn(
            url,
            preview._image_cache,
            f"pending={list(preview._pending_images)} failed={preview._failed_images}",
        )
        self.assertFalse(preview._image_cache[url].isNull())
        preview.close()
        server.close()


if __name__ == "__main__":
    unittest.main()
