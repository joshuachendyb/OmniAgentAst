# Agent 工具意图流程深度分析

**创建时间**: 2026-06-12 10:32:37  
**版本**: v1.0  
**作者**: 小沈  
**分析范围**: 后端 Agent 体系、工具体系、意图分类体系完整流程  

---

## 一、完整请求流程图

```
用户发送消息 (POST /api/v1/chat/stream)
    │
    ▼
[1] chat_stream_v2.py:48
    detect_intent(user_input)  ← CRSS正则评分
    返回: intent_type("file"/"system"/...), confidence, candidates
    │
    ▼
[2] chat_stream_v2.py:50
    get_service()  ← 获取LLM客户端
    │
    ▼
[3] chat_stream_v2.py:62
    register_task(task_id)  ← 注册任务到task_registry
    │
    ▼
[4] chat_stream_v2.py:64
    task_interrupt_check()  ← 检查任务是否被中断
    │
    ▼
[5] chat_stream_v2.py:70
    step_start()  ← 发送start Step给前端(SSE)
    │
    ▼
[6] chat_stream_v2.py:73
    run_sse_stream(intent_type, candidates, ...)  ← 启动SSE流
    │
    ▼
[7] run_sse_stream.py:42
    AgentFactory.create(intent_type, llm_client, task_id, candidates)
    │
    ▼
[8] agent_factory.py:31
    resolve_agent_config(intent_type)  ← 查AGENT_REGISTRY
    返回: AgentConfig(category, prompt_class, extra_categories, ...)
    │
    ▼
[9] universal_agent.__init__() → BaseAgent.__init__()
    │
    ├─ AgentInitializer._init_llm()        ← 初始化LLM客户端
    ├─ AgentInitializer._init_state()       ← 初始化状态(category, max_steps)
    ├─ AgentInitializer._init_messages()    ← 初始化消息构建器
    ├─ ToolManager.init_tools()             ← 加载工具(关键!)
    ├─ ToolRetryEngine()                    ← 初始化重试引擎
    └─ AgentInitializer._init_candidates()  ← 初始化候选意图
    │
    ▼
[10] agent.run_react_cycle(task=user_input)
    │
    ▼
[11] react_cycle.py:83
    initialize_run_state()  ← 重置状态,构建system+task prompt
    │
    ▼
[12] while step < max_steps:
    _process_single_step()
    │
    ├─ agent._call_llm()  ← 调用LLM
    │   └─ _call_llm_fc_stream()  ← FC模式流式调用
    │       ├─ LLM流式响应 → 收集chunk
    │       ├─ parse_json(full_content)  ← 解析JSON
    │       ├─ 容错: "tool_name"标记 → 向前定位{ → 括号匹配
    │       └─ 返回 ("response", {type:"action"/"answer", ...})
    │
    ├─ parsed_type = llm_response["type"]
    ├─ handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
    │
    ├─ type=="action" → handle_action():
    │   ├─ ThoughtStep emit
    │   ├─ check_safety_and_confirm()  ← 安全检查+HITL确认
    │   ├─ execute_tools()  ← 工具执行
    │   │   └─ _execute_tool() → retry_engine.execute_tool_with_retry()
    │   │       ├─ _find_tool(name) → tool_registry.get_implementation()
    │   │       ├─ _validate_params()
    │   │       ├─ _execute_tool_once()  ← 实际执行工具函数
    │   │       └─ _execute_with_retry()  ← 重试逻辑(仅timeout)
    │   └─ build_observation()  ← 构建observation返回给LLM
    │       ├─ build_observation_text()  ← 格式化文本
    │       └─ _update_message_builder()  ← 更新FC协议消息
    │
    └─ type=="answer" → handle_answer():
        ├─ ThoughtStep emit
        └─ FinalStep emit → status=COMPLETED
    │
    ▼
[13] run_sse_stream.py:116
    save_execution_steps_to_db()  ← 保存到SQLite
    │
    ▼
SSE流结束,前端收到完整响应
```

---

## 二、意图分类流程详解

### 2.1 CRSS评分完整逻辑

**双维度打分** (`crss_scorer.py:85-179`):

**第一层：类型维度** — 用户要对"什么"操作
- 遍历 `_CRSS_REGISTRY` 中每个意图定义
- 对每个意图的 `keywords`(英文正则)和 `chinese_keywords` 进行匹配
- 中文关键词 +2.0分/个，英文关键词 +1.0分/个
- 英文使用 `\b` 边界匹配（`_ascii_word_boundary_match`）
- 否定前缀检测（`_is_negated`）：检查"不/没/别/勿/无/未/非"等否定词

**第二层：动作维度** — 用户要"做什么" (`crss_definitions.py:7-69`)
- 8个动作定义：read/create/delete/execute/query/navigate/configure/capture
- 每个动作有关键词列表和兼容矩阵
- 动作命中后通过兼容系数调制类型分：`最终分 = 类型分 × (1 + 兼容系数 × CRSS_ACTION_MODULATION_FACTOR)`

**合成逻辑** (`_merge_scores`):
1. 有类型分 → 用动作兼容矩阵调制
2. 无类型分 → 用动作反推类型（兜底，compat≥1.0才参与）
3. 归一化：`1.0 - 2^(-raw)` 映射到 [0,1)

**阈值**: `CRSS_CONFIDENCE_THRESHOLD = 0.3` — ⚠️ **导入但从未使用**（见问题 P-1）

### 2.2 _CRSS_REGISTRY 完整结构

| CRSS名 | IntentType | 英文关键词 | 中文关键词 |
|---------|-----------|-----------|-----------|
| **FILE** | FILE | ls/dir/cd/pwd/cat/grep/find/tree/cp/mv/rm/mkdir/touch/**txt/md/json/yaml/toml/ini**/zip/tar/gz/compress/archive | 文件/目录/文件夹/路径/磁盘/c盘/d盘/e盘/压缩/解压/归档/打包/重命名/改名/复制/拷贝/移动/搜索 |
| **SHELL** | SYSTEM | npm/pip/node/gcc/python/git/docker/gradle | 终端/命令/脚本 |
| **TIME** | SYSTEM | date/time/now/clock/calendar/schedule | 时间/日期/今天星期/几月几号/现在几点 |
| **ENV** | SYSTEM | PATH/HOME/TEMP | 环境变量/系统变量 |
| **ENVIRONMENT** | SYSTEM | environment/env | 环境/环境变量 |
| **SYSTEM** | SYSTEM | cpu/memory/ram/disk/process/service | 系统信息/CPU/内存/进程/服务/磁盘 |
| **CODE_EXECUTION** | SYSTEM | compile/g++ | 编译/执行程序 |
| **META** | SYSTEM | version/config/info | 版本/配置/信息/状态 |
| **NETWORK** | NETWORK | ping/curl/wget/ssh/http/https/ftp/socket | 网络/端口/下载/请求/API/IP/IP地址/DNS/公网IP/网关/WIFI/WiFi |
| **DOCUMENT** | DOCUMENT | docx/pdf/csv/xlsx/pptx | 文档/报告/笔记/文本/文章 |
| **DATABASE** | DOCUMENT | sql/db/database/select/insert/update/delete | 数据库/表/数据/SQL |
| **DESKTOP** | DESKTOP | screenshot/capture/click/type/press/key | 截图/录屏/点击/按键/键盘/鼠标/窗口/桌面/浏览器 |

### 2.3 意图分类歧义分析

**txt/md/json 文件请求** — ✅ 正确路由到 FILE

用户说"读取config.json"时：
- FILE意图：`json` +1.0, `文件` +2.0 → **FILE分 = 3.0**
- DOCUMENT意图：无匹配 → **DOC分 = 0**
- FILE胜出 → **正确**

**docx/pdf 文件请求** — ✅ 正确路由到 DOCUMENT

用户说"读取report.docx"时：
- FILE意图：`文件` +2.0 → **FILE分 = 2.0**
- DOCUMENT意图：`docx` +1.0, `文档` +2.0 → **DOC分 = 3.0**
- DOCUMENT胜出 → **正确**

**歧义区域** — ⚠️ 存在风险

用户说"读取一个json文档"时：
- FILE意图：`json` +1.0 → **FILE分 = 1.0**
- DOCUMENT意图：`文档` +2.0 → **DOC分 = 2.0**
- DOCUMENT胜出 → ⚠️ json实际是FILE工具能处理的，但被分到DOCUMENT Agent

---

## 三、Agent选择流程详解

### 3.1 AgentFactory映射关系

`agent_config.py:53-96`:

| intent_type | AgentClass | ToolCategory | prompt | extra_categories |
|---|---|---|---|---|
| `file` | UniversalAgent | FILE | FileOperationPrompts | — |
| `system` | UniversalAgent | FUND_RUNTIME | SystemPrompts | **[FILE]** |
| `network` | UniversalAgent | NET_PROCESS | NetworkPrompts | — |
| `document` | UniversalAgent | DOC_CONTENT | DocumentPrompts | — |
| `desktop` | UniversalAgent | SCREEN | DesktopPrompts | — |

### 3.2 intent_type如何决定用哪个Agent

1. `detect_intent()` 返回 `intent_type`（如 `"file"`）
2. `AgentFactory.create(intent_type="file")` → `resolve_agent_config("file")`
3. `resolve_agent_config` 调用 `normalize_intent("file")` → 查 `INTENT_MAPPING`
4. `INTENT_MAPPING` 由 `_CRSS_REGISTRY` 自动派生
5. 最终从 `AGENT_REGISTRY` 获取 `AgentConfig`

### 3.3 意图映射的两层转换

```
CRSS返回: ToolCategory (如 FUND_RUNTIME)
    ↓ _TOOLCATEGORY_TO_INTENT 映射
detect_intent返回: intent_type (如 "system")
    ↓ normalize_intent 查 INTENT_MAPPING
resolve_agent_config: IntentType (如 SYSTEM)
    ↓ AGENT_REGISTRY.get()
AgentConfig: category=FUND_RUNTIME, prompt=SystemPrompts, extra=[FILE]
```

### 3.4 注意事项

**system Agent 额外加载 FILE 工具** (`agent_config.py:69`):
- `system` Agent 的 `extra_categories=[ToolCategory.FILE]`
- 意味着 system 意图的 Agent 可以调用文件工具
- 但 `file` Agent 没有 `extra_categories`，不能调用系统工具
- **这是有意设计**：system 意图（如"执行python脚本"）经常需要读写文件

---

## 四、ReAct循环详解

### 4.1 BaseAgent循环逻辑

`react_cycle.py:71-123`:

```python
while step < max_steps:
    # 1. 调用LLM → 获取chunk流 + 最终response
    llm_response = _process_single_step(agent, step_counter, chunk_buffer)
    
    # 2. 检查是否中断
    if agent.status in (COMPLETED, FAILED): break
    
    # 3. 检查chunk累积超时
    if chunk_buffer.should_force_stop(): break
```

### 4.2 thought/action/observation流转

1. **LLM返回** → `_call_llm_fc_stream()` 解析为 `{"type":"action","tool_name":"xxx",...}` 或 `{"type":"answer","content":"xxx"}`
2. **action路径**: emit ThoughtStep → check_safety → execute_tools → emit ActionToolStep → build_observation → emit ObservationStep → 回到LLM
3. **answer路径**: emit ThoughtStep → emit FinalStep → status=COMPLETED

### 4.3 工具调用完整链路

```
LLM返回JSON: {"type":"action", "tool_name":"read_text_file", "params":{...}}
    │
    ▼
[1] handle_action() (action_handler.py:163)
    │
    ├─ ThoughtStep emit  ← 发送思考步骤
    │
    ├─ check_safety_and_confirm()  ← 安全检查
    │   ├─ safety_checker.check_before_execute(tool_name, params)
    │   │   ├─ Layer 0: security.enabled 开关检查
    │   │   ├─ Layer 1: ToolSafetyLevel 级别检查
    │   │   ├─ Layer 2: _check_known_risks() 路径越权/写入污染/代码注入
    │   │   └─ Layer 3: file_safety.execute_with_safety() DB事务编排
    │   │
    │   ├─ blocked → ErrorStep emit → agent.status=FAILED
    │   └─ requires_confirmation → IncidentStep emit → wait_for_confirmation_result()
    │       ├─ confirmed → 继续执行
    │       └─ rejected → ErrorStep emit → agent.status=FAILED
    │
    ├─ execute_tools()  ← 工具执行
    │   └─ agent._execute_tool(tool_name, tool_params)
    │       └─ retry_engine.execute_tool_with_retry(tool_name, tool_params)
    │           ├─ _find_tool(name) → tool_registry.get_implementation()
    │           ├─ _validate_params()  ← 检查非法参数+必需参数
    │           ├─ _execute_tool_once()  ← 实际执行工具函数
    │           │   ├─ async工具 → await impl(**params)
    │           │   └─ sync工具 → loop.run_in_executor(None, impl, **params)
    │           └─ _execute_with_retry()  ← 重试逻辑(仅timeout)
    │               ├─ 最多3次重试
    │               ├─ 指数退避(退避因子2.0)
    │               └─ 仅重试timeout类错误
    │
    └─ build_observation()  ← 构建observation
        ├─ build_observation_text(result, tool_name, tool_params)  ← 格式化文本
        ├─ _update_message_builder(agent, obs_text, fc_context)  ← 更新FC协议消息
        │   └─ message_builder.add_observation(obs_text, fc_context)
        │       └─ role=assistant(tool_calls) + role=tool(tool_call_id)
        └─ ObservationStep emit  ← 发送观察步骤
```

### 4.4 错误处理和重试逻辑

- 重试配置在 `tool_constants.py:171-181`：默认最多3次重试，退避因子2.0
- 仅重试 `timeout` 类错误
- 参数验证失败直接返回错误，不重试
- 工具执行异常返回 `Exception` 对象，不中断循环

---

## 五、工具注册与发现机制

### 5.1 ToolRegistry单例模式

`registry.py:246`:
```python
tool_registry = ToolRegistry()
```
全局单例，所有模块共享。

### 5.2 工具注册流程

1. **启动时** → 不注册
2. **首次请求** → `Agent.__init__()` → `ToolManager.init_tools()` → 首次触发
3. `ensure_tools_registered()` (`lazy_loader.py:46`) → 遍历 `CATEGORY_MODULES` → 调用各分类的 `_register_xxx_tools()`
4. 各注册函数调用 `tool_registry.register()` 注册工具

### 5.3 7个工具分类

| 分类 | 注册模块 | 注册函数 | 工具数 |
|------|---------|---------|-------|
| file | app.services.tools.file | _register_file_tools | 11 |
| shell | app.services.tools.shell | _register_shell_tools | 4 |
| network | app.services.tools.network | _register_network_tools | 5 |
| system | app.services.tools.system | _register_system_tools | 10 |
| desktop | app.services.tools.desktop | _register_desktop_tools | 9 |
| document | app.services.tools.document | _register_document_tools | 9 |
| meta | app.services.tools.meta | _register_meta_tools | 10 |

### 5.4 工具加载逻辑（Agent级）

`tool_manager.py:22-50`:
1. **始终加载 meta 工具**（META_TOOL_NAMES: tool_help/tool_search/pipeline/get_time等）
2. **加载分类工具**（agent.tool_category 对应的工具）
3. **加载额外分类工具**（config.extra_categories，如 system Agent 额外加载 FILE 工具）

---

## 六、工具执行流程详解

### 6.1 从LLM输出到工具执行的完整链路

1. LLM流式响应 → `_call_llm_fc_stream()` (`universal_agent.py:149`)
2. `parse_json(full_content)` → 解析JSON
3. **容错机制** (`universal_agent.py:191-205`): 如果直接解析失败，搜索 `"tool_name"` 标记向前定位 `{` 再括号匹配
4. 提取 `tool_name`, `tool_params`, `tool_calls`(平行调用)
5. yield `("response", {"type":"action", ...})`
6. `react_cycle.py:65` 根据 `parsed_type` 分派到 `handle_action`

### 6.2 工具安全检查介入点

`action_handler.py:195-198` → `check_safety_and_confirm()`:
1. `tool_safety_checker.check_before_execute(tool_name, params)` (`tool_safety_checker.py:47`)
2. **三重检查**:
   - **Layer 2**: 安全级别策略（READ_ONLY/SAFE/DESTRUCTIVE/DANGEROUS_SANDBOX/DANGEROUS）
   - **路径越权**: 文件工具路径验证
   - **写入污染**: write_text_file 的内容检查
   - **代码注入**: execute_shell/execute_code 的危险模式匹配
3. `requires_confirmation=True` → 触发 HITL 确认（IncidentStep → 前端弹窗 → wait_for_confirmation_result）

### 6.3 工具结果如何返回给LLM

1. `action_handler.build_observation()` (`action_handler.py:102-161`)
2. `build_observation_text(result, tool_name, tool_params)` → 格式化文本
3. `_update_message_builder(agent, obs_text, fc_context)` → `message_builder.add_observation()`
4. FC协议格式：`role=assistant(tool_calls)` + `role=tool(tool_call_id)`
5. 下一轮LLM调用时，observation已在 conversation_history 中

---

## 七、发现的问题和矛盾

### 问题 P-1: CRSS_CONFIDENCE_THRESHOLD 已导入但从未使用

**严重程度**: P2-中

**位置**: `crss_scorer.py:25`

**现象**: `CRSS_CONFIDENCE_THRESHOLD = 0.3` 被导入，但 `detect_intent_v2()` 在返回结果时**不检查** confidence 是否达到阈值。只要有任何匹配（score > 0），就返回 primary intent。

**影响**: 当用户输入仅含极弱关键词（如单个英文单词 `info`），CRSS也会返回对应意图，而非fallback到LLM兜底。例如用户说"你好"可能被FILE的某个关键词部分匹配。

**建议**: 在 `detect_intent_v2()` 中添加阈值检查：
```python
if confidence < CRSS_CONFIDENCE_THRESHOLD:
    return None, [], confidence
```

---

### 问题 P-2: candidates命名体系与intent_type不一致

**严重程度**: P1-高

**位置**: `detect_intent.py:32`, `universal_agent.py:86-97`

**现象**: `detect_intent()` 返回的 candidates 是 ToolCategory.value（如 `"fund_runtime"`, `"doc_content"`），但 `_build_candidates_hint()` 调用 `resolve_agent_config(c)` 时传入的也是这些值。

**根因链路**:
```
detect_intent() 返回 candidates = [c.value for c in candidates]
→ candidates = ["fund_runtime", "doc_content", ...]
→ _build_candidates_hint() 调用 resolve_agent_config("fund_runtime")
→ normalize_intent("fund_runtime") → _lookup_intent("fund_runtime")
→ INTENT_MAPPING.get("FUND_RUNTIME") → None (因为key是"_SHELL"等)
→ 返回默认值 "system"
→ AGENT_REGISTRY.get("system") → system config
```

**影响**: 
- `doc_content` 被错误映射到 system config（应为 document config）
- `fund_runtime` 被错误映射到 system config（虽然结果碰巧正确，但语义错误）
- 候选意图提示显示错误的分类名称

**建议**: `detect_intent()` 返回 candidates 时应做映射转换：
```python
return intent, confidence, [_TOOLCATEGORY_TO_INTENT.get(c.value, c.value) for c in candidates if c]
```

---

### 问题 P-3: DOCUMENT工具未设置安全级别

**严重程度**: P2-中

**位置**: `document_register.py:329-337`

**现象**: 注册文档工具时未传入 `safety_level` 参数，全部使用默认值 `ToolSafetyLevel.SAFE`。但 `execute_sql` 工具可以执行写操作SQL（INSERT/UPDATE/DELETE），安全级别应为 `DESTRUCTIVE`。

**影响**: `execute_sql` 执行 `DROP TABLE` 等破坏性SQL时，不会触发HITL确认，直接执行。

**建议**: 在 `document_register.py` 中为 `execute_sql` 设置安全级别：
```python
safety_levels = {
    "execute_sql": ToolSafetyLevel.DESTRUCTIVE,
    # 其他工具保持 SAFE
}
```

---

### 问题 P-4: system Agent 额外加载 FILE 工具但FILE Agent不加载SYSTEM工具

**严重程度**: P3-低

**位置**: `agent_config.py:63-71`

**现象**: `system` Agent配置了 `extra_categories=[ToolCategory.FILE]`，意味着system意图的Agent可以调用文件工具。但 `file` Agent没有 `extra_categories`，不能调用系统工具。

**影响**: 这是有意设计（system意图如"执行python脚本"经常需要读写文件），但file意图如"读取文件并执行"无法执行shell命令。

**建议**: 如果需要双向能力，可考虑为file Agent也添加 `extra_categories=[ToolCategory.FUND_RUNTIME]`。但当前设计可能是合理的——file操作不需要shell能力。

---

### 问题 P-5: _TYPE_HANDLERS 只注册了 action 和 answer

**严重程度**: P3-低

**位置**: `react_cycle.py:26-30`

**现象**: `_TYPE_HANDLERS` 只注册了 `"action"` 和 `"answer"`。当LLM返回 `"chunk"` 或 `"parse_error"` 类型时，会走到 `_DEFAULT_HANDLER = handle_answer`。

**影响**: 实际影响很小——在FC-only模式下，chunk在 `_call_llm_fc_stream` 内部处理，不会出现在 `_process_single_step` 中。parse_error也不应该出现在这里。

**建议**: 可以添加显式处理或至少记录日志，但优先级低。

---

### 问题 P-6: parallel tool_calls的JSON解析存在静默失败风险

**严重程度**: P2-中

**位置**: `universal_agent.py:220-222`

**现象**: `json.loads(func.get("arguments", "{}"))` 从tool_calls中解析arguments。如果LLM返回的arguments格式异常，会静默失败（空dict），不报错。

**影响**: 平行调用中某个工具的参数会丢失，但不会报错，导致工具执行时参数缺失。

**建议**: 添加异常处理和日志记录：
```python
try:
    extra_params = json.loads(func.get("arguments", "{}"))
except (json.JSONDecodeError, TypeError) as e:
    logger.warning(f"[FC] 平行调用参数解析失败: {e}")
    extra_params = {}
```

---

### 问题 P-7: resolve_agent_config在找不到intent时抛出ValueError

**严重程度**: P2-中

**位置**: `agent_config.py:106`

**现象**: `resolve_agent_config` 在找不到对应intent时抛出 `ValueError`，而不是返回None或默认配置。这会导致整个请求失败。

**影响**: 如果CRSS返回了一个无效的intent_type（如通过别名映射），整个请求会崩溃。

**建议**: 考虑返回默认配置（system）而非抛出异常，或在调用方做好异常处理。

---

### 问题 P-8: ToolManager中tool_category为None时跳过分类工具加载

**严重程度**: P3-低

**位置**: `tool_manager.py:37`

**现象**: `if self.agent.tool_category:` — 当 `tool_category=None` 时，跳过分类工具加载。但meta工具始终加载。如果未来有Agent不指定category，将只有meta工具可用。

**影响**: 当前所有Agent都指定了category，所以不影响。但设计上存在隐患。

---

### 问题 P-9: _is_skip_safety() 可被config.yaml全局关闭安全检查

**严重程度**: P1-高

**位置**: `tool_safety_checker.py:24-30`

**现象**: `config.yaml` 中 `security.enabled: false` 时，所有安全检查被跳过（包括路径越权、代码注入检测）。

**影响**: 这是设计决策，但需要确保生产环境不会误配置。建议在生产环境配置中默认开启。

---

### 问题 P-10: candidates传递链路存在两次转换不一致

**严重程度**: P2-中

**位置**: `detect_intent.py:32` → `chat_stream_v2.py:48` → `run_sse_stream.py:44` → `agent_factory.py:44` → `universal_agent.py:30`

**现象**: 
1. `detect_intent()` 返回 candidates 为 ToolCategory.value 字符串列表
2. `chat_stream_v2()` 将 candidates 传给 `run_sse_stream()`
3. `run_sse_stream()` 将 candidates 传给 `AgentFactory.create()`
4. `AgentFactory.create()` 将 candidates 传给 `UniversalAgent.__init__()`
5. `UniversalAgent._build_candidates_hint()` 尝试用 candidates 调用 `resolve_agent_config(c)`

**问题**: 整个链路中 candidates 的值是 ToolCategory.value（如 `"fund_runtime"`），但 `resolve_agent_config` 期望的是 intent_type 名（如 `"system"`）。只有 `"file"` 能正确映射，其他都会 fallback 到 `"system"`。

---

## 八、问题汇总

| 编号 | 严重程度 | 问题描述 | 位置 |
|------|---------|---------|------|
| P-1 | P2 | CRSS_CONFIDENCE_THRESHOLD 导入但未使用 | crss_scorer.py:25 |
| P-2 | **P1** | candidates命名体系与intent_type不一致，导致候选意图提示错误 | detect_intent.py:32, universal_agent.py:86-97 |
| P-3 | P2 | DOCUMENT工具未设置安全级别，execute_sql可执行破坏性SQL | document_register.py:329-337 |
| P-4 | P3 | system Agent额外加载FILE工具但FILE Agent不加载SYSTEM工具 | agent_config.py:63-71 |
| P-5 | P3 | _TYPE_HANDLERS只注册action和answer | react_cycle.py:26-30 |
| P-6 | P2 | parallel tool_calls的JSON解析存在静默失败风险 | universal_agent.py:220-222 |
| P-7 | P2 | resolve_agent_config找不到intent时抛出ValueError | agent_config.py:106 |
| P-8 | P3 | ToolManager中tool_category为None时跳过分类工具加载 | tool_manager.py:37 |
| P-9 | P1 | config.yaml可全局关闭安全检查 | tool_safety_checker.py:24-30 |
| P-10 | P2 | candidates传递链路存在两次转换不一致 | detect_intent.py:32 → universal_agent.py:86-97 |

---

## 九、核心流程验证结论

### 9.1 意图分类 → 工具可用性匹配

**结论**: ✅ **基本正确**

- `txt/md/json` 在 FILE 意图中，文件操作请求正确路由到 FILE Agent
- `docx/pdf/csv/xlsx/pptx` 在 DOCUMENT 意图中，文档操作请求正确路由到 DOCUMENT Agent
- **风险**: 歧义输入（如"json文档"）可能路由到 DOCUMENT，但影响有限

### 9.2 Agent选择 → 工具加载匹配

**结论**: ✅ **正确**

- FILE Agent 加载 FILE 工具（11个）
- system Agent 加载 FUND_RUNTIME 工具 + FILE 工具（extra_categories）
- network Agent 加载 NET_PROCESS 工具
- document Agent 加载 DOC_CONTENT 工具
- desktop Agent 加载 SCREEN 工具

### 9.3 工具执行 → 安全检查匹配

**结论**: ⚠️ **基本正确，但有隐患**

- 四层安全体系完整
- 但 DOCUMENT 工具未设置安全级别（execute_sql 应为 DESTRUCTIVE）
- config.yaml 可全局关闭安全检查

### 9.4 候选意图提示

**结论**: ❌ **存在bug**

- candidates 使用 ToolCategory.value，但 resolve_agent_config 期望 intent_type 名
- 导致候选意图提示显示错误的分类名称

---

**分析完成时间**: 2026-06-12 10:32:37  
**分析人**: 小沈  
**下一步**: 根据问题严重程度优先修复 P-2 和 P-9
