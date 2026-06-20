# 工具 Observation 统一输出格式设计（融合方案）

**创建时间**: 2026-06-20 11:07:25  
**更新时间**: 2026-06-21 00:40:00  
**版本**: v5.0  
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
| v4.0 | 2026-06-20 22:00:00 | 全文档审查，修复不一致问题 | 小欧 |
| v4.0 | 2026-06-20 22:00:00 | 全量修复：exec_code统一为success/error/warning 3值enum；Ch6/7/8示例全部改用build_result格式；metrics措辞统一为"前端和LLM同等消费"；9.3重写为5.9引用 | 小欧 |
| v4.1 | 2026-06-20 22:45:00 | build_result新增exec_code/duration_ms/tool_params直接参数；builder接收exec_code不猜；移除data["_call_params"]注入；**extra过滤保留字段；other_data输出通道化；format_data_detail加try-except兜底；第10章新增3条禁止 | 小欧 |
| v5.0 | 2026-06-21 00:40:00 | **结构简化**：target从llm_data顶层降入action子字段（6顶层→5顶层）；action子字段从3→4（tool/tool_zh/target/params）；Ch1-3全量更新 | 小健 |

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
- build_result统一替代build_success/error/warning：message已移入llm_data.status.message，不再作为独立参数传递
- 不改功能逻辑，只改输出格式
- 渐进式改造，不求一步到位

---

## 三、核心设计：三层分离

### 3.1 三个层次的职责

| 层次 | 来源 | 职责 | LLM怎么用 | 前端怎么用 |
|------|------|------|----------|-----------|
| **观察** | formatter生成 | 状态+操作名 | 扫一眼知道发生了什么 | 状态指示器 |
| **结果** | llm_data字段 | 结构化摘要（action/status/metrics/summary） | 快速理解结果概况 | 渲染摘要卡片（summary做标题，action.tool_zh+action.target做标签） |
| **详情** | data字段 | 纯业务数据（只放llm_data没有的大块内容） | 需要精确数据时引用 | 可折叠详情面板 |

**核心原则：llm_data和data零重复**

- llm_data = 结构化描述（action含target/status/duration_ms/metrics/summary）
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
| **build层** | 数据生产者 | 结构化数据（summary/action含target/status/metrics） | 不格式化，不渲染 |
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

#### 3.2.1 llm_data结构（结构化摘要，5顶层字段，唯一持有action含target/status/metrics）

```python
llm_data = {
    # === 必填字段 ===
    "summary": str,     # 自然语言摘要（"读取 C:\test.py，156行，2380字节，UTF-8编码"）
    "action": {         # 操作描述（结构固定，新增工具只扩枚举不改结构）
        "tool": str,    # 工具名称，即LLM调用时的function name（"read_text_file"/"write_docx"/"execute_shell_command"/"search_web"/...）
        "tool_zh": str, # 中文操作类型（"读取"/"写入"/"删除"/"搜索"/"执行"/"复制"/"列出"/"查询"/"下载"/"点击"/"截图"/"设置"/"获取"/...）
        "target": str,  # 操作目标（路径/URL/查询词/命令，如"C:\test.py"）— 从params中提取的关键参数值，与action天然配对
        "params": dict, # LLM调用时传入的参数（{"file_path":"C:\\test.py","encoding":"utf-8"} / {"command":"Get-Process"} / {"query":"低空星链通信"}/...）
    },
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

**target为何放入action**：target本质是action.params中"最关键的那个参数值"（文件路径/URL/查询词/命令），与action描述的是同一件事——"谁对什么做了什么"。前端渲染时 `action.tool_zh + action.target` 天然配对（"读取 C:\test.py"），不需要跨顶层字段组合。

**metrics自描述设计**：每个值都带`text`文字说明，前端和LLM同等消费，无需外部查表。

**前端渲染**：遍历metrics，直接用text渲染标签。如`"156行 | 2380字节 | UTF-8编码"`。

**LLM消费**：直接看text理解含义，需要精确值时引用value。

**核心架构原则：工具自治，框架不变**

| 角色 | 职责 | 改动范围 |
|------|------|---------|
| 每个tool | 填写自己的llm_data内容（summary/action含target/status/metrics等具体值） | 只改自己的工具代码 |
| observation流程 | 只认llm_data的5字段结构，遍历渲染，不关心具体值 | 永远不变 |
| 前端 | 按结构渲染（summary做标题，action.tool_zh+action.target做标签，metrics.text做数字标签，data做详情） | 永远不变 |
| LLM | 按三段式文本理解（观察→结果→详情） | 永远不变 |

**结果**：新增/修改任何tool，只改该tool的llm_data填充逻辑，不影响observation formatter、不影响前端渲染、不影响LLM消费流程。

**结构稳定性保证**：

| 层级 | 结构 | 扩展方式 | 稳定性 |
|------|------|---------|--------|
| llm_data顶层 | summary/action/status/duration_ms/metrics | **永不加字段** | 冻结 |
| action | tool/tool_zh/target/params | 新增工具只扩枚举值 | 冻结 |
| status | exec_code/message/code/detail/hint | **永不加字段** | 冻结 |
| metrics | 自描述dict（value+text） | 新增工具自由加键值对，每个值自带文字说明 | 开放 |

新增工具时：只往action枚举加一个值、往metrics加几个键，**不改llm_data结构定义**。

**ReAct循环中的裁剪规则**：

| 数据 | 是否可裁剪/压缩 | 原因 |
|------|----------------|------|
| llm_data | ❌ **禁止裁剪压缩** | summary/message/action含target/status/duration_ms/metrics是LLM决策的核心上下文，裁剪会导致LLM无法理解结果、无法修正错误 |
| data | ✅ 可以裁剪压缩 | data是大块业务内容（文件内容/命令输出等），ReAct循环中token超限时只裁剪data，如截断content、只保留前N行 |

**裁剪策略**：当observation token超限时，只对data做截断（如`_prevent_json_oom`），llm_data原样保留。LLM始终能看到完整的摘要和状态，只是详情可能被截断。

**各场景字段使用**：

| 字段 | 成功 | 错误 | 警告 |
|------|------|------|------|
| summary | ✅ 结果摘要 | ✅ 错误摘要 | ✅ 警告摘要 |
| action | ✅ | ✅ | ✅ |
| action.tool | "read_text_file" | "read_text_file" | "execute_sql" |
| action.tool_zh | "读取" | "读取" | "执行" |
| action.target | "C:\test.py" | "C:\notexist.txt" | "SELECT * FROM users" |
| action.params | {"file_path":"C:\\test.py"} | {"file_path":"C:\\notexist.txt"} | {"sql":"SELECT..."} |
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
| 前端操作标签 | action.tool_zh + action.target | 天然配对："读取 C:\test.py" |
| 前端程序逻辑 | action.tool | 程序判断用工具名，精确匹配 |
| 日志/调试 | action.tool | 英文便于检索 |
| LLM调用回溯 | action.params | LLM看到"我传了什么参数" |

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
llm_data = {"summary":"读取 C:\\test.py，156行","action":{"tool":"read_text_file","tool_zh":"读取","target":"C:\\test.py","params":{"file_path":"C:\\test.py"}},"status":{"exec_code":"success","message":"读取成功","code":"","detail":"","hint":""},"metrics":{"lines":{"value":156,"text":"156行"},"bytes":{"value":2380,"text":"2380字节"}}}
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
| action.target | llm_data | — | 嵌在summary | — | 目标标签（"C:\test.py"） |
| action.params | llm_data | — | — | — | — |
| status.message | llm_data | ✅ "读取成功" | — | — | — |
| summary | llm_data | — | ✅ | — | 卡片标题 |
| status.* | llm_data | ✅ message(显示) + exec_code(路由) | — | — | 状态指示 |
| duration_ms | llm_data | — | — | — | 耗时标签 |
| metrics.* | llm_data | — | 嵌在summary | — | 数字标签 |
| content/output等 | data | — | — | ✅ | 可折叠详情 |

**前端渲染效果**：

```
┌─────────────────────────────────────────┐
│ 📄 读取 C:\test.py，156行，2380字节，UTF-8 │  ← summary
│ 读取 | C:\test.py | 156行 | 2380字节      │  ← action.tool_zh + action.target + metrics.text
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
| 详情 | data | 可读文本（formatter按结构自动格式化） | 不重复action含target/关键数字（观察+结果已有） |

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

**与旧方案的关键区别**：详情行只输出data（纯业务数据），不再重复action含target/关键数字

---

### 3.5 统一数据管道：从tool到observation文本

**核心思想**：llm_data是结构化中间态，observation文本是最终产物。整条管道是单向的"结构化数据→渲染→文本"。

**完整流程图**：

```
tool函数执行
  ↓ data 原始返回
build_result(tool_name, data=...)       ← builder 自动构建 llm_data
  ↓ result = {data, llm_data, other_data}
build_observation_text(result)          ← 桥接层拆包
  ↓
format_llm_observation(data, llm_data)  ← 不再接收 result dict
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
| tool函数 | 各tools/*.py | 业务参数 | data | 执行业务，返回原始data | 不格式化，不渲染 |
| builder_fn | 各tools/*.py（文件末尾） | data + exec_code + duration_ms + tool_params | llm_data（5字段结构化摘要） | 从data/exec_code/duration_ms/tool_params构建llm_data | 不改data内容 |
| build_result() | tool_response.py | tool_name, data, exec_code, duration_ms, tool_params, other_data | 统一result dict（{data, llm_data, other_data}） | 通过tool_name查找builder构建result | 不改llm_data内容 |
| format_llm_observation() | observation_formatter.py | data, llm_data | 三段式文本 | 机械渲染：llm_data→观察+结果行，data→详情行 | 不新增信息，不加工语义 |
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
| 新增工具 | 唯一：该工具的builder_fn + register_builder | formatter、build_result、前端渲染 |
| 修改llm_data字段内容 | 唯一：该tool的builder_fn | formatter（机械取值） |
| 修改observation文本格式 | 唯一：formatter渲染逻辑 | 工具侧builder、前端 |
| 前端改变展示方式 | 唯一：前端渲染 | 工具侧builder、formatter |

### 3.6 实施原则

**原则一：废除现有`llm_data`的旧代码和旧逻辑**

当前代码中散落的`llm_data`填充方式五花八门（有的None、有的partial、有的与data重复），observation_formatter中对`llm_data`的读取逻辑也混杂不清。实施本设计时，**旧的全部废除，全部按新5字段结构重写**，不做向后兼容。

| 废除内容 | 说明 |
|---------|------|
| tool函数中旧的`llm_data`填充（None/空dict/partial） | 统一为完整5字段结构 |
| observation_formatter中旧的`_extract_display_data()`等内容 | 统一为新三段式渲染 |
| message参数承载关键信息的写法 | 关键信息移入llm_data.status.message |

旧代码一律不保留、不兼容、不过渡。

**原则二：用build 3合一的新build_result函数实现新的observation文本——`llm_data`字段承载结构化中间态**

新build_result是整个管道的入口。改造后的签名中，`llm_data`字段承载新设计的5字段结构化中间态：

```
result = {
    "data": ...,        # 纯业务大块内容（给前端详情面板）
    "llm_data": {       # ⬅ 结构化中间态：formatter以此渲染observation文本
        "summary": str,
        "action": {"tool": str, "tool_zh": str, "target": str, "params": dict},
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
| `data` | 详情行 | `format_data_detail`格式化函数实现按类型自动渲染，不改内容 |

**关键约束**：
- LLM看到的observation文本 = `llm_data`全部entry的三段式渲染，不多也不少。
- formatter不承担业务理解、不新增、不组合、不修改内容。
- `data`由`format_data_detail`按数据类型（str/list/dict）机械渲染-格式化，不改内容。
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
def format_data_detail(data: Any) -> str:
    """按data结构类型自动格式化为可读文本
    
    内部可能抛异常，兜底 JSON dump 或 str() 确保不崩。
    """
    if not data:
        return ""
    
    try:
        if not isinstance(data, dict):
            return str(data)
        
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
    except Exception:
        # 兜底：JSON dump 或 str()
        import json
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)
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
| `metrics` | ❌ | dict | 关键数字指标，自描述格式 `{"key": {"value": ..., "text": "..."}}`，前端和LLM同等消费 |

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

**简要流程**：tool函数 → build_result构建result（builder自动构建llm_data） → observation文本 → FC协议消息对 → conversation_history → 发给LLM

```
tool函数执行
  ↓
build_result(tool_name, data=...)        # tool_response.py — builder自动构建llm_data
  ↓                                        # result = {data, llm_data, other_data}
result = {"data": ..., "llm_data": {...}, "other_data": {...}}  # ← llm_data由builder产出
  ↓
format_llm_observation(data, llm_data)   # observation_formatter.py — 直接接收data和llm_data
  ↓
message_builder.add_observation()        # message_builder.py — 追加两条FC协议消息
  ↓                                        消息1: role=assistant, 带tool_calls
  ↓                                        消息2: role=tool, content=observation文本
conversation_history                     # 累积所有轮次的消息
  ↓
prepare_messages_for_llm()               # 合并后发给LLM
```

**关键函数**：

| 函数 | 文件 | 职责 |
|------|------|------|
| `build_result(tool_name, data, other_data)` | tool_response.py | 构建result dict（builder自动构建llm_data） |
| `format_llm_observation(data, llm_data)` | observation_formatter.py | data+llm_data → observation文本 |
| `build_observation_text()` | message_utils.py | 桥接，拆包result后调format_llm_observation |
| `MessageBuilder.add_observation()` | message_builder.py | observation文本 → FC协议消息对 |
| `MessageBuilder.prepare_messages_for_llm()` | message_builder.py | conversation_history → 发给LLM的messages |

**llm_data和data在流程中的位置**：

```
build_result("read_text_file", data={"content":"...", "file_path":"C:/test.py", "line_count":156, ...})
  ↓
result = {"data": {"content":"...", "file_path":"C:/test.py", ...},
           "llm_data": {"summary":"读取 C:\\test.py，156行", "action":{...}, "status":{...}, "metrics":{...}},
           "other_data": {}}
  ↓                ↑ data在这里                    ↑ llm_data由builder从data提取产出
format_llm_observation(result["data"], result["llm_data"])
  ├─ 从llm_data取 → 生成"观察"行和"结果"行
  └─ 从data取     → 生成"详情"行（format_data_detail渲染）
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

### 5.9 Phase 1：Tool 注册 builder + build 3 重构，result 统一为 data/llm_data/other_data

#### 5.9.1 设计目标

Phase 1 是本次改造的核心阶段，目标：

| # | 目标 | 说明 |
|---|------|------|
| 1 | **llm_data 由各 tool 自行构建** | 每 tool 注册 builder，build 3 只透传不介入 llm_data 内部结构 |
| 2 | **result 统一为 3 字段** | `data`（业务数据）+ `llm_data`（结构化摘要）+ `other_data`（额外控制字段） |
| 3 | **format_llm_observation 直接收 data + llm_data** | 不再从 result dict 提取，signature 扁平化 |
| 4 | **清理旧 llm_data 相关代码** | 废弃的提取函数全部删除 |

#### 5.9.2 Builder 注册机制

##### 5.9.2.1 设计

每个 tool 在文件末尾注册一个 `builder_fn`，`build_result` 通过 `tool_name` 查注册表自动构建 llm_data。

**builder 签名**：接收 `exec_code` 和 `duration_ms` 等显式参数，不再从 data 内容猜状态：

```python
# builder_fn(tool_name, data, exec_code, duration_ms, tool_params) -> llm_data
```

```python
# tool_response.py 新增
_LLM_BUILDERS: Dict[str, Callable] = {}

def register_builder(tool_name: str, builder_fn: Callable) -> None:
    """注册 tool 的 llm_data 构建器
    
    Args:
        tool_name: 工具标识名（与 schema 中一致）
        builder_fn: (tool_name, data, exec_code, duration_ms, tool_params) → llm_data
    """
    _LLM_BUILDERS[tool_name] = builder_fn


def _default_builder(tool_name: str, data: Any = None,
                     exec_code: str = "success",
                     duration_ms: int = 0,
                     tool_params: Optional[Dict] = None) -> Dict:
    """兜底 builder — tool 未注册时使用"""
    summary = str(data)[:200] if data is not None else "执行完成"
    return {
        "summary": summary,
        "action": {"tool": tool_name, "tool_zh": tool_name, "params": tool_params or {}},
        "target": "",
        "status": {
            "exec_code": exec_code,
            "message": "执行成功" if exec_code in ("success", "warning") else "执行失败",
            "code": "", "detail": "", "hint": "",
        },
        "duration_ms": duration_ms,
        "metrics": {},
    }
```

##### 5.9.2.2 各 tool 注册示例

```python
# file_tools.py 文件末尾
def _read_text_file_llm_data(tool_name: str, data: dict,
                              exec_code: str, duration_ms: int,
                              tool_params: Optional[dict]) -> dict:
    """read_text_file 的 llm_data 构建器 — exec_code 由 build_result 显式传入，builder 不猜"""
    file_path = data.get("file_path", "")
    line_count = data.get("line_count", 0)
    file_size = data.get("file_size", 0)
    return {
        "summary": f"读取 {file_path}，{line_count}行，{file_size}字节",
        "action": {
            "tool": "read_text_file",
            "tool_zh": "读取文件",
            "params": tool_params or {},
        },
        "target": file_path,
        "status": {"exec_code": exec_code, "message": "读取成功",
                    "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "lines": {"value": line_count, "text": f"{line_count}行"},
            "bytes": {"value": file_size, "text": f"{file_size}字节"},
        },
    }

register_builder("read_text_file", _read_text_file_llm_data)
```

```python
# shell_tools.py 文件末尾
def _run_shell_llm_data(tool_name: str, data: dict,
                         exec_code: str, duration_ms: int,
                         tool_params: Optional[dict]) -> dict:
    command = (tool_params or {}).get("command", "")
    return {
        "summary": f"执行命令完成，返回码 {data.get('returncode', -1)}",
        "action": {
            "tool": "run_shell_command",
            "tool_zh": "执行Shell命令",
            "params": tool_params or {},
        },
        "target": command,
        "status": {"exec_code": exec_code, "message": "执行成功",
                    "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "returncode": {"value": data.get("returncode", -1), "text": f"返回码 {data.get('returncode', -1)}"},
        },
    }

register_builder("run_shell_command", _run_shell_llm_data)
```

##### 5.9.2.3 原则

| 原则 | 说明 |
|------|------|
| **builder_fn 只读 data，不修改 data** | data 保持 tool 原始返回不变 |
| **新增 tool 只需写 builder + 注册** | build 3 函数零改动 |
| **已有 tool 增减字段只改自己的 builder** | 不影响其他 tool |
| **未注册的 tool 使用默认 builder** | 兼容过渡期 |

#### 5.9.3 新 build 3 函数

##### 5.9.3.1 签名与实现

三个函数（build_success / build_error / build_warning）统一为一个。**llm_data 完全由 builder 产出，build_result 纯透传**：

```python
def build_result(
    tool_name: str,
    data: Any = None,
    exec_code: str = "success",
    duration_ms: int = 0,
    tool_params: Optional[Dict] = None,
    other_data: Optional[Dict] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建工具返回结果 — 2026-06-20 北京老陈 设计

    llm_data 完全由 tool 注册的 builder 产出，本函数纯透传。
    exec_code/duration_ms/tool_params 作为显式参数直接传入 builder。
    other_data 是输出通道（warning/retry_count/return_direct/attachment）。
    """
    llm_data = _LLM_BUILDERS.get(tool_name, _default_builder)(
        tool_name, data, exec_code, duration_ms, tool_params,
    )

    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    # 过滤保留字段，防止意外的 data/llm_data/other_data 覆盖顶层
    _RESERVED = {"data", "llm_data", "other_data"}
    for k, v in extra.items():
        if k not in _RESERVED:
            result[k] = v
    return result
```

调用方式统一：

```python
# 成功 — exec_code/duration_ms/tool_params 由 action_handler 传入
build_result("read_text_file", data={"content": "...", "file_path": "C:/test.py", "line_count": 156, "file_size": 2380},
             exec_code="success", duration_ms=25, tool_params={"file_path": "C:/test.py", "encoding": "utf-8"})

# 错误 — exec_code 由 action_handler 判断传入
build_result("read_text_file", data={"file_path": "C:/notfound.py"},
             exec_code="error", duration_ms=5, tool_params={"file_path": "C:/notfound.py"})
```

##### 5.9.3.2 builder 接收 exec_code，不猜状态

builder 不再从 data 内容猜测 exec_code，而是接收调用者显式传入：

```python
def _read_text_file_llm_data(tool_name: str, data: dict,
                              exec_code: str, duration_ms: int,
                              tool_params: Optional[dict]) -> dict:
    """read_text_file 的 llm_data 构建器 — exec_code 由调用者传入，builder 不猜"""
    file_path = data.get("file_path", "")
    line_count = data.get("line_count", 0)
    file_size = data.get("file_size", 0)

    # ── 错误
    if exec_code == "error":
        return {
            "summary": f"文件不存在: {file_path}",
            "action": {"tool": "read_text_file", "tool_zh": "读取文件", "params": tool_params or {}},
            "target": file_path,
            "status": {
                "exec_code": "error", "message": "文件不存在",
                "code": "ERR_FILE_NOT_FOUND", "detail": f"路径不正确: {file_path}",
                "hint": "请检查文件路径或文件名是否正确",
            },
            "duration_ms": duration_ms,
            "metrics": {},
        }

    # ── 警告
    if exec_code == "warning":
        return {
            "summary": f"文件为空: {file_path}",
            "action": {"tool": "read_text_file", "tool_zh": "读取文件", "params": tool_params or {}},
            "target": file_path,
            "status": {
                "exec_code": "warning", "message": "文件为空，可能不是预期内容",
                "code": "WARNING_EMPTY_FILE", "detail": "文件内容为空字符串",
                "hint": "",
            },
            "duration_ms": duration_ms,
            "metrics": {
                "lines": {"value": 0, "text": "0行"},
                "bytes": {"value": 0, "text": "0字节"},
            },
        }

    # ── 成功
    return {
        "summary": f"读取 {file_path}，{line_count}行，{file_size}字节",
        "action": {"tool": "read_text_file", "tool_zh": "读取文件", "params": tool_params or {}},
        "target": file_path,
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "lines": {"value": line_count, "text": f"{line_count}行"},
            "bytes": {"value": file_size, "text": f"{file_size}字节"},
        },
    }

register_builder("read_text_file", _read_text_file_llm_data)
```

##### 5.9.3.3 other_data 承载的字段（输出通道）

other_data **只用于输出**，不用于承载 exec_code：

| 字段 | 类型 | 说明 | 消费方 |
|------|------|------|--------|
| `warning` | `Optional[str]` | 成功但有风险时的警告信息 | 前端展示 |
| `retry_count` | `int` | 当前重试次数 | Agent 重试逻辑 |
| `return_direct` | `bool` | 是否直接返回给用户（跳过 LLM） | Agent 编排（FinalStep） |
| `attachment` | `Any` | 二进制附件（base64 图片等） | 前端渲染 |

#### 5.9.4 result 结构定义

```python
result = {
    "data": Any,               # tool 的主要业务数据（给 LLM 详情 + 前端面板）
    "llm_data": {              # 结构化摘要（给 LLM 三段式 + 前端卡片渲染）
        "summary": str,        #   结果摘要描述
        "action": {            #   工具信息
            "tool": str,       #     工具标识
            "tool_zh": str,    #     工具中文名
            "params": dict,    #     调用参数（来自 tool_params，builder 接收后放入）
        },
        "target": str,         #   操作目标描述
        "status": {            #   执行状态
            "exec_code": str,  #     "success" / "error" / "warning"
            "message": str,    #     人类可读消息
            "code": str,       #     详细错误码
            "detail": str,     #     详细错误信息
            "hint": str,       #     失败后的替代建议
        },
        "duration_ms": int,    #   执行耗时（ms），build_result 传入后 builder 放入
        "metrics": {           #   关键指标，value+text 自描述格式
            "key": {"value": ..., "text": str},
        },
    },
    "other_data": {            # 额外控制字段（输出通道）
        "warning": Optional[str],
        "retry_count": int,
        "return_direct": bool,
        "attachment": Any,
    },
}
```

#### 5.9.5 is_success / is_error 适配

```python
def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功 — 适配新 result 结构"""
    exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code", "")
    return exec_code in ("success", "warning")


def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败 — 适配新 result 结构"""
    exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code", "")
    return exec_code == "error"
```

#### 5.9.6 `format_llm_observation` 重构

##### 5.9.6.1 新签名

```python
def format_llm_observation(data: Any, llm_data: Dict) -> str:
    """格式化工具结果为 LLM observation 文本
    
    llm_data → 观察行 + 结果行（三段式的前两段）
    data     → 详情行（通过 format_data_detail，4.3.2 节）
    """
```

不再接收 result dict，直接接收 `data` 和 `llm_data` 两个参数。

##### 5.9.6.2 内部逻辑

```python
def format_llm_observation(data: Any, llm_data: Dict) -> str:
    status = llm_data.get("status", {})
    action = llm_data.get("action", {})
    summary = llm_data.get("summary", "")
    exec_code = status.get("exec_code", "")
    message = status.get("message", "")
    tool_zh = action.get("tool_zh", "")

    # ── 观察行 ──
    if exec_code == "success":
        text = f"观察: {message} - {tool_zh}"
    elif exec_code == "warning":
        text = f"观察: {message} - {tool_zh}\n⚠ 警告: {status.get('detail', '')}"
    else:
        text = f"观察: {message} - {tool_zh}"

    # ── 结果行 ──
    if summary:
        text += f"\n结果: {summary}"

    # ── 详情行 ──
    if data is not None and data != {} and data != [] and data != "":
        detail = format_data_detail(data)  # 4.3.2 节
        if detail:
            text += f"\n详情:\n{detail}"

    # ── 错误时追加 hint ──
    if exec_code == "error":
        hint = status.get("hint", "")
        if hint:
            text += f"\n{hint}"

    return text


注意：`metrics` 不走 format_llm_observation 的 observation 文本，而是通过 llm_data 结构化传入 LLM（前端和LLM同等消费）。summary 已包含关键指标的文字描述。
```

#### 5.9.7 duration_ms 测量规范

`duration_ms` 是 `llm_data` 的标准字段，作为 `build_result` 的**直接参数**传入，builder 接收后放入 llm_data，不再走 data→builder 提取路径。

**写法**：
```python
def read_text_file(file_path: str):
    t0 = time.perf_counter()
    try:
        content = do_read(file_path)
    except FileNotFoundError:
        content = None
    duration_ms = int((time.perf_counter() - t0) * 1000)
    
    return build_result("read_text_file", data={
        "content": content,
        "file_path": file_path,
        "line_count": len(content.splitlines()) if content else 0,
    }, exec_code="success" if content else "error",
       duration_ms=duration_ms,
       tool_params={"file_path": file_path})
```

**builder 接收** — builder 签名已包含 `duration_ms`，直接使用：
```python
def _read_text_file_llm_data(tool_name, data, exec_code, duration_ms, tool_params):
    return {
        ...
        "duration_ms": duration_ms,  # ← 直接参数，不猜
        ...
    }
```

**优势**：
1. `duration_ms` 不污染 data（data 只放业务字段）
2. builder 逻辑更清晰：`exec_code` + `duration_ms` 来自调用者，builder 只负责组装
3. Phase 2 中 `duration_ms` 同时出现在 ToolStep 顶层，直接从参数取

**并行执行下依然准确**：每个工具独立 `time.perf_counter()` 测量，互不干扰。

#### 5.9.8 受影响文件

| 文件 | 改动 |
|------|------|
| `tool_response.py` | build_success/error/warning 合并为统一的 `build_result(tool_name, data, exec_code, duration_ms, tool_params, *, other_data, ...)`；新增注册机制；**不再注入 data["_call_params"]**；`**extra` 过滤保留字段；is_success/error 适配 |
| **所有 tool 文件（30+个）** | 每个 tool 文件末尾添加 builder + register_builder；调用处传 tool_name + exec_code + duration_ms；工具函数内部加 `time.perf_counter()` 测 duration_ms |
| `observation_formatter.py` | **重写** — format_llm_observation 改为 `(data, llm_data)`；**删除** `_extract_display_data`、`_append_data`、`_format_summary_parts`、`build_execution_result_dict`；format_data_detail 移入（从 4.3.2 设计）|
| `message_utils.py` | build_observation_text 改为直接调 `format_llm_observation(result["data"], result["llm_data"])` |
| `action_handler.py` | ToolStep "observation" 构建时从 `other_data` 读 return_direct/warning/attachment；ToolStep "action_tool" 的 execution_result 为新 3 字段结构；**判断 exec_code 后传入 build_result** |
| `steps/tool_step.py` | to_dict 适配新 result 结构 |
| `tool_retry_engine.py` | is_success/is_error 判断走新路径 |

#### 5.9.9 不涉及的文件

| 文件 | 原因 |
|------|------|
| `run_sse_stream.py` | 透传 event_dict，不解析字段 |
| `sse_formatter.py` | 透传 JSON 到 SSE，不解析字段 |
| `chat_stream.py` | 透传 execution_steps list，不解析字段 |
| DB 存储层 | 全量 JSON 序列化，不解析字段 |

#### 5.9.10 实施顺序

| 步骤 | 内容 | 验证方式 |
|------|------|---------|
| 1 | `tool_response.py` — 实现注册机制 + 新 build_result（含 exec_code/duration_ms/tool_params 直接参数 + **extra 过滤保留字段）| 单测：注册→构建→result 结构正确 |
| 2 | `observation_formatter.py` — 重写 format_llm_observation；format_data_detail 加 try-except 兜底 | 单测：各种 data/llm_data 组合→observation 文本正确 |
| 3 | `message_utils.py` — 适配新签名 | 单测：桥接层正确 |
| 4 | 逐个 tool 文件 — 添加 builder + register_builder + 工具函数内部加 time.perf_counter()；**exec_code 和 duration_ms 作为直接参数传 build_result，不走 data** | 每个 tool 的 observation 文本正确，duration_ms 准确 |
| 5 | `action_handler.py` — 从 other_data 读字段；判断 exec_code 后传入 build_result | 集成测试：SSE 事件字段正确 |
| 6 | 删除旧代码 | 确认无引用 |
| 7 | 全量集成测试 | 所有场景通过 |

---

### 5.10 Phase 2：ToolStep 瘦身 + Observation step 承载全部信息

#### 5.10.1 动机

Phase 1 完成后，formatter 已改为 `(data, llm_data)` 签名，但 ToolStep 和 SSE 通道仍然混杂。ToolStep 的 `execution_result` 同时承载了 llm_data（给前端卡片）和 data（给详情面板），职责不单一。Observation step 只含文本，前端需要的信息分散在两个事件中。

Phase 2 将 ToolStep 和 Observation step 的职责彻底分开：

| 事件 | 职责 | 承载内容 |
|------|------|---------|
| **ToolStep** | 告诉前端"工具执行完成" | 仅 `duration_ms` |
| **Observation step** | 告诉前端"工具结果是什么" | `observation_text` + `llm_data` + `tool_result` |

#### 5.10.2 改动内容

| 维度 | 当前 | Phase 2 |
|------|------|---------|
| **build 3 函数** | `result={data, llm_data}` | **不动** |
| **ToolStep** | `execution_result` 含 data + llm_data + duration_ms | `execution_result = {duration_ms}`，仅完成时间 |
| **Observation step** | 只含 `observation_text` | 新增 `tool_result` 字段（承载原 data）+ 已有 `llm_data` |
| **SSE ToolStep 事件** | 发送完整 execution_result | 只发 `{duration_ms}`，code/message/data/llm_data 都不发 |
| **SSE Observation 事件** | 只发 observation_text | 发 `{observation_text, llm_data, tool_result}` |
| **前端消费** | `ToolStep.execution_result.data` → 详情面板 | `Observation.tool_result` → 详情面板 |
| **前端消费** | `ToolStep.execution_result.llm_data` → 卡片 | `Observation.llm_data` → 卡片 |

#### 5.10.3 新数据流

```
tool 函数执行
  ↓
build_result(tool_name, data=...)    ← 不动，仍然返回 {data, llm_data}
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

#### 5.10.4 受影响文件

| 层 | 文件 | 改动 |
|----|------|------|
| **构建层** | `tool_response.py` | **不动** |
| **格式化层** | `observation_formatter.py` | Phase 1 已改 `(data, llm_data)`，Phase 2 不动 |
| **桥接层** | `message_utils.py` | Phase 1 已拆包，Phase 2 不动 |
| **步骤模型** | `ToolStep` | `execution_result` 只存 `duration_ms` |
| **步骤模型** | Observation step 模型 | 新增 `tool_result` 字段 |
| **编排层** | `action_handler.py` | 构建 Observation step 时传入 data（作为 tool_result）|
| **SSE 层** | `run_sse_stream.py` | 调整 SSE 事件构造逻辑 |
| **前端** | 消费 ToolStep 的代码 | 改为从 Observation 事件取值 |
| **DB 存储** | `save_execution_steps_to_db` | 适配新结构 |

#### 5.10.5 实施要点

1. **ToolStep 瘦身**：`_execution_result` 只保留 `{"duration_ms": execution_time}`，不再接收完整的 result dict。

2. **Observation step 新增 tool_result**：在 `action_handler.py` 的 `build_observation()` 中，把 result["data"] 作为 `tool_result` 字段传入 Observation step。

3. **SSE 发送调整**：
   - ToolStep SSE → `{"step_type": "action_tool", "duration_ms": N}`，不发 code/message/data/llm_data
   - Observation SSE → `{"step_type": "observation", "observation_text": "...", "llm_data": {...}, "tool_result": {...}}`

4. **前端适配**：
   - ToolStep 事件 → 只用于显示"工具执行中..."状态，不再从中取数据
   - Observation 事件 → 从中取 `llm_data` 渲染摘要卡片，取 `tool_result` 渲染详情面板

#### 5.10.6 注意事项

| 注意点 | 说明 |
|--------|------|
| **前后端同步** | Phase 2 必须前后端同步上线，不能分步部署 |
| **DB 兼容** | 旧记录中 execution_result 含 data，新记录不含，前端需判断兼容 |
| **data 为空** | tool_result=None 时，前端跳过详情面板渲染 |
| **LLM 不受影响** | LLM 始终只读 observation_text，底层事件结构变化不影响它 |
| **Phase 1 为前提** | Phase 2 依赖 Phase 1 的 formatter 签名改造，必须先上线 Phase 1 |

---

## 六、各工具类型完整示例

### 6.1 文件操作

**read_text_file 成功**：
```python
# data
data = {"content":"def hello():\n    ..."}

# llm_data（builder 产出）
llm_data = {
    "summary": "读取 C:\\test.py，156行，2380字节，UTF-8编码",
    "action": {"tool": "read_text_file", "tool_zh": "读取", "params": {"file_path": "C:\\test.py", "encoding": "utf-8"}},
    "target": "C:\\test.py",
    "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"lines": {"value": 156, "text": "156行"}, "bytes": {"value": 2380, "text": "2380字节"}, "encoding": {"value": "utf-8", "text": "UTF-8编码"}},
}
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
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "写入 C:\\output.txt，50行/1024字节",
    "action": {"tool": "write_text_file", "tool_zh": "写入", "params": {"file_path": "C:\\output.txt"}},
    "target": "C:\\output.txt",
    "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"bytes_written": {"value": 1024, "text": "写入1024字节"}},
}
```
```
观察: 写入成功 - 写入
结果: 写入 C:\output.txt，50行/1024字节
```

**list_directory 成功**：
```python
# data
data = {"entries":["src/","README.md",...]}

# llm_data（builder 产出）
llm_data = {
    "summary": "列出 C:\\project\\，156个文件/目录",
    "action": {"tool": "list_directory", "tool_zh": "列出", "params": {"path": "C:\\project\\"}},
    "target": "C:\\project\\",
    "status": {"exec_code": "success", "message": "列出成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"total": {"value": 156, "text": "156个文件/目录"}, "truncated": {"value": False, "text": "完整列表"}},
}
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
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "复制 C:\\a.txt → C:\\b.txt，1024字节",
    "action": {"tool": "copy_file", "tool_zh": "复制", "params": {"source": "C:\\a.txt", "destination": "C:\\b.txt"}},
    "target": "C:\\a.txt → C:\\b.txt",
    "status": {"exec_code": "success", "message": "复制成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"bytes": {"value": 1024, "text": "1024字节"}},
}
```
```
观察: 复制成功 - 复制
结果: 复制 C:\a.txt → C:\b.txt，1024字节
```

**delete_file 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "删除 C:\\temp.log，已永久删除",
    "action": {"tool": "delete_file", "tool_zh": "删除", "params": {"file_path": "C:\\temp.log"}},
    "target": "C:\\temp.log",
    "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"deleted": {"value": True, "text": "已永久删除"}, "mode": {"value": "permanent", "text": "永久删除"}},
}
```
```
观察: 删除成功 - 删除
结果: 删除 C:\temp.log，已永久删除
```

**delete_file 幂等（文件不存在）**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "删除 C:\\temp.log，文件已不存在(幂等)",
    "action": {"tool": "delete_file", "tool_zh": "删除", "params": {"file_path": "C:\\temp.log"}},
    "target": "C:\\temp.log",
    "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"deleted": {"value": False, "text": "文件已不存在(幂等)"}, "mode": {"value": "already_gone", "text": "无需删除"}},
}
```
```
观察: 删除成功 - 删除
结果: 删除 C:\temp.log，文件已不存在(幂等)
```

### 6.2 数据库工具

**query_sql 成功**：
```python
# data
data = {"rows":[[1,"Alice","a@t.com"],...]}

# llm_data（builder 产出）
llm_data = {
    "summary": "查询返回5行，列: id, name, email",
    "action": {"tool": "query_sql", "tool_zh": "查询", "params": {"sql": "SELECT * FROM users"}},
    "target": "SELECT * FROM users",
    "status": {"exec_code": "success", "message": "查询成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"row_count": {"value": 5, "text": "5行"}, "columns": {"value": ["id","name","email"], "text": "列: id, name, email"}},
}
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
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "SQL执行成功，影响5行",
    "action": {"tool": "execute_sql", "tool_zh": "执行", "params": {"sql": "UPDATE users SET ..."}},
    "target": "UPDATE users SET ...",
    "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"affected_rows": {"value": 5, "text": "影响5行"}},
}
```
```
观察: 执行成功 - 执行
结果: SQL执行成功，影响5行
```

**get_db_schema 成功**：
```python
# data
data = {"tables":{"users":"...","orders":"...","products":"..."}}

# llm_data（builder 产出）
llm_data = {
    "summary": "获取到3个表的结构: users, orders, products",
    "action": {"tool": "get_db_schema", "tool_zh": "获取", "params": {}},
    "target": "database",
    "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"total": {"value": 3, "text": "3个表"}},
}
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
# data
data = {"content":"PDF文本..."}

# llm_data（builder 产出）
llm_data = {
    "summary": "读取 C:\\report.pdf，5页，12000字符",
    "action": {"tool": "read_pdf", "tool_zh": "读取", "params": {"file_path": "C:\\report.pdf"}},
    "target": "C:\\report.pdf",
    "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"pages": {"value": 5, "text": "5页"}, "chars": {"value": 12000, "text": "12000字符"}},
}
```
```
观察: 读取成功 - 读取
结果: 读取 C:\report.pdf，5页，12000字符
详情:
PDF文本...
```

**write_docx 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "写入 C:\\report.docx，3段落/500字",
    "action": {"tool": "write_docx", "tool_zh": "写入", "params": {"file_path": "C:\\report.docx"}},
    "target": "C:\\report.docx",
    "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"bytes_written": {"value": 2048, "text": "写入2048字节"}, "content_summary": {"value": "3段落/500字", "text": "3段落/500字"}},
}
```
```
观察: 写入成功 - 写入
结果: 写入 C:\report.docx，3段落/500字
```

**write_xlsx 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "写入 C:\\data.xlsx，10行×5列",
    "action": {"tool": "write_xlsx", "tool_zh": "写入", "params": {"file_path": "C:\\data.xlsx"}},
    "target": "C:\\data.xlsx",
    "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"bytes_written": {"value": 512, "text": "写入512字节"}, "content_summary": {"value": "10行×5列", "text": "10行×5列"}},
}
```
```
观察: 写入成功 - 写入
结果: 写入 C:\data.xlsx，10行×5列
```

### 6.4 网络工具

**search_web 成功**：
```python
# data
data = {"items":[...]}

# llm_data（builder 产出）
llm_data = {
    "summary": "搜索到8条结果(Parallel引擎)",
    "action": {"tool": "search_web", "tool_zh": "搜索", "params": {"query": "低空星链通信 2026"}},
    "target": "低空星链通信 2026",
    "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
    "metrics": {"total": {"value": 8, "text": "8条结果"}, "engine": {"value": "Parallel", "text": "Parallel引擎"}},
}
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
# data
data = {"body":"..."}

# llm_data（builder 产出）
llm_data = {
    "summary": "HTTP GET https://api.example.com，状态码200，响应体15000字符",
    "action": {"tool": "http_request", "tool_zh": "请求", "params": {"url": "https://api.example.com", "method": "GET"}},
    "target": "https://api.example.com",
    "status": {"exec_code": "success", "message": "请求成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"status_code": {"value": 200, "text": "HTTP 200"}, "content_type": {"value": "application/json", "text": "JSON格式"}},
}
```
```
观察: 请求成功 - 请求
结果: HTTP GET https://api.example.com，状态码200，响应体15000字符
详情:
{"status":"ok","data":[...]}
```

**download_file 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "下载完成，102400字节，保存到 C:\\download\\file.zip",
    "action": {"tool": "download_file", "tool_zh": "下载", "params": {"url": "https://example.com/file.zip"}},
    "target": "https://example.com/file.zip",
    "status": {"exec_code": "success", "message": "下载成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"bytes": {"value": 102400, "text": "102400字节"}, "file_path": {"value": "C:\\download\\file.zip", "text": "保存到 C:\\download\\file.zip"}},
}
```
```
观察: 下载成功 - 下载
结果: 下载完成，102400字节，保存到 C:\download\file.zip
```

### 6.5 Shell工具

**execute_shell_command 成功**：
```python
# data
data = {"output":"Handles  NPM(K)...","error_output":""}

# llm_data（builder 产出）
llm_data = {
    "summary": "命令执行成功，退出码0",
    "action": {"tool": "execute_shell_command", "tool_zh": "执行", "params": {"command": "Get-Process"}},
    "target": "Get-Process",
    "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"exit_code": {"value": 0, "text": "退出码0"}},
}
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
# data
data = {"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50},"disk":{"C:":{"total_gb":500,"used_pct":60}}}

# llm_data（builder 产出）
llm_data = {
    "summary": "获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)",
    "action": {"tool": "get_system_info", "tool_zh": "获取", "params": {}},
    "target": "system",
    "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
}
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
# data
data = {"events":[...]}

# llm_data（builder 产出）
llm_data = {
    "summary": "获取事件日志(Application)，10条记录",
    "action": {"tool": "event_log", "tool_zh": "获取", "params": {"log_name": "Application"}},
    "target": "event_log/Application",
    "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"total": {"value": 10, "text": "10条记录"}, "level": {"value": "Error", "text": "Error级别"}},
}
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
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "点击屏幕(500,300)，左键单击",
    "action": {"tool": "mouse_click", "tool_zh": "点击", "params": {"x": 500, "y": 300, "button": "left"}},
    "target": "screen(500,300)",
    "status": {"exec_code": "success", "message": "点击成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"button": {"value": "left", "text": "左键"}, "click_type": {"value": "single", "text": "单击"}},
}
```
```
观察: 点击成功 - 点击
结果: 点击屏幕(500,300)，左键单击
```

**screen_capture 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "截图保存到 C:\\capture.png，1920×1080",
    "action": {"tool": "screen_capture", "tool_zh": "截图", "params": {}},
    "target": "screen",
    "status": {"exec_code": "success", "message": "截图成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"file_path": {"value": "C:\\capture.png", "text": "保存到 C:\\capture.png"}, "width": {"value": 1920, "text": "1920px"}, "height": {"value": 1080, "text": "1080px"}},
}
```
```
观察: 截图成功 - 截图
结果: 截图保存到 C:\capture.png，1920×1080
```

### 6.8 注册表工具

**registry_read 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "读取 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)",
    "action": {"tool": "registry_read", "tool_zh": "读取", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
    "target": "HKCU\\Software\\MyApp\\LastLogin",
    "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"value": {"value": "2026-06-20", "text": "\"2026-06-20\""}, "value_type": {"value": "REG_SZ", "text": "REG_SZ类型"}},
}
```
```
观察: 读取成功 - 读取
结果: 读取 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)
```

**registry_write 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "写入 HKCU\\Software\\MyApp\\LastLogin = \"2026-06-20\"(REG_SZ)，旧值=\"2026-06-19\"",
    "action": {"tool": "registry_write", "tool_zh": "写入", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
    "target": "HKCU\\Software\\MyApp\\LastLogin",
    "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"new_value": {"value": "2026-06-20", "text": "新值=\"2026-06-20\""}, "old_value": {"value": "2026-06-19", "text": "旧值=\"2026-06-19\""}, "value_type": {"value": "REG_SZ", "text": "REG_SZ类型"}},
}
```
```
观察: 写入成功 - 写入
结果: 写入 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)，旧值="2026-06-19"
```

### 6.9 定时器工具

**timer_set 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "定时器设置成功，30秒后触发",
    "action": {"tool": "timer_set", "tool_zh": "设置", "params": {"delay_seconds": 30}},
    "target": "timer",
    "status": {"exec_code": "success", "message": "设置成功", "code": "", "detail": "", "hint": ""},
    "metrics": {"delay_seconds": {"value": 30, "text": "30秒"}, "trigger_time": {"value": "2026-06-20 10:51:00", "text": "触发时间 10:51:00"}},
}
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
# data（builder 从 data.error_detail 识别错误状态）
data = {"error_detail":"文件路径不存在","params":{"encoding":"utf-8"}}

# llm_data（builder 产出）
llm_data = {
    "summary": "文件 C:\\notexist.txt 不存在",
    "action": {"tool": "read_text_file", "tool_zh": "读取", "params": {"file_path": "C:\\notexist.txt"}},
    "target": "C:\\notexist.txt",
    "status": {"exec_code": "error", "message": "文件不存在", "code": "ERR_FILE_NOT_FOUND", "detail": "文件路径不存在", "hint": "请检查路径是否正确"},
}
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
# data
data = {"error_detail":"near SELCT: syntax error","params":{"sql":"SELCT * FROM users","connection_type":"sqlite"}}

# llm_data（builder 产出）
llm_data = {
    "summary": "SQL执行失败: near \"SELCT\": syntax error",
    "action": {"tool": "query_sql", "tool_zh": "查询", "params": {"sql": "SELCT * FROM users"}},
    "target": "SELCT * FROM users",
    "status": {"exec_code": "error", "message": "SQL语法错误", "code": "ERR_SQL_EXEC", "detail": "near SELCT: syntax error", "hint": "请检查SQL语法"},
}
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
# data
data = {"error_detail":"pyautogui库未安装","params":{"library":"pyautogui","install_command":"pip install pyautogui"}}

# llm_data（builder 产出）
llm_data = {
    "summary": "需要安装 pyautogui 库",
    "action": {"tool": "mouse_click", "tool_zh": "点击", "params": {}},
    "target": "desktop_automation",
    "status": {"exec_code": "error", "message": "依赖库未安装", "code": "ERR_NO_PYAUTOGUI", "detail": "pyautogui库未安装", "hint": "请先执行安装命令"},
}
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
# data
data = {"error_detail":"连接超时，30秒未响应","params":{"url":"https://slow-api.com","timeout":30}}

# llm_data（builder 产出）
llm_data = {
    "summary": "请求 https://slow-api.com 超时，30秒未响应",
    "action": {"tool": "http_request", "tool_zh": "请求", "params": {"url": "https://slow-api.com"}},
    "target": "https://slow-api.com",
    "status": {"exec_code": "error", "message": "请求超时", "code": "ERR_TIMEOUT", "detail": "连接超时，30秒未响应", "hint": "请稍后重试或检查网络连接"},
}
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
# data
data = {"affected_rows": 50000, "threshold": 10000, "sql": "UPDATE users SET ...", "rolled_back": True}

# llm_data（builder 产出）
llm_data = {
    "summary": "SQL影响50000行，超过安全阈值10000，已自动回滚",
    "action": {"tool": "execute_sql", "tool_zh": "执行", "params": {"sql": "UPDATE users SET ..."}},
    "target": "UPDATE users SET ...",
    "status": {"exec_code": "warning", "message": "影响行数超过安全阈值", "code": "WARNING_DB_SAFETY", "detail": "操作影响行数超过安全阈值，已自动回滚", "hint": "请使用WHERE子句缩小影响范围"},
    "metrics": {"affected_rows": {"value": 50000, "text": "影响50000行"}, "threshold": {"value": 10000, "text": "安全阈值10000"}},
}
```
```
观察: 影响行数超过安全阈值 - 执行
⚠ 警告: 操作影响行数超过安全阈值，已自动回滚
结果: SQL影响50000行，超过安全阈值10000，已自动回滚
建议: 请使用WHERE子句缩小影响范围
```

---

## 九、实现方案

### 9.1 两阶段改造

| 阶段 | 改造内容 | 影响范围 | 依赖 |
|------|---------|---------|------|
| **Phase 1** | Tool注册builder + build_result重构，result统一为data/llm_data/other_data三字段 + observation_formatter重写（format_llm_observation） | 21个工具文件 + 5个核心文件 | 无 |
| **Phase 2** | ToolStep瘦身 + Observation step承载全部信息，tool_step只做管道不加工 | 3-4个核心文件 | Phase 1 |

### 9.2 Phase 1实施清单

| 步骤 | 内容 | 涉及文件 | 5.9章节 |
|------|------|---------|---------|
| 0 | **清查**：全量搜索 llm_data 引用，按"定义/构建/消费/传递/注释"分类，逐处标注处理方式（保留/修改/删除），确保无遗漏后再进入步骤1 | 整个 backend/ | — |
| 1 | 更新tool_response.py：register_builder + _default_builder + build_result | `backend/app/tools/tool_response.py` | 5.9.2 / 5.9.3 |
| 2 | 给每个工具添加builder函数 + register_builder() + time.perf_counter() | 14个工具文件 + 7个helper文件（共21个） | 5.9.2.2 / 5.9.7 |
| 3 | 重写observation_formatter.py → format_llm_observation(data, llm_data)，清除旧格式化函数 | `backend/app/services/agent/observation_formatter.py` | 5.9.6 |
| 4 | 更新message_utils.py的build_observation_text桥接层，清除旧的build_execution_result_dict调用 | `backend/app/services/agent/agent_utils/message_utils.py` | 5.9.6 |
| 5 | 更新action_handler.py适配新result三字段，清除旧格式字段读取 | `backend/app/services/agent/core_agent/handlers/action_handler.py` | 5.9.8 |
| 6 | 更新tool_step.py适配新result结构，清除旧格式字段 | `backend/app/steps/tool_step.py` | 5.9.8 |
| 7 | 收尾统一清理：删除tool_response.py中的旧build_success/build_error/build_warning函数及相关常量 | `backend/app/tools/tool_response.py` | 3.6 |
| 8 | 完整回归测试 | — | — |

#### 9.2.1 分批实施策略

**总工作量**：21个工具文件（14个工具实现 + 7个helper），604处 build_xxx 调用（build_success=162, build_error=440, build_warning=2）需要替换为 build_result。604处不可能一次完成，按模块分8批执行。

**核心原则**：
1. 先清查再动手 — 步骤0全量摸底后，确保无遗漏再开始改造
2. 框架优先 — 先把5个核心文件改完，让新管道跑通
3. 分批推进 — 每批2-3个文件，改完立刻跑测试验证
4. 验证通过再下一批 — 不累积未验证的修改

#### 9.2.2 步骤0：全量清查旧llm_data代码

**目标**：动手改造前，把整个backend/里所有旧llm_data相关代码全部翻出来，逐处标注处理方式，确保改的时候不遗漏。

**清查方法**：

```
1. 全局搜索 "llm_data" 字符串（排除 __pycache__）
2. 逐处记录：文件路径、行号、代码行、上下文
3. 分类标注：
   - 【定义】函数参数中作为形参出现
   - 【构建】在函数体内构建 llm_data dict 并传给 build_success/build_error
   - 【消费】从 result dict 中读取 llm_data
   - 【传递】调用其他函数时作为实参传入
   - 【注释】仅在注释/文档中提及
4. 逐处标注处理方式：
   - 保留 → 新格式也需要的功能（如 format_llm_observation 消费 llm_data）
   - 修改 → 适配新格式（如 action_handler 读取方式）
   - 删除 → 旧逻辑不再需要（如旧格式化函数、内联构建）
5. 输出清查清单，确认无遗漏后进入步骤1
```

**输出物**：一份完整的 `旧llm_data代码清查清单.md`，包含所有引用位置和处理方式。

**清查清单格式参考**（按位置列出每处旧代码及其处理方式）：

| 位置 | 需清除/修改的旧代码 | 处理方式 | 执行时机 |
|------|-------------------|---------|---------|
| `observation_formatter.py` | extract_status、build_execution_result_dict、_extract_display_data、_append_data、_format_summary_parts、_format_result_observation等旧格式化函数 | **删除**（重写时替换） | 框架批 |
| `message_utils.py` | build_observation_text 中的 build_execution_result_dict 调用 | **删除**（改为直接调 format_llm_observation） | 框架批 |
| `action_handler.py` | result.get("code")、result.get("warning")、result.get("attachment")、result.get("return_direct") | **修改**（改为从 llm_data/other_data 取） | 框架批 |
| `tool_step.py` | execution_result/execution_status/summary/error_message 等旧格式字段 | **修改**（改为从 llm_data+other_data 投射） | 框架批 |
| 各工具文件（21个） | `from app.tools.tool_response import build_success, build_error, build_warning` 导入 + 内联 llm_data 构建代码 | **删除**（改为 build_result + builder） | 每批各自 |
| `tool_response.py` | build_success、build_error、build_warning、_add_optionals、_OPTIONAL_FIELDS、_REQUIRED_FIELDS | **删除**（所有工具改完后） | 收尾 |

#### 9.2.3 框架批（5个核心文件）

**一次性完成，不分批**。框架层改完是整个Phase 1的基座。框架批同时负责清除本层所有旧的llm_data提取和格式化逻辑。

| 文件 | 新增/修改内容 | 同时清除的旧代码 | 验收标准 |
|------|-------------|-----------------|---------|
| `backend/app/tools/tool_response.py` | 新增 register_builder + _default_builder + build_result + 新版 is_success/is_error | 旧函数保留（收尾步骤7才删） | 导入不报错，注册+构建正常 |
| `backend/app/services/agent/observation_formatter.py` | 重写 format_llm_observation(data, llm_data) + 新增 format_data_detail | 清除 extract_status、build_execution_result_dict、_extract_display_data、_append_data、_format_summary_parts、_format_result_observation、_format_success_observation、_format_warning_observation、_format_error_observation、_build_base_text、_append_warning、_append_hint | 新旧格式都能正常格式化 |
| `backend/app/services/agent/agent_utils/message_utils.py` | 更新 build_observation_text 桥接层：拆包 result → (data, llm_data)，直接调 format_llm_observation | 清除 build_execution_result_dict 调用 | observation 文本生成正常 |
| `backend/app/services/agent/core_agent/handlers/action_handler.py` | 适配新3字段 result：build_observation 从 llm_data 取 status.exec_code，从 other_data 取 warning/return_direct/attachment | 清除 result.get("code")、result.get("warning")、result.get("attachment")、result.get("return_direct") 等旧字段读取 | action 处理流程正常 |
| `backend/app/services/agent/steps/tool_step.py` | ToolStep 适配新 result 结构：execution_status 从 llm_data.status.exec_code 取，extra_fields 从 llm_data/other_data 取 | 清除旧格式字段引用：execution_result/execution_status/summary/error_message/action_retry_count/execution_time_ms/code/warning/attachment 改为从 llm_data+other_data 投射 | tool_step 序列化正常 |

**框架批完成后的验证**：
```
pytest -x --tb=short -k "test_tool_response or test_observation or test_message or test_action or test_tool_step"
```

#### 9.2.4 工具分批详表

工具文件共14个实现文件 + 7个 helper 文件，按以下8批执行。

**每批标准步骤**：
```
1. 给文件末尾添加 builder 函数（按5.9.2.2模板）
2. 添加 register_builder() 调用
3. 每个工具函数加 time.perf_counter() 测量（5.9.7规范）
4. 替换所有 build_success/build_error/build_warning → build_result，同时：
   a. 删除 from app.tools.tool_response import build_success, build_error, build_warning 导入
   b. 删除工具函数内内联构建 llm_data={...} 传给 build_success/build_error 的代码
   c. 改为 build_result(tool_name, data=..., other_data=...)，llm_data 由 builder 生成
5. 跑 pytest 验证本批修改
6. 通过 → 下一批
```

| 批 | 文件 | build_success | build_error | build_warning | 合计 | 优先级 |
|:-:|------|:------------:|:----------:|:------------:|:---:|:------:|
| **第1批** | `file/file_tools.py` + `toolhelper/file_helper.py` | 41 | 149 | 0 | **190** | 最高（最大文件，最常用） |
| **第2批** | `document/document_tools.py` | 14 | 40 | 0 | **54** | 高 |
| **第3批** | `system/system_tools.py` + `network/network_tools.py` | 17 | 78 | 0 | **95** | 高 |
| **第4批** | `desktop/desktop_gui_tools.py` + `desktop/desktop_tools.py` | 20 | 40 | 0 | **60** | 中 |
| **第5批** | `shell/shell_tools.py` + `shell/code_execution_tools.py` | 14 | 30 | 0 | **44** | 中 |
| **第6批** | `dataanalysis/dataanalysis_tools.py` + `dataanalysis/database_tools.py` | 8 | 28 | 2 | **38** | 中 |
| **第7批** | `fundamental/fundamental_tools.py` + `fundamental/time_tools.py` + `timer/timer_tools.py` + `win_registry/win_registry_tools.py` | 17 | 34 | 0 | **51** | 低 |
| **第8批** | 剩余6个helper：`data_format_helper.py` + `gui_helper.py` + `common_helper.py` + `network_helper.py` + `db_helper.py` + `window_helper.py` | 31 | 41 | 0 | **72** | 低 |

#### 9.2.5 收尾

框架批 + 工具8批全部完成后：

| 步骤 | 内容 | 验收标准 |
|:----:|------|---------|
| 1 | 删除 tool_response.py 中的旧 build_success/build_error/build_warning 函数 | 旧函数不再被引用（所有工具已改用 build_result） |
| 2 | 同时删除 _add_optionals、_OPTIONAL_FIELDS、_REQUIRED_FIELDS | 同上 |
| 3 | 全局搜索确认无残留的 build_success/build_error/build_warning 调用 | 无匹配 |
| 4 | 运行完整回归测试：`pytest` | failed=0, error=0 |
| 5 | 运行前端检查：`npm run check` | 无错误 |
| 6 | 提交commit + 打patch tag | |

### 9.3 核心改动（参考5.9/5.10章）

#### 9.3.1 format_llm_observation

签名与实现见 **5.9.6**。此处不再重复。

#### 9.3.2 llm_data格式统一

所有工具的llm_data统一为6字段结构，见 **5.2节**。

#### 9.3.3 data格式统一

所有工具的data只放纯业务数据（llm_data没有的大块内容），见 **4.2节**。

#### 9.3.4 build_result函数签名

改造方案见 **5.9.3**。统一为 `build_result(tool_name, data, exec_code, duration_ms, tool_params, other_data, **extra)`，builder_fn由各tool在文件末尾注册。

### 9.4 无Phase 3

原旧版3阶段方案中的Phase 3（统一error格式）已并入Phase 1 —— builder统一处理success/error/warning三种情况（见5.9.3.2），不再单独作为一个阶段。

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
| data放duration_ms | duration_ms是build_result直接参数，builder接收后放入llm_data |
| llm_data=None | 所有工具必须有llm_data |
| llm_data无summary | summary必填 |
| llm_data无status | status必填（内聚所有状态信息） |
| 裁剪llm_data | ReAct循环中禁止裁剪llm_data，只裁剪data |
| 详情用JSON dump | 详情必须用format_data_detail渲染为可读文本 |
| builder猜exec_code | builder**不能**从data内容猜exec_code，必须接收直接参数 |
| data[\"_call_params\"]注入 | tool_params不走data注入，作为builder直接参数传入 |
| **extra放保留字段 | **extra 禁止出现 data/llm_data/other_data，会被过滤 |

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

**文档更新时间**: 2026-06-20 22:45:00  
**版本**: v4.1  
**编写人**: 小健 + 北京老陈 + 小欧