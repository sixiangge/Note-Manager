"""Rich Markdown preview with offline math and framed code blocks."""

from __future__ import annotations

import os
import re
import tempfile
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor, QImage, QTextDocument, QTextTable
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
    return _normalize_fraction_arguments(normalized)


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
    if _CJK_TEXT_RE.search(expression):
        return _render_cjk_formula(expression, font_size, color)

    import numpy as np

    expression = _normalize_math_expression(expression)
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
    return "".join(output), images


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


class MarkdownPreview(QTextBrowser):
    """Read-only Markdown browser with local formula resources."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._formula_images: dict[str, QImage] = {}
        self._markdown = ""
        self._base_path: Path | None = None
        self._theme = "light"
        self._body_size = "standard"
        self._code_size = "standard"
        self._body_font = "system"
        self._code_font = "system"

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
            self._markdown, text_color, size_offset
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
        if (
            resource_type == QTextDocument.ResourceType.ImageResource
            and name.scheme() == "formula"
        ):
            image = self._formula_images.get(name.host())
            if image is not None:
                return image
        return super().loadResource(resource_type, name)

    def clear(self) -> None:
        self._markdown = ""
        self._base_path = None
        self._formula_images = {}
        super().clear()


__all__ = ["MarkdownPreview"]
