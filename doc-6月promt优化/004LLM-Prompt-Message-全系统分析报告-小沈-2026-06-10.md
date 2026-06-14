# LLM Prompt / Message / Conversation History 全系统分析报告

**创建时间**: 2026-06-10 15:40:46
**版本**: v1.1
**分析人**: 小沈
**初始复查**: 5轮（v1.0）
**10原则复核**: 3轮×12问题（v1.1）
**项目**: OmniAgentAs-desk

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-10 15:40:46 | 小沈 | 初始版本：全系统分析LLM prompt/message/conversation history |
| v1.1 | 2026-06-11 06:38:39 | 小沈 | 新增10大原则复核：P1-P12逐一3轮复核+10大原则评估，更新优先级结论 |

---

## 一、系统总览 — Prompt/Message全链路架构 2026-06-10 15:40:46

### 1.1 全链路数据流图

```
用户输入 "帮我读取config.json"
    ↓
[前端] useSSE → sendMessage → POST /chat/stream
    ↓
[后端 chat_stream_v2.py] → Intent分类(CRSS) → intent_type="file"
    ↓
[AgentFactory.create("file")] → AgentConfig → FileOperationPrompts
    ↓
[Agent.__init__] → MessageBuilder 初始化
    ↓
[initialize_run_state] → 初始化 conversation_history:
    messages[0] = {"role": "system", "content": <完整System Prompt>}
    messages[1] = {"role": "user", "content": <Task Prompt含任务+时间+步骤>}
    ↓
┌─────────────────────────────────────────────────┐
│           ReAct 循环 (react_cycle.py)            │
│                                                   │
│  while step < max_steps:                         │
│    ① _call_llm()                                 │
│       ├─ trim_history() → 容量感知裁剪           │
│       ├─ prepare_messages_for_llm() → 合并       │
│       │   conversation_history + temp_history     │
│       ├─ 注入 _build_executed_tool_summary()     │
│       └─ llm_client.request_stream(messages)     │
│                                                   │
│    ② parse_llm_response(llm_response)            │
│       → type: action/answer/chunk/parse_error    │
│                                                   │
│    ③ handler(agent, parsed, ...)                 │
│       ├─ action → ActionHandler.handle()         │
│       │   ├─ 安全检查+HITL确认                   │
│       │   ├─ execute_tools()                     │
│       │   ├─ build_observation()                 │
│       │   ├─ message_builder.add_assistant()     │
│       │   └─ message_builder.add_observation()   │
│       ├─ answer → FinalStep + COMPLETED          │
│       └─ chunk → ChunkBuffer累积                 │
│                                                   │
│    ④ 检查 status → COMPLETED/FAILED → break      │
└─────────────────────────────────────────────────┘
    ↓
[前端] SSE事件流 → ExecutionStep[] → UI渲染
```

### 1.2 核心组件职责表

| 组件 | 文件位置 | 职责 |
|------|---------|------|
| **BasePrompts** | `prompts/base_prompt_template.py` | Prompt基类：OUTPUT_FORMAT + TOOL_CALL_RULES + 组装入口 |
| **FileOperationPrompts** | `prompts/file/file_prompts.py` | 文件操作意图的Prompt模板 |
| **SystemPrompts** | `prompts/system/system_prompts.py` | 系统信息意图的Prompt模板 |
| **NetworkPrompts** | `prompts/network/network_prompts.py` | 网络操作意图的Prompt模板 |
| **DocumentPrompts** | `prompts/document/document_prompts.py` | 文档操作意图的Prompt模板 |
| **DesktopPrompts** | `prompts/desktop/desktop_prompts.py` | 桌面操作意图的Prompt模板 |
| **SystemAdapter** | `prompts/middle/system_adapter.py` | 中间层：注入服务器OS/路径/命令信息 |
| **MessageBuilder** | `agent/message_builder.py` | conversation_history状态管理器 |
| **message_utils** | `agent/agent_utils/message_utils.py` | 无状态工具函数（构建/注入/Schema） |
| **UniversalAgent** | `agent/universal_agent.py` | 配置驱动的通用Agent |
| **BaseAIService** | `llm_core/llm_core.py` | LLM客户端：request/request_stream/chat |
| **parse_llm_response** | `agent/llm_response_parser/parse_llm_response.py` | LLM响应解析链 |
| **ActionHandler** | `agent/core_agent/handlers/action_handler.py` | action类型处理：安全检查→工具执行→observation构建 |
| **ChunkBuffer** | `agent/chunk_buffer.py` | chunk拼接/阈值检测/flush管理 |
| **observation_formatter** | `agent/observation_formatter.py` | 工具结果→LLM observation文本格式化 |
| **react_cycle** | `agent/core_agent/react_cycle.py` | ReAct循环核心：调度+类型分派 |
| **initialize_run_state** | `agent/core_agent/initialize_run_state.py` | run级别状态初始化 |

---

### 1.3 10大原则复核总览（2026-06-11 小沈追加）

| 问题 | 问题简述 | 3轮复核结论 | 违反原则 | 处理建议 |
|------|---------|------------|---------|---------|
| **P1** | 网络/文档/桌面硬编码工具描述 | 真实问题，但与动态生成各有优劣 | DRY, OCP | 改为build_tool_descriptions() + 保留特有示例 |
| **P2** | 部分缺少reasoning示例 | 低优先级，不影响功能 | — | 统一示例格式，不紧急 |
| **P3** | OUTPUT_FORMAT与解析逻辑差异 | **严重问题** | KISS, SLAP, 禁止backward compatibility | 移除旧格式支持，只保留tool_name格式 |
| **P4** | assistant保留策略[-10:] | 真实问题，FC模式需要保护 | SLAP | 优先保护含tool_calls的assistant消息 |
| **P5** | observation去重基于MD5 | **当前方案合理，不修改** | — | 当前方案符合KISS+YAGNI，语义去重过度设计 |
| **P6** | temp_history生命周期模糊 | **当前设计合理** | — | 明确文档说明，不改代码 |
| **P7** | FC降级丢失tool_calls上下文 | **严重问题** | SLAP | 降级前将FC配对转为Text格式 |
| **P8** | executed_summary注入为system | **非问题，API允许** | — | 不改（OpenAI允许system消息在任意位置） |
| **P9** | 解析器chunk降级过于宽松 | **当前行为正确** | — | 不修改（Text模式输出文本=chunk是正常流程） |
| **P10** | 参数类型转换丢失信息 | 低优先级 | SLAP | 保留原始类型，延迟到工具执行层字符串化 |
| **P11** | sessionStorage异步保存 | 前端问题 | — | 不修改（前端范围，本报告专注后端） |
| **P12** | timestamp处理分散 | 前端问题 | — | 不修改（前端范围，本报告专注后端） |

**结论速览**：
- ✅ **需要修复**：P1, P3, P4, P7（4个问题）
- ✅ **当前合理，不修改**：P5, P6, P8, P9（4个问题）
- ⚠️ **低优先级**：P2, P10（2个问题）
- 🔘 **前端问题**：P11, P12（2个问题）

---

## 二、Prompt构建体系详解 2026-06-10 15:40:46

### 2.1 System Prompt组装链（唯一入口：build_full_system_prompt）

**组装顺序**：

```
BasePrompts.build_full_system_prompt()
  ├─ ① get_system_prompt()           ← 子类实现(分类特有)
  │     ├─ SystemAdapter.generate_system_prompt()  ← 中间层：OS/路径/命令
  │     ├─ build_tool_descriptions()              ← 动态工具描述
  │     └─ Tool Call Examples(JSON示例)
  │
  ├─ ② OUTPUT_FORMAT                  ← 公共：JSON输出格式+退出规则
  │     包含: 情况1(调用工具) + 情况2(任务完成finish)
  │     字段要求: thought/reasoning/tool_name/tool_params
  │     禁止项: 多tool_name/XML标签/TOOL_CALL格式
  │
  ├─ ③ TOOL_CALL_RULES                ← 公共：工具调用规则
  │     强制: 确认意图后立即调用工具
  │     禁止: 反复讨论不调用/仅文字回复不调用工具
  │
  ├─ ④ get_safety_reminder()          ← 子类覆盖(分类特有安全提醒)
  │
  ├─ ⑤ get_rollback_instructions()    ← 公共：回滚说明
  │
  └─ ⑥ 避免重复规则                   ← 公共：同一命令/URL不重复执行

运行时由 UniversalAgent._get_system_prompt() 追加:
  ├─ ⑦ _build_candidates_hint()       ← 动态：候选意图提示
  └─ ⑧ _build_cross_tool_hint()       ← 动态：跨分类工具提示
```

### 2.2 Task Prompt构建链（get_task_prompt）

**标准格式**：

```
Task: {用户的原始任务}
Current time: {当前系统时间}
请完成此{领域名称}任务,按以下步骤:
{领域步骤}
{领域额外备注}
```

**各意图的领域步骤差异**：

| 意图 | 领域名称 | 步骤 |
|------|---------|------|
| file | 文件管理 | 1.分析操作→2.使用工具→3.中文总结 |
| system | 系统信息 | 1.分析系统信息需求→2.使用系统工具→3.中文总结 |
| network | 网络 | 1.分析网络操作→2.使用正确参数→3.中文报告 |
| document | 文檔处理 | 1.分析文档操作→2.使用文档工具→3.中文总结 |
| desktop | 桌面操作 | 1.识别目标窗口→2.使用桌面工具→3.中文确认 |

### 2.3 各意图Prompt特点分析

#### 2.3.1 FileOperationPrompts — 最完善的模板

- **工具数量**: 11个（read_file, write_text_file, list_directory, search_files, grep_file_content, edit_file, rename_file, file_operation, archive_tool, read_media_file, data_file_format）
- **特色**: 互斥参数规则(P17)、write_text_file的text参数约束
- **安全提醒**: 文件覆盖警告 + text参数内容约束

#### 2.3.2 SystemPrompts — 动态生成

- **工具来源**: 从ToolRegistry动态获取FUND_RUNTIME分类工具
- **示例**: 使用`_build_examples(6)`从模板池动态生成
- **特点**: 不含命令格式注入(避免LLM幻觉调shell)

#### 2.3.3 NetworkPrompts — 硬编码描述

- **工具数量**: 5个（http_request, download_file, fetch_webpage, search_web, network_diagnose）
- **特色**: 每个工具都有详细When to use和Examples
- **注意**: 不注入命令格式(避免幻觉)

#### 2.3.4 DocumentPrompts — 分组展示

- **工具数量**: 9个（read/write/convert_document, analyze/filter_data, generate_chart, query/execute_sql, get_db_schema）
- **分组**: Document Read/Write / Data Analysis / Database Tools

#### 2.3.5 DesktopPrompts — 动作丰富

- **工具数量**: 9个（window_info, window_control, mouse_control, keyboard_control, screen_capture, clipboard_control, screen_record, ocr, send_notification）
- **分组**: Window Management / Mouse & Keyboard / Screen & Clipboard

### 2.4 Prompt中间层 — SystemAdapter

**职责**: 根据服务器OS动态生成系统自适应内容

**注入内容**:
1. 当前系统: Windows/Linux/macOS
2. 路径格式: C:\... 或 /home/...
3. 命令格式: dir/ls 等(仅shell意图注入)
4. 路径规则: 必须绝对路径/禁止~/

**include_commands参数控制**:
- `True`: 仅ShellAgent使用，注入命令格式
- `False`: 其他Agent使用，避免LLM看到ipconfig/curl后幻觉调execute_shell_command

---

## 三、Conversation History管理详解 2026-06-10 15:40:46

### 3.1 MessageBuilder核心数据结构

```python
class MessageBuilder:
    conversation_history: List[Dict]  # 正式对话历史
    temp_history: List[Dict]          # 临时历史(chunk累积)
    MAX_CONTEXT_CHARS: int            # 最大字符容量(150000)
```

### 3.2 消息生命周期

```
[initialize_run_state]
  conversation_history = [
    {"role": "system", "content": <完整System Prompt>},    ← messages[0]
    {"role": "user", "content": <Task Prompt>}              ← messages[1]
  ]

[ReAct循环中逐步追加]

  ① LLM返回action → action_handler.build_observation():
     message_builder.add_assistant(llm_response)     ← 追加assistant消息

  ② 工具执行完成 → action_handler._update_message_builder():
     message_builder.add_observation(obs_text)       ← 追加observation消息

  ③ add_observation内部:
     a. _prepare_observation_text() → 截断+归一化
     b. _append_observation() → 根据FC协议选择注入方式:
        - 有fc_context(Tools策略): role=assistant(tool_calls) + role=tool(tool_call_id)
        - 无fc_context(Text策略): role=user + content含[Tool Result]
     c. trim_history() → 容量感知裁剪

  ④ prepare_messages_for_llm():
     messages = conversation_history + temp_history

  ⑤ 注入 _build_executed_tool_summary():
     messages.append({"role": "system", "content": "【已执行工具(勿重复)】..."})
```

### 3.3 Observation消息注入方式（方案G）

**2026-06-09 小沈设计的方案G — 两种FC协议并存**:

```
┌─────────────────────────────────────────────────────┐
│  Text策略(无FC协议):                                  │
│  role=user, content="[Tool Result]\n{obs_text}"     │
│                                                       │
│  Tools策略(有FC协议):                                 │
│  ① role=assistant, tool_calls=[{id,name,params}]    │
│  ② role=tool, tool_call_id=id, content=obs_text     │
└─────────────────────────────────────────────────────┘
```

**判断逻辑**: `_is_observation_role(msg)` 检查两种形式:
1. `msg["role"] == "tool"` → True
2. `msg["role"] == "user" and "[Tool Result]" in content` → True

### 3.4 容量感知裁剪（trim_history）

**触发条件**: `total_chars >= MAX_CONTEXT_CHARS * 0.8` (120000字符)

**裁剪策略**:
```
1. 分类消息: system_msgs / obs_list / assistant_msgs
2. 预算: MAX_CONTEXT_CHARS * 0.7 (105000字符)
3. 裁剪:
   a. 去重observation(fingerprint MD5)
   b. 保留最近10条assistant消息
   c. 保留最近30条observation消息
   d. 从最旧开始删除observation直到满足预算
4. FC配对保护: _trim_fc_pairs()确保role:tool与assistant(tool_calls)严格配对
5. 重组验证: 确保至少有2条消息
```

### 3.5 Observation截断策略

**预算计算**（_get_observation_budget）:
```python
budget = OBSERVATION_BUDGET_MIN + OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
# 首次: 20000 + 10000*5 = 70000 → capped at 50000
# 第2次: 20000 + 10000*4 = 60000 → capped at 50000
# 第3次: 20000 + 10000*3 = 50000
# 第4次: 20000 + 10000*2 = 40000
# 第5次: 20000 + 10000*1 = 30000
# 第6次+: 20000 (OBSERVATION_BUDGET_MIN)
```

**设计意图**: 随着LLM调用次数增加，逐步减少observation占用的字符预算，防止历史累积超出context window。

### 3.6 temp_history管理

**用途**: LLM流式输出时的chunk累积缓冲

**容量保护**: `_cap_temp_history()` — 总字符超50000时从最旧截断

**flush时机**: `flush_temp_to_history()` — 将chunk_buffer内容刷入正式conversation_history

---

## 四、LLM调用链详解 2026-06-10 15:40:46

### 4.1 双模式调用架构

```
UniversalAgent._call_llm()
  ├─ _get_openai_tools() → 获取OpenAI格式工具定义(TTL缓存300s)
  │
  ├─ if openai_tools: → FC模式
  │   └─ _call_llm_fc_stream(messages, openai_tools)
  │       mode="tools", tools=openai_tools, tool_choice="auto"
  │       → 聚合跨chunk的tool_calls
  │       → 解析为JSON内容注入
  │
  └─ else: → Text模式
      └─ _call_llm_text_stream(messages)
          mode="text"
          → 直接输出文本
```

### 4.2 BaseAIService流式调用

```python
async def request_stream(messages, mode, tools, tool_choice):
    async for data_str in self._llm_sdk.request_stream(...):
        # 检查取消/暂停状态
        if await self._check_task_cancelled_or_paused():
            yield create_cancelled_chunk()
            return
        
        # 跨chunk聚合tool_calls
        tc_data = self._extract_tool_calls(data_str)
        for idx, entry in tc_data.items():
            tool_call_accumulator[idx] += entry
        
        # 解析SSE data
        chunk = self._parse_sse_data(data_str)
        yield chunk
    
    # 流结束后，聚合tool_calls转JSON注入
    if tool_call_accumulator:
        for idx in sorted(tool_call_accumulator):
            yield StreamChunk(content=action_json, ...)
```

### 4.3 已执行工具汇总注入

**目的**: 防止LLM重复调用已成功的工具

**格式**:
```
【已执行工具(勿重复)】read_file→success(/config.json); search_files→success(D:/project)
注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!
```

**构建逻辑**: `_build_executed_tool_summary()` — 只取最后8条成功的工具调用

---

## 五、LLM响应解析链详解 2026-06-10 15:40:46

### 5.1 解析器链（_HANDLERS顺序）

```
parse_llm_response(output)
  ├─ _handle_dict_input      → dict直接转换
  ├─ _handle_list_input      → list处理(取最后元素)
  ├─ _handle_json_array_string → JSON数组字符串
  ├─ _handle_empty_input     → 空输入返回parse_error
  ├─ _handle_standard_json   → 标准JSON提取
  └─ _handle_mixed_text_json → 混合文本JSON
       ├─ _extract_json_block_simple → 提取JSON块+前缀文本
       ├─ tool_name=="finish" → _handle_finish_tool → type="answer"
       ├─ tool_name存在 → _build_action_result → type="action"
       └─ content/reasoning存在 → _handle_implicit_content → type="implicit"
```

### 5.2 结果类型映射

| type | 触发条件 | 后续处理 |
|------|---------|---------|
| `action` | JSON含tool_name且非finish | ActionHandler → 工具执行 |
| `answer` | tool_name=="finish" | FinalStep → COMPLETED |
| `implicit` | JSON含content/reasoning无tool_name | FinalStep → COMPLETED |
| `chunk` | 非JSON文本或提取失败 | ChunkBuffer累积 |
| `parse_error` | 解析链耗尽/空输入 | 工具提醒注入 |

### 5.3 工具参数处理链

```
_process_tool_params(tool_params, tool_name, output)
  ├─ _normalize_tool_params_content → 内容归一化(bool/int/list/dict→str)
  └─ _filter_tool_params → 过滤非参数字段 + 驼峰→蛇形映射
       非参数字段: reasoning/thought/type/tool_name/action/...
       驼峰映射: filePath→file_path, dirPath→dir_path, ...
```

### 5.4 工具提醒注入机制

**触发条件**: `parsed_type == "chunk" and not _has_tool_call(agent)`

**注入内容**:
```
【系统提示·工具调用提醒】
你刚才的回复没有调用任何工具。用户请求需要实际操作才能完成，
你必须使用工具来执行。
请重新输出JSON格式，包含 tool_name 和 tool_params。
示例: {"thought": "分析", "reasoning": "理由", "tool_name": "write_text_file", "tool_params": {...}}
如果不需要工具（用户只是闲聊），请用 tool_name: finish 结束。
```

**注入位置**: 直接append到`conversation_history`，下次LLM调用时自然包含

---

## 六、前端SSE消息处理 2026-06-10 15:40:46

### 6.1 执行步骤类型

| type | 含义 | 前端处理 |
|------|------|---------|
| `start` | 会话开始 | 显示AI思考提示+模型信息 |
| `thought` | LLM思考 | 步骤列表显示思考过程 |
| `chunk` | 流式内容片段 | 累积到currentResponse，is_reasoning区分思考/答案 |
| `action_tool` | 工具调用 | 步骤列表显示工具名+参数 |
| `observation` | 工具结果 | 步骤列表显示执行结果 |
| `final` | 最终回答 | 完成回复，触发onComplete |
| `error` | 错误 | 显示错误信息 |
| `incident` | 中断(HITL) | 显示授权确认对话框 |

### 6.2 chunk保存规则（关键）

**核心原则**: chunk保存当前小块内容，不保存累积

- `step.content = chunkContent` ← 只存当前块
- `responseBufferRef.current += chunkContent` ← 累积用于实时显示
- `final` 事件保存完整response到message.content

**历史教训**: 如果chunk保存累积内容 → 导出JSON每个chunk重复 → 数据错误

---

## 七、不合理之处分析与建议 2026-06-10 15:40:46

### 7.1 Prompt层面的不合理

#### 问题 P1: 网络/文档/桌面Prompt硬编码工具描述

**现状**: `network_prompts.py`、`document_prompts.py`、`desktop_prompts.py` 直接在Python字符串中硬编码工具描述和示例。

**问题**: 
- 工具增删改时必须手动更新Prompt模板
- 与`file_prompts.py`和`system_prompts.py`使用`build_tool_descriptions()`动态生成不一致
- 容易出现Prompt与实际工具定义不匹配

**建议**: 统一使用`BasePrompts.build_tool_descriptions()`动态生成，保持一致性。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：3个文件硬编码vs1个文件动态生成→不一致 | 真实问题，但build_tool_descriptions()丢失"使用场景"和"示例"信息 |
| 第2轮 | 10原则：DRY❌(工具描述重复), OCP❌(增删改需改2处), YAGNI✅(工具描述极少变化) | 动态生成更符合OCP，但信息量下降是关键权衡 |
| 第3轮 | 边界/副作用：动态生成依赖ToolRegistry→初始化失败时空描述；硬编码版本无此风险 | 硬编码≈无外部依赖，稳定性更高 |

**最终结论**：
- ✅ **采纳建议，但方案修正为**：使用`build_tool_descriptions()`生成基础描述结构（name+desc+params），保留各模板特有"使用场景/分组/示例"作为硬编码补充
- **理由**：DRY原则要求消除重复，但纯粹动态生成会丢失信息量；混合方案兼顾OCP和信息丰富度

#### 问题 P2: 部分Prompt模板缺少reasoning字段示例

**现状**: `file_prompts.py`已升级添加reasoning字段示例（2026-04-14小沈），但`network_prompts.py`、`document_prompts.py`、`desktop_prompts.py`的示例中reasoning字段过于简略。

**问题**: LLM可能不理解reasoning字段的要求，输出空或过短的reasoning。

**建议**: 统一所有意图模板的示例格式，确保reasoning字段有实质内容。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：file_prompts有完整reasoning示例，其他3个文件过于简略 | 影响Prompt质量，不影响功能正确性 |
| 第2轮 | 10原则：KISS✅(不同模板可自有风格), YAGNI⚠️(reasoning字段是否有实质影响待验证) | LLM即使没看明白示例也会输出reasoning（由system prompt总体要求驱动） |
| 第3轮 | 边界/副作用：示例只是参考，LLM实际行为由OUTPUT_FORMAT+TOOL_CALL_RULES约束 | 影响极小，属于Prompt细节优化 |

**最终结论**：
- ⚠️ **低优先级，暂不修改**
- **理由**：纯Prompt质量优化，不影响功能正确性；当系统决定统一调整Prompt时一并处理

#### 问题 P3: OUTPUT_FORMAT与实际解析逻辑存在语义差异

**现状**: 
- OUTPUT_FORMAT要求返回`tool_name`+`tool_params`的JSON
- 但parse_llm_response还支持旧格式`action`+`action_input`和FC格式`name`+`arguments`

**问题**: Prompt告诉LLM一种格式，但解析器支持多种格式，导致LLM可能输出不规范的格式也能通过解析。

**建议**: 要么在Prompt中说明多种格式都接受，要么在解析器中限制只接受新格式。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：OUTPUT_FORMAT只教`tool_name`+`tool_params`，但parser实际支持3种格式(new/FC/old) | **真正的语义不一致问题**，LLM可输出不规范格式仍被解析 |
| 第2轮 | 10原则：KISS❌(一个格式教法三个解析法), SLAP❌(Prompt与解析器约定不同层), 禁止backward compatibility✅(应移除旧格式支持) | **禁止向后兼容原则**要求移除old/FC格式支持 |
| 第3轮 | 边界/副作用：移除old/FC格式后，旧测试数据需更新；当前没有agent使用旧格式生成新消息 | **安全移除**，无生产影响 |

**最终结论**：
- ✅ **需要修复** — 根据**禁止backward compatibility原则**，在解析器中移除`action`+`action_input`(old)和`name`+`arguments`(FC)格式支持，只保留`tool_name`+`tool_params`格式
- **修改范围**：`llm_response_parser/_result_builders.py`中删除_handle_old_format和_handle_fc_format分支
- **测试影响**：更新相关测试用例

### 7.2 Conversation History管理的不合理

#### 问题 P4: trim_history中assistant消息保留策略过于简单

**现状**: `assistant_msgs = assistant_msgs[-10:]` 固定保留最后10条assistant消息。

**问题**: 
- 不区分assistant消息的类型（thought/action/final）
- 可能丢失重要的tool_call历史（assistant消息中包含tool_calls字段）
- FC模式下assistant消息可能包含tool_calls，裁剪后可能导致FC配对断裂

**建议**: 保留策略应考虑FC配对完整性，优先保留有tool_calls的assistant消息。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：`assistant_msgs[-10:]`确实简单粗暴；当前已有的`_trim_fc_pairs`仅保护observation侧，未保护assistant侧 | FC模式下assistant消息含tool_calls字段，截断后对应role:tool变为孤儿 |
| 第2轮 | 10原则：KISS✅([-10:]简单直接), SLAP❌(FC模式下assistant+tool_calls配对应在同一裁剪策略中保护) | 需要将assistant(tool_calls)纳入FC配对保护范围 |
| 第3轮 | 边界/副作用：极端情况assistant全部含tool_calls→保留全部→裁剪失效 | 限制保留含tool_calls的assistant不超过最近10条 |

**最终结论**：
- ✅ **需要修复** — 修改trim_history逻辑：对assistant消息按"含tool_calls优先"排序，确保FC配对在裁剪后仍完整
- **修改范围**：`message_builder.py`中trim_history()调整assistant_msgs筛选逻辑

#### 问题 P5: observation去重基于MD5指纹不够精确

**现状**: `_dedup_by_fingerprint` 使用`md5(content.encode())[:16]`作为指纹。

**问题**:
- 相同内容的observation可能有不同语义（如不同工具返回相同结果）
- FC协议消息跳过去重（`role=tool`），但Text策略的重复observation不会被去重

**建议**: 考虑基于tool_name+tool_params的语义去重，或保留时间戳信息辅助判断。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：MD5(content)去重针对observation文本（工具执行结果），"相同内容不同语义"的说法牵强 | 同工具同内容=重复信息，去重合理；FC协议的role:tool已跳过去重 |
| 第2轮 | 10原则：KISS✅(MD5简单高效), YAGNI❌(语义去重是过度设计，收益极低) | **建议方案违反YAGNI** — 工具返回相同结果就是重复，无需语义判断 |
| 第3轮 | 边界/副作用：MD5碰撞概率2^(-64)，可忽略；空内容时所有空observation被去重→合理 | 当前方案完全满足需求 |

**最终结论**：
- 🚫 **不修改** — 当前`_dedup_by_fingerprint`方案符合KISS原则
- **理由**：原建议的"语义去重"违反YAGNI，收益极低(0.01%场景)且复杂度大增；MD5去重已满足需求

#### 问题 P6: temp_history与conversation_history的分离不够清晰

**现状**: 
- `temp_history` 用于LLM流式输出时的chunk累积
- `flush_temp_to_history()` 将temp_history内容刷入conversation_history
- 但`_cap_temp_history()`在`prepare_messages_for_llm()`中执行，可能在flush之前就截断

**问题**: temp_history的生命周期管理不够明确，可能出现数据丢失。

**建议**: 明确temp_history的语义：是"等待确认的assistant消息"还是"流式输出缓冲"，统一管理逻辑。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：temp_history=流式chunk缓冲，conversation_history=正式历史，职责分离清晰 | 当前语义已明确：temp=临时缓冲，conv=正式消息 |
| 第2轮 | 10原则：KISS✅(temp/conv分离直白), SRP✅(各管各的), SLAP✅(_cap_temp_history在prepare时执行合理) | **设计合理，无需修改** |
| 第3轮 | 边界/副作用：极端长流式输出>50000 chars→_cap_temp_history从最旧chunk清理→最新chunk保留 | 容量保护行为正确，"数据丢失"属于正常保护行为 |

**最终结论**：
- 🚫 **不修改** — 当前设计符合KISS/SRP/SLAP原则
- **改进建议**：在代码注释中明确说明`temp_history=流式输出缓冲`语义，避免未来开发者困惑

### 7.3 LLM调用链的不合理

#### 问题 P7: FC模式降级到Text模式时丢失tool_calls上下文

**现状**: `_call_llm_fc_stream`中，当`stream_error`时降级到`_call_llm_text_nostream`。

**问题**: 
- FC模式的messages包含assistant(tool_calls)+tool(tool_call_id)配对
- 降级到Text模式后，这些FC协议消息无法被正确处理
- LLM可能困惑于消息格式不一致

**建议**: 降级时需要清理FC协议消息，或在Text模式下重新构建消息列表。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：FC降级到Text时，messages中残留FC配对(assistant+tool_calls, role:tool) | Text模式LLM看不到FC格式，FC配对变成"不明角色"消息，可能混淆 |
| 第2轮 | 10原则：SRP✅(FC/Text模式各司其职), SLAP❌(降级路径没有清理模式相关状态) | 降级是跨模式状态转换，应在转换时清理旧模式残留 |
| 第3轮 | 边界/副作用：将FC配对转为role:user+[Tool Result]格式后→Text模式LLM正常理解 | 转换是安全的，只影响消息格式不影响语义 |

**最终结论**：
- ✅ **需要修复** — 在`_call_llm_fc_stream`降级到`_call_llm_text_stream`前，将FC配对消息统一转为Text格式(role:user+[Tool Result])
- **修改范围**：`universal_agent.py`中_call_llm_fc_stream降级路径，增加消息格式转换

#### 问题 P8: _build_executed_tool_summary注入为system角色

**现状**: `messages.append({"role": "system", "content": executed_summary})`

**问题**: 
- 在消息列表中间插入system消息不符合OpenAI API规范
- 可能导致LLM误解消息角色

**建议**: 将已执行工具信息追加到System Prompt末尾，或作为user消息注入。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：`messages.append({"role":"system","content":executed_summary})` | 验证OpenAI API：system消息允许在任何位置（非违规），只是语义上"角色定义"vs"执行摘要"不匹配 |
| 第2轮 | 10原则：KISS✅(直接append最简单), SRP⚠️(用system角色承载"工具摘要"语义错位但不影响功能) | **不是违反API规范**，只是语义上不够优雅 |
| 第3轮 | 边界/副作用：改为追加到System Prompt末尾→需要重建消息或修改system prompt字符串 | 修改成本>收益，当前方案不影响功能正确性 |

**最终结论**：
- 🚫 **不修改** — 当前方案不影响功能正确性
- **理由**：OpenAI等主流API允许system消息在任意位置；用system角色承载辅助信息虽语义不纯粹但实践中广泛使用；改到user角色或追加到system prompt末尾的收益极低

### 7.4 响应解析链的不合理

#### 问题 P9: 解析器链的降级策略过于宽松

**现状**: `_handle_mixed_text_json`中，如果提取不到JSON，返回`_build_chunk_result(output)`。

**问题**: 
- 非JSON文本被当作chunk处理，可能累积成无意义的内容
- chunk_handler会将chunk内容追加到chunk_buffer，最终可能被提升为implicit

**建议**: 对于明显不是工具调用的文本（如纯英文段落），应直接作为answer处理而非chunk。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：Text模式LLM输出自然语言→无法提取JSON→chunk是正常流程 | **不是降级问题**，而是Text模式的常规路径 | 
| 第2轮 | 10原则：KISS✅(Text→chunk累积→implicit, 流程清晰), SLAP✅(chunk=流式片段, 语义正确) | 当前行为完全符合chunk的语义定义 |
| 第3轮 | 边界/副作用：LLM输出纯文本→chunk累积→ChunkBuffer触发阈值→flush为implicit→最终返回 | 整个链条正确：chunk→implicit是正常Text模式输出路径 |

**最终结论**：
- 🚫 **不修改** — 当前行为是Text模式的正确路径
- **理由**：chunk的语义就是"流式内容片段"，非JSON文本就是LLM的自然语言输出，经ChunkBuffer累积后产生implicit响应；如果提前判断为answer，会打乱流式输出的渐进式渲染

#### 问题 P10: _normalize_tool_params_content的类型转换可能丢失信息

**现状**: 
```python
if isinstance(field_value, (list, dict)):
    normalized[field_name] = json.dumps(field_value, ensure_ascii=False)
```

**问题**: 
- 将list/dict转为JSON字符串，后续工具可能需要原始类型
- 转换后再经过`_filter_tool_params`可能进一步丢失信息

**建议**: 保留原始类型，仅在最终工具调用时进行序列化。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：`json.dumps(list/dict)`→字符串→下游工具收到字符串需要再解析 | 如果工具需要接收number/bool，当前的确发生类型丢失 |
| 第2轮 | 10原则：KISS✅(json.dumps简单), SLAP❌(类型转换发生在解析层但影响执行层) | 参数类型转换应该在离调用点最近的地方做 |
| 第3轮 | 边界/副作用：实际观察所有工具接收的参数→大多数接受字符串参数（内部二次解析），仅少数需要原始类型 | 影响范围小，但确实存在隐患 |

**最终结论**：
- ⚠️ **低优先级，建议优化** — 将类型转换从解析层延迟到`tool_executor.execute_tool()`层
- **理由**：遵循SLAP原则，解析层保持原始类型，字符串化在工具执行层；实际影响小但设计上更清晰

### 7.5 前端SSE处理的不合理

#### 问题 P11: sessionStorage备份可能导致数据不一致

**现状**: `saveStepsToStorage`在setTimeout(0)中异步保存，可能在步骤更新后才执行。

**问题**: 
- 页面刷新时从sessionStorage恢复的steps可能缺少最后几个步骤
- 多个步骤快速到达时，保存可能只保存了中间状态

**建议**: 使用防抖(debounce)机制，确保保存的是最终状态。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：setTimeout(0)异步保存→快步骤只保存中间态→刷新丢失最后步骤 | 真实的前端数据一致性问题 |
| 第2轮 | 10原则：本报告专注后端分析，前端问题仅做记录 | 不在后端优化范围内 |
| 第3轮 | 影响评估：低概率场景（用户恰好刷新在渲染间隙），不影响核心功能 | 低风险度 |

**最终结论**：
- 🔘 **前端问题，本报告不做修改**
- **理由**: 前端范围，本报告专注后端Prompt/Message/History分析

#### 问题 P12: 前端timestamp处理逻辑分散

**现状**: `processSSEData`中有复杂的timestamp类型转换逻辑：
```typescript
if (typeof rawData.timestamp === 'number') {
    timestampValue = rawData.timestamp;
} else if (typeof rawData.timestamp === 'string') {
    const parsed = Date.parse(rawData.timestamp);
    timestampValue = isNaN(parsed) ? Date.now() : parsed;
}
```

**问题**: 
- 后端应统一输出格式（数字或ISO字符串）
- 前端的fallback到`Date.now()`掩盖了后端问题

**建议**: 后端统一使用ISO字符串格式，前端简化解析逻辑。

**10大原则评估（2026-06-11 小沈复核3轮）**:

| 轮次 | 复核内容 | 结论 |
|------|---------|------|
| 第1轮 | 正确性：前端有复杂的类型判断(number→Date, string→parse, Date.now() fallback) | 后端格式统一可大幅简化前端 |
| 第2轮 | 10原则：本报告专注后端分析，前端问题仅做记录 | 不在后端优化范围内 |
| 第3轮 | 影响评估：不影响功能正确性，只是代码质量优化 | 低风险度 |

**最终结论**：
- 🔘 **前端问题，本报告不做修改**
- **理由**: 前端范围，本报告专注后端Prompt/Message/History分析

---

## 八、数据流完整性验证 2026-06-10 15:40:46

### 8.1 端到端数据流验证

| 阶段 | 输入 | 输出 | 验证 |
|------|------|------|------|
| Intent分类 | 用户消息 | intent_type | CRSS评分→file/system/network/document/desktop |
| Agent创建 | intent_type | Agent实例 | AgentFactory→config→prompt_class→agent_class |
| System Prompt | AgentConfig | 完整System Prompt | build_full_system_prompt()组装 |
| Task Prompt | task+时间 | Task Prompt | get_task_prompt()生成 |
| History初始化 | sys+task | conversation_history[0,1] | init_history() |
| LLM调用 | messages | LLM响应 | request_stream()流式 |
| 响应解析 | LLM响应 | parsed dict | parse_llm_response()链式 |
| 工具执行 | tool_name+params | 执行结果 | execute_tool_with_retry() |
| Observation构建 | 执行结果 | observation文本 | format_llm_observation() |
| History追加 | obs文本 | conversation_history更新 | add_observation() |
| History裁剪 | 完整history | 裁剪后history | trim_history() |
| 下次LLM调用 | 裁剪后history+tool_summary | LLM响应 | prepare_messages_for_llm() |

### 8.2 关键数据结构验证

| 结构 | 字段 | 来源 | 用途 |
|------|------|------|------|
| conversation_history[0] | role=system | build_full_system_prompt() | LLM角色定义+规则 |
| conversation_history[1] | role=user | get_task_prompt() | 任务描述+时间 |
| conversation_history[n] | role=assistant | add_assistant() | LLM响应/工具调用 |
| conversation_history[n] | role=user+[Tool Result] | _append_observation(Text策略) | 工具执行结果 |
| conversation_history[n] | role=tool+tool_call_id | _append_observation(FC策略) | 工具执行结果 |
| messages临时 | role=system | _build_executed_tool_summary() | 已执行工具汇总 |

---

## 九、总结与建议优先级 2026-06-10 15:40:46

### 9.1 按优先级排序的问题清单（10大原则复核后 2026-06-11 小沈更新）

| 优先级 | 问题 | 10原则复盘结论 | 处理建议 | 状态 |
|--------|------|---------------|---------|------|
| **P0** | P3: OUTPUT_FORMAT与解析逻辑语义差异 | 违反KISS+SLAP+禁止backward compatibility | 移除旧格式(action+action_input, name+arguments)支持，只保留tool_name+tool_params | ✅ 需修复 |
| **P1** | P7: FC降级丢失tool_calls上下文 | 违反SLAP(降级路径未清理旧模式状态) | 降级前将FC配对(assistant+tool_calls, role:tool)统一转为Text格式(role:user+[Tool Result]) | ✅ 需修复 |
| **P1** | P4: assistant消息保留策略[-10:] | 违反SLAP(FC模式下assistant含tool_calls应受保护) | 修改trim_history：含tool_calls的assistant消息优先保留 | ✅ 需修复 |
| **P1** | P1: 硬编码工具描述 | 违反DRY+OCP(工具描述在ToolRegistry和Prompt中重复) | 使用build_tool_descriptions()做基础结构，保留各模板特有场景/示例 | ✅ 需修复 |
| **P3** | P10: 参数类型转换丢失信息 | 违反SLAP(类型转换在解析层但影响执行层) | 延迟到tool_executor.execute_tool()层字符串化 | ⚠️ 建议优化 |
| **P3** | P2: 缺少reasoning示例 | 纯Prompt优化，不影响功能 | 统一格式化但不紧急 | ⚠️ 可暂缓 |
| **—** | P5: observation去重基于MD5 | 符合KISS+YAGNI(当前方案合理) | **不修改**，原语义去重建议违反YAGNI | 🚫 不修 |
| **—** | P6: temp_history生命周期 | 符合KISS+SRP+SLAP(当前设计合理) | **不修改**，仅建议加注释 | 🚫 不修 |
| **—** | P8: tool_summary注入system角色 | OpenAI API允许system消息在任意位置 | **不修改**，当前方案不影响功能 | 🚫 不修 |
| **—** | P9: 解析器chunk降级宽松 | 符合KISS+SLAP(Text→chunk是正常路径) | **不修改**，当前行为正确 | 🚫 不修 |
| **—** | P11: sessionStorage异步保存 | 前端问题 | 由前端专案处理 | 🔘 前端 |
| **—** | P12: timestamp处理分散 | 前端问题 | 由前端专案处理 | 🔘 前端 |

### 9.2 10原则复核关键发现

1. **P5/P6/P8/P9被原文档判定为问题，但10原则复核后判定为"当前合理，不修改"**
   - P5: MD5去重足够，语义去重是YAGNI过度设计
   - P6: temp_history/conv_history分离清晰，设计合理
   - P8: OpenAI API允许system消息任意位置，非规范问题
   - P9: chunk降级是Text模式正常行为，非降级问题

2. **P3的修复优先级最高** — 违反禁止backward compatibility原则，应移除旧格式支持

3. **P7的修复范围最关键** — FC降级是真实的生产故障路径（网络波动时触发）

### 9.2 设计亮点

1. **Prompt中间层(SystemAdapter)**: 根据OS动态生成系统信息，避免LLM幻觉调错误命令
2. **方案G双FC协议**: 兼容Text策略和Tools策略，适应不同LLM提供商
3. **observation预算衰减**: 随调用次数增加逐步减少observation占用，防止context overflow
4. **已执行工具汇总**: 防止LLM重复调用已成功的工具
5. **工具提醒注入**: FC模式下LLM返回纯文本时自动注入工具调用提醒
6. **FC配对保护裁剪**: trim_history时确保assistant(tool_calls)与role:tool严格配对

---

**报告完成时间**: 2026-06-10 15:40:46
**报告更新时间**: 2026-06-11 06:38:39（v1.1 10大原则复核）
**执行人**: 小沈
**初始复查轮数**: 5轮（v1.0）
**10原则复核轮数**: 3轮×12问题（v1.1）
**涉及文件数**: 30+个核心文件
