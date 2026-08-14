"""倒排索引构建模块。

遍历 data/notes/ 下所有 .md 文件，构建关键词倒排索引。
不索引 data/external/ 中的外部资料。
"""

import json
import sys
from pathlib import Path
from typing import Any

import jieba

from src.parsers.markdown_parser import Note, parse_markdown

# 索引的字段名与正文分词字段
INDEXED_FIELDS = ("title", "subject", "chapter", "tags", "body")


def _tokenize(text: str) -> list[str]:
    """对文本进行 jieba 分词，返回去除空白与重复的词项列表。

    Args:
        text: 待分词文本

    Returns:
        词项列表（保序去重）
    """
    if not text:
        return []
    tokens = [t.strip() for t in jieba.cut_for_search(text) if t.strip()]
    # 保序去重
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _field_frequencies(note: Note) -> dict[str, dict[str, int]]:
    """统计 Note 各字段的词频。

    Args:
        note: 已解析的笔记

    Returns:
        {词项: {字段名: 词频}}，如 {"极限": {"title": 1, "body": 12}}
    """
    field_texts = {
        "title": note.title,
        "subject": note.subject,
        "chapter": note.chapter,
        "tags": " ".join(note.tags),
        "body": note.body,
    }
    term_fields: dict[str, dict[str, int]] = {}
    for field, text in field_texts.items():
        for token in _tokenize(text):
            term_fields.setdefault(token, {}).setdefault(field, 0)
            term_fields[token][field] += 1
    return term_fields


def build_index(notes_root: Path, base_dir: Path | None = None) -> dict:
    """扫描 notes_root 下所有 .md 文件，构建倒排索引。

    Args:
        notes_root: 笔记根目录，默认 data/notes/
        base_dir: 索引键的相对基准目录，默认取 notes_root 的上一级。
                  传入项目根目录时索引键形如 data/notes/微积分/xx.md

    Returns:
        索引字典，结构见 plan.md §4.1：
        {
            "documents": {相对路径: {title, subject, chapter, tags, note_type, exam_freq}},
            "inverted_index": {词项: {相对路径: {字段: 词频}}},
        }

    处理流程：
      1. 遍历 notes_root/**/*.md
      2. 对每个文件调用 parse_markdown()
      3. 提取各字段文本，用 jieba 分词
      4. 统计每个词项在每个字段中的词频
      5. 写入 data/index/index.json
    """
    notes_root = Path(notes_root)
    if not notes_root.exists():
        raise FileNotFoundError(f"笔记目录不存在: {notes_root}")
    base_dir = Path(base_dir) if base_dir else notes_root.parent

    documents: dict[str, dict[str, Any]] = {}
    inverted_index: dict[str, dict[str, dict[str, int]]] = {}

    for md_file in sorted(notes_root.rglob("*.md")):
        try:
            note = parse_markdown(md_file)
        except (ValueError, FileNotFoundError, OSError) as e:
            print(f"[跳过] 无法解析的笔记: {md_file} — {e}", file=sys.stderr)
            continue

        # 索引键使用相对 base_dir 的路径，统一为正斜杠
        rel_path = str(md_file.relative_to(base_dir)).replace("\\", "/")
        documents[rel_path] = {
            "title": note.title,
            "subject": note.subject,
            "chapter": note.chapter,
            "tags": note.tags,
            "note_type": note.note_type,
            "exam_freq": note.exam_freq,
        }

        for term, fields in _field_frequencies(note).items():
            inverted_index.setdefault(term, {})[rel_path] = fields

    return {"documents": documents, "inverted_index": inverted_index}


def save_index(index: dict, output_path: Path) -> None:
    """将索引持久化为 JSON 文件。

    Args:
        index: 索引字典
        output_path: 输出文件路径（如 data/index/index.json）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def load_index(index_path: Path) -> dict:
    """从 JSON 文件加载索引。

    Args:
        index_path: 索引文件路径

    Returns:
        索引字典

    Raises:
        FileNotFoundError: 索引文件不存在
    """
    index_path = Path(index_path)
    if not index_path.exists():
        raise FileNotFoundError(f"索引文件不存在: {index_path}，请先运行 python main.py index")
    with index_path.open(encoding="utf-8") as f:
        return json.load(f)


def generate_sample_notes(notes_root: Path) -> None:
    """空仓启动时生成 5 篇示例笔记。

    每篇笔记包含完整的 YAML Front-matter 与不少于 200 字的正文
    （含 LaTeX 公式、代码块）。已存在的文件不会被覆盖。

    Args:
        notes_root: 笔记根目录，默认 data/notes/
    """
    notes_root = Path(notes_root)
    samples: dict[str, str] = {
        "微积分/[示例]极限与连续.md": _SAMPLE_CALCULUS_EXAM,
        "微积分/[示例]中值定理与泰勒展开.md": _SAMPLE_CALCULUS_POSTGRAD,
        "数据结构/[示例]二叉树与遍历.md": _SAMPLE_DS_EXAM,
        "数据结构/[示例]红黑树与B树.md": _SAMPLE_DS_POSTGRAD,
        "机器学习导论/[示例]监督学习基础.md": _SAMPLE_ML_EXAM,
    }
    for rel, content in samples.items():
        target = notes_root / rel
        if target.exists():
            print(f"[跳过] 已存在: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"[生成] 示例笔记: {target}")


# ======================= 示例笔记内容 =======================

_SAMPLE_CALCULUS_EXAM = """---
title: "极限与连续"
subject: "微积分"
chapter: "第一章 极限与连续"
tags: ["极限", "ε-δ定义", "连续函数", "洛必达"]
note_type: "exam"
exam_freq: 5
---

# 极限与连续（期末版）

## 1. 极限的定义

数列极限：$\\lim_{n\\to\\infty} a_n = A$ 表示 $\\forall \\varepsilon > 0, \\exists N > 0$，当 $n > N$ 时，$|a_n - A| < \\varepsilon$。

函数极限的 ε-δ 定义：$\\forall \\varepsilon > 0, \\exists \\delta > 0$，当 $0 < |x - x_0| < \\delta$ 时，$|f(x) - A| < \\varepsilon$。

> ⚠️ 易错点：ε 先取定，δ 由 ε 决定；去心邻域 $0 < |x-x_0|$ 不能丢掉。

## 2. 求极限常用方法

| 方法 | 适用场景 |
|------|----------|
| 等价无穷小代换 | $x \\to 0$ 时 $\\sin x \\sim x$，$1-\\cos x \\sim x^2/2$ |
| 洛必达法则 | $\\frac{0}{0}$ 或 $\\frac{\\infty}{\\infty}$ 型 |
| 夹逼准则 | 求 $\\lim_{n\\to\\infty} \\frac{n!}{n^n}$ 类问题 |
| 重要极限 | $\\lim_{x\\to 0}\\frac{\\sin x}{x}=1$，$\\lim_{x\\to\\infty}(1+\\frac1x)^x=e$ |

## 3. 连续与间断点

- 第一类间断点：可去间断点、跳跃间断点
- 第二类间断点：无穷间断点、振荡间断点

例题：判断 $f(x)=\\frac{\\sin x}{x}$ 在 $x=0$ 处的间断点类型。
解：$\\lim_{x\\to0}f(x)=1$ 存在但 $f(0)$ 无定义，故为可去间断点。

```python
# 用 Python 数值验证重要极限
import math
for n in [10, 100, 1000, 10000]:
    print(n, (1 + 1/n) ** n)  # 趋近于 e
```
"""

_SAMPLE_CALCULUS_POSTGRAD = """---
title: "中值定理与泰勒展开"
subject: "微积分"
chapter: "第三章 中值定理与导数应用"
tags: ["罗尔定理", "拉格朗日", "柯西中值", "泰勒展开", "考研"]
note_type: "postgraduate"
exam_freq: 4
---

# 中值定理与泰勒展开（考研版）

## 1. 三大中值定理的联系

1. **罗尔定理**：$f$ 在 $[a,b]$ 连续、$(a,b)$ 可导且 $f(a)=f(b)$，则 $\\exists \\xi \\in (a,b)$ 使 $f'(\\xi)=0$。
2. **拉格朗日中值定理**：$\\exists \\xi \\in (a,b)$ 使 $f'(\\xi)=\\frac{f(b)-f(a)}{b-a}$。罗尔是 $f(a)=f(b)$ 的特例。
3. **柯西中值定理**：$\\frac{f(b)-f(a)}{g(b)-g(a)}=\\frac{f'(\\xi)}{g'(\\xi)}$，拉格朗日是 $g(x)=x$ 的特例。

> 考研常考点：构造辅助函数。如证 $\\exists \\xi$ 使 $f'(\\xi)+f(\\xi)=0$，构造 $F(x)=e^x f(x)$ 后用罗尔定理。

## 2. 泰勒展开（带拉格朗日余项）

$$
f(x)=\\sum_{k=0}^{n}\\frac{f^{(k)}(x_0)}{k!}(x-x_0)^k + \\frac{f^{(n+1)}(\\xi)}{(n+1)!}(x-x_0)^{n+1}
$$

常用麦克劳林展开：

$$
e^x = 1 + x + \\frac{x^2}{2!} + \\cdots + o(x^n)
$$

$$
\\sin x = x - \\frac{x^3}{3!} + \\frac{x^5}{5!} - \\cdots + o(x^{2n+1})
$$

典型应用：求极限 $\\lim_{x\\to 0}\\frac{\\tan x - x}{x^3}$。由 $\\tan x = x + \\frac{x^3}{3} + o(x^3)$，原极限 $= \\frac{1}{3}$。用泰勒展开求极限比洛必达法则更直接，是考研高频考点。

## 3. 综合例题

设 $f$ 在 $[0,1]$ 二阶可导，$f(0)=f(1)=0$，$\\max f(x)=2$。证明 $\\exists \\xi$ 使 $f''(\\xi) \\le -16$。

思路：设 $f(x_0)=2$，在 $[0,x_0]$ 与 $[x_0,1]$ 上分别用拉格朗日定理，再用一次泰勒展开于 $x_0$ 处即可。

```python
# 符号验证泰勒展开
from sympy import symbols, series, sin
x = symbols('x')
print(series(sin(x), x, 0, 7))  # x - x**3/6 + x**5/120
```
"""

_SAMPLE_DS_EXAM = """---
title: "二叉树与遍历"
subject: "数据结构"
chapter: "第五章 树与二叉树"
tags: ["二叉树", "遍历", "前序", "中序", "后序", "层序"]
note_type: "exam"
exam_freq: 5
---

# 二叉树与遍历（期末版）

## 1. 基本性质

- 第 $i$ 层最多 $2^{i-1}$ 个结点（$i \\ge 1$）
- 深度为 $k$ 的二叉树最多 $2^k - 1$ 个结点
- 叶子结点数 $n_0$ 与度为 2 的结点数 $n_2$ 满足：$n_0 = n_2 + 1$

## 2. 四种遍历

| 遍历 | 访问顺序 | 用途 |
|------|----------|------|
| 前序 | 根 → 左 → 右 | 复制树、前缀表达式 |
| 中序 | 左 → 根 → 右 | **BST 得有序序列** |
| 后序 | 左 → 右 → 根 | 释放结点、后缀表达式 |
| 层序 | 逐层从左到右 | BFS、宽度计算 |

> ⚠️ 已知前序+中序（或后序+中序）可唯一确定二叉树；**只有前序+后序不能唯一确定**。

## 3. 代码模板

```python
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder(root: TreeNode | None):
    # 中序遍历（递归版）
    if root is None:
        return
    inorder(root.left)
    print(root.val, end=" ")
    inorder(root.right)

def level_order(root: TreeNode | None):
    # 层序遍历（队列版）
    from collections import deque
    if root is None:
        return
    q = deque([root])
    while q:
        node = q.popleft()
        print(node.val, end=" ")
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
```

## 4. 必考题型

1. 给定前序 + 中序，画二叉树并写后序
2. 统计叶子结点数 / 求树高（递归）
3. 判断是否为完全二叉树
"""

_SAMPLE_DS_POSTGRAD = """---
title: "红黑树与B树"
subject: "数据结构"
chapter: "第七章 查找"
tags: ["红黑树", "B树", "B+树", "平衡", "考研"]
note_type: "postgraduate"
exam_freq: 3
---

# 红黑树与 B 树（考研版）

## 1. 红黑树五条性质

1. 每个结点非红即黑
2. 根结点是黑色
3. 叶结点（NIL）是黑色
4. 红结点的两个孩子必为黑（不存在连续红边）
5. 从任一结点到其每个叶子的路径上黑结点数相同（黑高相等）

> 结论：根到叶最长路径 ≤ 2 × 最短路径，故红黑树高度 $O(\\log n)$。

## 2. 插入调整（考研重点）

| 情况 | 父为红时 | 处理 |
|------|----------|------|
| 叔叔为红 | 变色 | 父、叔变黑，祖父变红，上溯 |
| 叔叔为黑（LL/RR） | 单旋 | 右旋/左旋 + 变色 |
| 叔叔为黑（LR/RL） | 双旋 | 先转成 LL/RR 再单旋 |

## 3. B 树与 B+ 树对比

| 特性 | B 树 | B+ 树 |
|------|------|-------|
| 数据存放 | 内部结点也存 | 仅叶子结点存 |
| 查找 | 到内部结点即止 | 必须到叶子 |
| 范围查询 | 中序遍历 | 叶子链指针 |
| 应用 | 文件系统目录 | MySQL InnoDB 索引 |

## 4. 高频考点

- B 树阶数 $m$ 的约束：每个结点最多 $m-1$ 个关键字；除根外至少 $\\lceil m/2 \\rceil - 1$ 个
- 高度为 $h$ 的 $m$ 阶 B 树最少/最多关键字个数计算
- 红黑树删除的 8 种情况（理解即可，不要求背）

```python
# 红黑树插入后的平衡判断（伪代码）
def is_red(node): return node and node.color == "RED"
def fixup_after_insert(node):
    while is_red(node.parent):
        uncle = node.parent.sibling()
        if is_red(uncle):          # 情况1：变色
            recolor(node.parent, uncle, node.grandparent)
            node = node.grandparent
        else:                       # 情况2/3：旋转
            rotate_and_recolor(node)
    root.color = "BLACK"
```
"""

_SAMPLE_ML_EXAM = """---
title: "监督学习基础"
subject: "机器学习导论"
chapter: "第二章 监督学习"
tags: ["线性回归", "逻辑回归", "过拟合", "交叉验证"]
note_type: "exam"
exam_freq: 4
---

# 监督学习基础（期末版）

## 1. 核心概念

- **训练集 / 验证集 / 测试集**：验证集用于调超参，测试集只用于最终评估
- **损失函数**：衡量预测值与真实值的差距
- **过拟合**：训练误差低、泛化误差高；**欠拟合**：两者都高

## 2. 线性回归

假设函数 $h(x) = w^T x + b$，均方误差损失：

$$
J(w) = \\frac{1}{2m}\\sum_{i=1}^{m}(h(x^{(i)}) - y^{(i)})^2
$$

梯度下降更新：$w_j := w_j - \\alpha \\frac{\\partial J}{\\partial w_j}$

## 3. 逻辑回归与分类

$h(x) = \\sigma(w^T x) = \\frac{1}{1+e^{-w^T x}}$，用交叉熵损失：

$$
J(w) = -\\frac{1}{m}\\sum_{i=1}^{m}\\left[y^{(i)}\\log h(x^{(i)}) + (1-y^{(i)})\\log(1-h(x^{(i)}))\\right]
$$

## 4. 模型评估指标

| 指标 | 公式 | 适用 |
|------|------|------|
| 精确率 Precision | TP / (TP + FP) | 假阳性代价高 |
| 召回率 Recall | TP / (TP + FN) | 漏检代价高 |
| F1 分数 | 2PR / (P + R) | 不平衡数据 |

> ⚠️ 考试陷阱：精确率和召回率的分子都是 TP，别记混。

## 5. 防止过拟合

1. 增加训练数据
2. L1/L2 正则化
3. Dropout（神经网络）
4. 早停（Early Stopping）
5. K 折交叉验证（常用 K=5 或 10）

```python
# sklearn 逻辑回归示例
from sklearn.linear_model import LogisticRegression
model = LogisticRegression(C=1.0)  # C 越小正则越强
model.fit(X_train, y_train)
score = model.score(X_test, y_test)
print("accuracy:", score)
```
"""
