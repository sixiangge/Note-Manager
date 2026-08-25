# NoteManager 开发规划

> **项目代号**：NoteManager — 本地化计算机课程知识中台
> **受众**：开发者本人 + Coding Agent
> **用途**：个人开发路线图 & Agent 代码编写的执行规范

---

## 1. 项目概述

### 1.1 目标

构建一个纯本地运行的"计算机课程知识中台"，支持：

- **笔记管理**：Markdown 笔记 + YAML Front-matter 元数据，区分期末应试与考研深度两种笔记类型
- **关键词检索**：基于 jieba 分词 + 倒排索引的全文搜索，按字段权重和考点频率排序
- **远期教学校验**：AI 结合用户上传的外部资料（PPT/试卷/辅导书）与现有笔记对照讲解，指出笔记中的错误、遗漏或过时观点

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **双轨制元数据** | `note_type: exam`（期末）vs `postgraduate`（考研），两者独立存储但支持跨类型检索 |
| **Markdown 单一真源** | 笔记正文与 Front-matter 始终以 `data/notes/` 中的 Markdown 文件为准；数据库仅保存可重建的目录/元数据及搜索历史等应用状态，避免双向同步冲突 |
| **外部资料不入倒排索引** | 外部文件（PDF/PPTX/DOCX/TXT）仅在 RAG 阶段动态解析分块，不参与关键词索引 |
| **外部资料按需上传** | 用户不在文件夹中预存外部资料，而是在教学对话中临时上传（类似网页 AI 聊天上传附件），系统即时解析并校验笔记，会话结束后文件不持久化（可缓存副本供下次快速复用，但非强制） |
| **外部资料优先** | 教学场景中，外部资料（官方 PPT/试卷答案）被视为 Ground Truth，笔记作为被校验对象 |
| **纯本地、单机** | Phase 1-2 零网络依赖，Phase 3 可选接入本地或远程 LLM API |
| **空仓启动** | 首次运行时自动生成示例笔记，确保开箱可用 |
| **Git 版本管理** | 项目全程使用 Git 进行版本控制。代码与项目文档纳入追踪；笔记（`data/notes/`）、索引（`data/index/`）、外部资料缓存（`data/external/`）均不纳入，由用户自行管理笔记内容 |

### 1.3 技术栈

| 阶段 | 依赖 | 用途 |
|------|------|------|
| 开发全程 | `git` | 版本控制，代码与项目文档变更追踪 |
| Phase 1 | `jieba`, `python-frontmatter` | 分词、Front-matter 解析 |
| Phase 1 | `pathlib`, `json`, `argparse` | 文件操作、索引持久化、CLI |
| Phase 2 | `PyQt6`, `matplotlib` | 图形界面、离线 LaTeX 公式渲染 |
| Phase 2 扩展 | `sqlite3`（Python 标准库） | 本地笔记目录、元数据与搜索历史管理 |
| Phase 3 | `chromadb`, `pypdf`, `python-pptx`, `docx2txt` | 向量检索、文档解析 |
| Phase 3 | `ollama` 或 `openai` | LLM 调用（本地或 API） |

---

## 2. 目录结构

```
NoteManager/
├── README.md                     # 项目说明、Phase 功能边界、快速开始
├── plan.md                       # 本文件
├── main.py                       # CLI 入口，argparse 子命令分发
├── requirements.txt              # 依赖清单，按 Phase 分组注释
├── .gitignore                    # Git 忽略规则
│
├── data/
│   ├── 格式示例.md                # 笔记格式模板（占位内容，位于 data/ 根目录不参与索引）
│   ├── notes/                    # Markdown 笔记，按科目子文件夹（不纳入 Git，.gitignore 排除）
│   │   ├── 微积分/
│   │   │   ├── [示例]极限与连续.md
│   │   │   └── 导数与微分.md
│   │   ├── 数据结构/
│   │   │   ├── [示例]二叉树与遍历.md
│   │   │   └── 排序算法对比.md
│   │   └── 机器学习导论/
│   │       └── [示例]监督学习基础.md
│   │
│   ├── external/                 # 外部资料缓存（不纳入 Git，.gitignore 排除）
│   │   └── .gitkeep              # 仅保留目录结构占位
│   │
│   └── index/
│       ├── index.json            # 倒排索引（仅索引 .md 笔记，.gitignore 排除）
│       ├── notemanager.db         # SQLite 本地目录与应用状态（.gitignore 排除）
│       └── external_manifest.json # 上传文件缓存清单（.gitignore 排除）
│
├── src/
│   ├── __init__.py
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── markdown_parser.py    # Phase 1 ✅ Markdown 解析
│   │   ├── pdf_parser.py         # Phase 3 🔮 PDF 解析（占位）
│   │   ├── pptx_parser.py        # Phase 3 🔮 PPTX 解析（占位）
│   │   └── docx_parser.py        # Phase 3 🔮 DOCX 解析（占位）
│   │
│   ├── indexer.py                # 倒排索引构建（仅 .md 笔记）
│   ├── searcher.py               # 关键词检索 + 排序
│   ├── storage.py                # SQLite 笔记目录与搜索历史
│   ├── oracle.py                 # 教学校验引擎（Phase 1 占位，Phase 3 实现）
│   │
│   └── rag/
│       ├── __init__.py           # Phase 1 空桩
│       └── retriever.py          # Phase 3 🔮 RAG 检索器（占位）
│
└── tests/
    ├── __init__.py
    ├── test_markdown_parser.py
    ├── test_indexer.py
    └── test_searcher.py
```

---

## 3. 数据模型

### 3.1 Note（笔记）

```python
from dataclasses import dataclass, field
from typing import List, Literal
from pathlib import Path

@dataclass
class Note:
    title: str                              # 笔记标题
    subject: str                            # 所属科目，如"微积分"
    chapter: str                            # 章节，如"第一章 极限与连续"
    tags: List[str] = field(default_factory=list)  # 标签列表
    note_type: Literal["exam", "postgraduate"] = "exam"  # 笔记类型
    exam_freq: int = 0                      # 考点频率 0-5
    body: str = ""                          # Markdown 正文（不含 Front-matter）
    file_path: Path | None = None           # 源文件路径
```

**YAML Front-matter 示例**：

```yaml
---
title: "极限与连续"
subject: "微积分"
chapter: "第一章 极限与连续"
tags: ["极限", "ε-δ定义", "连续函数"]
note_type: "postgraduate"
exam_freq: 5
---
```

### 3.2 ExternalDocument（外部资料）

```python
from dataclasses import dataclass
from typing import List, Literal
from pathlib import Path

@dataclass
class ExternalDocument:
    doc_id: str                            # 唯一标识，由文件名+内容哈希生成
    source_path: Path                      # 用户上传时的原始路径（含文件名）
    subject: str | None = None             # 所属科目，由用户在上传时指定或从文件名推断
    doc_type: Literal["PPT", "试卷", "辅导书", "其他"] = "其他"  # 上传时用户指定或根据文件扩展名推断
    chunks: List[str] = field(default_factory=list)   # 文本分片（RAG检索用）
    upload_session_id: str = ""            # 上传所属的教学会话 ID，用于会话隔离
```

### 3.3 TeachSession（教学会话——远期）

```python
from dataclasses import dataclass
from typing import List

@dataclass
class TeachSession:
    user_question: str                     # 用户问题
    recalled_notes: List[dict]             # 召回的笔记片段 [{path, content, score}]
    external_chunks: List[dict]            # 引用的外部资料片段 [{doc_id, content, source_type}]
    final_answer: str = ""                 # LLM 生成的最终回答
    discrepancies: List[str] = field(default_factory=list)  # 差异清单
```

---

## 4. 搜索算法

### 4.1 倒排索引结构（index.json）

```json
{
  "documents": {
    "data/notes/微积分/[示例]极限与连续.md": {
      "title": "极限与连续",
      "subject": "微积分",
      "chapter": "第一章 极限与连续",
      "tags": ["极限", "ε-δ定义", "连续函数"],
      "note_type": "postgraduate",
      "exam_freq": 5
    }
  },
  "inverted_index": {
    "极限": {
      "data/notes/微积分/[示例]极限与连续.md": {
        "title": 1,
        "subject": 0,
        "chapter": 0,
        "tags": 1,
        "body": 12
      }
    }
  }
}
```

### 4.2 权重计算

对每个查询词项 t，对每篇文档 d：

```
score(d, t) = title_tf   × 3.0
            + subject_tf × 2.0
            + chapter_tf × 2.0
            + tags_tf    × 2.0
            + body_tf    × 1.0
```

文档总得分：

```
total_score(d, query) = Σ score(d, t)   for each t in jieba.cut(query)
                      + (exam_freq / 5.0) × 0.5   # 考点频率加分
```

### 4.3 过滤

- `--type exam`：仅返回 `note_type == "exam"` 的结果
- `--type postgraduate`：仅返回 `note_type == "postgraduate"` 的结果
- 不指定 `--type`：返回全部
- `--subject "科目"`：仅返回指定科目的结果；GUI 支持搜索科目并多选
- `--exclude-tag "标签"`：排除所有包含指定标签的结果；GUI 支持搜索标签并多选排除

### 4.4 分词

使用 `jieba.cut_for_search()` 兼顾召回率。

---

## 5. 核心模块规格

### 5.1 `src/parsers/markdown_parser.py`（Phase 1 实现）

**职责**：解析 Markdown 文件，分离 YAML Front-matter 元数据与正文。

```python
def parse_markdown(file_path: Path) -> Note:
    """
    解析 .md 文件，提取 Front-matter 和正文。

    Args:
        file_path: Markdown 文件的路径

    Returns:
        Note 对象，包含元数据和正文

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: Front-matter 格式错误或缺少必填字段
    """

def extract_metadata_from_frontmatter(post: dict, file_path: Path) -> Note:
    """从 python-frontmatter 解析结果中构造 Note 对象。"""

def validate_note(note: Note) -> list[str]:
    """
    校验 Note 对象字段合法性，返回错误信息列表。
    校验规则：
      - title 非空
      - subject 非空
      - note_type ∈ {exam, postgraduate}
      - exam_freq ∈ {0, 1, 2, 3, 4, 5}
      - body 非空
    """
```

### 5.2 `src/parsers/pdf_parser.py` / `pptx_parser.py` / `docx_parser.py`（Phase 3 占位）

```python
# 示例：pdf_parser.py
def parse_pdf(file_path: Path, chunk_size: int = 500) -> ExternalDocument:
    """
    🔮 Phase 3 — 解析 PDF 文件，提取纯文本并分块。

    Args:
        file_path: PDF 文件路径
        chunk_size: 每个分片的字符数

    Returns:
        ExternalDocument 对象，包含文本分片

    Raises:
        NotImplementedError: Phase 1-2 不实现
    """
    raise NotImplementedError("PDF 解析将在 Phase 3 实现")
```

`pptx_parser.py` 和 `docx_parser.py` 同理，函数名分别为 `parse_pptx` 和 `parse_docx`，签名一致。

### 5.3 `src/indexer.py`（Phase 1 实现）

**职责**：遍历 `data/notes/` 下所有 `.md` 文件，构建倒排索引。**不索引 `data/external/`。**

```python
def build_index(notes_root: Path) -> dict:
    """
    扫描 notes_root 下所有 .md 文件，构建倒排索引。

    Args:
        notes_root: 笔记根目录，默认 data/notes/

    Returns:
        索引字典，结构见 §4.1

    处理流程：
      1. 遍历 notes_root/**/*.md
      2. 对每个文件调用 parse_markdown()
      3. 提取各字段文本，用 jieba 分词
      4. 统计每个词项在每个字段中的词频
      5. 写入 data/index/index.json
    """

def save_index(index: dict, output_path: Path) -> None:
    """将索引持久化为 JSON 文件。"""

def load_index(index_path: Path) -> dict:
    """从 JSON 文件加载索引。"""

def generate_sample_notes(notes_root: Path) -> None:
    """
    空仓启动时生成 5 篇示例笔记：

    1. data/notes/微积分/[示例]极限与连续.md        — note_type: exam,          exam_freq: 5
    2. data/notes/微积分/[示例]中值定理与泰勒展开.md  — note_type: postgraduate,  exam_freq: 4
    3. data/notes/数据结构/[示例]二叉树与遍历.md     — note_type: exam,          exam_freq: 5
    4. data/notes/数据结构/[示例]红黑树与B树.md      — note_type: postgraduate,  exam_freq: 3
    5. data/notes/机器学习导论/[示例]监督学习基础.md  — note_type: exam,          exam_freq: 4

    每篇笔记包含：完整的 YAML Front-matter + 不少于 200 字的正文（含 LaTeX 公式、代码块）。
    """
```

### 5.4 `src/searcher.py`（Phase 1 实现）

**职责**：加载倒排索引，解析用户查询，按权重排序返回结果。

```python
def search(query: str, index: dict, note_type: str | None = None,
           top_k: int = 10, subject: str | list[str] | None = None,
           exclude_tag: str | list[str] | None = None) -> list[dict]:
    """
    关键词检索，按权重排序。

    Args:
        query: 搜索关键词
        index: 倒排索引字典
        note_type: 过滤条件，None=全部, 'exam' 或 'postgraduate'
        top_k: 返回前 K 个结果
        subject: 科目或科目列表，None=全部；多科目之间为“或”关系
        exclude_tag: 排除标签或标签列表，None=不排除；命中任一标签即排除

    Returns:
        [{path, title, subject, chapter, tags, note_type, exam_freq, score}]，按 score 降序

    算法：见 §4.2
    """

def retrieve_for_rag(query: str, top_k: int = 5, include_external: bool = True) -> list[dict]:
    """
    🔮 Phase 3 — 为 RAG 检索上下文。

    Phase 1 行为：打印提示并返回空列表。保留完整类型注解。

    Args:
        query: 用户问题
        top_k: 返回片段数
        include_external: 是否包含外部资料

    Returns:
        [{source_type: 'note'|'external', content, metadata}]
    """
    print("[Phase 3] RAG 检索功能尚未实现")
    return []
```

### 5.5 `src/oracle.py`（Phase 1 占位，Phase 3 实现）

**职责**：教学与校验引擎。Phase 1 仅提供完整函数签名和 docstring。

```python
def teach(question: str, files: list[str] | None = None,
          subject: str | None = None, note_type: str | None = None,
          model: str = "local") -> str:
    """
    🔮 Phase 3 — 教学校验引擎。

    输入：
      - question: 用户问题，如"解释极限的定义"
      - files: 可选的外部文件路径列表
      - subject: 可选的科目过滤
      - note_type: 可选的笔记类型过滤
      - model: LLM 模型选择，"local" 用 Ollama，"api" 用 OpenAI

    处理流程：
      1. 调用 searcher.retrieve_for_rag() 从笔记中召回相关片段
      2. 若用户提供了外部文件，依次调用对应的 parser（PDF/PPTX/DOCX）
         解析并分块，再通过向量检索（或关键词匹配）召回相关外部片段
      3. 差异分析 — 对比笔记内容与外部资料内容：
         - 若笔记与外部资料对同一概念有不同定义/公式，标记为"冲突"
         - 若外部资料提及但笔记未覆盖的考点，标记为"遗漏"
         - 若笔记有但外部资料未提及的（非冲突），保留作为补充视角
      4. 构造 Prompt，明确指令：
         "你是一位大学课程助教。请基于提供的上下文回答学生的问题。
         上下文包含两部分：①学生的个人笔记（可能包含错误或遗漏）；
         ②官方课程资料（PPT/试卷答案/辅导书），视为权威来源。
         若笔记信息与外部资料冲突，请以外部资料为准，并委婉指出笔记可能的缺陷或过时之处。
         若笔记遗漏了外部资料中的重要考点，请提醒学生补充。"
      5. 调用 LLM API（Ollama 本地模型 或 OpenAI API）生成最终回答
      6. 返回带差异提示的教学回答

    Phase 1 行为：
      - 打印 "[Phase 3] 教学功能尚未实现，预计在 Phase 3 提供。"
      - 打印 "输入问题: {question}"
      - 打印 "附件文件: {files}"（如有）
      - 返回占位字符串
      - 不抛出异常
    （提示文案不使用 emoji，避免 Windows GBK 控制台输出时 UnicodeEncodeError）

    Args:
        question: 用户问题
        files: 外部文件路径列表
        subject: 科目过滤
        note_type: 笔记类型过滤
        model: LLM 模型

    Returns:
        教学回答字符串（Phase 1 返回占位信息）
    """
    # Phase 1 占位实现
    ...

def _build_teach_prompt(question: str, note_contexts: list[dict],
                        external_contexts: list[dict]) -> str:
    """
    构造教学 Prompt。

    包含：
      - 系统角色设定（助教）
      - 笔记上下文
      - 外部资料上下文
      - 差异分析指令
      - 输出格式要求
    """
    ...

def _analyze_discrepancies(note_contexts: list[dict],
                           external_contexts: list[dict]) -> list[str]:
    """
    差异分析：对比笔记与外部资料，返回冲突/遗漏清单。

    Phase 1 占位，返回空列表。
    """
    return []
```

### 5.6 `src/rag/__init__.py` + `retriever.py`（Phase 3 占位）

```python
# rag/retriever.py — Phase 3
class VectorRetriever:
    """基于 ChromaDB 的向量检索器。Phase 1 占位。"""
    def __init__(self, collection_name: str = "nju_notes"):
        raise NotImplementedError("Phase 3")

    def index_notes(self, notes: list[Note]) -> None:
        raise NotImplementedError("Phase 3")

    def index_external(self, docs: list[ExternalDocument]) -> None:
        raise NotImplementedError("Phase 3")

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError("Phase 3")
```

### 5.7 `main.py`（Phase 1 实现）

**职责**：CLI 入口，argparse 子命令分发。

```python
# 子命令：
#   python main.py index                  — 构建索引（空仓时先生成示例笔记）
#   python main.py search "关键词"         — 关键词搜索
#       --type exam|postgraduate          — 按笔记类型过滤
#       --top 10                          — 返回结果数
#   python main.py teach "问题"            — 教学校验（Phase 1 占位）
#       --files file1 file2 ...           — 外部文件路径（任意位置临时上传）
#       --subject "科目"                   — 科目过滤
#       --type exam|postgraduate          — 笔记类型过滤
#   python main.py cleanup-cache          — 清空 data/external/ 及 external_manifest.json
#       --dry-run                         — 仅列出将被清理的文件，不实际删除
```

**命令行参数规格**：

| 子命令 | 参数 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| `index` | — | — | — | — | 扫描并构建倒排索引 |
| `search` | `query` | str | 是 | — | 搜索关键词 |
| `search` | `--type` | str | 否 | None | `exam` 或 `postgraduate` |
| `search` | `--top` | int | 否 | 10 | 返回结果数 |
| `teach` | `question` | str | 是 | — | 问题文本 |
| `teach` | `--files` | list[str] | 否 | None | 外部文件路径列表 |
| `teach` | `--subject` | str | 否 | None | 科目过滤 |
| `teach` | `--type` | str | 否 | None | 笔记类型过滤 |
| `cleanup-cache` | — | — | — | — | 清空 `data/external/` 及 `external_manifest.json` |
| `cleanup-cache` | `--dry-run` | flag | 否 | False | 仅列出将被清理的文件，不实际删除 |

---

## 6. 数据流图

### 6.1 Phase 1 — 索引 & 搜索

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ data/notes/  │────▶│  indexer.py      │────▶│ index.json   │
│  *.md 文件   │     │  jieba 分词      │     │ 倒排索引     │
└──────────────┘     │  字段词频统计    │     └──────┬───────┘
                     └──────────────────┘            │
                                                    ▼
                     ┌──────────────────┐     ┌──────────────┐
                     用户输入查询       │────▶│ searcher.py  │
                     "极限 --type exam" │     │ 加载索引     │
                     └──────────────────┘     │ 分词+加权    │
                                              │ 排序+过滤    │
                                              └──────┬───────┘
                                                     ▼
                                              终端输出结果
                                              [1] 极限与连续 (score: 15.3)
                                              [2] ...
```

### 6.2 Phase 3 — 教学校验（远期完整流程）

```
用户在 GUI 教学面板（或 CLI teach 命令）中:
  1. 输入问题文本，如"解释极限的定义"
  2. 点击"上传附件"选择本地文件（如 课件.pdf、2020真题.pdf）
  3. 发送请求
│
├─ 1. searcher.retrieve_for_rag("极限的定义", top_k=5)
│     └─ 从 index.json 召回相关笔记片段
│        返回: [{source_type: 'note', content: '极限的ε-δ定义是...', metadata: {...}}]
│
├─ 2. 解析用户本次上传的临时文件
│     └─ 根据扩展名分发到对应 parser（pdf_parser / pptx_parser / docx_parser）
│     └─ 文件存入 data/external/ 缓存（按 session_id 隔离，.gitignore 已排除）
│         返回: ExternalDocument(chunks=['第1章 极限...', '定义2.1...'])
│     └─ retriever.query("极限的定义", top_k=3)
│         返回: [{source_type: 'external', content: '定义：设f在x₀附近有定义...', ...}]
│
├─ 3. 差异分析 (_analyze_discrepancies)
│     │  笔记: "极限的ε-δ定义为 ∀ε>0, ∃δ>0, 当 |x-x₀|<ε 时, |f(x)-L|<δ"
│     │  课件: "∀ε>0, ∃δ>0, 当 0<|x-x₀|<δ 时, |f(x)-L|<ε"
│     └─ 检测到: 笔记写反了 ε 和 δ 的位置！
│        返回: ["笔记中 ε-δ 定义的条件顺序有误，应为 |x-x₀|<δ 时 |f(x)-L|<ε"]
│
├─ 4. 构造 Prompt (_build_teach_prompt)
│     └─ 包含: 系统角色 + 笔记上下文 + 外部资料上下文 + 差异指令
│
├─ 5. 调用 LLM → 生成回答
│     └─ "根据课件，极限的严格定义为... 我注意到你的笔记中ε和δ的位置写反了，
│         这可能是手误，正确的表述应该是..."
│
└─ 6. 返回完整 TeachSession
      └─ {question, recalled_notes, external_chunks, final_answer, discrepancies}
```

---

## 7. 开发阶段划分

### 7.1 Phase 1 — CLI 核心（当前必须完成）

**目标**：可用的命令行搜索工具 + 远期模块的完整骨架

**交付物清单**：

| # | 任务 | 产出 | 优先级 |
|---|------|------|--------|
| 1.1 | 创建完整目录结构 | 所有目录和 `__init__.py` | P0 |
| 1.2 | Git 初始化 | `git init` + `.gitignore` + 初始 commit | P0 |
| 1.3 | 实现 `src/parsers/markdown_parser.py` | 解析 .md + 校验 Note | P0 |
| 1.4 | 实现 `src/indexer.py` | 倒排索引构建 + 示例笔记生成 | P0 |
| 1.5 | 实现 `src/searcher.py` | 关键词检索 + 加权排序 + `--type` 过滤 | P0 |
| 1.6 | 实现 `main.py` | argparse 子命令（index/search/teach/cleanup-cache） | P0 |
| 1.7 | 创建远期模块占位文件 | parsers/pdf|pptx|docx_parser.py, oracle.py, rag/ | P0 |
| 1.8 | 编写 `README.md` | 项目说明 + Phase 功能边界表格 | P0 |
| 1.9 | 编写 `requirements.txt` | 依赖清单，按 Phase 分组注释 | P0 |
| 1.10 | 编写测试 `tests/` | test_markdown_parser, test_indexer, test_searcher | P1 |

**验收标准**：

```bash
# 空仓启动
python main.py index
# 期望：生成 5 篇示例笔记 + 构建 index.json

# 搜索
python main.py search "极限" --type postgraduate
# 期望：返回匹配结果，按权重排序，仅 postgraduate 类型

python main.py search "二叉树" --type exam
# 期望：仅返回 exam 类型的笔记

# 远期占位（不报错）—— 模拟用户从本地任意路径上传文件
python main.py teach "解释极限的定义" --files "C:\Users\25153\Desktop\课件.pdf"
# 期望：打印 "[Phase 3] 教学功能尚未实现，预计在 Phase 3 提供。" 并正常退出

# 帮助信息
python main.py --help
# 期望：显示 index / search / teach / cleanup-cache 四个子命令及参数说明
```

### 7.2 Phase 2 — GUI（中期）

**目标**：PyQt6 图形界面，支持笔记与外部文件的浏览、搜索、导入管理。**不内置编辑器**（用户用 MarkText 等外部编辑器）。

**功能范围**：

- 笔记列表浏览（按科目树形展示）
- 全文搜索面板（关键词 + 可搜索、可按当前结果全选/全不选的多选科目/标签筛选 + 类型过滤 + 结果高亮）
- 笔记内容预览（只读渲染，支持离线 LaTeX 公式与带边框的等宽字体代码块）
- **教学对话面板**（聊天式交互，用户输入问题 + 临时上传附件 → 发送）
- "上传附件"按钮：支持拖拽或文件选择对话框选取外部资料（PDF/PPTX/DOCX/TXT），每次请求临时上传，不上传到固定文件夹
- 一键重建索引
- 搜索历史记录
- 设置入口（已实现）：位于左侧栏底部，紧接“重建索引”按钮下方；使用相同按钮样式与齿轮图标，打开设置中心

**数据库扩展（已实现）**：使用 `sqlite3` 管理笔记目录和应用状态，不替换现有 `index.json` 全文索引。

- `notes` 表保存 `path`（主键）、标题、科目、章节、标签、笔记类型、考频、文件修改时间和内容哈希；不保存正文
- `search_history` 表保存查询词、多选科目/类型/多选排除标签筛选条件和搜索时间，替代 QSettings 中的 GUI 历史存储
- 重建索引时在同一事务中增量写入或删除目录记录；数据库丢失或损坏时，笔记目录可通过扫描 `data/notes/` 重建，搜索历史允许重置
- GUI 启动时先显示居中的主题化启动页，在后台读取 `index.json` 与搜索历史，并以深绿色进度条及右下方加载项反馈进度；完成后再创建正式窗口
- GUI 启动不执行 SQLite 笔记目录全量同步或内容哈希。“仅手动重建”策略跳过目录扫描；“启动时检查文件变更并提示重建”策略只在后台比较 Markdown 路径集合和修改时间。全文扫描、内容哈希和 SQLite 目录同步仅由主动重建索引触发
- 外部编辑器仍直接修改 Markdown；GUI 不直接编辑数据库中的笔记字段，避免数据库与文件内容不一致

### 7.2.1 设置中心（Phase 2 增量，已实现）

**目标**：为单机使用提供可恢复、可解释的个性化配置。设置只影响 GUI 行为、检索偏好和本地应用状态；Markdown 正文与 YAML Front-matter 仍是笔记的唯一真源，不通过设置页面编辑。

**入口与交互**：

- 左侧栏底部的“设置”按钮固定放在“重建索引”正下方，沿用相同的按钮尺寸、边框和悬停样式，图标使用齿轮
- 设置中心采用独立页面或模态对话框；一级分类在左侧，右侧展示设置项、当前值、简短说明与“恢复默认”操作
- 设置修改即时生效；涉及索引、数据库清理、缓存删除或 API 连通性检查的操作必须二次确认，并明确说明影响范围

**设置层次结构**：

```
设置
├── 外观与阅读
│   ├── 界面配色：浅色（默认）/ 深色 / 跟随系统；深色模式按设计令牌完整反转，应用图标除外
│   ├── 界面缩放：90% / 100%（默认）/ 110% / 125%
│   ├── 笔记正文字号：小 / 标准（默认）/ 大
│   ├── 代码块字号：小 / 标准（默认）/ 大
│   ├── 正文字体与代码字体：使用系统推荐字体（默认）或从预设字体中选择
│   └── 启动位置：打开笔记库（默认）/ 打开全文搜索；是否恢复上次阅读的笔记与滚动位置
├── 搜索与笔记库
│   ├── 搜索行为：输入后按 Enter 搜索（默认）；预留“输入即搜索”开关
│   └── 示例笔记：首次启动自动生成（默认）；显示/隐藏带“示例”标签的笔记
├── 文件与索引
│   ├── 笔记目录：显示当前 data/notes 路径；后续可选择其他本地目录并要求重建索引
│   ├── 索引策略：仅手动重建（默认）/ 启动时检查文件变更并提示重建
│   ├── 外部编辑器：使用系统默认程序（默认）/ 指定可执行文件；显示当前检测结果
│   ├── 数据库与缓存：显示 SQLite 路径、笔记数量和上次同步时间
│   └── 维护操作：重建索引、清理外部资料缓存、重置全部应用设置
├── 隐私与数据
│   ├── 搜索历史持久化：启用（默认）/ 停用；保留条数（默认 20）
│   ├── 外部资料缓存：不保留（默认）/ 会话结束后保留至手动清理
│   ├── 本地数据导出：导出设置与搜索历史；不导出 Markdown 正文
│   └── 本地数据说明：明确 notes、index.json、SQLite 与外部资料缓存各自用途及可重建性
└── 教学与模型（Phase 3 预留，当前禁用并标注“即将推出”）
    ├── 模型提供方：Ollama（本地）/ OpenAI 兼容 API
    ├── 模型与连接：模型名称、服务地址、超时、连通性测试
    ├── 检索策略：返回片段数、外部资料优先级、是否引用示例笔记
    ├── 上传策略：允许的文件类型、单文件大小上限、会话结束后的清理策略
    └── 凭据管理：API Key 仅写入系统凭据存储或环境变量，不写入 SQLite、索引或 Git
```

**设置项说明**：

| 分类 | 设置项 | 默认值 | 作用与影响范围 |
|------|--------|--------|----------------|
| 外观与阅读 | 界面配色 | 浅色 | 在浅色与深色主题之间切换；选择“跟随系统”时使用系统当前颜色主题，并在系统主题变化后即时更新。深色模式必须按语义完整反转 GUI 的颜色：黑色文字、图标、滑块变为白色；白色背景、滑条变为黑色；深绿强调色变为浅绿，浅绿选中/提示色变为深绿。反转覆盖原生标题栏与窗口控制按钮、页面背景、列表、弹窗、Markdown 预览、代码块、公式容器、复选框、滚动条及除应用图标外的全部图标；应用图标保持原设计和原颜色，不参与反转。 |
| 外观与阅读 | 界面缩放 | 100% | 统一调整侧栏、控件、图标、间距与常规界面文字的比例，便于高分辨率屏幕或视力需求下使用；不改变笔记 Markdown 源文件。 |
| 外观与阅读 | 笔记正文字号 | 标准 | 仅调整预览区域中普通段落、标题、列表和表格的字号，保留相对层级；不影响外部编辑器中的笔记显示。 |
| 外观与阅读 | 代码块字号 | 标准 | 独立调整等宽代码块的字号，避免代码与正文必须使用同一大小；边框、字体族和代码内容保持不变。 |
| 外观与阅读 | 正文字体与代码字体 | 系统推荐字体 | 从经过测试的预设字体中分别选择正文与等宽代码字体；缺失字体自动回退到系统推荐字体，避免中文或数学字符缺字。 |
| 外观与阅读 | 启动位置与阅读恢复 | 笔记库；不恢复 | 决定启动时首先显示笔记库还是搜索页，并可选择恢复上次打开的笔记和滚动位置；只保存路径与位置，不复制笔记正文。 |
| 搜索与笔记库 | 搜索行为 | 按 Enter 搜索 | 控制全文搜索何时执行。默认避免输入过程反复查询；“输入即搜索”作为后续选项需带短暂防抖，以免索引较大时影响界面响应。 |
| 搜索与笔记库 | 示例笔记 | 首次启动自动生成并显示 | 控制空笔记库是否自动生成内置示例，以及是否在笔记库中显示带 `示例` 标签的笔记。它不改变搜索页中用户临时选择的标签排除条件。 |
| 文件与索引 | 笔记目录 | `data/notes` | 展示当前索引来源。后续允许切换到其他本地目录；确认切换后必须重建索引和 SQLite 目录，原 Markdown 文件不移动、不修改。 |
| 文件与索引 | 索引策略 | 仅手动重建 | 决定是否在启动时检测 Markdown 文件变更并提示用户重建。即使启用检测，也不自动改写笔记，只提示或等待用户确认。 |
| 文件与索引 | 外部编辑器 | 系统默认程序 | 使用系统对 `.md` 文件的关联程序，或由用户指定可执行文件。设置页展示检测结果，用于处理没有关联程序或 Electron 编辑器启动环境异常的情况。 |
| 文件与索引 | 数据库与缓存状态 | 只读信息 | 显示 SQLite 路径、当前笔记数量、上次同步时间与外部资料缓存状态，帮助判断索引是否需要重建；不直接编辑数据库字段。 |
| 文件与索引 | 维护操作 | 按需执行 | 提供重建索引、清理外部资料缓存和重置全部应用设置。每项操作需说明影响并二次确认；搜索历史继续只在搜索面板中清空，避免重复入口。 |
| 隐私与数据 | 搜索历史持久化与保留条数 | 启用；20 条 | 控制搜索记录是否写入 SQLite 及最多保留多少条；关闭后不再新增持久记录，不改变已存在记录。清空历史仍使用现有搜索面板按钮。 |
| 隐私与数据 | 外部资料缓存 | 不保留 | 决定 Phase 3 临时上传资料在会话结束后是否保留至手动清理。默认不保留，以降低本地隐私暴露和磁盘占用。 |
| 隐私与数据 | 本地数据导出 | 按需导出 | 仅导出设置与搜索历史，方便迁移应用偏好；不导出 `data/notes` 中的 Markdown 正文，笔记仍由用户独立管理。 |
| 隐私与数据 | 本地数据说明 | 只读说明 | 解释 `data/notes`、`index.json`、SQLite 与外部缓存的职责、位置和可重建性，避免用户误删后不了解影响。 |
| 教学与模型（Phase 3） | 模型提供方 | 未启用 | 选择 Ollama 本地模型或 OpenAI 兼容 API，决定后续教学对话的调用方式；Phase 2 只显示禁用占位。 |
| 教学与模型（Phase 3） | 模型与连接 | 未启用 | 配置模型名称、服务地址和超时，并提供不发送笔记内容的连通性测试，便于先验证服务可用性。 |
| 教学与模型（Phase 3） | 检索策略 | 未启用 | 调整每次教学请求取回的片段数量、外部资料优先级及是否引用示例笔记，影响回答上下文而不修改原始笔记。 |
| 教学与模型（Phase 3） | 上传策略 | 未启用 | 限制允许的文件类型、单文件大小和会话结束后的清理方式，防止意外上传或长期保留敏感资料。 |
| 教学与模型（Phase 3） | 凭据管理 | 未启用 | API Key 只能从系统凭据存储或环境变量读取，绝不写入 SQLite、索引、导出文件或 Git；设置页仅显示是否已配置。 |

**实施边界与存储**：

- Phase 2 已实现“外观与阅读”“搜索与笔记库”“文件与索引”“隐私与数据”的全部设置项；目录切换只改变索引来源并重建索引，不迁移或改写原 Markdown 文件
- 在 `notemanager.db` 中增加独立的 `app_settings` 表保存非敏感键值和版本号；设置缺失时回退到内置默认值，数据库重建后不影响 Markdown 笔记
- 搜索历史开关、历史条数、搜索行为和示例笔记显示策略只影响 GUI 初始状态和历史记录，不改变 CLI 的默认行为；默认类型和标签排除继续由现有搜索界面按次选择
- Phase 3 的模型/网络设置与 API Key 分层保存：普通连接偏好可本地持久化，密钥必须使用系统凭据存储或环境变量；无可用模型时教学面板保持占位状态

### 7.3 Phase 3 — 教学校验引擎（远期）

**目标**：实现 `oracle` 模块的完整教学与校验功能。

**任务分解**：

| # | 任务 | 依赖 |
|---|------|------|
| 3.1 | 实现 `pdf_parser.py` / `pptx_parser.py` / `docx_parser.py` — 解析上传的临时文件，返回结构化文本分片 | pypdf, python-pptx, docx2txt |
| 3.2 | 实现 `rag/retriever.py` — ChromaDB 向量存储与检索（笔记 + 临时上传的外部资料分别建索引，会话结束后外部资料索引可清除） | chromadb |
| 3.3 | 实现 `oracle.py` — 差异分析 + Prompt 构造 + LLM 调用 | ollama/openai SDK |
| 3.4 | 更新 `main.py` teach 子命令 — 连接真实逻辑，支持 `--files` 传入临时文件路径 | 3.1-3.3 |
| 3.5 | 更新 GUI — 教学面板完整功能（聊天式交互 + 文件上传 + 差异高亮渲染） | 3.1-3.4 |

---

## 8. Git 版本管理

### 8.1 初始化

```bash
cd NoteManager
git init
```

### 8.2 `.gitignore` 规则

以下内容**不纳入版本控制**：

| 忽略项 | 原因 |
|--------|------|
| `data/notes/` | 笔记由用户自行管理，目录位置固定但内容不纳入版本控制 |
| `data/index/index.json` | 索引文件由 `index` 命令重建，无需追踪 |
| `data/index/notemanager.db*` | SQLite 本地目录、搜索历史及 WAL 辅助文件，属于用户运行数据 |
| `data/index/external_manifest.json` | 上传缓存清单，每次会话变化 |
| `data/external/**`（除 `.gitkeep`） | 外部资料为临时上传缓存，不持久化在仓库中 |
| `__pycache__/`、`*.pyc` | Python 编译产物 |
| `.venv/`、`venv/` | 虚拟环境 |
| `*.egg-info/`、`dist/`、`build/` | 打包产物 |
| `.DS_Store`、`Thumbs.db` | OS 元数据文件 |

### 8.3 纳入追踪的内容

仅代码和项目文档纳入版本控制，笔记与数据文件由用户自行管理：

| 追踪项 | 说明 |
|--------|------|
| 所有 `src/**/*.py` | 源代码 |
| `tests/` | 测试代码 |
| `README.md`、`plan.md`、`requirements.txt` | 项目文档 |
| `.gitignore` | Git 忽略规则（确保团队成员使用一致的忽略策略） |

### 8.4 Commit 规范

- 每完成一个 Phase 1 子任务后立即 commit
- Commit message 格式：`<type>: <简短描述>`
  - `feat:` — 新功能（如 `feat: 实现倒排索引构建`）
  - `fix:` — 修复
  - `stub:` — 添加占位文件（如 `stub: 创建 Phase 3 parser 占位`）
  - `docs:` — 文档更新
  - `test:` — 测试
- 每次 commit 前确保代码可运行（至少 `python main.py --help` 不报错）

---

## 9. 非功能性需求

| 需求 | 说明 |
|------|------|
| **跨平台** | 代码兼容 Windows 10/11，所有文件编码 UTF-8 |
| **中文路径** | 所有路径操作使用 `pathlib.Path`，确保含中文路径正常工作 |
| **Python 版本** | ≥ 3.10（使用 `str | None` 联合类型语法） |
| **错误处理** | 解析失败不中断索引构建；记录错误但继续处理剩余文件 |
| **幂等性** | `index` 命令可重复执行，覆盖旧索引 |
| **版本控制** | 全程 Git 管理，仅代码与项目文档纳入追踪；笔记、索引、缓存均不追踪 |

---

## 10. Coding Agent 执行指南

Agent 在按本 plan.md 编写代码时，请遵循以下顺序：

1. **先建骨架**：创建目录结构和所有 `__init__.py`
2. **Git 初始化**：`git init` + 创建 `.gitignore` + 初始 commit
3. **自底向上**：parsers → indexer → searcher → oracle → main.py
4. **每个模块写完后立即写对应的 test_**，确保可验证
5. **每完成一个子任务立即 commit**，遵循 §8.4 的 commit 规范
6. **示例笔记内容需丰富**：包含 LaTeX 公式（行内 `$...$`；块级公式 `$$` 独占行、公式内容分行，兼容 MarkText 渲染）、代码块（```python```）、列表、表格
7. **异常处理**：所有文件 I/O 和解析操作包裹 try-except，不因单个文件错误中断批量处理
8. **类型注解**：所有公开函数必须包含完整类型注解
9. **docstring**：使用 Google 风格 docstring（Args/Returns/Raises）
10. **占位模块**：远期模块仅需函数签名 + `raise NotImplementedError("消息")`，不需伪实现
