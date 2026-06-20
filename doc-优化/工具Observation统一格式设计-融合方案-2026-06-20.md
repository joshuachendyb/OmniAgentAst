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
| v3.0 | 2026-06-20 20:24:00 | 明确"llm_data是observation的结构化中间态（非独立通道）"的根本性质，新增3.5统一数据管道，新增9.3.4 build 3函数签名改造 | 小欧 |

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
- 去掉build_success/build_error的message参数：message已移入llm_data.message，不再作为独立参数传递
- 不改功能逻辑，只改输出格式
- 渐进式改造，不求一步到位

---

## 三、核心设计：三层分离

### 3.1 三个层次的职责

| 层次 | 来源 | 职责 | LLM怎么用 | 前端怎么用 |
|------|------|------|----------|-----------|
| **观察** | formatter生成 | 状态+操作名 | 扫一眼知道发生了什么 | 状态指示器 |
| **结果** | llm_data字段 | 结构化摘要（action/target/status/metrics/summary） | 快速理解结果概况 | 渲染摘要卡片（summary做标题，action/metrics做标签） |
| **详情** | data字段 | 纯业务数据（只放llm_data没有的大块内容） | 需要精确数据时引用 | 可折叠详情面板 |

**核心原则：llm_data和data零重复**

- llm_data = 结构化描述（action/target/status/duration_ms/metrics/summary）
- data = 纯业务数据（content/output等大块内容，llm_data不存的）
- 同一字段只出现一次，改一处即可

**根本性质：llm_data是observation的结构化中间态，不是独立数据通道**

llm_data并不独立发给LLM，而是作为**结构化源数据**，由formatter机械渲染为三段式observation文本：

```
结构化源数据（llm_data）→ 渲染 → observation文本（LLM直接阅读）
```

这条链路上三个层次各司其职：

| 层次 | 角色 | 产出 | 不做什么 |
|------|------|------|---------|
| **build层** | 数据生产者 | 结构化数据（summary/action/target/status/metrics） | 不格式化，不渲染 |
| **formatter层** | 机械渲染器 | 三段式文本（观察/结果/详情） | 不新增信息，不加工语义 |
| **LLM层** | 消费者 | 只收到observation文本 | 不接触结构化数据 |

llm_data和observation文本是**一体两面**，不是两套数据。融合方案说"保留llm_data"，保留的是**结构化中间态**，不是独立LLM通道。

**设计含义**：
- 修改llm_data结构 = 修改observation文本内容（formatter自动跟随）
- LLM无需理解结构化字段名，直接读自然语言文本
- 前端仍可直接消费llm_data渲染摘要卡片（结构化数据对前端更友好）

### 3.2 关键设计：llm_data与data的职责分离

**旧设计**：llm_data和data都有action/target/关键数字 → 重复写两遍

**新设计**：llm_data管"描述"，data管"内容"，零重复

#### 3.2.1 llm_data结构（结构化摘要，唯一持有action/target/status/metrics）

```python
llm_data = {
    # === 必填字段 ===
    "summary": str,     # 自然语言摘要（"读取 C:\test.py，156行，2380字节，UTF-8编码"）
    "action": {         # 操作类型（结构固定，新增工具只扩枚举不改结构）
        "tool": str,    # 工具名称，即LLM调用时的function name（"read_text_file"/"write_docx"/"execute_shell_command"/"search_web"/...）
        "tool_zh": str,    # 中文操作类型（"读取"/"写入"/"删除"/"搜索"/"执行"/"复制"/"列出"/"查询"/"下载"/"点击"/"截图"/"设置"/"获取"/...）
        "params": dict, # LLM调用时传入的参数（{"file_path":"C:\\test.py","encoding":"utf-8"} / {"command":"Get-Process"} / {"query":"低空星链通信"}/...）
    },
    "target": str,      # 操作目标（路径/URL/查询词/命令，如"C:\test.py"）
    "status": {         # 执行状态（结构固定，三种场景统一，所有状态信息内聚于此）
        "exec_code": str,   # 执行结果码："success" / "error" / "warning"
        "message": str, # 状态文字说明（code的自然语言版本，LLM直接消费）：成功="读取成功" / 错误="文件不存在" / 警告="影响行数超过安全阈值"
        "code": str,    # 状态码（程序用）：成功="" / 错误="ERR_FILE_NOT_FOUND" / 警告="WARNING_DB_SAFETY"
        "detail": str,  # 状态详情：成功="" / 错误="文件路径不存在" / 警告="操作影响行数超过安全阈值，已自动回滚"
        "hint": str,    # 修正建议：成功="" / 错误="请检查路径是否正确" / 警告="请使用WHERE子句缩小影响范围"
    },
    
    # === 可选字段 ===
    "duration_ms": int, # 执行耗时（毫秒），前端渲染"耗时X秒"，LLM判断是否超时，日志性能分析
    "metrics": dict,    # 关键数字指标（自描述，每个值带文字说明，前端和LLM同等消费，无需外部查表）
                        # 格式：{"键名": {"value": 值, "text": "文字说明"}}
                        # 成功示例：{"lines":{"value":156,"text":"156行"}, "bytes":{"value":2380,"text":"2380字节"}, "encoding":{"value":"utf-8","text":"UTF-8编码"}}
                        # 成功示例：{"exit_code":{"value":0,"text":"退出码0"}}
                        # 成功示例：{"status_code":{"value":200,"text":"HTTP 200"}, "content_type":{"value":"application/json","text":"JSON格式"}}
                        # 成功示例：{"row_count":{"value":5,"text":"5行"}, "columns":{"value":["id","name","email"],"text":"列: id, name, email"}}
                        # 成功示例：{"total":{"value":8,"text":"8条结果"}, "engine":{"value":"Parallel","text":"Parallel引擎"}}
                        # 成功示例：{"deleted":{"value":True,"text":"已永久删除"}, "mode":{"value":"permanent","text":"永久删除"}}
                        # 成功示例：{"bytes_written":{"value":1024,"text":"写入1024字节"}}
                        # 成功示例：{"pages":{"value":5,"text":"5页"}, "chars":{"value":12000,"text":"12000字符"}}
                        # 错误示例：{}
                        # 警告示例：{"affected_rows":{"value":50000,"text":"影响50000行"}, "threshold":{"value":10000,"text":"安全阈值10000"}}
}
```

**metrics自描述设计**：每个值都带`text`文字说明，前端和LLM同等消费，无需外部查表。

**前端渲染**：遍历metrics，直接用text渲染标签。如`"156行 | 2380字节 | UTF-8编码"`。

**LLM消费**：直接看text理解含义，需要精确值时引用value。

**核心架构原则：工具自治，框架不变**

| 角色 | 职责 | 改动范围 |
|------|------|---------|
| 每个tool | 填写自己的llm_data内容（summary/action/status/metrics等具体值） | 只改自己的工具代码 |
| observation流程 | 只认llm_data的6字段结构，遍历渲染，不关心具体值 | 永远不变 |
| 前端 | 按结构渲染（summary做标题，metrics.text做标签，data做详情） | 永远不变 |
| LLM | 按三段式文本理解（观察→结果→详情） | 永远不变 |

**结果**：新增/修改任何tool，只改该tool的llm_data填充逻辑，不影响observation formatter、不影响前端渲染、不影响LLM消费流程。

**结构稳定性保证**：

| 层级 | 结构 | 扩展方式 | 稳定性 |
|------|------|---------|--------|
| llm_data顶层 | summary/action/target/status/duration_ms/metrics | **永不加字段** | 冻结 |
| action | tool/tool_zh/params | 新增工具只扩枚举值 | 冻结 |
| status | exec_code/message/code/detail/hint | **永不加字段** | 冻结 |
| metrics | 自描述dict（value+text） | 新增工具自由加键值对，每个值自带文字说明 | 开放 |

新增工具时：只往action枚举加一个值、往metrics加几个键，**不改llm_data结构定义**。

**ReAct循环中的裁剪规则**：

| 数据 | 是否可裁剪/压缩 | 原因 |
|------|----------------|------|
| llm_data | ❌ **禁止裁剪压缩** | summary/message/action/target/status/duration_ms/metrics是LLM决策的核心上下文，裁剪会导致LLM无法理解结果、无法修正错误 |
| data | ✅ 可以裁剪压缩 | data是大块业务内容（文件内容/命令输出等），ReAct循环中token超限时只裁剪data，如截断content、只保留前N行 |

**裁剪策略**：当observation token超限时，只对data做截断（如`_prevent_json_oom`），llm_data原样保留。LLM始终能看到完整的摘要和状态，只是详情可能被截断。

**各场景字段使用**：

| 字段 | 成功 | 错误 | 警告 |
|------|------|------|------|
| summary | ✅ 结果摘要 | ✅ 错误摘要 | ✅ 警告摘要 |
| action | ✅ | ✅ | ✅ |
| action.tool | "read_text_file" | "read_text_file" | "execute_sql" |
| action.params | {"file_path":"C:\\test.py"} | {"file_path":"C:\\notexist.txt"} | {"sql":"SELECT..."} |
| target | ✅ | ✅ | ✅ |
| status.exec_code | "success" | "error" | "warning" |
| status.message | "读取成功" | "文件不存在" | "影响行数超过安全阈值" |
| status.code | "" | "ERR_FILE_NOT_FOUND" | "WARNING_DB_SAFETY" |
| status.detail | "" | "文件路径不存在" | "操作影响行数超过安全阈值，已自动回滚" |
| status.hint | "" | "请检查路径是否正确" | "请使用WHERE子句缩小影响范围" |
| duration_ms | 150 | 30000 | 200 |
| metrics | ✅ 关键数字 | 通常空 | ✅ 关键数字 |

**status结构设计理由**：

| 字段 | 给谁用 | 说明 |
|------|--------|------|
| exec_code | 前端程序 | 一个字段判断走哪条渲染路径 |
| code | 前端程序 | 按code做精确错误处理（弹特定提示、自动重试等） |
| message | LLM | code的自然语言版本，LLM直接理解（"文件不存在" vs "ERR_FILE_NOT_FOUND"） |
| detail | LLM | 比message更详细的说明，warning场景必填 |
| hint | LLM | 修正建议，LLM据此调整下一步操作 |

**code与message的关系**：code是程序标识，message是code的中文翻译，描述同一件事。程序用code判断，LLM用message理解。

**status.message编写标准**：

每个工具的message必须包含三要素：

| 要素 | 说明 | 示例 |
|------|------|------|
| 操作类型 | 读取/写入/查询/执行/删除/... | "读取"、"写入"、"查询" |
| 关键对象 | 文件路径/表名/命令/URL | "C:\test.py"、"SELECT * FROM users" |
| 关键数字 | 行数/字节数/影响行数/状态码 | "156行"、"2380字节"、"影响5行" |

```python
# ❌ 旧message（没信息量）
message = "执行成功"
message = "读取文件成功"

# ✅ 新message（操作+对象+数字）
message = "读取成功"           # 成功时简短即可，对象和数字在summary里
message = "文件不存在"          # 错误时必须说清原因
message = "影响行数超过安全阈值" # 警告时必须说清原因
```

**注意**：成功时message简短（"读取成功"），因为对象和关键数字已在summary和metrics里；错误/警告时message必须包含足够信息让LLM理解原因。

**action结构各字段用途**：

| 消费方 | 用action.tool还是action.tool_zh | 原因 |
|--------|-------------------------------|------|
| formatter观察行 | action.tool_zh | LLM看中文更直观："读取成功"比"read_text_file success"更清晰 |
| 前端操作标签 | action.tool_zh | 用户看中文 |
| 前端程序逻辑 | action.tool | 程序判断用工具名，精确匹配 |
| 日志/调试 | action.tool | 英文便于检索 |
| LLM调用回溯 | action.params | LM看到"我传了什么参数" |

**为什么要有message？**

| 场景 | message示例 | 作用 |
|------|-----------|------|
| 成功 | "读取成功" | LLM扫一眼就确认结果，无需读summary |
| 错误 | "文件不存在" | 一句话点明错误原因，LLM立即可决策 |
| 警告 | "影响行数超过安全阈值" | 明确风险性质，LLM知道要谨慎处理 |

**为什么metrics是自由dict？**

不同工具的关键数字完全不同（文件有lines/bytes，Shell有exit_code，HTTP有status_code），无法用固定字段覆盖。用自由dict，新增工具只需加键值对，不改结构定义。

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
# ✅ 正确：llm_data有lines（在metrics里），data不放lines
llm_data = {"summary":"读取 C:\\test.py，156行","action":{"tool":"read_text_file","tool_zh":"读取","params":{"file_path":"C:\\test.py"}},"target":"C:\\test.py","status":{"exec_code":"success","message":"读取成功","code":"","detail":"","hint":""},"metrics":{"lines":{"value":156,"text":"156行"},"bytes":{"value":2380,"text":"2380字节"}}}
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
| action.tool | llm_data | — | — | — | 操作标签（英文，程序用） |
| action.tool_zh | llm_data | ✅ "读取成功" | — | — | 操作标签（中文，用户看） |
| action.params | llm_data | — | — | — | — |
| target | llm_data | — | 嵌在summary | — | 目标标签 |
| status.message | llm_data | ✅ "读取成功" | — | — | — |
| summary | llm_data | — | ✅ | — | 卡片标题 |
| status.* | llm_data | ✅ message(显示) + exec_code(路由) | — | — | 状态指示 |
| duration_ms | llm_data | — | — | — | 耗时标签 |
| metrics.* | llm_data | — | 嵌在summary | — | 数字标签 |
| content/output等 | data | — | — | ✅ | 可折叠详情 |

**前端渲染效果**：

```
┌─────────────────────────────────────────┐
│ 📄 读取 C:\test.py                      │  ← summary
│ 读取 | 156行 | 2380字节 | UTF-8          │  ← 从llm_data取action.tool_zh/metrics.text
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
| 观察 | formatter | status.message + action.tool_zh | — |
| 结果 | llm_data | summary | 不重复action（观察已有） |
| 详情 | data | 可读文本（formatter按结构自动格式化） | 不重复action/target/关键数字（观察+结果已有） |

**成功**：
```
观察: {status.message} - {action.tool_zh}
结果: {summary}
详情:
{format_data_detail(data)}
```

**错误**：
```
观察: {status.message} - {action.tool_zh}
结果: {summary}
详情:
{format_data_detail(data)}
建议: {status.hint}
```

**警告**：
```
观察: {status.message} - {action.tool_zh}
⚠ 警告: {status.detail}
结果: {summary}
详情:
{format_data_detail(data)}
建议: {status.hint}
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
观察: 读取成功 - 读取
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情:
def hello():
    print('hi')
    return True
...
```

**LLM的认知路径**：
1. 第一行：成功读取了文件
2. 第二行：156行，2380字节，UTF-8编码 — 关键信息直接可见
3. 第三行：需要具体内容时看详情 — 只有纯业务数据

**与旧方案的关键区别**：详情行只输出data（纯业务数据），不再重复action/target/关键数字

---

### 3.5 统一数据管道：从tool到observation文本

**核心思想**：llm_data是结构化中间态，observation文本是最终产物。整条管道是单向的"结构化数据→渲染→文本"。

**完整流程图**：

```
tool函数执行
  ↓ data + llm_data结构化数据
build_success / build_error / build_warning
  ↓ result = {code, data, message, llm_data}
format_llm_observation(result)
  ├─ llm_data → 观察行(status.message - action.tool_zh)
  ├─ llm_data → 结果行(summary)
  └─ data → 详情行(format_data_detail渲染)
  ↓
三段式observation文本（role=tool, content=文本）
  ↓
发给LLM
```

**各角色职责**：

| 角色 | 所在文件 | 输入 | 输出 | 职责 | 不做什么 |
|------|---------|------|------|------|---------|
| tool函数 | 各tools/*.py | 业务参数 | data + llm_data | 执行业务，填结构化数据 | 不格式化，不渲染 |
| build_*() | tool_response.py | data, llm_data, message... | 统一result dict | 构建标准返回结构 | 不改业务数据内容 |
| format_llm_observation() | observation_formatter.py | result dict | 三段式文本 | 机械渲染：llm_data→观察+结果行，data→详情行 | 不新增信息，不加工语义 |
| LLM | — | observation文本 | 推理决策 | 直接阅读文本 | 不接触结构化数据 |

**数据流向**：

```
结构化数据（llm_data）→ 渲染 → 自然语言文本（observation）
    ↑                               ↑
  build层写入                      formatter层转换
  （工具侧）                        （框架侧）
```

**关键规则**：

1. **机械渲染**：formatter对llm_data只取值拼接，不加工、不新增、不组合——保证LLM看到的和结构化数据内容一致
2. **单向管道**：结构化数据→文本，不存在反向依赖。改了llm_data结构，formatter自动跟随渲染
3. **分层稳定**：工具侧数据变了，formatter渲染逻辑不变；formatter渲染方式变了，工具侧数据不变

**一致性保证**：

| 修改场景 | 需要改什么 | 不改什么 |
|---------|-----------|---------|
| 新增工具 | 唯一：该工具的llm_data填充逻辑 | formatter、build函数、前端渲染 |
| 修改llm_data字段内容 | 唯一：该工具的数据来源 | formatter（机械取值） |
| 修改observation文本格式 | 唯一：formatter渲染逻辑 | 工具侧llm_data、前端 |
| 前端改变展示方式 | 唯一：前端渲染 | 工具侧llm_data、formatter |

### 3.6 实施原则

**原则一：废除现有`llm_data`的旧代码和旧逻辑**

当前代码中散落的`llm_data`填充方式五花八门（有的None、有的partial、有的与data重复），observation_formatter中对`llm_data`的读取逻辑也混杂不清。实施本设计时，**旧的全部废除，全部按新6字段结构重写**，不做向后兼容。

| 废除内容 | 说明 |
|---------|------|
| tool函数中旧的`llm_data`填充（None/空dict/partial） | 统一为完整6字段结构 |
| observation_formatter中旧的`_extract_display_data()`等内容 | 统一为新三段式渲染 |
| message参数承载关键信息的写法 | 关键信息移入llm_data.status.message |

旧代码一律不保留、不兼容、不过渡。

**原则二：用build 3函数实现新的observation文本——`llm_data`字段承载结构化中间态**

build 3函数（build_success / build_error / build_warning）是整个管道的入口。改造后的签名中，`llm_data`字段承载新设计的6字段结构化中间态：

```
result = {
    "data": ...,        # 纯业务大块内容（给前端详情面板）
    "llm_data": {       # ⬅ 结构化中间态：formatter以此渲染observation文本
        "summary": str,
        "action": {"tool": str, "tool_zh": str, "params": dict},
        "target": str,
        "status": {"exec_code": str, "message": str, "code": str, "detail": str, "hint": str},
        "duration_ms": int,       # 可选
        "metrics": {"key": {"value": ..., "text": str}},  # 可选
    },
}
```

**关于字段名`llm_data`**：当前result dict中的字段名保持为`llm_data`，便于与前端的字段引用兼容。实际代码实现时，Python变量名可改写为`toolsummary`或`toolentry`，以更准确地表达"结构化工具结果摘要"的语义。最终选哪个名字在实现时确定，不影响本设计的结构定义。

**原则三：formatter是机械渲染器，不给observation增信**

LLM只读observation文本（三行），不直接读`result` dict。formatter对`llm_data`只做机械取值拼接，不加工、不新增、不组合。

**消费规则**：
| 源字段 | 渲染位置 | 角色 |
|--------|---------|------|
| `llm_data`全部entry | 观察行 + 结果行 | 机械取值，不加工 |
| `data` | 详情行 | `format_data_detail`按类型自动渲染，不改内容 |

**关键约束**：
- LLM看到的observation文本 = `llm_data`全部entry的三段式渲染，不多也不少。
- formatter不承担业务理解、不新增、不组合、不修改内容。
- `data`由`format_data_detail`按数据类型（str/list/dict）机械渲染，不改内容。
- `status.exec_code`仅用于formatter选择成功/错误/警告渲染模板，不给LLM看到原始值。

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

**零重复原则**：同一字段只出现一次，llm_data和data不重复任何信息。

```python
# llm_data（结构化摘要）
llm_data = {"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":{...},"target":"C:\\test.py","status":{...},"metrics":{"lines":{"value":156,"text":"156行"},"bytes":{"value":2380,"text":"2380字节"},"encoding":{"value":"utf-8","text":"UTF-8编码"}}}

# data（纯业务数据）
data = {"content": "def hello():\n    ..."}
```

**禁止**：
- llm_data有lines，data又放lines → 重复
- llm_data有action，data又放action → 重复
- llm_data有bytes，data又放bytes_written → 同义重复

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

### 4.3 data格式化渲染规范

data保持dict（前端需要结构化数据），但formatter输出详情时**转为可读文本**而非JSON dump，LLM直接读无需解析JSON。

**核心原则：工具只管提供结构化data，formatter负责格式化为可读文本**

```python
# ❌ 旧方案：JSON dump，LLM要解析
详情: {"operation_id":"abc","file_path":"C:\\test.py","bytes_read":2380,"content":"def hello():..."}

# ✅ 新方案：可读文本，LLM直接读
详情:
def hello():
    print('hi')
    return True
...
```

**职责分离**：

| 角色 | 职责 | 不做什么 |
|------|------|---------|
| 工具 | 提供结构化data（dict） | 不做格式化，不输出文本 |
| formatter | 按data结构类型自动格式化为可读文本 | 不改data内容，只改渲染方式 |
| 前端 | 直接消费原始data（dict） | 不依赖formatter的文本 |

#### 4.3.1 格式化分派规则

| data结构 | 格式化方式 | 输出示例 |
|----------|-----------|---------|
| `{"content": str}` | 原样输出文本 | `def hello():\n    print('hi')` |
| `{"content": {"headers": list, "rows": list}}` | 表格格式 | `id=1 | name=Alice | email=a@t.com` |
| `{"entries": list}` | 列表格式 | `src/ [目录]\nREADME.md [文件, 2048字节]` |
| `{"items": list}` | 编号列表 | `[1] 标题 - 摘要...\n[2] 标题 - 摘要...` |
| `{"rows": list}` | 表格格式 | `id=1 | name=Alice | email=a@t.com` |
| `{"tables": dict}` | Markdown表格 | `## users\n|字段|类型|主键|\n|id|INTEGER|是|` |
| `{"cpu": dict, "memory": dict, ...}` | 键值对格式 | `CPU: 12核, 已用45%\n内存: 16GB, 已用50%` |
| `{"events": list}` | 编号列表 | `[1] 2026-06-20 10:30 | Error | Application` |
| `{"output": str, "error_output": str}` | 原样输出 | Shell输出原样 |
| `{}` | 跳过详情行 | 无详情行 |
| `{"error_detail": str, "params": dict}` | 键值对格式 | `错误: 文件路径不存在\n参数: encoding=utf-8` |

#### 4.3.2 格式化函数设计

**工具不需要实现格式化**——只管提供结构化data，formatter按data结构类型自动分派渲染。

```python
def format_data_detail(data: dict) -> str:
    """按data结构类型自动格式化为可读文本"""
    if not data:
        return ""
    
    # 表格类：content含headers+rows
    if "content" in data and isinstance(data["content"], dict) and "headers" in data["content"]:
        return _format_table(data["content"]["headers"], data["content"]["rows"])
    
    # 纯文本类：content是字符串
    if "content" in data and isinstance(data["content"], str):
        return data["content"]
    
    # 目录列表类
    if "entries" in data:
        return _format_entries(data["entries"])
    
    # 搜索结果类
    if "items" in data:
        return _format_items(data["items"])
    
    # 数据库行类
    if "rows" in data:
        return _format_rows(data["rows"])
    
    # Schema类
    if "tables" in data:
        return _format_schema(data["tables"])
    
    # Shell输出类
    if "output" in data:
        parts = []
        if data["output"]:
            parts.append(data["output"])
        if data.get("error_output"):
            parts.append(f"[stderr] {data['error_output']}")
        return "\n".join(parts)
    
    # 事件日志类
    if "events" in data:
        return _format_events(data["events"])
    
    # 键值对类（系统信息/错误详情等）
    return _format_key_value(data)
```

#### 4.3.3 格式化效果对比

**数据库查询**：
```
# JSON dump（LLM要解析）
详情: {"rows":[[1,"Alice","a@t.com"],[2,"Bob","b@t.com"]]}

# 可读文本（LLM直接读）
详情:
id=1 | name=Alice | email=a@t.com
id=2 | name=Bob | email=b@t.com
```

**目录列表**：
```
# JSON dump
详情: {"entries":["src/","README.md","package.json"]}

# 可读文本
详情:
  src/ [目录]
  README.md [文件, 2048字节]
  package.json [文件, 1024字节]
```

**系统信息**：
```
# JSON dump
详情: {"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50}}

# 可读文本
详情:
  CPU: 12核, 已用45%
  内存: 16GB, 已用50%
  磁盘 C:: 500GB, 已用60%
```

**新增工具时**：只要遵循data结构规范（4.2节），formatter自动渲染，无需写格式化代码。

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

# 规范后（零重复，action/target/status在llm_data）
build_error(ERR_FILE_NOT_FOUND, 
    data={"error_detail": "文件路径不存在", "params": {"encoding": "utf-8"}},
    llm_data={"summary":"文件 D:/test.txt 不存在","action":{"tool":"read_text_file","tool_zh":"读取","params":{"file_path":"D:/test.txt"}},"target":"D:/test.txt","status":{"exec_code":"error","message":"文件不存在","code":"ERR_FILE_NOT_FOUND","detail":"文件路径不存在","hint":"请检查路径是否正确"}}
)
```

---

## 五、llm_data统一格式规范

### 5.1 llm_data定位

**llm_data = 结构化摘要（唯一持有summary/action/target/status/metrics）**

| 角色 | 消费方式 | 说明 |
|------|---------|------|
| **LLM** | 通过"结果"行消费summary | summary包含action/target/metrics的文字描述 |
| **前端** | 渲染摘要卡片 | summary做标题，tool_zh做操作标签，metrics.text做数字标签 |
| **formatter** | 机械渲染llm_data全部entry | 三段式observation文本：观察行+结果行+详情行 |

**data不再重复llm_data已有的任何字段**（零重复原则）。

### 5.2 llm_data完整结构（6顶层字段，冻结）

```python
llm_data = {
    # === 必填 ===
    "summary": str,     # 自然语言摘要（"读取 C:\test.py，156行，2380字节，UTF-8编码"）
    "action": {         # 操作类型（结构冻结）
        "tool": str,    # function name（"read_text_file"）
        "tool_zh": str, # 中文操作类型（"读取"）
        "params": dict, # LLM调用参数（{"file_path":"C:\\test.py"}）
    },
    "target": str,      # 操作目标（路径/URL/查询词/命令）
    "status": {         # 执行状态（结构冻结）
        "exec_code": str,   # "success" / "error" / "warning"
        "message": str,     # 状态文字（code的中文翻译，LLM直接消费）
        "code": str,        # 状态码（程序用），成功="" / 错误="ERR_FILE_NOT_FOUND"
        "detail": str,      # 状态详情，成功="" / 错误="文件路径不存在"
        "hint": str,        # 修正建议，成功="" / 错误="请检查路径是否正确"
    },
    
    # === 可选 ===
    "duration_ms": int, # 执行耗时（毫秒）
    "metrics": dict,    # 关键数字（自描述，每个值带文字说明）
                        # 格式：{"键名": {"value": 值, "text": "文字说明"}}
}
```

#### 5.2.1 字段定义

| 顶层字段 | 必填 | 类型 | 说明 |
|---------|------|------|------|
| `summary` | ✅ | str | 自然语言摘要，见5.2.2格式规范 |
| `action` | ✅ | dict | 操作类型，见action子字段表 |
| `target` | ✅ | str | 操作目标，见5.2.3取值规则 |
| `status` | ✅ | dict | 执行状态，见status子字段表 |
| `duration_ms` | ❌ | int | 执行耗时（毫秒） |
| `metrics` | ❌ | dict | 关键数字，自描述格式 `{"key": {"value": ..., "text": "..."}}` |

**action子字段**（结构冻结，不可增删）：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `tool` | str | function name，如 `"read_text_file"` |
| `tool_zh` | str | 中文操作类型，如 `"读取"` |
| `params` | dict | LLM调用参数，如 `{"file_path":"C:\\test.py"}` |

**status子字段**（结构冻结，不可增删）：

| 子字段 | 类型 | success | error | warning |
|--------|------|---------|-------|---------|
| `exec_code` | str | `"success"` | `"error"` | `"warning"` |
| `message` | str | `"读取成功"` | `"文件不存在"` | `"数据量过大已截断"` |
| `code` | str | `""` | `"ERR_FILE_NOT_FOUND"` | `"WARNING_DATA_TRUNCATED"` |
| `detail` | str | `""` | `"文件路径不存在"` | `"返回结果超过1000条，已截断"` |
| `hint` | str | `""` | `"请检查路径是否正确"` | `"建议增加条件缩小范围"` |

#### 5.2.2 summary格式规范

格式：`{操作} {对象}，{关键数字1}，{关键数字2}`

```python
"读取 C:\\test.py，156行，2380字节，UTF-8编码"
"写入 C:\\output.docx，3段落/500字"
"查询返回5行，列: id, name, email"
"搜索到8条结果(Parallel引擎)"
"删除 C:\\temp.log，已永久删除"
```

**规范要求**：
- 以`{操作类型}`开头（与tool_zh一致）
- `{对象}`即target值
- 关键数字用逗号分隔，与metrics.text内容一致
- 整句自然流畅，LLM扫一眼即知核心信息

#### 5.2.3 target取值规则

| 场景 | target值 | 示例 |
|------|---------|------|
| 文件操作 | 文件/目录的绝对路径 | `"C:\\test.py"` |
| 网络请求 | URL | `"https://api.example.com/users"` |
| Shell命令 | 命令摘要（前80字符） | `"node build.js --production"` |
| 系统信息 | 查询类型 | `"cpu"` |
| 数据库查询 | SQL摘要或表名 | `"SELECT * FROM users"` |
| 桌面操作 | 操作类型 | `"click"` / `"记事本"` |
| 事件日志 | 日志源 | `"System"` |
| 无主体操作 | 空字符串 | `""` |

#### 5.2.4 status.message编写标准

格式：`{操作类型}{结果}`，简短自然，LLM一眼就懂。

```python
# 成功
"读取成功" / "写入成功" / "删除成功" / "搜索完成" / "执行成功"

# 错误
"文件不存在" / "SQL语法错误" / "请求超时" / "权限不足"

# 警告
"影响行数超过安全阈值" / "数据量过大已截断"
```

### 5.3 禁止

| 禁止行为 | 错误示例 | 正确做法 | 后果 |
|---------|---------|---------|------|
| 把原始大块内容放入llm_data | `llm_data["content"]=文件全文` | 大块内容放data，llm_data只放摘要 | content长达MB级，污染LLM上下文 |
| llm_data字段用中文key | `llm_data["文件名"]=...` | 必须用英文key | 前端和formatter无法解析 |
| 违反零重复原则 | llm_data有lines，data也放lines | 同一字段只出现一次 | 数据不一致，LLM困惑 |
| 关键数字用裸值 | `"lines": 156` | 必须用自描述格式 `{"value":156,"text":"156行"}` | 前端无法渲染数字标签 |
| 跳过一个必填字段 | 缺少`action`或`status` | 6字段必须完整 | formatter渲染报错 |
| 自己拼llm_data dict | 各tool自己构造dict | 必须通过build 3函数构建 | 格式不统一，校验缺失 |

### 5.4 各工具类型的llm_data规范参考

以下为各工具类型的关键llm_data字段规范。完整代码示例见第六章。

#### 5.4.1 文件操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| read_text_file | 读取 | 文件路径 | lines, bytes, encoding | 读取 C:\test.py，156行，2380字节，UTF-8编码 |
| write_text_file | 写入 | 文件路径 | bytes_written | 写入 C:\output.txt，50行/1024字节 |
| write_docx | 写入 | 文件路径 | bytes_written, content_summary | 写入 C:\report.docx，3段落/500字 |
| write_xlsx | 写入 | 文件路径 | bytes_written, content_summary | 写入 C:\data.xlsx，10行×5列 |
| list_directory | 列出 | 目录路径 | total, truncated | 列出 C:\project\，156个文件/目录 |
| copy_file | 复制 | source→destination | bytes | 复制 C:\a.txt → C:\b.txt，1024字节 |
| delete_file | 删除 | 文件路径 | deleted, mode | 删除 C:\temp.log，已永久删除 |
| search_files | 搜索 | 搜索目录 | count, matches | 搜索到3个文件: a.py, b.py, c.py |
| file_media | 读取 | 文件路径 | mime_type, size | 读取 img.png，image/png，100KB |

#### 5.4.2 数据库操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| query_sql | 查询 | SQL摘要 | row_count, columns | 查询返回5行，列: id, name, email |
| execute_sql | 执行 | SQL摘要 | affected_rows | SQL执行成功，影响5行 |
| get_db_schema | 获取 | "database" | total | 获取到3个表的结构: users, orders, products |

#### 5.4.3 文档操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| read_pdf | 读取 | 文件路径 | pages, chars | 读取 C:\report.pdf，5页，12000字符 |

#### 5.4.4 网络/搜索操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| search_web | 搜索 | 搜索词 | total, engine | 搜索到8条结果(Parallel引擎) |
| http_request | 请求 | URL | status_code, content_type, body_len | HTTP GET https://api.example.com，200，15KB |

#### 5.4.5 Shell执行

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| execute_shell | 执行 | 命令摘要 | exit_code | 命令执行完成，退出码0 |

#### 5.4.6 系统操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| get_system_info | 获取 | info_type | 各指标平铺 | CPU: 8核/45% |
| get_event_log | 查询 | 日志源 | count, level | System日志: 15条错误 |
| list_processes | 列出 | "all" | count | 当前120个进程 |
| list_services | 列出 | "all" | count | 当前80个服务 |
| reboot_system | 重启 | "scheduled" | delay | 系统计划60秒后重启 |

#### 5.4.7 桌面操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| screenshot | 截图 | 文件路径 | size, width, height | 截图已保存，512KB，1920×1080 |
| mouse_click | 点击 | "click" | x, y, button | 鼠标点击 (100,200) 左键 |
| keyboard_type | 输入 | "type" | text | 输入文本 "hello" |
| window_control | 操作 | 窗口标题 | action, x, y, w, h | 移动窗口"记事本"到 (0,0) |

#### 5.4.8 注册表操作

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| registry_read | 读取 | 注册表路径 | value, type | 读取 HKLM\...\key，REG_SZ |
| registry_write | 写入 | 注册表路径 | type | 写入 HKLM\...\key，REG_SZ |
| registry_delete | 删除 | 注册表路径 | — | 删除 HKLM\...\key |

#### 5.4.9 基础工具

| 工具 | tool_zh | target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| ask_question | 询问 | "question"/"confirm" | — | 询问用户确认 |
| finish | 完成 | "success"/"failed" | reason | 任务完成 |
| think | 思考 | "" | thought | 思考中... |
| execute_code | 执行 | 语言 | exit_code, stdout, stderr | Python代码执行完成，退出码0 |
| get_current_time | 获取 | "local"/"utc" | datetime, timezone | 当前时间 2026-06-20 15:30:00(Asia/Shanghai) |

### 5.5 metrics自描述规范

每个值都带`text`文字说明，前端和LLM同等消费，无需外部查表。

```python
# 文件类
"metrics": {"lines": {"value": 156, "text": "156行"},
            "bytes": {"value": 2380, "text": "2380字节"},
            "encoding": {"value": "utf-8", "text": "UTF-8编码"}}

# 数据库类
"metrics": {"row_count": {"value": 5, "text": "5行"},
            "columns": {"value": ["id","name","email"], "text": "列: id, name, email"}}

# 网络类
"metrics": {"total": {"value": 8, "text": "8条结果"},
            "engine": {"value": "Parallel", "text": "Parallel引擎"}}

# Shell类
"metrics": {"exit_code": {"value": 0, "text": "退出码0"}}

# 删除类
"metrics": {"deleted": {"value": True, "text": "已永久删除"},
            "mode": {"value": "permanent", "text": "永久删除"}}
```

### 5.6 前端渲染示例

```
┌──────────────────────────────────────────────┐
│ 📄 读取 C:\test.py                           │  ← summary
│ 读取 | 156行 | 2380字节 | UTF-8               │  ← action.tool_zh + metrics.text
│                                    [展开详情▼] │  ← 可折叠data
└──────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────┐
│ 🔍 搜索到8条结果(Parallel引擎)                │  ← summary
│ 搜索 | 8条结果 | Parallel引擎                  │  ← action.tool_zh + metrics.text
│                                    [展开详情▼] │
└──────────────────────────────────────────────┘
```

### 5.7 llm_data全覆盖

**所有工具必须有llm_data**（当前8/10有，2/10没有）。这是强制规范。

### 5.8 给LLM的message组装过程及样式

**简要流程**：tool函数 → build 3函数构建result → observation文本 → FC协议消息对 → conversation_history → 发给LLM

```
tool函数执行
  ↓
build_success(data=..., llm_data=...)   # tool_response.py — 构建result dict
build_error(code=..., data=..., llm_data=...)    # result = {data, llm_data}
build_warning(code=..., data=..., llm_data=...)
  ↓
result = {"data": ..., "llm_data": {...}}  # ← llm_data在这里填入
  ↓
format_llm_observation(result)          # observation_formatter.py — 从result取llm_data和data，生成observation文本
  ↓
message_builder.add_observation()       # message_builder.py — 追加两条FC协议消息
  ↓                                       消息1: role=assistant, 带tool_calls
  ↓                                       消息2: role=tool, content=observation文本
conversation_history                    # 累积所有轮次的消息
  ↓
prepare_messages_for_llm()              # 合并后发给LLM
```

**关键函数**：

| 函数 | 文件 | 职责 |
|------|------|------|
| `build_success/error/warning()` | tool_response.py | tool函数调用，构建result dict（含llm_data） |
| `format_llm_observation()` | observation_formatter.py | result → observation文本（从result取llm_data和data） |
| `build_observation_text()` | message_utils.py | 桥接，调用format_llm_observation |
| `MessageBuilder.add_observation()` | message_builder.py | observation文本 → FC协议消息对 |
| `MessageBuilder.prepare_messages_for_llm()` | message_builder.py | conversation_history → 发给LLM的messages |

**llm_data和data在流程中的位置**：

```
build_success(data={"content":"..."}, llm_data={"summary":"...","action":{...},"status":{...},"metrics":{...}})
  ↓
result = {"data": {"content":"..."}, "llm_data": {"summary":"...","action":{...},"status":{...},"metrics":{...}}}
  ↓                        ↑ data在这里          ↑ llm_data在这里
format_llm_observation(result)
  ├─ 从result["llm_data"]取 → 生成"观察"行和"结果"行
  └─ 从result["data"]取     → 生成"详情"行（format_data_detail渲染）
  ↓
observation文本 = "观察: 读取成功 - 读取\n结果: 读取 C:\test.py，156行\n详情:\ndef hello():..."
```

**当前代码的observation文本样式**（改造前）：

```
[Observation] success - 读取文件成功
【摘要】 action=read | file_path=C:\test.py | bytes_read=2380
【数据】 {"operation_id":"abc123","file_path":"C:\\test.py","bytes_read":2380,"encoding":"utf-8","line_count":156,"content":"def hello():\n    ..."}
```

问题：`【摘要】`和`【数据】`字段重复（file_path、bytes_read出现两次），`【数据】`是JSON dump LLM需解析。

**新设计的observation文本样式**（改造后）：

```
观察: 读取成功 - 读取
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情:
def hello():
    print('hi')
    return True
...
```

改进：三层（观察/结果/详情）零重复，详情是可读文本LLM直接读。

**最终发给LLM的message样式**（改造后，一轮完整ReAct循环）：

```python
[
    {"role": "system",  "content": "你是一个智能助手..."},
    {"role": "user",    "content": "请读取C:\\test.py"},

    # LLM返回tool_calls
    {"role": "assistant",
     "content": None,
     "tool_calls": [{"id": "call_abc123", "type": "function",
                     "function": {"name": "read_text_file",
                                  "arguments": "{\"file_path\":\"C:\\\\test.py\"}"}}]},

    # observation文本作为tool消息（改造后）
    {"role": "tool", "tool_call_id": "call_abc123",
     "content": "观察: 读取成功 - 读取\n结果: 读取 C:\\test.py，156行，2380字节，UTF-8编码\n详情:\ndef hello():\n    print('hi')\n    return True\n..."},

    # LLM根据observation继续推理或回答
    {"role": "assistant", "content": "文件内容是..."},
]
```

**observation文本三种场景模板**：

| 场景 | content内容 |
|------|------------|
| 成功 | `观察: {status.message} - {action.tool_zh}\n结果: {summary}\n详情:\n{format_data_detail(data)}` |
| 错误 | `观察: {status.message} - {action.tool_zh}\n结果: {summary}\n详情:\n{format_data_detail(data)}\n建议: {status.hint}` |
| 警告 | `观察: {status.message} - {action.tool_zh}\n⚠ 警告: {status.detail}\n结果: {summary}\n建议: {status.hint}` |

**关键点**：observation文本是tool消息的content，LLM直接阅读这段文本理解工具结果，无需解析JSON。

---
### 5.9 Phase:1  按照新的LLMdata和data 构建给LLM message的改造工作主要工作项目
1.去掉 现在代码的LLMdata的 相关代码和逻辑
2. 实现新的3build3函数 加新的参数 tool data--tool的执行返回的原始数据
3. 重写build3函数  按照新的LLMdata 数据结构 构建所有知道字段?
4. `format_llm_observation`函数里面调用#### 4.3.2 格式化函数设计的格式化函数 输出格式化的data给LLM的message


### 5.10 phase 2：`format_llm_observation` 签名改为 `(data, llm_data)`

#### 5.10.1 动机

当前 `format_llm_observation(result)` 从 result dict 里用 `result.get("data")` 和 `result.get("llm_data")` 分别提取两个字段。虽然 build 3 函数返回的 result 同时包含 data 和 llm_data，但 formatter 只需要这两个字段——它不关心 result 里的 code/message。

改签名后语义更清晰：`data` 是可选的大块内容，`llm_data` 是必填的结构化摘要，签名直接体现。

#### 5.10.2 改动内容

| 改动 | 当前 | Phase 2 |
|------|------|---------|
| **build 3 函数** | `build_success(data=..., llm_data=...)` → result={data, llm_data} | **不动**，保持原样 |
| **result dict** | `{"data": ..., "llm_data": {...}}` | **不动** |
| **format_llm_observation 签名** | `format_llm_observation(result)` | `format_llm_observation(data, llm_data)` |
| **build_observation_text（桥接层）** | 传 exec_result dict 进 formatter | 拆包：`format_llm_observation(result["data"], result["llm_data"])` |
| **formatter 内部逻辑** | `result.get("data")`, `result.get("llm_data")` | 直接使用参数，逻辑不变 |

#### 5.10.3 数据流

```
build_success(data=..., llm_data=...)
  ↓
result = {"data": ..., "llm_data": {...}}   ← build 3 函数不动，data 仍在 result 里
  ↓
build_observation_text(result)
  ↓ 拆包
format_llm_observation(result["data"], result["llm_data"])
  ├─ data     → 详情行（format_data_detail渲染）
  └─ llm_data → 观察行 + 结果行
```

#### 5.10.4 受影响文件

| 文件 | 改动 |
|------|------|
| `observation_formatter.py` | `format_llm_observation` 签名改 `(data, llm_data)`，内部 `result.get("data")` 改为参数 `data` |
| `message_utils.py` | `build_observation_text` 拆包传参 |
| `tool_response.py` | **不改** |
| 所有 tool 文件（30+个） | **不改** |

#### 5.10.5 注意事项

- `data` 可能为 None → formatter 内部判断 `if data is None: skip detail line`
- 这只是签名层面的重构，不改变数据流和前端逻辑
- 改动量小，适合作为 Phase 2 独立上线

---

### 5.11 Phase 3：ToolStep 瘦身 + Observation step 承载全部信息

#### 5.12.1 动机

Phase 2 虽然优化了 formatter 签名，但 ToolStep 和 SSE 通道仍然混杂。ToolStep 的 `execution_result` 同时承载了 llm_data（给前端卡片）和 data（给详情面板），职责不单一。Observation step 只含文本，前端需要的信息分散在两个事件中。

Phase 3 将 ToolStep 和 Observation step 的职责彻底分开：

| 事件 | 职责 | 承载内容 |
|------|------|---------|
| **ToolStep** | 告诉前端"工具执行完成" | 仅 `duration_ms` |
| **Observation step** | 告诉前端"工具结果是什么" | `observation_text` + `llm_data` + `tool_result` |

#### 5.11.2 改动内容

| 维度 | 当前 | Phase 3 |
|------|------|---------|
| **build 3 函数** | `result={data, llm_data}` | **不动** |
| **ToolStep** | `execution_result` 含 data + llm_data + duration_ms | `execution_result = {duration_ms}`，仅完成时间 |
| **Observation step** | 只含 `observation_text` | 新增 `tool_result` 字段（承载原 data）+ 已有 `llm_data` |
| **SSE ToolStep 事件** | 发送完整 execution_result | 只发 `{duration_ms}`，code/message/data/llm_data 都不发 |
| **SSE Observation 事件** | 只发 observation_text | 发 `{observation_text, llm_data, tool_result}` |
| **前端消费** | `ToolStep.execution_result.data` → 详情面板 | `Observation.tool_result` → 详情面板 |
| **前端消费** | `ToolStep.execution_result.llm_data` → 卡片 | `Observation.llm_data` → 卡片 |

#### 5.11.3 新数据流

```
tool 函数执行
  ↓
build_success(data=..., llm_data=...)    ← 不动，仍然返回 {data, llm_data}
  ↓
result = {"data": ..., "llm_data": {...}}
  ↓                       ↓
ToolStep                  build_observation_text(result)
execution_result            ↓
  = {duration_ms}       format_llm_observation(data, llm_data)
  ↓                         ↓
SSE: 仅完成时间         observation_text
  ↓                         ↓
前端: 知道"执行完毕"    Observation SSE 事件
                          ├─ observation_text
                          ├─ llm_data        ← 前端渲染卡片
                          └─ tool_result     ← 前端渲染详情面板（原 data）
```

#### 5.11.4 受影响文件

| 层 | 文件 | 改动 |
|----|------|------|
| **构建层** | `tool_response.py` | **不动** |
| **格式化层** | `observation_formatter.py` | Phase 2 已改 `(data, llm_data)`，Phase 3 不动 |
| **桥接层** | `message_utils.py` | Phase 2 已拆包，Phase 3 不动 |
| **步骤模型** | `ToolStep` | `execution_result` 只存 `duration_ms` |
| **步骤模型** | Observation step 模型 | 新增 `tool_result` 字段 |
| **编排层** | `action_handler.py` | 构建 Observation step 时传入 data（作为 tool_result）|
| **SSE 层** | `run_sse_stream.py` | 调整 SSE 事件构造逻辑 |
| **前端** | 消费 ToolStep 的代码 | 改为从 Observation 事件取值 |
| **DB 存储** | `save_execution_steps_to_db` | 适配新结构 |

#### 5.11.5 实施要点

1. **ToolStep 瘦身**：`_execution_result` 只保留 `{"duration_ms": execution_time}`，不再接收完整的 result dict。

2. **Observation step 新增 tool_result**：在 `action_handler.py` 的 `build_observation()` 中，把 result["data"] 作为 `tool_result` 字段传入 Observation step。

3. **SSE 发送调整**：
   - ToolStep SSE → `{"step_type": "action_tool", "duration_ms": N}`，不发 code/message/data/llm_data
   - Observation SSE → `{"step_type": "observation", "observation_text": "...", "llm_data": {...}, "tool_result": {...}}`

4. **前端适配**：
   - ToolStep 事件 → 只用于显示"工具执行中..."状态，不再从中取数据
   - Observation 事件 → 从中取 `llm_data` 渲染摘要卡片，取 `tool_result` 渲染详情面板

#### 5.11.6 注意事项

| 注意点 | 说明 |
|--------|------|
| **前后端同步** | Phase 3 必须前后端同步上线，不能分步部署 |
| **DB 兼容** | 旧记录中 execution_result 含 data，新记录不含，前端需判断兼容 |
| **data 为空** | tool_result=None 时，前端跳过详情面板渲染 |
| **LLM 不受影响** | LLM 始终只读 observation_text，底层事件结构变化不影响它 |
| **Phase 2 为前提** | Phase 3 依赖 Phase 2 的 formatter 签名改造，必须先上线 Phase 2 |

---

## 六、各工具类型完整示例

### 6.1 文件操作

**read_text_file 成功**：
```python
build_success(
    data={"content":"def hello():\n    ..."},
    llm_data={
        "summary": "读取 C:\\test.py，156行，2380字节，UTF-8编码",
        "action": {"tool": "read_text_file", "tool_zh": "读取", "params": {"file_path": "C:\\test.py", "encoding": "utf-8"}},
        "target": "C:\\test.py",
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"lines": {"value": 156, "text": "156行"}, "bytes": {"value": 2380, "text": "2380字节"}, "encoding": {"value": "utf-8", "text": "UTF-8编码"}},
    },
)
```
输出：
```
观察: 读取成功 - 读取
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情:
def hello():
    print('hi')
    return True
...
```

**llm_data各字段去向说明**：
| llm_data字段 | LLM看到 | 前端看到 | 说明 |
|---|---|---|---|
| summary | 结果行（自然语言） | 摘要卡片标题 | 已包含target/关键数字的文字描述 |
| action.tool | 观察行可选 | 操作标识 | function name |
| action.tool_zh | 观察行 | 操作类型标签 | "读取" |
| action.params | — | — | LLM调用参数，前端按需展示 |
| target | 嵌在summary里 | 目标标签 | "C:\test.py" |
| status.message | 观察行 | 状态指示器 | "读取成功" |
| metrics.*.text | 嵌在summary里 | 结构化标签 | "156行 | 2380字节 | UTF-8" |

**write_text_file 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "写入 C:\\output.txt，50行/1024字节",
        "action": {"tool": "write_text_file", "tool_zh": "写入", "params": {"file_path": "C:\\output.txt"}},
        "target": "C:\\output.txt",
        "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"bytes_written": {"value": 1024, "text": "写入1024字节"}},
    },
)
```
```
观察: 写入成功 - 写入
结果: 写入 C:\output.txt，50行/1024字节
```

**list_directory 成功**：
```python
build_success(
    data={"entries":["src/","README.md",...]},
    llm_data={
        "summary": "列出 C:\\project\\，156个文件/目录",
        "action": {"tool": "list_directory", "tool_zh": "列出", "params": {"path": "C:\\project\\"}},
        "target": "C:\\project\\",
        "status": {"exec_code": "success", "message": "列出成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"total": {"value": 156, "text": "156个文件/目录"}, "truncated": {"value": False, "text": "完整列表"}},
    },
)
```
```
观察: 列出成功 - 列出
结果: 列出 C:\project\，156个文件/目录
详情:
  src/ [目录]
  README.md [文件, 2048字节]
  package.json [文件, 1024字节]
```

**copy_file 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "复制 C:\\a.txt → C:\\b.txt，1024字节",
        "action": {"tool": "copy_file", "tool_zh": "复制", "params": {"source": "C:\\a.txt", "destination": "C:\\b.txt"}},
        "target": "C:\\a.txt → C:\\b.txt",
        "status": {"exec_code": "success", "message": "复制成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"bytes": {"value": 1024, "text": "1024字节"}},
    },
)
```
```
观察: 复制成功 - 复制
结果: 复制 C:\a.txt → C:\b.txt，1024字节
```

**delete_file 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "删除 C:\\temp.log，已永久删除",
        "action": {"tool": "delete_file", "tool_zh": "删除", "params": {"file_path": "C:\\temp.log"}},
        "target": "C:\\temp.log",
        "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"deleted": {"value": True, "text": "已永久删除"}, "mode": {"value": "permanent", "text": "永久删除"}},
    },
)
```
```
观察: 删除成功 - 删除
结果: 删除 C:\temp.log，已永久删除
```

**delete_file 幂等（文件不存在）**：
```python
build_success(
    data={},
    llm_data={
        "summary": "删除 C:\\temp.log，文件已不存在(幂等)",
        "action": {"tool": "delete_file", "tool_zh": "删除", "params": {"file_path": "C:\\temp.log"}},
        "target": "C:\\temp.log",
        "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"deleted": {"value": False, "text": "文件已不存在(幂等)"}, "mode": {"value": "already_gone", "text": "无需删除"}},
    },
)
```
```
观察: 删除成功 - 删除
结果: 删除 C:\temp.log，文件已不存在(幂等)
```

### 6.2 数据库工具

**query_sql 成功**：
```python
build_success(
    data={"rows":[[1,"Alice","a@t.com"],...]},
    llm_data={
        "summary": "查询返回5行，列: id, name, email",
        "action": {"tool": "query_sql", "tool_zh": "查询", "params": {"sql": "SELECT * FROM users"}},
        "target": "SELECT * FROM users",
        "status": {"exec_code": "success", "message": "查询成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"row_count": {"value": 5, "text": "5行"}, "columns": {"value": ["id","name","email"], "text": "列: id, name, email"}},
    },
)
```
```
观察: 查询成功 - 查询
结果: 查询返回5行，列: id, name, email
详情:
id=1 | name=Alice | email=a@t.com
id=2 | name=Bob | email=b@t.com
```

**execute_sql 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "SQL执行成功，影响5行",
        "action": {"tool": "execute_sql", "tool_zh": "执行", "params": {"sql": "UPDATE users SET ..."}},
        "target": "UPDATE users SET ...",
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"affected_rows": {"value": 5, "text": "影响5行"}},
    },
)
```
```
观察: 执行成功 - 执行
结果: SQL执行成功，影响5行
```

**get_db_schema 成功**：
```python
build_success(
    data={"tables":{"users":"...","orders":"...","products":"..."}},
    llm_data={
        "summary": "获取到3个表的结构: users, orders, products",
        "action": {"tool": "get_db_schema", "tool_zh": "获取", "params": {}},
        "target": "database",
        "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"total": {"value": 3, "text": "3个表"}},
    },
)
```
```
观察: 获取成功 - 获取
结果: 获取到3个表的结构: users, orders, products
详情:
## users
|字段|类型|主键|
|id|INTEGER|是|
...
```

### 6.3 文档工具

**read_pdf 成功**：
```python
build_success(
    data={"content":"PDF文本..."},
    llm_data={
        "summary": "读取 C:\\report.pdf，5页，12000字符",
        "action": {"tool": "read_pdf", "tool_zh": "读取", "params": {"file_path": "C:\\report.pdf"}},
        "target": "C:\\report.pdf",
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"pages": {"value": 5, "text": "5页"}, "chars": {"value": 12000, "text": "12000字符"}},
    },
)
```
```
观察: 读取成功 - 读取
结果: 读取 C:\report.pdf，5页，12000字符
详情:
PDF文本...
```

**write_docx 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "写入 C:\\report.docx，3段落/500字",
        "action": {"tool": "write_docx", "tool_zh": "写入", "params": {"file_path": "C:\\report.docx"}},
        "target": "C:\\report.docx",
        "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"bytes_written": {"value": 2048, "text": "写入2048字节"}, "content_summary": {"value": "3段落/500字", "text": "3段落/500字"}},
    },
)
```
```
观察: 写入成功 - 写入
结果: 写入 C:\report.docx，3段落/500字
```

**write_xlsx 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "写入 C:\\data.xlsx，10行×5列",
        "action": {"tool": "write_xlsx", "tool_zh": "写入", "params": {"file_path": "C:\\data.xlsx"}},
        "target": "C:\\data.xlsx",
        "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"bytes_written": {"value": 512, "text": "写入512字节"}, "content_summary": {"value": "10行×5列", "text": "10行×5列"}},
    },
)
```
```
观察: 写入成功 - 写入
结果: 写入 C:\data.xlsx，10行×5列
```

### 6.4 网络工具

**search_web 成功**：
```python
build_success(
    data={"items":[...]},
    llm_data={
        "summary": "搜索到8条结果(Parallel引擎)",
        "action": {"tool": "search_web", "tool_zh": "搜索", "params": {"query": "低空星链通信 2026"}},
        "target": "低空星链通信 2026",
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "metrics": {"total": {"value": 8, "text": "8条结果"}, "engine": {"value": "Parallel", "text": "Parallel引擎"}},
    },
)
```
```
观察: 搜索完成 - 搜索
结果: 搜索到8条结果(Parallel引擎)
详情:
[1] 标题 - 摘要...
[2] 标题 - 摘要...
```

**http_request 成功**：
```python
build_success(
    data={"body":"..."},
    llm_data={
        "summary": "HTTP GET https://api.example.com，状态码200，响应体15000字符",
        "action": {"tool": "http_request", "tool_zh": "请求", "params": {"url": "https://api.example.com", "method": "GET"}},
        "target": "https://api.example.com",
        "status": {"exec_code": "success", "message": "请求成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"status_code": {"value": 200, "text": "HTTP 200"}, "content_type": {"value": "application/json", "text": "JSON格式"}},
    },
)
```
```
观察: 请求成功 - 请求
结果: HTTP GET https://api.example.com，状态码200，响应体15000字符
详情:
{"status":"ok","data":[...]}
```

**download_file 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "下载完成，102400字节，保存到 C:\\download\\file.zip",
        "action": {"tool": "download_file", "tool_zh": "下载", "params": {"url": "https://example.com/file.zip"}},
        "target": "https://example.com/file.zip",
        "status": {"exec_code": "success", "message": "下载成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"bytes": {"value": 102400, "text": "102400字节"}, "file_path": {"value": "C:\\download\\file.zip", "text": "保存到 C:\\download\\file.zip"}},
    },
)
```
```
观察: 下载成功 - 下载
结果: 下载完成，102400字节，保存到 C:\download\file.zip
```

### 6.5 Shell工具

**execute_shell_command 成功**：
```python
build_success(
    data={"output":"Handles  NPM(K)...","error_output":""},
    llm_data={
        "summary": "命令执行成功，退出码0",
        "action": {"tool": "execute_shell_command", "tool_zh": "执行", "params": {"command": "Get-Process"}},
        "target": "Get-Process",
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"exit_code": {"value": 0, "text": "退出码0"}},
    },
)
```
```
观察: 执行成功 - 执行
结果: 命令执行成功，退出码0
详情:
Handles  NPM(K)...
```

### 6.6 系统工具

**get_system_info 成功**：
```python
build_success(
    data={"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50},"disk":{"C:":{"total_gb":500,"used_pct":60}}},
    llm_data={
        "summary": "获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)",
        "action": {"tool": "get_system_info", "tool_zh": "获取", "params": {}},
        "target": "system",
        "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
    },
)
```
```
观察: 获取成功 - 获取
结果: 获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)
详情:
  CPU: 12核, 已用45%
  内存: 16GB, 已用50%
  磁盘 C:: 500GB, 已用60%
```

**event_log 成功**：
```python
build_success(
    data={"events":[...]},
    llm_data={
        "summary": "获取事件日志(Application)，10条记录",
        "action": {"tool": "event_log", "tool_zh": "获取", "params": {"log_name": "Application"}},
        "target": "event_log/Application",
        "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"total": {"value": 10, "text": "10条记录"}, "level": {"value": "Error", "text": "Error级别"}},
    },
)
```
```
观察: 获取成功 - 获取
结果: 获取事件日志(Application)，10条记录
详情:
[1] 2026-06-20 10:30 | Error | Application
[2] 2026-06-20 10:25 | Warning | Application
...
```

### 6.7 桌面工具

**mouse_click 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "点击屏幕(500,300)，左键单击",
        "action": {"tool": "mouse_click", "tool_zh": "点击", "params": {"x": 500, "y": 300, "button": "left"}},
        "target": "screen(500,300)",
        "status": {"exec_code": "success", "message": "点击成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"button": {"value": "left", "text": "左键"}, "click_type": {"value": "single", "text": "单击"}},
    },
)
```
```
观察: 点击成功 - 点击
结果: 点击屏幕(500,300)，左键单击
```

**screen_capture 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "截图保存到 C:\\capture.png，1920×1080",
        "action": {"tool": "screen_capture", "tool_zh": "截图", "params": {}},
        "target": "screen",
        "status": {"exec_code": "success", "message": "截图成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"file_path": {"value": "C:\\capture.png", "text": "保存到 C:\\capture.png"}, "width": {"value": 1920, "text": "1920px"}, "height": {"value": 1080, "text": "1080px"}},
    },
)
```
```
观察: 截图成功 - 截图
结果: 截图保存到 C:\capture.png，1920×1080
```

### 6.8 注册表工具

**registry_read 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "读取 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)",
        "action": {"tool": "registry_read", "tool_zh": "读取", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
        "target": "HKCU\\Software\\MyApp\\LastLogin",
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"value": {"value": "2026-06-20", "text": "\"2026-06-20\""}, "value_type": {"value": "REG_SZ", "text": "REG_SZ类型"}},
    },
)
```
```
观察: 读取成功 - 读取
结果: 读取 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)
```

**registry_write 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "写入 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)，旧值=\"2026-06-19\"",
        "action": {"tool": "registry_write", "tool_zh": "写入", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
        "target": "HKCU\\Software\\MyApp\\LastLogin",
        "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"new_value": {"value": "2026-06-20", "text": "新值=\"2026-06-20\""}, "old_value": {"value": "2026-06-19", "text": "旧值=\"2026-06-19\""}, "value_type": {"value": "REG_SZ", "text": "REG_SZ类型"}},
    },
)
```
```
观察: 写入成功 - 写入
结果: 写入 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)，旧值="2026-06-19"
```

### 6.9 定时器工具

**timer_set 成功**：
```python
build_success(
    data={},
    llm_data={
        "summary": "定时器设置成功，30秒后触发",
        "action": {"tool": "timer_set", "tool_zh": "设置", "params": {"delay_seconds": 30}},
        "target": "timer",
        "status": {"exec_code": "success", "message": "设置成功", "code": "", "detail": "", "hint": ""},
        "metrics": {"delay_seconds": {"value": 30, "text": "30秒"}, "trigger_time": {"value": "2026-06-20 10:51:00", "text": "触发时间 10:51:00"}},
    },
)
```
```
观察: 设置成功 - 设置
结果: 定时器设置成功，30秒后触发
```

---

## 七、错误格式规范

### 7.1 错误data（只放llm_data没有的信息）

```python
data = {
    "error_detail": str,    # 必填：错误详情（比status.detail更具体）
    "params": dict,         # 可选：导致错误的参数（LLM可据此修正）
}
```

### 7.2 错误llm_data（status内聚所有状态信息）

```python
llm_data = {
    "summary": str,          # 必填：自然语言错误摘要
    "action": {              # 必填：操作类型
        "tool": str,         # function name
        "tool_zh": str,      # 中文操作类型
        "params": dict,      # LLM调用参数
    },
    "target": str,           # 必填：操作目标
    "status": {              # 必填：执行状态
        "exec_code": "error",
        "message": str,      # 状态文字（LLM直接消费）
        "code": str,         # 错误码（程序用）
        "detail": str,       # 错误详情
        "hint": str,         # 修正建议
    },
    "metrics": {},           # 错误时通常为空
}
```

### 7.3 错误输出格式

```
观察: {status.message} - {action.tool_zh}
结果: {summary}
详情: {format_data_detail(data)}
建议: {status.hint}
```

### 7.4 错误示例

**文件不存在**：
```python
build_error(
    ERR_FILE_NOT_FOUND, "文件不存在",
    data={"error_detail":"文件路径不存在","params":{"encoding":"utf-8"}},
    llm_data={
        "summary": "文件 C:\\notexist.txt 不存在",
        "action": {"tool": "read_text_file", "tool_zh": "读取", "params": {"file_path": "C:\\notexist.txt"}},
        "target": "C:\\notexist.txt",
        "status": {"exec_code": "error", "message": "文件不存在", "code": "ERR_FILE_NOT_FOUND", "detail": "文件路径不存在", "hint": "请检查路径是否正确"},
    },
)
```
```
观察: 文件不存在 - 读取
结果: 文件 C:\notexist.txt 不存在
详情:
  错误: 文件路径不存在
  参数: encoding=utf-8
建议: 请检查路径是否正确
```

**SQL执行失败**：
```python
build_error(
    ERR_SQL_EXEC, "SQL执行错误",
    data={"error_detail":"near SELCT: syntax error","params":{"sql":"SELCT * FROM users","connection_type":"sqlite"}},
    llm_data={
        "summary": "SQL执行失败: near \"SELCT\": syntax error",
        "action": {"tool": "query_sql", "tool_zh": "查询", "params": {"sql": "SELCT * FROM users"}},
        "target": "SELCT * FROM users",
        "status": {"exec_code": "error", "message": "SQL语法错误", "code": "ERR_SQL_EXEC", "detail": "near SELCT: syntax error", "hint": "请检查SQL语法"},
    },
)
```
```
观察: SQL语法错误 - 查询
结果: SQL执行失败: near "SELCT": syntax error
详情:
  错误: near SELCT: syntax error
  参数: sql=SELCT * FROM users, connection_type=sqlite
建议: 请检查SQL语法
```

**依赖库未安装**：
```python
build_error(
    ERR_NO_PYAUTOGUI, "依赖库未安装",
    data={"error_detail":"pyautogui库未安装","params":{"library":"pyautogui","install_command":"pip install pyautogui"}},
    llm_data={
        "summary": "需要安装 pyautogui 库",
        "action": {"tool": "mouse_click", "tool_zh": "点击", "params": {}},
        "target": "desktop_automation",
        "status": {"exec_code": "error", "message": "依赖库未安装", "code": "ERR_NO_PYAUTOGUI", "detail": "pyautogui库未安装", "hint": "请先执行安装命令"},
    },
)
```
```
观察: 依赖库未安装 - 点击
结果: 需要安装 pyautogui 库
详情:
  错误: pyautogui库未安装
  参数: library=pyautogui, install_command=pip install pyautogui
建议: 请先执行安装命令
```

**HTTP请求超时**：
```python
build_error(
    ERR_TIMEOUT, "请求超时",
    data={"error_detail":"连接超时，30秒未响应","params":{"url":"https://slow-api.com","timeout":30}},
    llm_data={
        "summary": "请求 https://slow-api.com 超时，30秒未响应",
        "action": {"tool": "http_request", "tool_zh": "请求", "params": {"url": "https://slow-api.com"}},
        "target": "https://slow-api.com",
        "status": {"exec_code": "error", "message": "请求超时", "code": "ERR_TIMEOUT", "detail": "连接超时，30秒未响应", "hint": "请稍后重试或检查网络连接"},
    },
)
```
```
观察: 请求超时 - 请求
结果: 请求 https://slow-api.com 超时，30秒未响应
详情:
  错误: 连接超时，30秒未响应
  参数: url=https://slow-api.com, timeout=30
建议: 请稍后重试或检查网络连接
```

---

## 八、警告格式规范

### 8.1 警告输出格式

```
观察: {status.message} - {action.tool_zh}
⚠ 警告: {status.detail}
结果: {summary}
详情: {format_data_detail(data)}
建议: {status.hint}
```

### 8.2 警告llm_data结构

```python
llm_data = {
    "summary": str,
    "action": {"tool": str, "tool_zh": str, "params": dict},
    "target": str,
    "status": {
        "exec_code": "warning",
        "message": str,      # 警告简述
        "code": str,         # 警告码（"WARNING_DB_SAFETY"）
        "detail": str,       # 警告详情
        "hint": str,         # 修正建议
    },
    "metrics": dict,         # 警告时有关键数字（如影响行数）
}
```

### 8.3 警告示例

**数据量过大回滚**：
```python
build_warning(
    WARNING_DB_SAFETY, "SQL影响行数过大",
    data={},
    llm_data={
        "summary": "SQL影响50000行，超过安全阈值10000，已自动回滚",
        "action": {"tool": "execute_sql", "tool_zh": "执行", "params": {"sql": "UPDATE users SET ..."}},
        "target": "UPDATE users SET ...",
        "status": {"exec_code": "warning", "message": "影响行数超过安全阈值", "code": "WARNING_DB_SAFETY", "detail": "操作影响行数超过安全阈值，已自动回滚", "hint": "请使用WHERE子句缩小影响范围"},
        "metrics": {"affected_rows": {"value": 50000, "text": "影响50000行"}, "threshold": {"value": 10000, "text": "安全阈值10000"}},
    },
)
```
```
观察: 影响行数超过安全阈值 - 执行
⚠ 警告: 操作影响行数超过安全阈值，已自动回滚
结果: SQL影响50000行，超过安全阈值10000，已自动回滚
建议: 请使用WHERE子句缩小影响范围
```
观察: {status.message} - {action.tool_zh}
⚠ 警告: {status.detail}
结果: {summary}
详情: {format_data_detail(data)}
建议: {status.hint}
```

### 8.2 警告示例

**数据量过大回滚**：
```
观察: 影响行数超过安全阈值 - 执行
⚠ 警告: 操作影响行数超过安全阈值，已自动回滚
结果: SQL影响50000行，超过安全阈值10000，已自动回滚
建议: 请使用WHERE子句缩小影响范围
```

---

## 九、实现方案

### 9.1 三阶段改造

| 阶段 | 改造内容 | 影响范围 | 依赖 |
|------|---------|---------|------|
| **Phase 1** | 修复P0+P1：data传str→dict、data=None→dict、补齐缺失字段、补齐llm_data | ~25个函数 | 无 |
| **Phase 2** | 统一llm_data为6字段结构（action/status/metrics） + 统一data为纯业务数据 + 重构observation_formatter（用format_data_detail渲染详情） | 71个函数 | Phase 1 |
| **Phase 3** | 统一error时data格式（加error_detail/params） + 补齐status结构 | ~50个error调用 | Phase 2 |

### 9.2 Phase 1修复清单（Top 10优先）

| 序号 | 函数 | 当前问题 | 修复方式 |
|------|------|---------|---------|
| 1 | generate_chart | data=str | 改为`{"content":...}` |
| 2 | _delete_file幂等 | data=None | 改为`{}` |
| 3 | write_docx | data只有file_path | 加content_summary到metrics |
| 4 | write_pdf | data只有file_path | 加content_summary到metrics |
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
        # 成功：观察(status.message + action.tool_zh) + 结果(summary) + 详情(format_data_detail)
        action = llm_data.get("action", {}) if isinstance(llm_data, dict) else {}
        tool_zh = action.get("tool_zh", tool_name) if isinstance(action, dict) else tool_name
        status = llm_data.get("status", {}) if isinstance(llm_data, dict) else {}
        status_msg = status.get("message", "成功") if isinstance(status, dict) else "成功"
        
        text = f"观察: {status_msg} - {tool_zh}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        elif message:
            text += f"\n结果: {message}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            detail = format_data_detail(safe_data) if isinstance(safe_data, dict) else str(safe_data)
            if detail:
                text += f"\n详情:\n{detail}"
        return text

    elif isinstance(code, str) and code.startswith("WARNING_"):
        # 警告
        action = llm_data.get("action", {}) if isinstance(llm_data, dict) else {}
        tool_zh = action.get("tool_zh", tool_name) if isinstance(action, dict) else tool_name
        status = llm_data.get("status", {}) if isinstance(llm_data, dict) else {}
        status_msg = status.get("message", "警告") if isinstance(status, dict) else "警告"
        status_detail = status.get("detail", "") if isinstance(status, dict) else ""
        status_hint = status.get("hint", "") if isinstance(status, dict) else ""
        
        text = f"观察: {status_msg} - {tool_zh}"
        if status_detail:
            text += f"\n⚠ 警告: {status_detail}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            detail = format_data_detail(safe_data) if isinstance(safe_data, dict) else str(safe_data)
            if detail:
                text += f"\n详情:\n{detail}"
        if status_hint:
            text += f"\n建议: {status_hint}"
        return text

    else:
        # 错误
        action = llm_data.get("action", {}) if isinstance(llm_data, dict) else {}
        tool_zh = action.get("tool_zh", tool_name) if isinstance(action, dict) else tool_name
        status = llm_data.get("status", {}) if isinstance(llm_data, dict) else {}
        status_msg = status.get("message", message) if isinstance(status, dict) else message
        status_hint = status.get("hint", "") if isinstance(status, dict) else ""
        
        text = f"观察: {status_msg} - {tool_zh}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if data is not None and data != {}:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            detail = format_data_detail(safe_data) if isinstance(safe_data, dict) else str(safe_data)
            if detail:
                text += f"\n详情:\n{detail}"
        if status_hint:
            text += f"\n建议: {status_hint}"
        return text
```

#### 9.3.2 llm_data格式统一

所有工具的llm_data统一为6字段结构：
```python
llm_data = {
    "summary": str,     # 必填
    "action": dict,     # 必填：{tool, tool_zh, params}
    "target": str,      # 必填
    "status": dict,     # 必填：{exec_code, message, code, detail, hint}
    "duration_ms": int, # 可选
    "metrics": dict,    # 可选：{key: {value, text}}
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

#### 9.3.4 build 3函数签名改造

build_success / build_error / build_warning 三个函数是结构化数据的**入口**，也是整个管道的第一道关口。
改造目标：签入干净、签出清爽、与llm_data的6字段结构对齐。

**改造要点**：

| 原签名的项目 | 改造方式 |
|-------------|---------|
| `llm_data: Optional[Dict]=None` 参数 | 保留，但改为**建议必填**（tool侧应统一填充，不依赖None兜底） |
| `llm_data` 无结构约束 | 工具侧自觉保证6字段结构（summary/action/target/status/duration_ms/metrics），formatter按结构取值 |
| `message` 参数与llm_data.status.message重叠 | message保留作为build层**兜底**（老工具过渡用），新工具优先用llm_data.status.message |
| `data` 与 `llm_data` 字段重复 | 工具侧自觉遵守**零重复原则**：llm_data管描述（action/target/metrics），data管大块内容 |

**签名规范（建议）**：

```python
def build_success(
    data: Any = None,                    # 纯业务数据（llm_data不存的大块内容）
    llm_data: Optional[Dict] = None,     # 结构化摘要（6字段：summary/action/target/status/duration_ms/metrics）
    message: str = "执行成功",           # 兜底用，新工具优先用llm_data.status.message
    ...
) -> Dict[str, Any]:
```

**formatter消费规则**：

| formatter读取优先级 | 说明 |
|-------------------|------|
| 优先从llm_data取值 | status.message → 观察行，summary → 结果行，action.tool_zh → 观察行 |
| 兜底才用顶层字段 | llm_data缺失时fallback到result.message、tool_name参数 |

**工具侧填充llm_data的强制检查清单**：

- [ ] llm_data不为None
- [ ] llm_data有summary（自然语言摘要）
- [ ] llm_data有action（tool/tool_zh/params）
- [ ] llm_data有target（操作目标）
- [ ] llm_data有status（exec_code/message/code/detail/hint）
- [ ] llm_data与data无字段重复

### 9.4 Phase 3核心改动

统一error时data格式，每个build_error调用补齐error_detail/params，同时补齐llm_data的status结构。

---

## 十、规范速查

### 10.1 llm_data六顶层字段（结构冻结）

```python
llm_data = {
    # 必填
    "summary": str,     # 自然语言摘要（"操作+对象+数字"）
    "action": {         # 操作类型（结构冻结）
        "tool": str,    # function name
        "tool_zh": str, # 中文操作类型
        "params": dict, # LLM调用参数
    },
    "target": str,      # 操作目标
    "status": {         # 执行状态（结构冻结）
        "exec_code": str,   # "success" / "error" / "warning"
        "message": str,     # 状态文字（LLM直接消费）
        "code": str,        # 状态码（程序用）
        "detail": str,      # 状态详情
        "hint": str,        # 修正建议
    },
    # 可选
    "duration_ms": int, # 执行耗时（毫秒）
    "metrics": dict,    # 关键数字（自描述：{key: {value, text}}）
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

### 10.4 observation输出三层格式

| 场景 | 观察 | 结果 | 详情 | 建议 |
|------|------|------|------|------|
| 成功 | `{status.message} - {action.tool_zh}` | `{summary}` | `{format_data_detail(data)}` | — |
| 错误 | `{status.message} - {action.tool_zh}` | `{summary}` | `{format_data_detail(data)}` | `{status.hint}` |
| 警告 | `{status.message} - {action.tool_zh}` | `{summary}` | `{format_data_detail(data)}` | `{status.hint}` |

### 10.5 禁止

| 禁止 | 说明 |
|------|------|
| data=None | 必须传dict（可以为空dict） |
| data=str | 必须传dict |
| data和llm_data字段重复 | 同一字段只出现一次 |
| data放action/target | 这些在llm_data里 |
| data放关键数字 | lines/bytes/exit_code等在llm_data.metrics里 |
| llm_data=None | 所有工具必须有llm_data |
| llm_data无summary | summary必填 |
| llm_data无status | status必填（内聚所有状态信息） |
| 裁剪llm_data | ReAct循环中禁止裁剪llm_data，只裁剪data |
| 详情用JSON dump | 详情必须用format_data_detail渲染为可读文本 |

---

## 十一、设计优势总结

| 优势 | 说明 |
|------|------|
| **每看全懂** | 观察行status.message+action.tool_zh，LLM扫一眼就知道发生了什么 |
| **格式统一** | 所有llm_data都是6字段结构，所有data只放纯业务数据 |
| **信息完整** | status内聚所有状态信息（message/code/detail/hint），metrics自描述关键数字 |
| **零重复** | llm_data管描述，data管内容，同一字段只出现一次，改一处即可 |
| **LLM和前端一视同仁** | metrics自描述（value+text），前端渲染标签，LLM直接看text |
| **前端可控** | 摘要模式只显示llm_data，详情模式展开data |
| **维护简单** | 工具自治，框架不变——新增工具只改自己的llm_data填充逻辑 |
| **结构稳定** | 6顶层字段冻结，action/status结构冻结，只有metrics开放扩展 |
| **详情可读** | format_data_detail自动渲染为可读文本，LLM无需解析JSON |
| **裁剪安全** | ReAct循环只裁剪data，llm_data完整保留，LLM始终能看摘要和状态 |

---

**文档更新时间**: 2026-06-20 20:24:00  
**版本**: v3.0  
**编写人**: 小健 + 北京老陈 + 小欧