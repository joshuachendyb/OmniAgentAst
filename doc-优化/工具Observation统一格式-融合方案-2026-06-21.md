# 工具 Observation 统一输出格式设计（融合方案）

**创建时间**: 2026-06-20 11:07:25  
**更新时间**: 2026-06-22 17:24:27  
**版本**: v7.2  
**编写人**: 小健 + 北京老陈  
**适用范围**: OmniAgentAs-desk 所有工具给LLM和前端的observation输出格式  
**状态**: 审查通过

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
| v6.0 | 2026-06-21 01:20:00 | **构建方式简化**：取消builder注册机制，改为每个tool直接调用builder函数构建llm_data后传给build_success/error/warning；build_result拆回3个函数（函数名即语义，exec_code不再作为参数） | 小健 |
| v6.1 | 2026-06-21 19:59:40 | **审查修复**：修复5.8节警告模板缺少"详情:"行；修复8.3节警告示例data结构与4.2节定义不一致（遵循零重复原则） | 小健 |
| v6.2 | 2026-06-21 20:06:24 | **精简第9章**：删除9.3冗余节（纯引用无新内容）和9.4节（信息合并到9.1 Phase 1描述） | 小健 |
| v6.3 | 2026-06-21 20:10:07 | **重写9.2实施清单**：按"每个tool处理流程"重组（清理旧代码→建builder→改调用）；明确严禁内联赋值；明确严禁用脚本修改必须手动分析 | 小健 |
| v6.8 | 2026-06-22 15:17:13 | **补充Phase 2审查缺口**：①5.10.4澄清Observation step复用ToolStep（非独立模型）；②5.10.7补充DB迁移步骤；③新增9.3节Phase 2实施清单（5步） | 小欧 |
| v6.9 | 2026-06-22 16:00:00 | **修复Phase 2 4个设计错误**：F1-5.10.7/9.3.1保持现有逻辑→选择性保留（删6冗余字段保3非冗余）；F2-9.3.2并行_status/_other取错，增加合并other_data逻辑；F3-9.3.1补充__init__实际代码；F4-9.3.3修正SSE目标函数和字段名 | 小欧 |
| v7.1 | 2026-06-22 17:12:14 | **5轮复核修复12个问题**：A类6处Phase 2/3标签混淆（5.10标题/表头/实施要点/DB说明）；B类3处9.3格式残留（重复行/多余```/残留字典）；C类3处缺other_data（5.10.2 SSE/DB字段/5.10.4描述）| 小欧 |
| v7.2 | 2026-06-22 17:24:27 | **Phase 2/3分离准确性修复**：D1-5.10.3数据流图标注Phase 3；D2-5.10.3存储规则表标注Phase归属；D3/D4-5.10.6注意事项标注Phase 3；D5-5.10.7 DB表ToolStep列改为Phase 2状态（不变）；Phase 3瘦身目标修正为{code,message,duration_ms}（非仅duration_ms） | 小欧 |
| v7.0 | 2026-06-22 16:30:00 | **拆分Phase 2/3**：action_tool模式的execution_result瘦身和DB存储优化从Phase 2移除，新增9.4节Phase 3实施清单。Phase 2只改observation模式 | 小欧 |

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
- build_success/error/warning保持3个函数（函数名即语义），llm_data由工具直接构建传入，不再由build函数查找builder
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
   ↓ 业务逻辑 + time.perf_counter()
llm_data = _build_xxx_llm_data(exec_code, duration_ms, ...)   ← 工具直接调用builder函数
   ↓
build_success(data=..., llm_data=llm_data)                    ← 函数名即语义，无需exec_code参数
   ↓ result = {data, llm_data, other_data}
build_observation_text(result)                                 ← 桥接层拆包
   ↓
format_llm_observation(data, llm_data)                         ← 不再接收 result dict
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
| builder函数 | 各tools/*.py（紧跟tool函数） | exec_code + duration_ms + 业务参数 | llm_data（5字段结构化摘要） | 从业务参数构建llm_data | 不改data内容 |
| build_success/error/warning | tool_response.py | data, llm_data, other_data | 统一result dict（{data, llm_data, other_data}） | 纯组装result，函数名即语义 | 不构建llm_data，不改llm_data内容 |
| format_llm_observation() | observation_formatter.py | data, llm_data | 三段式文本 | 机械渲染：llm_data→观察+结果行，data→详情行 | 不新增信息，不加工语义 |
| LLM | — | observation文本 | 推理决策 | 直接阅读文本 | 不接触结构化数据 |

**数据流向**：

```
结构化数据（llm_data）→ 渲染 → 自然语言文本（observation）
    ↑                               ↑
  tool直接构建                     formatter层转换
  （工具侧调builder函数）           （框架侧）
```

**关键规则**：

1. **机械渲染**：formatter对llm_data只取值拼接，不加工、不新增、不组合——保证LLM看到的和结构化数据内容一致
2. **单向管道**：结构化数据→文本，不存在反向依赖。改了llm_data结构，formatter自动跟随渲染
3. **分层稳定**：工具侧数据变了，formatter渲染逻辑不变；formatter渲染方式变了，工具侧数据不变

**一致性保证**：

| 修改场景 | 需要改什么 | 不改什么 |
|---------|-----------|---------|
| 新增工具 | 唯一：该工具的builder函数 + tool函数中调用 | formatter、build_success/error/warning、前端渲染 |
| 修改llm_data字段内容 | 唯一：该tool的builder函数 | formatter（机械取值） |
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

**原则二：每个tool直接调用builder函数构建llm_data，传给build_success/error/warning**

工具函数内直接调用builder函数构建llm_data，然后传给build_success/error/warning。**不使用注册机制**——工具直接调builder，直线传递，不绕注册表。

build_success/error/warning保持3个函数（不合一），函数名即语义，无需exec_code参数。

新签名、实现代码、旧参数去向、is_success/is_error适配、删除旧代码清单、retry_engine适配、与注册方案对比——详见 **5.9.2节**。

builder函数签名、完整示例、工具函数典型写法——详见 **5.9.3节**。

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
llm_data = {"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":{"tool":"read_text_file","tool_zh":"读取","target":"C:\\test.py","params":{"file_path":"C:\\test.py"}},"status":{...},"metrics":{"lines":{"value":156,"text":"156行"},"bytes":{"value":2380,"text":"2380字节"},"encoding":{"value":"utf-8","text":"UTF-8编码"}}}

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
build_error(data={"file_path": "D:/test.txt"}, llm_data={...})

# 规范后（零重复，action含target/status在llm_data）
build_error(
    data={"error_detail": "文件路径不存在", "params": {"encoding": "utf-8"}},
    llm_data={"summary":"文件 D:/test.txt 不存在","action":{"tool":"read_text_file","tool_zh":"读取","target":"D:/test.txt","params":{"file_path":"D:/test.txt"}},"status":{"exec_code":"error","message":"文件不存在","code":"ERR_FILE_NOT_FOUND","detail":"文件路径不存在","hint":"请检查路径是否正确"}}
)
```

---

## 五、llm_data统一格式规范

### 5.1 llm_data定位

**llm_data = 结构化摘要（唯一持有summary/action含target/status/metrics）**

| 角色 | 消费方式 | 说明 |
|------|---------|------|
| **LLM** | 通过"结果"行消费summary | summary包含action.target/metrics的文字描述 |
| **前端** | 渲染摘要卡片 | summary做标题，tool_zh+target做标签，metrics.text做数字标签 |
| **formatter** | 机械渲染llm_data全部entry | 三段式observation文本：观察行+结果行+详情行 |

**data不再重复llm_data已有的任何字段**（零重复原则）。

### 5.2 llm_data完整结构（5顶层字段，冻结）

```python
llm_data = {
    # === 必填 ===
    "summary": str,     # 自然语言摘要（"读取 C:\test.py，156行，2380字节，UTF-8编码"）
    "action": {         # 操作类型（结构冻结）
        "tool": str,    # function name（"read_text_file"）
        "tool_zh": str, # 中文操作类型（"读取"）
        "target": str,  # 操作目标（路径/URL/查询词/命令，如"C:\test.py"）— 从params中提取的关键参数值，与action天然配对
        "params": dict, # LLM调用参数（{"file_path":"C:\\test.py"}）
    },
    "status": {         # 执行状态（结构冻结）
        "exec_code": str,   # "success" / "error" / "warning"
        "message": str,     # 状态文字（code的自然语言版本，LLM直接消费）
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
| `action` | ✅ | dict | 操作描述，见action子字段表 |
| `status` | ✅ | dict | 执行状态，见status子字段表 |
| `duration_ms` | ❌ | int | 执行耗时（毫秒） |
| `metrics` | ❌ | dict | 关键数字指标，自描述格式 `{"key": {"value": ..., "text": "..."}}`，前端和LLM同等消费 |

**action子字段**（结构冻结，不可增删）：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `tool` | str | function name，如 `"read_text_file"` |
| `tool_zh` | str | 中文操作类型，如 `"读取"` |
| `target` | str | 操作目标，如 `"C:\\test.py"` — 从params中提取的关键参数值，与action天然配对 |
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

#### 5.2.3 action.target取值规则

target本质是action.params中"最关键的那个参数值"（文件路径/URL/查询词/命令），与action描述的是同一件事——"谁对什么做了什么"。前端渲染时 `action.tool_zh + action.target` 天然配对（"读取 C:\test.py"），不需要跨顶层字段组合。

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
| 跳过一个必填字段 | 缺少`action`或`status` | 5字段必须完整 | formatter渲染报错 |
| 自己拼llm_data dict | 各tool自己构造dict | 必须通过builder函数构建后传给build_success/error/warning | 格式不统一，校验缺失 |

### 5.4 各工具类型的llm_data规范参考

以下为各工具类型的关键llm_data字段规范。完整代码示例见第六章。

#### 5.4.1 文件操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
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

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| query_sql | 查询 | SQL摘要 | row_count, columns | 查询返回5行，列: id, name, email |
| execute_sql | 执行 | SQL摘要 | affected_rows | SQL执行成功，影响5行 |
| get_db_schema | 获取 | "database" | total | 获取到3个表的结构: users, orders, products |

#### 5.4.3 文档操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| read_pdf | 读取 | 文件路径 | pages, chars | 读取 C:\report.pdf，5页，12000字符 |

#### 5.4.4 网络/搜索操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| search_web | 搜索 | 搜索词 | total, engine | 搜索到8条结果(Parallel引擎) |
| http_request | 请求 | URL | status_code, content_type, body_len | HTTP GET https://api.example.com，200，15KB |

#### 5.4.5 Shell执行

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| execute_shell | 执行 | 命令摘要 | exit_code | 命令执行完成，退出码0 |

#### 5.4.6 系统操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| get_system_info | 获取 | info_type | 各指标平铺 | CPU: 8核/45% |
| get_event_log | 查询 | 日志源 | count, level | System日志: 15条错误 |
| list_processes | 列出 | "all" | count | 当前120个进程 |
| list_services | 列出 | "all" | count | 当前80个服务 |
| reboot_system | 重启 | "scheduled" | delay | 系统计划60秒后重启 |

#### 5.4.7 桌面操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| screenshot | 截图 | 文件路径 | size, width, height | 截图已保存，512KB，1920×1080 |
| mouse_click | 点击 | "click" | x, y, button | 鼠标点击 (100,200) 左键 |
| keyboard_type | 输入 | "type" | text | 输入文本 "hello" |
| window_control | 操作 | 窗口标题 | action, x, y, w, h | 移动窗口"记事本"到 (0,0) |

#### 5.4.8 注册表操作

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| registry_read | 读取 | 注册表路径 | value, type | 读取 HKLM\...\key，REG_SZ |
| registry_write | 写入 | 注册表路径 | type | 写入 HKLM\...\key，REG_SZ |
| registry_delete | 删除 | 注册表路径 | — | 删除 HKLM\...\key |

#### 5.4.9 基础工具

| 工具 | tool_zh | action.target | 核心metrics | summary示例 |
|------|---------|--------|------------|------------|
| ask_question | 询问 | "question"/"confirm" | — | 询问用户确认 |
| finish | 完成 | "success"/"failed" | reason | 任务完成 |
| think | 思考 | "" | thought | 思考中... |
| execute_code | 执行 | 语言 | exit_code, stdout, stderr | Python代码执行完成，退出码0 |
| get_current_time | 获取 | "local"/"utc" | datetime, timezone | 当前时间 2026-06-20 15:30:00(Asia/Shanghai) |
| tool_search | 搜索 | 搜索词 | total | 搜索到3个匹配工具 |

**tool_search的data格式**：`data = {"matches": [...]}`（matches是业务数据列表，不是关键数字指标，放data不放metrics。tool_executor从 `result.data.matches` 取值）

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
│ 读取 | C:\test.py | 156行 | 2380字节 | UTF-8  │  ← action.tool_zh + action.target + metrics.text
│                                    [展开详情▼] │  ← 可折叠data
└──────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────┐
│ 🔍 搜索到8条结果(Parallel引擎)                │  ← summary
│ 搜索 | 低空星链通信 | 8条结果 | Parallel引擎    │  ← action.tool_zh + action.target + metrics.text
│                                    [展开详情▼] │
└──────────────────────────────────────────────┘
```

### 5.7 llm_data全覆盖

**所有工具必须有llm_data**（当前8/10有，2/10没有）。这是强制规范。

### 5.8 给LLM的message组装过程及样式

**简要流程**：tool函数 → builder函数构建llm_data → build_success/error/warning组装result → observation文本 → FC协议消息对 → conversation_history → 发给LLM

```
tool函数执行
  ↓
llm_data = _build_xxx_llm_data(exec_code, duration_ms, ...)   ← 工具直接调用builder函数
  ↓
build_success(data=..., llm_data=llm_data)                    ← 函数名即语义，无需exec_code参数
  ↓ result = {data, llm_data, other_data}
build_observation_text(result)                                 ← 桥接层拆包
  ↓
format_llm_observation(data, llm_data)                         ← 不再接收 result dict
  ├─ llm_data → 观察行(status.message - action.tool_zh)
  ├─ llm_data → 结果行(summary)
  └─ data → 详情行(format_data_detail渲染)
  ↓
三段式observation文本（role=tool, content=文本）
  ↓
发给LLM
```

**关键函数**：

| 函数 | 文件 | 职责 |
|------|------|------|
| `_build_xxx_llm_data(...)` | 各tools/*.py | 从业务参数构建llm_data（5字段结构化摘要） |
| `build_success/error/warning(data, llm_data, other_data)` | tool_response.py | 纯组装result dict，不构建llm_data |
| `format_llm_observation(data, llm_data)` | observation_formatter.py | data+llm_data → observation文本 |
| `build_observation_text()` | message_utils.py | 桥接，拆包result后调format_llm_observation |
| `MessageBuilder.add_observation()` | message_builder.py | observation文本 → FC协议消息对 |
| `MessageBuilder.prepare_messages_for_llm()` | message_builder.py | conversation_history → 发给LLM的messages |

**llm_data和data在流程中的位置**：

```
llm_data = _build_read_text_file_llm("success", 25, "C:\\test.py", 156, 2380, "utf-8")
  ↓
build_success(data={"content":"def hello():..."}, llm_data=llm_data)
  ↓
result = {"data": {"content":"def hello():..."},
           "llm_data": {"summary":"读取 C:\\test.py，156行","action":{"tool":"read_text_file","tool_zh":"读取","target":"C:\\test.py","params":{"file_path":"C:\\test.py"}},"status":{...},"metrics":{...}},
           "other_data": {}}
  ↓                ↑ data在这里                    ↑ llm_data由builder函数构建后传入
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
| 警告 | `观察: {status.message} - {action.tool_zh}\n⚠ 警告: {status.detail}\n结果: {summary}\n详情:\n{format_data_detail(data)}\n建议: {status.hint}` |

**关键点**：observation文本是tool消息的content，LLM直接阅读这段文本理解工具结果，无需解析JSON。
---

### 5.9 Phase 1：build 3 函数重构 + 工具直接调用 builder，result 统一为 data/llm_data/other_data

#### 5.9.1 设计目标

Phase 1 是本次改造的核心阶段，目标：

| # | 目标 | 说明 |
|---|------|------|
| 1 | **llm_data 由各 tool 直接调用 builder 函数构建** | 工具函数内直接调builder函数构建llm_data，传给build_success/error/warning，不使用注册机制 |
| 2 | **result 统一为 3 字段** | `data`（业务数据）+ `llm_data`（结构化摘要）+ `other_data`（额外控制字段） |
| 3 | **format_llm_observation 直接收 data + llm_data** | 不再从 result dict 提取，signature 扁平化 |
| 4 | **清理旧 llm_data 相关代码** | 废弃的提取函数全部删除 |

#### 5.9.2 build_success/error/warning 3函数重构

**构建方式**：每个tool直接调用builder函数构建llm_data，传给build_success/error/warning。不使用注册机制——工具直接调builder，直线传递，不绕注册表。

build_success/error/warning保持3个函数（不合一），函数名即语义，无需exec_code参数。

**新签名与旧签名的对比**：

```python
# ── 旧签名（当前代码）──
def build_success(data=None, message="执行成功", warning=None, llm_data=None,
                  retry_count=0, return_direct=False, attachment=None, code=None, **extra)
def build_error(code, message, data=None, warning=None, llm_data=None, attachment=None, **extra)
def build_warning(code, message, data=None, llm_data=None, attachment=None, **extra)

# ── 新签名（改造后）──
def build_success(data=None, llm_data=None, other_data=None, **extra)
def build_error(data=None, llm_data=None, other_data=None, **extra)
def build_warning(data=None, llm_data=None, other_data=None, **extra)
```

**删除的参数及去向**：

| 旧参数 | 去向 | 原因 |
|--------|------|------|
| message | llm_data.status.message | 信息内聚于status，build函数不再单独持有 |
| code | llm_data.status.code | 同上 |
| warning | other_data["warning"] | 控制字段归入other_data输出通道 |
| retry_count | other_data["retry_count"] | 同上 |
| return_direct | other_data["return_direct"] | 同上 |
| attachment | other_data["attachment"] | 同上 |

**新增的参数**：

| 新参数 | 说明 |
|--------|------|
| llm_data | 从可选变必填（5字段结构化摘要，builder构建后传入） |
| other_data | 新增输出通道（承载warning/retry_count/return_direct/attachment） |

**实现代码**：

```python
_RESERVED_TOP_KEYS: set = {"data", "llm_data", "other_data"}

def build_success(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建成功响应 — 纯组装result，不构建llm_data"""
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result

def build_error(data: Any = None, llm_data: Optional[Dict] = None,
                other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建错误响应 — 纯组装result，不构建llm_data"""
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result

def build_warning(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建警告响应 — 纯组装result，不构建llm_data"""
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result
```

**is_success/is_error适配**：

```python
def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功 — 从llm_data.status.exec_code判断"""
    exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code", "")
    return exec_code in ("success", "warning")

def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败 — 从llm_data.status.exec_code判断"""
    exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code", "")
    return exec_code == "error"
```

**删除的旧代码**：

| 删除项 | 说明 |
|--------|------|
| `_REQUIRED_FIELDS` | 旧格式必填字段（code/data/message），新格式不需要 |
| `_OPTIONAL_FIELDS` | 旧格式可选字段（warning/llm_data/retry_count/return_direct/attachment），新格式不需要 |
| `_add_optionals()` | 旧格式可选字段写入逻辑，新格式不需要 |
| `register_builder()` | 注册机制，新方案不使用 |
| `_default_builder()` | 兜底builder，新方案不使用 |
| `_BUILDERS` | 注册表字典，新方案不使用 |
| `build_result()` | 合一函数，拆回3个替代 |

**tool_retry_engine的特殊适配**：

| 位置 | 旧用法 | 新用法 |
|------|--------|--------|
| `_build_retry_error` | `build_error(code, message, retry_count=N, error_message=msg, error_type=type)` | `build_error(data=..., llm_data=..., other_data={"retry_count": N}, error_type=type)` |
| 工具未找到(L91) | `build_error(ERR_TOOL_NOT_FOUND, message, retry_count=0, ...)` | `build_error(data=..., llm_data=..., other_data={"retry_count": 0}, ...)` |
| ERR_结果注入(L153-154) | `result["retry_count"] = engine.attempt_count` | 从other_data取，不再直接修改result |
| 成功包装(L156) | `build_success(data=result, message=..., retry_count=N)` | **直接透传工具返回的result**，不再二次包装 |

**为什么拆回3个而不是合一**：

| 维度 | build_result合一 | build_success/error/warning拆3个 |
|------|-----------------|--------------------------------|
| 调用方式 | `build_result(data=..., llm_data=..., exec_code="success")` | `build_success(data=..., llm_data=...)` |
| exec_code | 每次都要传，与llm_data.status.exec_code冗余 | 不用传，函数名已表达 |
| 可读性 | 看不出是成功还是错误 | 一眼看出语义 |
| 函数体 | 3个函数体完全相同 | 3个函数体完全相同 |

3个函数体相同，但函数名不同——**函数名即文档**，比参数表达语义更直接（KISS-DIRECT）。

**与注册方案的对比**：

| 维度 | 注册+查找（旧方案） | 直接调用builder（新方案） |
|------|---------------------|--------------------------|
| 调用路径 | tool_name→查表→调builder→build_result | tool直接调builder→build_success/error/warning |
| 基础设施 | _BUILDERS字典+register_builder+查找逻辑 | 不需要，删掉 |
| 可读性 | 看工具函数看不到llm_data怎么来的 | 工具函数里直接看到builder调用 |
| 遗漏风险 | 忘记register→走默认builder→信息丢失 | 忘记调builder→llm_data=None→立即暴露 |
| build函数 | 1个build_result(exec_code参数冗余) | 3个函数名即语义 |

#### 5.9.3 builder函数设计

每个tool文件内定义一个`_build_xxx_llm_data`函数，紧跟tool函数。builder函数接收业务参数，返回完整5字段llm_data。

**builder签名**：

```python
def _build_xxx_llm_data(exec_code: str, duration_ms: int, ..., 业务参数) -> dict:
    """xxx工具的llm_data构建函数 — 工具直接调用"""
```

**builder接收exec_code，不猜状态**：

builder不再从data内容猜测exec_code，而是接收调用者显式传入。builder按exec_code分支返回不同的status内容。

**builder完整示例**：

```python
def _build_read_text_file_llm(exec_code, duration_ms, file_path, line_count, file_size, encoding):
    """read_text_file的llm_data构建函数 — 工具直接调用"""
    if exec_code == "error":
        return {
            "summary": f"文件 {file_path} 不存在",
            "action": {"tool": "read_text_file", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "文件不存在", "code": "ERR_FILE_NOT_FOUND", "detail": f"路径不正确: {file_path}", "hint": "请检查文件路径是否正确"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"文件为空: {file_path}",
            "action": {"tool": "read_text_file", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "warning", "message": "文件为空，可能不是预期内容", "code": "WARNING_EMPTY_FILE", "detail": "文件内容为空字符串", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {"lines": {"value": 0, "text": "0行"}, "bytes": {"value": 0, "text": "0字节"}},
        }
    return {
        "summary": f"读取 {file_path}，{line_count}行，{file_size}字节，{encoding}编码",
        "action": {"tool": "read_text_file", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"lines": {"value": line_count, "text": f"{line_count}行"}, "bytes": {"value": file_size, "text": f"{file_size}字节"}},
    }
```

**工具函数典型写法**：

```python
# file_tools.py
def read_text_file(file_path):
    t0 = time.perf_counter()
    content = do_read(file_path)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    exec_code = "success" if content else "error"
    llm_data = _build_read_text_file_llm(exec_code, duration_ms, file_path, ...)
    if exec_code == "success":
        return build_success(data={"content": content}, llm_data=llm_data)
    else:
        return build_error(data={"error_detail": "文件不存在"}, llm_data=llm_data)
```

**调用链**：tool函数 → builder函数构建llm_data → build_success/error/warning组装result。直线传递，不绕注册表。

**原则**：

| 原则 | 说明 |
|------|------|
| **builder接收业务参数，不读data** | builder直接接收执行结果（line_count/file_size等），不从data提取，避免data与metrics重复 |
| **新增 tool 只需写 builder 函数** | build 3 函数零改动 |
| **已有 tool 增减字段只改自己的 builder** | 不影响其他 tool |
| **builder 不猜 exec_code** | exec_code 由调用者显式传入 |
| **data只放纯业务数据** | data不含摘要数字（line_count/bytes等在builder参数里，放入metrics），保证零重复 |

#### 5.9.4 result 结构定义

```python
result = {
    "data": Any,               # tool 的主要业务数据（给 LLM 详情 + 前端面板）
    "llm_data": {              # 结构化摘要（给 LLM 三段式 + 前端卡片渲染）
        "summary": str,        #   结果摘要描述
        "action": {            #   操作描述
            "tool": str,       #     工具标识
            "tool_zh": str,    #     工具中文名
            "target": str,     #     操作目标（从params中提取的关键参数值）
            "params": dict,    #     调用参数
        },
        "status": {            #   执行状态
            "exec_code": str,  #     "success" / "error" / "warning"
            "message": str,    #     人类可读消息
            "code": str,       #     详细错误码
            "detail": str,     #     详细错误信息
            "hint": str,       #     失败后的替代建议
        },
        "duration_ms": int,    #   执行耗时（ms）
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

#### 5.9.5 `format_llm_observation` 重构

##### 5.9.5.1 新签名

```python
def format_llm_observation(data: Any, llm_data: Dict) -> str:
    """格式化工具结果为 LLM observation 文本
    
    llm_data → 观察行 + 结果行（三段式的前两段）
    data     → 详情行（通过 format_data_detail，4.3.2 节）
    """
```

不再接收 result dict，直接接收 `data` 和 `llm_data` 两个参数。

##### 5.9.5.2 内部逻辑

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

    # ── 错误/警告时追加 hint ──
    if exec_code in ("error", "warning"):
        hint = status.get("hint", "")
        if hint:
            text += f"\n建议: {hint}"

    return text
```

注意：`metrics` 不走 format_llm_observation 的 observation 文本，而是通过 llm_data 结构化传入 LLM（前端和LLM同等消费）。summary 已包含关键指标的文字描述。

#### 5.9.6 duration_ms 测量规范

`duration_ms` 是 `llm_data` 的标准字段，由工具函数内 `time.perf_counter()` 测量，作为 builder 函数的参数传入。

**写法**：
```python
def read_text_file(file_path: str):
    t0 = time.perf_counter()
    try:
        content = do_read(file_path)
    except FileNotFoundError:
        content = None
    duration_ms = int((time.perf_counter() - t0) * 1000)
    exec_code = "success" if content else "error"
    llm_data = _build_read_text_file_llm(exec_code, duration_ms, file_path, ...)
    if exec_code == "success":
        return build_success(data={"content": content}, llm_data=llm_data)
    else:
        return build_error(data={"error_detail": "文件不存在"}, llm_data=llm_data)
```

**builder 接收** — builder 签名已包含 `duration_ms`，直接使用：
```python
def _build_read_text_file_llm(exec_code, duration_ms, file_path, line_count, file_size, encoding):
    return {
        ...
        "duration_ms": duration_ms,  # ← 直接参数，不猜
        ...
    }
```

**优势**：
1. `duration_ms` 不污染 data（data 只放业务字段）
2. builder 逻辑更清晰：`exec_code` + `duration_ms` 来自调用者，builder 只负责组装

**并行执行下依然准确**：每个工具独立 `time.perf_counter()` 测量，互不干扰。

**重试场景下的duration_ms定义**：

duration_ms = **最后一次工具执行的纯耗时**（不含重试间隔、不含重试次数）。

| 场景 | duration_ms含义 | 说明 |
|------|----------------|------|
| 正常执行 | 本次执行耗时 | 唯一一次 |
| 重试后成功 | 最后一次执行的耗时 | 前几次的耗时丢弃 |
| 重试后仍失败 | 最后一次执行的耗时 | 同上 |

理由：LLM需要知道"这次操作本身花了多久"，判断是否超时。重试是框架行为，不应混入工具执行耗时。如需总耗时，在other_data中加 `total_duration_ms` 字段。

#### 5.9.7 受影响文件

| 文件 | 改动 |
|------|------|
| `tool_response.py` | build_success/error/warning 签名重写（data, llm_data, other_data, **extra）；删除 _REQUIRED_FIELDS/_OPTIONAL_FIELDS/_add_optionals/register_builder/_default_builder/_BUILDERS/build_result；is_success/error 适配 |
| **所有 tool 文件（21个）** | 每个 tool 文件添加 builder 函数；调用处改为 builder→build_success/error/warning；工具函数内部加 `time.perf_counter()` 测 duration_ms |
| `observation_formatter.py` | **重写** — format_llm_observation 改为 `(data, llm_data)`；**删除** `_extract_display_data`、`_append_data`、`_format_summary_parts`、`build_execution_result_dict`；format_data_detail 移入（从 4.3.2 设计）|
| `message_utils.py` | build_observation_text 改为直接调 `format_llm_observation(result["data"], result["llm_data"])` |
| `action_handler.py` | ToolStep "observation" 构建时从 `other_data` 读 return_direct/warning/attachment；ToolStep "action_tool" 的 execution_result 为新 3 字段结构 |
| `steps/tool_step.py` | to_dict 适配新 result 结构 |
| `tool_retry_engine.py` | 透传工具result（不再二次包装）；判断exec_code从 `llm_data.status.exec_code` 取（替代 `result.get("code")`）；自身错误改用build_error(data=..., llm_data=...)；retry_count放入other_data |
| `tool_executor.py` | auto_inject_from_search从 `result.data.matches` 取值（替代旧路径 `result.data.llm_data.matches`） |

#### 5.9.8 不涉及的文件

| 文件 | 原因 |
|------|------|
| `run_sse_stream.py` | 透传 event_dict，不解析字段 |
| `sse_formatter.py` | 透传 JSON 到 SSE，不解析字段 |
| `chat_stream.py` | 透传 execution_steps list，不解析字段 |
| DB 存储层 | 全量 JSON 序列化，不解析字段 |

#### 5.9.9 实施顺序

| 步骤 | 内容 | 验证方式 |
|------|------|---------|
| 1 | `tool_response.py` — 新 build_success/error/warning 签名 + is_success/is_error 适配 | 单测：构建→result 结构正确 |
| 2 | `observation_formatter.py` — 重写 format_llm_observation；format_data_detail 加 try-except 兜底 | 单测：各种 data/llm_data 组合→observation 文本正确 |
| 3 | `message_utils.py` — 适配新签名 | 单测：桥接层正确 |
| 4 | 逐个 tool 文件 — 添加 builder 函数 + 工具函数内部加 time.perf_counter()；替换 build_success/error/warning 调用 | 每个 tool 的 observation 文本正确，duration_ms 准确 |
| 5 | `action_handler.py` — 从 other_data 读字段 | 集成测试：SSE 事件字段正确 |
| 6 | 删除旧代码 | 确认无引用 |
| 7 | 全量集成测试 | 所有场景通过 |

---

### 5.10 最终效果：ToolStep 瘦身 + Observation step 承载全部信息（Phase 2+3）

> **注意**：本节描述Phase 2+3的**最终效果**。实施时分为两阶段：
> - **Phase 2**（9.3节）：只改observation模式，新增llm_data、tool_result和other_data字段
> - **Phase 3**（9.4节）：action_tool模式瘦身，execution_result只存duration_ms
> - ToolStep瘦身（execution_result只存duration_ms）属于**Phase 3**

#### 5.10.1 动机

Phase 1 完成后，formatter 已改为 `(data, llm_data)` 签名，但 ToolStep 和 SSE 通道仍然混杂。ToolStep 的 `execution_result` 同时承载了 llm_data（给前端卡片）和 data（给详情面板），职责不单一。Observation step 只含文本，前端需要的信息分散在两个事件中。

Phase 2+3 将 ToolStep 和 Observation step 的职责彻底分开：

| 事件 | 职责 | 承载内容 |
|------|------|---------|
| **ToolStep** | 告诉前端"工具执行完成" | 仅 `duration_ms` |
| **Observation step** | 告诉前端"工具结果是什么" | `observation_text` + `llm_data` + `tool_result` + `other_data` |

#### 5.10.2 改动内容

| 维度 | 当前 | 最终效果(Phase 2+3) |
|------|------|---------|
| **build 3 函数** | `result={data, llm_data, other_data}` | **不动** |
| **ToolStep** | `execution_result` 含 data + llm_data + duration_ms | `execution_result = {code, message, duration_ms}`，删除data/llm_data <br>*(Phase 3 实施)* |
| **Observation step** | 只含 `observation_text` | 新增 `llm_data` + `tool_result` + `other_data` 字段 <br>*(Phase 2 实施)* |
| **SSE ToolStep 事件** | 发送完整 execution_result | 只发 `{duration_ms}`，code/message/data/llm_data 都不发 <br>*(Phase 3 实施)* |
| **SSE Observation 事件** | 只发 observation_text | 发 `{observation_text, llm_data, tool_result, other_data}` <br>*(Phase 2 实施)* |
| **前端消费** | `ToolStep.execution_result.data` → 详情面板 | `Observation.tool_result` → 详情面板 <br>*(Phase 2: Observation事件取数; Phase 3: ToolStep瘦身)* |
| **前端消费** | `ToolStep.execution_result.llm_data` → 卡片 | `Observation.llm_data` → 卡片 <br>*(Phase 2: Observation事件取数; Phase 3: ToolStep瘦身)* |

#### 5.10.3 新数据流

```
tool 函数执行
  ↓
build_success/error/warning(data=..., llm_data=...)    ← 不动，仍然返回 {data, llm_data, other_data}
  ↓
result = {"data": ..., "llm_data": {...}, "other_data": {...}}
  ↓                       ↓
ToolStep                  build_observation_text(result)
execution_result            ↓
  = {duration_ms}       format_llm_observation(data, llm_data)
  ← Phase 3瘦身          ↓
  ↓                         ↓
SSE: 仅完成时间         observation_text
  ↓                         ↓
前端: 知道"执行完毕"    Observation SSE 事件
                          ├─ observation_text  ← 给LLM，不截断（100轮内完整）
                          ├─ llm_data          ← 给前端，可优化截断
                          ├─ tool_result       ← 给前端渲染详情面板（原 data）
                          └─ other_data        ← 给前端控制字段
```

**数据存储与发送规则**：

| 数据 | DB存储 | SSE发送 | 说明 |
|------|--------|---------|------|
| `observation_text` | 原始完整 | 原始完整 | 给LLM，不做任何处理 |
| `llm_data` | **原始完整** | 可优化截断 | DB存原始，SSE可优化 |
| `tool_result` | **原始完整** | 可优化截断 | DB存原始data，SSE可优化 |
| ToolStep.data | Phase 2不变，Phase 3不存 | Phase 3不发 | Phase 3瘦身：action阶段只存code/message/duration_ms |

**数据截断规则**：

| 数据 | 接收方 | 截断规则 | 说明 |
|------|--------|----------|------|
| `observation_text` | LLM | **不截断** | 100轮对话内保持完整，确保LLM有完整上下文 |
| `llm_data` | 前端 | SSE可优化截断 | 前端只用于展示，metrics过多时只保留前5个 |
| `tool_result` | 前端 | SSE可优化截断 | 大文件内容前端可截断显示 |

**核心原则**：
- **DB存原始数据**：Observation存入DB的llm_data和tool_result必须是原始完整数据，不做任何处理
- **SSE可优化**：发送给前端的数据可以优化截断，减少传输量
- **Action不存data**：Phase 3，ToolStep（action阶段）execution_result瘦身，只存code/message/duration_ms，不存data/llm_data

#### 5.10.4 受影响文件与模型澄清

**模型澄清**：当前代码中不存在独立的 `ObservationStep` 类。"Observation step" 是 `ToolStep` 的一个 `step_type="observation"` 模式（通过 `_extra_fields()` 分支处理）。Phase 2 **不新建独立 ObservationStep 类**，而是继续复用 `ToolStep`，在 observation 模式下新增 `llm_data`、`tool_result` 和 `other_data` 字段。

| 层 | 文件 | 改动 |
|----|------|------|
| **构建层** | `tool_response.py` | **不动** |
| **格式化层** | `observation_formatter.py` | Phase 1 已改 `(data, llm_data)`，Phase 2 不动 |
| **桥接层** | `message_utils.py` | Phase 1 已拆包，Phase 2 不动 |
| **步骤模型** | `tool_step.py` (ToolStep类) | **Phase 2(observation模式)**：`_extra_fields()` 新增 `llm_data`、`tool_result` 和 `other_data` 字段（替代现有6冗余字段）。**Phase 3(action_tool模式)**：`execution_result` 只存 `{"duration_ms": N}`，删除 data/llm_data等字段 |
| **编排层** | `action_handler.py` | `build_observation()` 中：传入 `llm_data`、`tool_result` 和 `other_data`（从result拆包）|
| **SSE 层** | `run_sse_stream.py` | SSE发送时可优化截断，DB存储必须原始完整 |
| **前端** | 消费 ToolStep 的代码 | action_tool事件→只取duration_ms显示loading；observation事件→取llm_data渲染卡片、取tool_result渲染详情面板 |
| **DB 存储** | `save_execution_steps_to_db` | Observation存原始llm_data、tool_result和other_data，ToolStep不存data |

#### 5.10.5 实施要点

1. **ToolStep 瘦身**（Phase 3）：`_execution_result` 只保留 `{code, message, duration_ms}`，**不存 data/llm_data**。

2. **Observation step 新增字段**（Phase 2）：在 `action_handler.py` 的 `build_observation()` 中，把 result["data"] 作为 `tool_result`、result["llm_data"] 作为 `llm_data`、result["other_data"] 作为 `other_data` 字段传入 Observation step。

3. **DB 存储规则**（Phase 2+3）：
   - Observation存入DB的 `llm_data`、`tool_result`、`other_data` 必须是**原始完整数据**，不做任何处理
   - ToolStep存入DB的 `execution_result` Phase 3瘦身为 `{code, message, duration_ms}`，不存 data/llm_data

4. **SSE 发送规则**（Phase 2+3）：
   - ToolStep SSE（Phase 3）→ `{step_type: "action_tool", tool_name, execution_result: {code, message, duration_ms}, ...}`，不发 data/llm_data
   - Observation SSE（Phase 2）→ `{"step_type": "observation", "observation_text": "...", "llm_data": {...}, "tool_result": {...}, "other_data": {...}}`
   - SSE发送时可优化截断（减少传输量），但DB必须存原始完整数据

5. **前端适配**（Phase 2+3）：
   - ToolStep 事件（Phase 3）→ 只用于显示"工具执行中..."状态，从中取execution_result.code/code判断状态，不再取data/llm_data
   - Observation 事件（Phase 2）→ 从中取 `llm_data` 渲染摘要卡片，取 `tool_result` 渲染详情面板，取 `other_data` 获取控制字段

#### 5.10.6 注意事项

| 注意点 | 说明 |
|--------|------|
| **前后端同步** | Phase 2 必须前后端同步上线，不能分步部署 |
| **DB 不兼容** | Phase 2：Observation记录JSON结构变化，旧数据删除；Phase 3：action_tool记录execution_result瘦身，前端遇到旧格式直接报错提示"请刷新页面" |
| **data 为空** | tool_result=None 时，前端跳过详情面板渲染 |
| **LLM 不受影响** | LLM 始终只读 observation_text，底层事件结构变化不影响它 |
| **Phase 1 为前提** | Phase 2 依赖 Phase 1 的 formatter 签名改造，必须先上线 Phase 1 |
| **LLM数据不截断** | 给LLM的observation_text不做截断，100轮对话以内保持完整，确保LLM有完整上下文 |
| **前端数据可优化** | 给前端的llm_data可优化或截断（如metrics过多时只保留前5个），前端只用于展示，不影响LLM |
| **DB存原始数据** | Observation存入DB的llm_data和tool_result必须是原始完整数据，不做任何处理 |
| **Action不存data** | Phase 3：ToolStep（action阶段）execution_result瘦身，只存code/message/duration_ms，不存data/llm_data |

#### 5.10.7 DB表字段更新

Phase 2需要更新Observation step的DB字段，ToolStep字段不变。

**execution_steps表字段**：

| 字段 | 类型 | ToolStep (action_tool) | Observation step | 说明 |
|------|------|------------------------|------------------|------|
| `step_type` | str | "action_tool" | "observation" | 不变 |
| `content` | JSON | `{code, message, data, llm_data, duration_ms}`（Phase 2不变） | `{observation_text, llm_data, tool_result, other_data}` | **Observation字段结构更新**；Phase 3 ToolStep瘦身为`{code, message, duration_ms}` |
| `created_at` | datetime | 自动填充 | 自动填充 | 不变 |

**Observation step的content字段结构**：

```python
# Phase 1（当前）
content = {
    "observation_text": str,  # LLM观察文本
}

# Phase 2（新增3个完整字段，符合DRY原则）
content = {
    "observation_text": str,   # LLM观察文本，不截断
    "llm_data": {              # 新增：完整llm_data
        "summary": str,
        "action": dict,
        "status": dict,
        "duration_ms": int,
        "metrics": dict,
    },
    "tool_result": Any,        # 新增：完整data
    "other_data": {            # 新增：完整other_data
        "warning": str,
        "attachment": Any,
        "return_direct": bool,
        "retry_count": int,
        # ... 其他控制字段
    },
}
```

**前端取值方式**：
- `return_direct` → `content.other_data.return_direct`
- `warning` → `content.other_data.warning`
- `attachment` → `content.other_data.attachment`

**ToolStep的content字段结构**：

```python
# Phase 1 + Phase 2（不变）
content = {
    "code": str,
    "message": str,
    "data": Any,
    "llm_data": dict,
    "duration_ms": int,
}

# Phase 3（瘦身：删除data和llm_data，保留code/message/duration_ms）
content = {
    "code": str,
    "message": str,
    "duration_ms": int,
}
```

**DB迁移说明**：

| 迁移项 | 说明 |
|--------|------|
| **不做兼容** | 新旧数据结构不兼容，禁止向后兼容代码 |
| **旧DB数据删除** | Phase 2上线时删除旧DB所有execution_steps（Observation因JSON结构变化无法兼容；ActionTool虽然结构不变，但step_type在JSON内部无法按类型选择性删除） |
| **前后端同步上线** | Phase 2必须前后端同步上线，不能分步部署 |

**DB迁移步骤**（Phase 2上线时执行）：

```
步骤1: 停止后端服务
步骤2: 备份SQLite数据库文件（~/.omniagent/operations.db）
步骤3: 执行SQL删除旧数据:
        DELETE FROM execution_steps;  /* 旧Observation记录格式不兼容，整体清空 */
步骤4: 部署Phase 2代码（后端+前端同步）
步骤5: 启动后端服务
步骤6: 验证新数据格式正确（发一个工具调用，检查DB中Observation step的content字段结构）
```

#### 5.10.8 并行场景合并规则

LLM同时调用多个工具时，每个工具各产出一个result，Observation step需要合并。

| 字段 | 合并规则 | 说明 |
|------|---------|------|
| `observation_text` | 多个obs_text用 `\n\n` 拼接 | 当前已有此逻辑 |
| `llm_data` | 按详细规则合并（见下表） | LLM需要知道最差状态+所有摘要 |
| `tool_result` | 合并为list：`[{"tool_name": "read_text_file", "data": ...}, ...]` | 前端按tool_name分tab展示 |
| `other_data.warning` | 收集所有非空warning，拼接 | 不丢失任何警告 |
| `other_data.attachment` | 收集所有非空attachment，合并为list | 不丢失任何附件 |
| `other_data.return_direct` | 任一为True则True | 任何一个工具要求直接返回就生效 |

**llm_data 详细合并规则**：

| 字段 | 合并规则 | 示例 |
|------|---------|------|
| `exec_code` | 取最严重的（error > warning > success） | 2个success+1个error → error |
| `summary` | 拼接所有summary，用`\n\n`分隔 | "读取文件成功\n\n写入文件成功" |
| `action` | 取exec_code最严重那个工具的action | error工具的action |
| `status` | 取exec_code最严重那个工具的status | error工具的status |
| `metrics` | 合并所有metrics，key加tool_name前缀 | `{"read_file.lines": {...}, "write_file.bytes": {...}}` |
| `duration_ms` | 取最大值（代表并行执行总耗时） | max([100, 200]) → 200 |

**ToolStep 合并规则**：

| 字段 | 合并规则 | 说明 |
|------|---------|------|
| `duration_ms` | 取最大值 | 代表并行执行的总耗时 |

**合并代码示例**：

```python
def merge_llm_data(all_llm_data: List[Dict]) -> Dict:
    """并行场景llm_data合并 — 小健 2026-06-22"""
    if not all_llm_data:
        return {}
    if len(all_llm_data) == 1:
        return all_llm_data[0]

    # 按严重程度排序
    severity_order = {"error": 3, "warning": 2, "success": 1}
    sorted_data = sorted(all_llm_data,
        key=lambda d: severity_order.get(d.get("status", {}).get("exec_code", "success"), 0),
        reverse=True)

    most_severe = sorted_data[0]

    # 合并metrics（加tool_name前缀）
    merged_metrics = {}
    for llm_d in all_llm_data:
        tool_name = llm_d.get("action", {}).get("tool", "unknown")
        for k, v in llm_d.get("metrics", {}).items():
            merged_metrics[f"{tool_name}.{k}"] = v

    return {
        "summary": "\n\n".join([d.get("summary", "") for d in all_llm_data]),
        "action": most_severe.get("action", {}),
        "status": most_severe.get("status", {}),
        "duration_ms": max([d.get("duration_ms", 0) for d in all_llm_data]),
        "metrics": merged_metrics,
    }


def _merge_other_data(all_other_data: List[Dict]) -> Dict:
    """并行场景other_data合并 — 小健 2026-06-22"""
    merged: Dict[str, Any] = {}
    warnings = []
    attachments = []
    return_direct = False

    for od in all_other_data:
        if od.get("warning"):
            warnings.append(od["warning"])
        if od.get("attachment") is not None:
            attachments.append(od["attachment"])
        if od.get("return_direct"):
            return_direct = True
        # retry_count不合并，只取第一个有值的
        if "retry_count" not in merged and od.get("retry_count") is not None:
            merged["retry_count"] = od["retry_count"]

    if warnings:
        merged["warning"] = "\n\n".join(warnings)
    if attachments:
        merged["attachment"] = attachments if len(attachments) > 1 else attachments[0]
    if return_direct:
        merged["return_direct"] = True
    return merged
```

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
    "action": {"tool": "read_text_file", "tool_zh": "读取", "target": "C:\\test.py", "params": {"file_path": "C:\\test.py", "encoding": "utf-8"}},
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
| target | 嵌在summary里 | 目标标签（action.target） | "C:\test.py" |
| status.message | 观察行 | 状态指示器 | "读取成功" |
| metrics.*.text | 嵌在summary里 | 结构化标签 | "156行 | 2380字节 | UTF-8" |

**write_text_file 成功**：
```python
# data
data = {}

# llm_data（builder 产出）
llm_data = {
    "summary": "写入 C:\\output.txt，50行/1024字节",
    "action": {"tool": "write_text_file", "tool_zh": "写入", "target": "C:\\output.txt", "params": {"file_path": "C:\\output.txt"}},
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
    "action": {"tool": "list_directory", "tool_zh": "列出", "target": "C:\\project\\", "params": {"path": "C:\\project\\"}},
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
    "action": {"tool": "copy_file", "tool_zh": "复制", "target": "C:\\a.txt → C:\\b.txt", "params": {"source": "C:\\a.txt", "destination": "C:\\b.txt"}},
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
    "action": {"tool": "delete_file", "tool_zh": "删除", "target": "C:\\temp.log", "params": {"file_path": "C:\\temp.log"}},
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
    "action": {"tool": "delete_file", "tool_zh": "删除", "target": "C:\\temp.log", "params": {"file_path": "C:\\temp.log"}},
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
    "action": {"tool": "query_sql", "tool_zh": "查询", "target": "SELECT * FROM users", "params": {"sql": "SELECT * FROM users"}},
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
    "action": {"tool": "execute_sql", "tool_zh": "执行", "target": "UPDATE users SET ...", "params": {"sql": "UPDATE users SET ..."}},
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
    "action": {"tool": "get_db_schema", "tool_zh": "获取", "target": "database", "params": {}},
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
    "action": {"tool": "read_pdf", "tool_zh": "读取", "target": "C:\\report.pdf", "params": {"file_path": "C:\\report.pdf"}},
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
    "action": {"tool": "write_docx", "tool_zh": "写入", "target": "C:\\report.docx", "params": {"file_path": "C:\\report.docx"}},
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
    "action": {"tool": "write_xlsx", "tool_zh": "写入", "target": "C:\\data.xlsx", "params": {"file_path": "C:\\data.xlsx"}},
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
    "action": {"tool": "search_web", "tool_zh": "搜索", "target": "低空星链通信 2026", "params": {"query": "低空星链通信 2026"}},
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
    "action": {"tool": "http_request", "tool_zh": "请求", "target": "https://api.example.com", "params": {"url": "https://api.example.com", "method": "GET"}},
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
    "action": {"tool": "download_file", "tool_zh": "下载", "target": "https://example.com/file.zip", "params": {"url": "https://example.com/file.zip"}},
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
    "action": {"tool": "execute_shell_command", "tool_zh": "执行", "target": "Get-Process", "params": {"command": "Get-Process"}},
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
    "action": {"tool": "get_system_info", "tool_zh": "获取", "target": "system", "params": {}},
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
    "action": {"tool": "event_log", "tool_zh": "获取", "target": "event_log/Application", "params": {"log_name": "Application"}},
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
    "action": {"tool": "mouse_click", "tool_zh": "点击", "target": "screen(500,300)", "params": {"x": 500, "y": 300, "button": "left"}},
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
    "action": {"tool": "screen_capture", "tool_zh": "截图", "target": "screen", "params": {}},
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
    "action": {"tool": "registry_read", "tool_zh": "读取", "target": "HKCU\\Software\\MyApp\\LastLogin", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
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
    "action": {"tool": "registry_write", "tool_zh": "写入", "target": "HKCU\\Software\\MyApp\\LastLogin", "params": {"key_path": "HKCU\\Software\\MyApp\\LastLogin"}},
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
    "action": {"tool": "timer_set", "tool_zh": "设置", "target": "timer", "params": {"delay_seconds": 30}},
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
    "action": {              # 必填：操作描述
        "tool": str,         # function name
        "tool_zh": str,      # 中文操作类型
        "target": str,       # 操作目标
        "params": dict,      # LLM调用参数
    },
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
    "action": {"tool": "read_text_file", "tool_zh": "读取", "target": "C:\\notexist.txt", "params": {"file_path": "C:\\notexist.txt"}},
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
    "action": {"tool": "query_sql", "tool_zh": "查询", "target": "SELCT * FROM users", "params": {"sql": "SELCT * FROM users"}},
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
    "action": {"tool": "mouse_click", "tool_zh": "点击", "target": "desktop_automation", "params": {}},
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
    "action": {"tool": "http_request", "tool_zh": "请求", "target": "https://slow-api.com", "params": {"url": "https://slow-api.com"}},
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
    "action": {"tool": str, "tool_zh": str, "target": str, "params": dict},
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
# data（关键数字在llm_data.metrics里，data只放额外上下文）
data = {"sql": "UPDATE users SET ...", "rolled_back": True}

# llm_data（builder 产出）
llm_data = {
    "summary": "SQL影响50000行，超过安全阈值10000，已自动回滚",
    "action": {"tool": "execute_sql", "tool_zh": "执行", "target": "UPDATE users SET ...", "params": {"sql": "UPDATE users SET ..."}},
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
| **Phase 1** | build 3函数重构 + 工具直接调用builder，result统一为data/llm_data/other_data三字段 + observation_formatter重写（format_llm_observation）+ 统一error格式（原Phase 3并入） | 21个工具文件 + 5个核心文件 | 无 |
| **Phase 2** | Observation step承载全部信息（新增llm_data/tool_result/other_data），tool_step observation模式只做管道不加工 | 3-4个核心文件 | Phase 1 |
| **Phase 3** | ToolStep action_tool模式execution_result瘦身（只存code/message/duration_ms，删除data/llm_data）+ DB存储优化 | 2个文件 | Phase 2 |

### 9.2 Phase 1实施清单

#### 9.2.1 核心原则

**严禁用脚本修改代码，必须手动修改进行深入彻底的分析。**

每个tool代码文件的改造必须按以下顺序执行，一步不能跳：

```
步骤1: 清理旧llm_data代码逻辑（删除内联构建、删除旧参数传递）
步骤2: 建立新的builder函数（严禁内联赋值llm_data各个参数）
步骤3: 修改build3函数调用（替换为新签名）
```

#### 9.2.2 每个tool的重构和处理流程（3步）

**步骤1：重构分类的tool独立代码文件**

(1)删除 本分类的现有的代码文件和本分类 的help代码
(2)分类注册tool:一个tool函数一个代码文件,不再设置独立的helper代码文件
(3)代码逻辑必须严格遵守代码10大规模不得违背.

**步骤2：建立新的builder函数**

在tool文件末尾添加 `_build_xxx_llm_data` 函数，**严禁以下行为**：
- ❌ 在builder函数内用字典直接赋值各字段（如 `"message": "读取成功"`）
- ❌ 在builder函数内用变量赋值各字段（如 `msg = "读取成功"; "message": msg`）
- ✅ 必须按5.9.3节模板，用完整5字段结构构建llm_data
1严格执行一个tool函数只能有一个builder llmdta函数 不能多也不能少  必须与注册函数完全对应,使用注册函数名称
--helper代码函数 ,子函数里面严令禁止出现任何定义的llmdata build3函数
2 tool的代码里面的data 不能出现任何切断的操作 ,不管是给前端的还是LLM 这些都统一到后面的 给前端的yield的时候处理
3. 任何tool的计时 只能在主函数里面 子函数除build llmdata外的其他子函数都严令计时

4 =严格遵守代码10大规范要求

**步骤3：修改build3函数调用**

将所有旧签名调用替换为新签名：
```python
# 旧
build_success(data=..., message="执行成功", code=None, llm_data={...})

# 新
build_success(data=..., llm_data=llm_data)
```

#### 9.2.3 全量清查（步骤0）

动手改造前，把整个backend/里所有旧llm_data相关代码全部翻出来，逐处标注处理方式。

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
5. 输出清查清单，确认无遗漏后再开始改造
```

**输出物**：一份完整的 `旧llm_data代码清查清单.md`，包含所有引用位置和处理方式。

#### 9.2.4 框架层改造（5个核心文件）

框架层改造是整个Phase 1的基座，一次性完成。

| 文件 | 新增/修改内容 | 清除的旧代码 |
|------|-------------|-------------|
| `tool_response.py` | 新签名 build_success/error/warning(data, llm_data, other_data, **extra) + 新版 is_success/is_error | 旧签名保留，收尾删除 |
| `observation_formatter.py` | 重写 format_llm_observation(data, llm_data) + 新增 format_data_detail | 清除所有旧格式化函数 |
| `message_utils.py` | 更新 build_observation_text：拆包 result → (data, llm_data)，直接调 format_llm_observation | 清除 build_execution_result_dict 调用 |
| `action_handler.py` | 适配新3字段 result：从 llm_data/other_data 取字段 | 清除 result.get("code/warning/attachment/return_direct") |
| `tool_step.py` | ToolStep 适配新 result 结构 | 清除旧格式字段引用 |

**验证**：
```
pytest -x --tb=short -k "test_tool_response or test_observation or test_message or test_action or test_tool_step"
```

#### 9.2.5 工具层改造（21个文件，分8批）

**总工作量**：21个工具文件（14个工具实现 + 7个helper），604处 build_xxx 调用。

**每批执行流程**（按9.2.2的3步）：
```
1. 清理旧llm_data代码（删除内联构建、删除旧参数）
2. 添加builder函数（按5.9.3模板，严禁内联赋值）
3. 替换build_success/error/warning调用为新签名
4. 跑 pytest 验证
5. 通过 → 下一批
```

| 批 | 文件 | 调用数 | 优先级 |
|:-:|------|:-----:|:------:|
| **第1批** | `file/file_tools.py` + `toolhelper/file_helper.py` | 190 | 最高 |
| **第2批** | `document/document_tools.py` | 54 | 高 |
| **第3批** | `system/system_tools.py` + `network/network_tools.py` | 95 | 高 |
| **第4批** | `desktop/desktop_gui_tools.py` + `desktop/desktop_tools.py` | 60 | 中 |
| **第5批** | `shell/shell_tools.py` + `shell/code_execution_tools.py` | 44 | 中 |
| **第6批** | `dataanalysis/dataanalysis_tools.py` + `dataanalysis/database_tools.py` | 38 | 中 |
| **第7批** | `fundamental/fundamental_tools.py` + `fundamental/time_tools.py` + `timer/timer_tools.py` + `win_registry/win_registry_tools.py` | 51 | 低 |
| **第8批** | 剩余6个helper | 72 | 低 |

#### 9.2.6 收尾

框架层 + 工具8批全部完成后：

| 步骤 | 内容 | 验收标准 |
|:----:|------|---------|
| 1 | 删除 tool_response.py 中的旧 build_success/build_error/build_warning 函数 | 旧函数不再被引用 |
| 2 | 同时删除 _add_optionals、_OPTIONAL_FIELDS、_REQUIRED_FIELDS | 同上 |
| 3 | 全局搜索确认无残留的旧签名调用 | 无匹配 |
| 4 | 运行完整回归测试：`pytest` | failed=0, error=0 |
| 5 | 运行前端检查：`npm run check` | 无错误 |
| 6 | 提交commit + 打patch tag | — |

### 9.3 Phase 2实施清单（仅observation模式，action_tool模式不变）

**前提**：Phase 1全部完成并验证通过。

**范围**：Phase 2只改 **observation模式** 相关代码，action_tool模式的`execution_result`瘦身和DB存储优化拆分到**Phase 3**（9.4节）。

**受影响文件**：3个核心文件（tool_step.py、action_handler.py、run_sse_stream.py）+ 前端消费代码。

**每步必须手动修改，禁止脚本批量修改。**

#### 9.3.1 步骤1：ToolStep新增参数（tool_step.py）

**核心说明**：ToolStep类有两种模式，Phase 2只改observation模式，action_tool模式不变（Phase 3才改）。

| 模式 | step_type | Phase 2改动 | 存储内容 |
|------|-----------|-------------|----------|
| **action_tool模式** | "action_tool" | **不变** | execution_result含完整data+llm_data（Phase 3才瘦身） |
| **observation模式** | "observation" | **新增字段** | llm_data（完整）+ tool_result（完整data）+ other_data（完整） |

修改 `ToolStep.__init__()` 新增 `llm_data`/`tool_result` 参数：

```python
# Phase 2修改前（observation模式 — 当前__init__不含llm_data/tool_result）
def __init__(
    self,
    step: int,
    tool_name: str,
    tool_params: Dict[str, Any],
    *,
    step_type: str = "action_tool",
    execution_status: str = "success",
    summary: str = "",
    execution_result: Any = None,
    error_message: str = "",
    action_retry_count: int = 0,
    execution_time_ms: int = 0,
    observation: str = "",
    return_direct: bool = False,
    code: str = "",
    warning: Optional[str] = None,
    attachment: Any = None,
    timestamp: Optional[int] = None,
):
    ...
    self._attachment = attachment

# Phase 2修改后（新增llm_data/tool_result参数）
def __init__(
    self,
    step: int,
    tool_name: str,
    tool_params: Dict[str, Any],
    *,
    step_type: str = "action_tool",
    execution_status: str = "success",
    summary: str = "",
    execution_result: Any = None,
    error_message: str = "",
    action_retry_count: int = 0,
    execution_time_ms: int = 0,
    observation: str = "",
    return_direct: bool = False,
    code: str = "",
    warning: Optional[str] = None,
    attachment: Any = None,
    timestamp: Optional[int] = None,
    llm_data: Optional[Dict[str, Any]] = None,      # 新增
    tool_result: Any = None,                        # 新增
    other_data: Optional[Dict[str, Any]] = None,    # 新增
):
    ReasoningStep.__init__(self, step, timestamp)
    self.TYPE = step_type
    ...  # 保持现有赋值不变
    self._attachment = attachment
    self._llm_data = llm_data or {}                 # 新增
    self._tool_result = tool_result                 # 新增
    self._other_data = other_data or {}             # 新增
```

修改observation模式的 `_extra_fields()`，新增3个完整字段：

**新增字段**（完整保存，符合DRY原则）：
- `llm_data`：完整的llm_data，不做任何处理
- `tool_result`：完整的data，不做任何处理
- `other_data`：完整的other_data，不做任何处理（含warning/attachment/return_direct/retry_count等）

**删除的旧字段**（已在llm_data或other_data中，不再单独保存）：
- summary/tool_name/tool_params/execution_status/error_message/code → 在llm_data中
- return_direct/warning/attachment → 在other_data中

```python
# Phase 2修改后（observation模式 — 新增llm_data/tool_result/other_data字段）
def _extra_fields(self) -> Dict[str, Any]:
    if self.TYPE == "action_tool":
        ...
    if self.TYPE == "observation":
        obs: Dict[str, Any] = {}
        # 新增字段（完整保存，符合DRY原则）
        if self._llm_data is not None:
            obs["llm_data"] = self._llm_data
        if self._tool_result is not None:
            obs["tool_result"] = self._tool_result
        if self._other_data is not None:
            obs["other_data"] = self._other_data
        return obs
```

**返回结构说明**：

```python
# observation模式的_extra_fields()返回结构（符合DRY原则）
{
    "llm_data": dict,           # 完整llm_data
    "tool_result": Any,         # 完整data
    "other_data": dict,         # 完整other_data（含return_direct/warning/attachment/retry_count等）
}
```

**前端取值方式**：
- `return_direct` → `other_data.return_direct`
- `warning` → `other_data.warning`
- `attachment` → `other_data.attachment`

**验证**：`pytest -x --tb=short -k "test_tool_step"`

#### 9.3.2 步骤2：action_handler适配（action_handler.py）

修改 `build_observation()` 函数：

```python
# Phase 2修改前
events.append(ctx.agent._step_emitter.emit(ToolStep(
    step=ctx.step,
    tool_name=ctx.tool_name,
    tool_params=ctx.tool_params,
    step_type="observation",
    observation=merged_obs,
    execution_status=_status.get("exec_code", ""),
    code=_status.get("code", ""),
    warning=_other.get("warning"),
    attachment=_other.get("attachment"),
    return_direct=_other.get("return_direct", False),
)))

# Phase 2修改后
# 1. 从所有results中提取llm_data和tool_result
_all_llm_data = []
_all_tool_results = []
_all_other_data = []
for r in ctx.results:
    if isinstance(r, dict):
        _all_llm_data.append(r.get("llm_data", {}))
        _all_tool_results.append(r.get("data"))
        _all_other_data.append(r.get("other_data", {}))

# 2. 合并llm_data（串行用第1个，并行用_merge_llm_data）
merged_llm_data = _all_llm_data[0]
if len(_all_llm_data) > 1:
    merged_llm_data = _merge_llm_data(_all_llm_data)

# 3. 合并other_data（串行用第1个，并行合并warning/attachment/return_direct）
merged_other = _all_other_data[0]
if len(_all_other_data) > 1:
    merged_other = _merge_other_data(_all_other_data)  # 见5.10.8

events.append(ctx.agent._step_emitter.emit(ToolStep(
    step=ctx.step,
    tool_name=ctx.tool_name,
    tool_params=ctx.tool_params,
    step_type="observation",
    observation=merged_obs,
    # 新增字段（完整保存，符合DRY原则）：
    llm_data=merged_llm_data,
    tool_result=_all_tool_results[0] if len(_all_tool_results) == 1 else _all_tool_results,
    other_data=merged_other,
)))
```

**注意**：不再单独传`warning`/`attachment`/`return_direct`参数，前端从`other_data`中取值。

**验证**：`pytest -x --tb=short -k "test_action_handler or test_observation"`

#### 9.3.3 步骤3：SSE层适配（run_sse_stream.py + sse_formatter.py）

SSE字段结构由ToolStep._extra_fields()控制（已在9.3.1和9.3.2中修改），format_agent_sse()是纯透传函数无需改动。SSE事件中observation的字段就是to_dict()返回的全部字段。

**observation事件的SSE格式**：
```python
{
    "type": "observation",          # to_dict()的type字段
    "step": N,
    "timestamp": ...,
    "content": "观察: ...\n结果: ...\n",  # observation_text
    "observation": {                # _extra_fields()产出
        "llm_data": {...},          # 完整llm_data
        "tool_result": {...},       # 完整data
        "other_data": {             # 完整other_data
            "return_direct": False,
            "warning": ...,
            "attachment": ...,
            "retry_count": 0,
        },
    },
}
```

**验证**：启动 dev server，发送工具调用，检查 SSE 事件格式。

#### 9.3.4 步骤4：前端适配

修改前端消费 Observation 事件的代码：

```typescript
// 修改前: 从 ToolStep.execution_result 取值
const data = event.execution_result?.data
const llm_data = event.execution_result?.llm_data
const return_direct = event.execution_result?.return_direct

// 修改后: 从 Observation 事件取值
// ToolStep事件 → 只显示 loading
// Observation事件 → 从 observation 字段取值
const llm_data = event.observation?.llm_data           // 渲染卡片
const tool_result = event.observation?.tool_result     // 渲染详情
const other_data = event.observation?.other_data       // 控制字段
const return_direct = other_data?.return_direct        // 是否直接返回
const warning = other_data?.warning                    // 警告
const attachment = other_data?.attachment              // 附件
```

**验证**：`npm run check` + 手动测试工具调用。

#### 9.3.5 步骤5：DB字段更新 + 收尾

执行Observation step的DB字段更新（ToolStep action_tool字段不变，留到Phase 3）：

```
1. DB字段更新（按5.10.7）：Observation的content字段新增llm_data/tool_result/other_data
   - 不做兼容，旧DB数据直接删除
2. 运行完整回归测试: pytest
3. 运行前端检查: npm run check
4. 提交commit + 打patch tag
```

**验证**：`pytest -x --tb=short -k "test_action_handler or test_observation"`

---

### 9.4 Phase 3实施清单（action_tool模式瘦身 + DB存储优化）

**前提**：Phase 2全部完成并验证通过。

**范围**：Phase 3专门处理action_tool模式的`execution_result`瘦身和DB存储优化。action_tool模式当前在`_extra_fields()`中把完整`execution_result`（含code+message+data+llm_data+duration_ms）透传给前端和DB，Phase 3将其压缩为只存`{code, message, duration_ms}`。

**受影响文件**：`tool_step.py`（_extra_fields action_tool模式）+ DB迁移脚本。

#### 9.4.1 步骤1：action_tool模式_execution_result瘦身

```python
# Phase 3修改前（action_tool模式）
def _extra_fields(self) -> Dict[str, Any]:
    if self.TYPE == "action_tool":
        return {
            "tool_name": self._tool_name or "",
            "tool_params": self._tool_params or {},
            "execution_status": self._execution_status,
            "execution_result": self._execution_result,  # 含data+llm_data+duration_ms
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
        }

# Phase 3修改后（action_tool模式）
def _extra_fields(self) -> Dict[str, Any]:
    if self.TYPE == "action_tool":
        return {
            "tool_name": self._tool_name or "",
            "tool_params": self._tool_params or {},
            "execution_status": self._execution_status,
            "execution_result": {
                "code": self._execution_result.get("code", "") if isinstance(self._execution_result, dict) else "",
                "message": self._execution_result.get("message", "") if isinstance(self._execution_result, dict) else "",
                "duration_ms": self._execution_time_ms,
            },  # 只存code/message/duration_ms，删除data/llm_data
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
        }
```

**验证**：`pytest -x --tb=short -k "test_tool_step"`

#### 9.4.2 步骤2：DB字段清理

**变更**：`execution_steps`表的`execution_result`字段不再存储data/llm_data，只存`{code, message, duration_ms}`。

**迁移**：
```sql
-- 无需迁移旧数据（前端读取时兼容旧格式）
-- 新写入的记录自动只存 code/message/duration_ms
```

#### 9.4.3 步骤3：收尾

```
1. 全局搜索确认无残留的旧字段引用（execution_result.data等用于action_tool模式的代码）
2. 运行完整回归测试: pytest
3. 运行前端检查: npm run check
4. 提交commit + 打patch tag
```
---

## 十、规范速查

### 10.1 llm_data五顶层字段（结构冻结）

```python
llm_data = {
    # 必填
    "summary": str,     # 自然语言摘要（"操作+对象+数字"）
    "action": {         # 操作描述（结构冻结）
        "tool": str,    # function name
        "tool_zh": str, # 中文操作类型
        "target": str,  # 操作目标（从params中提取的关键参数值）
        "params": dict, # LLM调用参数
    },
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
| data放duration_ms | duration_ms由builder函数构建后放入llm_data |
| llm_data=None | 所有工具必须有llm_data |
| llm_data无summary | summary必填 |
| llm_data无status | status必填（内聚所有状态信息） |
| 裁剪llm_data | ReAct循环中禁止裁剪llm_data，只裁剪data |
| 详情用JSON dump | 详情必须用format_data_detail渲染为可读文本 |
| builder猜exec_code | builder**不能**从data内容猜exec_code，必须接收显式参数 |
| data放action.target | target在llm_data.action里 |

---

## 十一、设计优势总结

| 优势 | 说明 |
|------|------|
| **每看全懂** | 观察行status.message+action.tool_zh，LLM扫一眼就知道发生了什么 |
| **格式统一** | 所有llm_data都是5字段结构，所有data只放纯业务数据 |
| **信息完整** | status内聚所有状态信息（message/code/detail/hint），metrics自描述关键数字 |
| **零重复** | llm_data管描述，data管内容，同一字段只出现一次，改一处即可 |
| **LLM和前端一视同仁** | metrics自描述（value+text），前端渲染标签，LLM直接看text |
| **前端可控** | 摘要模式只显示llm_data，详情模式展开data |
| **维护简单** | 工具自治，框架不变——新增工具只改自己的builder函数 |
| **结构稳定** | 5顶层字段冻结，action（含target）/status结构冻结，只有metrics开放扩展 |
| **详情可读** | format_data_detail自动渲染为可读文本，LLM无需解析JSON |
| **裁剪安全** | ReAct循环只裁剪data，llm_data完整保留，LLM始终能看摘要和状态 |

---

**文档更新时间**: 2026-06-22 19:00:00  
**版本**: v7.1  
**编写人**: 小健 + 北京老陈 + 小欧  
**更新内容**: 
- v7.0: 删除冗余字段，符合DRY原则
- v7.1: 补充5.10.3数据流图和数据存储规则表的other_data字段、修复9.3.3节SSE格式代码
- v6.8: 补充Phase 2审查缺口：①5.10.4澄清Observation step复用ToolStep（非独立模型）；②5.10.7补充DB迁移步骤；③新增9.3节Phase 2实施清单（5步）
- v6.9: 修复Phase 2 4个设计错误
- v7.0: 拆分Phase 2/3：action_tool模式execution_result瘦身+DB存储优化移到Phase 3，Phase 2只改observation模式
