# NoteManager — Git 使用指南

> 本文基于项目的 `.gitignore` 配置和 Commit 规范撰写，面向日常开发场景。

## 1. Git 追踪策略

本项目采用**代码与数据分离**的策略：

```
✅ 纳入 Git 追踪                 ❌ 不纳入 Git 追踪
─────────────────────────       ─────────────────────────
src/**/*.py    源代码            data/notes/       笔记内容
tests/         测试代码           data/index/      索引文件
README.md      项目文档           data/external/   上传缓存
plan.md        开发规划           __pycache__/     Python 编译
.gitignore     忽略规则           .venv/          虚拟环境
requirements.txt 依赖清单
```

> 💡 **笔记为什么不在 Git 里？**
> 笔记目录 `data/notes/` 位置固定，但内容由用户自行管理。你可以在其他地方（如 OneDrive、坚果云）单独备份笔记；项目代码只需 `git clone` 即可在任何机器上运行。

---

## 2. 日常开发流程

### 2.1 开始工作前

```bash
# 确认工作区干净
git status

# 如果有未提交的修改，先决定：提交还是暂存
```

### 2.2 编写代码 → 一个子任务 → 一次 commit

本项目的开发粒度是 **一个模块/子任务 = 一次 commit**（参考 `plan.md` §7.1 交付物清单）。

```bash
# 示例：实现 markdown_parser.py（任务 1.3）
# 1. 编写 src/parsers/markdown_parser.py
# 2. 编写 tests/test_markdown_parser.py
# 3. 运行测试确认无误
# 4. 提交
git add src/parsers/markdown_parser.py tests/test_markdown_parser.py
git commit -m "feat: 实现 Markdown 解析器（含 Front-matter 提取与 Note 校验）"
```

### 2.3 查看改动历史

```bash
git log --oneline                    # 简洁列表
git log --oneline --graph --all      # 可视化分支
git diff HEAD~1                      # 查看最近一次改了什么
```

### 2.4 回滚某个文件

```bash
# 回滚到最近一次 commit 的状态
git checkout -- src/searcher.py

# 回滚到两次 commit 前的状态
git checkout HEAD~2 -- src/searcher.py
```

---

## 3. Commit 规范

格式：**`<type>: <简短描述>`**

| Type | 用途 | 示例 |
|------|------|------|
| `feat:` | 新功能 | `feat: 实现倒排索引构建` |
| `fix:` | 修复 bug | `fix: 修复中文分词空字符串崩溃` |
| `stub:` | 添加占位文件 | `stub: 创建 Phase 3 parser 占位` |
| `docs:` | 文档更新 | `docs: 补充搜索算法说明` |
| `test:` | 测试相关 | `test: 添加 search 过滤测试` |
| `chore:` | 杂项/配置 | `chore: 更新 .gitignore 规则` |

规则：
- **每次 commit 前确保 `python main.py --help` 不报错**（这是最低可用性检查）
- 描述用中文，尽量说清"做了什么"而非"怎么做的"
- 一次 commit 只做一件事（不要同时修 bug 和加功能）

---

## 4. 分支策略（可选，建议）

当前项目单人开发，你可以选择两种方式：

### 方案 A：单分支，线性开发（简单）

```
master（或 main）
  │
  ├─ init: 项目骨架         ← 初始 commit
  ├─ feat: markdown_parser
  ├─ feat: indexer
  ├─ feat: searcher
  ├─ feat: main.py 入口
  ├─ feat: GUI Phase 2
  └─ ...
```

适用场景：你在本地开发，不需要协作分支。

### 方案 B：按 Phase 分支（推荐，更安全）

```bash
# 在 Phase 1 完结时打 tag
git tag v0.1-phase1

# Phase 2 在独立分支上开发
git checkout -b phase2-gui
# ... 开发 GUI ...
git checkout master
git merge phase2-gui
git tag v0.2-phase2
git branch -d phase2-gui

# Phase 3 同理
git checkout -b phase3-oracle
# ... 开发 ...
```

> 💡 分支方式的好处：如果 Phase 2 GUI 写到一半想放弃换方案，直接 `git checkout master` 切回去，Phase 1 的代码完好无损。

---

## 5. 常见场景速查

### 5.1 我想新建一篇笔记

```bash
# 直接用 MarkText/Typora/VS Code 在 data/notes/科目名/ 下创建 .md 文件
# 然后重建索引
python main.py index
```

笔记不在 Git 里，所以不需要 `git add`。

### 5.2 我改了代码但改坏了，想撤销

```bash
# 丢弃工作区所有未提交的修改（回到最近一次 commit 的状态）
git checkout -- .
```

### 5.3 我提交了但提交信息写错了

```bash
# 修改最近一次 commit 的 message（仅限尚未 push 时）
git commit --amend -m "fix: 正确的新提交信息"
```

### 5.4 我忘了在某个 commit 里加一个文件

```bash
# 把漏掉的文件加入最近一次 commit
git add 漏掉的文件.py
git commit --amend --no-edit
```

### 5.5 我想看某个文件的历史

```bash
git log --oneline -- path/to/file.py    # 该文件的提交历史
git log -p -- path/to/file.py           # 每次提交的详细 diff
```

---

## 6. 关于外部资料缓存

`data/external/` 目录存放教学会话中临时上传的文件副本，**不在 Git 追踪范围内**。清理方式：

```bash
# CLI 清理（本项目自带）
python main.py cleanup-cache

# 预览模式（先看再删）
python main.py cleanup-cache --dry-run

# 手动清理
rm -rf data/external/*
```

---

## 7. 新手最简流程

如果你对 Git 不熟，开发时只需记住三条命令：

```bash
# 1. 完成一个功能模块后
git add .
git commit -m "feat: 描述你做了什么"

# 2. 想看改过什么
git status
git diff

# 3. 改坏了想回去
git checkout -- .
```

就这三条，足够支撑整个 Phase 1 开发。分支和 tag 等高级操作用到了再查。
