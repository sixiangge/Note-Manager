# Phase 3：教学与校验

## 开始使用

本次已经在项目内准备 `.venv-phase3` 独立环境，未改动原有 Python 环境。从项目目录启动：

```powershell
.\.venv-phase3\Scripts\python.exe main.py gui
```

到“设置 → 教学与模型”启用提供方，填写模型名和服务地址，再点击“测试连接”。模型默认关闭；未安装依赖、模型名为空或 API 密钥缺失时，教学输入保持禁用，笔记浏览和搜索仍可使用。测试连接仅查询模型列表，不发送笔记；模型可列出并不保证支持生成或 JSON 模式。

若将代码复制到另一台机器，先在自己的 Python 3.10+ 环境中运行：

```powershell
python -m pip install -r requirements-phase3.txt
python main.py gui
```

### Ollama

需要用户已安装并启动 Ollama，且已自行准备模型。填写本机实际模型名和 `http://localhost:11434`。程序不会安装服务或自动下载模型。

```powershell
.\.venv-phase3\Scripts\python.exe main.py teach "解释极限的定义" --model local --model-name MODEL_NAME --subject "微积分" --type exam --files "C:\课程资料\课件.pdf"
```

`MODEL_NAME` 替换为已有模型名。CLI 也支持 `NOTEMANAGER_MODEL`、`NOTEMANAGER_BASE_URL` 环境变量；仍需用 `--model local` 或 `--model api` 显式启用。`--top` 控制每类来源的片段数，`--timeout` 设置超时，`--include-samples` 允许引用示例，`--keep-cache` 保留附件提取文本。

### OpenAI 兼容 API

设置中选择 API，填写服务提供方的模型名、兼容地址和 API Key，例如 OpenAI 的 `https://api.openai.com/v1`。需要支持 Chat Completions 与 JSON object 输出。GUI 中填写的密钥由当前 Windows 账户的凭据管理器加密保存，直到用户修改或清除；不会写入 SQLite、设置导出、日志或 Git。`OPENAI_API_KEY` 环境变量仍作为未保存 GUI 密钥时的兼容后备。不要在 URL、模型名、笔记或代码中填写密钥。

GUI 每次远程请求都会确认目的地址和发送范围；CLI 显式选择 API 即表示授权该次请求，可能产生费用。兼容服务的模型列表或 JSON 支持可能不同，失败时会提示，不自动重试。连接本机模型时绕过系统代理，非本机地址必须 HTTPS，不跟随 HTTP 重定向。

## 功能与边界

- 上传支持 PDF/PPTX/DOCX/UTF-8 TXT。提供文件选择、拖入、移除附件、大小/类型校验；默认每个文件 20 MB，每次最多 20 个。Office 解压总量另限 100 MB；提取文本最多 200 万字符/文件。不执行宏、不运行 Office，不识别扫描图片或图片型公式。PDF 有密码需先解密。
- 原文件只读，外部资料不写进关键词倒排索引。PDF 标注页号，PPTX 提取文本/表格/组合形状并标注幻灯片号。相邻分块最多重叠 50 字符。单个失败会提示并继续其他附件，全部失败则不请求模型。
- 每次重新读取当前 Markdown，按科目、笔记类型及示例策略过滤；不需要重建关键词索引才能引用刚编辑的笔记。笔记和外部资料使用独立、随机会话名的 Chroma 集合，检索结束即删除。每集合上限 20000 段，过大时请缩小范围。
- 嵌入使用本地中英文词法特征哈希向量（2048 维）和余弦相似度，不是神经语义检索。同义改写可能召回不足，建议提供明确术语。没有自动下载嵌入模型，也不远程发送内容用于嵌入。笔记/外部资料各自最多取回设置的 K 段，低于 0.08 的匹配不使用；这不是“正确率”。
- 模型收到问题、最多最近 6 条对话（每条最多 4000 字符）和召回片段的标题/内容/编号，不发送完整附件或本地绝对路径。语料本身若包含敏感信息仍会随片段发送。资料内容作为数据，不执行其中指令。
- 外部资料默认优先；关闭后并列展示依据。返回“冲突”“可能遗漏”“补充”和来源编号。编号会验证，但 AI 判断仍可能出错；“可能遗漏”只表示召回笔记片段未覆盖，不能推断整篇笔记缺失。用户可勾选“显示引用片段原文”复核。
- 教学聊天支持 Markdown 文本显示和差异高亮；不加载模型回答中的图片、文件或外链资源。笔记原有预览渲染代码未改变。教学页目前不提供笔记预览级的 LaTeX 图片渲染。
- GUI 在后台解析/检索/请求模型，可取消；取消将在当前解析或网络调用返回后的安全位置生效，网络等待受设置超时限制。已发出的远程请求可能仍在服务端执行或计费。关闭窗口时若有请求，会先取消并提示稍后再关闭，避免销毁运行中的线程。
- 附件只用于本次请求，完成后移除；追问如需再次引用外部材料请重新选择。最近对话只留内存，切换检索范围或模型后不再传递旧历史。“新对话”清空内存记录；退出不保存聊天。
- 默认不保留解析缓存。隐私设置选择“保留至手动清理”时，在 `data/external/` 缓存按内容哈希命名的提取文本，不复制原文件；缓存包含资料内容，应视为敏感数据。向量索引仍总是临时的。用设置中的“清理缓存”或 CLI `cleanup-cache` 清理；不会删除上传的原文件。

## 验证

```powershell
.\.venv-phase3\Scripts\python.exe -m unittest discover -v
```

测试使用临时笔记和附件，以及只监听 `127.0.0.1` 的模拟模型服务，覆盖真实解析库、Chroma 会话隔离/清理、实际 SDK 请求格式、错误与超时、GUI 发送/取消/引用显示、设置持久化及原有功能回归。未使用你的笔记做模型测试，也未发起真实付费调用。没有可选依赖的基础环境自动跳过相应集成测试。

## 本次快速回退

先关闭 NoteManager。项目内的 `phase3-rollback` 是本次交付专用的本地回退包（不上传 GitHub）。

```powershell
# 只检查，不修改任何文件
python phase3-rollback/rollback.py --check

# 检查通过后回退本轮代码、测试和文档
python phase3-rollback/rollback.py --apply
```

也可双击 `phase3-rollback/rollback.cmd`，确认后执行。回退前逐文件核对交付时哈希；如果后来改过这些文件，或已有暂存修改，会拒绝覆盖，请先保留后续工作并人工合并。不会使用 `reset --hard`、不会操作笔记、索引、SQLite 或原始附件，也不会卸载依赖。回退包本身和 `.venv-phase3` 会保留，以便恢复；回退 `.gitignore` 后请不要把这些本地目录上传。

需要恢复本轮代码时，在回退后且没有其他改动的前提下，可用 `git apply --check phase3-rollback/phase3.patch` 检查，再用 `git apply phase3-rollback/phase3.patch` 恢复。回退包已经在临时副本中验证正向应用与反向回退。

## 接口依据

实现使用 [OpenAI JSON 输出说明](https://developers.openai.com/api/docs/guides/structured-outputs)、[Ollama Chat 接口](https://docs.ollama.com/api/chat) 和 [Chroma 自带嵌入向量写入接口](https://docs.trychroma.com/docs/collections/add-data)。
