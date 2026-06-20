# 工具 Observation 统一输出格式设计（融合方案）

**创建时间**: 2026-06-20 11:07:25  
**更新时间**: 2026-06-20 16:30:00  
**版本**: v2.0  
**编写人**: 小健 + 北京老陈  
**适用范围**: OmniAgentAs-desk 所有工具给LLM和前端的observation输出格式  
**状态**: 待审查

---

## 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-20 11:07:25 | 初始融合方案 | 小健 + 北京老陈 |
| v1.1 | 2026-06-20 11:30:00 | llm_data重新定位：不再是"给LLM的额外数据"，而是LLM和前端共享的摘要层，包含summary+结构化关键信息 | 小健 + 北京老陈 |
| v1.2 | 2026-06-20 12:15:00 | 详情行统一改为只输出data.result（成功/警告），error时输出整个data；formatter代码同步更新；3.1表格更新 | 小健 + 北京老陈 |
| v2.0 | 2026-06-20 16:30:00 | 重大重构：消除llm_data与data的字段重复。llm_data=结构化摘要（action/target/关键数字/summary），data=纯业务数据（只放llm_data没有的大块内容）；data不再需要action/target/result三必填；error同理 | 小健 + 北京老陈 |

---

## 一、问题现状

### 1.1 三大问题

**问题1：data不完整** — LLM拿到的数据缺少关键决策信息

| 示例 | data内容 | LLM缺什么 |
|------|---------|-----------|
| write_docx成功 | `{"file_path": "..."}` | 写了多少段落？多少字？ |
| delete_file幂等 | `None` | 哪个文件？什么操作？ |
| generate_chart成功 | `"D:/chart.png"`(裸字符串) | 图表类型？ |
| event_log错误 | `{"error": "..."}` | 哪个日志？什么级别？ |
| registry_write成功 | `{"key_path": "...", "value": "..."}` | 旧值是什么？ |

**问题2：data格式千奇百怪** — 同类操作结构不统一

| 操作类型 | 工具 | data结构 | 问题 |
|---------|------|---------|------|
| 写入文件 | write_text_file | `{operation_id, file_path, bytes_written}` | 有operation_id |
| 写入文件 | write_docx | `{file_path}` | 无operation_id，无内容摘要 |
| 写入文件 | write_xlsx | `{file_path, row_count}` | 无operation_id |
| 读取文件 | read_text_file | `{content, total_lines, ...}` | 字段最多 |
| 读取文件 | read_pdf | `{text, page_count, ...}` | 用text而非content |
| 读取文件 | read_xlsx | `{headers, rows, row_count, ...}` | 完全不同的结构 |
| 剪贴板读 | clipboard_read | `{text}` | 字段名text |
| 剪贴板写 | clipboard_write | `{content}` | 字段名content |

**问题3：message没信息量** — "执行成功""读取文件成功"不告诉LLM关键数字

**问题4：llm_data定位模糊** — 覆盖不完整、与data信息重叠、维护两套、前端不用

**问题5：error时data信息严重不足** — LLM无法理解错误原因和修正

### 1.2 问题统计

| 严重程度 | 数量 | 典型问题 |
|---------|------|---------|
| P0-紧急 | 1 | generate_chart data传str而非dict |
| P1-高 | 23 | data完整性缺失 |
| P2-中 | 15 | 格式一致性、字段命名不一致 |
| P3-低 | 14 | error时data缺少修正上下文 |
| **合计** | **53** | |

---

## 二、设计目标

### 2.1 核心原则

1. **每看全懂** — LLM看到observation就能准确理解工具执行结果
2. **格式统一** — 所有工具用同一种data结构和observation格式
3. **信息完整** — 关键事实都在，不丢失重要信息
4. **简洁高效** — 不废话，不冗余，token占用最小
5. **LLM和前端一视同仁** — 同一数据源，前端可控制显示层级

### 2.2 设计约束

- 格式化逻辑留在observation_formatter.py（SRP）
- 工具侧只管提供结构化data和llm_data
- data保持dict（接口一致性，无业务数据时为空dict）
- 去掉message参数：成功时summary已覆盖，错误时code+summary已覆盖，无冗余
- 不改功能逻辑，只改输出格式
- 渐进式改造，不求一步到位

---

## 三、核心设计：三层分离

### 3.1 三个层次的职责

| 层次 | 来源 | 职责 | LLM怎么用 | 前端怎么用 |
|------|------|------|----------|-----------|
| **观察** | formatter生成 | 状态+操作名 | 扫一眼知道发生了什么 | 状态指示器 |
| **结果** | llm_data字段 | 结构化摘要（action/target/关键数字/summary） | 快速理解结果概况 | 渲染摘要卡片（summary做标题，action/target/关键数字做标签） |
| **详情** | data字段 | 纯业务数据（只放llm_data没有的大块内容） | 需要精确数据时引用 | 可折叠详情面板 |

**核心原则：llm_data和data零重复**

- llm_data = 结构化描述（action/target/关键数字/summary）
- data = 纯业务数据（content/output等大块内容，llm_data不存的）
- 同一字段只出现一次，改一处即可

### 3.2 关键设计：llm_data与data的职责分离

**旧设计**：llm_data和data都有action/target/关键数字 → 重复写两遍

**新设计**：llm_data管"描述"，data管"内容"，零重复

#### 3.2.1 llm_data结构（结构化摘要，唯一持有action/target/关键数字/message）

```python
llm_data = {
    # === 必填字段 ===
    "summary": str,     # 自然语言摘要（"读取 C:\test.py，156行，2380字节，UTF-8编码"）
    "action": str,      # 操作类型英文（"read"/"write"/"delete"/"search"/"execute"/"copy"/"list"/"query"/"download"/"click"/"capture"/"set"/"info"）
    "action_zh": str,   # 操作类型中文（"读取"/"写入"/"删除"/"搜索"/"执行"/"复制"/"列出"/"查询"/"下载"/"点击"/"截图"/"设置"/"获取"）
    "target": str,      # 操作目标（路径/URL/查询词/命令，如"C:\test.py"）
    "message": str,     # 状态文字说明（成功："读取成功"/写入："写入成功"/ 错误："文件不存在"/"请求超时"）
    
    # === 可选字段（按工具类型放关键数字）===
    "lines": int,       # 行数（文本类）
    "bytes": int,       # 字节数（文件类）
    "encoding": str,    # 编码（文本类）
    "exit_code": int,   # 退出码（Shell类）
    "status_code": int, # HTTP状态码（网络类）
    "row_count": int,   # 行数（数据库类）
    "columns": list,    # 列名（数据库类）
    "total": int,       # 总数（搜索/列表类）
    "deleted": bool,    # 是否实际删除（删除类）
    "mode": str,        # 模式（删除类：permanent/recycle/already_gone）
    "bytes_written": int,# 写入字节数（写入类）
    "pages": int,       # 页数（PDF类）
    ...
}
```

**为什么action要双语？**

| 消费方 | 用action还是action_zh | 原因 |
|--------|----------------------|------|
| formatter观察行 | action_zh | LLM看中文更直观："读取成功"比"read success"更清晰 |
| 前端操作标签 | action_zh | 用户看中文 |
| 前端程序逻辑 | action | 程序判断用英文，不依赖中文 |
| 日志/调试 | action | 英文便于检索 |

**为什么要有message？**

| 场景 | message示例 | 作用 |
|------|-----------|------|
| 成功 | "读取成功" | LLM一眼知道操作结果 |
| 错误 | "文件不存在" | LLM理解失败原因（code如ERR_FILE_NOT_FOUND对LLM无意义） |
| 警告 | "影响行数超过安全阈值" | LLM理解警告原因 |

#### 3.2.2 data结构（纯业务数据，只放llm_data没有的大块内容）

```python
# read类
data = {"content": str|list|dict}   # 读取到的内容

# execute类
data = {"output": str, "error_output": str}  # 命令输出

# search类
data = {"items": list}              # 搜索结果列表

# 数据库类
data = {"rows": list}               # 查询结果行
# 或
data = {"tables": dict}             # Schema信息

# 系统信息类
data = {"cpu": dict, "memory": dict, "disk": dict}  # 系统详情

# 事件日志类
data = {"events": list}             # 事件列表

# write/delete/copy/download/capture/click/set类（无大块内容）
data = {}                           # 空dict

# error类
data = {"error_detail": str, "params": dict}  # 错误详情和参数
```

#### 3.2.3 llm_data与data的零重复原则

**同一字段只出现一次**：

```python
# ✅ 正确：llm_data有lines，data不放lines
llm_data = {"summary":"读取 C:\\test.py，156行","action":"read","action_zh":"读取","target":"C:\\test.py","message":"读取成功","lines":156,"bytes":2380}
data = {"content": "def hello():\n    ..."}

# ❌ 错误：data又放lines → 重复
data = {"content": "def hello():...", "lines": 156, "bytes": 2380}
```

**禁止**：
- llm_data有lines，data又放lines → 重复
- llm_data有action，data又放action → 重复
- llm_data有bytes，data又放bytes_written → 同义重复

#### 3.2.4 各字段最终去向

| 字段 | 持有者 | 观察行 | 结果行 | 详情行 | 前端标签 |
|------|--------|--------|--------|--------|---------|
| action | llm_data | — | — | — | 操作标签（英文，程序用） |
| action_zh | llm_data | ✅ "读取成功" | — | — | 操作标签（中文，用户看） |
| target | llm_data | — | 嵌在summary | — | 目标标签 |
| message | llm_data | ✅ "读取成功" | — | — | — |
| summary | llm_data | — | ✅ | — | 卡片标题 |
| lines/bytes等 | llm_data | — | 嵌在summary | — | 数字标签 |
| content/output等 | data | — | — | ✅ | 可折叠详情 |

**前端渲染效果**：

```
┌─────────────────────────────────────────┐
│ 📄 读取 C:\test.py                      │  ← summary
│ 读取 | 156行 | 2380字节 | UTF-8          │  ← 从llm_data取action_zh/lines/bytes/encoding
│ [展开详情 ▼]                             │  ← 可折叠data
└─────────────────────────────────────────┘
```

**前端控制**：
- 摘要模式：只显示llm_data（summary + 关键标签）
- 详情模式：展开显示data（纯业务数据）
- 小屏/移动端：只显示summary

### 3.3 observation输出格式

**核心原则：每层只说自己的事，零重复**

| 层 | 来源 | 输出内容 | 不重复 |
|---|------|---------|--------|
| 观察 | formatter | 状态+action_zh+message | — |
| 结果 | llm_data | summary | 不重复action（观察已有） |
| 详情 | data | 纯业务数据 | 不重复action/target/关键数字（观察+结果已有） |

**成功**：
```
观察: {llm_data.action_zh}成功 - {llm_data.message}
结果: {llm_data.summary}
详情: {json.dumps(data)}
```

**错误**：
```
观察: {llm_data.action_zh}失败 - {llm_data.message}
结果: {llm_data.summary}
详情: {json.dumps(data)}
建议: {hint}
```

**警告**：
```
观察: {llm_data.action_zh}警告 - {llm_data.message}
⚠ 警告: {warning}
结果: {llm_data.summary}
详情: {json.dumps(data)}
建议: {hint}
```


### 3.4 对比效果

**旧格式**（当前）：
```
Observation: success - 读取文件成功
【摘要】 action=read_file | file_path=C:\test.py | bytes_read=2380
【数据】 {"operation_id":"abc123","file_path":"C:\\test.py","bytes_read":2380,"encoding":"utf-8","line_count":156,"content":"def hello():\n    ..."}
```

**新格式**：
```
观察: success - read
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情: {"content":"def hello():\n    ..."}
```

**LLM的认知路径**：
1. 第一行：成功读取了文件
2. 第二行：156行，2380字节，UTF-8编码 — 关键信息直接可见
3. 第三行：需要具体内容时看详情 — 只有纯业务数据

**与旧方案的关键区别**：详情行只输出data（纯业务数据），不再重复action/target/关键数字

---

## 四、data统一格式规范

### 4.1 核心规范：data只放纯业务数据

data不再持有action/target/关键数字（这些在llm_data里），只放llm_data不存的大块业务内容。

```python
# data = 纯业务数据（只放llm_data没有的东西）
data = {
    "content": str|list|dict,  # 可选：大块内容（文件内容/命令输出/搜索结果等）
    # 按工具类型不同，放业务数据
}
```

**为什么data不再需要action/target/result？**

| 字段 | 旧方案 | 新方案 | 理由 |
|------|--------|--------|------|
| `action` | data和llm_data都有 | 只在llm_data | 零重复 |
| `target` | data和llm_data都有 | 只在llm_data | 零重复 |
| `result` | data的嵌套层 | 去掉，data本身就是结果 | 减少嵌套，data直接放业务字段 |
| 关键数字 | data.result和llm_data都有 | 只在llm_data | 零重复 |

### 4.2 各操作类型的data格式

#### 4.2.1 read类（读取）

```python
data = {
    "content": str|list|dict,  # 读取到的内容
}
```

**示例**：
- read_text_file: `{"content": "def hello():..."}`
- read_xlsx: `{"content": {"headers": [...], "rows": [...]}}`
- read_pdf: `{"content": "PDF文本内容..."}`

#### 4.2.2 write类（写入）

```python
data = {}  # 写入成功通常无需额外业务数据，关键数字在llm_data
```

**示例**：
- write_text_file: `{}`  （bytes_written/content_summary在llm_data里）
- write_docx: `{}` 
- write_xlsx: `{}` 

#### 4.2.3 search类（搜索）

```python
data = {
    "items": list,             # 搜索结果列表
}
```

#### 4.2.4 execute类（执行）

```python
data = {
    "output": str,             # 输出内容
    "error_output": str,       # 错误输出
}
```

#### 4.2.5 delete类（删除）

```python
data = {}  # 删除结果的关键信息在llm_data（deleted/mode）
```

#### 4.2.6 copy/move类（复制/移动）

```python
data = {}  # 关键信息在llm_data（source→destination/bytes）
```

#### 4.2.7 其他类型

按实际需要放业务数据，原则：**llm_data已有的字段，data不再重复**。

### 4.3 data与llm_data的零重复原则

**核心原则：同一字段只出现一次**

```python
# llm_data（结构化摘要）
llm_data = {"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":"read","target":"C:\\test.py","lines":156,"bytes":2380,"encoding":"utf-8"}

# data（纯业务数据）
data = {"content": "def hello():\n    ..."}
```

**禁止**：
- llm_data有lines，data又放lines → 重复
- llm_data有action，data又放action → 重复
- llm_data有bytes，data又放bytes_written → 同义重复

### 4.4 error时的data格式

error时data也只放llm_data没有的信息：

```python
data = {
    "error_detail": str,       # 必填：错误详情（比message更具体）
    "params": dict,            # 可选：导致错误的参数（LLM可据此修正）
}
```

**示例**：

```python
# 当前（信息不足）
build_error(ERR_FILE_NOT_FOUND, "文件不存在", data={"file_path": "D:/test.txt"})

# 规范后（零重复，action/target在llm_data）
build_error(ERR_FILE_NOT_FOUND, "文件不存在", 
    data={"error_detail": "文件路径不存在", "params": {"encoding": "utf-8"}},
    llm_data={"summary":"文件 D:/test.txt 不存在","action":"read","target":"D:/test.txt"}
)
```

---

## 五、llm_data统一格式规范

### 5.1 llm_data定位

**llm_data = 结构化摘要（唯一持有action/target/关键数字）**

- LLM通过"结果"行消费summary
- 前端渲染摘要卡片（summary做标题，action/target/关键数字做标签）
- data不再重复这些字段

### 5.2 llm_data必填字段

```python
llm_data = {
    "summary": str,     # 必填：自然语言摘要，格式为"操作+对象+数字"
    "action": str,      # 必填：操作类型（动词）
    "target": str,      # 必填：操作目标（路径/URL/查询词/命令）
}
```

**summary格式规范**：`{操作} {对象}，{关键数字1}，{关键数字2}`

```python
# 示例
"读取 C:\\test.py，156行，2380字节，UTF-8编码"
"写入 C:\\output.docx，3段落/500字"
"查询返回5行，列: id, name, email"
"搜索到8条结果(Parallel引擎)"
"删除 C:\\temp.log，已永久删除"
```

### 5.3 llm_data可选字段

按工具类型放关键数字，前端渲染为标签。**这些字段只出现在llm_data，data不再重复**：

```python
# 文件类
llm_data = {"summary": "...", "action": "read", "target": "C:\\test.py",
            "lines": 156, "bytes": 2380, "encoding": "utf-8"}

# 数据库类
llm_data = {"summary": "...", "action": "query", "target": "SELECT * FROM users",
            "row_count": 5, "columns": ["id", "name", "email"]}

# 网络类
llm_data = {"summary": "...", "action": "search", "target": "低空星链通信 2026",
            "total": 8, "engine": "Parallel"}

# Shell类
llm_data = {"summary": "...", "action": "execute", "target": "Get-Process",
            "exit_code": 0}
```

### 5.4 前端渲染示例

```
┌──────────────────────────────────────────────┐
│ 📄 读取 C:\test.py                           │  ← summary
│ 读取 | 156行 | 2380字节 | UTF-8               │  ← 从llm_data取action/lines/bytes/encoding
│                                    [展开详情▼] │  ← 可折叠data
└──────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────┐
│ 🔍 搜索到8条结果(Parallel引擎)                │  ← summary
│ 搜索 | 8条结果 | Parallel引擎                  │  ← 从llm_data取action/total/engine
│                                    [展开详情▼] │
└──────────────────────────────────────────────┘
```

### 5.5 llm_data全覆盖

**所有工具必须有llm_data**（当前8/10有，2/10没有）。这是强制规范。

---

## 六、各工具类型完整示例

### 6.1 文件操作

**read_text_file 成功**：
```python
build_success(
    data={"content":"def hello():\n    ..."},

    llm_data={"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":"read","target":"C:\\test.py","lines":156,"bytes":2380,"encoding":"utf-8"},
)
```
输出：
```
观察: success - read
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情: {"content":"def hello():\n    ..."}
```

**llm_data各字段去向说明**：
| llm_data字段 | LLM看到 | 前端看到 | 说明 |
|---|---|---|---|
| summary | 结果行（自然语言） | 摘要卡片标题 | 已包含target/lines/bytes/encoding的文字描述 |
| action | 观察行 | 操作类型标签 | 如"read" |
| target | 嵌在summary里 | 目标标签 | 如"C:\test.py" |
| lines/bytes/encoding | 嵌在summary里 | 结构化标签 | 前端渲染为"156行 | 2380字节 | UTF-8" |

**write_text_file 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"写入 C:\\output.txt，50行/1024字节","action":"write","target":"C:\\output.txt","bytes_written":1024},
)
```
```
观察: success - write
结果: 写入 C:\output.txt，50行/1024字节
详情: {}
```

**list_directory 成功**：
```python
build_success(
    data={"entries":["src/","README.md",...]},

    llm_data={"summary":"列出 C:\\project\\，156个文件/目录","action":"list","target":"C:\\project\\","total":156,"truncated":False},
)
```
```
观察: success - list
结果: 列出 C:\project\，156个文件/目录
详情: {"entries":["src/","README.md",...]}
```

**copy_file 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"复制 C:\\a.txt → C:\\b.txt，1024字节","action":"copy","target":"C:\\a.txt → C:\\b.txt","bytes":1024},
)
```
```
观察: success - copy
结果: 复制 C:\a.txt → C:\b.txt，1024字节
详情: {}
```

**delete_file 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"删除 C:\\temp.log，已永久删除","action":"delete","target":"C:\\temp.log","deleted":True,"mode":"permanent"},
)
```
```
观察: success - delete
结果: 删除 C:\temp.log，已永久删除
详情: {}
```

**delete_file 幂等（文件不存在）**：
```python
build_success(
    data={},

    llm_data={"summary":"删除 C:\\temp.log，文件已不存在(幂等)","action":"delete","target":"C:\\temp.log","deleted":False,"mode":"already_gone"},
)
```
```
观察: success - delete
结果: 删除 C:\temp.log，文件已不存在(幂等)
详情: {}
```

### 6.2 数据库工具

**query_sql 成功**：
```python
build_success(
    data={"rows":[[1,"Alice","a@t.com"],...]},

    llm_data={"summary":"查询返回5行，列: id, name, email","action":"query","target":"SELECT * FROM users","row_count":5,"columns":["id","name","email"]},
)
```
```
观察: success - query
结果: 查询返回5行，列: id, name, email
详情: {"rows":[[1,"Alice","a@t.com"],...]}
```

**execute_sql 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"SQL执行成功，影响5行","action":"execute","target":"UPDATE users SET ...","affected_rows":5},
)
```
```
观察: success - execute
结果: SQL执行成功，影响5行
详情: {}
```

**get_db_schema 成功**：
```python
build_success(
    data={"tables":{"users":"...","orders":"...","products":"..."}},

    llm_data={"summary":"获取到3个表的结构: users, orders, products","action":"schema","target":"database","total":3},
)
```
```
观察: success - schema
结果: 获取到3个表的结构: users, orders, products
详情: {"tables":{"users":"...","orders":"...","products":"..."}}
```

### 6.3 文档工具

**read_pdf 成功**：
```python
build_success(
    data={"content":"PDF文本..."},

    llm_data={"summary":"读取 C:\\report.pdf，5页，12000字符","action":"read","target":"C:\\report.pdf","pages":5,"chars":12000},
)
```
```
观察: success - read
结果: 读取 C:\report.pdf，5页，12000字符
详情: {"content":"PDF文本..."}
```

**write_docx 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"写入 C:\\report.docx，3段落/500字","action":"write","target":"C:\\report.docx","bytes_written":2048,"content_summary":"3段落/500字"},
)
```
```
观察: success - write
结果: 写入 C:\report.docx，3段落/500字
详情: {}
```

**write_xlsx 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"写入 C:\\data.xlsx，10行×5列","action":"write","target":"C:\\data.xlsx","bytes_written":512,"content_summary":"10行×5列"},
)
```
```
观察: success - write
结果: 写入 C:\data.xlsx，10行×5列
详情: {}
```

### 6.4 网络工具

**search_web 成功**：
```python
build_success(
    data={"items":[...]},

    llm_data={"summary":"搜索到8条结果(Parallel引擎)","action":"search","target":"低空星链通信 2026","total":8,"engine":"Parallel"},
)
```
```
观察: success - search
结果: 搜索到8条结果(Parallel引擎)
详情: {"items":[...]}
```

**http_request 成功**：
```python
build_success(
    data={"body":"..."},

    llm_data={"summary":"HTTP GET https://api.example.com，状态码200，响应体15000字符","action":"request","target":"https://api.example.com","status_code":200,"content_type":"application/json"},
)
```
```
观察: success - request
结果: HTTP GET https://api.example.com，状态码200，响应体15000字符
详情: {"body":"..."}
```

**download_file 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"下载完成，102400字节，保存到 C:\\download\\file.zip","action":"download","target":"https://example.com/file.zip","bytes":102400,"file_path":"C:\\download\\file.zip"},
)
```
```
观察: success - download
结果: 下载完成，102400字节，保存到 C:\download\file.zip
详情: {}
```

### 6.5 Shell工具

**execute_shell_command 成功**：
```python
build_success(
    data={"output":"Handles  NPM(K)...","error_output":""},

    llm_data={"summary":"命令执行成功，退出码0","action":"execute","target":"Get-Process","exit_code":0},
)
```
```
观察: success - execute
结果: 命令执行成功，退出码0
详情: {"output":"Handles  NPM(K)...","error_output":""}
```

### 6.6 系统工具

**get_system_info 成功**：
```python
build_success(
    data={"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50},"disk":{"C:":{"total_gb":500,"used_pct":60}}},

    llm_data={"summary":"获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)","action":"info","target":"system"},
)
```
```
观察: success - info
结果: 获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)
详情: {"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50},"disk":{"C:":{"total_gb":500,"used_pct":60}}}
```

**event_log 成功**：
```python
build_success(
    data={"events":[...]},

    llm_data={"summary":"获取事件日志(Application)，10条记录","action":"read","target":"event_log/Application","total":10,"level":"Error"},
)
```
```
观察: success - read
结果: 获取事件日志(Application)，10条记录
详情: {"events":[...]}
```

### 6.7 桌面工具

**mouse_click 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"点击屏幕(500,300)，左键单击","action":"click","target":"screen(500,300)","button":"left","click_type":"single"},
)
```
```
观察: success - click
结果: 点击屏幕(500,300)，左键单击
详情: {}
```

**screen_capture 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"截图保存到 C:\\capture.png，1920×1080","action":"capture","target":"screen","file_path":"C:\\capture.png","width":1920,"height":1080},
)
```
```
观察: success - capture
结果: 截图保存到 C:\capture.png，1920×1080
详情: {}
```

### 6.8 注册表工具

**registry_read 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"读取 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)","action":"read","target":"HKCU\\Software\\MyApp\\LastLogin","value":"2026-06-20","value_type":"REG_SZ"},
)
```
```
观察: success - read
结果: 读取 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)
详情: {}
```

**registry_write 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"写入 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)，旧值=\"2026-06-19\"","action":"write","target":"HKCU\\Software\\MyApp\\LastLogin","new_value":"2026-06-20","old_value":"2026-06-19","value_type":"REG_SZ"},
)
```
```
观察: success - write
结果: 写入 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)，旧值="2026-06-19"
详情: {}
```

### 6.9 定时器工具

**timer_set 成功**：
```python
build_success(
    data={},

    llm_data={"summary":"定时器设置成功，30秒后触发","action":"set","target":"timer","delay_seconds":30,"trigger_time":"2026-06-20 10:51:00"},
)
```
```
观察: success - set
结果: 定时器设置成功，30秒后触发
详情: {}
```

---

## 七、错误格式规范

### 7.1 错误data（只放llm_data没有的信息）

```python
data = {
    "error_detail": str,    # 必填：错误详情（比message更具体）
    "params": dict,         # 可选：导致错误的参数（LLM可据此修正）
}
```

### 7.2 错误llm_data（持有action/target）

```python
llm_data = {
    "summary": str,          # 必填：自然语言错误摘要
    "action": str,           # 必填：操作类型
    "target": str,           # 必填：操作目标
}
```

### 7.3 错误示例

**文件不存在**：
```python
build_error(
    ERR_FILE_NOT_FOUND, "文件不存在",
    data={"error_detail":"文件路径不存在","params":{"encoding":"utf-8"}},
    llm_data={"summary":"文件 C:\\notexist.txt 不存在","action":"read","target":"C:\\notexist.txt"},
)
```
```
观察: error [ERR_FILE_NOT_FOUND] - 文件不存在
结果: 文件 C:\notexist.txt 不存在
详情: {"error_detail":"文件路径不存在","params":{"encoding":"utf-8"}}
建议: 请检查路径是否正确
```

**SQL执行失败**：
```python
build_error(
    ERR_SQL_EXEC, "SQL执行错误",
    data={"error_detail":"near SELCT: syntax error","params":{"sql":"SELCT * FROM users","connection_type":"sqlite"}},
    llm_data={"summary":"SQL执行失败: near \"SELCT\": syntax error","action":"query","target":"SELCT * FROM users"},
)
```
```
观察: error [ERR_SQL_EXEC] - SQL执行错误
结果: SQL执行失败: near "SELCT": syntax error
详情: {"error_detail":"near SELCT: syntax error","params":{"sql":"SELCT * FROM users","connection_type":"sqlite"}}
建议: 请检查SQL语法
```

**依赖库未安装**：
```python
build_error(
    ERR_NO_PYAUTOGUI, "依赖库未安装",
    data={"error_detail":"pyautogui库未安装","params":{"library":"pyautogui","install_command":"pip install pyautogui"}},
    llm_data={"summary":"需要安装 pyautogui 库","action":"execute","target":"desktop_automation"},
)
```
```
观察: error [ERR_NO_PYAUTOGUI] - 依赖库未安装
结果: 需要安装 pyautogui 库
详情: {"error_detail":"pyautogui库未安装","params":{"library":"pyautogui","install_command":"pip install pyautogui"}}
建议: 请先执行安装命令
```

**HTTP请求超时**：
```python
build_error(
    ERR_TIMEOUT, "请求超时",
    data={"error_detail":"连接超时，30秒未响应","params":{"url":"https://slow-api.com","timeout":30}},
    llm_data={"summary":"请求 https://slow-api.com 超时，30秒未响应","action":"request","target":"https://slow-api.com"},
)
```
```
观察: error [ERR_TIMEOUT] - 请求超时
结果: 请求 https://slow-api.com 超时，30秒未响应
详情: {"error_detail":"连接超时，30秒未响应","params":{"url":"https://slow-api.com","timeout":30}}
建议: 请稍后重试或检查网络连接
```

---

## 八、警告格式规范

### 8.1 警告输出格式

```
观察: warning [{code}] - {message}
⚠ 警告: {warning}
结果: {llm_data.summary}
详情: {json.dumps(data.result)}
建议: {hint}
```

### 8.2 警告示例

**数据量过大回滚**：
```
观察: warning [WARNING_DB_SAFETY] - SQL影响行数过大
⚠ 警告: 操作影响行数超过安全阈值，已自动回滚
结果: SQL影响50000行，超过安全阈值10000，已自动回滚
详情: {"affected_rows":50000,"action_taken":"rollback"}
建议: 请使用 WHERE 子句缩小影响范围
```

---

## 九、实现方案

### 9.1 三阶段改造

| 阶段 | 改造内容 | 影响范围 | 依赖 |
|------|---------|---------|------|
| **Phase 1** | 修复P0+P1：data传str→dict、data=None→dict、补齐缺失字段、补齐llm_data | ~25个函数 | 无 |
| **Phase 2** | 统一data为action/target/result结构 + 统一llm_data为summary/action/target格式 + 重构observation_formatter | 71个函数 | Phase 1 |
| **Phase 3** | 统一error时data格式（加action/target/error_detail/params） | ~50个error调用 | Phase 2 |

### 9.2 Phase 1修复清单（Top 10优先）

| 序号 | 函数 | 当前问题 | 修复方式 |
|------|------|---------|---------|
| 1 | generate_chart | data=str | 改为`{"action":"generate","target":output_path,"result":{...}}` |
| 2 | _delete_file幂等 | data=None | 改为`{"action":"delete","target":file_path,"result":{"deleted":False}}` |
| 3 | write_docx | data只有file_path | 加content_summary |
| 4 | write_pdf | data只有file_path | 加content_summary |
| 5 | write_xlsx | 缺llm_data | 补充llm_data |
| 6 | _read_xlsx/_read_csv | 缺llm_data | 补充llm_data |
| 7 | clipboard_read/write | text vs content | 统一为content |
| 8 | analyze_data llm_data | 列名永远为空 | 修复isinstance判断 |
| 9 | find_command不可用 | 用success表达失败 | 改为warning |
| 10 | _ping不可达/_port_check关闭 | 用success表达失败 | 改为warning |

### 9.3 Phase 2核心改动

#### 9.3.1 重构 observation_formatter.py

```python
def format_llm_observation(result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    code = result.get("code")
    data = result.get("data")
    llm_data = result.get("llm_data")
    message = result.get("message", "")

    if code == SUCCESS_CODE:
        # 成功：观察 + 结果 + 详情（只输出data，纯业务数据）
        action = llm_data.get("action", tool_name) if isinstance(llm_data, dict) else tool_name
        text = f"观察: success - {action}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        elif message:
            text += f"\n结果: {message}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            text += f"\n详情: {json.dumps(safe_data, ensure_ascii=False)}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        return text

    elif isinstance(code, str) and code.startswith("WARNING_"):
        # 警告：详情只输出data
        action = llm_data.get("action", tool_name) if isinstance(llm_data, dict) else tool_name
        text = f"观察: warning [{code}] - {message}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            text += f"\n详情: {json.dumps(safe_data, ensure_ascii=False)}"
        hint = _get_failure_hint(tool_name, tool_params, result)
        if hint:
            text += f"\n建议: {hint}"
        return text

    else:
        # 错误：详情输出整个data
        text = f"观察: error [{code}] - {message}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            text += f"\n详情: {json.dumps(safe_data, ensure_ascii=False)}"
        hint = _get_failure_hint(tool_name, tool_params, result)
        if hint:
            text += f"\n建议: {hint}"
        return text
```

#### 9.3.2 llm_data格式统一

所有工具的llm_data统一为：
```python
llm_data = {
    "summary": str,     # 必填
    "action": str,      # 必填
    "target": str,      # 必填
    # + 按工具类型的关键数字字段（只出现在llm_data，data不重复）
}
```

#### 9.3.3 data格式统一

所有工具的data只放纯业务数据（llm_data没有的大块内容）：
```python
# read类
data = {"content": "..."}

# execute类
data = {"output": "...", "error_output": "..."}

# write/delete/copy类（无大块内容）
data = {}

# error类
data = {"error_detail": "...", "params": {...}}
```

### 9.4 Phase 3核心改动

统一error时data格式，每个build_error调用补齐action/target/error_detail/params，同时补齐llm_data。

---

## 十、规范速查

### 10.1 llm_data三必填（结构化摘要，唯一持有action/target/关键数字）

```python
llm_data = {
    "summary": str,   # 自然语言摘要（"操作+对象+数字"）
    "action": str,    # 操作类型
    "target": str,    # 操作目标
    # + 按工具类型的关键数字字段
}
```

### 10.2 data只放纯业务数据（llm_data没有的大块内容）

```python
# read类
data = {"content": "..."}

# execute类
data = {"output": "...", "error_output": "..."}

# write/delete/copy类（无大块内容）
data = {}

# search类
data = {"items": [...]}
```

### 10.3 error时data两必填

```python
data = {
    "error_detail": str,    # 错误详情
    "params": dict,         # 导致错误的参数
}
```

### 10.4 禁止

| 禁止 | 说明 |
|------|------|
| data=None | 必须传dict（可以为空dict） |
| data=str | 必须传dict |
| data和llm_data字段重复 | 同一字段只出现一次 |
| data放action/target | 这些在llm_data里 |
| data放关键数字 | lines/bytes/exit_code等在llm_data里 |
| llm_data=None | 所有工具必须有llm_data |
| llm_data无summary | summary必填 |
| message="执行成功" | success时message无实际作用，摘要由llm_data.summary承担；error时message用于观察行标签 |

---

## 十一、设计优势总结

| 优势 | 说明 |
|------|------|
| **每看全懂** | 结果行自然语言摘要，LLM扫一眼就懂 |
| **格式统一** | 所有llm_data都是summary/action/target，所有data只放纯业务数据 |
| **信息完整** | llm_data有摘要+关键数字，data有大块内容，error有修正上下文 |
| **零重复** | llm_data管描述，data管内容，同一字段只出现一次，改一处即可 |
| **LLM和前端一视同仁** | llm_data是共享摘要层，前端渲染卡片，LLM看结果行 |
| **前端可控** | 摘要模式只显示llm_data，详情模式展开data |
| **维护简单** | 不再写两遍相同字段，消除了数据不一致的根源 |

---

**文档更新时间**: 2026-06-20 16:30:00  
**版本**: v2.0  
**编写人**: 小健 + 北京老陈