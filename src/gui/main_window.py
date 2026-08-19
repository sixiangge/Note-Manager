"""Main PyQt6 window for browsing and searching course notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSettings, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.indexer import build_index, generate_sample_notes, load_index, save_index
from src.parsers.markdown_parser import Note, parse_markdown
from src.searcher import search


APP_STYLE = """
QMainWindow, QWidget#root {
    background: #f7f7f8;
    color: #202123;
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
QLineEdit, QComboBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #d7d9dd;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #b8ddd5;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #4d8f82; }
QComboBox { padding-right: 24px; }
QTreeWidget, QListWidget, QTextBrowser {
    background: transparent;
    border: 0;
    outline: 0;
}
QTreeWidget::item {
    min-height: 29px;
    border-radius: 4px;
    padding: 2px 4px;
}
QTreeWidget::item:hover, QListWidget::item:hover { background: #eceeef; }
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #dde9e6;
    color: #153f37;
}
QListWidget::item {
    border-bottom: 1px solid #ececef;
    padding: 11px 10px;
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
"""


class IndexWorker(QObject):
    """Build the inverted index without blocking the GUI thread."""

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, notes_root: Path, base_dir: Path, index_path: Path) -> None:
        super().__init__()
        self.notes_root = notes_root
        self.base_dir = base_dir
        self.index_path = index_path

    def run(self) -> None:
        """Generate samples when needed, then rebuild and save the index."""
        try:
            if not self.notes_root.exists() or not any(self.notes_root.rglob("*.md")):
                generate_sample_notes(self.notes_root)
            index = build_index(self.notes_root, base_dir=self.base_dir)
            save_index(index, self.index_path)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(index)


class MainWindow(QMainWindow):
    """Desktop workspace for note browsing, search, and read-only preview."""

    HISTORY_LIMIT = 20

    def __init__(self, base_dir: Path, notes_root: Path, index_path: Path) -> None:
        super().__init__()
        self.base_dir = base_dir.resolve()
        self.notes_root = notes_root.resolve()
        self.index_path = index_path.resolve()
        self.index: dict[str, Any] = {"documents": {}, "inverted_index": {}}
        self.current_query = ""
        self.settings = QSettings()
        self.search_history = self._load_history()
        self._preview_parts: dict[
            QTextBrowser, tuple[QLabel, QLabel, QPushButton]
        ] = {}
        self._preview_notes: dict[QTextBrowser, Note] = {}
        self._index_thread: QThread | None = None
        self._index_worker: IndexWorker | None = None

        self.setWindowTitle("NJUCSKeeper")
        self.resize(1380, 860)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()
        self._load_initial_index()

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
        self.workspace.addWidget(self.library_page)
        self.workspace.addWidget(self.search_page)
        self.workspace.addWidget(self.teaching_page)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.workspace, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("正在载入笔记...")

    def _standard_icon(self, pixmap: QStyle.StandardPixmap):
        return QApplication.style().standardIcon(pixmap)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(238)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(8)

        brand = QLabel("NJUCSKeeper")
        brand.setObjectName("brand")
        brand.setContentsMargins(8, 2, 0, 13)
        layout.addWidget(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_specs = [
            ("笔记库", QStyle.StandardPixmap.SP_DirOpenIcon, 0),
            ("全文搜索", QStyle.StandardPixmap.SP_FileDialogContentsView, 1),
            ("教学对话", QStyle.StandardPixmap.SP_MessageBoxInformation, 2),
        ]
        for label, icon, page_index in nav_specs:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setIcon(self._standard_icon(icon))
            button.setIconSize(QSize(17, 17))
            button.clicked.connect(lambda checked, i=page_index: self._switch_page(i))
            self.nav_group.addButton(button, page_index)
            layout.addWidget(button)
        self.nav_group.button(0).setChecked(True)

        section = QLabel("科目")
        section.setObjectName("sectionLabel")
        section.setContentsMargins(8, 15, 0, 2)
        layout.addWidget(section)

        self.subject_tree = QTreeWidget()
        self.subject_tree.setHeaderHidden(True)
        self.subject_tree.setIndentation(16)
        self.subject_tree.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self.subject_tree, 1)

        self.rebuild_button = QPushButton("重建索引")
        self.rebuild_button.setIcon(
            self._standard_icon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.rebuild_button.setToolTip("重新扫描全部 Markdown 笔记")
        self.rebuild_button.clicked.connect(self.rebuild_index)
        layout.addWidget(self.rebuild_button)
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
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("搜索标题、章节、标签和正文")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self.perform_search)
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
        self.subject_filter = QComboBox()
        self.subject_filter.addItem("全部科目", None)
        self.subject_filter.currentIndexChanged.connect(self._rerun_active_search)
        filter_row.addWidget(self.subject_filter, 1)
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部类型", None)
        self.type_filter.addItem("期末", "exam")
        self.type_filter.addItem("考研", "postgraduate")
        self.type_filter.currentIndexChanged.connect(self._rerun_active_search)
        filter_row.addWidget(self.type_filter, 1)
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

        browser = QTextBrowser()
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
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("教学对话")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        badge = QLabel("Phase 3")
        badge.setObjectName("badge")
        header.addWidget(badge)
        header.addStretch(1)
        layout.addLayout(header)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch(1)
        empty_title = QLabel("课程助教尚未接入")
        empty_title.setObjectName("noteTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_hint = QLabel("教学对话与资料校验将在 Phase 3 启用")
        empty_hint.setObjectName("muted")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_hint)
        empty_layout.addStretch(1)
        layout.addWidget(empty, 1)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(12, 10, 12, 10)
        question = QPlainTextEdit()
        question.setPlaceholderText("向课程助教提问...")
        question.setMaximumHeight(80)
        question.setEnabled(False)
        composer_layout.addWidget(question)
        actions = QHBoxLayout()
        attach = QPushButton("上传附件")
        attach.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        attach.setEnabled(False)
        attach.setToolTip("Phase 3 启用")
        actions.addWidget(attach)
        actions.addStretch(1)
        send = QPushButton("发送")
        send.setObjectName("primaryButton")
        send.setEnabled(False)
        actions.addWidget(send)
        composer_layout.addLayout(actions)
        layout.addWidget(composer)
        return page

    def _switch_page(self, page_index: int) -> None:
        self.workspace.setCurrentIndex(page_index)
        button = self.nav_group.button(page_index)
        if button is not None:
            button.setChecked(True)
        if page_index == 1:
            self.query_input.setFocus()

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

    def rebuild_index(self) -> None:
        """Rebuild the note index in a worker thread."""
        if self._index_thread is not None and self._index_thread.isRunning():
            return
        self.rebuild_button.setEnabled(False)
        self.rebuild_button.setText("正在重建...")
        self.statusBar().showMessage("正在扫描 Markdown 笔记并重建索引...")

        thread = QThread(self)
        worker = IndexWorker(self.notes_root, self.base_dir, self.index_path)
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
        self._populate_library()
        if self.current_query:
            self.perform_search(record_history=False)
        count = len(self.index.get("documents", {}))
        self.statusBar().showMessage(f"已载入 {count} 篇笔记", 4000)

    def _documents(self) -> list[tuple[str, dict[str, Any]]]:
        documents = self.index.get("documents", {})
        return sorted(
            documents.items(),
            key=lambda pair: (
                str(pair[1].get("subject", "")),
                str(pair[1].get("chapter", "")),
                str(pair[1].get("title", "")),
            ),
        )

    def _subjects(self) -> list[str]:
        return sorted({doc.get("subject", "") for _, doc in self._documents() if doc.get("subject")})

    def _populate_subject_tree(self) -> None:
        self.subject_tree.clear()
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for path, doc in self._documents():
            grouped.setdefault(str(doc.get("subject", "未分类")), []).append((path, doc))
        for subject, notes in grouped.items():
            parent = QTreeWidgetItem([subject])
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

    def _populate_subject_filter(self) -> None:
        selected = self.subject_filter.currentData()
        self.subject_filter.blockSignals(True)
        self.subject_filter.clear()
        self.subject_filter.addItem("全部科目", None)
        for subject in self._subjects():
            self.subject_filter.addItem(subject, subject)
        selected_index = self.subject_filter.findData(selected)
        self.subject_filter.setCurrentIndex(max(selected_index, 0))
        self.subject_filter.blockSignals(False)

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
        results = search(
            query,
            self.index,
            note_type=self.type_filter.currentData(),
            subject=self.subject_filter.currentData(),
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
        preview.setMarkdown(note.body)
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

    @staticmethod
    def _highlight_query(preview: QTextBrowser, query: str) -> None:
        preview.setExtraSelections([])
        if not query:
            return
        selections: list[QTextEdit.ExtraSelection] = []
        cursor = QTextCursor(preview.document())
        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#fff0a8"))
        highlight.setForeground(QColor("#202123"))
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
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(note.file_path)))
        if not opened:
            QMessageBox.warning(self, "无法打开笔记", "系统未找到可用的 Markdown 编辑器。")

    def _load_history(self) -> list[str]:
        value = self.settings.value("search/history", [])
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    def _record_history(self, query: str) -> None:
        self.search_history = [item for item in self.search_history if item != query]
        self.search_history.insert(0, query)
        self.search_history = self.search_history[: self.HISTORY_LIMIT]
        self.settings.setValue("search/history", self.search_history)

    def _show_search_history(self, target: QListWidget) -> None:
        target.clear()
        self.search_section_title.setText("最近搜索")
        self.clear_history_button.setVisible(True)
        if not self.search_history:
            empty = QListWidgetItem("暂无搜索记录")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            target.addItem(empty)
            return
        for query in self.search_history:
            item = QListWidgetItem(query)
            item.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "history", "query": query})
            target.addItem(item)

    def clear_search_history(self) -> None:
        self.search_history = []
        self.settings.remove("search/history")
        if not self.current_query:
            self._show_search_history(self.search_results)

    def closeEvent(self, event) -> None:
        """Wait for an active index worker before closing the window."""
        if self._index_thread is not None and self._index_thread.isRunning():
            self._index_thread.quit()
            if not self._index_thread.wait(3000):
                self.statusBar().showMessage("索引仍在写入，请稍候再关闭")
                event.ignore()
                return
        super().closeEvent(event)
