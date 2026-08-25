"""Fast startup screen and background data loader."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class StartupLoadResult:
    """Data prepared before constructing the main window."""

    index: dict[str, Any]
    search_history: list[dict[str, Any]]
    index_missing: bool = False
    index_stale: bool = False
    index_error: str = ""


class StartupScreen(QWidget):
    """Small frameless startup page shown before heavy GUI construction."""

    def __init__(self, theme: str, app_icon: QIcon) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("startupScreen")
        self.setWindowTitle("NoteManager")
        self.setWindowIcon(app_icon)
        self.setFixedSize(560, 300)

        dark = theme == "dark"
        background = "#080807" if dark else "#f7f7f8"
        text = "#ffffff" if dark else "#17181a"
        muted = "#8d8982" if dark else "#72767d"
        track = "#282622" if dark else "#dfe3e2"
        self.setStyleSheet(
            f"""
            QWidget#startupScreen {{ background: {background}; }}
            QLabel#startupName {{
                color: {text};
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 27px;
                font-weight: 700;
            }}
            QLabel#startupStatus {{
                color: {muted};
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 12px;
            }}
            QProgressBar {{
                min-height: 7px;
                max-height: 7px;
                border: 0;
                border-radius: 3px;
                background: {track};
                text-align: center;
            }}
            QProgressBar::chunk {{
                border-radius: 3px;
                background: #176b5b;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 44, 52, 32)
        layout.setSpacing(0)
        layout.addStretch(1)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addStretch(1)
        icon = QLabel()
        icon.setFixedSize(44, 44)
        icon.setPixmap(app_icon.pixmap(QSize(44, 44)))
        brand.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        name = QLabel("NoteManager")
        name.setObjectName("startupName")
        brand.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(28)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(3)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        layout.addSpacing(9)

        status_row = QHBoxLayout()
        status_row.addStretch(1)
        self.status = QLabel("准备加载")
        self.status.setObjectName("startupStatus")
        self.status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        status_row.addWidget(self.status)
        layout.addLayout(status_row)
        layout.addStretch(1)

    def show_centered(self) -> None:
        """Show at the center of the screen containing the cursor."""
        screen = (
            QApplication.screenAt(self.cursor().pos())
            or QApplication.primaryScreen()
        )
        if screen is not None:
            frame = self.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.move(frame.topLeft())
        self.show()
        self.raise_()
        self.activateWindow()

    def update_progress(self, value: int, item: str) -> None:
        self.progress.setValue(max(0, min(value, 100)))
        self.status.setText(item)


class StartupLoader(QObject):
    """Load index/history and check freshness without blocking the GUI thread."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)

    def __init__(
        self,
        *,
        base_dir: Path,
        notes_root: Path,
        index_path: Path,
        database_path: Path,
        history_enabled: bool,
        history_limit: int,
        check_for_changes: bool,
    ) -> None:
        super().__init__()
        self.base_dir = Path(base_dir).resolve()
        self.notes_root = Path(notes_root).resolve()
        self.index_path = Path(index_path).resolve()
        self.database_path = Path(database_path).resolve()
        self.history_enabled = history_enabled
        self.history_limit = history_limit
        self.check_for_changes = check_for_changes

    def run(self) -> None:
        """Perform startup I/O. This method runs in a worker thread."""
        from src.indexer import load_index
        from src.storage import load_search_history

        index: dict[str, Any] = {"documents": {}, "inverted_index": {}}
        index_missing = not self.index_path.is_file()
        index_error = ""

        self.progress.emit(24, "正在读取全文索引")
        if not index_missing:
            try:
                loaded_index = load_index(self.index_path)
                if not isinstance(loaded_index, dict) or not isinstance(
                    loaded_index.get("documents"), dict
                ):
                    raise ValueError("索引格式无效，请重新构建索引")
                index = loaded_index
            except (OSError, ValueError) as exc:
                index_error = str(exc)

        self.progress.emit(48, "正在读取搜索历史")
        history: list[dict[str, Any]] = []
        if self.history_enabled:
            try:
                history = load_search_history(self.database_path, self.history_limit)
            except (OSError, ValueError, sqlite3.Error):
                history = []

        index_stale = False
        if self.check_for_changes and not index_missing and not index_error:
            self.progress.emit(68, "正在检查笔记变更")
            index_stale = self._index_is_stale(index)
        else:
            self.progress.emit(68, "正在准备笔记目录")

        self.progress.emit(80, "正在准备主界面")
        self.finished.emit(
            StartupLoadResult(
                index=index,
                search_history=history,
                index_missing=index_missing,
                index_stale=index_stale,
                index_error=index_error,
            )
        )

    def _index_base_dir(self) -> Path:
        try:
            self.notes_root.relative_to(self.base_dir)
        except ValueError:
            return self.notes_root
        return self.base_dir

    def _index_is_stale(self, index: dict[str, Any]) -> bool:
        """Compare paths and mtimes only; never read note content or hash files."""
        indexed_paths = {
            str(path).replace("\\", "/")
            for path in index.get("documents", {})
        }
        if not self.notes_root.is_dir():
            return bool(indexed_paths)

        index_base = self._index_base_dir()
        current_paths: set[str] = set()
        newest_note_mtime = 0
        try:
            for file_path in self.notes_root.rglob("*.md"):
                relative_path = str(file_path.relative_to(index_base)).replace(
                    "\\", "/"
                )
                current_paths.add(relative_path)
                newest_note_mtime = max(
                    newest_note_mtime, file_path.stat().st_mtime_ns
                )
            index_mtime = self.index_path.stat().st_mtime_ns
        except (OSError, ValueError):
            return True
        return current_paths != indexed_paths or newest_note_mtime > index_mtime


__all__ = ["StartupLoadResult", "StartupLoader", "StartupScreen"]
