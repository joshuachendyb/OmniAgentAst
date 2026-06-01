# Hermes Agent 源码深度研究报告

**创建时间**: 2026-06-01 16:53:36
**存放位置**: G:\OmniAgentAs-desk\notes\
**研究目标**: Hermes Agent (NousResearch) 核心架构 —— Agent/Prompt/Tool/Memory 四大模块
**研究轮次**: 3 轮交叉验证后定稿
**编写人**: 小沈

---

## 1 Agent 模块

### 1.1 总体架构

核心入口类 `AIAgent`（`run_agent.py:294`, 4816 行）本质是一个**薄转发器**。`__init__`（`run_agent.py:317`）将所有参数原封转发给 `agent.agent_init.init_agent()`。关键行为均在 `agent/` 子模块中实现：

| 行为 | 实际实现文件 |
|------|-------------|
| 初始化 + 工具发现 + 系统提示构建 | `agent/agent_init.py` |
| 对话主循环 | `agent/conversation_loop.py`（4707 行） |
| API 调用 + 流式处理 | `agent/chat_completion_helpers.py`（2457 行） |
| 工具执行（顺序/并发） | `agent/tool_executor.py`（1016 行） |
| 运行时工具调用桥接 | `agent/agent_runtime_helpers.py` |
| 系统提示组装 | `agent/system_prompt.py` + `agent/prompt_builder.py` |
| 上下文压缩 | `agent/conversation_compression.py` + `agent/context_compressor.py` |
| 内存管理 | `agent/memory_manager.py` + `agent/memory_provider.py` |
| 工具循环护栏 | `agent/tool_guardrails.py` |

### 1.2 对话循环 flow

入口 `AIAgent.run_conversation()` → `agent.conversation_loop.run_conversation()`（`conversation_loop.py:351`）。

#### 1.2.1 循环条件（`conversation_loop.py:796`）

```python
while (api_call_count < agent.max_iterations and agent.iteration_budget.remaining > 0) or agent._budget_grace_call:
```

两个条件（API 调用次数 + iteration budget）必须同时满足，除非 `_budget_grace_call` 给予一次额外机会。

#### 1.2.2 每次迭代的完整 flow

```
开始迭代
  │
  ├─ 检查中断请求（line 801）
  ├─ 消耗 budget（line 815）
  ├─ 准备 API 消息（line 907–1073）
  │   ├─ 修复 tool_call 参数
  │   ├─ 注入外部记忆预取内容
  │   ├─ 注入系统提示 + 临时提示
  │   ├─ 注入预填信息
  │   ├─ 应用 Anthropic prompt caching
  │   └─ 清理孤立工具结果
  │
  ├─ API 调用尝试（line 1156+）
  │   └─ 内层 retry 循环（指数退避）
  │
  ├─ 解析 LLM 响应
  │
  ├─ 分支 A：有 tool_calls（line 3762–3937）
  │   ├─ 后调用修剪：_cap_delegate_task_calls() + _deduplicate_tool_calls()
  │   ├─ 构建 assistant_message → 追加到 messages
  │   ├─ agent._execute_tool_calls() —— 分派工具执行
  │   │   ├─ _should_parallelize_tool_batch() 决定并发/顺序
  │   │   └─ 每步调用前：guardrails.before_call()
  │   │   └─ 每步调用后：guardrails.after_call()
  │   ├─ 检查 guardrail_halt_decision（line 3842）
  │   └─ 检查 is_compress_needed → 触发上下文压缩
  │
  └─ 分支 B：无 tool_calls（line 3940–4273）
      ├─ 空白响应 → 重试 / 回退前轮次内容 / 思考预填
      └─ 有内容 → 预处理后跳出循环
```

#### 1.2.3 循环退出原因

| 退出原因 | 含义 |
|----------|------|
| `interrupted_by_user` | 用户中断 |
| `budget_exhausted` | iteration budget 耗尽 |
| `guardrail_halt` | 工具循环护栏触发暂停 |
| `text_response(finish_reason=...)` | 正常文本响应 |
| `max_iterations_reached` | 达到 max_iterations |

循环退出后若 `final_response is None`（预算用完但无响应），额外调用一次无工具 API 请求生成摘要（`_handle_max_iterations`, `conversation_loop.py:4332`）。

#### 1.2.4 工具执行 flow 详解

`AIAgent._execute_tool_calls()`（`run_agent.py:4471`）：
1. `_should_parallelize_tool_batch()` 检查工具批是否可并行
2. 读类工具可并行；文件读写需检查路径是否冲突
3. 串行路径 → `agent/tool_executor.execute_tool_calls_sequential()`
4. 并行路径 → `agent/tool_executor.execute_tool_calls_concurrent()`

每个工具调用（`tool_executor.py:110`+）：
1. **`guardrails.before_call()`**：检查是否 blocked（hard_stop 模式）
2. **检查点**：`write_file`/`patch`/`terminal` 前创建文件系统检查点
3. **`agent._invoke_tool()`** → `agent_runtime_helpers.invoke_tool()` → `handle_function_call()`
4. **`guardrails.after_call()`**：记录观察结果，若 warn 追加指导文本

### 1.3 工具循环护栏（`agent/tool_guardrails.py`, 475 行）

**纯副作用自由控制器**，不依赖任何 AIAgent 状态。

#### 1.3.1 检测类型

| 检测类型 | 触发条件 | 默认阈值 |
|---------|---------|---------|
| **精确失败重复** | 相同的 `ToolCallSignature`（tool_name + 规范参数 hash）连续失败 | warn=2, block=5 |
| **同工具失败** | 同一 tool_name 的失败 | warn=3, halt=8 |
| **幂等无进展** | 幂等工具返回相同结果哈希 | warn=2, block=5 |
| **变异工具** | 变异工具不跟踪无进展 | - |

#### 1.3.2 响应级别

| 级别 | 含义 | 行为 |
|------|------|------|
| `allow` | 允许执行 | 无操作 |
| `warn` | 警告（追加到工具结果） | 运行时在工具结果尾部追加 `[Tool loop warning: ...]` |
| `block` | 阻塞执行（返回合成错误） | `before_call` 返回 `action="block"`，合成 `{"error": "Blocked..."}` |
| `halt` | 暂停整个轮次 | `after_call` 设置 `_tool_guardrail_halt_decision`，循环跳出 |

#### 1.3.3 幂等工具名单

`IDEMPOTENT_TOOL_NAMES`（`tool_guardrails.py` 行 17-33）：`read_file`, `search_files`, `web_search`, `web_extract`, `session_search`, `browser_snapshot`, `browser_console`, `browser_get_images` 及 `mcp_filesystem_*` 系列。

`MUTATING_TOOL_NAMES`（行 37-51）：`terminal`, `execute_code`, `write_file`, `patch`, `todo`, `memory`, `skill_manage`, `browser_click`, `browser_type`, `browser_press`, `browser_scroll`, `browser_navigate`, `send_message`, `cronjob`, `delegate_task`, `process`。

---

## 2 Prompt 模块

### 2.1 三层系统提示架构

核心文件：`agent/system_prompt.py`（407 行）+ `agent/prompt_builder.py`（1507 行）。

`build_system_prompt_parts()`（`system_prompt.py:61`）返回字典 `{stable, context, volatile}`，由 `build_system_prompt()` 用 `"\n\n"` 连接。

**关键设计决策**：提示**每个会话只构建一次**，缓存于 `agent._cached_system_prompt`，仅上下文压缩后重建。日期格式（`%A, %B %d, %Y`）而非分钟精度，保持前缀缓存命中。

#### 2.1.1 稳定层（`system_prompt.py:84-280`）

| 组成部分 | 条件门控 |
|---------|---------|
| SOUL.md 身份（优先） | `agent.load_soul_identity` 或 `not agent.skip_context_files` |
| `DEFAULT_AGENT_IDENTITY`（回退） | SOUL.md 未加载 |
| `HERMES_AGENT_HELP_GUIDANCE` | 始终注入 |
| `TASK_COMPLETION_GUIDANCE` | 默认 True + 存在有效工具 |
| memory/session_search/skills 行为指导 | 按 `agent.valid_tool_names` 中存在性门控 |
| Kanban 指导 | `_kanban_worker_guidance` 或 `kanban_show` 在 valid_tool_names |
| `COMPUTER_USE_GUIDANCE` | `computer_use` 工具已加载 |
| nous 订阅提示 | 返回非空时 |
| 工具使用强制（`TOOL_USE_ENFORCEMENT_GUIDANCE`） | 配置模式 auto/true/false/list |
| 模型操作指导（Google/GPT/Grok） | 按模型名称匹配 |
| 技能提示（`build_skills_system_prompt()`） | 存在技能工具 |
| 阿里云模型名适配 | provider == "alibaba" |
| 环境提示 | `build_environment_hints()` 非空 |
| 环境探测（python 工具链） | `agent._environment_probe`（默认 True） |
| 活跃配置文件提示 | 始终注入 |
| 平台提示 | 按 platform 键匹配 `PLATFORM_HINTS` 字典 |

#### 2.1.2 上下文层（`system_prompt.py:282-299`）

| 组成部分 | 条件 |
|---------|------|
| 调用者提供 `system_message` | 不为 None |
| 上下文文件（AGENTS.md/.cursorrules/HERMES.md） | `not agent.skip_context_files` |

注意：`ephemeral_system_prompt` 不在此处——只在 API 调用时注入。

#### 2.1.3 易变层（`system_prompt.py:301-339`）

| 组成部分 | 条件 |
|---------|------|
| 内存快照 `format_for_system_prompt("memory")` | `_memory_store` + `_memory_enabled` |
| USER.md 配置 | `_memory_store` + `_user_profile_enabled` |
| 外部内存提供者块 | `_memory_manager` |
| 时间戳行（仅日期） | 始终；含 timestamp + session_id + model + provider |

### 2.2 提示缓存（`agent/prompt_caching.py`, 79 行）

策略名：**`system_and_3`**（Anthropic 原生）。

- 最多 **4 个 `cache_control` 断点**
- 第 1 个：系统提示消息（`role == "system"`）
- 最多 3 个：最后 3 条非 system 消息
- TTL 可选：`"5m"`（默认）或 `"1h"`
- 输入深拷贝避免污染

### 2.3 DEFAULT_AGENT_IDENTITY（`prompt_builder.py:120-128`）

```python
"You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
"You are helpful, knowledgeable, and direct. You assist users with a wide "
"range of tasks including answering questions, writing and editing code, "
"analyzing information, creative work, and executing actions via your tools. "
"You communicate clearly, admit uncertainty when appropriate, and prioritize "
"being genuinely useful over being verbose unless otherwise directed below. "
"Be targeted and efficient in your exploration and investigations."
```

### 2.4 平台提示（`prompt_builder.py:442-621`）

为每个平台（whatsapp/telegram/discord/slack/signal/email/cron/cli/sms/bluebubbles/mattermost/matrix/feishu/weixin/wecom/qqbot/yuanbao/api_server/webui）定义了专门的平台提示，告诉模型该平台的界面特性（如 Telegram 的 Markdown 支持、Discord 的斜杠命令等）。

---

## 3 Tool 模块

### 3.1 注册系统（`tools/registry.py`, 589 行）

#### 3.1.1 AST 自发现

`discover_builtin_tools()`（`registry.py:48`）：
1. 扫描 `tools/*.py` 所有文件（排除 `__init__`、`registry.py`、`mcp_tool.py`）
2. 对每个文件做 AST 解析，检查模块级的 `registry.register()` 调用
3. 通过 `importlib.import_module()` 导入——模块级调用自动执行注册

#### 3.1.2 ToolEntry 结构

| 字段 | 含义 |
|------|------|
| `name` | 工具名 |
| `toolset` | 所属工具集 |
| `schema` | OpenAI 格式 JSON schema |
| `handler` | 调用函数（`Callable`） |
| `check_fn` | 可用性检测函数 |
| `requires_env` | 需要的环境变量列表 |
| `is_async` | 是否异步 |
| `emoji` | 显示 emoji |
| `max_result_size_chars` | 结果大小上限 |
| `dynamic_schema_overrides` | 运行时动态 schema 覆盖函数 |

#### 3.1.3 注册模式示例

```python
# 文件工具（tools/file_tools.py:1436）— 一行式，共享 check_fn
registry.register(name="read_file", toolset="file", schema=READ_FILE_SCHEMA,
    handler=_handle_read_file, check_fn=_check_file_reqs, emoji="📖",
    max_result_size_chars=100_000)

# Web 工具（tools/web_tools.py:1326）— 多行式，lambda handler，异步
registry.register(
    name="web_search", toolset="web", schema=WEB_SEARCH_SCHEMA,
    handler=lambda args, **kw: web_search_tool(args.get("query", ""), limit=...),
    check_fn=check_web_api_key, requires_env=_web_requires_env(),
    is_async=False, emoji="🔍", max_result_size_chars=100_000)

# 终端工具（tools/terminal_tool.py:2590）— 多行式，命名函数 handler
registry.register(name="terminal", toolset="terminal", schema=TERMINAL_SCHEMA,
    handler=_handle_terminal, check_fn=check_terminal_requirements,
    emoji="💻", max_result_size_chars=100_000)
```

#### 3.1.4 check_fn TTL 缓存（`registry.py:109-148`）

- **TTL**: 30 秒（`_CHECK_FN_TTL_SECONDS`）
- **缓存键**: Callable 函数对象本身
- **线程安全**: `_check_fn_cache_lock`（`threading.Lock`）
- **异常处理**: 任何异常视为 `False`（工具标记为不可用）
- **显式失效**: `invalidate_check_fn_cache()` 清除全部缓存

`get_definitions()` 中还有一层**单次调用内缓存**（`check_results: Dict[Callable, bool]`），避免同一 `check_fn` 在同一 definitions 请求中被重复调用。

### 3.2 Toolset 系统（`toolsets.py`, 882 行）

#### 3.2.1 定义模式

```python
TOOLSETS = {
    "web":       {"description": "...", "tools": ["web_search", "web_extract"], "includes": []},
    "terminal":  {"description": "...", "tools": ["terminal", "process"],       "includes": []},
    "browser":   {"description": "...", "tools": ["browser_navigate", ...],     "includes": []},
    "debugging": {"tools": ["terminal", "process"], "includes": ["web", "file"]},
    "hermes-cli":{"tools": _HERMES_CORE_TOOLS,      "includes": []},
    # ...30+ toolsets
}
```

#### 3.2.2 关键特性

- **组合**: `includes` 支持递归引用其他 toolset
- **解析**: `resolve_toolset()` 扁平化递归，带循环检测
- **平台映射**: 每个平台都有自己的 `hermes-{platform}` toolset
- **工具搜索**: 渐进式披露——当工具总量超阈值时非核心工具被桥接到 `tool_search`/`tool_describe`/`tool_call`

### 3.3 运行时桥接（`model_tools.py`, 1067 行）

#### 3.3.1 Schema 提供 `get_tool_definitions()`（`model_tools.py:264`）

```python
def get_tool_definitions(enabled_toolsets, disabled_toolsets, quiet_mode, skip_tool_search_assembly):
```

两层缓存：
1. `_tool_defs_cache` —— 基于 `(toolsets, disabled, registry._generation, config_mtime, ...)` 键
2. `registry` 内部的 `check_fn` TTL 缓存（30s）

`_compute_tool_definitions()` 内部 flow：
1. 遍历 `enabled_toolsets` → `resolve_toolset()` 获取扁平工具名列表
2. 应用 `disabled_toolsets` 减集
3. `registry.get_definitions()` 过滤 `check_fn` + 应用 `dynamic_schema_overrides`
4. 后处理：`execute_code` schema 重建、discord 动态 schema、browser_navigate 描述裁剪
5. 渐进式披露：当 deferrable 表面超阈值时用桥接工具替换非核心 MCP/plugin 工具

#### 3.3.2 工具分派 `handle_function_call()`（`model_tools.py:802`）

```
handle_function_call(name, args, ...)
  │
  ├─ coerce_tool_args()          — 字符串→数字/bool 类型转换
  ├─ Tool Search 桥接分派        — tool_search/tool_describe/tool_call 的桥接
  ├─ Agent 拦截                  — todo/memory/session_search 返回 stub 错误
  ├─ Plugin pre-tool-call hook   — 检查是否 blocked
  ├─ ACP edit approval           — write_file/patch 的审批
  ├─ 读循环跟踪器                — 文件工具连续读计数器重置
  │
  └─ registry.dispatch(name, args, **kwargs)
       ├─ 异步桥接: _run_async() — 持久化事件循环
       └─ 异常→_sanitize_tool_error()
  │
  ├─ Plugin post-tool-call hook
  └─ Plugin transform-tool-result hook
```

#### 3.3.3 异步桥接（`model_tools.py:38-173`）

`_run_async()` 处理 3 种场景：
1. **已在异步循环中**（gateway/RL）：可抛弃线程 + 自有事件循环
2. **Worker 线程**（并行工具）：线程级持久化循环
3. **主线程**（CLI）：共享持久化 `_tool_loop`

### 3.4 工具实现模式

| 模式 | 示例 | 特点 |
|------|------|------|
| 同步函数 handler | `read_file`, `terminal` | 直接返回字符串 |
| lambda 包装 handler | `web_search`, `web_extract` | 从 args 字典提取参数 |
| 异步函数（`is_async=True`） | `web_extract` | 自动桥接到持久化事件循环 |
| shared `check_fn` | 同类工具共享 | 减少重复探测开销 |
| `requires_env` | web 工具 | 声明需要的环境变量 |
| `dynamic_schema_overrides` | 运行时改变 schema | 每次 get_definitions 调用时执行 |
| `max_result_size_chars` | 限制工具结果大小 | 防止大工具结果撑爆上下文 |

---

## 4 Memory 模块

### 4.1 MemoryManager（`agent/memory_manager.py`, 653 行）

#### 4.1.1 职责

编排**内置内存**（MEMORY.md + USER.md）+ **至多一个外部内存提供者**。

#### 4.1.2 关键方法

| 方法 | 功能 |
|------|------|
| `add_provider(provider)` | 注册提供者，构建 `_tool_to_provider` 路由表 |
| `prefetch_all(query, session_id)` | 预取所有外部提供者内容 |
| `sync_all(text)` | 同步所有提供者 |
| `handle_tool_call(tool_name, args)` | 按 `_tool_to_provider` 路由到正确提供者 |
| `on_session_switch(new_session_id, ...)` | 会话切换时通知所有提供者 |
| `on_memory_write(action, target, content, ...)` | 内置内存写入时镜像到外部 |
| `shutdown_all()` | 关闭所有提供者 |
| `get_all_tool_schemas()` | 聚合所有提供者的工具定义 |

#### 4.1.3 工具调用路由

`handle_tool_call()`（`memory_manager.py:441`）：
1. 在 `_tool_to_provider` 字典中查找工具名
2. 未找到 → 返回 `tool_error("No memory provider handles tool ...")`
3. 找到 → 委托给 `provider.handle_tool_call(tool_name, args)`

### 4.2 MemoryProvider 抽象（`agent/memory_provider.py`, 296 行）

**抽象基类**（`ABC`），定义可插拔内存后端的合约。

#### 4.2.1 必须实现

| 方法 | 返回 | 用途 |
|------|------|------|
| `name`（属性） | `str` | 唯一标识符 |
| `is_available()` | `bool` | 配置/凭据就绪检查 |
| `initialize(session_id, **kwargs)` | `None` | 创建资源、建立连接 |
| `get_tool_schemas()` | `List[Dict]` | 返回 OpenAI 格式工具定义 |
| `handle_tool_call(tool_name, args)` | `str` | 执行工具调用 |

#### 4.2.2 可选覆盖

| 方法 | 默认 | 用途 |
|------|------|------|
| `system_prompt_block()` | `""` | 注入到系统提示的静态文本 |
| `prefetch(query, session_id)` | `""` | 为即将到来的轮次召回上下文 |
| `queue_prefetch(query, session_id)` | 无操作 | 排队后台召回 |
| `sync_turn(user_content, assistant_content)` | 无操作 | 持久化完成轮次 |
| `shutdown()` | 无操作 | 清理资源 |

#### 4.2.3 可选钩子

| 钩子 | 触发时机 |
|------|---------|
| `on_turn_start(turn_number, message)` | 每轮开始 |
| `on_session_end(messages)` | 会话结束时 |
| `on_session_switch(new_session_id, ...)` | 会话 ID 轮换时 |
| `on_pre_compress(messages)` | 压缩前提取洞察 |
| `on_delegation(task, result, ...)` | 子代理完成时 |
| `on_memory_write(action, target, content, metadata)` | 内置内存写入时镜像 |

### 4.3 StreamingContextScrubber（`memory_manager.py:62-225`）

**用途**：状态机，从流式 SSE 文本中剥离 `<memory-context>...</memory-context>` 标签跨度。

**为什么需要**：一次性正则表达式会在标签跨 chunk 时失效。

**状态**：
- `_in_span: bool` —— 当前是否在标签内
- `_buf: str` —— 持有可能成为标签前缀的尾部字节
- `_at_block_boundary: bool` —— 验证开放标签是否为块级

**核心方法**：
- `feed(text)`: 返回去除标签后的可见文本
- `flush()`: 流结束时处理尾部

### 4.4 上下文压缩（`agent/conversation_compression.py` + `agent/context_compressor.py`）

#### 4.4.1 触发时机

1. **预检压缩**（`conversation_loop.py:587`）：进入主循环前估算 token 数，超过阈值则压缩
2. **工具执行后**（`conversation_loop.py:3885`）：每次工具执行后检查 `should_compress()`
3. **手动触发**：用户 `/compress` 命令

#### 4.4.2 `compress_context()` 执行流程（`conversation_compression.py:271`）

```
compress_context(messages, system_message)
  │
  ├─ 1. 惰性可行性检查（首次压缩时探测辅助模型）
  ├─ 2. 获取压缩锁（防止同一 session 并发 → 会话分叉）
  ├─ 3. 通知内存提供者 on_pre_compress()
  ├─ 4. 运行 context_compressor.compress()
  ├─ 5. 处理压缩中止（辅助 LLM 失败时无操作返回）
  ├─ 6. 追加待办快照
  ├─ 7. 使系统提示失效 + 重建
  ├─ 8. 轮换 SQLite 会话（结束旧会话、创建子会话）
  ├─ 9. 通知上下文引擎 + 内存提供者
  ├─ 10. 多次压缩警告（>=2 次后警告质量下降）
  └─ 11. 释放压缩锁
```

#### 4.4.3 ContextCompressor（`context_compressor.py:522-2078`）

- **结构化摘要模板**：Active Task / In Progress / Pending / Remaining 四段式
- **缩放预算**：默认 20% 的上下文窗口
- **尾部保护**：保留最后 N 条消息的 token 预算
- **迭代摘要**：可增量更新历史摘要
- **旧工具输出裁剪**：摘要化后修剪原始工具输出

---

## 5 可借鉴设计要点总结

| 设计 | 来源 | 可借鉴价值 |
|------|------|-----------|
| AST 扫描自发现工具 | **Tool** | 消除手动 `ensure_tools_registered()` |
| check_fn TTL 缓存 | **Tool** | 避免重复探测 Docker/Modal 等环境 |
| 双层工具过滤 (toolset + check_fn) | **Tool** | 比单一 category 分类更灵活 |
| 动态 schema 覆盖 | **Tool** | 运行时按需调整参数 schema |
| 三层系统提示 (stable/context/volatile) | **Prompt** | 区分缓存策略，减少 token 浪费 |
| 前缀缓存友好设计 (日期不精确到分钟) | **Prompt** | 提高提供商侧缓存命中率 |
| Anthropic system_and_3 缓存 | **Prompt** | 按提供商策略选择性使用 |
| 工具循环护栏 (4 检测 + 3 级别) | **Agent** | 防止 LLM 在失败工具上死循环 |
| 纯护栏控制器 (side-effect free) | **Agent** | 可独立测试和验证 |
| 子代理架构 (ThreadPoolExecutor) | **Agent** | 并发执行子任务 |
| 外部内存提供者抽象 | **Memory** | 可插拔记忆后端 |
| StreamingContextScrubber | **Memory** | 跨 chunk 标签清洗 |
| 上下文压缩流程 (会话轮换) | **Memory** | 突破上下文窗口限制 |


---

## 5 自改进循环 (Self-Improvement Loop)

**源文件**: `agent/background_review.py` (597 行)

### 5.1 核心机制

每次对话轮次结束后，`AIAgent.run_conversation` 可能调用 `spawn_background_review_thread()`，fork 出一个**守护线程**（daemon thread），对对话快照进行评估。线程创建一个新的 `AIAgent` 实例运行 review prompt，执行写操作直通 memory + skill 存储，但**不触碰主的对话状态和提示缓存**。

### 5.2 关键设计

| 设计 | 实现 | 价值 |
|------|------|------|
| **运行时继承** | 继承父代理的 provider/model/base_url/api_key/credential_pool | 避过 OAuth/凭据池无法重构造的问题 |
| **工具白名单** | 仅允许 memory + skills 工具，其余在运行时 deny | 安全的自省沙箱 |
| **缓存共享** | 继承 `_cached_system_prompt` + `session_start` + `session_id` | Anthropic 前缀缓存命中 → ~26% 端到端成本降低 |
| **静默执行** | stdout/stderr → devnull + `suppress_status_output = True` | 用户不感知后台活动 |
| **自动拒绝危险命令** | `_bg_review_auto_deny` 回调 → 返回 "deny" | 防止死锁 (input() 在守护线程中无意义) |
| **去重摘要** | `summarize_background_review_actions()` 与 `prior_snapshot` 对比 | 避免重复展示陈旧的操作 |

### 5.3 三种 Prompt

| Prompt | 触发条件 |
|--------|---------|
| `_MEMORY_REVIEW_PROMPT` (34-43) | review_memory=True, review_skills=False |
| `_SKILL_REVIEW_PROMPT` (45-233) + 组合 | review_skills=True, review_memory=False |
| `_COMBINED_REVIEW_PROMPT` | 两者均为 True |

Memory review prompt 关注用户个人信息/偏好；Skill review prompt 含 4 个行动优先级 (update loaded → update existing → add support file → create new umbrella)。

### 5.4 对比 OmniAgent 适用性

Hermes 的 review fork 模型对 OmniAgent 的改进点：forking AIAgent 比我们在 `tools/` 中内联 review 更清洁；tool whitelist 模式可直接套用为当前 Agent 的沙箱模式。

---

## 6 技能生成能力 (Skills Generation System)

### 6.1 三个子系统

| 子系统 | 源文件 | 行数 | 职责 |
|--------|--------|------|------|
| **Agent Skill 管理工具** | `tools/skill_manager_tool.py` | 1034 | 6 种操作 (create/edit/patch/delete/write_file/remove_file) |
| **Skill 浏览工具** | `tools/skills_tool.py` | 1524 | 渐近式披露 (skills_list→元数据, skill_view→完整内容) |
| **Skills Hub CLI** | `tools/skills_hub.py` | 3748 | 注册中心适配器 (GitHub/WellKnown/Official) |

### 6.2 SKILL.md 格式规范

```yaml
---
name: skill-name         # 必须 ≤64 字符
description: ...         # 必须 ≤1024 字符  
version: 1.0.0           # 可选
license: MIT             # 可选 (agentskills.io)
platforms: [macos]       # 可选 — 限制 OS 平台
prerequisites:           # 可选
  env_vars: [API_KEY]    #   环境变量要求
  commands: [curl, jq]   #   命令检查 (仅 advisory)
compatibility: ...       # 可选 (agentskills.io)
metadata:                # 可选 (agentskills.io)
  hermes:
    tags: [fine-tuning]
    related_skills: [peft]
---
```

### 6.3 目录规范

```
my-skill/
├── SKILL.md          # 主指令 (必须)
├── references/       # 引用文档
├── templates/        # 模板文件
├── scripts/          # 可重复运行的脚本
└── assets/           # agentskills.io 补充文件标准
```

### 6.4 Security Guard

`tools/skills_guard.py` 对 hub 安装的技能进行安全扫描 (内容哈希、信任仓库列表、可疑模式检测)。Agent 自创的技能默认跳过扫描（因为 Agent 已可通过终端执行相同代码路径）。

### 6.5 自改进流程集成

background_review 的 `_SKILL_REVIEW_PROMPT` 驱动 Agent 在每轮对话后:
1. 检查是否有风格/工作流/技术被纠正 → 更新已有技能
2. 检查是否有同类任务经验 → 创建新的 umbrella skill
3. 4 级优先级：update loaded → update existing → add support file → create new

---

## 7 Honcho 辨证记忆系统

**源文件**: `plugins/memory/honcho/__init__.py` (1800+ 行)

### 7.1 是什么

Honcho 是一个 AI-native 跨会话用户建模系统，提供**辨证问答** (Dialectic Q&A)、**语义搜索**、**对等卡片** (Peer Cards) 和**持久化结论**。通过 `MemoryProvider` ABC 接入 Hermes。

### 7.2 5 个工具

| 工具 | 用途 | 是否调用 LLM |
|------|------|-------------|
| `honcho_profile` | 读取/更新对等卡片 (curated facts) | ❌ 无 LLM |
| `honcho_search` | 语义搜索原始对话摘要 | ❌ 无 LLM |
| `honcho_context` | 获取完整会话上下文快照 | ❌ 无 LLM |
| `honcho_reasoning` | LLM 合成回答问题 | ✅ Honcho 端 LLM |
| `honcho_conclude` | 创建/删除持久化结论 | ❌ 直接写入 |

### 7.3 辨证推理 (Dialectic Reasoning)

**重要澄清**: Honcho 使用的 "dialectic" 并非 "支持方+反对方碰撞" 模式，而是**多层递进式 LLM 推理**：

| 层次 (depth) | 行为 | 说明 |
|-------------|------|------|
| depth=1 | 1 次冷启动/温会话查询 | 单人设问，LLM 直接回答 |
| depth=2 | 第 0 次 + 第 1 次自审 | 第 1 次对第 0 次结果进行差距分析 |
| depth=3 | 第 0 次 + 第 1 次 + 第 2 次调和 | 第 2 次检查一致性，调和矛盾 |

**推理深度选择**: `reasoning_level` 参数 (minimal/low/medium/high/max) + 查询长度启发式 (≥120 字符 bump 1 级, ≥400 bump 2 级) + `reasoning_level_cap` 上限钳制。每个 pass 调用 Honcho 端的 `.chat()` API（非本地模型）。

**提前退出**: `_signal_sufficient()` 检测输出是否 ≥100 字符且有结构化内容（## ● 编号列表）→ 跳过后续 pass。

### 7.4 三种调取模式

| 模式 (recall_mode) | 自动注入 | 工具可用 | 使用场景 |
|-------------------|---------|---------|---------|
| context | ✅ | ❌ | 完全自动，无感知 |
| tools | ❌ | ✅ | Agent 自主决策调取 |
| hybrid | ✅ | ✅ | 自动辅助 + 按需深查 |

### 7.5 节奏控制 (Cadence Gating)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `dialecticCadence` | 1 (新配置 2) | 辨证调用间隔 (轮次数) |
| `contextCadence` | 1 | 基础上下文刷新间隔 |
| `injectionFrequency` | "every-turn" | 或 "first-turn" (仅首轮注入) |

空结果退避: `_dialectic_empty_streak` 累计空返回 → cadence 递增 (上限 base × 8)。

### 7.6 预取架构

- **预热线程**: 会话初始化时启动 `honcho-prewarm-dialectic` 守护线程，执行完整辨证深度 → 结果写入 `_prefetch_result` → 首轮直接使用
- **queue_prefetch()**: 每轮间异步刷新 `_base_context_cache` + 辨证补充
- **过期处理**: 超过 cadence × 2 轮的预取结果丢弃（避免陈旧 pivot 注入）

---

## 8 三层跨会话记忆系统

### 8.1 三层架构

| 层级 | 存储方式 | 文件/模块 | 检索延迟 | 信息类型 |
|------|---------|-----------|---------|---------|
| **L1: 消息级检索** | SQLite + FTS5 | `hermes_state.py` (SessionDB) | 毫秒 | 历史消息全文检索 |
| **L2: 外部记忆提供者** | 插件式 (Honcho 等) | `memory_manager.py` + `memory_provider.py` | 百毫秒~秒级 | 用户模型 + 辨证洞察 |
| **L3: 文件式记忆** | MEMORY.md/USER.md | `agent/memory_manager.py` | 毫秒 | 声明式持久化知识 |

### 8.2 FTS5 全文搜索 (L1)

**源文件**: `hermes_state.py` (第 320-351 行创建 FTS 表)

```sql
-- 默认 unicode61 tokenizer (英文)
CREATE VIRTUAL TABLE messages_fts USING fts5(content, tokenize='unicode61');

-- 三元组 tokenizer (CJK 子串搜索)
CREATE VIRTUAL TABLE messages_fts_trigram USING fts5(content, tokenize='trigram');
```

**FTS5 查询策略 (第 2720-2866 行)**:

```
query → sanitize_fts5() → 检查是否是 CJK (含中文字符)
  ├─ 非 CJK → messages_fts MATCH (快速路径)
  └─ CJK → 检查每个 token 字符数
      ├─ ≥3 CJK 字符 → messages_fts_trigram MATCH (trigram)
      └─ 1-2 CJK 字符 → LIKE 子串匹配 (降级，trigram 需要 ≥9 UTF-8 字节)
```

**降级机制**: 当 Python 构建的 SQLite 没有 FTS5 模块时 (`_is_fts5_unavailable_error`)，优雅降级为 LIKE 查询。

### 8.3 会话搜索工具

`tools/session_search_tool.py` (602 行) 提供 3 种形状：

| 形状 | 参数 | 行为 |
|------|------|------|
| **DISCOVERY** | `query` | FTS5 搜索 → 按会话谱系去重 → 每个命中返回 snippet + ±5 消息窗口 + bookends |
| **SCROLL** | `session_id` + `around_message_id` | 以指定消息为中心 ±window 条消息，无 FTS5 |
| **BROWSE** | 无参数 | 返回最近会话 (标题/预览/时间戳) |

### 8.4 MemoryProvider 抽象 (L2)

```
MemoryProvider (ABC)          ← HonchoMemoryProvider
├── initialize(session_id)
├── system_prompt_block()     → 注入系统提示
├── prefetch(query)           → 预取上下文
├── queue_prefetch(query)     → 后台刷新
├── sync_turn(user, assistant)→ 同步对话轮次
├── on_turn_start(turn, msg)
├── on_session_end(messages)
├── on_memory_write(action, target, content)
├── get_tool_schemas()        → 注册工具
├── handle_tool_call(name, args)
└── has_tool(name)
```

`MemoryManager` (244 行) 是门面，管理多个 provider 实例，串联 `build_system_prompt()` → `prefetch_all()` → `sync_all()` → `queue_prefetch_all()`。

---

## 9 六种执行后端

### 9.1 架构

**源文件**: `tools/environments/` (11 文件, ~4970 行)

所有后端实现同一接口 `BaseEnvironment.execute()`，通过 `_create_environment()` 工厂函数 (`terminal_tool.py:1144`) 基于 `TERMINAL_ENV` 环境变量选择。

### 9.2 后端列表

| 后端 | 类 | 适用场景 | 特点 |
|------|---|---------|------|
| **local** | `_LocalEnvironment` | 开发/测试 | 直接 subprocess，最简 |
| **docker** | `_DockerEnvironment` | 隔离执行 | containers, 孤儿清理, 持久卷 |
| **singularity** | `_SingularityEnvironment` | HPC/科学计算 | overlay/SIF 缓存 |
| **modal** (直连) | `_ModalEnvironment` | 云端 Serverless | Modal Sandbox API |
| **modal** (托管) | `_ManagedModalEnvironment` | Nous 托管 | 由 Nous 管理的 Modal 实例 |
| **daytona** | `_DaytonaEnvironment` | 云端开发环境 | Daytona API |
| **ssh** | `_SSHEnvironment` | 远程机器 | SSH 连接池 |

### 9.3 通用模型

所有后端使用 **spawn-per-call** 模型：每个命令启动一个新的 `bash -c` 进程。会话快照（env vars、函数、别名）在 init 时捕获一次，每个命令前重新 source。CWD 通过 stdout 标记 (远程) 或临时文件 (本地) 持久化。

### 9.4 Liveness 机制

- **`touch_activity_if_due()`**: 每 10 秒发射活动回调，让网关知道后台操作仍在进行
- **中断检查**: 每个命令执行中定期检查 `is_interrupted()`，支持优雅终止

---

## 10 agentskills.io 开放技能标准

### 10.1 是什么

agentskills.io 是一个**开放标准**，定义了 AI agent 技能的组织格式、元数据和发现机制。Hermes 是其参考实现之一。

### 10.2 核心发现协议

```
GET {base_url}/.well-known/skills/index.json
```

**index.json 格式**:
```json
{
  "skills": [
    {
      "name": "skill-creator",
      "description": "...",
      "files": ["SKILL.md", "references/api.md"]
    }
  ]
}
```

**标识符格式**:
- URL 片段: `{base_url}/.well-known/skills/index.json#skill-name`
- 直接 URL: `{base_url}/.well-known/skills/skill-name/SKILL.md`
- well-known 前缀: `well-known:{base_url}/.well-known/skills/skill-name`

### 10.3 Hermes 的 WellKnownSource 实现

| 方法 | 用途 | 缓存 |
|------|------|------|
| `search(query)` | 搜索 index.json 中所有技能 | 1 小时 TTL + hash 缓存 |
| `inspect(identifier)` | 获取单个技能元数据 (读取 SKILL.md 前端) | 无 |
| `fetch(identifier)` | 下载完整的技能包 (按 files 列表逐一获取) | 无 |

**安全机制**:
- `_guarded_http_get()`: SSRF 防护 + 每跳 URL 安全检查 + 最大 5 跳重定向限制
- `_validate_bundle_rel_path()`: 路径遍历/绝对路径/空路径/Windows 盘符前缀 拦截
- `_normalize_lock_install_path()`: rmtree 逃逸防护 (symlink 检查 + 中间路径逐段验证)

### 10.4 信任等级系统

| 等级 | 说明 | 对应 Hermes 源 |
|------|------|---------------|
| `builtin` | Hermes 内置 | 随 repo 分发 |
| `trusted` | 受信任仓库 | GitHub trusted repos 列表 |
| `community` | 社区提交 | WellKnownSource (任何 agentskills.io 注册站) |

### 10.5 部署模型

```json
// HERMES_HOME/honcho.json (按此顺序解析)
{
  "recall_mode": "hybrid",
  "dialectic_depth": 2,
  "dialecticCadence": 2,
  "injectionFrequency": "every-turn"
}
```

配置链: `$HERMES_HOME/honcho.json` → `~/.honcho/config.json` → 环境变量

---

## 11 可借鉴设计要点总结（补充）

| 设计 | 来源 | 可借鉴价值 |
|------|------|-----------|
| **Fork 自改进循环** | §5 Self-Improvement | Agent 自主评估自身表现，无需外部 review |
| **Tool 白名单沙箱** | §5 Self-Improvement | Review fork 隔离运行，工具受限 |
| **渐近式披露技能** | §6 Skills | skills_list(元数据) → skill_view(完整) 模式 |
| **技能目录规范** | §6 Skills | 4 种子目录 (references/templates/scripts/assets) |
| **辨证多轮推理** | §7 Honcho | 1-3 层递进式自我批判，可提前退出 |
| **归因前端码** | §7 Honcho | reasoning_level 参数化，根据查询长度自适应 |
| **Cadence 退避** | §7 Honcho | 空结果递增间隔，防止无意义轮询 |
| **双重 FTS5 表** | §8 Memory | unicode61(英文) + trigram(CJK) 双表 |
| **优雅降级** | §8 Memory | FTS5 不可用时自动降级为 LIKE |
| **3 形状搜索** | §8 Memory | DISCOVERY/SCROLL/BROWSE 分离 |
| **MemoryProvider ABC** | §8 Memory | 可插拔，当前 OmniAgent 缺少 |
| **Spawn-per-call 后端** | §9 Environments | 每个命令全新程，消除状态污染 |
| **Liveness 回调** | §9 Environments | 长时间命令可通知前端 |
| **agentskills.io 发现协议** | §10 Standards | `.well-known/skills/index.json` 开放标准 |
| **数字安全扫描** | §10 Standards | 内容哈希 + 信任列表 + 路径遍历防护 |

---

**更新时间**: 2026-06-01 22:50:00
**编写人**: 小沈
