# NJUCSKeeper

本地化计算机课程知识中台 — 笔记管理与 AI 教学校验。

## 功能边界

| 功能 | Phase 1 (CLI) | Phase 2 (GUI) | Phase 3 (AI) |
|------|:---:|:---:|:---:|
| Markdown 笔记管理 | ✅ | ✅ | ✅ |
| 关键词全文搜索 | ✅ | ✅ | ✅ |
| 双轨制过滤（期末/考研） | ✅ | ✅ | ✅ |
| 按科目过滤 | ✅ | ✅ | ✅ |
| 空仓示例笔记生成 | ✅ | ✅ | ✅ |
| 图形界面浏览/搜索 | — | ✅ | ✅ |
| 外部资料拖拽导入 | — | 预留 | 🔮 |
| PDF/PPTX/DOCX 解析 | — | — | 🔮 |
| AI 教学校验 | — | — | 🔮 |
| 向量检索（RAG） | — | — | 🔮 |

> ✅ 已实现 &nbsp;&nbsp; 🔮 设计蓝图，远期实现

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 构建索引（首次运行自动生成示例笔记）
python main.py index

# 搜索笔记
python main.py search "极限"

# 按科目和笔记类型过滤
python main.py search "应用层" --subject "计算机网络" --type exam

# 启动图形界面
python main.py gui
```

图形界面支持按科目浏览、全文搜索与高亮、只读 Markdown 预览、搜索历史和一键重建索引。教学对话与附件上传仅保留界面位置，将在 Phase 3 接入。

## 远期能力预览

当您上传往年试卷后，系统可对比您的笔记与试卷答案，指出笔记中遗漏的考点或过时表述：

```bash
# Phase 3 功能（当前为占位提示）
python main.py teach "解释极限的定义" --files "课件.pdf"
```

## 项目结构

```
├── main.py                CLI 入口
├── data/notes/            笔记目录（按科目分类）
├── data/external/         外部资料缓存
├── data/index/            倒排索引
├── src/parsers/           文件解析器
├── src/rag/               向量检索模块
└── tests/                 单元测试
```

## 许可

个人学习项目。
