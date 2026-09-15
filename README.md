# NoteManager

本地化课程知识中台 — 笔记管理与 AI 教学校验。

## 功能边界

| 功能                   | Phase 1 (CLI) | Phase 2 (GUI) | Phase 3 (AI) |
| -------------------- |:-------------:|:-------------:|:------------:|
| Markdown 笔记管理        | ✅             | ✅             | ✅            |
| 关键词全文搜索              | ✅             | ✅             | ✅            |
| 双轨制过滤（期末/考研）         | ✅             | ✅             | ✅            |
| 按科目过滤                | ✅             | ✅             | ✅            |
| 按标签排除搜索结果            | ✅             | ✅             | ✅            |
| 空仓示例笔记生成             | ✅             | ✅             | ✅            |
| SQLite 笔记目录与搜索历史     | —             | ✅             | ✅            |
| 图形界面浏览/搜索            | —             | ✅             | ✅            |
| LaTeX 公式与代码块增强渲染     | —             | ✅             | ✅            |
| 个性化设置与深浅色主题          | —             | ✅             | ✅            |
| 外部资料拖拽导入             | —             | 预留            | ✅            |
| PDF/PPTX/DOCX/TXT 解析 | —             | —             | ✅            |
| AI 教学校验              | —             | —             | ✅            |
| 向量检索（RAG）            | —             | —             | ✅            |

> ✅ 已实现。Phase 3 需要额外安装可选依赖并配置模型，默认关闭；不影响离线浏览和关键词搜索。

## 打包 Windows 应用

在 PowerShell 中运行以下命令可生成带图标的 GUI 发行版：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -InstallBuildDependencies
```

生成的程序位于 `dist\NoteManager\NoteManager.exe`。请保留整个 `NoteManager` 文件夹，不能只移动其中的 `.exe`。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 构建索引并同步 SQLite 笔记目录（首次运行自动生成示例笔记）
python main.py index

# 搜索笔记
python main.py search "极限"

# 按科目和笔记类型过滤
python main.py search "应用层" --subject "计算机网络" --type exam

# 排除带有“示例”标签的笔记
python main.py search "极限" --exclude-tag "示例"

# 启动图形界面
python main.py gui
```

图形界面支持按科目浏览、全文搜索与高亮、只读 Markdown 预览、离线 LaTeX 公式渲染、带边框的等宽字体代码块、标签排除、持久化搜索历史和一键重建索引。公式使用 `$...$`（行内）或 `$$...$$`（独立公式）书写。科目列表和排除标签列表均支持搜索、多选和全选/全不选；输入列表搜索词后，批量选择只作用于当前匹配项。搜索结果可以同时来自多个已选科目，命中任一已选排除标签的笔记不会显示；点击历史记录会恢复当时选择的全部科目、笔记类型与排除标签。内置示例笔记的标题带有 `[示例]` 前缀，并统一包含 `示例` 标签。教学对话与附件上传已在 Phase 3 接入，需按下文启用可选依赖和模型。

GUI 启动后会立即显示与当前主题一致的启动页，并在后台读取索引和搜索历史。默认“仅手动重建”策略不会在启动时扫描笔记目录；选择“启动时检查文件变更并提示重建”后，只在后台比较文件路径和修改时间。启动过程不会全量同步 SQLite 笔记目录或计算内容哈希；这些操作仅在运行 `python main.py index` 或点击“重建索引”时按需执行。

### 设置

GUI 左侧栏底部的“设置”位于“重建索引”下方。设置会即时保存到 SQLite，并支持：

- 浅色/深色/跟随系统主题、界面缩放、笔记与代码字号和字体
- 启动页面、恢复上次阅读笔记与滚动位置
- 按 Enter 搜索或输入即搜索、示例笔记生成与显示策略
- 切换本地笔记目录、启动时检查索引变化、指定外部 Markdown 编辑器
- 搜索历史开关和保留条数、外部资料缓存策略、本地设置与搜索历史导出
- 查看数据库与缓存状态、重建索引、清理缓存和恢复默认设置

深色主题会反转 GUI 的文字、背景、控件、滚动条、复选框、选中状态、Markdown、代码块和公式颜色，应用图标保持原设计。切换笔记目录只改变索引来源并要求重建索引，不会移动或修改原 Markdown 文件。

## 数据存储

SQLite 由 Python 标准库 `sqlite3` 提供，不需要安装或运行独立数据库服务。

- `data/notes/`：Markdown 原始笔记，是正文与 Front-matter 的唯一数据源
- `data/index/index.json`：jieba 全文检索使用的可重建倒排索引
- `data/index/notemanager.db`：SQLite 笔记目录、文件指纹、GUI 设置与搜索历史

不要直接修改 SQLite 中的笔记字段。使用外部编辑器修改 Markdown 后，运行 `python main.py index`，或在 GUI 中点击“重建索引”，系统会在同一轮操作中更新 `index.json` 和 SQLite。数据库文件丢失或损坏时，关闭 GUI、移除该数据库及其 `-wal`/`-shm` 辅助文件，再重新构建索引即可恢复笔记目录；搜索历史会被重置。

## 教学与校验（Phase 3）

教学页面支持问题、科目/类型过滤、附件选择或拖入、引用原文与差异高亮。模型校验结论需人工复核，系统绝不修改笔记。

```bash
# 在已安装基础依赖的环境中，按需安装教学依赖
python -m pip install -r requirements-phase3.txt

# MODEL_NAME 替换为本机 Ollama 中已有的模型名称
python main.py teach "解释极限的定义" --model local --model-name MODEL_NAME --files "课件.pdf"
```

GUI 在“设置 → 教学与模型”中选择提供方、模型名与地址，可先测试连接。OpenAI 兼容 API 的密钥只从 `OPENAI_API_KEY` 环境变量读取。远程调用前会确认发送范围；本地模型连接绕过系统代理。仅发送召回的文本片段和最近对话，不发送完整附件或本地绝对路径。

完整用法、能力限制、测试与本次快速回退方法见 [PHASE3.md](PHASE3.md)。检索使用本地文本特征向量 + ChromaDB，不是神经语义嵌入；不自动下载嵌入模型，不支持图片/扫描件 OCR。

## 项目结构

```
├── main.py                CLI 入口
├── data/notes/            笔记目录（按科目分类）
├── data/external/         外部资料缓存
├── data/index/            倒排索引与 SQLite 本地数据库
├── src/storage.py         SQLite 存储与同步
├── src/gui/startup.py     启动页与后台轻量加载
├── src/parsers/           文件解析器
├── src/rag/               向量检索模块
└── tests/                 单元测试
```

## 许可

个人学习项目。
