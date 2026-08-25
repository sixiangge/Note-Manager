"""Settings workspace matching the existing quiet desktop layout."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


CATEGORY_KEYS = {
    "appearance": {
        "theme",
        "ui_scale",
        "note_font_size",
        "code_font_size",
        "body_font",
        "code_font",
        "startup_page",
        "restore_reading_state",
    },
    "search": {"search_mode", "auto_generate_samples", "show_sample_notes"},
    "files": {
        "notes_root",
        "index_strategy",
        "external_editor_mode",
        "external_editor_path",
    },
    "privacy": {
        "history_enabled",
        "history_limit",
        "external_cache_policy",
    },
}


class SettingsOptionPicker(QToolButton):
    """Single-select popup matching the full-text search filter controls."""

    value_changed = pyqtSignal(object)

    def __init__(
        self,
        items: list[tuple[str, Any]],
        minimum_width: int = 170,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsOptionPicker")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumWidth(minimum_width)
        self._value: Any = None
        self.clicked.connect(self._toggle_popup)

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("multiSelectPopup")
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(6, 6, 6, 6)
        popup_layout.setSpacing(0)
        self.item_list = QListWidget()
        self.item_list.setObjectName("settingsOptionList")
        self.item_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.item_list.itemClicked.connect(self._select_item)
        popup_layout.addWidget(self.item_list)
        self.set_items(items)

    def set_items(self, items: list[tuple[str, Any]]) -> None:
        current = self._value
        self.item_list.clear()
        for label, value in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self.item_list.addItem(item)
        self.item_list.setFixedHeight(
            min(260, max(38, self.item_list.count() * 37 + 2))
        )
        self.set_value(current, emit=False)

    def value(self) -> Any:
        return self._value

    def set_value(self, value: Any, *, emit: bool = False) -> None:
        selected: QListWidgetItem | None = None
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == value:
                selected = item
                break
        if selected is None and self.item_list.count():
            selected = self.item_list.item(0)
        if selected is None:
            self._value = None
            self.setText("▾")
            return
        previous = self._value
        self._value = selected.data(Qt.ItemDataRole.UserRole)
        self.item_list.setCurrentItem(selected)
        self.setText(f"{selected.text()}  ▾")
        self.setToolTip(selected.text())
        if emit and self._value != previous:
            self.value_changed.emit(self._value)

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.close()
            return
        width = max(self.width(), self.minimumWidth())
        self._popup.setFixedWidth(width)
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

    def _select_item(self, item: QListWidgetItem) -> None:
        self.set_value(item.data(Qt.ItemDataRole.UserRole), emit=True)
        self._popup.close()


class SettingRow(QFrame):
    """One unframed setting row with a label, explanation, and control."""

    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 13, 0, 13)
        layout.setSpacing(18)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("settingTitle")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        text_box.addWidget(title_label)
        text_box.addWidget(description_label)
        layout.addLayout(text_box, 1)

        control.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)


class SettingsPage(QWidget):
    """Categorized settings page; persistence is handled by MainWindow."""

    setting_changed = pyqtSignal(str, object)
    action_requested = pyqtSignal(str)

    def __init__(self, settings: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = dict(settings)
        self._controls: dict[str, QWidget] = {}
        self._updating = False
        self._category_ids = ["appearance", "search", "files", "privacy", "phase3"]
        self._build_ui()
        self.set_values(settings)

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        category_panel = QFrame()
        category_panel.setObjectName("settingsCategoriesPanel")
        category_layout = QVBoxLayout(category_panel)
        category_layout.setContentsMargins(22, 22, 18, 18)
        category_layout.setSpacing(10)
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        category_layout.addWidget(title)

        self.categories = QListWidget()
        self.categories.setObjectName("settingsCategories")
        for label in ("外观与阅读", "搜索与笔记库", "文件与索引", "隐私与数据", "教学与模型"):
            self.categories.addItem(QListWidgetItem(label))
        self.categories.currentRowChanged.connect(self._show_category)
        category_layout.addWidget(self.categories, 1)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_appearance_page())
        self.pages.addWidget(self._build_search_page())
        self.pages.addWidget(self._build_files_page())
        self.pages.addWidget(self._build_privacy_page())
        self.pages.addWidget(self._build_phase3_page())
        outer.addWidget(category_panel)
        outer.addWidget(self.pages, 1)
        self.categories.setCurrentRow(0)

    def _page(self, title: str, category_id: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(30, 22, 30, 20)
        page_layout.setSpacing(0)

        header = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        header.addWidget(heading)
        header.addStretch(1)
        if category_id != "phase3":
            reset = QPushButton("恢复本页默认")
            reset.clicked.connect(
                lambda _checked=False, key=category_id: self.action_requested.emit(
                    f"reset_category:{key}"
                )
            )
            header.addWidget(reset)
        page_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 10, 8, 10)
        content_layout.setSpacing(0)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page, content_layout

    def _combo(
        self,
        key: str,
        items: list[tuple[str, Any]],
        minimum_width: int = 170,
    ) -> SettingsOptionPicker:
        picker = SettingsOptionPicker(items, minimum_width)
        picker.value_changed.connect(
            lambda value, setting_key=key: self._emit_change(setting_key, value)
        )
        self._controls[key] = picker
        return picker

    def _check(self, key: str, label: str = "启用") -> QCheckBox:
        checkbox = QCheckBox(label)
        checkbox.toggled.connect(
            lambda value, setting_key=key: self._emit_change(setting_key, value)
        )
        self._controls[key] = checkbox
        return checkbox

    def _spin(self, key: str, minimum: int, maximum: int, suffix: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName("settingsNumberInput")
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.valueChanged.connect(
            lambda value, setting_key=key: self._emit_change(setting_key, value)
        )
        self._controls[key] = spin
        return spin

    @staticmethod
    def _row(layout: QVBoxLayout, title: str, description: str, control: QWidget) -> None:
        layout.addWidget(SettingRow(title, description, control))

    def _font_items(self, monospace: bool = False) -> list[tuple[str, str]]:
        installed = set(QFontDatabase.families())
        candidates = (
            ["Cascadia Mono", "JetBrains Mono", "Consolas", "Courier New"]
            if monospace
            else ["Microsoft YaHei UI", "Segoe UI", "Microsoft YaHei", "SimSun"]
        )
        return [("系统推荐", "system")] + [
            (font, font) for font in candidates if font in installed
        ]

    def _build_appearance_page(self) -> QWidget:
        page, layout = self._page("外观与阅读", "appearance")
        self._row(
            layout,
            "界面配色",
            "在浅色与深色主题之间切换。",
            self._combo(
                "theme",
                [("浅色", "light"), ("深色", "dark"), ("跟随系统", "system")],
            ),
        )
        self._row(layout, "界面缩放", "统一调整界面文字、控件和图标的显示比例。", self._combo("ui_scale", [(f"{value}%", value) for value in (90, 100, 110, 125)]))
        sizes = [("小", "small"), ("标准", "standard"), ("大", "large")]
        self._row(layout, "笔记正文字号", "调整预览中的正文、标题、列表和表格字号。", self._combo("note_font_size", sizes))
        self._row(layout, "代码块字号", "独立调整代码块的等宽文字大小。", self._combo("code_font_size", sizes))
        self._row(layout, "正文字体", "选择笔记正文使用的字体；缺失时回退到系统字体。", self._combo("body_font", self._font_items()))
        self._row(layout, "代码字体", "选择代码块使用的等宽字体；缺失时回退到系统字体。", self._combo("code_font", self._font_items(monospace=True)))
        self._row(layout, "启动位置", "决定每次启动后首先打开笔记库还是全文搜索。", self._combo("startup_page", [("笔记库", "library"), ("全文搜索", "search")]))
        self._row(layout, "恢复阅读位置", "启动时重新打开上次阅读的笔记并恢复滚动位置。", self._check("restore_reading_state"))
        layout.addStretch(1)
        return page

    def _build_search_page(self) -> QWidget:
        page, layout = self._page("搜索与笔记库", "search")
        self._row(layout, "搜索行为", "按 Enter 执行搜索，或在停止输入约 350 毫秒后自动搜索。", self._combo("search_mode", [("按 Enter 搜索", "enter"), ("输入即搜索", "live")]))
        self._row(layout, "自动生成示例笔记", "笔记目录为空时，在重建索引前生成内置示例。", self._check("auto_generate_samples"))
        self._row(layout, "显示示例笔记", "控制笔记树、列表和搜索结果是否显示带“示例”标签的笔记。", self._check("show_sample_notes"))
        layout.addStretch(1)
        return page

    def _path_control(self, key: str, action: str, button_text: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        field = QLineEdit()
        field.setReadOnly(True)
        field.setMinimumWidth(310)
        self._controls[key] = field
        row.addWidget(field, 1)
        button = QPushButton(button_text)
        button.clicked.connect(lambda: self.action_requested.emit(action))
        row.addWidget(button)
        return container

    def _build_files_page(self) -> QWidget:
        page, layout = self._page("文件与索引", "files")
        self._row(layout, "笔记目录", "切换本地 Markdown 目录后会确认并重建索引，不移动或修改原文件。", self._path_control("notes_root", "choose_notes_root", "选择目录"))
        self._row(layout, "索引策略", "可仅手动重建，或在启动发现文件变化时询问是否重建。", self._combo("index_strategy", [("仅手动重建", "manual"), ("启动时检查并提示", "prompt")]))

        editor_box = QWidget()
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(7)
        editor_mode = self._combo("external_editor_mode", [("系统默认程序", "system"), ("指定程序", "custom")], 310)
        editor_layout.addWidget(editor_mode)
        editor_layout.addWidget(self._path_control("external_editor_path", "choose_external_editor", "选择程序"))
        self.editor_status = QLabel()
        self.editor_status.setObjectName("muted")
        editor_layout.addWidget(self.editor_status)
        self._row(layout, "外部编辑器", "使用系统关联程序，或指定用于打开 Markdown 的可执行文件。", editor_box)

        status_box = QWidget()
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.storage_status = QLabel("正在读取本地数据状态...")
        self.storage_status.setObjectName("muted")
        self.storage_status.setWordWrap(True)
        status_layout.addWidget(self.storage_status)
        refresh = QPushButton("刷新状态")
        refresh.clicked.connect(lambda: self.action_requested.emit("refresh_storage_status"))
        status_layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignRight)
        self._row(layout, "数据库与缓存", "只读显示 SQLite、笔记目录和外部资料缓存状态。", status_box)

        actions = QWidget()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        for label, action in (
            ("重建索引", "rebuild_index"),
            ("清理缓存", "clear_external_cache"),
            ("重置全部设置", "reset_all_settings"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, key=action: self.action_requested.emit(key))
            action_layout.addWidget(button)
        self._row(layout, "维护操作", "操作前会说明影响范围并要求确认。", actions)
        layout.addStretch(1)
        return page

    def _build_privacy_page(self) -> QWidget:
        page, layout = self._page("隐私与数据", "privacy")
        self._row(layout, "保存搜索历史", "关闭后不再写入新的搜索记录，已有记录不会被删除。", self._check("history_enabled"))
        self._row(layout, "历史保留条数", "限制 SQLite 中最多保留的最近搜索记录。", self._spin("history_limit", 1, 100, " 条"))
        self._row(layout, "外部资料缓存", "选择退出应用时清理临时外部资料，或保留到手动清理。", self._combo("external_cache_policy", [("退出时清理", "discard"), ("保留至手动清理", "keep")]))

        export_button = QPushButton("导出本地数据")
        export_button.clicked.connect(lambda: self.action_requested.emit("export_local_data"))
        self._row(layout, "本地数据导出", "导出设置和搜索历史，不包含 Markdown 笔记正文。", export_button)

        explanation = QLabel(
            "data/notes 保存 Markdown 原文，是唯一真源；index.json 是可重建的全文索引；"
            "notemanager.db 保存可重建的笔记目录、设置和搜索历史；data/external 保存临时外部资料。"
        )
        explanation.setObjectName("muted")
        explanation.setWordWrap(True)
        explanation.setMinimumWidth(360)
        self._row(layout, "本地数据说明", "说明各类本地文件的用途和可恢复边界。", explanation)
        layout.addStretch(1)
        return page

    def _build_phase3_page(self) -> QWidget:
        page, layout = self._page("教学与模型", "phase3")
        badge = QLabel("Phase 3 · 即将推出")
        badge.setObjectName("badge")
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        for title, description in (
            ("模型提供方", "Ollama 本地模型或 OpenAI 兼容 API。"),
            ("模型与连接", "模型名称、服务地址、超时与连通性测试。"),
            ("检索策略", "返回片段数、外部资料优先级与示例笔记引用策略。"),
            ("上传策略", "允许的文件类型、大小上限与会话清理策略。"),
            ("凭据管理", "API Key 仅使用系统凭据存储或环境变量。"),
        ):
            unavailable = QLabel("暂不可用")
            unavailable.setObjectName("muted")
            self._row(layout, title, description, unavailable)
        layout.addStretch(1)
        return page

    def _show_category(self, row: int) -> None:
        if 0 <= row < self.pages.count():
            self.pages.setCurrentIndex(row)
            if self._category_ids[row] == "files":
                self.action_requested.emit("refresh_storage_status")

    def _emit_change(self, key: str, value: Any) -> None:
        if self._updating:
            return
        self._settings[key] = value
        self.setting_changed.emit(key, value)

    def set_values(self, settings: dict[str, Any]) -> None:
        self._settings = dict(settings)
        self._updating = True
        try:
            for key, control in self._controls.items():
                value = settings.get(key)
                if isinstance(control, SettingsOptionPicker):
                    control.set_value(value, emit=False)
                elif isinstance(control, QCheckBox):
                    control.setChecked(bool(value))
                elif isinstance(control, QSpinBox):
                    control.setValue(int(value))
                elif isinstance(control, QLineEdit):
                    control.setText(str(value or ""))
        finally:
            self._updating = False
        self._update_editor_path_state()

    def set_setting_value(self, key: str, value: Any) -> None:
        values = dict(self._settings)
        values[key] = value
        self.set_values(values)

    def _update_editor_path_state(self) -> None:
        path = self._controls.get("external_editor_path")
        custom = self._settings.get("external_editor_mode") == "custom"
        if path is not None:
            path.parentWidget().setEnabled(custom)
        if not hasattr(self, "editor_status"):
            return
        if not custom:
            self.editor_status.setText("当前使用系统的 .md 文件关联程序")
            return
        configured = Path(str(self._settings.get("external_editor_path", "")))
        self.editor_status.setText(
            "已检测到指定程序" if configured.is_file() else "指定程序不存在或尚未选择"
        )

    def update_storage_status(self, summary: dict[str, Any]) -> None:
        sync_ns = int(summary.get("last_sync_ns", 0))
        sync_text = (
            datetime.fromtimestamp(sync_ns / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S")
            if sync_ns
            else "尚未同步"
        )
        database_size = int(summary.get("database_size", 0)) / 1024
        cache_size = int(summary.get("cache_size", 0)) / 1024
        self.storage_status.setText(
            f"SQLite：{summary.get('database_path', '')}\n"
            f"笔记：{summary.get('note_count', 0)} 篇 · 上次同步：{sync_text} · 数据库：{database_size:.1f} KiB\n"
            f"外部缓存：{summary.get('cache_count', 0)} 项 · {cache_size:.1f} KiB"
        )

    def category_keys(self, category_id: str) -> set[str]:
        return set(CATEGORY_KEYS.get(category_id, set()))


__all__ = ["SettingsPage"]
