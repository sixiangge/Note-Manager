"""Optional, read-only teaching workspace with cancellable background work."""

from collections.abc import Callable
from html import escape
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import urlsplit

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QTextDocument, QTextCursor, QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from src.llm import test_connection
from src.models import TeachSession
from src.oracle import TeachingCancelled, teach_session
from src.teaching_config import TeachingConfig
from src.gui.theme import resolved_theme, theme_colors


class _ChatBrowser(QTextBrowser):
    def loadResource(self, resource_type: int, name: QUrl) -> object:
        # Generated answers cannot load local files or tracking images.
        return None


class _TeachingWorker(QThread):
    progress = pyqtSignal(str)
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation: Callable, parent: QWidget) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        try:
            result = self.operation(self)
            if self.isInterruptionRequested():
                raise TeachingCancelled("已取消。已发送的请求可能仍在服务端运行。")
            self.result.emit(result)
        except (TeachingCancelled, ValueError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"请求未完成（{type(exc).__name__}），请检查文件、依赖和模型设置。")


class TeachingPage(QWidget):
    """Chat, upload and evidence display; preferences are fetched at send time."""

    def __init__(self, settings: Callable[[], dict], notes_root: Callable[[], Path],
                 cache_root: Path, open_settings: Callable[[], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.get_settings = settings
        self.get_notes_root = notes_root
        self.cache_root = cache_root
        self.worker = None
        self.history = []
        self.transcript = []
        self._context_key = None
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("教学对话")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        settings_button = QPushButton("模型设置")
        settings_button.clicked.connect(open_settings)
        header.addWidget(settings_button)
        self.clear_button = QPushButton("新对话")
        self.clear_button.clicked.connect(self.clear_session)
        header.addWidget(self.clear_button)
        layout.addLayout(header)
        self.notice = QLabel()
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.browser = _ChatBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setAccessibleName("教学对话及校验结果")
        layout.addWidget(self.browser, 1)
        self.sources = QCheckBox("显示引用片段原文")
        self.sources.toggled.connect(self._render)
        layout.addWidget(self.sources)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("科目"))
        self.subject = QLineEdit()
        self.subject.setAccessibleName("科目过滤")
        self.subject.setPlaceholderText("留空为全部；输入完整科目名称")
        filters.addWidget(self.subject, 1)
        filters.addWidget(QLabel("笔记类型"))
        self.note_type = QComboBox()
        self.note_type.setAccessibleName("笔记类型过滤")
        for label, value in (("全部", None), ("期末", "exam"), ("考研", "postgraduate")):
            self.note_type.addItem(label, value)
        filters.addWidget(self.note_type)
        layout.addLayout(filters)
        self.attachments = QListWidget()
        self.attachments.setAccessibleName("本次请求附件，双击移除")
        self.attachments.setMaximumHeight(85)
        self.attachments.itemDoubleClicked.connect(
            lambda item: self.attachments.takeItem(self.attachments.row(item)))
        self.attachments.hide()
        layout.addWidget(self.attachments)
        layout.addWidget(QLabel("问题（Ctrl+Enter 发送）"))
        self.question = QPlainTextEdit()
        self.question.setAccessibleName("教学问题")
        self.question.setPlaceholderText("向课程助教提问；可拖入 PDF、PPTX、DOCX、TXT。")
        self.question.setAcceptDrops(False)
        self.question.setMaximumHeight(90)
        layout.addWidget(self.question)
        self.status = QLabel("尚未启用模型")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.attach_button = QPushButton("上传附件")
        self.attach_button.clicked.connect(self.choose_files)
        actions.addWidget(self.attach_button)
        self.remove_button = QPushButton("移除选中附件")
        self.remove_button.clicked.connect(self._remove_selected)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self.send)
        actions.addWidget(self.send_button)
        layout.addLayout(actions)
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.activated.connect(self.send)
        self.refresh_settings()

    def is_busy(self) -> bool:
        """Return whether a worker is still owned (including pending signals)."""
        return self.worker is not None

    def refresh_settings(self) -> None:
        """Update readiness and theme without loading optional SDKs."""
        settings = self.get_settings()
        config = TeachingConfig.from_settings(settings)
        error = ""
        try:
            config.validate()
            modules = ["chromadb", "pypdf", "pptx", "docx2txt",
                       "ollama" if config.provider == "local" else "openai"]
            if any(find_spec(module) is None for module in modules):
                error = "当前 Python 缺少教学依赖，请安装 requirements-phase3.txt 或使用 .venv-phase3 启动。"
        except ValueError as exc:
            error = str(exc)
        self.notice.setText(error or
            f"模型：{config.model} · 服务：{config.base_url}\n"
            "只发送问题、最近对话和召回的文本片段；不会改写笔记。AI 校验结论请对照来源复核。")
        if not error and self.status.text() == "尚未启用模型":
            self.status.setText("可开始提问；也可先到模型设置中测试连接。")
        enabled = not error and not self.is_busy()
        for control in (self.send_button, self.question, self.attach_button):
            control.setEnabled(enabled)
        for control in (self.clear_button, self.subject, self.note_type, self.attachments, self.remove_button):
            control.setEnabled(not self.is_busy())
        self.cancel_button.setEnabled(self.is_busy())
        self._render()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self.refresh_settings()

    def choose_files(self) -> None:
        """Select temporary attachments without copying their source files."""
        paths, _ = QFileDialog.getOpenFileNames(self, "选择本次教学附件", "",
                                              "课程资料 (*.pdf *.pptx *.docx *.txt)")
        self.add_files(paths)

    def add_files(self, paths: list[str]) -> None:
        """Validate lightweight metadata; actual extraction runs in the worker."""
        if self.is_busy() or not self.attach_button.isEnabled():
            return
        config = TeachingConfig.from_settings(self.get_settings())
        allowed = config.allowed_types.lower().replace(" ", "").split(",")
        existing = {self.attachments.item(i).text() for i in range(self.attachments.count())}
        errors = []
        for value in paths:
            path = Path(value).resolve()
            try:
                if (not path.is_file() or path.suffix.lower() not in allowed or
                        path.stat().st_size > config.max_file_mb * 1024 * 1024):
                    raise ValueError("类型不允许、文件不存在或超过大小上限")
                if str(path) in existing:
                    continue
                if self.attachments.count() >= 20:
                    raise ValueError("每次最多 20 个附件")
                self.attachments.addItem(str(path))
                existing.add(str(path))
            except (OSError, ValueError) as exc:
                errors.append(f"{path.name}：{exc}")
        self.attachments.setVisible(self.attachments.count() > 0)
        self.status.setText("；".join(errors) if errors else f"本次已选 {self.attachments.count()} 个附件")

    def _remove_selected(self) -> None:
        row = self.attachments.currentRow()
        if row >= 0:
            self.attachments.takeItem(row)
        self.attachments.setVisible(self.attachments.count() > 0)

    def dragEnterEvent(self, event: object) -> None:
        if (not self.is_busy() and self.attach_button.isEnabled() and
                event.mimeData().hasUrls() and all(url.isLocalFile() for url in event.mimeData().urls())):
            event.acceptProposedAction()

    def dropEvent(self, event: object) -> None:
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def send(self) -> None:
        """Snapshot all settings before starting background extraction/retrieval."""
        if self.is_busy() or not self.send_button.isEnabled():
            return
        question = self.question.toPlainText().strip()
        if not question or len(question) > 4000:
            self.status.setText("请输入 1–4000 字符的问题。")
            return
        settings = dict(self.get_settings())
        config = TeachingConfig.from_settings(settings)
        if urlsplit(config.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            answer = QMessageBox.question(self, "向远程模型发送资料",
                f"将向 {config.base_url} 发送本次问题、最近对话及相关笔记/附件文本片段。服务可能计费。继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        paths = [self.attachments.item(i).text() for i in range(self.attachments.count())]
        root = self.get_notes_root()
        subject, note_type = self.subject.text().strip() or None, self.note_type.currentData()
        key = (str(root), subject, note_type, config)
        if key != self._context_key:
            self.history.clear()
            self._context_key = key
        history = list(self.history)
        cache = self.cache_root if settings.get("external_cache_policy") == "keep" else None
        self.transcript.append(("user", question))
        self._start(lambda worker: teach_session(
            question, paths, subject, note_type, config=config, notes_root=root,
            cache_dir=cache, history=history, cancelled=worker.isInterruptionRequested,
            progress=worker.progress.emit))

    def check_connection(self) -> None:
        """Confirm a model-list-only connection check and run off the GUI thread."""
        if self.is_busy():
            self.status.setText("请等待当前请求结束。")
            return
        config = TeachingConfig.from_settings(self.get_settings())
        try:
            config.validate()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        answer = QMessageBox.question(self, "测试模型连接",
            f"将连接 {config.base_url} 并查询模型列表，不发送笔记或问题。继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._start(lambda worker: test_connection(config))

    def _start(self, operation: Callable) -> None:
        self.worker = _TeachingWorker(operation, self)
        self.worker.progress.connect(self.status.setText)
        self.worker.result.connect(self._receive)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.status.setText("正在准备…")
        self.progress.show()
        self.refresh_settings()
        self.worker.start()

    def _receive(self, result: object) -> None:
        if isinstance(result, TeachSession):
            self.transcript.append(("assistant", result))
            self.transcript = self.transcript[-60:]
            self.history.extend([{"role": "user", "content": result.user_question},
                                 {"role": "assistant", "content": result.final_answer}])
            self.history = self.history[-6:]
            self.question.clear()
            self.attachments.clear()
            self.attachments.hide()
            self.status.setText("回答完成；临时向量索引已清理。附件仅用于本次请求，追问如需校验请重新选择。")
            self._render()
        else:
            self.status.setText(str(result))

    def _failed(self, message: str) -> None:
        self.status.setText(message)
        self.transcript.append(("status", message))
        self._render()

    def _finished(self) -> None:
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.progress.hide()
        self.refresh_settings()

    def cancel(self) -> None:
        """Cancel at safe boundaries; do not terminate threads during native I/O."""
        if self.worker is not None:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText("正在取消…当前解析或网络调用需返回后清理；网络等待受请求超时限制。")

    def clear_session(self) -> None:
        """Discard in-memory chat and pending uploads, not source files."""
        if self.is_busy():
            return
        self.history.clear()
        self.transcript.clear()
        self.attachments.clear()
        self.attachments.hide()
        self.question.clear()
        self._render()
        self.status.setText("已开始新对话。已启用的磁盘文本缓存可在设置中手动清理。")

    def _render(self, *_args: object) -> None:
        self.transcript = self.transcript[-60:]
        parts, findings = [], []
        for role, value in self.transcript:
            if role == "assistant":
                parts.append("## 课程助教\n\n" + escape(value.final_answer))
                if value.discrepancies:
                    parts.append("### 校验提示（AI 生成，请复核）\n")
                    for finding in value.discrepancies:
                        parts.append(escape(finding) + "\n")
                        findings.append(finding)
                for warning in value.warnings:
                    parts.append("提示：" + escape(warning) + "\n")
                if value.recalled_notes or value.external_chunks:
                    parts.append("### 本次引用来源\n")
                for source in value.recalled_notes + value.external_chunks:
                    parts.append(escape(f"[{source['id']}] {source['metadata']['title']} · 片段 {source['metadata']['chunk']}") + "\n")
                    if self.sources.isChecked():
                        parts.append("\n".join("> " + escape(line) for line in source["content"].splitlines()) + "\n")
            else:
                parts.append(("## 你\n\n" if role == "user" else "提示：") + escape(str(value)))
        self.browser.setMarkdown("\n\n".join(parts) if parts else "## 课程助教\n\n配置模型后，输入问题或选择外部课程资料开始。\n\n不会自动修改笔记；新对话和退出应用都会清除内存中的聊天记录。")
        colors = theme_colors(resolved_theme(str(self.get_settings().get("theme", "light"))))
        selections = []
        block = self.browser.document().begin()
        while block.isValid():
            if block.text().startswith(("【冲突】", "【可能遗漏】", "【补充】")):
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format.setBackground(QColor(colors["selection"]))
                selection.format.setForeground(QColor(colors["selection_text"]))
                selections.append(selection)
            block = block.next()
        self.browser.setExtraSelections(selections)
        self.browser.moveCursor(QTextCursor.MoveOperation.End)
