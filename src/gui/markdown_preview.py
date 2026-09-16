"""Rich Markdown preview with offline math and framed code blocks."""

from __future__ import annotations

import os
import re
import tempfile
from hashlib import sha256
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QByteArray, QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QColor, QImage, QPainter, QTextDocument, QTextTable
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QTextBrowser


_DISPLAY_MATH_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$(?!\$)")
_INLINE_CODE_RE = re.compile(r"(`+)([^`\n]*?)\1")
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_PRE_GROUP_RE = re.compile(
    r'(?:<pre style="[^"]*">.*?</pre>\s*)+',
    re.DOTALL,
)
_PRE_CONTENT_RE = re.compile(r'<pre style="[^"]*">(.*?)</pre>', re.DOTALL)
_BODY_SIZES = {"small": 9.5, "standard": 11.0, "large": 12.5}
_CODE_SIZES = {"small": 9.5, "standard": 10.5, "large": 12.0}
_CJK_TEXT_RE = re.compile(r"[\u3400-\u9fff，。；：、！？（）]+")
_FRAC_COMMAND_RE = re.compile(r"\\frac(?![A-Za-z])")
_MATH_COMMAND_RE = re.compile(r"\\(?:[A-Za-z]+|.)")
_BARE_BR_RE = re.compile(r"<br\s*>", re.IGNORECASE)
_BARE_IMG_RE = re.compile(r"<img\b([^<>]*?)(?<!/)>", re.IGNORECASE)
_FORMULA_ONLY_LIST_ITEM_RE = re.compile(
    r"(?m)^[ \t]*(?:[-+*]|\d+[.)])[ \t]+"
    r"(?:!\[math-inline\]\(formula://math-\d+\)[ \t]*)+$"
)
_CJK_TEXT_COMMAND_RE = re.compile(
    r"\\(?:text|textrm|textsf|mathrm|mathbf|mathit|operatorname)\s*"
    r"\{([^{}]*[\u3400-\u9fff][^{}]*)\}"
)
_CJK_SCRIPT_RE = re.compile(r"[_^]\s*\{([^{}]*[\u3400-\u9fff][^{}]*)\}")
_CJK_BARE_SCRIPT_RE = re.compile(r"[_^]\s*([\u3400-\u9fff]+)")
_MAX_NETWORK_IMAGE_BYTES = 20 * 1024 * 1024
_NETWORK_IMAGE_TIMEOUT_MS = 15_000
_CASES_RE = re.compile(r"\\begin\{cases\}(.+?)\\end\{cases\}", re.DOTALL)


def _default_image_cache_dir() -> Path:
    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation
    )
    if not root:
        root = str(Path(tempfile.gettempdir()) / "NoteManager")
    return Path(root) / "markdown-images"


def _matplotlib_cache_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "NoteManager" / "matplotlib"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache_dir()))


@lru_cache(maxsize=1)
def _math_parser() -> tuple[Any, Any]:
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import MathTextParser

    return MathTextParser("agg"), FontProperties


def _mixed_cjk_math(expression: str) -> str:
    # MathText cannot combine its commands/braces with separately rendered
    # CJK runs. Preserve the readable CJK content instead of letting the
    # entire display formula fail (for example ``\text{中文}`` or ``x_{中文}``).
    previous = None
    while expression != previous:
        previous = expression
        expression = _CJK_TEXT_COMMAND_RE.sub(r"\1", expression)
    expression = _CJK_SCRIPT_RE.sub(r" \1", expression)
    expression = _CJK_BARE_SCRIPT_RE.sub(r" \1", expression)
    parts = re.split(f"({_CJK_TEXT_RE.pattern})", expression)
    mixed: list[str] = []
    for part in parts:
        if not part:
            continue
        if _CJK_TEXT_RE.fullmatch(part):
            mixed.append(part)
            continue
        leading = part[: len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()) :]
        core = part.strip()
        mixed.append(f"{leading}${core}${trailing}" if core else part)
    return "".join(mixed)


def _normalize_table_breaks(markdown: str) -> str:
    """Make unsafe HTML void elements safe for Qt's Markdown reader.

    Qt's Markdown reader treats ``<br>`` in a table as the start of an
    unclosed HTML block and can swallow everything through end-of-file. The
    same happens with bare ``<img>`` tags. Their self-closing forms render
    correctly, so normalize them while leaving fenced code untouched.
    """
    output: list[str] = []
    active_fence: tuple[str, int] | None = None
    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE_RE.match(line)
        if active_fence is None and fence_match:
            marker = fence_match.group(1)
            active_fence = (marker[0], len(marker))
            output.append(line)
            continue
        if active_fence is not None:
            output.append(line)
            if fence_match:
                marker = fence_match.group(1)
                if marker[0] == active_fence[0] and len(marker) >= active_fence[1]:
                    active_fence = None
            continue
        stripped = line.strip()
        safe_line = (
            _BARE_BR_RE.sub("<br />", line)
            if stripped.startswith("|") and stripped.endswith("|")
            else line
        )
        output.append(_BARE_IMG_RE.sub(r"<img\1 />", safe_line))
    return "".join(output)


def _normalize_fraction_arguments(expression: str) -> str:
    """Add braces around TeX's optional single-token fraction arguments."""
    output: list[str] = []
    position = 0
    while match := _FRAC_COMMAND_RE.search(expression, position):
        output.append(expression[position:match.end()])
        cursor = match.end()
        arguments: list[str] = []
        for _ in range(2):
            while cursor < len(expression) and expression[cursor].isspace():
                cursor += 1
            if cursor >= len(expression):
                break
            if expression[cursor] == "{":
                start = cursor
                depth = 0
                while cursor < len(expression):
                    if expression[cursor] == "{":
                        depth += 1
                    elif expression[cursor] == "}":
                        depth -= 1
                        if depth == 0:
                            cursor += 1
                            break
                    cursor += 1
                if depth != 0:
                    break
                arguments.append(expression[start:cursor])
                continue
            command = _MATH_COMMAND_RE.match(expression, cursor)
            if command:
                arguments.append("{" + command.group(0) + "}")
                cursor = command.end()
            else:
                arguments.append("{" + expression[cursor] + "}")
                cursor += 1
        if len(arguments) != 2:
            output.append(expression[match.end():])
            return "".join(output)
        output.extend(arguments)
        position = cursor
    output.append(expression[position:])
    return "".join(output)


def _normalize_math_expression(expression: str) -> str:
    """Translate common TeX aliases into MathText-compatible syntax."""
    normalized = re.sub(r"\\le(?![A-Za-z])", r"\\leq", expression)
    normalized = re.sub(r"\\ge(?![A-Za-z])", r"\\geq", normalized)
    normalized = _CASES_RE.sub(_normalize_cases, normalized)
    # MathText rejects physical newlines inside its surrounding $...$ span.
    # Explicit LaTeX row separators (``\\``) are unaffected.
    normalized = re.sub(r"[\r\n]+", " ", normalized).strip()
    return _normalize_fraction_arguments(normalized)


def _normalize_cases(match: re.Match[str]) -> str:
    """Translate a LaTeX cases block to MathText's supported substack form."""
    body = match.group(1).strip().replace(r"\displaystyle", "")
    body = body.replace("&", r"\quad ")
    body = re.sub(
        r"\\text\{([^{}]*)\}",
        lambda text: r"\mathrm{" + text.group(1).strip().replace(" ", r"\ ") + "}",
        body,
    )
    return r"\left\{\substack{" + body + r"}\right."


def _render_cjk_formula(expression: str, font_size: int, color: str) -> QImage:
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import math_to_image

    output = BytesIO()
    math_to_image(
        _mixed_cjk_math(_normalize_math_expression(expression.strip())),
        output,
        prop=FontProperties(family="Microsoft YaHei", size=font_size),
        dpi=144,
        format="png",
        color=color,
    )
    image = QImage.fromData(output.getvalue(), "PNG")
    if image.isNull():
        raise ValueError("公式图像生成失败")
    image.setDevicePixelRatio(2.0)
    return image


@lru_cache(maxsize=512)
def _render_formula(
    expression: str,
    display: bool,
    color: str,
    size_offset: int,
) -> QImage:
    font_size = (15 if display else 14) + size_offset
    expression = _normalize_math_expression(expression)
    if _CJK_TEXT_RE.search(expression):
        return _render_cjk_formula(expression, font_size, color)

    import numpy as np

    parser, font_properties = _math_parser()
    parsed = parser.parse(
        f"${expression.strip()}$",
        dpi=144,
        prop=font_properties(size=font_size),
    )
    alpha = np.asarray(parsed.image, dtype=np.uint8)
    height, width = alpha.shape
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    formula_color = QColor(color)
    rgba[:, :, 0] = formula_color.red()
    rgba[:, :, 1] = formula_color.green()
    rgba[:, :, 2] = formula_color.blue()
    rgba[:, :, 3] = alpha
    image = QImage(
        rgba.data,
        width,
        height,
        int(rgba.strides[0]),
        QImage.Format.Format_RGBA8888,
    ).copy()
    image.setDevicePixelRatio(2.0)
    return image


def _replace_math(
    markdown: str,
    color: str,
    size_offset: int,
) -> tuple[str, dict[str, QImage]]:
    images: dict[str, QImage] = {}
    formula_number = 0

    def formula_placeholder(expression: str, display: bool, original: str) -> str:
        nonlocal formula_number
        try:
            image = _render_formula(expression, display, color, size_offset)
        except (ImportError, OSError, RuntimeError, ValueError):
            return original
        key = f"math-{formula_number}"
        formula_number += 1
        images[key] = image
        kind = "display" if display else "inline"
        placeholder = f"![math-{kind}](formula://{key})"
        return f"\n\n{placeholder}\n\n" if display else placeholder

    def process_math_text(text: str) -> str:
        text = _DISPLAY_MATH_RE.sub(
            lambda match: formula_placeholder(match.group(1), True, match.group(0)),
            text,
        )
        return _INLINE_MATH_RE.sub(
            lambda match: formula_placeholder(match.group(1), False, match.group(0)),
            text,
        )

    def process_prose(text: str) -> str:
        result: list[str] = []
        position = 0
        for match in _INLINE_CODE_RE.finditer(text):
            result.append(process_math_text(text[position:match.start()]))
            result.append(match.group(0))
            position = match.end()
        result.append(process_math_text(text[position:]))
        return "".join(result)

    output: list[str] = []
    prose: list[str] = []
    active_fence: tuple[str, int] | None = None

    def flush_prose() -> None:
        if prose:
            output.append(process_prose("".join(prose)))
            prose.clear()

    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE_RE.match(line)
        if active_fence is None and fence_match:
            flush_prose()
            marker = fence_match.group(1)
            active_fence = (marker[0], len(marker))
            output.append(line)
            continue
        if active_fence is not None:
            output.append(line)
            if fence_match:
                marker = fence_match.group(1)
                if marker[0] == active_fence[0] and len(marker) >= active_fence[1]:
                    active_fence = None
            continue
        prose.append(line)
    flush_prose()
    processed = "".join(output)
    # Qt 6.11 progressively indents sibling list items whose only content is
    # an image. A zero-width no-break space keeps them text-bearing and is
    # discarded by QTextDocument, so neither the source nor visible output
    # changes.
    processed = _FORMULA_ONLY_LIST_ITEM_RE.sub(
        lambda match: match.group(0) + "\ufeff",
        processed,
    )
    return processed, images


def _box_code_blocks(
    html: str,
    code_font: str,
    code_size: float,
    background: str,
    border: str,
) -> str:
    monospace_style = f"font-family:{code_font}; font-size:{code_size}pt;"
    html = html.replace("font-family:'monospace';", monospace_style)

    def code_box(match: re.Match[str]) -> str:
        lines = _PRE_CONTENT_RE.findall(match.group(0))
        content = "<br />".join(lines)
        return (
            '<table border="1" cellspacing="0" cellpadding="9" width="100%" '
            f'style="margin-top:10px; margin-bottom:10px; border-color:{border}; '
            'border-collapse:collapse;">'
            f'<tr><td bgcolor="{background}">'
            '<p style="margin:0px; white-space:pre-wrap;">'
            f"{content}</p></td></tr></table>"
        )

    return _PRE_GROUP_RE.sub(code_box, html)


def _style_formula_images(html: str) -> str:
    html = html.replace(
        'alt="math-inline" title=""',
        'alt="math-inline" title="" style="vertical-align:middle;"',
    )
    display_pattern = re.compile(
        r'<p style="[^"]*">(<img [^>]*alt="math-display"[^>]*/>)</p>'
    )
    return display_pattern.sub(
        r'<p align="center" style="margin-top:10px; margin-bottom:10px;">\1</p>',
        html,
    )


def _align_table_headers(document: QTextDocument) -> None:
    """Copy each column's parsed alignment to its omitted header cell."""
    for frame in document.rootFrame().childFrames():
        if not isinstance(frame, QTextTable) or frame.rows() < 2:
            continue
        for column in range(frame.columns()):
            header_cursor = frame.cellAt(0, column).firstCursorPosition()
            header_format = header_cursor.blockFormat()
            body_format = frame.cellAt(1, column).firstCursorPosition().blockFormat()
            header_format.setAlignment(body_format.alignment())
            header_cursor.setBlockFormat(header_format)


def _style_body(
    html: str,
    body_font: str,
    body_size: float,
    text_color: str,
) -> str:
    """Replace QTextDocument's fixed Sans Serif 9pt body defaults."""
    body_style = (
        f'<body style="font-family:{body_font}; font-size:{body_size}pt; '
        f'font-weight:400; font-style:normal; color:{text_color};">'
    )
    return re.sub(r'<body style="[^"]*">', body_style, html, count=1)


def _decode_network_image(data: bytes, content_type: str = "") -> QImage:
    """Validate and decode an image downloaded for the Markdown preview."""
    if not data or len(data) > _MAX_NETWORK_IMAGE_BYTES:
        return QImage()
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type and not (
        media_type.startswith("image/")
        or media_type in {"application/octet-stream", "binary/octet-stream"}
    ):
        return QImage()
    return QImage.fromData(QByteArray(data))


class MarkdownPreview(QTextBrowser):
    """Read-only Markdown browser with formula, local, and network images."""

    def __init__(self, parent=None, *, image_cache_dir: Path | None = None) -> None:
        super().__init__(parent)
        self._formula_images: dict[str, QImage] = {}
        self._markdown = ""
        self._base_path: Path | None = None
        self._theme = "light"
        self._body_size = "standard"
        self._code_size = "standard"
        self._body_font = "system"
        self._code_font = "system"
        self._network_manager = QNetworkAccessManager(self)
        self._image_cache: dict[str, QImage] = {}
        self._scaled_image_cache: dict[tuple[str, int], QImage] = {}
        self._image_cache_dir = image_cache_dir or _default_image_cache_dir()
        self._pending_images: dict[str, QNetworkReply] = {}
        self._failed_images: set[str] = set()
        self._loading_image = self._make_image_notice("正在加载图片…")
        self._failed_image = self._make_image_notice("图片加载失败")

    def _make_image_notice(self, text: str) -> QImage:
        """Create a small theme-neutral fallback shown during image loading."""
        image = QImage(240, 44, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#f4f6f8"))
        painter = QPainter(image)
        painter.setPen(QColor("#72767d"))
        painter.drawRect(0, 0, image.width() - 1, image.height() - 1)
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return image

    def _fit_image(self, image: QImage, cache_key: str = "") -> QImage:
        """Show Markdown images at two thirds size and fit them to the view."""
        if image.isNull():
            return image
        available_width = max(64, self.viewport().width() - 24)
        target_width = min(available_width, max(1, round(image.width() * 2 / 3)))
        scaled_key = (cache_key, target_width)
        if cache_key and scaled_key in self._scaled_image_cache:
            return self._scaled_image_cache[scaled_key]
        scaled = image.scaledToWidth(
            target_width,
            Qt.TransformationMode.SmoothTransformation,
        )
        if cache_key:
            self._scaled_image_cache[scaled_key] = scaled
        return scaled

    def _disk_image_path(self, url: str) -> Path:
        """Map a network URL to a filesystem-safe persistent cache key."""
        return self._image_cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}.img"

    def _load_disk_image(self, url: str) -> QImage:
        path = self._disk_image_path(url)
        try:
            if not path.is_file() or path.stat().st_size > _MAX_NETWORK_IMAGE_BYTES:
                return QImage()
            image = QImage(str(path))
        except OSError:
            return QImage()
        if image.isNull():
            try:
                path.unlink()
            except OSError:
                pass
        return image

    def _store_disk_image(self, url: str, data: bytes) -> None:
        """Persist validated network bytes, replacing an older cache entry."""
        temporary: Path | None = None
        try:
            self._image_cache_dir.mkdir(parents=True, exist_ok=True)
            target = self._disk_image_path(url)
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
        except OSError:
            # A read-only or full cache location must not break note rendering.
            try:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def set_render_settings(
        self,
        *,
        theme: str,
        body_size: str,
        code_size: str,
        body_font: str,
        code_font: str,
    ) -> None:
        changed = (
            theme,
            body_size,
            code_size,
            body_font,
            code_font,
        ) != (
            self._theme,
            self._body_size,
            self._code_size,
            self._body_font,
            self._code_font,
        )
        self._theme = theme
        self._body_size = body_size
        self._code_size = code_size
        self._body_font = body_font
        self._code_font = code_font
        if changed and self._markdown:
            scroll = self.verticalScrollBar().value()
            self._render()
            self.verticalScrollBar().setValue(scroll)

    def set_markdown(self, markdown: str, base_path: Path | None = None) -> None:
        self._markdown = markdown
        self._base_path = base_path
        # A temporary network failure should not remain permanent after the
        # user reopens or refreshes a note.
        self._failed_images.clear()
        self._render()

    def _render(self) -> None:
        dark = self._theme == "dark"
        text_color = "#dfdedc" if dark else "#202123"
        code_background = "#0b0907" if dark else "#f4f6f8"
        code_border = "#302a24" if dark else "#cfd5db"
        body_size = _BODY_SIZES.get(self._body_size, _BODY_SIZES["standard"])
        code_size = _CODE_SIZES.get(self._code_size, _CODE_SIZES["standard"])
        size_offset = {"small": -1, "standard": 0, "large": 2}.get(
            self._body_size, 0
        )
        body_font = (
            "'Segoe UI','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
            if self._body_font == "system"
            else f"'{self._body_font}','Microsoft YaHei UI',sans-serif"
        )
        code_font = (
            "'Cascadia Mono','JetBrains Mono','Consolas','Courier New',monospace"
            if self._code_font == "system"
            else f"'{self._code_font}','Consolas',monospace"
        )
        processed, self._formula_images = _replace_math(
            _normalize_table_breaks(self._markdown), text_color, size_offset
        )
        document = QTextDocument()
        document.setDefaultStyleSheet(
            f"body {{ color: {text_color}; font-family: {body_font}; "
            f"font-size: {body_size}pt; }} "
            f"a {{ color: {'#b8ddd5' if dark else '#176b5b'}; }}"
        )
        if self._base_path is not None:
            document.setBaseUrl(
                QUrl.fromLocalFile(str(self._base_path.resolve()) + "/")
            )
        document.setMarkdown(processed)
        _align_table_headers(document)
        html = _style_body(
            _style_formula_images(
                _box_code_blocks(
                    document.toHtml(),
                    code_font,
                    code_size,
                    code_background,
                    code_border,
                )
            ),
            body_font,
            body_size,
            text_color,
        )
        if self._base_path is not None:
            self.document().setBaseUrl(
                QUrl.fromLocalFile(str(self._base_path.resolve()) + "/")
            )
        self.setHtml(html)

    def loadResource(self, resource_type: int, name: QUrl):
        if resource_type != QTextDocument.ResourceType.ImageResource:
            return super().loadResource(resource_type, name)

        if name.scheme() == "formula":
            image = self._formula_images.get(name.host())
            if image is not None:
                return image

        scheme = name.scheme().lower()
        key = name.toString()
        if scheme in {"http", "https"}:
            cached = self._image_cache.get(key)
            if cached is not None:
                return self._fit_image(cached, key)
            cached = self._load_disk_image(key)
            if not cached.isNull():
                self._image_cache[key] = cached
                return self._fit_image(cached, key)
            if key in self._failed_images:
                return self._failed_image
            if key not in self._pending_images:
                self._request_network_image(name, key)
            return self._loading_image

        local_path: Path | None = None
        if scheme == "file":
            local_path = Path(name.toLocalFile())
        elif len(scheme) == 1 and name.path().startswith(("/", "\\")):
            # Qt parses a raw Windows path in Markdown as a URL whose scheme
            # is the drive letter (for example ``C:\\...`` -> scheme ``c``).
            local_path = Path(f"{scheme.upper()}:{name.path()}")
        elif not scheme and self._base_path is not None:
            local_path = self._base_path / name.path()
        if local_path is not None:
            cache_key = str(local_path.resolve())
            cached = self._image_cache.get(cache_key)
            if cached is not None:
                return self._fit_image(cached, cache_key)
            image = QImage(str(local_path))
            if not image.isNull():
                self._image_cache[cache_key] = image
                return self._fit_image(image, cache_key)
        return super().loadResource(resource_type, name)

    def _request_network_image(self, url: QUrl, key: str) -> None:
        """Start one asynchronous HTTP(S) image request."""
        request = QNetworkRequest(url)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        request.setTransferTimeout(_NETWORK_IMAGE_TIMEOUT_MS)
        request.setRawHeader(b"User-Agent", b"NoteManager/1.0")
        reply = self._network_manager.get(request)
        self._pending_images[key] = reply
        reply.finished.connect(lambda: self._finish_network_image(key, url, reply))

    def _finish_network_image(
        self,
        key: str,
        resource_url: QUrl,
        reply: QNetworkReply,
    ) -> None:
        """Decode a completed request and replace its document resource."""
        self._pending_images.pop(key, None)
        image = QImage()
        data = b""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            content_type = bytes(
                reply.rawHeader(b"Content-Type")
            ).decode("ascii", errors="ignore")
            data = bytes(reply.readAll())
            image = _decode_network_image(data, content_type)
        reply.deleteLater()

        if image.isNull():
            self._failed_images.add(key)
            replacement = self._failed_image
        else:
            self._image_cache[key] = image
            self._store_disk_image(key, data)
            self._failed_images.discard(key)
            replacement = self._fit_image(image, key)

        self.document().addResource(
            QTextDocument.ResourceType.ImageResource,
            resource_url,
            replacement,
        )
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()

    def clear(self) -> None:
        self._markdown = ""
        self._base_path = None
        self._formula_images = {}
        super().clear()


__all__ = ["MarkdownPreview"]
