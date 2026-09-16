"""Main PyQt6 window for browsing and searching course notes."""

from __future__ import annotations

import os
import math
import re
import shutil
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPoint,
    QPointF,
    QProcess,
    QRect,
    QRectF,
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDesktopServices,
    QDrag,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.indexer import build_index, generate_sample_notes, load_index, save_index
from src.api_credentials import (
    CredentialStorageError,
    delete_saved_api_key,
    save_api_key,
)
from src.app_settings import DEFAULT_APP_SETTINGS, normalized_settings
from src.gui.markdown_preview import MarkdownPreview
from src.gui.settings_page import SettingsPage
from src.gui.theme import (
    apply_application_palette,
    resolved_theme,
    set_windows_title_bar_theme,
    theme_colors,
)
from src.parsers.markdown_parser import Note, parse_markdown
from src.searcher import search
from src.storage import (
    clear_search_history as clear_persisted_search_history,
    export_local_data,
    load_app_settings,
    load_search_history,
    record_search,
    reset_app_settings,
    save_app_setting,
    save_app_settings,
    storage_summary,
    sync_note_catalog,
    trim_search_history,
)


# One-line rollback switch for note-only manual ordering.
ENABLE_MANUAL_NOTE_ORDER = True


APP_STYLE = """
QWidget {
    color: #202123;
}
QMainWindow, QWidget#root {
    background: #f7f7f8;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 14px;
}
QFrame#sidebar {
    background: #f1f2f3;
    border-right: 1px solid #dedfe2;
}
QLabel#brand {
    font-size: 19px;
    font-weight: 700;
    color: #17181a;
}
QLabel#sectionLabel {
    color: #777b82;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#navButton {
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 9px 10px;
    text-align: left;
    color: #34363a;
}
QPushButton#navButton:hover { background: #e5e7e9; }
QPushButton#navButton:checked {
    background: #dde4e2;
    color: #123d36;
    font-weight: 600;
}
QPushButton, QToolButton {
    min-height: 32px;
    border: 1px solid #d7d9dd;
    border-radius: 6px;
    background: #ffffff;
    padding: 0 11px;
    color: #2d2f33;
}
QPushButton:hover, QToolButton:hover { background: #f1f3f4; }
QPushButton:pressed, QToolButton:pressed { background: #e7e9eb; }
QPushButton:disabled, QToolButton:disabled { color: #a2a5aa; background: #f4f4f5; }
QPushButton#primaryButton {
    background: #176b5b;
    border-color: #176b5b;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #12594c; }
QLineEdit, QPlainTextEdit {
    background: #ffffff;
    color: #202123;
    border: 1px solid #d7d9dd;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #b8ddd5;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #4d8f82; }
QLineEdit QToolButton {
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    margin: 0;
    padding: 0;
    border: 0;
    border-radius: 9px;
    background: transparent;
}
QLineEdit QToolButton:hover { background: #e5e7e9; }
QLineEdit QToolButton:pressed { background: #d7d9dd; }
QTreeWidget, QListWidget, QTextBrowser {
    background: transparent;
    color: #202123;
    border: 0;
    outline: 0;
}
QTreeWidget::item {
    color: #202123;
    min-height: 29px;
    border-radius: 4px;
    padding: 2px 4px;
}
QTreeWidget::item:hover, QListWidget::item:hover { background: #eceeef; }
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #dde9e6;
    color: #111111;
}
QListWidget::item {
    color: #202123;
    border-bottom: 1px solid #ececef;
    padding: 11px 10px;
}
QListWidget#multiSelectList::item {
    border-bottom: 0;
    padding: 5px 4px;
}
QListWidget#multiSelectList::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #111111;
    background: #ffffff;
    image: none;
}
QListWidget#multiSelectList::indicator:checked {
    border: 1px solid #111111;
    background: #111111;
    image: none;
}
QScrollBar:vertical {
    width: 12px;
    margin: 0;
    border: 0;
    background: #ffffff;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    margin: 0 4px;
    border: 0;
    background: #111111;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    border: 0;
    background: #ffffff;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: #ffffff;
}
QScrollBar:horizontal {
    height: 4px;
    margin: 0;
    border: 0;
    background: #ffffff;
}
QScrollBar::handle:horizontal {
    min-width: 28px;
    border: 0;
    background: #111111;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    border: 0;
    background: #ffffff;
}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal,
QAbstractScrollArea::corner {
    background: #ffffff;
}
QFrame#panel {
    background: #ffffff;
    border: 0;
}
QFrame#panelDivider { border-right: 1px solid #e2e3e5; }
QLabel#pageTitle {
    font-size: 18px;
    font-weight: 650;
    color: #202123;
}
QLabel#noteTitle {
    font-size: 24px;
    font-weight: 700;
    color: #18191b;
}
QLabel#muted { color: #72767d; }
QLabel#badge {
    color: #285c52;
    background: #e2efec;
    border-radius: 5px;
    padding: 3px 7px;
    font-size: 12px;
}
QFrame#composer {
    background: #ffffff;
    border: 1px solid #dfe1e4;
    border-radius: 8px;
}
QSplitter::handle { background: #e2e3e5; width: 1px; }
QStatusBar { background: #ffffff; color: #686c73; border-top: 1px solid #e5e6e8; }
QFrame#multiSelectPopup {
    background: #ffffff;
    border: 1px solid #9da1a6;
}
"""


SETTINGS_STYLE = """
QFrame#settingsCategoriesPanel {
    min-width: 220px;
    max-width: 220px;
    background: #f1f2f3;
    border-right: 1px solid #dedfe2;
}
QListWidget#settingsCategories::item {
    border: 0;
    border-radius: 6px;
    padding: 10px 11px;
}
QFrame#settingRow { border-bottom: 1px solid #ececef; }
QLabel#settingTitle { color: #202123; font-weight: 600; }
QScrollArea#settingsScroll { background: transparent; border: 0; }
QScrollArea#settingsScroll > QWidget > QWidget { background: transparent; }
QSpinBox#settingsNumberInput {
    min-height: 32px;
    min-width: 150px;
    border: 1px solid #d7d9dd;
    border-radius: 6px;
    background: #ffffff;
    color: #202123;
    padding: 0 9px;
}
QSpinBox#settingsNumberInput:hover { background: #f1f3f4; }
QSpinBox#settingsNumberInput:focus { border-color: #4d8f82; }
QToolButton#settingsOptionPicker {
    min-width: 150px;
    text-align: left;
    padding-left: 11px;
    padding-right: 11px;
}
QListWidget#settingsOptionList::item {
    min-height: 28px;
    border-bottom: 0;
    border-radius: 4px;
    padding: 4px 8px;
}
QCheckBox { color: #202123; spacing: 8px; }
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #111111;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    border: 1px solid #111111;
    background: #111111;
}
"""


_DARK_REPLACEMENTS = {
    "#f7f7f8": "#080807",
    "#ffffff": "#000000",
    "#f1f2f3": "#0e0d0c",
    "#202123": "#dfdedc",
    "#17181a": "#ffffff",
    "#18191b": "#ffffff",
    "#34363a": "#cbc9c5",
    "#2d2f33": "#d2d0cc",
    "#72767d": "#8d8982",
    "#777b82": "#88847d",
    "#686c73": "#97938c",
    "#46505a": "#b9afa5",
    "#d7d9dd": "#282622",
    "#dedfe2": "#21201d",
    "#dfe1e4": "#201e1b",
    "#e2e3e5": "#1d1c1a",
    "#e5e6e8": "#1a1917",
    "#ececef": "#131310",
    "#eceeef": "#131110",
    "#e5e7e9": "#1a1816",
    "#e7e9eb": "#181614",
    "#f1f3f4": "#0e0c0b",
    "#f4f4f5": "#0b0b0a",
    "#a2a5aa": "#5d5a55",
    "#176b5b": "#b8ddd5",
    "#12594c": "#cde9e3",
    "#123d36": "#ecf7f5",
    "#dde4e2": "#221b1d",
    "#dde9e6": "#123d36",
    "#111111": "#ffffff",
    "#4d8f82": "#b2707d",
    "#b8ddd5": "#176b5b",
    "#9da1a6": "#625e59",
    "#285c52": "#d7a39a",
    "#e2efec": "#1d1013",
}


def build_app_style(theme: str, scale: int) -> str:
    """Return the existing visual language at the requested theme and scale."""
    style = APP_STYLE + SETTINGS_STYLE
    factor = scale / 100
    replacements = {
        "font-size: 14px": f"font-size: {max(12, round(14 * factor))}px",
        "font-size: 12px": f"font-size: {max(11, round(12 * factor))}px",
        "font-size: 18px": f"font-size: {round(18 * factor)}px",
        "font-size: 19px": f"font-size: {round(19 * factor)}px",
        "font-size: 24px": f"font-size: {round(24 * factor)}px",
        "min-height: 32px": f"min-height: {round(32 * factor)}px",
        "width: 12px": f"width: {max(10, round(12 * factor))}px",
        "margin: 0 4px": f"margin: 0 {max(3, round(4 * factor))}px",
        "width: 4px": f"width: {max(3, round(4 * factor))}px",
        "height: 4px": f"height: {max(3, round(4 * factor))}px",
    }
    for source, target in replacements.items():
        style = style.replace(source, target)
    if theme == "dark":
        style = re.sub(
            r"#[0-9a-fA-F]{6}",
            lambda match: _DARK_REPLACEMENTS.get(
                match.group(0).lower(), match.group(0)
            ),
            style,
        )
    return style


@lru_cache(maxsize=None)
def _painted_icon(name: str, theme: str = "light") -> QIcon:
    """Create a monochrome UI icon without loading PNG resources."""
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    icon_color = theme_colors(theme)["icon"]
    pen = QPen(QColor(icon_color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name in {"folder", "open"}:
        path = QPainterPath()
        path.moveTo(3.5, 7)
        path.lineTo(9, 7)
        path.lineTo(11, 9.5)
        path.lineTo(20.5, 9.5)
        path.lineTo(19.5, 19)
        path.lineTo(3.5, 19)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(4, 10, 20, 10)
    elif name == "search":
        painter.drawEllipse(QRectF(4, 4, 11, 11))
        painter.drawLine(14, 14, 20, 20)
    elif name == "info":
        painter.drawEllipse(QRectF(3.5, 3.5, 17, 17))
        painter.drawPoint(12, 8)
        painter.drawLine(12, 11, 12, 17)
    elif name == "refresh":
        painter.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 285 * 16)
        path = QPainterPath()
        path.moveTo(18.5, 3.5)
        path.lineTo(20.5, 8)
        path.lineTo(16, 7)
        path.closeSubpath()
        painter.setBrush(QColor(icon_color))
        painter.drawPath(path)
    elif name == "forward":
        painter.drawLine(4, 12, 19, 12)
        painter.drawLine(14, 7, 19, 12)
        painter.drawLine(14, 17, 19, 12)
    elif name == "trash":
        painter.drawLine(6, 7, 18, 7)
        painter.drawLine(9, 5, 15, 5)
        painter.drawRect(QRectF(7.5, 8.5, 9, 11))
        painter.drawLine(11, 11, 11, 17)
        painter.drawLine(14, 11, 14, 17)
    elif name == "file":
        path = QPainterPath()
        path.moveTo(6, 3.5)
        path.lineTo(14, 3.5)
        path.lineTo(19, 8.5)
        path.lineTo(19, 20.5)
        path.lineTo(6, 20.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(14, 4, 14, 9)
        painter.drawLine(14, 9, 19, 9)
    elif name == "close":
        painter.drawLine(7, 7, 17, 17)
        painter.drawLine(17, 7, 7, 17)
    elif name == "gear":
        # Six-tooth outline gear, sized to fill the same visual area as
        # the rebuild icon. Both the gear body and hub remain unfilled.
        gear = QPainterPath()
        center = QPointF(12, 12)
        outline_points: list[tuple[float, float]] = []
        for tooth in range(6):
            tooth_center = -90 + tooth * 60
            outline_points.extend(
                (
                    (tooth_center - 30, 7.2),
                    (tooth_center - 12, 9.6),
                    (tooth_center + 12, 9.6),
                    (tooth_center + 30, 7.2),
                )
            )
        for index, (angle_degrees, radius) in enumerate(outline_points):
            angle = math.radians(angle_degrees)
            point = QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius,
            )
            if index == 0:
                gear.moveTo(point)
            else:
                gear.lineTo(point)
        gear.closeSubpath()
        painter.drawPath(gear)
        painter.drawEllipse(QRectF(8.7, 8.7, 6.6, 6.6))

    painter.end()
    return QIcon(pixmap)


class AnimatedTreeDelegate(QStyledItemDelegate):
    """Paint tree rows with short vertical ease-out transitions."""

    def __init__(self, tree: "OrderedSubjectTree") -> None:
        super().__init__(tree)
        self.tree = tree
        self.offsets: dict[int, float] = {}
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._advance)
        self.animation.finished.connect(self._finish)
        self._starts: dict[int, float] = {}
        self.release_animation = QVariantAnimation(self)
        self.release_animation.setDuration(240)
        self.release_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.release_animation.setStartValue(1.035)
        self.release_animation.setEndValue(1.0)
        self.release_animation.valueChanged.connect(self._advance_release)
        self.release_animation.finished.connect(self._finish_release)
        self._release_item_id: int | None = None
        self._release_scale = 1.0

    def paint(self, painter, option, index) -> None:
        item = self.tree.itemFromIndex(index)
        painter.save()
        painter.translate(0, self.offsets.get(id(item), 0.0))
        if id(item) == self._release_item_id:
            center = option.rect.center()
            painter.translate(center)
            painter.scale(self._release_scale, self._release_scale)
            painter.translate(-center.x(), -center.y())
        if item is self.tree.dragged_item:
            painter.setOpacity(0.18)
        super().paint(painter, option, index)
        painter.restore()

    def visual_offset(self, item: QTreeWidgetItem) -> float:
        return self.offsets.get(id(item), 0.0)

    def animate_to_layout(
        self, old_tops: list[tuple[QTreeWidgetItem, float]]
    ) -> None:
        self.animation.stop()
        self._starts = {
            id(item): old_top - self.tree.visualItemRect(item).top()
            for item, old_top in old_tops
        }
        self.offsets = dict(self._starts)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def animate_release(self, item: QTreeWidgetItem) -> None:
        self._release_item_id = id(item)
        self._release_scale = 1.035
        self.release_animation.stop()
        self.release_animation.start()

    def _advance(self, value: Any) -> None:
        progress = float(value)
        self.offsets = {
            item_id: start * (1.0 - progress)
            for item_id, start in self._starts.items()
        }
        self.tree.viewport().update()

    def _finish(self) -> None:
        self.offsets.clear()
        self._starts.clear()
        self.tree.viewport().update()

    def _advance_release(self, value: Any) -> None:
        self._release_scale = float(value)
        self.tree.viewport().update()

    def _finish_release(self) -> None:
        self._release_item_id = None
        self._release_scale = 1.0
        self.tree.viewport().update()


class OrderedSubjectTree(QTreeWidget):
    """Tree allowing animated reordering of notes within one subject only."""

    order_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setAutoScroll(False)
        self.setAutoExpandDelay(-1)
        self.dragged_item: QTreeWidgetItem | None = None
        self._press_timer = QElapsedTimer()
        self._delegate = AnimatedTreeDelegate(self)
        self.setItemDelegate(self._delegate)
        self._active_drag: QDrag | None = None
        self._drag_visual_left = 0
        self._drag_hotspot_y = 0

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        # Require a short hold before entering drag mode; ordinary clicks and
        # quick pointer motions retain their original behavior.
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._press_timer.isValid()
            and self._press_timer.elapsed() < 180
        ):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_timer.invalidate()
        super().mouseReleaseEvent(event)

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        # Subject folders keep the default fixed ordering and never drag.
        if item is None or item.parent() is None:
            return
        rect = self.visualItemRect(item)
        scale_x, scale_y = 1.03, 1.06
        logical_size = QSize(
            max(1, round(rect.width() * scale_x)),
            max(1, round(rect.height() * scale_y)),
        )
        # Repaint the row at high pixel density instead of scaling a captured
        # bitmap. This keeps text and icons sharp while the drag item is lifted.
        pixel_ratio = max(2.0, self.viewport().devicePixelRatioF())
        lifted = QPixmap(
            round(logical_size.width() * pixel_ratio),
            round(logical_size.height() * pixel_ratio),
        )
        lifted.setDevicePixelRatio(pixel_ratio)
        lifted.fill(Qt.GlobalColor.transparent)
        index = self.indexFromItem(item)
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = QRect(0, 0, rect.width(), rect.height())
        self._delegate.initStyleOption(option, index)
        painter = QPainter(lifted)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.scale(scale_x, scale_y)
        self._delegate.paint(painter, option, index)
        painter.end()

        drag = QDrag(self)
        drag.setMimeData(self.mimeData([item]))
        drag.setPixmap(lifted)
        pointer = self.viewport().mapFromGlobal(QCursor.pos())
        hotspot_x = pointer.x() - rect.left()
        self._drag_visual_left = rect.left()
        self._drag_hotspot_y = logical_size.height() // 2
        drag.setHotSpot(
            QPoint(hotspot_x, self._drag_hotspot_y)
        )
        self._active_drag = drag
        self.dragged_item = item
        self.viewport().update()
        drag.exec(Qt.DropAction.MoveAction)
        self._active_drag = None
        self.dragged_item = None
        self._delegate.animate_release(item)
        self.viewport().update()

    def dragMoveEvent(self, event) -> None:
        """Swap only with an adjacent sibling as the pointer moves vertically."""
        source = self.currentItem()
        pointer = event.position().toPoint()
        if self._active_drag is not None:
            # Keep the drag pixmap's left edge anchored to its original row.
            # The mouse may move horizontally, but the visual only follows Y.
            self._active_drag.setHotSpot(
                QPoint(
                    pointer.x() - self._drag_visual_left,
                    self._drag_hotspot_y,
                )
            )
        # Sample the row at a fixed horizontal coordinate so left/right mouse
        # motion has no effect whatsoever on ordering or hierarchy.
        target = self.itemAt(QPoint(self.viewport().width() // 2, pointer.y()))
        if source is None:
            event.ignore()
            return

        source_parent = source.parent()
        # Subjects are fixed; notes may only exchange with siblings.
        if source_parent is None or target is None or target.parent() is not source_parent:
            event.ignore()
            return
        source_index = source_parent.indexOfChild(source)
        target_index = source_parent.indexOfChild(target)
        direction = (target_index > source_index) - (target_index < source_index)
        if direction:
            adjacent = source_parent.child(source_index + direction)
            old_tops = [
                (
                    source,
                    self.visualItemRect(source).top()
                    + self._delegate.visual_offset(source),
                ),
                (
                    adjacent,
                    self.visualItemRect(adjacent).top()
                    + self._delegate.visual_offset(adjacent),
                ),
            ]
            item = source_parent.takeChild(source_index)
            source_parent.insertChild(source_index + direction, item)
            self.setCurrentItem(source)
            self._delegate.animate_to_layout(old_tops)
            self.order_changed.emit()

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(self, event) -> None:
        """Finish the already-applied adjacent swaps without Qt moving again."""
        if self.currentItem() is None:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class ClearableLineEdit(QLineEdit):
    """Line edit with a painter-based trailing clear action."""

    def __init__(self, parent: QWidget | None = None, theme: str = "light") -> None:
        super().__init__(parent)
        self._clear_action = QAction(_painted_icon("close", theme), "清除", self)
        self._clear_action.setVisible(False)
        self._clear_action.triggered.connect(self.clear)
        self.addAction(self._clear_action, QLineEdit.ActionPosition.TrailingPosition)
        self.textChanged.connect(
            lambda text: self._clear_action.setVisible(bool(text))
        )

    def set_icon_theme(self, theme: str) -> None:
        self._clear_action.setIcon(_painted_icon("close", theme))


def _open_external_file(path: Path, executable: Path | None = None) -> bool:
    """Open a file without letting the associated app inherit our console."""
    if executable is not None:
        if not executable.is_file():
            return False
        return bool(QProcess.startDetached(str(executable), [str(path)]))
    if sys.platform != "win32":
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    import ctypes
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", wintypes.LPVOID),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    execute_info = ShellExecuteInfo()
    execute_info.cbSize = ctypes.sizeof(ShellExecuteInfo)
    execute_info.fMask = 0x00008000 | 0x00000400  # NO_CONSOLE | FLAG_NO_UI
    execute_info.lpVerb = "open"
    execute_info.lpFile = str(path)
    execute_info.lpDirectory = str(path.parent)
    execute_info.nShow = 1  # SW_SHOWNORMAL
    shell_execute = ctypes.windll.shell32.ShellExecuteExW
    shell_execute.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell_execute.restype = wintypes.BOOL
    electron_run_as_node = os.environ.pop("ELECTRON_RUN_AS_NODE", None)
    try:
        return bool(shell_execute(ctypes.byref(execute_info)))
    finally:
        if electron_run_as_node is not None:
            os.environ["ELECTRON_RUN_AS_NODE"] = electron_run_as_node


class SearchableMultiSelectPicker(QToolButton):
    """Compact searchable multi-select picker."""

    selection_changed = pyqtSignal()

    def __init__(
        self,
        *,
        search_placeholder: str,
        empty_text: str,
        single_template: str,
        multiple_template: str,
        empty_tooltip: str,
        tooltip_prefix: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._empty_text = empty_text
        self._single_template = single_template
        self._multiple_template = multiple_template
        self._empty_tooltip = empty_tooltip
        self._tooltip_prefix = tooltip_prefix
        self._updating = False
        self._pressed_item: QListWidgetItem | None = None
        self._pressed_check_state: Qt.CheckState | None = None
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.clicked.connect(self._toggle_popup)

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("multiSelectPopup")
        self._popup.setMinimumWidth(280)
        self._popup.setMaximumWidth(360)
        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search_input = ClearableLineEdit()
        self.search_input.setPlaceholderText(search_placeholder)
        self.search_input.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_input)

        self.toggle_all_button = QPushButton("全选")
        self.toggle_all_button.clicked.connect(self._toggle_visible_items)
        layout.addWidget(self.toggle_all_button)

        self.item_list = QListWidget()
        self.item_list.setObjectName("multiSelectList")
        self.item_list.setMinimumHeight(220)
        self.item_list.setMaximumHeight(320)
        self.item_list.itemPressed.connect(self._remember_check_state)
        self.item_list.itemClicked.connect(self._toggle_clicked_item)
        self.item_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.item_list)

        clear_button = QPushButton("清除选择")
        clear_button.clicked.connect(self.clear_selection)
        layout.addWidget(clear_button)

        self._popup.setFocusProxy(self.search_input)
        self._update_summary()

    def set_items(self, values: list[str]) -> None:
        selected = set(self.selected_items())
        self._updating = True
        self.item_list.clear()
        for value in values:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if value in selected
                else Qt.CheckState.Unchecked
            )
            self.item_list.addItem(item)
        self._updating = False
        self._update_summary()

    def selected_items(self) -> list[str]:
        return [
            self.item_list.item(row).text()
            for row in range(self.item_list.count())
            if self.item_list.item(row).checkState() == Qt.CheckState.Checked
        ]

    def set_selected_items(
        self, values: list[str] | tuple[str, ...] | None
    ) -> None:
        selected = {value for value in (values or []) if value}
        self._updating = True
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.text() in selected
                else Qt.CheckState.Unchecked
            )
        self._updating = False
        self._update_summary()

    def clear_selection(self) -> None:
        if not self.selected_items():
            return
        self.set_selected_items([])
        self.selection_changed.emit()

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.close()
            return
        self._show_popup()

    def _show_popup(self) -> None:
        self.search_input.clear()
        self._popup.setFixedWidth(max(280, min(self.width(), 360)))
        self._popup.adjustSize()
        position = self.mapToGlobal(QPoint(0, self.height()))
        screen = QApplication.screenAt(position) or self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            position.setX(
                max(
                    available.left(),
                    min(position.x(), available.right() - self._popup.width() + 1),
                )
            )
            if position.y() + self._popup.height() > available.bottom() + 1:
                position.setY(
                    self.mapToGlobal(QPoint(0, 0)).y() - self._popup.height()
                )
        self._popup.move(position)
        self._popup.show()
        self._popup.raise_()
        self._popup.activateWindow()
        self.search_input.setFocus(Qt.FocusReason.PopupFocusReason)
        QTimer.singleShot(
            0,
            lambda: self.search_input.setFocus(Qt.FocusReason.PopupFocusReason),
        )

    def _filter_items(self, query: str) -> None:
        normalized_query = query.strip().casefold()
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            item.setHidden(
                bool(normalized_query)
                and normalized_query not in item.text().casefold()
            )
        self._update_toggle_all_button()

    def _visible_items(self) -> list[QListWidgetItem]:
        return [
            self.item_list.item(row)
            for row in range(self.item_list.count())
            if not self.item_list.item(row).isHidden()
        ]

    def _toggle_visible_items(self) -> None:
        items = self._visible_items()
        if not items:
            return
        all_selected = all(
            item.checkState() == Qt.CheckState.Checked for item in items
        )
        target_state = (
            Qt.CheckState.Unchecked if all_selected else Qt.CheckState.Checked
        )
        self._updating = True
        for item in items:
            item.setCheckState(target_state)
        self._updating = False
        self._update_summary()
        self.selection_changed.emit()

    def _update_toggle_all_button(self) -> None:
        items = self._visible_items()
        all_selected = bool(items) and all(
            item.checkState() == Qt.CheckState.Checked for item in items
        )
        self.toggle_all_button.setText("全不选" if all_selected else "全选")
        self.toggle_all_button.setEnabled(bool(items))

    def _remember_check_state(self, item: QListWidgetItem) -> None:
        self._pressed_item = item
        self._pressed_check_state = item.checkState()

    def _toggle_clicked_item(self, item: QListWidgetItem) -> None:
        if item is not self._pressed_item or self._pressed_check_state is None:
            return
        if item.checkState() == self._pressed_check_state:
            item.setCheckState(
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
        self._pressed_item = None
        self._pressed_check_state = None

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        if self._updating:
            return
        self._update_summary()
        self.selection_changed.emit()

    def _update_summary(self) -> None:
        selected = self.selected_items()
        if not selected:
            text = self._empty_text
        elif len(selected) == 1:
            text = self._single_template.format(item=selected[0], count=1)
        else:
            text = self._multiple_template.format(count=len(selected))
        self.setText(f"{text}  ▾")
        self.setToolTip(
            self._tooltip_prefix + "：" + "、".join(selected)
            if selected
            else self._empty_tooltip
        )
        self._update_toggle_all_button()


class SearchableSingleSelectPicker(QToolButton):
    """Searchable single-select picker matching the multi-select controls."""

    selection_changed = pyqtSignal()

    def __init__(
        self,
        *,
        search_placeholder: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_data: Any = None
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.clicked.connect(self._toggle_popup)

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("multiSelectPopup")
        self._popup.setMinimumWidth(280)
        self._popup.setMaximumWidth(360)
        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search_input = ClearableLineEdit()
        self.search_input.setPlaceholderText(search_placeholder)
        self.search_input.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_input)

        self.item_list = QListWidget()
        self.item_list.setObjectName("multiSelectList")
        self.item_list.setMinimumHeight(120)
        self.item_list.setMaximumHeight(220)
        self.item_list.itemClicked.connect(self._select_item)
        layout.addWidget(self.item_list)

        self._popup.setFocusProxy(self.search_input)

    def set_items(self, items: list[tuple[str, Any]]) -> None:
        self.item_list.clear()
        for label, data in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.item_list.addItem(item)
        self.set_current_data(self._current_data)

    def currentData(self) -> Any:
        return self._current_data

    def set_current_data(self, data: Any) -> None:
        selected_item: QListWidgetItem | None = None
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == data:
                selected_item = item
                break
        if selected_item is None and self.item_list.count():
            selected_item = self.item_list.item(0)
        if selected_item is None:
            self._current_data = None
            self.setText("  ▾")
            return
        self._current_data = selected_item.data(Qt.ItemDataRole.UserRole)
        self.item_list.setCurrentItem(selected_item)
        self.setText(f"{selected_item.text()}  ▾")
        self.setToolTip(f"笔记类型：{selected_item.text()}")

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.close()
            return
        self.search_input.clear()
        self._popup.setFixedWidth(max(280, min(self.width(), 360)))
        self._popup.adjustSize()
        position = self.mapToGlobal(QPoint(0, self.height()))
        screen = QApplication.screenAt(position) or self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            position.setX(
                max(
                    available.left(),
                    min(position.x(), available.right() - self._popup.width() + 1),
                )
            )
            if position.y() + self._popup.height() > available.bottom() + 1:
                position.setY(
                    self.mapToGlobal(QPoint(0, 0)).y() - self._popup.height()
                )
        self._popup.move(position)
        self._popup.show()
        self._popup.raise_()
        self._popup.activateWindow()
        self.search_input.setFocus(Qt.FocusReason.PopupFocusReason)
        QTimer.singleShot(
            0,
            lambda: self.search_input.setFocus(Qt.FocusReason.PopupFocusReason),
        )

    def _filter_items(self, query: str) -> None:
        normalized_query = query.strip().casefold()
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            item.setHidden(
                bool(normalized_query)
                and normalized_query not in item.text().casefold()
            )

    def _select_item(self, item: QListWidgetItem) -> None:
        previous_data = self._current_data
        self.set_current_data(item.data(Qt.ItemDataRole.UserRole))
        self._popup.close()
        if self._current_data != previous_data:
            self.selection_changed.emit()


class IndexWorker(QObject):
    """Build the inverted index without blocking the GUI thread."""

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        notes_root: Path,
        base_dir: Path,
        index_path: Path,
        database_path: Path,
        index_base_dir: Path,
        auto_generate_samples: bool,
    ) -> None:
        super().__init__()
        self.notes_root = notes_root
        self.base_dir = base_dir
        self.index_path = index_path
        self.database_path = database_path
        self.index_base_dir = index_base_dir
        self.auto_generate_samples = auto_generate_samples

    def run(self) -> None:
        """Generate samples when needed, then rebuild and save the index."""
        try:
            self.notes_root.mkdir(parents=True, exist_ok=True)
            if self.auto_generate_samples and not any(self.notes_root.rglob("*.md")):
                generate_sample_notes(self.notes_root)
            index = build_index(self.notes_root, base_dir=self.index_base_dir)
            save_index(index, self.index_path)
            sync_note_catalog(index, self.index_base_dir, self.database_path)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(index)


class MainWindow(QMainWindow):
    """Desktop workspace for note browsing, search, and read-only preview."""

    def __init__(
        self,
        base_dir: Path,
        notes_root: Path,
        index_path: Path,
        *,
        preloaded_settings: dict[str, Any] | None = None,
        preloaded_index: dict[str, Any] | None = None,
        preloaded_history: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            self.setWindowIcon(app.windowIcon())
        self.base_dir = base_dir.resolve()
        self.default_notes_root = notes_root.resolve()
        self.index_path = index_path.resolve()
        self.database_path = self.index_path.with_name("notemanager.db")
        if preloaded_settings is None:
            try:
                stored_settings = load_app_settings(self.database_path)
            except (OSError, sqlite3.Error):
                stored_settings = {}
        else:
            stored_settings = dict(preloaded_settings)
        self.settings = normalized_settings(stored_settings, self.default_notes_root)
        self.notes_root = Path(self.settings["notes_root"]).resolve()
        self.theme = resolved_theme(str(self.settings["theme"]), QApplication.instance())
        self.index: dict[str, Any] = preloaded_index or {
            "documents": {},
            "inverted_index": {},
        }
        self.current_query = ""
        self.search_history = (
            list(preloaded_history)
            if preloaded_history is not None
            else self._load_history()
        )
        self._last_preview: QTextBrowser | None = None
        self._last_note_path = ""
        self._preview_parts: dict[
            QTextBrowser, tuple[QLabel, QLabel, QPushButton]
        ] = {}
        self._preview_notes: dict[QTextBrowser, Note] = {}
        self._index_thread: QThread | None = None
        self._index_worker: IndexWorker | None = None
        self._reading_state_restored = False
        self._live_search_timer = QTimer(self)
        self._live_search_timer.setSingleShot(True)
        self._live_search_timer.setInterval(350)
        self._live_search_timer.timeout.connect(self.perform_search)
        style_hints = QApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(
                self._on_system_color_scheme_changed
            )

        self.setWindowTitle("NoteManager")
        self.resize(1380, 860)
        self.setMinimumSize(980, 640)
        self._apply_appearance_settings(refresh_content=False)
        self._build_ui()
        self._apply_appearance_settings()
        self._apply_startup_page()
        if preloaded_index is None:
            self._load_initial_index()
        else:
            self._refresh_from_index()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.workspace = QStackedWidget()
        self.library_page, self.library_list, self.library_preview = self._build_library_page()
        self.search_page, self.search_results, self.search_preview = self._build_search_page()
        self.teaching_page = self._build_teaching_page()
        self.settings_page = SettingsPage(self.settings)
        self.settings_page.setting_changed.connect(self._on_setting_changed)
        self.settings_page.action_requested.connect(self._on_settings_action)
        self.workspace.addWidget(self.library_page)
        self.workspace.addWidget(self.search_page)
        self.workspace.addWidget(self.teaching_page)
        self.workspace.addWidget(self.settings_page)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.workspace, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("正在载入笔记...")

    def _standard_icon(self, pixmap: QStyle.StandardPixmap) -> QIcon:
        icon_names = {
            QStyle.StandardPixmap.SP_DirOpenIcon: "folder",
            QStyle.StandardPixmap.SP_DirIcon: "folder",
            QStyle.StandardPixmap.SP_DialogOpenButton: "open",
            QStyle.StandardPixmap.SP_FileDialogContentsView: "search",
            QStyle.StandardPixmap.SP_MessageBoxInformation: "info",
            QStyle.StandardPixmap.SP_BrowserReload: "refresh",
            QStyle.StandardPixmap.SP_ArrowForward: "forward",
            QStyle.StandardPixmap.SP_TrashIcon: "trash",
            QStyle.StandardPixmap.SP_FileIcon: "file",
        }
        return _painted_icon(icon_names.get(pixmap, "file"), self.theme)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(238)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 2, 0, 13)
        brand_row.setSpacing(8)
        brand_icon = QLabel()
        brand_icon.setObjectName("brandIcon")
        brand_icon.setFixedSize(22, 22)
        app_icon = QApplication.windowIcon()
        if app_icon.isNull():
            app_icon = QIcon(
                str(Path(__file__).resolve().parent / "assets" / "notemanager.svg")
            )
        brand_icon.setPixmap(app_icon.pixmap(QSize(22, 22)))
        brand_icon.setToolTip("NoteManager")
        brand_row.addWidget(brand_icon)

        brand = QLabel("NoteManager")
        brand.setObjectName("brand")
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_specs = [
            ("笔记库", QStyle.StandardPixmap.SP_DirOpenIcon, 0),
            ("全文搜索", QStyle.StandardPixmap.SP_FileDialogContentsView, 1),
            ("教学对话", QStyle.StandardPixmap.SP_MessageBoxInformation, 2),
        ]
        self.nav_buttons: dict[int, tuple[QPushButton, QStyle.StandardPixmap]] = {}
        for label, icon, page_index in nav_specs:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setIcon(self._standard_icon(icon))
            button.setIconSize(QSize(17, 17))
            button.clicked.connect(lambda checked, i=page_index: self._switch_page(i))
            self.nav_group.addButton(button, page_index)
            self.nav_buttons[page_index] = (button, icon)
            layout.addWidget(button)
        self.nav_group.button(0).setChecked(True)

        section = QLabel("科目")
        section.setObjectName("sectionLabel")
        section.setContentsMargins(8, 15, 0, 2)
        layout.addWidget(section)

        self.subject_tree = (
            OrderedSubjectTree() if ENABLE_MANUAL_NOTE_ORDER else QTreeWidget()
        )
        self.subject_tree.setHeaderHidden(True)
        self.subject_tree.setIndentation(16)
        self.subject_tree.itemClicked.connect(self._on_tree_item_clicked)
        if isinstance(self.subject_tree, OrderedSubjectTree):
            self.subject_tree.order_changed.connect(self._on_note_order_changed)
        layout.addWidget(self.subject_tree, 1)

        self.rebuild_button = QPushButton("重建索引")
        self.rebuild_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.rebuild_button.setIconSize(QSize(17, 17))
        self.rebuild_button.setToolTip("重新扫描全部 Markdown 笔记")
        self.rebuild_button.clicked.connect(self.rebuild_index)
        layout.addWidget(self.rebuild_button)
        self.settings_button = QPushButton("设置")
        self.settings_button.setIcon(_painted_icon("gear", self.theme))
        self.settings_button.setIconSize(QSize(17, 17))
        self.settings_button.setToolTip("打开个性化设置")
        self.settings_button.clicked.connect(lambda: self._switch_page(3))
        layout.addWidget(self.settings_button)
        return sidebar

    def _build_library_page(self) -> tuple[QWidget, QListWidget, QTextBrowser]:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        list_panel = QFrame()
        list_panel.setObjectName("panelDivider")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(22, 20, 18, 16)
        heading = QLabel("全部笔记")
        heading.setObjectName("pageTitle")
        self.library_heading = heading
        list_layout.addWidget(heading)
        self.library_count = QLabel()
        self.library_count.setObjectName("muted")
        list_layout.addWidget(self.library_count)
        note_list = QListWidget()
        note_list.setSpacing(1)
        note_list.setWordWrap(True)
        note_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        note_list.currentItemChanged.connect(self._on_library_note_changed)
        list_layout.addWidget(note_list, 1)

        preview_panel, preview = self._build_preview_panel()
        splitter.addWidget(list_panel)
        splitter.addWidget(preview_panel)
        splitter.setSizes([370, 750])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        return page, note_list, preview

    def _build_search_page(self) -> tuple[QWidget, QListWidget, QTextBrowser]:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        search_panel = QFrame()
        search_panel.setObjectName("panelDivider")
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(22, 20, 18, 16)

        title = QLabel("全文搜索")
        title.setObjectName("pageTitle")
        search_layout.addWidget(title)

        query_row = QHBoxLayout()
        query_row.setSpacing(7)
        self.query_input = ClearableLineEdit()
        self.query_input.setPlaceholderText("搜索标题、章节、标签和正文")
        self.query_input.returnPressed.connect(self.perform_search)
        self.query_input.textChanged.connect(self._on_query_text_changed)
        query_row.addWidget(self.query_input, 1)
        self.search_button = QToolButton()
        self.search_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.search_button.setToolTip("搜索")
        self.search_button.clicked.connect(lambda: self.perform_search())
        query_row.addWidget(self.search_button)
        search_layout.addLayout(query_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(7)
        self.subject_filter = SearchableMultiSelectPicker(
            search_placeholder="搜索科目",
            empty_text="全部科目",
            single_template="{item}",
            multiple_template="已选择 {count} 个科目",
            empty_tooltip="选择要搜索的科目",
            tooltip_prefix="搜索科目",
        )
        self.subject_filter.selection_changed.connect(self._rerun_active_search)
        filter_row.addWidget(self.subject_filter, 1)
        self.type_filter = SearchableSingleSelectPicker(
            search_placeholder="搜索类型",
        )
        self.type_filter.set_items(
            [
                ("全部类型", None),
                ("期末", "exam"),
                ("考研", "postgraduate"),
            ]
        )
        self.type_filter.selection_changed.connect(self._rerun_active_search)
        filter_row.addWidget(self.type_filter, 1)
        self.exclude_tag_filter = SearchableMultiSelectPicker(
            search_placeholder="搜索标签",
            empty_text="不过滤标签",
            single_template="排除：{item}",
            multiple_template="已排除 {count} 个标签",
            empty_tooltip="选择要排除的标签",
            tooltip_prefix="排除标签",
        )
        self.exclude_tag_filter.selection_changed.connect(self._rerun_active_search)
        filter_row.addWidget(self.exclude_tag_filter, 1)
        search_layout.addLayout(filter_row)

        history_row = QHBoxLayout()
        self.search_section_title = QLabel("最近搜索")
        self.search_section_title.setObjectName("sectionLabel")
        history_row.addWidget(self.search_section_title)
        history_row.addStretch(1)
        self.clear_history_button = QToolButton()
        self.clear_history_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.clear_history_button.setToolTip("清空搜索历史")
        self.clear_history_button.clicked.connect(self.clear_search_history)
        history_row.addWidget(self.clear_history_button)
        search_layout.addLayout(history_row)

        results = QListWidget()
        results.setSpacing(1)
        results.setWordWrap(True)
        results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results.itemClicked.connect(self._activate_search_item)
        results.itemActivated.connect(self._activate_search_item)
        results.currentItemChanged.connect(self._on_search_item_changed)
        search_layout.addWidget(results, 1)
        self._show_search_history(results)

        preview_panel, preview = self._build_preview_panel()
        splitter.addWidget(search_panel)
        splitter.addWidget(preview_panel)
        splitter.setSizes([410, 710])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        return page, results, preview

    def _build_preview_panel(self) -> tuple[QFrame, QTextBrowser]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 22, 30, 20)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("选择一篇笔记")
        title.setObjectName("noteTitle")
        title.setWordWrap(True)
        meta = QLabel("从左侧列表打开只读预览")
        meta.setObjectName("muted")
        meta.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(meta)
        top.addLayout(title_box, 1)
        open_button = QPushButton("外部打开")
        open_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        open_button.setEnabled(False)
        top.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        browser = MarkdownPreview()
        browser.set_render_settings(
            theme=self.theme,
            body_size=str(self.settings["note_font_size"]),
            code_size=str(self.settings["code_font_size"]),
            body_font=str(self.settings["body_font"]),
            code_font=str(self.settings["code_font"]),
        )
        browser.setOpenExternalLinks(True)
        browser.setReadOnly(True)
        browser.setFrameShape(QFrame.Shape.NoFrame)
        browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setPlaceholderText("笔记内容将在这里显示")
        self._preview_parts[browser] = (title, meta, open_button)
        open_button.clicked.connect(lambda: self.open_preview_note(browser))
        layout.addWidget(browser, 1)
        return panel, browser

    def _build_teaching_page(self) -> QWidget:
        from src.gui.teaching_page import TeachingPage

        def open_model_settings() -> None:
            self._switch_page(3)
            self.settings_page.categories.setCurrentRow(4)

        return TeachingPage(
            lambda: self.settings, lambda: self.notes_root,
            self.base_dir / "data" / "external", open_model_settings, self,
        )

    def _switch_page(self, page_index: int) -> None:
        self.workspace.setCurrentIndex(page_index)
        button = self.nav_group.button(page_index)
        if button is not None:
            button.setChecked(True)
        elif page_index == 3:
            self.nav_group.setExclusive(False)
            for nav_button in self.nav_group.buttons():
                nav_button.setChecked(False)
            self.nav_group.setExclusive(True)
        if page_index == 1:
            self.query_input.setFocus()
        elif page_index == 3:
            self._refresh_storage_status()

    def _apply_startup_page(self) -> None:
        self._switch_page(1 if self.settings["startup_page"] == "search" else 0)

    def _index_base_dir(self) -> Path:
        try:
            self.notes_root.relative_to(self.base_dir)
        except ValueError:
            return self.notes_root
        return self.base_dir

    def _prompt_rebuild_for_changes(self) -> None:
        answer = QMessageBox.question(
            self,
            "检测到笔记变化",
            "笔记目录中的文件与现有索引不一致，是否现在重建索引？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.rebuild_index()

    def _load_initial_index(self) -> None:
        if not self.index_path.exists():
            QTimer.singleShot(0, self.rebuild_index)
            return
        try:
            self.index = load_index(self.index_path)
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"索引读取失败: {exc}")
            QTimer.singleShot(0, self.rebuild_index)
            return
        self._refresh_from_index()

    def complete_startup(
        self,
        *,
        index_missing: bool = False,
        index_stale: bool = False,
        index_error: str = "",
    ) -> None:
        """Handle startup checks after the main window becomes visible."""
        if index_error:
            self.statusBar().showMessage(f"索引读取失败: {index_error}")
            QTimer.singleShot(0, self.rebuild_index)
            return
        if index_missing:
            self.statusBar().showMessage("未找到全文索引，正在按需构建...")
            QTimer.singleShot(0, self.rebuild_index)
            return
        if not index_stale:
            return
        if self.settings["index_strategy"] == "prompt":
            QTimer.singleShot(0, self._prompt_rebuild_for_changes)
        else:
            self.statusBar().showMessage(
                "检测到笔记文件变化，可点击“重建索引”更新内容", 8000
            )

    def rebuild_index(self) -> None:
        """Rebuild the note index in a worker thread."""
        if self._index_thread is not None and self._index_thread.isRunning():
            return
        self.rebuild_button.setEnabled(False)
        self.rebuild_button.setText("正在重建...")
        self.statusBar().showMessage("正在扫描 Markdown 笔记并重建索引...")

        thread = QThread(self)
        worker = IndexWorker(
            self.notes_root,
            self.base_dir,
            self.index_path,
            self.database_path,
            self._index_base_dir(),
            bool(self.settings["auto_generate_samples"]),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_index_rebuilt)
        worker.failed.connect(self._on_index_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_index_worker)
        self._index_thread = thread
        self._index_worker = worker
        thread.start()

    def _on_index_rebuilt(self, index: dict) -> None:
        self.index = index
        self._refresh_from_index()
        count = len(index.get("documents", {}))
        self.statusBar().showMessage(f"索引已更新，共 {count} 篇笔记", 5000)
        self.rebuild_button.setEnabled(True)
        self.rebuild_button.setText("重建索引")
        self._refresh_storage_status()

    def _on_index_failed(self, message: str) -> None:
        self.rebuild_button.setEnabled(True)
        self.rebuild_button.setText("重建索引")
        self.statusBar().showMessage("索引重建失败")
        QMessageBox.critical(self, "索引重建失败", message)

    def _clear_index_worker(self) -> None:
        self._index_thread = None
        self._index_worker = None

    def _refresh_from_index(self) -> None:
        self._populate_subject_tree()
        self._populate_subject_filter()
        self._populate_tag_filter()
        self._populate_library()
        if self.current_query:
            self.perform_search(record_history=False)
        count = len(self._documents())
        self.statusBar().showMessage(f"已载入 {count} 篇笔记", 4000)
        QTimer.singleShot(0, self._restore_reading_state)

    def _documents(self) -> list[tuple[str, dict[str, Any]]]:
        documents = self.index.get("documents", {})
        visible_documents = documents.items()
        if not self.settings["show_sample_notes"]:
            visible_documents = (
                (path, document)
                for path, document in visible_documents
                if "示例" not in document.get("tags", [])
            )
        saved_note_order = (
            self.settings.get("note_order", {}) if ENABLE_MANUAL_NOTE_ORDER else {}
        )

        def order_key(pair: tuple[str, dict[str, Any]]) -> tuple[Any, ...]:
            path, document = pair
            subject = str(document.get("subject", ""))
            subject_key: tuple[Any, ...] = (subject,)
            paths = saved_note_order.get(subject, [])
            try:
                note_key: tuple[Any, ...] = (0, paths.index(path))
            except (AttributeError, ValueError):
                note_key = (
                    1,
                    str(document.get("chapter", "")),
                    str(document.get("title", "")),
                )
            return (*subject_key, *note_key)

        return sorted(
            visible_documents,
            key=order_key,
        )

    def _subjects(self) -> list[str]:
        return sorted({doc.get("subject", "") for _, doc in self._documents() if doc.get("subject")})

    def _tags(self) -> list[str]:
        return sorted({
            str(tag)
            for _, doc in self._documents()
            for tag in doc.get("tags", [])
            if str(tag).strip()
        })

    def _populate_subject_tree(self) -> None:
        self.subject_tree.clear()
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for path, doc in self._documents():
            grouped.setdefault(str(doc.get("subject", "未分类")), []).append((path, doc))
        for subject, notes in grouped.items():
            parent = QTreeWidgetItem([subject])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            parent.setData(0, Qt.ItemDataRole.UserRole, {"subject": subject})
            parent.setIcon(0, self._standard_icon(QStyle.StandardPixmap.SP_DirIcon))
            self.subject_tree.addTopLevelItem(parent)
            for path, doc in notes:
                child = QTreeWidgetItem([str(doc.get("title", Path(path).stem))])
                child.setData(0, Qt.ItemDataRole.UserRole, {"path": path})
                child.setToolTip(0, str(doc.get("chapter", "")))
                child.setIcon(0, self._standard_icon(QStyle.StandardPixmap.SP_FileIcon))
                parent.addChild(child)
            parent.setExpanded(True)

    def _on_note_order_changed(self) -> None:
        """Persist the tree order and immediately mirror it in All Notes."""
        note_order: dict[str, list[str]] = {}
        for subject_index in range(self.subject_tree.topLevelItemCount()):
            parent = self.subject_tree.topLevelItem(subject_index)
            parent_data = parent.data(0, Qt.ItemDataRole.UserRole) or {}
            subject = str(parent_data.get("subject", ""))
            if not subject:
                continue
            paths: list[str] = []
            for note_index in range(parent.childCount()):
                child_data = (
                    parent.child(note_index).data(0, Qt.ItemDataRole.UserRole) or {}
                )
                path = child_data.get("path")
                if path:
                    paths.append(str(path))
            note_order[subject] = paths

        self.settings["note_order"] = note_order
        try:
            save_app_settings(
                self.database_path,
                {"note_order": note_order},
            )
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "顺序保存失败", str(exc))
            return
        self._populate_library()
        self.statusBar().showMessage("笔记顺序已保存", 3000)

    def _populate_subject_filter(self) -> None:
        self.subject_filter.set_items(self._subjects())

    def _populate_tag_filter(self) -> None:
        self.exclude_tag_filter.set_items(self._tags())

    def _populate_library(self, subject: str | None = None) -> None:
        self.library_list.clear()
        shown = 0
        for path, doc in self._documents():
            if subject and doc.get("subject") != subject:
                continue
            item = QListWidgetItem(self._note_item_text(doc))
            item.setData(Qt.ItemDataRole.UserRole, {"path": path})
            item.setToolTip(path)
            self.library_list.addItem(item)
            shown += 1
        self.library_heading.setText(subject or "全部笔记")
        self.library_count.setText(f"{shown} 篇笔记")

    @staticmethod
    def _note_item_text(doc: dict[str, Any], score: float | None = None) -> str:
        type_label = "期末" if doc.get("note_type") == "exam" else "考研"
        title = str(doc.get("title", "未命名笔记"))
        subject = str(doc.get("subject", "未分类"))
        chapter = str(doc.get("chapter", ""))
        suffix = f"  ·  匹配度 {score:.1f}" if score is not None else ""
        return f"{title}\n{subject}  ·  {chapter}  ·  {type_label}{suffix}"

    def _on_tree_item_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        path = data.get("path")
        if path:
            self._switch_page(0)
            self._select_library_path(path)
            return
        subject = data.get("subject")
        if subject:
            self._switch_page(0)
            self._populate_library(subject)

    def _select_library_path(self, path: str) -> None:
        self._populate_library()
        for row in range(self.library_list.count()):
            item = self.library_list.item(row)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            if data.get("path") == path:
                self.library_list.setCurrentItem(item)
                self.library_list.scrollToItem(item)
                break

    def _on_library_note_changed(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole) or {}
        path = data.get("path")
        if path:
            self._show_note(path, self.library_preview)

    def _on_query_text_changed(self, text: str) -> None:
        if self.settings["search_mode"] != "live":
            return
        self._live_search_timer.stop()
        if text.strip():
            self._live_search_timer.start()
        else:
            self.current_query = ""
            self._show_search_history(self.search_results)

    def perform_search(self, record_history: bool = True) -> None:
        """Run a full-text search using the active filters."""
        query = self.query_input.text().strip()
        if not query:
            self.current_query = ""
            self._show_search_history(self.search_results)
            return
        self.current_query = query
        if record_history:
            self._record_history(query)
        excluded_tags = self.exclude_tag_filter.selected_items()
        if not self.settings["show_sample_notes"] and "示例" not in excluded_tags:
            excluded_tags = [*excluded_tags, "示例"]
        results = search(
            query,
            self.index,
            note_type=self.type_filter.currentData(),
            subject=self.subject_filter.selected_items(),
            exclude_tag=excluded_tags,
            top_k=100,
        )
        self.search_results.clear()
        self.search_section_title.setText(f"搜索结果 · {len(results)}")
        self.clear_history_button.setVisible(False)
        for result in results:
            item = QListWidgetItem(self._note_item_text(result, result.get("score", 0.0)))
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "result", **result})
            item.setToolTip(str(result.get("path", "")))
            self.search_results.addItem(item)
        if results:
            self.search_results.setCurrentRow(0)
            self.statusBar().showMessage(f"找到 {len(results)} 条结果", 4000)
        else:
            empty = QListWidgetItem("未找到匹配笔记\n请调整关键词或筛选条件")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.search_results.addItem(empty)
            self._clear_preview(self.search_preview, "没有匹配结果", "请调整关键词或筛选条件")
            self.statusBar().showMessage("未找到匹配笔记", 4000)

    def _rerun_active_search(self) -> None:
        if self.current_query:
            self.perform_search(record_history=False)

    def _on_search_item_changed(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") == "result" and data.get("path"):
            self._show_note(data["path"], self.search_preview, self.current_query)

    def _activate_search_item(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") == "history":
            self.current_query = ""
            self.subject_filter.set_selected_items(data.get("subjects"))
            self.type_filter.set_current_data(data.get("note_type"))
            self.exclude_tag_filter.set_selected_items(data.get("exclude_tags"))
            self.query_input.setText(data.get("query", ""))
            self.perform_search()

    def _show_note(self, relative_path: str, preview: QTextBrowser, query: str = "") -> None:
        path = self._resolve_note_path(relative_path)
        try:
            note = parse_markdown(path)
        except (OSError, ValueError, FileNotFoundError) as exc:
            self._clear_preview(preview, "无法打开笔记", str(exc))
            self.statusBar().showMessage(f"笔记读取失败: {path.name}")
            return
        title, meta, open_button = self._preview_parts[preview]
        type_label = "期末" if note.note_type == "exam" else "考研"
        tags = " · ".join(note.tags)
        details = f"{note.subject}  ·  {note.chapter}  ·  {type_label}"
        if tags:
            details += f"\n{tags}"
        title.setText(note.title)
        meta.setText(details)
        open_button.setEnabled(True)
        self._preview_notes[preview] = note
        self._last_preview = preview
        self._last_note_path = relative_path
        preview.set_markdown(note.body, note.file_path.parent if note.file_path else None)
        preview.moveCursor(QTextCursor.MoveOperation.Start)
        self._highlight_query(preview, query)

    def _resolve_note_path(self, relative_path: str) -> Path:
        candidate = (self.base_dir / relative_path).resolve()
        try:
            candidate.relative_to(self.notes_root)
        except ValueError:
            fallback = (self.notes_root / relative_path).resolve()
            fallback.relative_to(self.notes_root)
            return fallback
        return candidate

    def _highlight_query(self, preview: QTextBrowser, query: str) -> None:
        preview.setExtraSelections([])
        if not query:
            return
        selections: list[QTextEdit.ExtraSelection] = []
        cursor = QTextCursor(preview.document())
        highlight = QTextCharFormat()
        colors = theme_colors(self.theme)
        highlight.setBackground(QColor(colors["highlight"]))
        highlight.setForeground(QColor(colors["text"]))
        while True:
            cursor = preview.document().find(query, cursor)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight
            selections.append(selection)
        preview.setExtraSelections(selections)

    def _clear_preview(
        self, preview: QTextBrowser, title_text: str, meta_text: str
    ) -> None:
        title, meta, open_button = self._preview_parts[preview]
        title.setText(title_text)
        meta.setText(meta_text)
        open_button.setEnabled(False)
        self._preview_notes.pop(preview, None)
        preview.clear()

    def open_preview_note(self, preview: QTextBrowser) -> None:
        """Open the note displayed by a preview in the default editor."""
        note = self._preview_notes.get(preview)
        if note is None or note.file_path is None:
            return
        executable = None
        if self.settings["external_editor_mode"] == "custom":
            configured = str(self.settings["external_editor_path"]).strip()
            executable = Path(configured) if configured else Path()
        opened = _open_external_file(note.file_path, executable)
        if not opened:
            QMessageBox.warning(
                self,
                "无法打开笔记",
                "指定的编辑器不可用，请在设置中重新选择。"
                if executable is not None
                else "系统未找到可用的 Markdown 编辑器。",
            )

    def _load_history(self) -> list[dict[str, Any]]:
        if not self.settings["history_enabled"]:
            return []
        try:
            return load_search_history(
                self.database_path, int(self.settings["history_limit"])
            )
        except (OSError, sqlite3.Error):
            return []

    def _record_history(self, query: str) -> None:
        if not self.settings["history_enabled"]:
            return
        history_limit = int(self.settings["history_limit"])
        try:
            record_search(
                self.database_path,
                query,
                subject=self.subject_filter.selected_items(),
                note_type=self.type_filter.currentData(),
                exclude_tag=self.exclude_tag_filter.selected_items(),
                limit=history_limit,
            )
            self.search_history = load_search_history(
                self.database_path, history_limit
            )
        except (OSError, sqlite3.Error) as exc:
            self.statusBar().showMessage(f"搜索历史写入失败: {exc}", 5000)

    def _show_search_history(self, target: QListWidget) -> None:
        target.clear()
        self.search_section_title.setText("最近搜索")
        self.clear_history_button.setVisible(True)
        self.clear_history_button.setEnabled(bool(self.settings["history_enabled"]))
        if not self.settings["history_enabled"]:
            empty = QListWidgetItem("搜索历史已关闭")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            target.addItem(empty)
            return
        if not self.search_history:
            empty = QListWidgetItem("暂无搜索记录")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            target.addItem(empty)
            return
        for history in self.search_history:
            filters: list[str] = []
            if history.get("subjects"):
                filters.append("科目 " + "、".join(history["subjects"]))
            if history.get("note_type") == "exam":
                filters.append("期末")
            elif history.get("note_type") == "postgraduate":
                filters.append("考研")
            if history.get("exclude_tags"):
                filters.append(f"排除 {'、'.join(history['exclude_tags'])}")
            filter_text = " · ".join(filters) if filters else "全部笔记"
            item = QListWidgetItem(f"{history['query']}\n{filter_text}")
            item.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            item.setData(
                Qt.ItemDataRole.UserRole,
                {"kind": "history", **history},
            )
            target.addItem(item)

    def clear_search_history(self) -> None:
        try:
            clear_persisted_search_history(self.database_path)
            self.search_history = []
        except (OSError, sqlite3.Error) as exc:
            self.statusBar().showMessage(f"搜索历史清理失败: {exc}", 5000)
            return
        if not self.current_query:
            self._show_search_history(self.search_results)

    def _apply_appearance_settings(self, refresh_content: bool = True) -> None:
        self.theme = resolved_theme(
            str(self.settings["theme"]), QApplication.instance()
        )
        scale = int(self.settings["ui_scale"])
        app = QApplication.instance()
        if app is not None:
            apply_application_palette(app, self.theme)
            font = QFont(app.font())
            font.setPointSizeF(max(8.0, 9.0 * scale / 100))
            app.setFont(font)
        self.setStyleSheet(build_app_style(self.theme, scale))
        set_windows_title_bar_theme(self, self.theme)
        if not refresh_content or not hasattr(self, "workspace"):
            return

        icon_size = QSize(round(17 * scale / 100), round(17 * scale / 100))
        self.sidebar.setFixedWidth(round(238 * scale / 100))
        for button, icon in self.nav_buttons.values():
            button.setIcon(self._standard_icon(icon))
            button.setIconSize(icon_size)
        self.rebuild_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.rebuild_button.setIconSize(icon_size)
        self.settings_button.setIcon(_painted_icon("gear", self.theme))
        self.settings_button.setIconSize(icon_size)
        self.search_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.clear_history_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        for preview, (_title, _meta, open_button) in self._preview_parts.items():
            open_button.setIcon(
                self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton)
            )
            preview.set_render_settings(
                theme=self.theme,
                body_size=str(self.settings["note_font_size"]),
                code_size=str(self.settings["code_font_size"]),
                body_font=str(self.settings["body_font"]),
                code_font=str(self.settings["code_font"]),
            )
        self._highlight_query(self.search_preview, self.current_query)
        self.teaching_page.refresh_settings()
        for line_edit in self.findChildren(ClearableLineEdit):
            line_edit.set_icon_theme(self.theme)
        self._populate_subject_tree()
        if not self.current_query:
            self._show_search_history(self.search_results)

    def _on_system_color_scheme_changed(self, _scheme: Any) -> None:
        if self.settings.get("theme") == "system":
            self._apply_appearance_settings()

    def _on_setting_changed(self, key: str, value: Any) -> None:
        candidate = dict(self.settings)
        candidate[key] = value
        normalized = normalized_settings(candidate, self.default_notes_root)
        new_value = normalized[key]
        try:
            save_app_setting(self.database_path, key, new_value)
        except (OSError, sqlite3.Error) as exc:
            self.settings_page.set_setting_value(key, self.settings[key])
            QMessageBox.warning(self, "设置保存失败", str(exc))
            return
        self.settings[key] = new_value
        self.settings_page.set_setting_value(key, new_value)
        if key.startswith("teach_"):
            self.teaching_page.refresh_settings()

        if key in {
            "theme",
            "ui_scale",
            "note_font_size",
            "code_font_size",
            "body_font",
            "code_font",
        }:
            self._apply_appearance_settings()
        elif key == "show_sample_notes":
            self._refresh_from_index()
        elif key in {"history_enabled", "history_limit"}:
            if key == "history_limit":
                try:
                    trim_search_history(self.database_path, int(new_value))
                except (OSError, sqlite3.Error):
                    pass
            self.search_history = self._load_history()
            if not self.current_query:
                self._show_search_history(self.search_results)

    def _on_settings_action(self, action: str) -> None:
        if action == "save_api_key":
            self._save_api_key()
        elif action == "clear_api_key":
            self._clear_api_key()
        elif action == "test_teaching_connection":
            self._switch_page(2)
            self.teaching_page.check_connection()
        elif action.startswith("reset_category:"):
            self._reset_settings_category(action.split(":", 1)[1])
        elif action == "choose_notes_root":
            self._choose_notes_root()
        elif action == "choose_external_editor":
            self._choose_external_editor()
        elif action == "refresh_storage_status":
            self._refresh_storage_status()
        elif action == "rebuild_index":
            answer = QMessageBox.question(
                self,
                "重建索引",
                "将重新扫描当前笔记目录并覆盖可重建的索引和 SQLite 笔记目录。继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.rebuild_index()
        elif action == "clear_external_cache":
            self._confirm_clear_external_cache()
        elif action == "reset_all_settings":
            self._reset_all_settings()
        elif action == "export_local_data":
            self._export_local_data()

    def _save_api_key(self) -> None:
        key = self.settings_page.api_key_text()
        if not key:
            QMessageBox.warning(self, "API Key 未填写", "请输入 API Key 后再保存。")
            return
        try:
            save_api_key(key)
        except (ValueError, CredentialStorageError) as exc:
            QMessageBox.warning(self, "API Key 保存失败", str(exc))
            return
        self.settings_page.clear_api_key_input()
        self.settings_page.refresh_api_key_status()
        self.teaching_page.refresh_settings()
        self.statusBar().showMessage("API Key 已安全保存到 Windows 凭据管理器", 5000)

    def _clear_api_key(self) -> None:
        answer = QMessageBox.question(
            self,
            "清除 API Key",
            "将删除 NoteManager 保存在 Windows 凭据管理器中的 API Key。"
            "系统环境变量 OPENAI_API_KEY 不受影响。继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_saved_api_key()
        except CredentialStorageError as exc:
            QMessageBox.warning(self, "API Key 清除失败", str(exc))
            return
        self.settings_page.clear_api_key_input()
        self.settings_page.refresh_api_key_status()
        self.teaching_page.refresh_settings()
        self.statusBar().showMessage("已清除 NoteManager 保存的 API Key", 5000)

    def _default_value(self, key: str) -> Any:
        if key == "notes_root":
            return str(self.default_notes_root)
        return DEFAULT_APP_SETTINGS[key]

    def _reset_settings_category(self, category_id: str) -> None:
        keys = self.settings_page.category_keys(category_id)
        if not keys:
            return
        previous_settings = dict(self.settings)
        previous_notes_root = self.notes_root
        for key in keys:
            self.settings[key] = self._default_value(key)
        try:
            save_app_settings(
                self.database_path, {key: self.settings[key] for key in keys}
            )
        except (OSError, sqlite3.Error) as exc:
            self.settings = previous_settings
            self.settings_page.set_values(previous_settings)
            QMessageBox.warning(self, "设置保存失败", str(exc))
            return
        self.settings = normalized_settings(self.settings, self.default_notes_root)
        self.notes_root = Path(self.settings["notes_root"]).resolve()
        self.settings_page.set_values(self.settings)
        self._apply_appearance_settings()
        self.search_history = self._load_history()
        if category_id == "search":
            self._refresh_from_index()
        elif category_id == "privacy":
            self.search_history = self._load_history()
            if not self.current_query:
                self._show_search_history(self.search_results)
        if category_id == "files" and self.notes_root != previous_notes_root:
            self.rebuild_index()

    def _reset_all_settings(self) -> None:
        answer = QMessageBox.warning(
            self,
            "重置全部设置",
            "将恢复所有应用设置的默认值，但不会删除 Markdown 笔记或搜索历史。继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous_notes_root = self.notes_root
        try:
            reset_app_settings(self.database_path)
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "设置重置失败", str(exc))
            return
        self.settings = normalized_settings({}, self.default_notes_root)
        self.notes_root = Path(self.settings["notes_root"]).resolve()
        self.settings_page.set_values(self.settings)
        self.search_history = self._load_history()
        self._apply_appearance_settings()
        self._refresh_from_index()
        if self.notes_root != previous_notes_root:
            self.rebuild_index()
        self.statusBar().showMessage("全部应用设置已恢复默认", 4000)

    def _choose_notes_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择 Markdown 笔记目录",
            str(self.notes_root),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
        )
        if not selected:
            return
        new_root = Path(selected).resolve()
        if new_root == self.notes_root:
            return
        answer = QMessageBox.question(
            self,
            "切换笔记目录",
            f"将索引来源切换为：\n{new_root}\n\n原目录中的文件不会移动或修改。现在切换并重建索引吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            save_app_setting(self.database_path, "notes_root", str(new_root))
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "设置保存失败", str(exc))
            return
        self.notes_root = new_root
        self.settings["notes_root"] = str(new_root)
        self.settings_page.set_setting_value("notes_root", str(new_root))
        self.catalog_documents = None
        self.rebuild_index()

    def _choose_external_editor(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 Markdown 编辑器",
            str(Path(self.settings["external_editor_path"]).parent)
            if self.settings["external_editor_path"]
            else str(self.base_dir),
            "可执行程序 (*.exe);;所有文件 (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not selected:
            return
        editor_path = str(Path(selected).resolve())
        self.settings["external_editor_mode"] = "custom"
        self.settings["external_editor_path"] = editor_path
        try:
            save_app_settings(
                self.database_path,
                {
                    "external_editor_mode": "custom",
                    "external_editor_path": editor_path,
                },
            )
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "设置保存失败", str(exc))
            return
        self.settings_page.set_values(self.settings)

    def _external_cache_paths(self) -> tuple[Path, Path]:
        return (
            (self.base_dir / "data" / "external").resolve(),
            (self.base_dir / "data" / "index" / "external_manifest.json").resolve(),
        )

    def _clear_external_cache(self) -> int:
        external_dir, manifest_path = self._external_cache_paths()
        external_dir.relative_to(self.base_dir)
        manifest_path.relative_to(self.base_dir)
        removed = 0
        if external_dir.exists():
            for entry in external_dir.iterdir():
                if entry.name == ".gitkeep":
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                removed += 1
        if manifest_path.exists():
            manifest_path.unlink()
            removed += 1
        return removed

    def _confirm_clear_external_cache(self) -> None:
        answer = QMessageBox.warning(
            self,
            "清理外部资料缓存",
            "将永久删除 data/external 中的临时资料和缓存清单，不影响 Markdown 笔记。继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = self._clear_external_cache()
        except OSError as exc:
            QMessageBox.warning(self, "缓存清理失败", str(exc))
            return
        self._refresh_storage_status()
        self.statusBar().showMessage(f"已清理 {removed} 个缓存项", 4000)

    def _cache_summary(self) -> tuple[int, int]:
        external_dir, manifest_path = self._external_cache_paths()
        files: list[Path] = []
        if external_dir.exists():
            files.extend(
                path
                for path in external_dir.rglob("*")
                if path.is_file() and path.name != ".gitkeep"
            )
        if manifest_path.is_file():
            files.append(manifest_path)
        return len(files), sum(path.stat().st_size for path in files)

    def _refresh_storage_status(self) -> None:
        if not hasattr(self, "settings_page"):
            return
        try:
            summary = storage_summary(self.database_path)
            summary["cache_count"], summary["cache_size"] = self._cache_summary()
        except (OSError, sqlite3.Error) as exc:
            self.settings_page.storage_status.setText(f"本地数据状态读取失败：{exc}")
            return
        self.settings_page.update_storage_status(summary)

    def _export_local_data(self) -> None:
        suggested = self.base_dir / "NoteManager-local-data.json"
        output, _filter = QFileDialog.getSaveFileName(
            self,
            "导出设置与搜索历史",
            str(suggested),
            "JSON 文件 (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not output:
            return
        output_path = Path(output)
        if output_path.suffix.lower() != ".json":
            output_path = output_path.with_suffix(".json")
        try:
            export_local_data(self.database_path, output_path)
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self.statusBar().showMessage(f"本地数据已导出到 {output_path}", 5000)

    def _restore_reading_state(self) -> None:
        if self._reading_state_restored or not self.settings["restore_reading_state"]:
            return
        relative_path = str(self.settings["last_note_path"])
        if not relative_path:
            self._reading_state_restored = True
            return
        visible_paths = {path for path, _document in self._documents()}
        if relative_path not in visible_paths:
            self._reading_state_restored = True
            return
        self._reading_state_restored = True
        self._switch_page(0)
        self._select_library_path(relative_path)
        scroll = int(self.settings["last_note_scroll"])
        QTimer.singleShot(
            0,
            lambda: self.library_preview.verticalScrollBar().setValue(scroll),
        )

    def _save_reading_state(self) -> None:
        if not self.settings["restore_reading_state"]:
            return
        scroll = (
            self._last_preview.verticalScrollBar().value()
            if self._last_preview is not None
            else 0
        )
        values = {
            "last_note_path": self._last_note_path,
            "last_note_scroll": scroll,
        }
        self.settings.update(values)
        try:
            save_app_settings(self.database_path, values)
        except (OSError, sqlite3.Error):
            pass

    def closeEvent(self, event) -> None:
        """Wait for an active index worker before closing the window."""
        if self.teaching_page.is_busy():
            self.teaching_page.cancel()
            self.statusBar().showMessage("正在取消教学请求并清理临时索引，请稍候再关闭")
            event.ignore()
            return
        if self._index_thread is not None and self._index_thread.isRunning():
            self._index_thread.quit()
            if not self._index_thread.wait(3000):
                self.statusBar().showMessage("索引仍在写入，请稍候再关闭")
                event.ignore()
                return
        self._save_reading_state()
        if self.settings["external_cache_policy"] == "discard":
            try:
                self._clear_external_cache()
            except OSError:
                pass
        super().closeEvent(event)
