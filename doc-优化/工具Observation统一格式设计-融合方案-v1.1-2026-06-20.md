# 工具 Observation 统一输出格式设计（融合方案）

**创建时间**: 2026-06-20 11:07:25  
**更新时间**: 2026-06-20 12:15:00  
**版本**: v1.2  
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

- data保持dict（前端需要结构化数据）
- 格式化逻辑留在observation_formatter.py（SRP）
- 工具侧只管提供结构化data和llm_data
- 不改功能逻辑，只改输出格式
- 渐进式改造，不求一步到位

---

## 三、核心设计：三层分离

### 3.1 三个层次的职责

| 层次 | 来源 | 职责 | LLM怎么用 | 前端怎么用 |
|------|------|------|----------|-----------|
| **观察** | formatter生成 | 状态+操作名 | 扫一眼知道发生了什么 | 状态指示器 |
| **结果** | llm_data字段 | 自然语言摘要+结构化关键信息 | 快速理解结果概况 | 渲染摘要卡片（summary做标题，其余做标签） |
| **详情** | data.result字段 | 业务结果数据 | 需要精确数据时引用 | 可折叠详情面板 |

### 3.2 关键设计：llm_data重新定位

**旧llm_data**：给LLM的额外精简数据，前端不用，与data重复

**新llm_data**：LLM和前端共享的摘要层，包含自然语言+结构化关键信息

```python
llm_data = {
    "summary": str,     # 必填：自然语言摘要（"读取 C:\test.py，156行，2380字节"）
    "action": str,      # 必填：操作类型
    "target": str,      # 必填：操作目标
    # 以下按工具类型不同，放关键数字
    "lines": int,       # 可选：行数
    "bytes": int,       # 可选：字节数
    ...
}
```

**前端渲染效果**：

```
┌─────────────────────────────────────────┐
│ 📄 读取 C:\test.py                      │  ← summary
│ 读取 | 156行 | 2380字节 | UTF-8          │  ← 结构化标签
│ [展开详情 ▼]                             │  ← 可折叠data
└─────────────────────────────────────────┘
```

**前端控制**：
- 摘要模式：只显示llm_data（summary + 关键标签）
- 详情模式：展开显示data（完整结构化数据）
- 小屏/移动端：只显示summary

### 3.3 observation输出格式

**核心原则：每层只说自己的事，不重复**

| 层 | 来源 | 输出内容 | 不重复 |
|---|------|---------|--------|
| 观察 | formatter | 状态+action | — |
| 结果 | llm_data | summary | 不重复action（观察已有） |
| 详情 | data.result | 业务数据 | 不重复action/target（观察+结果已有） |

**成功**：
```
观察: success - {llm_data.action}
结果: {llm_data.summary}
详情: {json.dumps(data.result)}
```

**错误**：
```
观察: error [{code}] - {message}
结果: {llm_data.summary}
详情: {json.dumps(data)}  ← error时data没有result，直接输出整个data
建议: {hint}
```

**警告**：
```
观察: warning [{code}] - {message}
⚠ 警告: {warning}
结果: {llm_data.summary}
详情: {json.dumps(data.result)}
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
观察: success - read_file
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情: {"content":"def hello():\n    ...","lines":156,"bytes":2380,"encoding":"utf-8","format":"text"}
```

**LLM的认知路径**：
1. 第一行：成功读取了文件
2. 第二行：156行，2380字节，UTF-8编码 — 关键信息直接可见
3. 第三行：需要具体内容时看详情 — 结构化，精确引用

---

## 四、data统一格式规范

### 4.1 核心规范：data必须是dict，三必填

```python
data = {
    "action": str,      # 必填：操作类型（动词），如 "read"/"write"/"delete"/"search"/"execute"
    "target": str,      # 必填：操作目标（路径/URL/查询词/命令），如 "D:/test.txt"
    "result": Any,      # 必填：操作结果数据（dict/list/int/str/None）
}
```

**为什么是这3个字段？**

| 字段 | LLM需要 | 前端需要 | 说明 |
|------|---------|---------|------|
| `action` | 知道做了什么 | 渲染操作类型 | 消除歧义：同工具可能做不同操作 |
| `target` | 知道操作对象 | 渲染目标路径/URL | 最核心的上下文信息 |
| `result` | 拿到结果数据 | 渲染详细结果 | 业务数据，按工具类型不同 |

### 4.2 各操作类型的result格式

#### 4.2.1 read类（读取）

```python
result = {
    "content": str|list|dict,  # 读取到的内容
    "lines": int,               # 行数（文本类）或条数（列表类）
    "bytes": int,               # 字节数（文件大小）
    "format": str,              # 内容格式（text/json/table/binary）
}
```

**示例**：
- read_text_file: `{"content": "def hello():...", "lines": 156, "bytes": 2380, "format": "text"}`
- read_xlsx: `{"content": {"headers": [...], "rows": [...]}, "lines": 50, "bytes": 4096, "format": "table"}`
- read_pdf: `{"content": "PDF文本内容...", "lines": 5, "bytes": 12000, "format": "text"}`  （lines=页数）

#### 4.2.2 write类（写入）

```python
result = {
    "bytes_written": int,      # 写入字节数（文件类）
    "content_summary": str,    # 内容摘要（如"3段落/1024字"）
}
```

**示例**：
- write_text_file: `{"bytes_written": 1024, "content_summary": "50行/1024字节"}`
- write_docx: `{"bytes_written": 2048, "content_summary": "3段落/500字"}`
- write_xlsx: `{"bytes_written": 512, "content_summary": "10行×5列"}`

#### 4.2.3 search类（搜索）

```python
result = {
    "items": list,             # 搜索结果列表
    "total": int,              # 总结果数
    "truncated": bool,         # 是否截断
}
```

#### 4.2.4 execute类（执行）

```python
result = {
    "exit_code": int,          # 退出码
    "output": str,             # 输出内容
    "error_output": str,       # 错误输出
}
```

#### 4.2.5 delete类（删除）

```python
result = {
    "deleted": bool,           # 是否实际删除（幂等时可能为False）
    "mode": str,               # 删除模式（recycle/permanent）
}
```

### 4.3 data.result与llm_data的字段一致性原则

**核心原则：llm_data的关键数字字段 = data.result中对应字段的子集**

两者描述同一件事，字段名必须一致。llm_data是摘要（挑关键字段），data.result是详情（完整字段）。

```python
# data.result（详情）
data = {"action":"read","target":"C:\\test.py","result":{"content":"...","lines":156,"bytes":2380,"encoding":"utf-8","format":"text"}}

# llm_data（摘要）—— 从result中挑关键字段
llm_data = {"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":"read","target":"C:\\test.py","lines":156,"bytes":2380,"encoding":"utf-8"}
```

**禁止**：llm_data和data.result用不同的字段名描述同一信息（如llm_data用"行数"，result用"lines"）。

### 4.4 error时的data格式

error时data也必须包含action和target，让LLM知道"哪个操作的什么目标失败了"：

```python
data = {
    "action": str,             # 必填：操作类型
    "target": str,             # 必填：操作目标
    "error_detail": str,       # 必填：错误详情（比message更具体）
    "params": dict,            # 可选：导致错误的参数（LLM可据此修正）
}
```

**示例**：

```python
# 当前（信息不足）
build_error(ERR_FILE_NOT_FOUND, "文件不存在", data={"file_path": "D:/test.txt"})

# 规范后（LLM可理解+可修正）
build_error(ERR_FILE_NOT_FOUND, "文件不存在", data={
    "action": "read",
    "target": "D:/test.txt",
    "error_detail": "文件路径不存在",
    "params": {"file_path": "D:/test.txt", "encoding": "utf-8"}
})
```

---

## 五、llm_data统一格式规范

### 5.1 llm_data新定位

**llm_data = LLM和前端共享的摘要层**

不再是"给LLM的额外数据"，而是：
- LLM通过"结果"行消费
- 前端渲染摘要卡片
- 包含自然语言摘要 + 结构化关键信息

### 5.2 llm_data必填字段

```python
llm_data = {
    "summary": str,     # 必填：自然语言摘要，格式为"操作+对象+数字"
    "action": str,      # 必填：操作类型（与data.action一致）
    "target": str,      # 必填：操作目标（与data.target一致）
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

按工具类型放关键数字，前端渲染为标签：

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
│ 读取 | 156行 | 2380字节 | UTF-8               │  ← 结构化标签
│                                    [展开详情▼] │  ← 可折叠data
└──────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────┐
│ 🔍 搜索到8条结果(Parallel引擎)                │  ← summary
│ 搜索 | 8条结果 | Parallel引擎                  │  ← 结构化标签
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
    data={"action":"read","target":"C:\\test.py","result":{"content":"def hello():\n    ...","lines":156,"bytes":2380,"encoding":"utf-8"}},
    message="读取文件成功",
    llm_data={"summary":"读取 C:\\test.py，156行，2380字节，UTF-8编码","action":"read","target":"C:\\test.py","lines":156,"bytes":2380,"encoding":"utf-8"},
)
```
```
观察: success - read_file
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情: {"content":"def hello():\n    ...","lines":156,"bytes":2380,"encoding":"utf-8"}
```

**write_text_file 成功**：
```python
build_success(
    data={"action":"write","target":"C:\\output.txt","result":{"bytes_written":1024,"content_summary":"50行/1024字节"}},
    message="写入文件成功",
    llm_data={"summary":"写入 C:\\output.txt，50行/1024字节","action":"write","target":"C:\\output.txt","bytes_written":1024},
)
```
```
观察: success - write_file             ------->llmdata.action
结果: 写入 C:\output.txt，50行/1024字节  ----->llmdata.summary
详情: {"bytes_written":1024,"content_summary":"50行/1024字节"}
```

**list_directory 成功**：
```
观察: success - list_directory
结果: 列出 C:\project\，156个文件/目录
详情: {"entries":["src/","README.md",...],"total":156,"truncated":false}
```

**copy_file 成功**：
```
观察: success - copy_file
结果: 复制 C:\a.txt → C:\b.txt，1024字节
详情: {"bytes_written":1024}
```

**delete_file 成功**：
```
观察: success - delete_file
结果: 删除 C:\temp.log，已永久删除
详情: {"deleted":true,"mode":"permanent"}
```

**delete_file 幂等（文件不存在）**：
```
观察: success - delete_file
结果: 删除 C:\temp.log，文件已不存在(幂等)
详情: {"deleted":false,"mode":"already_gone"}
```

### 6.2 数据库工具

**query_sql 成功**：
```
观察: success - query_sql
结果: 查询返回5行，列: id, name, email
详情: {"columns":["id","name","email"],"rows":[[1,"Alice","a@t.com"],...],"row_count":5}
```

**execute_sql 成功**：
```
观察: success - execute_sql
结果: SQL执行成功，影响5行
详情: {"affected_rows":5}
```

**get_db_schema 成功**：
```
观察: success - get_db_schema
结果: 获取到3个表的结构: users, orders, products
详情: {"tables":["users","orders","products"],"total":3}
```

### 6.3 文档工具

**read_pdf 成功**：
```
观察: success - read_pdf
结果: 读取 C:\report.pdf，5页，12000字符
详情: {"content":"PDF文本...","lines":5,"bytes":12000,"format":"text"}
```

**write_docx 成功**：
```
观察: success - write_docx
结果: 写入 C:\report.docx，3段落/500字
详情: {"bytes_written":2048,"content_summary":"3段落/500字"}
```

**write_xlsx 成功**：
```
观察: success - write_xlsx
结果: 写入 C:\data.xlsx，10行×5列
详情: {"bytes_written":512,"content_summary":"10行×5列"}
```

### 6.4 网络工具

**search_web 成功**：
```
观察: success - search_web
结果: 搜索到8条结果(Parallel引擎)
详情: {"items":[...],"total":8,"truncated":false}
```

**http_request 成功**：
```
观察: success - http_request
结果: HTTP GET https://api.example.com，状态码200，响应体15000字符
详情: {"status_code":200,"body":"...","content_type":"application/json"}
```

**download_file 成功**：
```
观察: success - download_file
结果: 下载完成，102400字节，保存到 C:\download\file.zip
详情: {"file_path":"C:\\download\\file.zip","bytes_written":102400}
```

### 6.5 Shell工具

**execute_shell_command 成功**：
```
观察: success - execute_shell
结果: 命令执行成功，退出码0
详情: {"exit_code":0,"output":"Handles  NPM(K)...","error_output":""}
```

### 6.6 系统工具

**get_system_info 成功**：
```
观察: success - get_system_info
结果: 获取系统信息，CPU 12核/内存 16GB(已用50%)/磁盘 C: 500GB(已用60%)
详情: {"cpu":{"cores":12,"usage":"45%"},"memory":{"total_gb":16,"used_pct":50},"disk":{"C:":{"total_gb":500,"used_pct":60}}}
```

**event_log 成功**：
```
观察: success - event_log
结果: 获取事件日志(Application)，10条记录
详情: {"events":[...],"total":10,"level":"Error"}
```

### 6.7 桌面工具

**mouse_click 成功**：
```
观察: success - mouse_click
结果: 点击屏幕(500,300)，左键单击
详情: {"x":500,"y":300,"button":"left","click_type":"single"}
```

**screen_capture 成功**：
```
观察: success - screen_capture
结果: 截图保存到 C:\capture.png，1920×1080
详情: {"file_path":"C:\\capture.png","width":1920,"height":1080}
```

### 6.8 注册表工具

**registry_read 成功**：
```
观察: success - registry_read
结果: 读取 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)
详情: {"value_name":"LastLogin","value":"2026-06-20","value_type":"REG_SZ"}
```

**registry_write 成功**：
```
观察: success - registry_write
结果: 写入 HKCU\Software\MyApp\LastLogin = "2026-06-20"(REG_SZ)，旧值="2026-06-19"
详情: {"value_name":"LastLogin","new_value":"2026-06-20","old_value":"2026-06-19","value_type":"REG_SZ"}
```

### 6.9 定时器工具

**timer_set 成功**：
```
观察: success - timer_set
结果: 定时器设置成功，30秒后触发
详情: {"delay_seconds":30,"trigger_time":"2026-06-20 10:51:00"}
```

---

## 七、错误格式规范

### 7.1 错误data四必填

```python
data = {
    "action": str,          # 必填：操作类型
    "target": str,          # 必填：操作目标
    "error_detail": str,    # 必填：错误详情
    "params": dict,         # 可选：导致错误的参数
}
```

### 7.2 错误llm_data

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
    data={"action":"read","target":"C:\\notexist.txt","error_detail":"文件路径不存在","params":{"file_path":"C:\\notexist.txt"}},
    llm_data={"summary":"文件 C:\\notexist.txt 不存在","action":"read","target":"C:\\notexist.txt"},
)
```
```
观察: error [ERR_FILE_NOT_FOUND] - 文件不存在
结果: 文件 C:\notexist.txt 不存在
详情: {"action":"read","target":"C:\\notexist.txt","error_detail":"文件路径不存在","params":{"file_path":"C:\\notexist.txt"}}
建议: 请检查路径是否正确
```

**SQL执行失败**：
```
观察: error [ERR_SQL_EXEC] - SQL执行错误
结果: SQL执行失败: near "SELCT": syntax error
详情: {"action":"query","target":"SELCT * FROM users","error_detail":"near SELCT: syntax error","params":{"sql":"SELCT * FROM users","connection_type":"sqlite"}}
建议: 请检查SQL语法
```

**依赖库未安装**：
```
观察: error [ERR_NO_PYAUTOGUI] - 依赖库未安装
结果: 需要安装 pyautogui 库
详情: {"action":"execute","target":"desktop_automation","error_detail":"pyautogui库未安装","params":{"library":"pyautogui","install_command":"pip install pyautogui"}}
建议: 请先执行安装命令
```

**HTTP请求超时**：
```
观察: error [ERR_TIMEOUT] - 请求超时
结果: 请求 https://slow-api.com 超时，30秒未响应
详情: {"action":"request","target":"https://slow-api.com","error_detail":"连接超时，30秒未响应","params":{"url":"https://slow-api.com","timeout":30}}
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
        # 成功：观察 + 结果 + 详情（只输出data.result）
        action = data.get("action", tool_name) if isinstance(data, dict) else tool_name
        text = f"观察: success - {action}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        elif message:
            text += f"\n结果: {message}"
        if isinstance(data, dict) and "result" in data:
            detail = data["result"]
            safe_detail = _prevent_json_oom(detail, LLM_SAFE_LIMIT) if isinstance(detail, (dict, list)) else detail
            text += f"\n详情: {json.dumps(safe_detail, ensure_ascii=False)}"
        elif data is not None:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            text += f"\n详情: {json.dumps(safe_data, ensure_ascii=False)}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        return text

    elif isinstance(code, str) and code.startswith("WARNING_"):
        # 警告：详情只输出data.result
        action = data.get("action", tool_name) if isinstance(data, dict) else tool_name
        text = f"观察: warning [{code}] - {message}"
        if result.get("warning"):
            text += f"\n⚠ 警告: {result['warning']}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if isinstance(data, dict) and "result" in data:
            detail = data["result"]
            safe_detail = _prevent_json_oom(detail, LLM_SAFE_LIMIT) if isinstance(detail, (dict, list)) else detail
            text += f"\n详情: {json.dumps(safe_detail, ensure_ascii=False)}"
        elif data is not None:
            safe_data = _prevent_json_oom(data, LLM_SAFE_LIMIT) if isinstance(data, (dict, list)) else data
            text += f"\n详情: {json.dumps(safe_data, ensure_ascii=False)}"
        hint = _get_failure_hint(tool_name, tool_params, result)
        if hint:
            text += f"\n建议: {hint}"
        return text

    else:
        # 错误：详情输出整个data（error时data没有result结构）
        text = f"观察: error [{code}] - {message}"
        if llm_data and isinstance(llm_data, dict) and llm_data.get("summary"):
            text += f"\n结果: {llm_data['summary']}"
        if data is not None:
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
    # + 按工具类型的关键数字字段
}
```

### 9.4 Phase 3核心改动

统一error时data格式，每个build_error调用补齐action/target/error_detail/params，同时补齐llm_data。

---

## 十、规范速查

### 10.1 data三必填

```python
data = {
    "action": str,    # 操作类型
    "target": str,    # 操作目标
    "result": Any,    # 结果数据
}
```

### 10.2 llm_data三必填

```python
llm_data = {
    "summary": str,   # 自然语言摘要（"操作+对象+数字"）
    "action": str,    # 操作类型
    "target": str,    # 操作目标
}
```

### 10.3 error四必填

```python
data = {
    "action": str,          # 操作类型
    "target": str,          # 操作目标
    "error_detail": str,    # 错误详情
    "params": dict,         # 导致错误的参数
}
```

### 10.4 禁止

| 禁止 | 说明 |
|------|------|
| data=None | 必须传dict |
| data=str | 必须传dict |
| data无action/target | 必填字段 |
| error时data只有error | 必须有action/target/error_detail |
| llm_data=None | 所有工具必须有llm_data |
| llm_data无summary | summary必填 |
| message="执行成功" | message回归纯描述，摘要由llm_data.summary承担 |

---

## 十一、设计优势总结

| 优势 | 说明 |
|------|------|
| **每看全懂** | 结果行自然语言摘要，LLM扫一眼就懂 |
| **格式统一** | 所有data都是action/target/result，所有llm_data都是summary/action/target |
| **信息完整** | llm_data有摘要，data有详情，error有修正上下文 |
| **LLM和前端一视同仁** | llm_data是共享摘要层，前端渲染卡片，LLM看结果行 |
| **前端可控** | 摘要模式只显示llm_data，详情模式展开data |
| **维护简单** | llm_data和data职责清晰不重叠，llm_data是摘要，data是详情 |

---

**文档更新时间**: 2026-06-20 12:15:00  
**版本**: v1.2  
**编写人**: 小健 + 北京老陈