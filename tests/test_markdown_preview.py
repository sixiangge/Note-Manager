"""Regression tests for Markdown preview preprocessing."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QBuffer, QEvent, QEventLoop, QIODevice, QTimer, QUrl
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

    def test_formula_only_list_items_keep_the_same_visual_indent(self):
        preview = MarkdownPreview()
        preview.resize(750, 500)
        preview.set_markdown(
            "- **长度**\n"
            "  - $∣w∣=n$\n"
            "  - $∣uv∣=∣u∣+∣v∣$\n"
        )
        document = preview.document()
        document.setTextWidth(700)
        document.documentLayout()

        positions = []
        block = document.begin()
        while block.isValid():
            if block.textList() is not None:
                positions.append(block.layout().lineAt(0).x())
            block = block.next()

        self.assertEqual(len(positions), 3)
        self.assertEqual(positions[1], positions[2])

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
        self.assertEqual(fitted.deviceIndependentSize().width(), 200)
        self.assertEqual(fitted.deviceIndependentSize().height(), 100)
        self.assertEqual(
            preview._fit_image(image, "test-image").cacheKey(),
            fitted.cacheKey(),
        )
        self.assertEqual(len(preview._scaled_image_cache), 1)

    def test_high_dpi_images_keep_source_detail_at_same_display_size(self):
        preview = MarkdownPreview()
        preview.resize(400, 240)
        image = QImage(300, 150, QImage.Format.Format_ARGB32)
        with patch.object(preview, "devicePixelRatioF", return_value=2.0):
            fitted = preview._fit_image(image, "high-dpi")
        self.assertEqual(fitted.deviceIndependentSize().width(), 200)
        self.assertEqual(fitted.deviceIndependentSize().height(), 100)
        # There is no reason to discard native pixels then upscale them again.
        self.assertEqual((fitted.width(), fitted.height()), (300, 150))

    def test_preview_formulas_have_high_resolution_backing_images(self):
        preview = MarkdownPreview()
        with patch.object(preview, "devicePixelRatioF", return_value=2.0):
            preview.set_markdown(r"Inline $\frac{x^2}{y}+\sqrt{z}$.")
        self.assertEqual(len(preview._formula_images), 1)
        image = next(iter(preview._formula_images.values()))
        self.assertGreaterEqual(image.devicePixelRatio(), 4.0)

    def test_image_scale_cache_separates_screen_pixel_ratios(self):
        preview = MarkdownPreview()
        preview.resize(400, 240)
        source = QImage(600, 300, QImage.Format.Format_ARGB32)
        with patch.object(preview, "devicePixelRatioF", return_value=1.0):
            low = preview._fit_image(source, "diagram")
        with patch.object(preview, "devicePixelRatioF", return_value=1.5):
            high = preview._fit_image(source, "diagram")
            cached = preview._fit_image(source, "diagram")
        self.assertEqual(low.deviceIndependentSize(), high.deviceIndependentSize())
        self.assertGreater(high.width(), low.width())
        self.assertEqual(cached.cacheKey(), high.cacheKey())
        self.assertEqual(source.devicePixelRatio(), 1.0)
        self.assertEqual(len(preview._scaled_image_cache), 2)

    def test_source_with_pixel_ratio_keeps_its_logical_size(self):
        preview = MarkdownPreview()
        preview.resize(400, 240)
        source = QImage(600, 300, QImage.Format.Format_ARGB32)
        source.setDevicePixelRatio(2.0)
        with patch.object(preview, "devicePixelRatioF", return_value=2.0):
            fitted = preview._fit_image(source)
        self.assertEqual(fitted.deviceIndependentSize().width(), 200)
        self.assertEqual(fitted.deviceIndependentSize().height(), 100)
        self.assertEqual((fitted.width(), fitted.height()), (400, 200))
        self.assertEqual(source.devicePixelRatio(), 2.0)

    def test_formula_supersampling_keeps_approximate_display_dimensions(self):
        expressions = [
            r"\frac{x^2}{y}+\sqrt{z}",
            r"\begin{cases}x & x>0 \\ -x & x\le0\end{cases}",
            r"x+\text{中文}",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                low = _render_formula(expression, True, "#202123", 0, 2.0)
                high = _render_formula(expression, True, "#202123", 0, 4.0)
                self.assertGreater(high.width(), low.width())
                self.assertAlmostEqual(
                    low.deviceIndependentSize().width(),
                    high.deviceIndependentSize().width(), delta=2,
                )
                self.assertAlmostEqual(
                    low.deviceIndependentSize().height(),
                    high.deviceIndependentSize().height(), delta=2,
                )

    def test_screen_change_replaces_cached_document_images(self):
        with tempfile.TemporaryDirectory() as directory:
            source = QImage(900, 450, QImage.Format.Format_ARGB32)
            source.fill(QColor("#176b5b"))
            image_path = Path(directory) / "diagram.png"
            self.assertTrue(source.save(str(image_path), "PNG"))
            preview = MarkdownPreview(image_cache_dir=Path(directory) / "cache")
            preview.resize(500, 300)
            url = QUrl.fromLocalFile(str(image_path))
            markdown = f"![diagram]({url.toString()})\n\n" + r"$x^2$"
            with patch.object(preview, "devicePixelRatioF", return_value=1.0):
                preview.set_markdown(markdown, Path(directory))
                low = preview.document().resource(
                    QTextDocument.ResourceType.ImageResource, url
                )
                preview.document().setTextWidth(470)
                # Qt must lay the image out in logical, not backing pixels.
                low_layout_width = preview.document().begin().layout().lineAt(0).naturalTextWidth()
            with patch.object(preview, "devicePixelRatioF", return_value=2.5):
                if hasattr(QEvent.Type, "DevicePixelRatioChange"):
                    self.app.sendEvent(preview, QEvent(QEvent.Type.DevicePixelRatioChange))
                    self.assertTrue(preview._refresh_timer.isActive())
                    preview._refresh_timer.stop()
                preview._refresh_resolution()
                high = preview.document().resource(
                    QTextDocument.ResourceType.ImageResource, url
                )
                preview.document().setTextWidth(470)
                high_layout_width = preview.document().begin().layout().lineAt(0).naturalTextWidth()
                formula = preview.document().resource(
                    QTextDocument.ResourceType.ImageResource, QUrl("formula://math-0")
                )
            self.assertGreater(high.width(), low.width())
            self.assertAlmostEqual(low_layout_width, high_layout_width, delta=1)
            self.assertEqual(formula.devicePixelRatio(), 5.0)
            self.assertEqual(high.deviceIndependentSize().width(), low.deviceIndependentSize().width())

    def test_resize_refreshes_image_fit_and_bounds_scale_cache(self):
        preview = MarkdownPreview()
        source = QImage(900, 450, QImage.Format.Format_ARGB32)
        with patch.object(preview, "devicePixelRatioF", return_value=1.0):
            for width in range(200, 250):
                preview.resize(width, 240)
                preview._fit_image(source, "diagram")
        self.assertLessEqual(len(preview._scaled_image_cache), 32)

    def test_rerender_does_not_keep_obsolete_documents(self):
        preview = MarkdownPreview()
        for number in range(10):
            preview.set_markdown(f"Note {number}: $x^2$.")
        self.assertEqual(len(preview.findChildren(QTextDocument)), 1)

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
