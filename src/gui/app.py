"""GUI application entry point."""

import sys
import sqlite3
import tempfile
from pathlib import Path


_qt_message_handler = None


def _set_windows_app_id() -> None:
    """Give Windows a stable taskbar identity instead of using python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NoteManager.Desktop"
        )
    except (AttributeError, OSError):
        pass


def _install_qt_message_filter() -> None:
    """Ignore one harmless libpng profile warning while preserving all others."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    global _qt_message_handler
    previous_handler = None

    def handle_message(message_type, context, message) -> None:
        if (
            message_type == QtMsgType.QtWarningMsg
            and message == "libpng warning: iCCP: known incorrect sRGB profile"
        ):
            return
        if previous_handler is not None:
            previous_handler(message_type, context, message)
        else:
            sys.stderr.write(f"{message}\n")
            sys.stderr.flush()

    previous_handler = qInstallMessageHandler(handle_message)
    _qt_message_handler = handle_message


def _create_app_icon():
    """Draw the application icon in memory without decoding image files."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 64.0, size / 64.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#176b5b"))
        painter.drawRoundedRect(QRectF(2, 2, 60, 60), 12, 12)

        left_page = QPainterPath(QPointF(11, 22))
        left_page.cubicTo(18, 21, 25, 22, 32, 28)
        left_page.lineTo(32, 53)
        left_page.cubicTo(26, 48, 19, 46, 11, 47)
        left_page.closeSubpath()
        right_page = QPainterPath(QPointF(53, 22))
        right_page.cubicTo(46, 21, 39, 22, 32, 28)
        right_page.lineTo(32, 53)
        right_page.cubicTo(38, 48, 45, 46, 53, 47)
        right_page.closeSubpath()
        painter.setBrush(QColor("#ffffff"))
        painter.drawPath(left_page)
        painter.drawPath(right_page)

        pen = QPen(QColor("#b8ddd5"), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(22, 21), QPointF(22, 17))
        painter.drawLine(QPointF(22, 17), QPointF(42, 17))
        painter.drawLine(QPointF(42, 17), QPointF(42, 21))
        painter.drawLine(QPointF(32, 17), QPointF(32, 11))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPointF(22, 14), 3, 3)
        painter.drawEllipse(QPointF(32, 9), 3, 3)
        painter.drawEllipse(QPointF(42, 14), 3, 3)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _set_window_icon(window, icon) -> None:
    """Set both Qt and native Windows icons used by the taskbar."""
    window.setWindowIcon(icon)
    if sys.platform != "win32":
        return
    try:
        import ctypes

        icon_dir = Path(tempfile.gettempdir()) / "NoteManager"
        icon_dir.mkdir(parents=True, exist_ok=True)
        icon_path = icon_dir / "notemanager.ico"
        if not icon.pixmap(256, 256).save(str(icon_path), "ICO"):
            return

        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        )
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        user32.SendMessageW.restype = ctypes.c_ssize_t

        image_icon = 1
        load_from_file = 0x0010
        wm_set_icon = 0x0080
        icon_small = 0
        icon_big = 1
        big_handle = user32.LoadImageW(
            None, str(icon_path), image_icon, 32, 32, load_from_file
        )
        small_handle = user32.LoadImageW(
            None, str(icon_path), image_icon, 16, 16, load_from_file
        )
        if big_handle:
            user32.SendMessageW(
                int(window.winId()), wm_set_icon, icon_big, big_handle
            )
        if small_handle:
            user32.SendMessageW(
                int(window.winId()), wm_set_icon, icon_small, small_handle
            )
        window._notemanager_native_icon_handles = (big_handle, small_handle)
    except (AttributeError, OSError, TypeError, ValueError):
        pass


def run_gui(base_dir: Path, notes_root: Path, index_path: Path) -> int:
    """Start the NoteManager PyQt6 desktop application.

    Args:
        base_dir: Project root used to resolve paths stored in the index.
        notes_root: Root directory containing Markdown notes.
        index_path: Persistent inverted-index file.

    Returns:
        Qt application exit code.
    """
    _set_windows_app_id()

    try:
        from PyQt6.QtCore import QCoreApplication, QObject, QThread, pyqtSlot
        from PyQt6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        raise RuntimeError(
            "GUI 依赖尚未安装，请先运行: pip install -r requirements.txt"
        ) from exc

    from src.app_settings import normalized_settings
    from src.gui.startup import StartupLoader, StartupScreen
    from src.gui.theme import (
        apply_application_palette,
        resolved_theme,
        set_windows_title_bar_theme,
    )
    from src.storage import load_app_settings

    _install_qt_message_filter()
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    QCoreApplication.setOrganizationName("NoteManager")
    QCoreApplication.setApplicationName("NoteManager")
    app.setStyle("Fusion")
    database_path = Path(index_path).with_name("notemanager.db")
    try:
        stored_settings = load_app_settings(database_path)
    except (OSError, sqlite3.Error):
        stored_settings = {}
    initial_settings = normalized_settings(stored_settings, Path(notes_root))
    initial_theme = resolved_theme(str(initial_settings["theme"]), app)
    apply_application_palette(app, initial_theme)

    app_icon = _create_app_icon()
    app.setWindowIcon(app_icon)

    splash = StartupScreen(initial_theme, app_icon)
    splash.show_centered()
    splash.update_progress(8, "正在读取启动设置")
    app.processEvents()

    splash.update_progress(14, "正在加载界面组件")
    app.processEvents()
    from src.gui.main_window import MainWindow

    effective_notes_root = Path(str(initial_settings["notes_root"]))
    thread = QThread(app)
    worker = StartupLoader(
        base_dir=Path(base_dir),
        notes_root=effective_notes_root,
        index_path=Path(index_path),
        database_path=database_path,
        history_enabled=bool(initial_settings["history_enabled"]),
        history_limit=int(initial_settings["history_limit"]),
        check_for_changes=initial_settings["index_strategy"] == "prompt",
    )
    worker.moveToThread(thread)

    state: dict[str, object] = {
        "splash": splash,
        "thread": thread,
        "worker": worker,
    }

    class StartupCoordinator(QObject):
        @pyqtSlot(object)
        def finish(self, result) -> None:
            try:
                splash.update_progress(84, "正在构建正式页面")
                app.processEvents()
                window = MainWindow(
                    base_dir=Path(base_dir),
                    notes_root=Path(notes_root),
                    index_path=Path(index_path),
                    preloaded_settings=initial_settings,
                    preloaded_index=result.index,
                    preloaded_history=result.search_history,
                )
                state["window"] = window
                _set_window_icon(window, app_icon)
                splash.update_progress(96, "正在恢复界面状态")
                window.show()
                set_windows_title_bar_theme(window, window.theme)
                splash.update_progress(100, "加载完成")
                app.processEvents()
                splash.close()
                window.complete_startup(
                    index_missing=result.index_missing,
                    index_stale=result.index_stale,
                    index_error=result.index_error,
                )
            except Exception as exc:
                splash.update_progress(100, "启动失败")
                QMessageBox.critical(splash, "NoteManager 启动失败", str(exc))
                splash.close()

    coordinator = StartupCoordinator(app)
    state["coordinator"] = coordinator
    app._notemanager_startup_state = state

    thread.started.connect(worker.run)
    worker.progress.connect(splash.update_progress)
    worker.finished.connect(coordinator.finish)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()

    if owns_app:
        return app.exec()
    return 0
