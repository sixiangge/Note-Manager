"""GUI application entry point."""

import sys
from pathlib import Path


def run_gui(base_dir: Path, notes_root: Path, index_path: Path) -> int:
    """Start the NJUCSKeeper PyQt6 desktop application.

    Args:
        base_dir: Project root used to resolve paths stored in the index.
        notes_root: Root directory containing Markdown notes.
        index_path: Persistent inverted-index file.

    Returns:
        Qt application exit code.
    """
    try:
        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "GUI 依赖尚未安装，请先运行: pip install -r requirements.txt"
        ) from exc

    from src.gui.main_window import MainWindow

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    QCoreApplication.setOrganizationName("NJUCSKeeper")
    QCoreApplication.setApplicationName("NJUCSKeeper")
    app.setStyle("Fusion")

    window = MainWindow(
        base_dir=Path(base_dir),
        notes_root=Path(notes_root),
        index_path=Path(index_path),
    )
    window.show()

    if owns_app:
        return app.exec()
    return 0
