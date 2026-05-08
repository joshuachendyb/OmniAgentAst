# Time类型Prompt参数命名问题分析

**创建时间**: 2026-05-07 19:55:01  
**创建人**: 小沈  
**问题现象**: LLM调用time工具时传错参数名，导致`unexpected keyword argument`错误

---

## 一、问题现象

### 1.1 典型错误案例

| 工具 | LLM传的参数 | 正确参数名 | 错误信息 |
|------|-----------|----------|---------|
| `time_format` | `{"date":"2026-06-19"}` | `timestamp`, `pattern` | `got an unexpected keyword argument 'date'` |
| `time_is_weekend` | `{"path":"//www.baidu.com/..."}` | `date` | `got an unexpected keyword argument 'path'` |

### 1.2 参数校验结果

```python
# Schema定义（正确）
time_format: properties = ['timestamp', 'pattern']
time_is_weekend: properties = ['date']

# 函数签名（正确）
time_format(timestamp: Optional[Any] = None, pattern: Optional[str] = None)
time_is_weekend(date: Optional[Any] = None)

# LLM实际传入（错误）
time_format(date="2026-06-19")           # 参数名错误
time_is_weekend(path="http://...")       # 完全错误（把URL当参数）
```
### 1.3  梳理出整个系统的调用LLM的信息情况

```
┌─ prompt文本 ─┐
│ system_adapter.py   → 段落① 系统信息
│ time_prompts.py     → 段落②⑤⑥ 自然语言说明
│ BasePromptTemplate  → 段落③④⑦⑧ 公共规则
└─────────────────────┘

┌─ tools定义（JSON Schema）──┐
│ time_schema.py  → 参数类型+required数组
│ time_register.py → description+input_schema生成
└────────────────────────────┘

```
所以：

register/schema 不是二级代码，是另一个并行通道
prompt通道：自然语言指导（人可读）
tool通道：结构化定义（机器可解析）
两者都传给LLM，只是形式不同。LLM同时看到：

prompt的自然语言描述（"time_format用于格式化时间..."）
tools的JSON Schema（{"required":["timestamp"], "properties":{...}}）

意图识别阶段（只执行一次）
    ↓
确定意图 = [Time, File]
    ↓
加载 tools = get_tools(Time) + get_tools(File)
    ↓
进入ReAct循环
    轮次1: messages=[sys, task] + tools[42个]  ← 固定
    轮次2: messages=[...] + tools[42个]        ← 同一个
    轮次3: messages=[...] + tools[42个]        ← 同一个
    ...
    轮次N: messages=[...] + tools[42个]        ← 同一个


---

## 二、首次Messages组装分析

### 2.1 组装流程

```python
# base_react.py L401-402
conversation_history = [
    {"role": "system", "content": sys_prompt},   # 系统提示
    {"role": "user", "content": task_prompt}     # 用户任务
]
```

### 2.2 首次给LLM的Messages架构和tools的说明

### 2.2.1 关于message的组装构建分析

**conversation_history由2条独立message组成**：

```
conversation_history = [
    {"role": "system", "content": sys_prompt},   # 第1条：系统提示（5636字符）
    {"role": "user", "content": task_prompt}     # 第2条：任务提示（270字符）
]

prompt文件 vs register/schema 是两个不同通道：

通道1：Prompt文本通道（文档L58-72列的是这个）

给LLM的 system message 自然语言文本：

文件	输出到message的什么
system_adapter.py	段落① 系统信息
time_prompts.py	段落②角色定义+工具描述+示例 ⑤Safety ⑥Parameter Reminder
BasePromptTemplate.py	段落③OUTPUT_FORMAT ④TOOL_CALL_RULES ⑦FINISH_RULE ⑧回滚说明
通道2：Tool定义通道（register + schema）

给LLM的 tools JSON Schema结构化定义：

文件	作用
time_schema.py	Pydantic模型 → 定义参数名+类型+必填/可选
time_register.py	注册工具 → 生成input_schema + 详细description
这两个文件生成的信息不进prompt文本，而是进tools定义传给LLM。
给LLM的信息 = prompt文本 + tools定义



```
conversation_history (首次messages)
├── message[0] {"role": "system"}  → sys_prompt (第1条，内部8个段落)
│   ├── ① 系统信息(298) — system_adapter.py
│   ├── ② 角色定义+工具描述+示例(5636) — time_prompts.py
│   ├── ③ OUTPUT_FORMAT(388) — BasePromptTemplate.py
│   ├── ④ TOOL_CALL_RULES(229) — BasePromptTemplate.py
│   ├── ⑤ Safety提醒(103) — time_prompts.py
│   ├── ⑥ Parameter Reminder(970) — time_prompts.py
│   ├── ⑦ FINISH_RULE(498) — BasePromptTemplate.py
│   └── ⑧ 回滚说明(192) — BasePromptTemplate.py
└── message[1] {"role": "user"}    → task_prompt (第2条，独立)
    ├── （1）Task: xxx — time_prompts.py
    ├── （2）Current time: xxx — time_prompts.py
    └── （3）执行步骤 — time_prompts.py
```
### 2.2.2 关于tool的组装构建分析

**tools定义结构（与messages并行传给LLM）**：

```
tools = [
  {
    "type": "function",
    "function": {
      "name": "timer_set",
      "description": "设置定时器...",      ← time_register.py
      "parameters": {                      ← time_schema.py生成
        "type": "object",
        "properties": {
          "delay": {"type": "number", "description": "延迟秒数...必填参数"},
          "callback": {"type": "string", "description": "回调描述...必填参数"},
          "callback_data": {"type": "object", "default": null, "description": "...可选参数"}
        },
        "required": ["delay", "callback"]   ← 必填参数列表
      }
    }
  },
  ...其他工具
]
```
request_json = {
    "model": self.model,
    "messages": messages      # ← 消息数组
}

if tools:
    request_json["tools"] = tools      # ← 工具定义数组（与messages同级）
    request_json["tool_choice"] = tool_choice


    # 1. 从register获取工具描述
    tool_description = {
        "name": tool_name,
        "description": tool_description,  # 来自register
        "parameters": tool_schema        # 来自schema
    }

    # 2. 组装到tools数组
    tools.append({
        "type": "function",
        "function": tool_description
    })

    # 3. 传给LLM
    request_json = {
        "model": self.model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto"
    }

所以LLM同时看到：

自然语言描述（prompt文本）：
- "time_format用于格式化时间..."
- "参数: timestamp(时间戳), pattern(格式串)"

结构化定义（tools JSON Schema）：
- {"required":["timestamp"], "properties":{"timestamp":{"type":"number"}}}

两者都传给LLM，只是形式不同。LLM同时看到：

注册总数：125个
每次API调用只传当前意图的工具（如Time意图=16个）
如果是多意图，会动态加载多个分类的工具（_loaded_categories机制）。
def _load_tools(self):
    if not self.tool_category:
        return {}
    return get_tools_from_registry_by_category(self.tool_category)  # ← 只加载当前意图


### 2.3 sys_prompt 内部层次（build_full_system_prompt组装，8段落）

**sys_prompt由8个段落组成**：

| 序号 | 段落名称 | 来源 | 内容示例 | 字符数 |
|------|---------|------|---------|--------|
| ① | 系统信息 | get_system_info() | `【当前系统】Windows...` | 298 |
| ② | 角色定义+工具描述+示例 | get_system_prompt() | TIME Tools + Tool Call Examples | 5636 |
| ③ | OUTPUT_FORMAT | BasePrompts常量 | JSON输出格式规则 | 388 |
| ④ | TOOL_CALL_RULES | BasePrompts常量 | 工具调用规则 | 229 |
| ⑤ | Safety提醒 | get_safety_reminder() | `⚠️ Time Safety...` | 103 |
| ⑥ | **Parameter Reminder** | **get_parameter_reminder()** | **参数名+类型+FORBIDDEN** | **970** |
| ⑦ | FINISH_RULE | BasePrompts常量 | 终止规则（防死循环） | 498 |
| ⑧ | 回滚说明 | get_rollback_instructions() | 失败处理建议 | 192 |



```
 ① 段落1 (298字符): get_system_info() → 系统信息+路径格式+命令格式+路径规则
【当前系统】
Windows
【路径格式】
- 当前系统: C:\Users\xxx\file.txt 或 C:/Users/xxx/file.txt
【命令格式】
- list: dir
- copy: copy
- delete: del
- read: type
- create_dir: mkdir
【路径规则】
- 必须使用绝对路径（禁止相对路径如 ./file.txt）
- 禁止用 ~ 表示家目录
- ❌ 路径中的中文字符必须原样保留，禁止翻译或转换！用户说"E:\下载\科幻小说"就用"E:\下载\科幻小说"，禁止改成"E:\download\sci-fi-novel"

② 段落2 (5636字符): get_system_prompt() → 角色定义+工具详细描述+Tool Call Examples
  L19:  【Available TIME Tools】:
  L32:  2. time_format - Format timestamp or date string
  L33:     - Parameters:
  L34:       - timestamp: Unix timestamp (int/float), date string, or datetime
  L35:       - pattern: Format string like "%Y年%m月%d日"
  L37:     - Example: time_format(timestamp=1777103094, pattern="%Y年%m月%d日")
  ...
  L85:  9. time_is_weekend - Check if a date is weekend
  L86:     - Parameters:
  L87:       - date: Date to check. None = today
  L89:     - Example: time_is_weekend(date="2026-04-26")
  ...
  L130: 【Tool Call Examples】:
  L131: Example 1 - 查询当前时间: {"thought":"...", "tool_name":"get_current_time", ...}
  L134: Example 2 - 计算明天的日期: {"thought":"...", "tool_name":"time_add", ...}
  L137: Example 3 - 任务完成: {"tool_name":"finish", "tool_params":{"result":"..."}}

③ 段落3 (388字符): OUTPUT_FORMAT → JSON输出格式规则（对齐解析器）
  - thought: 分析当前状态和下一步决策
  - reasoning: 为什么选这个工具、参数如何确定（必需）
  - tool_name: 要调用的工具名
  - tool_params: 工具参数（无参数时为空对象{}）
  - 禁止使用 [TOOL_CALL] 格式

④ 段落4 (229字符): TOOL_CALL_RULES → 工具调用规则
  - 确认意图后立即调用工具，禁止反复讨论
  - reasoning简短1-2句
  - 禁止在thought中列举多个工具比较而不调用
  - 始终用中文回复用户
  - 工具返回错误时向用户解释并建议替代方案

⑤ 段落5 (103字符): get_safety_reminder() → 安全提醒
  ⚠️ Time Safety: timer_clear only affects timers created in current session.
  Do NOT clear system timers.

⑥ 段落6 (970字符): get_parameter_reminder() → 参数命名提醒+FORBIDDEN
  L145: - time_format: timestamp(optional, int/float/str), pattern(optional, str)  ← 已增强！含类型
  L153: - time_is_weekend: date(optional, str, default=today)                    ← 已增强！含类型+默认值
  L156: FORBIDDEN parameter names - DO NOT use:                                  ← 已新增FORBIDDEN
  L157: - ❌ amount / value (correct: delta)

⑦ 段落7 (498字符): FINISH_RULE → 终止规则（防死循环）
  - 含 tool_name 且 ≠"finish" → type=action（继续循环）
  - 含 tool_name="finish" → type=answer（退出循环）
  - 不含 tool_name → type=implicit（退出循环）
  - 方式1: {"tool_name":"finish", "tool_params":{"result":"..."}}
  - 方式2: {"content":"...", "reasoning":"..."}

⑧ 段落8 (192字符): get_rollback_instructions() → 回滚说明
  1. Analyze why the operation failed
  2. Try an alternative approach
  3. Report the error clearly
```


### 2.4 task_prompt 组成（270字符）

message[1] {"role": "user"}    → task_prompt (第2条，独立)
    ├── （1） Task: xxx
    ├── （2）Current time: xxx
    └── （3）执行步骤

```python
# time_prompts.py L159-166

# （1） Task: xxx
def get_task_prompt(self, task: str) -> str:
    return f"""Task: {task}

# （2）Current time: xxx
Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# （3）执行步骤
Please help me complete this time/date task. Follow these steps:
1. First, analyze what time operation is needed
2. Use the appropriate time tool to accomplish the task
3. Provide a friendly Chinese response with the result
"""
```

**示例（任务="查询今天是星期几"）**：
```
Task: 查询今天是星期几
Current time: 2026-05-07 20:08:47
Please help me complete this time/date task. Follow these steps:
1. First, analyze what time operation is needed
2. Use the appropriate time tool to accomplish the task
3. Provide a friendly Chinese response with the result
```

**作用**：
- 告诉LLM当前具体任务（`Task: xxx`）
- 提供当前时间基准（`Current time: 2026-05-07 20:08:47`）
- 指导执行步骤（分析→调用工具→中文回复）


### 2.5 多轮Conversation演化

**conversation_history随轮次增长**：

```
═══════════════════════════════════════════════════════════
【首次初始化】(2条message)
═══════════════════════════════════════════════════════════
conversation_history = [
    [0] {"role": "system"} → sys_prompt (5636字符)
        ├── ① 系统信息(298)
        ├── ② 角色定义+工具描述+示例(5636)
        ├── ③ OUTPUT_FORMAT(388)
        ├── ④ TOOL_CALL_RULES(229)
        ├── ⑤ Safety提醒(103)
        ├── ⑥ Parameter Reminder(970)
        ├── ⑦ FINISH_RULE(498)
        └── ⑧ 回滚说明(192)
    [1] {"role": "user"} → task_prompt (270字符)
]

═══════════════════════════════════════════════════════════
【第1轮后 - LLM返回thought】(3条message)
═══════════════════════════════════════════════════════════
conversation_history = [
    [0] system → sys_prompt
    [1] user → task_prompt
    [2] assistant → response (thought内容，如"我需要调用get_current_time")
]
# 代码位置: base_react.py L569

═══════════════════════════════════════════════════════════
【第1轮后 - LLM返回action】(4条message)
═══════════════════════════════════════════════════════════
conversation_history = [
    [0] system → sys_prompt
    [1] user → task_prompt
    [2] assistant → response (JSON调用，如{"tool_name":"get_current_time",...})
    [3] user → observation (工具执行结果，如"当前时间: 2026-05-07 20:30:00")
]
# 代码位置: base_react.py L712 + L767

═══════════════════════════════════════════════════════════
【第2轮 - LLM再次思考】(5-6条message)
═══════════════════════════════════════════════════════════
conversation_history = [
    [0] system → sys_prompt
    [1] user → task_prompt
    [2] assistant → response1 (第1次tool调用)
    [3] user → observation1 (第1次工具结果)
    [4] assistant → response2 (第2次thought或action)
    [5] user → observation2 (如果是action，追加工具结果)
]

═══════════════════════════════════════════════════════════
【第N轮 - 历史裁剪】(最多保留15条)
═══════════════════════════════════════════════════════════
当len(conversation_history) > 15时:
  - 保留 [0] system (必须)
  - 保留 [1] user (原始任务，必须)
  - 删除中间低价值对话
  - 保留最近5条 (上下文连续性)
# 代码位置: base_react.py L859-921 _trim_history()
```

**演化规律**：

| 轮次 | message数 | 新增内容 | 代码位置 |
|------|----------|---------|---------|
| 初始 | 2 | system + task_prompt | L401-402 |
| 第1轮thought | 3 | assistant response | L569 |
| 第1轮action | 4 | assistant response + observation | L712 + L767 |
| 第2轮 | 5-6 | 新一轮 assistant + observation | 循环 |
| 第N轮 | ≤15 | 触发_trim_history裁剪 | L859 |

**关键点**：
- system prompt始终保留（L887强制保留[0]）
- 原始task_prompt始终保留（L890强制保留[1]）
- 每轮新增2条：assistant(response) + user(observation)
- 超过15条触发裁剪，保留system + 原始task + 最近5条
    
---

## 三、问题根因分析

### 3.1 详细描述 vs Parameter Reminder 对比

**详细描述（L32-37）**：
```
2. time_format - Format timestamp or date string
   - Parameters:
     - timestamp: Unix timestamp (int/float), date string, or datetime. None = current time
     - pattern: Format string like "%Y年%m月%d日"
   - Example: time_format(timestamp=1777103094, pattern="%Y年%m月%d日")
```

**Parameter Reminder（L136）**：
```
- time_format: timestamp, pattern    ← 只有两个单词！无类型/示例
```

### 3.2 LLM为何传错参数

| 因素 | 说明 | 影响 |
|------|------|------|
| **位置距离** | 详细描述L32-37，Parameter Reminder L136，相隔100行 | LLM调用时记忆模糊 |
| **LLM记忆机制** | 调用时凭"最近记忆"，Parameter Reminder靠后更近 | 简略信息覆盖详细描述 |
| **信息密度** | Parameter Reminder太简略，`timestamp, pattern`只有名字 | 无法区分参数类型 |
| **语义偏差** | `time_format`语义是"格式化时间"，LLM直觉认为有`date`参数 | 语义理解错误 |

### 3.3 两个错误的差异

| 错误 | LLM思考过程 | 根因 |
|------|-----------|------|
| `time_format(date=...)` | "格式化日期应该有date参数" | **语义偏差**：直觉认为时间工具应该叫`date` |
| `time_is_weekend(path=...)` | 把搜索上下文的URL参数带进来 | **上下文污染**：前序对话的参数名干扰 |

---

## 四、三层信息对比

### 4.1 Parameter Reminder（v0.12.19已增强）

```python
# time_prompts.py L142-160
def get_parameter_reminder(self) -> str:
    return (
        "Parameter Reminder:\n"
        "- get_current_time: timezone(optional, str, e.g.\"Asia/Shanghai\"), format(optional, str), locale(optional, str)\n"
        "- time_add: start(optional, str/int, default=now), delta(required, int/float), unit(optional, str, default=\"days\", options: days/hours/minutes/seconds/months)\n"
        "- time_format: timestamp(optional, int/float/str), pattern(optional, str)\n"
        "- time_diff: start(optional, str/int), end(optional, str/int, default=now)\n"
        "- timer_set: delay(required, int, 1~86400), callback(required, str), callback_data(optional)\n"
        "- timer_clear: timer_id(required, str)\n"
        "- time_utc_to_local: utc_time(required, str/int), target_tz(optional, str)\n"
        "- time_local_to_utc: local_time(required, str/int), source_tz(optional, str)\n"
        "- time_is_weekend: date(optional, str, default=today)\n"
        "- time_is_holiday: date(optional, str, default=today)\n"
        "\n"
        "FORBIDDEN parameter names - DO NOT use:\n"
        "- ❌ amount / value (correct: delta)\n"
        "- ❌ unit_type (correct: unit)\n"
        "- ❌ tid / id (correct: timer_id)"
    )
```

### 4.2 Prompt详细描述

```python
# time_prompts.py L32-37
2. time_format - Format timestamp or date string
   - Parameters:
     - timestamp: Unix timestamp (int/float), date string, or datetime. None = current time
     - pattern: Format string like "%Y年%m月%d日". None = "%Y-%m-%d %H:%M:%S"
   - When to use: "格式化时间", "把这个时间转成中文格式", "YYYY年MM月DD日"
   - Example: time_format(timestamp=1777103094, pattern="%Y年%m月%d日")
```

### 4.3 Schema定义

```python
# tool_registry中的input_schema
time_format:
  properties:
    timestamp:
      description: "时间戳（Unix秒）、日期字符串（如'2026-04-25'）、或datetime对象..."
      type: string
    pattern:
      description: "格式字符串（如'%Y-%m-%d %H:%M:%S'）..."
      type: string
```

### 4.4 三层对比结论

| 层次 | 信息量 | 位置 | LLM可见性 |
|------|--------|------|----------|
| Parameter Reminder | ★★★ (参数名+类型+默认值+FORBIDDEN) | prompt尾部 | **高**（调用时记忆清晰） |
| Prompt详细描述 | ★★★ (参数+类型+示例) | prompt中部 | 中（被大量文字淹没） |
| Schema定义 | ★★☆ (参数+类型) | tool_registry | 低（不直接给LLM） |

**已解决**：v0.12.19增强Parameter Reminder后，信息量已与详细描述相当，且位置更优。

---

## 五、改进方案

### 5.1 方案A：增强Parameter Reminder（✅ v0.12.19已实施）

**已实施**：所有8个Prompt类已增强Parameter Reminder，统一包含类型说明+FORBIDDEN段落。

```python
# 当前：
"- time_format: timestamp, pattern\n"
"- time_is_weekend: date\n"

# 改进后：
"- time_format: timestamp(时间戳/日期串如2026-04-25), pattern(格式串如%Y年%m月%d日)\n"
"- time_is_weekend: date(日期串/时间戳，如2026-04-25)\n"
```

**优点**：
- 保持Parameter Reminder简洁性
- 加入类型说明和示例，LLM不会混淆
- 修改量小

### 5.2 方案B：加强制性约束提醒（已融入FORBIDDEN段落）

v0.12.19已在各Parameter Reminder中统一加入FORBIDDEN段落，替代单独的强制性约束提醒。

### 5.3 方案C：执行层兜底（✅已实施）

修改 `tool_executor.py` 的 `_normalize_params`：检测到非法参数后**删除**，防止传给函数崩溃。

```python
# 当前（只WARNING不删除）：
if key not in valid_params:
    logger.warning(...)

# 改进（删除非法参数）：
invalid_keys.append(key)
for key in invalid_keys:
    del params[key]
```

**优点**：防止崩溃  
**缺点**：治标不治本，LLM仍传错参数

---

## 六、time类型的分析总结

### 6.1 问题本质

**Prompt设计问题**：Parameter Reminder过于简略（只有参数名），LLM凭直觉传参数导致错误。

### 6.2 改进优先级

1. **治本**：增强Parameter Reminder（方案A，✅ v0.12.19已实施）
2. **治标**：执行层兜底删除非法参数（方案C，✅ 已实施）
3. **辅助**：FORBIDDEN段落融入Parameter Reminder（方案B，✅ v0.12.19已实施）

### 6.3 适用范围

此问题不仅存在于Time类型，其他工具类型（File/Shell/Network等）的Parameter Reminder同样存在简略问题，需要系统性改进。

---

## 七、File类型对比分析

### 7.1 sys_prompt 对比

| 对比项 | Time类型 | File类型 | 差异 |
|--------|---------|---------|------|
| **总字符数** | 5315 | 6028 | File多713字符 |
| **段落数** | 6个 | 5个 | File少1个段落 |
| **Parameter Reminder** | ✓ 有（详细） | **✓ 有（详细）** | 均已增强 |
| **Tool详细描述** | ~3500字符 | ~4510字符 | File更详细 |
| **Tool Call Examples** | ~500字符 | ~883字符 | File示例更完整 |
| **特殊规则段落** | 无 | write_text_file规则(2792字符) | File专属 |

### 7.2 File sys_prompt 结构（6028字符，5段）

```
═══════════════════════════════════════════════════════════
【File sys_prompt结构】
═══════════════════════════════════════════════════════════
段落1 (300字符):
【当前系统】Windows
【路径格式】...
【命令格式】...
【路径规则】...

段落2 (162字符):
You are a professional file management assistant. You help users organize, 
analyze, and manage files...

段落3 (4510字符):
Available Tools:
1. read_text_file(file_path, head=None, tail=None, offset=None, limit=None, encoding=None)
2. write_text_file(file_path, text, mode='write', encoding='utf-8', backup=True)
3. list_directory(dir_path, include_hidden=False, max_depth=1)
...

段落4 (883字符):
【Tool Call Examples - Follow this format exactly】:
Example 1: List directory
{"thought": "查看D盘根目录文件列表", "tool_name": "list_directory", 
 "tool_params": {"dir_path": "D:/"}}

段落5 (2792字符):
【⚠️ write_text_file text规则 - 极其重要】:
- text参数必须传入实际的文件内容（代码、文本、正文等）
- ❌ 绝对禁止将你的思考/计划/状态确认当作text传入
- ❌ 禁止text="好的，我将..."
- ✅ 正确：text=实际的文件内容字符串
```

### 7.3 task_prompt 对比

| 对比项 | Time类型 | File类型 |
|--------|---------|---------|
| **字符数** | 274 | 452 |
| **Task声明** | `Task: 查询今天是星期几` | `Task: 读取test.txt文件` |
| **Current time** | ✓ 有 | ✓ 有 |
| **执行步骤** | 3步（分析→工具→回复） | 4步（分析→工具→总结→Remember） |
| **特殊提醒** | 无 | Remember: 多工具序列/失败处理/安全追踪 |

**File task_prompt完整示例**：
```
Task: 读取test.txt文件
Current time: 2026-05-08 03:13:36
Please help me complete this file management task. Follow these steps:
1. First, analyze what needs to be done
2. Use the appropriate tools to accomplish the task
3. Provide a summary when finished
Remember:
- You can use multiple tools in sequence
- Each tool call should be well-reasoned
- If an operation fails, explain why and suggest alternatives
- All file operations are tracked for safety
```

### 7.4 关键差异分析

#### 差异1：File已有Parameter Reminder（v0.12.19已补齐）

**Time有**：
```
Parameter Reminder:
- get_current_time: timezone(optional, str, e.g."Asia/Shanghai"), format(optional, str), locale(optional, str)
- time_format: timestamp(optional, int/float/str), pattern(optional, str)
```

**File已有**（v0.12.19补齐，含类型说明和FORBIDDEN）：
```
Parameter Reminder:
- list_directory: dir_path
- read_text_file: file_path
- write_text_file: file_path, text
...
Common mistakes to avoid:
- ❌ directory_path (use: dir_path)
- ❌ filepath (use: file_path)
- ❌ content for write (use: text)
```

#### 差异2：File专属write_text_file规则

**段落5（2792字符）**专门约束`write_text_file`的`text`参数：
```
【⚠️ write_text_file text规则 - 极其重要】:
- text参数必须传入实际的文件内容（代码、文本、正文等）
- ❌ 绝对禁止将你的思考/计划/状态确认当作text传入
- ❌ 禁止text="好的，我将..."
```

**原因**：File操作的`write_text_file`最易出错，LLM经常把思考过程当作文件内容写入。需要强约束。

#### 差异3：File task_prompt更详细

**File的Remember**（178字符）：
```
Remember:
- You can use multiple tools in sequence
- Each tool call should be well-reasoned
- If an operation fails, explain why and suggest alternatives
- All file operations are tracked for safety
```

**Time无Remember**：Time操作相对简单，不需要多工具序列提醒。

### 7.5 多轮Conversation演化（File与Time相同）

File类型的conversation_history演化**完全遵循2.5节描述的模式**：
- 初始2条：system + task_prompt
- 每轮新增2条：assistant(response) + user(observation)
- 超过15条触发裁剪

**差异仅在于sys_prompt和task_prompt的内容**，演化机制统一由`base_react.py`控制。

### 7.6 File类型的参数命名问题

**File有Parameter Reminder吗？** ✓ 有（v0.12.19已有）。

**File的Parameter Reminder质量**：★★★，含类型说明+FORBIDDEN段落。

**File参数命名风险**：中。虽有Parameter Reminder，但工具参数多（6-7个参数），仍有传错风险。

---

## 八、Document类型对比分析

### 8.1 sys_prompt 对比（Document vs Time vs File）

| 对比项 | Time类型 | File类型 | Document类型 |
|--------|---------|---------|-------------|
| **总字符数** | 5315 | 6028 | **1634** |
| **功能段落数** | 6个 | 5个 | **6个** |
| **Parameter Reminder** | ✓ 有（详细） | ✓ 有（详细） | **✓ 有（详细）** |
| **Tool详细描述** | ~3500字符 | ~4510字符 | ~1200字符 |
| **Tool Call Examples** | ~500字符 | ~883字符 | ~900字符 |
| **Safety提醒** | ~100字符 | ~200字符 | ~80字符 |
| **特殊规则段落** | 无 | write_text_file规则(2792字符) | **无** |

### 8.2 Document sys_prompt 结构（1634字符，6个功能段落）

```
═══════════════════════════════════════════════════════════
【Document sys_prompt结构】
═══════════════════════════════════════════════════════════
1段落① (299字符):
【当前系统】Windows
【路径格式】...
【命令格式】...
【路径规则】...

2段落② (~1200字符):
You are a professional document operations assistant. You help users read/write 
PDF, Word, Excel, PPT documents...

Available Tools:
1. read_pdf(file_path) - Read PDF document content
2. read_docx(file_path) - Read Word document content
3. read_xlsx(file_path) - Read Excel file content
4. write_docx(file_path, content) - Create Word document
5. write_xlsx(file_path, data) - Create Excel file
...

3段落③ (~900字符):
【Tool Call Examples】:
Example 1: Read PDF
{"thought": "读取PDF文档", "tool_name": "read_pdf", 
 "tool_params": {"file_path": "D:/report.pdf"}}

Example 2: Create Word document
{"thought": "创建Word文档", "tool_name": "write_docx",
 "tool_params": {"file_path": "D:/report.docx", "content": "文档内容"}}

4段落④ (~80字符):
Safety: 文档操作可能涉及敏感信息，注意权限和隐私

5段落⑤ (~800字符):
Parameter Reminder:
- read_pdf: file_path(required)
- read_docx: file_path(required)
- write_docx: file_path(required), content(required)
- write_xlsx: file_path(required), data(required)
- convert_document: input_path(required), output_format(required)
...

6段落⑥ (~600字符):
TERMINATION RULE: 完成任务后用finish退出
```

### 8.3 task_prompt 对比

| 对比项 | Time类型 | File类型 | Document类型 |
|--------|---------|---------|-------------|
| **字符数** | 274 | 452 | **203** |
| **Task声明** | `Task: 查询今天是星期几` | `Task: 读取test.txt文件` | `Task: 读取report.pdf` |
| **Current time** | ✓ 有 | ✓ 有 | **✗ 无** |
| **执行步骤** | 3步 | 4步+Remember | **3步** |
| **特殊提醒** | 无 | Remember多工具序列 | **无** |

**Document task_prompt完整示例**：
```
Task: 读取report.pdf
Please help me complete this document task. Follow these steps:
1. First, analyze the document operation needed
2. Use the appropriate document tool
3. Provide a summary of the result
```

### 8.4 Document的Parameter Reminder特点

**Document的Parameter Reminder是最完整的**：

```
Parameter Reminder:
- read_pdf: file_path(required)
- read_docx: file_path(required)
- read_xlsx: file_path(required)
- read_pptx: file_path(required)
- write_docx: file_path(required), content(required)
- write_xlsx: file_path(required), data(required)
- write_pdf: file_path(required), content(required)
- write_pptx: file_path(required), content(required)
- convert_document: input_path(required), output_format(required)
- read_csv_dataframe: file_path(required)
- read_excel_dataframe: file_path(required)
- analyze_data: data(required)
- generate_chart: data(required), chart_type(required)
- filter_data: data(required), conditions(required)
```

**对比三种类型的Parameter Reminder质量**：

| 类型 | 参数数量 | 标注required/optional | 带类型说明 | 带FORBIDDEN | 质量等级 |
|------|---------|---------------------|----------|------------|---------|
| **Time** | 10个工具 | ✓ | ✓ | ✓ | ★★★ |
| **File** | 11个工具 | ✗ | ✓ | ✓ | ★★★ |
| **Document** | 13个工具 | ✓ | ✓ | ✓ | ★★☆ |

**v0.12.19后三种类型均已增强**：统一包含类型说明+FORBIDDEN段落。

### 8.5 关键差异分析

#### 差异1：Document最简洁（1634字符）

**原因**：
- Document工具参数简单，多为`file_path`单参数
- 无复杂规则段落（如File的write_text_file规则）
- task_prompt无Current time和Remember

#### 差异2：Document无Current time

**Time/File都有**：
```
Current time: 2026-05-08 03:13:36
```

**Document无**：文档操作不需要时间基准，不需要告知LLM当前时间。

#### 差异3：Document工具统一性强

**Document工具参数模式统一**：
```
read_xxx(file_path)           # 所有读取工具：单参数file_path
write_xxx(file_path, content/data)  # 所有写入工具：file_path + 内容
```

**对比File工具参数复杂度**：
```
read_text_file(file_path, head, tail, offset, limit, encoding)  # 6个参数
edit_text_file(file_path, old_string, new_string, replaceAll)   # 4个参数
search_files(path, pattern, file_pattern, exclude_patterns)     # 4个参数
```

Document工具参数简单统一，LLM不易传错。

### 8.6 多轮Conversation演化（Document与Time/File相同）

Document类型的conversation_history演化**完全遵循2.5节描述的模式**：
- 初始2条：system + task_prompt
- 每轮新增2条：assistant(response) + user(observation)
- 超过15条触发裁剪

**演化机制统一由`base_react.py`控制，所有类型共享同一逻辑**。

### 8.7 Document类型的参数命名问题

**Document有Parameter Reminder吗？** ✓ 有，且标注required。

**Document有参数命名问题吗？** 极少。

**原因**：
1. **工具参数简单**：多为单参数`file_path`，不易混淆
2. **Parameter Reminder完整**：标注required，LLM知道哪些参数必填
3. **工具命名清晰**：`read_pdf`/`write_docx`语义明确，参数名自解释

**但仍可改进**：加入类型说明
```
Parameter Reminder:
- read_pdf: file_path(required, PDF文件路径如D:/report.pdf)
- write_docx: file_path(required, Word路径), content(required, 文档内容)
```

### 8.8 三种类型对比总结

| 维度 | Time | File | Document |
|------|------|------|----------|
| **sys_prompt长度** | 5315 | 6028 | **1634** |
| **task_prompt长度** | 270 | 444 | **195** |
| **Parameter Reminder** | ✓ 有（★★★） | ✓ 有（★★★） | ✓ 有（★★☆） |
| **特殊规则段落** | 无 | 有(2792字符) | 无 |
| **工具参数复杂度** | 中 | 高 | **低** |
| **参数命名风险** | 低 | 中 | **低** |

---

## 九、Shell类型对比分析

### 9.1 sys_prompt 对比（Shell vs Time）

| 对比项 | Time类型 | Shell类型 | 差异 |
|--------|---------|----------|------|
| **总字符数** | 5315 | 3265 | Shell少2050字符 |
| **功能段落数** | 6个 | **6个** | 相同 |
| **Parameter Reminder** | ✓ 有（详细） | **✓ 有（v0.12.19新增）** | 均已有 |
| **Tool详细描述** | ~3500字符 | ~720字符 | Shell更精简 |
| **Tool Call Examples** | ~500字符 | ~1500字符 | Shell示例更多 |
| **Safety提醒** | ~100字符 | ~200字符 | Shell有安全提醒 |

### 9.2 Shell sys_prompt 结构（3265字符，6个功能段落）

```
段落① (299字符):
【当前系统】Windows
【路径格式】...
【命令格式】...
【路径规则】...

段落② (~720字符):
You are a professional shell command execution assistant...
Available Tools:
1. execute_shell_command(command, timeout, working_dir) - Execute shell command
2. get_working_directory() - Get current working directory
3. change_directory(path) - Change working directory
4. check_path_exists(path) - Check if path exists
5. check_command_available(command) - Check if command is available
6. locate_command(command) - Find command location
7. get_shell_output() - Get pending shell output
8. terminate_shell(shell_id) - Terminate running shell

段落③ (~1380字符):
⚠️ Shell Safety:
- 命令注入风险：禁止rm -rf /、format等危险命令
- 网络命令需确认：curl/wget等需用户确认
- 执行超时保护：默认30秒超时
- 工作目录限制：仅允许指定目录操作

段落④ (~1500字符):
【Tool Call Examples】:
Example 1: 执行命令
{"thought": "查看目录", "tool_name": "execute_shell_command", 
 "tool_params": {"command": "dir D:/project"}}

Example 2: 检查命令
{"thought": "检查python是否可用", "tool_name": "check_command_available",
 "tool_params": {"command": "python"}}

段落⑤ (~720字符):
TERMINATION RULE: 完成任务后用finish退出
```

### 9.3 Shell task_prompt（212字符）

```
Task: 测试任务
Please help me execute this shell command task. Follow these steps:
1. First, check if the command is available
2. Execute the command with appropriate timeout
3. Provide a clear summary of the result
```

| 对比项 | Time | Shell |
|--------|------|-------|
| **字符数** | 274 | 212 |
| **Current time** | ✓ 有 | ✗ 无 |
| **执行步骤** | 3步 | 3步（含命令可用性检查） |

### 9.4 关键差异分析

#### 差异1：Shell已有Parameter Reminder（v0.12.19新增）

**v0.12.19新增**：Shell已有完整Parameter Reminder，含类型说明+FORBIDDEN段落：
```
Parameter Reminder:
- execute_shell_command: command(required, str), working_dir(optional, str), timeout(optional, int, default=120), shell_type(optional, str, default=powershell)
- get_working_directory: no params
- change_directory: path(required, str)
...
FORBIDDEN parameter names - DO NOT use:
- ❌ cmd / script / shell_cmd (correct: command)
- ❌ directory / dir / cwd (correct: working_dir or path)
- ❌ id / session / sid (correct: session_id)
```

#### 差异2：Shell安全提醒最详细（~1380字符）

Shell操作安全风险最高（命令注入、危险命令），Safety段落远比其他类型详细：
- 命令注入风险禁止
- 网络命令需确认
- 执行超时保护
- 工作目录限制

#### 差异3：Shell Tool Call Examples最多（~1500字符）

Shell命令语法多样，需要更多示例覆盖不同场景。

### 9.5 Shell类型参数命名风险

| 风险点 | 说明 | 风险等级 |
|--------|------|---------|
| `execute_shell_command` | LLM可能传`cmd`而非`command` | 中 |
| `change_directory` | LLM可能传`dir`而非`path` | 中 |
| `check_path_exists` | LLM可能传`file_path`而非`path` | 低 |

---

## 十、Network类型对比分析

### 10.1 sys_prompt 对比（Network vs Time）

| 对比项 | Time类型 | Network类型 | 差异 |
|--------|---------|------------|------|
| **总字符数** | 5315 | 3197 | Network少2118字符 |
| **功能段落数** | 6个 | **6个** | 相同 |
| **Parameter Reminder** | ✓ 有（详细） | **✓ 有（详细）** | 均已增强 |
| **Tool详细描述** | ~3500字符 | ~700字符 | Network更精简 |
| **Tool Call Examples** | ~500字符 | ~1400字符 | Network示例更多 |
| **Safety提醒** | ~100字符 | ~200字符 | 相当 |

### 10.2 Network sys_prompt 结构（3197字符，6个功能段落）

```
段落① (299字符):
【当前系统】Windows
【路径格式】...
【命令格式】...
【路径规则】...

段落② (~700字符):
You are a professional network operations assistant...
Available Tools:
1. http_request(url, method, headers, body, timeout) - Send HTTP request
2. download_file(url, save_path, timeout) - Download file
3. fetch_webpage(url, format) - Fetch webpage content
4. search_web(query, max_results) - Search the web
5. ping(host, count, timeout) - Ping test
6. port_check(host, port, timeout) - Check port

段落③ (~700字符):
⚠️ Network Safety:
- HTTP请求需注意安全：禁止访问内网地址
- 下载文件需确认路径
- 搜索引擎降级机制：DuckDuckGo优先，失败降级Bing

段落④ (~1400字符):
【Tool Call Examples】:
Example 1: HTTP GET请求
{"thought": "调用API", "tool_name": "http_request",
 "tool_params": {"url": "https://api.example.com/data", "method": "GET"}}

Example 2: 搜索网络
{"thought": "搜索信息", "tool_name": "search_web",
 "tool_params": {"query": "Python教程", "max_results": 5}}

Example 3: Ping测试
{"thought": "测试连通性", "tool_name": "ping",
 "tool_params": {"host": "8.8.8.8", "count": 4}}

段落⑤ (~510字符):
Parameter Reminder:
- http_request: url(required), method(optional,default=GET), headers(optional), 
  body(optional), timeout(optional,default=30)
- download_file: url(required), save_path(required), timeout(optional,default=300)
- fetch_webpage: url(required), format(optional,default=text)
- search_web: query(required), max_results(optional,default=10)
- ping: host(required), count(optional,default=4), timeout(optional,default=5)
- port_check: host(required), port(required), timeout(optional,default=3)

段落⑥ (~700字符):
TERMINATION RULE: 完成任务后用finish退出
```

### 10.3 Network task_prompt（563字符，v0.12.19已增强）

```
Task: 测试任务
Please help me complete this network task. Follow these steps:
1. First, identify the network operation needed (HTTP request, download, search, connectivity test)
2. Use the appropriate network tool with correct URL/parameters
3. Handle errors gracefully (timeout, connection refused, DNS failure) and suggest alternatives
Remember:
- URL must include scheme (http:// or https://)
- For POST/PUT, use body parameter (NOT data/params)
- Use timeout for operations that may hang
- If DuckDuckGo search fails, try alternative keywords or simpler queries
```

| 对比项 | Time | Shell | Network |
|--------|------|-------|---------|
| **字符数** | 270 | 212 | **563** |
| **Current time** | ✓ 有 | ✗ 无 | ✗ 无 |
| **执行步骤** | 3步详细 | 3步详细 | **3步详细+Remember** |

**v0.12.19已增强**：Network task_prompt从88字符泛化1步→563字符3步详细指导+Remember。

### 10.4 关键差异分析

#### 差异1：Network Parameter Reminder已增强（v0.12.19）

**v0.12.19增强后**：Network Parameter Reminder新增类型说明+FORBIDDEN段落。

**对比5种类型Parameter Reminder质量**：

| 类型 | 标注required/optional | 带默认值 | 带类型说明 | 带FORBIDDEN | 质量等级 |
|------|---------------------|---------|----------|------------|---------|
| Time | ✓ | ✓ | ✓ | ✓ | ★★★ |
| File | ✗ | ✗ | ✓ | ✓ | ★★★ |
| Document | ✓ | ✗ | ✓ | ✓ | ★★☆ |
| Shell | ✓ | ✓ | ✓ | ✓ | ★★★ |
| **Network** | ✓ | ✓ | ✓ | ✓ | ★★★ |

**v0.12.19后5种类型均达到★★★**（File除外因无required/optional标注）。

#### 差异2：Network task_prompt已增强（v0.12.19）

**对比**：
```
Time (270字符):   3步详细 + Current time
Shell (212字符):  3步详细（含命令检查）
Network (563字符): 3步详细+Remember（v0.12.19已增强）
```

**已解决**：v0.12.19已将Network task_prompt从88字符增强为563字符3步详细指导+Remember。

#### 差异3：search_web双引擎降级

Network的Safety段落包含搜索引擎降级机制说明（DuckDuckGo→Bing），这是5月7日新增的修复，其他类型无此特性。

### 10.5 Network类型参数命名风险

| 风险点 | 说明 | 风险等级 |
|--------|------|---------|
| `http_request` | LLM可能传`url`为相对路径 | 低（Parameter Reminder有required标注） |
| `download_file` | LLM可能传`destination_path`而非`save_path` | **中**（参数名与其他工具不一致） |
| `search_web` | LLM可能传`num_results`而非`max_results` | **中**（语义相似但名称不同） |

---

## 十一、5种类型综合对比总结

### 11.1 sys_prompt对比

| 维度 | Time | File | Document | Shell | Network |
|------|------|------|----------|-------|---------|
| **字符数** | 5315 | 6028 | 1634 | 3265 | 3197 |
| **功能段落数** | 6 | 5 | 6 | 5 | 6 |

### 11.2 task_prompt对比

| 维度 | Time | File | Document | Shell | Network |
|------|------|------|----------|-------|---------|
| **字符数** | 270 | 444 | 195 | 212 | 563 |
| **Current time** | ✓ | ✓ | ✗ | ✗ | ✗ |
| **步骤指导** | 3步详细 | 4步+Remember | 3步 | 3步 | 3步详细+Remember |

### 11.3 Parameter Reminder质量对比

| 维度 | Time | File | Document | Shell | Network |
|------|------|------|----------|-------|---------|
| **存在** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **标注required** | ✓ | ✗ | ✓ | ✓ | ✓ |
| **标注optional** | ✓ | ✗ | ✗ | ✓ | ✓ |
| **带默认值** | ✓ | ✗ | ✗ | ✓ | ✓ |
| **带类型说明** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **带FORBIDDEN** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **质量等级** | ★★★ | ★★★ | ★★☆ | ★★★ | ★★★ |
