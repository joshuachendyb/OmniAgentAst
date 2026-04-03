# OMNI-LLM 的 Prompt 组建流程及记录的方法设计

**创建时间**: 2026-03-24 19:00:00
**作者**: 小沈
**版本**: v1.1

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-24 19:00:00 | 小沈 | 初始版本：Prompt 完整流程分析 |
| v1.1 | 2026-03-24 19:30:00 | 小沈 | 补充：PromptLogger 设计说明、日志格式规范、日志记录位置 |

---

## 一、设计背景

### 1.1 问题

在调试和优化 LLM 应用时，我们经常遇到以下问题：

1. **不知道最终发给 LLM 的 Prompt 是什么**
   - Prompt 由多个部分组成（系统 Prompt、任务 Prompt、中间层注入）
   - 每次调用都可能不同
   - 无法直观看到最终的 Prompt 内容

2. **不知道 Prompt 是如何组装的**
   - Prompt 的组装过程分散在多个文件中
   - 中间层注入的 OS 信息可能丢失或不正确
   - 无法追踪 Prompt 的变化过程

3. **不知道每轮 LLM 调用时 Prompt 的变化**
   - ReAct 循环中，每轮 LLM 调用前后的 Prompt 都不同
   - Observation 会添加到消息列表中
   - 无法追踪 Prompt 的累积过程

### 1.2 解决方案

创建 **PromptLogger**，记录每次请求的 Prompt 组装过程，便于调试和分析。

---

## 二、PromptLogger 设计说明

### 2.1 设计目标

1. **记录完整流程**：从用户输入到 LLM 调用的完整 Prompt 变化过程
2. **便于调试**：通过 JSON 文件可以直观查看 Prompt 内容
3. **并发安全**：支持多个请求同时处理，日志不会互相干扰
4. **易于分析**：JSON 格式便于程序解析和人工查看

### 2.2 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    PromptLogger                          │
├─────────────────────────────────────────────────────────┤
│  线程局部存储 (threading.local)                          │
│  ├─ _current_log: 当前请求的日志数据                      │
│  └─ _log_file_path: 日志文件路径                         │
├─────────────────────────────────────────────────────────┤
│  核心方法                                                │
│  ├─ start_request()      开始记录一次请求                 │
│  ├─ log_system_prompt()  记录系统 Prompt                 │
│  ├─ log_task_prompt()    记录任务 Prompt                 │
│  ├─ log_llm_call()       记录 LLM 调用                   │
│  ├─ log_observation()    记录观察结果                     │
│  └─ save()               保存日志到文件                   │
├─────────────────────────────────────────────────────────┤
│  日志文件                                                │
│  └─ backend/logs/prompt-logs/prompt_时间戳_随机ID.json   │
└─────────────────────────────────────────────────────────┘
```

### 2.3 并发安全设计

使用 `threading.local()` 实现线程局部存储，每个线程/请求独立的日志数据。

```python
# 全局实例
_prompt_logger = PromptLogger()

# 每个线程独立的日志数据
self._local = threading.local()

def _get_current_log(self):
    return getattr(self._local, 'current_log', None)

def _set_current_log(self, log_data):
    self._local.current_log = log_data
```

**优势**：
- 每个请求的日志数据完全隔离
- 不会互相覆盖
- 无需加锁，性能好

---

## 三、日志格式规范

### 3.1 日志文件命名

```
prompt_时间戳_随机ID.json
```

**示例**：
```
prompt_20260324_190000_a1b2c3d4.json
```

**组成**：
- `prompt_`：前缀，标识这是 Prompt 日志
- `20260324_190000`：时间戳，精确到秒
- `a1b2c3d4`：UUID 随机 ID，避免文件名冲突

### 3.2 日志文件结构

```json
{
  "基本信息": {
    "时间戳": "2026-03-24 19:00:00",
    "会话ID": "abc123",
    "用户消息ID": "msg_abc123_190000",
    "AI消息ID": "待生成",
    "用户消息": "查看D盘文件",
    "日志文件": "D:\\OmniAgentAs-desk\\backend\\logs\\prompt-logs\\prompt_20260324_190000_a1b2c3d4.json"
  },
  "Prompt组装过程": [
    {
      "步骤": "中间层注入-服务器OS信息",
      "类型": "系统Prompt",
      "来源": "system_adapter.py:generate_system_prompt()",
      "内容": "【当前系统】Windows\n\n【路径格式】\n- Windows: C:\\Users\\xxx\\file.txt...",
      "内容长度": 256,
      "详情": {
        "系统信息长度": 256,
        "包含内容": "服务器OS、路径格式、命令格式"
      },
      "时间戳": "2026-03-24 19:00:01"
    },
    {
      "步骤": "系统Prompt生成",
      "类型": "系统Prompt",
      "来源": "file_prompts.py:get_system_prompt()",
      "内容": "【当前系统】Windows\n\n---\n\nYou are a professional file management assistant...",
      "内容长度": 2048,
      "时间戳": "2026-03-24 19:00:01"
    },
    {
      "步骤": "任务Prompt生成",
      "类型": "任务Prompt",
      "来源": "file_prompts.py:get_task_prompt()",
      "内容": "Task: 查看D盘文件\n\nCurrent time: 2026-03-24 19:00:01\n\nPlease help me...",
      "内容长度": 512,
      "时间戳": "2026-03-24 19:00:01"
    }
  ],
  "LLM调用记录": [
    {
      "轮次": 1,
      "调用类型": "text",
      "模型": "glm-4-flash",
      "提供商": "zhipuai",
      "消息统计": {
        "system": 1,
        "user": 1
      },
      "消息总数": 2,
      "消息摘要": [
        {
          "序号": 1,
          "角色": "system",
          "内容长度": 2048,
          "内容摘要": "【当前系统】Windows\n\n---\n\nYou are a professional file management assistant..."
        },
        {
          "序号": 2,
          "角色": "user",
          "内容长度": 512,
          "内容摘要": "Task: 查看D盘文件\n\nCurrent time: 2026-03-24 19:00:01..."
        }
      ],
      "完整消息列表": [
        {"role": "system", "content": "完整系统 Prompt..."},
        {"role": "user", "content": "完整任务 Prompt..."}
      ],
      "额外参数": {
        "max_steps": 20,
        "use_function_calling": false
      },
      "时间戳": "2026-03-24 19:00:02"
    }
  ]
}
```

### 3.3 字段说明

#### 基本信息

| 字段 | 类型 | 说明 |
|------|------|------|
| 时间戳 | string | 请求开始时间 |
| 会话ID | string | 会话唯一标识 |
| 用户消息ID | string | 用户消息唯一标识 |
| AI消息ID | string | AI 消息唯一标识（初始为"待生成"） |
| 用户消息 | string | 用户输入的原始消息 |
| 日志文件 | string | 日志文件完整路径 |

#### Prompt组装过程

| 字段 | 类型 | 说明 |
|------|------|------|
| 步骤 | string | 步骤名称（如：系统Prompt生成） |
| 类型 | string | Prompt 类型（系统Prompt/任务Prompt/观察结果） |
| 来源 | string | 代码来源（如：file_prompts.py:get_system_prompt()） |
| 内容 | string | Prompt 完整内容 |
| 内容长度 | int | Prompt 内容长度（字符数） |
| 详情 | object | 额外详情（可选） |
| 时间戳 | string | 记录时间 |

#### LLM调用记录

| 字段 | 类型 | 说明 |
|------|------|------|
| 轮次 | int | LLM 调用轮次（从 1 开始） |
| 调用类型 | string | 调用类型（text/tools/response_format） |
| 模型 | string | 使用的模型名称 |
| 提供商 | string | LLM 提供商 |
| 消息统计 | object | 按角色统计的消息数量 |
| 消息总数 | int | 消息总数量 |
| 消息摘要 | array | 每条消息的摘要（角色、长度、前 200 字符） |
| 完整消息列表 | array | 发送给 LLM 的完整消息列表 |
| 额外参数 | object | 额外参数（max_steps 等） |
| 时间戳 | string | 记录时间 |

---

## 四、日志记录的位置

### 4.1 记录节点总览

| 序号 | 节点 | 文件 | 方法 | 记录方法 | 说明 |
|------|------|------|------|---------|------|
| 1 | 系统 Prompt 生成 | `file_prompts.py` | `get_system_prompt()` | `log_system_prompt()` | 记录完整系统 Prompt |
| 2 | 中间层 OS 注入 | `system_adapter.py` | `generate_system_prompt()` | `log_system_prompt()` | 记录 OS 信息 |
| 3 | 任务 Prompt 生成 | `file_prompts.py` | `get_task_prompt()` | `log_task_prompt()` | 记录任务 Prompt |
| 4 | 消息列表组装 | `agent.py` | `conversation_history.append()` | `log_system_prompt()` | 记录组装后的消息列表 |
| 5 | LLM 调用 | `agent.py` | `_get_llm_response()` | `log_llm_call()` | 记录完整消息列表 |

### 4.2 代码位置

#### 4.2.1 系统 Prompt 生成记录

**文件**：`file_prompts.py`
**位置**：第 34-55 行
**代码**：
```python
def get_system_prompt(self) -> str:
    """获取增强版系统Prompt"""
    # 获取系统信息（来自中间层）
    system_info = get_system_info()
    logger.info(f"[FileOperationPrompts] get_system_prompt() 被调用，中间层已注入系统信息，长度: {len(system_info)}")
    
    # ========== Prompt 日志记录 ==========
    from app.utils.prompt_logger import get_prompt_logger
    prompt_logger = get_prompt_logger()
    prompt_logger.log_system_prompt(
        step_name="中间层注入-服务器OS信息",
        prompt_content=system_info,
        source="system_adapter.py:generate_system_prompt()",
        details={
            "系统信息长度": len(system_info),
            "包含内容": "服务器OS、路径格式、命令格式"
        }
    )
```

#### 4.2.2 中间层 OS 注入记录

**文件**：`system_adapter.py`
**位置**：第 117-120 行
**代码**：
```python
def get_system_prompt() -> str:
    """快捷函数：获取系统Prompt字符串"""
    adapter = get_system_adapter()
    logger.info(f"[Prompt中间层] get_system_prompt() 被调用, 服务器OS: {adapter.get_system_name()}")
    return adapter.generate_system_prompt()
```

#### 4.2.3 任务 Prompt 生成记录

**文件**：`agent.py`
**位置**：第 570-573 行
**代码**：
```python
prompt_logger.log_task_prompt(
    task_content=task_prompt,
    context=context
)
```

#### 4.2.4 LLM 调用记录

**文件**：`agent.py`
**位置**：第 199-212 行
**代码**：
```python
# ========== LLM 调用日志记录 ==========
from datetime import datetime
prompt_logger = get_prompt_logger()
prompt_logger.log_llm_call(
    round_number=self.llm_call_count,
    messages=self.conversation_history.copy(),
    model=getattr(self, 'model', 'unknown'),
    provider=getattr(self, 'provider', 'unknown'),
    call_type="text",
    extra_params={
        "max_steps": self.max_steps,
        "use_function_calling": self.use_function_calling
    }
)
```

#### 4.2.5 日志保存

**文件**：`agent.py`
**位置**：第 697-703 行
**代码**：
```python
finally:
    # ========== 保存 Prompt 日志 ==========
    try:
        prompt_logger = get_prompt_logger()
        prompt_logger.save()
    except Exception as e:
        logger.error(f"保存 Prompt 日志失败: {e}")
```

---

## 五、完整流程图

```
用户输入 ("查看D盘文件")
    │
    ├─→ chat2.py:chat_stream()
    │   │   位置: 第468行
    │   │   代码: async for sse_data in agent.ver1_run_stream(...)
    │   │
    │   └─→ agent.py:ver1_run_stream()
    │       │   位置: 第763-800行
    │       │   职责: 封装 run_stream()，转换 SSE 格式
    │       │
    │       └─→ agent.py:run_stream()
    │           │   位置: 第500-695行
    │           │
    │           ├─→ preprocessing/pipeline.py:process()
    │           │   │   位置: 第540-548行
    │           │   ├─→ corrector.py:correct()        拼写纠错
    │           │   └─→ intent_classifier.py:classify()  意图检测
    │           │
    │           ├─→ intent/registry.py:get()          意图识别
    │           │   位置: 第551-555行
    │           │
    │           ├─→ file_prompts.py:get_system_prompt()  构建系统 Prompt
    │           │   │   位置: 第550行
    │           │   │   代码行: 第34-55行
    │           │   │
    │           │   └─→ system_adapter.py:generate_system_prompt()
    │           │       │   代码行: 第76-101行
    │           │       │
    │           │       └─→ 返回: "【当前系统】Windows\n【路径格式】..."
    │           │
    │           ├─→ file_prompts.py:get_task_prompt()    构建任务 Prompt
    │           │   │   位置: 第551行
    │           │   │   代码行: 第188-217行
    │           │   │
    │           │   └─→ 返回: "Task: 查看D盘文件\nCurrent time: ..."
    │           │
    │           ├─→ agent.py:conversation_history.append()
    │           │   位置: 第553-555行
    │           │
    │           │   conversation_history = [
    │           │     {"role": "system", "content": "系统 Prompt"},
    │           │     {"role": "user", "content": "任务 Prompt"}
    │           │   ]
    │           │
    │           ├─→ agent.py:_get_llm_response()
    │           │   │   位置: 第194-267行
    │           │   │
    │           │   └─→ llm_strategies.py:TextStrategy.call()
    │           │       │   位置: 第57-97行
    │           │       │
    │           │       └─→ adapter.py:dict_list_to_messages()
    │           │           │   位置: 第76-123行
    │           │           │
    │           │           └─→ llm_client()  实际 API 调用
    │           │               │
    │           │               └─→ ai_service.chat()
    │           │                   │
    │           │                   └─→ HTTP 请求到 LLM API
    │           │
    │           └─→ 返回 LLM 响应
    │
    └─→ 返回 SSE 流式响应给前端
```

---

## 六、Prompt 变化过程

### 第 1 轮 LLM 调用前

```python
conversation_history = [
    {"role": "system", "content": "【当前系统】Windows..."},
    {"role": "user", "content": "Task: 查看D盘文件..."}
]
```

### 第 1 轮 LLM 调用后

```python
conversation_history = [
    {"role": "system", "content": "【当前系统】Windows..."},
    {"role": "user", "content": "Task: 查看D盘文件..."},
    {"role": "assistant", "content": "{'thought': '...', 'action_tool': 'list_directory', ...}"}
]
```

### 工具执行后（添加 observation）

```python
conversation_history = [
    {"role": "system", "content": "【当前系统】Windows..."},
    {"role": "user", "content": "Task: 查看D盘文件..."},
    {"role": "assistant", "content": "{'thought': '...', 'action_tool': 'list_directory', ...}"},
    {"role": "user", "content": "Observation: success - 列出目录成功"}
]
```

### 第 2 轮 LLM 调用前

```python
conversation_history = [
    {"role": "system", "content": "【当前系统】Windows..."},
    {"role": "user", "content": "Task: 查看D盘文件..."},
    {"role": "assistant", "content": "{'thought': '...', 'action_tool': 'list_directory', ...}"},
    {"role": "user", "content": "Observation: success - 列出目录成功"},
    {"role": "assistant", "content": "{'thought': '...', 'action_tool': 'finish', ...}"}
]
```

---

## 七、关键数据流

### 7.1 系统 Prompt 数据流

```
system_adapter.py:generate_system_prompt()
    ↓
    "【当前系统】Windows\n【路径格式】..."
    ↓
file_prompts.py:get_system_prompt()
    ↓
    system_info + "\n\n---\n\nYou are a professional..."
    ↓
agent.py:run_stream()
    ↓
    sys_prompt (完整系统 Prompt)
    ↓
conversation_history.append({"role": "system", "content": sys_prompt})
```

### 7.2 任务 Prompt 数据流

```
用户输入: "查看D盘文件"
    ↓
file_prompts.py:get_task_prompt(task, context)
    ↓
    "Task: 查看D盘文件\nCurrent time: 2026-03-24 19:00:00..."
    ↓
agent.py:run_stream()
    ↓
    task_prompt (完整任务 Prompt)
    ↓
conversation_history.append({"role": "user", "content": task_prompt})
```

### 7.3 LLM 调用数据流

```
conversation_history (完整消息列表)
    ↓
agent.py:_get_llm_response()
    ↓
llm_strategies.py:TextStrategy.call()
    ↓
adapter.py:dict_list_to_messages()
    ↓
    [Message(role="system", content="..."), Message(role="user", content="...")]
    ↓
llm_client(message, history)
    ↓
ai_service.chat()
    ↓
HTTP 请求到 LLM API
```

---

## 八、使用方法

### 8.1 查看日志

日志文件存放在：`backend/logs/prompt-logs/`

**文件名格式**：`prompt_时间戳_随机ID.json`

**示例**：
```
backend/logs/prompt-logs/
├── prompt_20260324_190000_a1b2c3d4.json
├── prompt_20260324_190005_e5f6g7h8.json
└── prompt_20260324_190010_i9j0k1l2.json
```

### 8.2 分析日志

1. **打开 JSON 文件**：用文本编辑器或 JSON 查看器
2. **查看基本信息**：了解请求的基本信息
3. **查看 Prompt组装过程**：了解 Prompt 是如何组装的
4. **查看 LLM调用记录**：了解每轮 LLM 调用时的消息列表

### 8.3 调试示例

**场景**：LLM 返回了错误的工具调用

**调试步骤**：
1. 找到对应的日志文件
2. 查看 `LLM调用记录` → `完整消息列表`
3. 确认系统 Prompt 是否正确（包含 OS 信息）
4. 确认任务 Prompt 是否正确（包含用户消息）
5. 如果 Prompt 正确，问题可能在 LLM 本身
6. 如果 Prompt 不正确，检查 Prompt 组装过程

---

## 九、总结

### 涉及文件数量
- **总计**: 14 个代码文件

### 关键步骤数量
- **总计**: 8 个步骤

### 日志记录节点
- **总计**: 5 个节点已记录

### 核心调用链
```
chat2.py
  ↓
agent.py:ver1_run_stream()
  ↓
agent.py:run_stream()
  ↓
file_prompts.py → system_adapter.py (构建 Prompt)
  ↓
agent.py:conversation_history.append() (组装消息)
  ↓
agent.py:_get_llm_response() (LLM 调用)
  ↓
llm_strategies.py:TextStrategy.call() (策略调用)
  ↓
llm_client() (实际 API 调用)
```

---

**文档结束**
