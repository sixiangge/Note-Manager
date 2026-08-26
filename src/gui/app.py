"""GUI application entry point."""

import sys
import sqlite3
from pathlib import Path


_qt_message_handler = None
_WINDOWS_APP_ID = "NoteManager.Desktop.2026"


def _set_windows_app_id() -> None:
    """Give Windows a stable taskbar identity instead of using python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            _WINDOWS_APP_ID
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
    """Load the packaged application icon, with an in-memory fallback."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

    icon_path = Path(__file__).resolve().parent / "assets" / "notemanager.ico"
    packaged_icon = QIcon(str(icon_path))
    if not packaged_icon.isNull():
        return packaged_icon

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
    """Set the Qt window icon."""
    window.setWindowIcon(icon)


def _set_windows_taskbar_properties(window, base_dir: Path) -> None:
    """Associate the native window with NoteManager's taskbar icon."""
    if sys.platform != "win32":
        return
    try:
        from win32com.propsys import propsys, pscon

        icon_path = (
            Path(base_dir) / "src" / "gui" / "assets" / "notemanager.ico"
        ).resolve()
        if not icon_path.is_file():
            return
        store = propsys.SHGetPropertyStoreForWindow(
            int(window.winId()), propsys.IID_IPropertyStore
        )
        store.SetValue(
            pscon.PKEY_AppUserModel_ID,
            propsys.PROPVARIANTType(_WINDOWS_APP_ID),
        )
        store.SetValue(
            pscon.PKEY_AppUserModel_RelaunchIconResource,
            propsys.PROPVARIANTType(f"{icon_path},0"),
        )
        store.Commit()
    except (ImportError, OSError, TypeError):
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
                _set_windows_taskbar_properties(window, Path(base_dir))
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
