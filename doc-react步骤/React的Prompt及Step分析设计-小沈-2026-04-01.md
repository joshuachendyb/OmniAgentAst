# React的Prompt及Step分析设计

**创建时间**: 2026-03-29 05:08:14 **版本**: v1.21 **编写人**: 小沈 **更新时间**: 2026-04-01

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.20 | 2026-03-29 21:28:00 | 小沈 | 初始版本 |
| v1.21 | 2026-04-01 | 小沈 | 重新编写章节号，从第一章开始 |

---

## 一、React的Type字段完整分析

### 1.1 网络深度学习成果：Type字段的生成时机（LLM调用前还是调用后）

#### 1.1.1 重要概念区分：messages数组 vs type字段

> ⚠️ **必须首先明确的概念**：type字段不是给LLM的prompt内容，而是前端显示步骤类型的数据。

| 概念 | 用途 | 内容 | 数据流向 |
|------|------|------|---------|
| **messages数组** | 给LLM的prompt（输入） | system, user(任务), assistant(Thought), user(Observation) | 程序 → LLM |
| **type字段** | 前端显示的步骤类型（输出） | thought, action_tool, observation, chunk, final, start, error | 程序 → 前端UI |

**关键区别**：

| 维度 | messages数组 | type字段 |
|------|-------------|----------|
| **作用** | 让LLM理解对话上下文 | 让前端显示执行步骤 |
| **内容来源** | 程序组装后发给LLM | LLM返回或工具执行后填充 |
| **包含Observation** | ✅ user(Observation) - 注入给LLM | ✅ observation - 显示给用户 |
| **两者的Observation** | 是**同一个数据**的不同视角 | - |

**举例说明**：

```
【给LLM的messages数组】                    【前端显示的type字段】
system: "你是一个助手..."                   start: {model: "gpt-4", ...}
user: "帮我整理桌面文件"                    thought: {content: "我需要...", action_tool: "list_directory"}
assistant: "我需要查看文件"                 
user: "Observation: [文档, 图片]"           observation: {content: "看到3个文件夹", obs_summary: "..."}
                                           chunk: {content: "现在我看到..."}
assistant: "我来创建分类文件夹"              
user: "Observation: success"                action_tool: {tool_name: "create_directory", ...}
                                           final: {content: "已完成整理"}
```

**核心理解**：
- messages是程序组装好发给LLM的prompt
- type字段是程序解析LLM返回后，生成给前端显示的数据
- 两者的"observation"是**同一个执行结果**的两种用途：注入给LLM vs 显示给用户

#### 7.1.1.1 数据流向图（北京老陈提供）

```
数据流向图
                        【LLM】
                          ↑
           messages数组（给LLM的prompt）
           [system, user, assistant, observation]
                          ↑
                       【Agent程序】
                          ↓
           type字段（给前端显示的数据）
           [start, thought, action_tool, observation, chunk, final]
                          ↓
                       【前端UI】
```

**图解说明**：
1. **Agent程序**是核心枢纽，负责：
   - 组装 messages 数组发给 LLM（向上箭头）
   - 解析 LLM 返回，生成 type 字段给前端显示（向下箭头）

2. **messages数组**（向上箭头）：
   - 作用：让LLM理解对话上下文
   - 内容：system, user(任务), assistant(Thought), user(Observation)
   - 流向：Agent程序 → LLM

3. **type字段**（向下箭头）：
   - 作用：让前端显示执行步骤
   - 内容：start, thought, action_tool, observation, chunk, final
   - 流向：Agent程序 → 前端UI

**关键洞察**：
- **同一个数据，两种用途**：工具执行结果 → ①注入给LLM（作为user(Observation)） ②显示给用户（作为observation步骤）
- **Agent程序是桥梁**：连接LLM和前端UI，负责数据转换和流程控制

---

#### 1.1.2 学习来源

| 来源 | 内容 | 核心结论 |
|------|------|---------|
| **ReAct论文** | Yao et al., ICLR 2023 - "ReAct: Synergizing Reasoning and Acting in Language Models" | Thought/Action/Observation是交互式循环，不是一次性准备 |
| **LangChain实现** | create_react_agent + AgentExecutor | 使用Stop Sequence截断，防止LLM幻觉Observation |
| **Prompt Engineering Guide** | ReAct Prompting官方文档 | Thought→Action→Observation是顺序执行，每次调用LLM后才生成下一步 |

#### 1.1.3 核心结论

**问题**：React的Type字段是在LLM调用前组装给LLM，还是调用LLM后通过返回的信息来填充？

**准确答案**：**除start字段外，所有Type字段都是在LLM调用后或工具执行后填充的，不是调用前组装的**

> 注：这里的"Type字段"是指前端SSE事件的type类型，用于前端显示步骤类型，不是给LLM的prompt内容。

| Type | 生成时机 | 数据来源 | 证据 |
|------|---------|---------|------|
| **start** | LLM调用**前** | 框架生成（provider/model信息） | start_step.py:53 - 用户消息→LLM调用前生成 |
| **thought** | LLM调用**后** | LLM返回的推理文本 | LLM生成"Thought: I need to..." |
| **action_tool** | LLM调用**后** | LLM返回的动作指令 | LLM生成"Action: search(...)" |
| **observation** | 工具执行**后** | 程序执行工具返回的结果 | Python执行工具，注入真实结果 |
| **chunk** | LLM流式返回**后** | LLM返回的文本片段 | 流式输出的中间内容 |
| **final** | LLM返回finish**后** | LLM返回的最终答案 | LLM生成"Final Answer: ..." |

#### 1.1.4 ReAct循环流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ReAct 循环流程图（Agent程序视角）                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ① [Agent程序] 发送 messages 给 LLM                                    │
│       messages = [system, user, ...]                                    │
│       程序位置：base_react.py:run_stream()                               │
│                                                                         │
│   ② [LLM调用] LLM 处理并返回响应                                         │
│       ↓                                                                 │
│   ③ [Agent程序解析] 解析 LLM 返回的 Thought + Action                    │
│       程序位置：base_react.py:170-177 (parser.parse_response)           │
│       ⭐ 这里生成 type='thought' 和 type='action_tool'                   │
│       ⭐ 数据来源：【LLM调用后返回的内容】                                │
│                                                                         │
│   ④ [Agent程序执行] 执行 Action（工具调用）                              │
│       程序位置：base_react.py:189-204 (_execute_tool)                   │
│       ↓                                                                 │
│   ⑤ [Agent程序] 生成 Observation（工具执行结果）                         │
│       程序位置：base_react.py:206-241                                    │
│       ⭐ 这里生成 type='observation'                                     │
│       ⭐ 数据来源：【工具执行后返回的结果】                                │
│                                                                         │
│   ⑥ [Agent程序] 注入 Observation 到 messages，再次调用 LLM               │
│       程序位置：base_react.py:213-217 (_add_observation_to_history)     │
│       ↓                                                                 │
│   重复 ①-⑥ 直到 LLM 返回 Final Answer                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 1.1.5 关键证据：Stop Sequence机制

根据LangChain实现（AgentExecutor）：

```python
# 关键技术：Stop Sequence
# LLM生成 "Action: search("Neo")" 后，会自动继续生成 "Observation: Neo is..."
# 但这是LLM的幻觉！实际Observation应该由程序执行工具后返回

# 解决方案：设置 stop=["Observation:"]
response = llm.generate(history, stop=["\nObservation:"])

# 结果：LLM生成到 "Observation:" 就停止
# Python执行工具，获取真实的 Observation，追加到 history
# 再次调用 LLM
```

**这证明**：
1. Thought + Action 是 LLM 调用后返回的
2. Observation 是程序执行工具后注入的，**不是LLM生成的**
3. 所有 type 字段都是 **LLM调用后** 填充的数据

#### 1.1.6 总结

| 问题 | 答案 |
|------|------|
| start 是调用前还是调用后？ | **调用前** - 框架在LLM调用前生成 |
| Thought 是调用前还是调用后？ | **调用后** - LLM返回的内容 |
| Action 是调用前还是调用后？ | **调用后** - LLM在Thought中决定的 |
| Observation 是调用前还是调用后？ | **工具执行后** - 程序执行工具返回的结果 |
| chunk 是调用前还是调用后？ | **调用后** - LLM流式返回的片段 |

**核心结论**：**除start字段（框架在LLM调用前生成）外**，所有Type字段都是在 **LLM调用后** 或 **工具执行后** 填充的，**不是调用前组装给LLM的**。

---

## 二、Type字段核心字段总结（基于通用ReAct框架研究）

### 2.1 研究背景

**研究目的**：抛开我们系统的具体实现，基于通用ReAct框架的学习，总结每个Type字段必须的核心字段。

**研究方法**：学习100篇相关代码实现（ReAct、LangChain、RAGents、Agent Patterns等），总结通用ReAct框架中每个Type字段的核心字段。

**核心原则**：Type字段是LLM调用后或工具执行后填充的数据，不是调用前组装的。

### 2.2 Type字段核心字段总结

#### 2.2.1 **start** - 开始步骤

**生成时机**：LLM调用**前**（框架生成）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `model` | string | 使用的LLM模型名称 | ✅ 必须 |
| `provider` | string | LLM提供商（openai、anthropic等） | ✅ 必须 |
| `timestamp` | string/number | 开始时间戳 | ✅ 必须 |
| `session_id` | string | 会话ID | ✅ 必须 |
| `task` | string | 用户任务/问题 | ✅ 必须 |

**可选字段**：
- `agent_id`: Agent标识
- `max_steps`: 最大迭代步数
- `available_tools`: 可用工具列表

#### 2.2.2 **thought** - 思考步骤

**生成时机**：第1次LLM调用**后**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 思考内容（LLM的推理过程） | ✅ 必须 |
| `action_tool` | string/null | 计划执行的工具名称（如果没有工具调用则为null） | ✅ 必须 |
| `params` | object | 工具调用参数（如果action_tool不为null） | ✅ 必须 |

**可选字段**：
- `reasoning`: 详细的推理过程
- `confidence`: 置信度（0-1）
- `plan`: 执行计划列表
- `next_steps`: 下一步计划

**字段关系**：
```
如果 action_tool == null:
    - 这是纯思考，没有工具调用
    - params 应该为空对象 {}
    - 可能是最终回答（thought+final合并）
    
如果 action_tool != null:
    - 这是思考+工具调用
    - params 必须包含工具调用参数
```

#### 2.2.3 **action_tool** - 工具执行步骤

**生成时机**：工具执行**后**（工具执行结果）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `tool_name` | string | 执行的工具名称 | ✅ 必须 |
| `tool_params` | object | 工具调用参数 | ✅ 必须 |
| `execution_status` | string | 执行状态（success/error） | ✅ 必须 |
| `execution_result` | any | 工具执行结果 | ✅ 必须 |
| `timestamp` | string/number | 执行时间戳 | ✅ 必须 |

**可选字段**：
- `execution_time_ms`: 执行耗时（毫秒）
- `summary`: 执行结果摘要
- `raw_data`: 原始数据
- `error_message`: 错误信息（如果执行失败）
- `retry_count`: 重试次数

**字段关系**：
```
execution_status 可能的值：
- "success": 成功执行
- "error": 执行失败
- "timeout": 执行超时
- "permission_denied": 权限不足

根据 execution_status 不同：
- 如果 "success": execution_result 必须有值
- 如果 "error": error_message 必须有值
```

#### 2.2.4 **observation** - 观察步骤

**生成时机**：第2次LLM调用**后**（LLM响应 + 工具执行结果）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 观察内容（LLM对工具结果的总结） | ✅ 必须 |
| `tool_result` | any | 原始工具执行结果 | ✅ 必须 |
| `tool_name` | string | 对应的工具名称 | ✅ 必须 |
| `is_finished` | boolean | 是否完成任务 | ✅ 必须 |
| `next_action` | string/null | 下一个动作（如果is_finished=false） | ✅ 必须 |

**可选字段**：
- `reasoning`: LLM对工具结果的推理
- `confidence`: 置信度（0-1）
- `summary`: 结果摘要
- `raw_data`: 原始数据

**字段关系**：
```
如果 is_finished == true:
    - content 应该是最终回答
    - next_action 应该为 null
    
如果 is_finished == false:
    - content 是对工具结果的观察和总结
    - next_action 是下一个计划的动作
```

#### 2.2.5 **chunk** - 流式输出步骤

**生成时机**：LLM流式返回**时**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 文本片段内容 | ✅ 必须 |
| `delta` | string | 增量内容（相对于前一个chunk的增量） | ✅ 必须 |
| `is_final` | boolean | 是否是最后一个chunk | ✅ 必须 |
| `timestamp` | string/number | 时间戳 | ✅ 必须 |

**可选字段**：
- `index`: chunk序号
- `role`: 角色（assistant）
- `model`: 使用的模型
- `finish_reason`: 完成原因（stop/length/tool_calls等）

**字段关系**：
```
流式输出的逻辑：
1. 第一个chunk：content = delta
2. 后续chunk：content = 前一个content + delta
3. 最后一个chunk：is_final = true
```

#### 2.2.6 **final** - 最终回答步骤

**生成时机**：LLM返回finish**时**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 最终回答内容 | ✅ 必须 |
| `timestamp` | string/number | 完成时间戳 | ✅ 必须 |
| `total_steps` | number | 总执行步骤数 | ✅ 必须 |
| `total_tokens` | number | 总使用token数 | ✅ 必须 |

**可选字段**：
- `reasoning`: 最终推理总结
- `sources`: 信息来源
- `confidence`: 最终置信度
- `usage`: 使用统计（token、时间等）
- `intermediate_steps`: 中间步骤摘要

**字段关系**：
```
final 是 ReAct 循环结束的标志：
- content 是对用户问题的最终回答
- total_steps 记录循环次数
- total_tokens 记录LLM调用消耗
```

#### 2.2.7 **error** - 错误步骤

**生成时机**：发生错误**时**（异常处理）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `error_type` | string | 错误类型 | ✅ 必须 |
| `error_message` | string | 错误信息 | ✅ 必须 |
| `timestamp` | string/number | 错误时间戳 | ✅ 必须 |
| `recoverable` | boolean | 是否可恢复 | ✅ 必须 |

**可选字段**：
- `stack_trace`: 堆栈跟踪
- `context`: 错误上下文
- `suggested_fix`: 建议修复
- `retry_suggestion`: 重试建议

**字段关系**：
```
error_type 可能的值：
- "max_steps_exceeded": 超过最大步数
- "llm_error": LLM调用错误
- "tool_error": 工具执行错误
- "parsing_error": 解析错误
- "network_error": 网络错误
- "permission_error": 权限错误
```

### 2.3 核心字段总结表

| Type | 必须的核心字段 | 字段说明 |
|------|---------------|----------|
| **start** | model, provider, timestamp, session_id, task | 框架生成，LLM调用前 |
| **thought** | content, action_tool, params | LLM响应，思考+工具调用 |
| **action_tool** | tool_name, tool_params, execution_status, execution_result, timestamp | 工具执行后 |
| **observation** | content, tool_result, tool_name, is_finished, next_action | 第2次LLM响应+工具结果 |
| **chunk** | content, delta, is_final, timestamp | LLM流式响应 |
| **final** | content, timestamp, total_steps, total_tokens | LLM最终回答 |
| **error** | error_type, error_message, timestamp, recoverable | 错误处理 |

### 2.4 字段生成时机总结

| Type | 生成时机 | 数据来源 |
|------|---------|---------|
| **start** | LLM调用**前** | 框架生成 |
| **thought** | 第1次LLM调用**后** | LLM响应 |
| **action_tool** | 工具执行**后** | 工具执行结果 |
| **observation** | 第2次LLM调用**后** | LLM响应 + 工具结果 |
| **chunk** | LLM流式返回**时** | LLM响应 |
| **final** | LLM返回finish**时** | LLM响应 |
| **error** | 发生错误**时** | 异常信息 |

### 2.5 研究成果应用建议

1. **前端渲染**：根据每个Type的核心字段设计前端组件
2. **数据存储**：设计数据库表结构时参考核心字段
3. **API设计**：定义SSE事件结构时使用核心字段
4. **测试用例**：基于核心字段设计测试用例
5. **文档规范**：作为系统设计的参考规范

**重要提醒**：
- 以上总结基于通用ReAct框架研究，抛开了具体系统实现
- 核心字段是**必须有的**，可选字段可以根据需求添加
- 不同框架可能有不同的字段命名，但核心字段本质相同

---

## 三、Type字段在当前系统的具体实现分析

> **说明**：本章分析Type字段在**当前系统**的具体实现，包括代码位置、数据来源等。之前的第二章节为通用理论分析章节。

### 3.1 Type字段定义（前端）

根据 `frontend/src/utils/sse.ts` 第66行：

```typescript
type: "thought" | "action_tool" | "observation" | "chunk" | "final" | "error" | "incident" | "interrupted" | "start" | "paused" | "resumed" | "retrying";
```

### 3.2 Type字段分类

| 类别 | Type | 用途 |
|------|------|------|
| **内容步骤** | `start` | 开始步骤，记录模型信息 |
| | `chunk` | AI流式回复的内容片段 |
| | `final` | 最终回答 |
| **执行步骤** | `thought` | AI思考过程 |
| | `action_tool` | 工具调用 |
| | `observation` | 工具执行结果 |
| **异常步骤** | `error` | 错误 |
| | `incident` | 中断（包含interrupted/paused/resumed/retrying） |

### 3.3 Type字段生成时机分析（当前系统）

#### 3.3.1 ✅ LLM调用**前**准备的数据（框架生成）

| Type | 生成位置 | 时机 | 数据来源 |
|------|---------|------|---------|
| **start** | `start_step.py:53` | 用户发送消息后，LLM调用前 | 框架生成，记录model/provider等信息 |

#### 3.3.2 ✅ LLM调用**后**填充的数据

| Type | 生成位置 | 时机 | 数据来源 |
|------|---------|------|---------|
| **thought** | `base_react.py:170` | 第1次LLM调用后，解析响应时 | LLM返回的content+action_tool+params |
| **action_tool** | `base_react.py:194` | thought之后，工具执行后 | 工具执行结果+LLM决定的action |
| **observation** | `base_react.py:230` | 工具执行后，第2次LLM调用后 | 工具执行结果+第2次LLM返回的content |
| **chunk** | `chat_stream_query.py:190` | LLM流式返回时 | LLM返回的文本片段 |
| **final** | `base_react.py:182/251` | LLM返回finish时 | LLM返回的最终内容 |
| **error** | `base_react.py:260/269` | 发生错误时 | 错误信息 |

### 3.4 ReAct循环的时序图（当前系统）

```
┌─────────────────────────────────────────────────────────────────┐
│                      ReAct 循环时序图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ① [框架] start 步骤                                            │
│     type='start'                                                │
│     时机：用户消息→LLM调用前                                     │
│     来源：框架生成                                               │
│                                                                 │
│  ② [LLM调用1] 第1次LLM调用                                      │
│     ↓                                                           │
│  ③ [LLM响应] type='thought'                                     │
│     时机：第1次LLM调用完成后                                     │
│     来源：LLM返回的content+action_tool+params                   │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ④ [工具执行] type='action_tool'                                │
│     时机：工具执行完成后                                         │
│     来源：工具执行结果+LLM决定的action                           │
│                                                                 │
│  ⑤ [LLM调用2] 第2次LLM调用（观察阶段）                           │
│     ↓                                                           │
│  ⑥ [LLM响应] type='observation'                                 │
│     时机：第2次LLM调用完成后                                     │
│     来源：工具执行结果+LLM返回的content                          │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ⑦ [流式输出] type='chunk'                                      │
│     时机：LLM流式返回时                                          │
│     来源：LLM返回的文本片段                                      │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ⑧ [结束] type='final'                                          │
│     时机：LLM返回finish时                                        │
│     来源：LLM返回的最终内容                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 关键结论（当前系统）

#### 3.5.1 结论1：thought 是 LLM调用后填充

```python
# base_react.py:152-177
response = await self._get_llm_response()  # LLM调用
parsed = self.parser.parse_response(response)  # 解析响应

yield {
    "type": "thought",
    "content": parsed.get("content", ""),     # ← 来自LLM响应
    "action_tool": parsed.get("action_tool"), # ← 来自LLM响应
    "params": parsed.get("params", {})        # ← 来自LLM响应
}
```

**结论**：thought 的 content、action_tool、params 都来自 LLM 响应，不是调用前准备的。

#### 3.5.2 结论2：action_tool 是工具执行后填充

```python
# base_react.py:189-204
execution_result = await self._execute_tool(action_tool, params)  # 工具执行

yield {
    "type": "action_tool",
    "content": action_tool,
    "execution_status": execution_result.get("status"),  # ← 工具执行结果
    "summary": execution_result.get("summary", ""),      # ← 工具执行结果
    "raw_data": execution_result.get("data")             # ← 工具执行结果
}
```

**结论**：action_tool 的 execution_status、summary、raw_data 来自工具执行结果。

#### 3.5.3 结论3：observation 是第2次LLM调用后填充

```python
# base_react.py:216-241
llm_response = await self._get_llm_response()  # 第2次LLM调用
parsed_obs = self.parser.parse_response(llm_response)  # 解析响应

yield {
    "type": "observation",
    "content": parsed_obs.get("content", ""),      # ← 来自第2次LLM响应
    "obs_action_tool": parsed_obs.get("action_tool"),  # ← 来自第2次LLM响应
    "obs_params": parsed_obs.get("params", {})     # ← 来自第2次LLM响应
}
```

**结论**：observation 的 content 来自第2次LLM响应，不是工具执行结果本身。

### 3.6 参考依据

| 来源 | 内容 | 链接 |
|------|------|------|
| **后端代码** | base_react.py:170-241 - Type字段生成位置 | backend/app/services/agent/base_react.py |
| **前端代码** | sse.ts:66 - Type字段定义 | frontend/src/utils/sse.ts |

### 3.7 总结表（当前系统）

| Type | 生成时机 | 数据来源 | LLM调用前/后 |
|------|---------|---------|-------------|
| **start** | LLM调用前 | 框架生成 | ⏱️ 调用前 |
| **thought** | 第1次LLM调用后 | LLM响应 | ✅ 调用后 |
| **action_tool** | 工具执行后 | 工具结果 | ✅ 调用后 |
| **observation** | 第2次LLM调用后 | LLM响应 | ✅ 调用后 |
| **chunk** | LLM流式返回时 | LLM响应 | ✅ 调用后 |
| **final** | LLM返回finish时 | LLM响应 | ✅ 调用后 |
| **error** | 发生错误时 | 错误信息 | - |

**核心结论**：除 `start` 外，所有Type字段都是 **LLM调用后** 填充的数据，不是调用前准备的。

---
