# React步骤分析与设计

**存放位置**: D:\OmniAgentAs-desk\doc-react步骤\

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-04-02 00:15:30 | 小沈 | 初始版本：Thought字段设计分析 |
| v2.0 | 2026-04-02 07:30:00 | 小沈 | 重构文档结构：去重合并，逻辑优化 |
| v3.0 | 2026-04-02 08:00:00 | 小沈 | 增补核心概念、问题1分析、完整Step设计 |
| v3.1 | 2026-04-02 09:09:41 | 小沈 | 新增5.5节Stop Sequence机制保障，确保observation是原始数据 |
| v3.2 | 2026-04-02 09:27:10 | 小沈 | 明确Step和Loop概念定义，统一术语使用 |
| v3.3 | 2026-04-02 09:36:58 | 小沈 | 在type字段设计中添加step字段，明确chunk不需要step字段 |
| v3.4 | 2026-04-02 10:04:45 | 小沈 | 新增1.6-1.8节：说明Prompt生成、type字段填写、循环终止条件与final跳转机制 |
| v3.5 | 2026-04-02 10:56:45 | 小沈 | 整理文档格式，修正章节编号，统一标题层级 |
| v3.6 | 2026-04-02 11:30:00 | 小沈 | 修复第4章设计：start添加step字段，observation添加tool_name和tool_params，明确step递增规则 |
| v3.7 | 2026-04-02 11:45:00 | 小沈 | 修正step序号规则说明：将"会话"改为"对话"，明确一次新的对话中重新开始计数 |
| v3.8 | 2026-04-02 12:30:00 | 小沈 | 新增5.2节：每个type字段的生成与填写详细说明，包含字段生成规则、代码示例和前端使用建议 |
| v3.9 | 2026-04-02 13:00:00 | 小沈 | 修正step递增规则：参考当前代码实现，thought/action_tool/observation共享同一个loop计数器step值 |
| v4.0 | 2026-04-02 12:53:54 | 小沈 | 修正所有type的step生成规则：统一使用`next_step()`独立递增，修正示例代码和示例值，start.step=1 |
| v4.1 | 2026-04-02 13:00:20 | 小沈 | start type新增3个字段：user_message、security_check、display_name |
| v4.2 | 2026-04-02 13:07:00 | 小沈 | timestamp字段类型修正：string→number（毫秒级时间戳），统一所有生成方法和代码示例 |
| v4.3 | 2026-04-02 13:13:10 | 小沈 | tool_name/tool_params字段从action_tool移至thought，observation数据来源改为从thought复制 |
| v4.5 | 2026-04-02 14:25:17 | 小沈 | 新增5.1.1节ReAct输出统一解析器设计（参考LlamaIndex源码） |
| v4.6 | 2026-04-02 14:29:33 | 小沈 | 5.2.2/5.2.5代码示例统一使用parse_react_response()，消除独立解析器 |
| v4.7 | 2026-04-02 14:35:00 | 小沈 | 修正主循环与build函数参数一致性；修正4.5/5.1.1识别规则一致性；更新版本信息 |
| v4.8 | 2026-04-02 15:00:00 | 小沈 | 新增5.1.2节Thinking Process设计 |
| v4.9 | 2026-04-02 16:00:00 | 小沈 | 新增5.1.3节ReasoningStep基类参考设计、各type补充LlamaIndex源码对照分析 |
| v4.10 | 2026-04-02 17:00:00 | 小沈 | final步骤新增is_finished字段（业务完成标志） |
| v4.11 | 2026-04-02 17:30:00 | 小沈 | 修正章节编号问题 |
| v4.12 | 2026-04-02 18:11:00 | 小沈 | 添加action_tool部分的get_content和yield说明 |
| v4.13 | 2026-04-02 18:41:00 | 小沈 | 添加start部分的get_content和yield说明 |
| v4.14 | 2026-04-03 06:02:52 | 小沈 | 新增第6章：设计文档与当前代码的深度对比分析（解析器/is_done/messages构建/observation字段） |
| v4.15 | 2026-04-07 22:00:00 | 小沈 | 新增第7章：设计文档与当前代码的深度对比分析（解析器/is_done/messages构建/observation字段） |
| v4.16 | 2026-04-08 08:40:24 | 小沈 | 新增7.4.5节：实际修改总结（删除第二次LLM调用，统一字段名，添加tool_name） |
| v4.17 | 2026-04-08 10:00:00 | 小强 | 新增4.8节：设计文档与代码实现深度对比分析（字段差异分析+修改决策） |
| v4.18 | 2026-04-08 11:25:00 | 小沈 | 更新4.8节为实施结果说明（删除reasoning字段） |
| v4.19 | 2026-04-08 11:35:00 | 小沈 | 4.8节改为当前代码字段定义（与代码保持一致） |
| v4.20 | 2026-04-08 15:23:58 | 小沈 | 第7章重写：整合第5章分析结果，新增ReasoningStep基类分析、ReAct统一解析器分析，修正final/error的step字段说明 |
| v4.21 | 2026-04-08 15:34:53 | 小沈 | 更新7.1.1节：新增session_id vs task_id详细分析，明确两者用途不同 |
| v4.22 | 2026-04-08 15:47:25 | 小沈 | 新增第8章：后端tool_name/tool_params统一化修改方案，包含完整修改清单 |
| v4.23 | 2026-04-08 16:30:00 | 小健 | 修正8.2.2节：补充format_thought_sse函数的action_tool/params参数名修改 |
| v4.24 | 2026-04-08 17:35:00 | 小沈 | 完成后端代码修改：base_react.py/sse_formatter.py/step_types.py/tool_parser.py/llm_strategies.py/file_prompts.py，统一为tool_name/tool_params，测试全部通过 |
| v4.25 | 2026-04-11 21:02:42 | 小沈 | 文档修正：核对实际代码，修正4.8节字段定义、7.1.4节observation对比、7.6节改进建议；新增第10章：2026-04-11文档修正记录；新增429错误统一处理、超长历史TODO、search_files参数统一等说明 |
| v4.26 | 2026-04-14 11:12:27 | 小欧 | 新增第12章：未实现项详细说明（补充版），详细列出文档设计与代码实现的差异，包含字段缺失、功能改进等20项未实现内容 |


---

## 一、ReAct核心概念

### 1.0 关键概念定义

> ⚠️ **重要概念澄清**：本文档中严格区分"Step"和"Loop"两个概念：

| 概念 | 定义 | 示例 |
|------|------|------|
| **Step** | ReAct循环中的**单个步骤**类型，是前端显示和数据存储的基本单位 | thought、action_tool、observation、final、error等 |
| **Loop** | 完整的ReAct**循环迭代**，包含thought→action→observation三个步骤 | 第1轮思考、第2轮思考、第3轮思考... |

**核心区别**：
- **Step** = 循环中的**组成部分**（如：thought是一个step）
- **Loop** = 完整的**思考-行动-观察**循环（如：第1个loop包含thought+action_tool+observation三个step）

**应用指导**：
- `type`字段定义的是**Step类型**（thought、action_tool等）
- `max_steps`、`total_steps`等统计字段统计的是**Step数量**
- `loop_count`、`current_loop`等统计的是**Loop数量**

### 1.1 标准ReAct的Step定义

**权威来源**：
- ReAct论文 (Yao et al., ICLR 2023)
- Arun Baby (2026-02-24): "Thought是自然语言字符串，包含状态跟踪、差距识别、行动理由、错误确认"
- Michael Brenndoerfer (2026-02-03): "Thought是模型的内部推理，解释当前状态、还需要什么信息、下一步做什么"

**标准ReAct的格式**：
```
Thought: 我需要查看目录结构，使用list_directory工具
Action: list_directory[{"path": "/home"}]
Observation: [文档, 图片, 视频]

Step N:
  LLM调用 → thought + action + action_input
       ↓
  工具执行
       ↓
  yield observation（工具执行结果）

Step N+1:
  LLM调用 → 基于Step N的observation，决定下一步
```

**核心原则**：
1. **Thought**：纯自然语言，只包含推理过程
2. **Action**：LLM决定的工具调用（不含执行结果）
3. **Observation**：工具执行的原始结果

### 1.2 messages数组 vs type字段

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

**关键洞察**：
- **同一个数据，两种用途**：工具执行结果 → ①注入给LLM（作为user(Observation)） ②显示给用户（作为observation步骤）
- **Agent程序是桥梁**：连接LLM和前端UI，负责数据转换和流程控制

### 1.3 数据流向图

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

### 1.4 ReAct循环流程图

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

### 1.5 Stop Sequence机制

**关键技术**：
```python
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
4. 
### 1.6 Stop Sequence机制保障

重构后的设计如何保证Observation是原始数据：

1. **thought/action分离**：LLM只生成thought和action，不生成observation
2. **observation独立Step**：由程序执行工具后直接生成，不经过LLM
3. **消除第2次LLM调用**：避免LLM"总结"工具结果

流程保障：
```
LLM调用 → 生成thought + action
     ↓
Stop Sequence截断
     ↓
程序执行工具 → 生成observation（原始数据）
     ↓
注入messages，再次调用LLM
```
**关键保障点**：
- **observation字段设计**：只包含`observation`和`return_direct`，不包含LLM生成的内容
- **数据源隔离**：thought来自LLM，observation来自工具执行
- **防止幻觉**：Stop Sequence阻止LLM生成虚假的observation内容

## 二、现在系统的问题分析

### 2.1 每loop调用2次LLM是否正确？

已经解决

## 三、重构message即Prompt的设计方案
原则：message的 agent输出给LLM的

| 概念 | 用途 | 内容 | 数据流向 |
|------|------|------|---------|
| **messages数组** | 给LLM的prompt（输入） | system, user(任务), assistant(Thought), user(Observation) | 程序 → LLM |

### 3.1 Prompt（messages数组）的生成与组装原则


**messages数组构成规则**：

| 位置 | 角色 | 作用 | 来源 |
|------|------|------|------|
| 第1位 | `system` | 系统提示词 | 固定内容 |
| 第2位 | `user` | 用户任务 | 用户输入 |
| 第3位 | `assistant` | LLM推理 | LLM返回的thought |
| 第4位 | `user` | 工具结果 | 工具执行的observation |
| 第5位 | `assistant` | LLM推理 | LLM返回的thought |
| 第6位 | `user` | 工具结果 | 工具执行的observation |

**累积规则**：
- 每次循环增加2条：`assistant(thought)` + `user(observation)`
- system和user(任务)始终在前2位

**示例**：
```
第1次调用: [system, user]                           → 2条
第2次调用: [system, user, assistant, user]           → 4条
第3次调用: [system, user, assistant, user, assistant, user] → 6条
```
### 3.2 Prompt（messages数组）的生成与组装实施详细说明

#### 3.2.1 核心设计思路

**messages数组**是给LLM的输入，**type字段**是给前端的输出。两者数据来源相同，但格式和用途不同。

```
┌─────────────────────────────────────────────────────────────────────┐
│                    同一数据，两种用途                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  工具执行结果(observation)                                          │
│       ↓                                                             │
│  ┌────┴────┐                                                        │
│  ↓         ↓                                                        │
│ 注入给LLM  发送给前端                                                │
│  messages数组  type字段                                             │
│  user(Observation)  observation步骤                                  │
│                                                                     │
│  LLM返回(thought+action)                                            │
│       ↓                                                             │
│  ┌────┴────┐                                                        │
│  ↓         ↓                                                        │
│ 注入给LLM  发送给前端                                                │
│  messages数组  type字段                                             │
│  assistant(Thought)  thought步骤                                     │
│                     action_tool步骤                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 messages数组的生成规则

**初始状态（第1次LLM调用前）**：
```python
messages = [
    {"role": "system", "content": system_prompt},           # 系统提示词
    {"role": "user", "content": user_task},                 # 用户任务
]
```

**每轮循环追加规则**：
```python
# 第N轮循环：
# 1. LLM返回thought + action → 追加assistant消息
messages.append({"role": "assistant", "content": thought_content})

# 2. 工具执行返回observation → 追加user消息
messages.append({"role": "user", "content": f"Observation: {observation}"})

# 3. 再次调用LLM，messages已包含完整历史
```

**messages数组累积示例**：
```
第1次LLM调用: [system, user]                                    → 2条
第2次LLM调用: [system, user, assistant(thought1), user(obs1)]   → 4条
第3次LLM调用: [system, user, assistant(t1), user(o1),           → 6条
              assistant(t2), user(o2)]
```

#### 3.2.3 从type步骤历史构建messages数组

**核心函数**：`build_messages_from_steps(steps: list[dict]) -> list[dict]`

```python
def build_messages_from_steps(steps: list[dict], system_prompt: str, user_task: str) -> list[dict]:
    """从type步骤历史构建messages数组（给LLM的prompt）"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_task},
    ]
    
    for step in steps:
        if step["type"] == "thought":
            # thought步骤 → assistant消息
            assistant_content = step["content"]
            if step.get("tool_name"):
                assistant_content += f"\nAction: {step['tool_name']}"
                assistant_content += f"\nAction Input: {step['tool_params']}"
            messages.append({"role": "assistant", "content": assistant_content})
            
        elif step["type"] == "observation":
            # observation步骤 → user消息
            messages.append({
                "role": "user",
                "content": f"Observation: {step['observation']}"
            })
            
        elif step["type"] == "final":
            # final步骤 → assistant消息（最终回答）
            messages.append({
                "role": "assistant",
                "content": step["response"]
            })
            
        # start/action_tool/error/chunk 不注入messages数组
        # - start: 对话开始标记，不是LLM上下文
        # - action_tool: 工具执行结果，已通过observation注入
        # - error: 错误信息，不注入LLM
        # - chunk: 流式输出片段，不注入LLM
    
    return messages
```

#### 3.2.4 各type步骤对messages数组的贡献

| type | 是否注入messages | 注入角色 | 注入内容 | 说明 |
|------|-----------------|---------|---------|------|
| **start** | ❌ 不注入 | - | - | 对话开始标记，仅前端展示 |
| **thought** | ✅ 注入 | `assistant` | `content` + `tool_name` + `tool_params` | LLM推理过程 |
| **action_tool** | ❌ 不注入 | - | - | 工具执行结果通过observation注入 |
| **observation** | ✅ 注入 | `user` | `Observation: {observation}` | 工具执行结果 |
| **final** | ✅ 注入 | `assistant` | `response` | 最终回答 |
| **error** | ❌ 不注入 | - | - | 错误信息，不注入LLM |
| **chunk** | ❌ 不注入 | - | - | 流式输出片段，不注入LLM |

#### 3.2.5 从start开始逐步组装messages的完整示例

第1次LLM调用：start之后，messages = [system, user]
第2次LLM调用：observation注入后，messages = [system, user, assistant(thought1), user(obs1)]
第3次LLM调用：第2轮observation注入后...
所以LLM调用的时机是：

初始调用：start之后，messages只有system+user
循环调用：每次observation注入到messages后，触发下一次LLM调用

**场景**：用户查询"北京天气"，LLM调用天气工具后回答

**完整步骤历史（type字段，发送给前端）**：
```
step=1: start          → 对话开始（不注入messages）
step=2: thought        → "需要查询北京天气" + tool_name="get_weather"
step=3: action_tool    → 工具执行成功（不注入messages）
step=4: observation    → "北京今天晴，25度"
step=5: thought        → "已获取天气信息，可以回答用户"
step=6: final          → "北京今天晴天，气温25度。"
```
步骤历史（type字段，发送给前端）：
[
    {"type": "start", "step": 1, "model": "glm-4", ...},
    {"type": "thought", "step": 2, "content": "需要查询北京天气", "tool_name": "get_weather", "tool_params": {"city": "北京"}},
    {"type": "action_tool", "step": 3, "execution_status": "success", "execution_result": "北京今天晴，25度"},
    {"type": "observation", "step": 4, "tool_name": "get_weather", "observation": "北京今天晴，25度"},
    {"type": "thought", "step": 5, "content": "已获取天气信息，可以回答用户", "tool_name": ""},
    {"type": "final", "step": 6, "response": "北京今天晴天，气温25度。", "is_finished": true},
]
---

**第1步：start（step=1）→ 不注入messages，仅初始化**

```python
# start步骤：对话开始标记
start_step = {
    "type": "start",
    "step": 1,
    "model": "glm-4",
    "provider": "zhipu",
    "display_name": "智谱GLM-4",
    "session_id": "sess_abc123",
    "task": "北京天气怎么样？",
    "user_message": "北京天气怎么样？",
    "security_check": {"passed": True, "risk_level": "low"},
    "timestamp": 1743566400000
}

# messages数组初始化（system + user任务）
messages = [
    {"role": "system", "content": "你是一个助手。你有以下工具：\n- get_weather: 查询天气\n\nTo use a tool, please respond with:\nThought: your thought\nAction: tool_name\nAction Input: {\"input\": \"value\"}\n\nIf you have completed the task, please respond with:\nThought: your thought\nFinal Answer: your final answer\n\nBegin!"},
    {"role": "user", "content": "北京天气怎么样？"},
]

# 当前messages条数：2条
# 发送给LLM？否（start不触发LLM调用）
```

---

**第2步：thought（step=2）→ 注入assistant消息**

```python
# thought步骤：LLM返回推理过程
thought_step = {
    "type": "thought",
    "step": 2,
    "content": "需要查询北京天气",
    "tool_name": "get_weather",
    "tool_params": {"city": "北京"},
    "timestamp": 1743566405000
}

# 追加assistant消息到messages
messages.append({
    "role": "assistant",
    "content": "需要查询北京天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"
})

# 当前messages数组：
messages = [
    {"role": "system", "content": "你是一个助手..."},           # 第1条
    {"role": "user", "content": "北京天气怎么样？"},             # 第2条
    {"role": "assistant", "content": "需要查询北京天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"},  # 第3条
]

# 当前messages条数：3条
# 发送给LLM？否（thought后需要执行工具，不立即调用LLM）
```

---

**第3步：action_tool（step=3）→ 不注入messages，仅执行工具**

```python
# action_tool步骤：工具执行结果
action_tool_step = {
    "type": "action_tool",
    "step": 3,
    "execution_status": "success",
    "execution_result": "北京今天晴，25度",
    "error_message": None,
    "timestamp": 1743566406000
}

# messages数组不变（action_tool不注入messages）
# 当前messages条数：3条
# 发送给LLM？否（工具执行结果需要通过observation注入）
```

---

**第4步：observation（step=4）→ 注入user消息**

```python
# observation步骤：工具执行结果
observation_step = {
    "type": "observation",
    "step": 4,
    "tool_name": "get_weather",
    "tool_params": {"city": "北京"},
    "observation": "北京今天晴，25度",
    "return_direct": False,
    "timestamp": 1743566407000
}

# 追加user消息到messages
messages.append({
    "role": "user",
    "content": "Observation: 北京今天晴，25度"
})

# 当前messages数组：
messages = [
    {"role": "system", "content": "你是一个助手..."},           # 第1条
    {"role": "user", "content": "北京天气怎么样？"},             # 第2条
    {"role": "assistant", "content": "需要查询北京天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"},  # 第3条
    {"role": "user", "content": "Observation: 北京今天晴，25度"},  # 第4条
]

# 当前messages条数：4条
# 发送给LLM？✅ 是（observation注入后，再次调用LLM）
```

---

**第5步：thought（step=5）→ 注入assistant消息**

```python
# thought步骤：LLM返回推理过程（不需要再调用工具）
thought_step = {
    "type": "thought",
    "step": 5,
    "content": "已获取天气信息，可以回答用户",
    "tool_name": "",
    "tool_params": {},
    "timestamp": 1743566410000
}

# 追加assistant消息到messages
messages.append({
    "role": "assistant",
    "content": "已获取天气信息，可以回答用户"
})

# 当前messages数组：
messages = [
    {"role": "system", "content": "你是一个助手..."},           # 第1条
    {"role": "user", "content": "北京天气怎么样？"},             # 第2条
    {"role": "assistant", "content": "需要查询北京天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"},  # 第3条
    {"role": "user", "content": "Observation: 北京今天晴，25度"},  # 第4条
    {"role": "assistant", "content": "已获取天气信息，可以回答用户"},  # 第5条
]

# 当前messages条数：5条
# 发送给LLM？否（thought后没有tool_name，说明LLM已准备好回答）
```

---

**第6步：final（step=6）→ 注入assistant消息，循环结束**

```python
# final步骤：LLM返回最终回答
final_step = {
    "type": "final",
    "step": 6,
    "response": "北京今天晴天，气温25度。",
    "is_finished": True,
    "thought": "已获取天气信息，可以回答用户",
    "is_streaming": False,
    "timestamp": 1743566415000
}

# 追加assistant消息到messages
messages.append({
    "role": "assistant",
    "content": "北京今天晴天，气温25度。"
})

# 当前messages数组（最终状态）：
messages = [
    {"role": "system", "content": "你是一个助手..."},           # 第1条
    {"role": "user", "content": "北京天气怎么样？"},             # 第2条
    {"role": "assistant", "content": "需要查询北京天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"},  # 第3条
    {"role": "user", "content": "Observation: 北京今天晴，25度"},  # 第4条
    {"role": "assistant", "content": "已获取天气信息，可以回答用户"},  # 第5条
    {"role": "assistant", "content": "北京今天晴天，气温25度。"},  # 第6条
]

# 当前messages条数：6条
# 发送给LLM？否（final表示循环结束，不再调用LLM）
```

---

**messages数组累积总结**：

| 步骤 | type | 注入角色 | 注入内容 | messages条数 | 是否调用LLM |
|------|------|---------|---------|-------------|------------|
| step=1 | start | ❌ 不注入 | - | 2条（初始） | ❌ |
| step=2 | thought | `assistant` | "需要查询北京天气\nAction: get_weather..." | 3条 | ❌ |
| step=3 | action_tool | ❌ 不注入 | - | 3条 | ❌ |
| step=4 | observation | `user` | "Observation: 北京今天晴，25度" | 4条 | ✅ |
| step=5 | thought | `assistant` | "已获取天气信息，可以回答用户" | 5条 | ❌ |
| step=6 | final | `assistant` | "北京今天晴天，气温25度。" | 6条 | ❌ |

**关键规则**：
- **start**：初始化messages（system + user），不触发LLM调用
- **thought**：追加assistant消息，不触发LLM调用（等待工具执行或final）
- **action_tool**：不注入messages，仅执行工具
- **observation**：追加user消息，触发LLM调用（注入后再次调用LLM）
- **final**：追加assistant消息，循环结束

#### 3.2.6 与LlamaIndex的对照

| LlamaIndex机制 | 我们的实现 | 说明 |
|---------------|-----------|------|
| `current_reasoning.append(step)` | `steps.append(step_dict)` | 每一步追加到历史 |
| `step.get_content()` | `build_messages_from_steps()` | 从步骤历史构建prompt |
| `formatter.format(messages)` | 直接构造messages数组 | 格式化为LLM输入 |
| `reasoning_text += "\nObservation: "` | `messages.append({"role": "user", ...})` | 提示LLM继续 |

#### 3.2.7 关键设计要点

1. **数据源分离**：thought来自LLM，observation来自工具执行，两者独立生成
2. **Stop Sequence保障**：LLM生成到"Observation:"自动停止，防止幻觉
3. **角色对应**：thought→assistant，observation→user，符合对话模式
4. **不注入的步骤**：start/action_tool/error/chunk仅用于前端展示，不注入LLM上下文

#### 3.2.8 LLM调用的时机与位置

**核心规则**：LLM只在**observation注入后**被调用。

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM调用时机流程图                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ① start完成后 → 初始化messages → ✅ 第1次调用LLM                   │
│     messages = [system, user]                                       │
│                                                                     │
│  ② LLM返回thought+action → 追加assistant → ❌ 不调用LLM             │
│     messages.append({"role": "assistant", "content": thought})      │
│                                                                     │
│  ③ 工具执行action_tool → 不注入messages → ❌ 不调用LLM              │
│     (仅执行工具，获取结果)                                           │
│                                                                     │
│  ④ 生成observation → 追加user → ✅ 第2次调用LLM                     │
│     messages.append({"role": "user", "content": "Observation: ..."})│
│     → 再次调用LLM                                                   │
│                                                                     │
│  ⑤ LLM返回thought（无action）→ 追加assistant → ❌ 不调用LLM         │
│     (LLM已准备好回答，不需要再调用工具)                               │
│                                                                     │
│  ⑥ 生成final → 追加assistant → ❌ 不调用LLM（循环结束）              │
│     messages.append({"role": "assistant", "content": response})     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**LLM调用触发条件**：

| 步骤 | type | messages变化 | 是否调用LLM | 原因 |
|------|------|-------------|------------|------|
| start | 初始化 | `[system, user]` | ✅ 第1次 | 开始对话 |
| thought | 追加assistant | `+1条` | ❌ | 等待工具执行 |
| action_tool | 不注入 | `不变` | ❌ | 仅执行工具 |
| observation | 追加user | `+1条` | ✅ 第N+1次 | 注入后调用LLM |
| thought(无action) | 追加assistant | `+1条` | ❌ | 准备回答 |
| final | 追加assistant | `+1条` | ❌ | 循环结束 |

**代码位置**：`base_react.py:run_stream()` 中的循环体

```python
async def run_stream(self, user_task: str):
    # 初始化messages
    messages = [system_prompt, user_task]
    
    # 第1次调用LLM
    response = await self.llm.achat(messages)
    
    while True:
        # 解析LLM返回
        parsed = parse_react_response(response)
        
        if parsed["type"] == "answer":
            # 生成final，循环结束
            break
        
        # 执行工具
        result = await self._execute_tool(parsed["tool_name"], parsed["tool_params"])
        
        # 注入observation到messages
        messages.append({"role": "user", "content": f"Observation: {result}"})
        
        # ✅ 再次调用LLM（关键位置）
        response = await self.llm.achat(messages)
```

**关键洞察**：
- LLM调用次数 = 1（初始）+ N（observation注入次数）
- 每次observation注入后，messages数组增长2条（assistant+user）
- LLM始终看到的是完整的messages历史，包含所有推理步骤
------------
### 3.3  实现情况【2026-4-11日】

messages数组生成规则	✅ 完全实现
各type步骤贡献	✅ 完全实现
LLM调用时机	✅ 完全实现
数据源分离设计	✅ 完全实现
文档第3章描述的messages数组生成规则，现在代码已经全部实现。

## 四、重构后的type字段值的设计方案

### 4.1 start（重构后）
**基本字段**：
```
start: {
    step: number,           // 步骤序号 = 1（标识对话开始）
    model: string,          // 使用的LLM模型名称
    provider: string,       // LLM提供商（openai、anthropic等）
    display_name: string,   // 模型显示名称
    timestamp: number,      // 毫秒级时间戳
    session_id: string,     // 会话ID
    task: string,           // 用户任务/问题
    user_message: string,   // 用户消息
    security_check: object  // 安全检查结果
}
```

**step序号规则**：
- start.step = 1（标识对话开始）
- 后续步骤调用`next_step()`函数获得独立递增的step值
- 整个对话过程中使用**一个**step计数器函数（`create_step_counter()`）
- 每次调用`next_step()`返回递增1的值
- 示例：thought→2, action_tool→3, observation→4, thought→5, action_tool→6, observation→7
- 在**一次新的对话**中重新创建计数器，start=1，后续从2开始递增
- **参考当前代码实现**：`chat_helpers.py` 中 `create_step_counter()` 返回闭包函数，每次调用递增1


**可选字段**：
- `agent_id`: Agent标识
- `max_steps`: 最大迭代步数
- `available_tools`: 可用工具列表

### 4.2 thought（重构后）
**基本字段**：
```
thought: {
    step: number,          // 步骤序号
    content: string,        // LLM的推理过程（纯自然语言）
    timestamp: number       // 毫秒级时间戳
}
```

**条件必需字段**（LLM决定调用工具时填写）：
- `tool_name`: 工具名称（LLM决定调用的工具）
- `tool_params`: 工具参数（调用工具时传递的参数）

step=next_step()

**Thought特征**：
1. **纯自然语言**：不包含结构化字段
2. **状态跟踪**：记录已确定的信息
3. **差距识别**：说明还需要什么信息
4. **行动理由**：解释为什么要执行某个动作
5. **错误确认**：当出现问题时承认并提议修正

**tool_name/tool_params字段说明**：
- `tool_name`：LLM决定调用的工具名称
- `tool_params`：调用工具时传递的**原始参数**
- 用于前端显示用户知道AI决定用什么工具和参数
- 与action_tool的execution_status配合使用，thought决定→action_tool执行

**Thought内容示例**：
```
正常情况："我需要先查看目录结构，然后才能决定如何整理文件。"
多步推理："我已经确认了作者是海明威，现在需要找到他的出生地，最后查询该城市的人口。"
错误处理："之前的搜索没有返回结果，我需要尝试更具体的关键词。"
```

### 4.3 action_tool（重构后）
**基本字段**：
```
action_tool: {
    step: number,             // 步骤序号
    execution_status: string, // 执行状态
    execution_result: any,    // 执行结果
    timestamp: number         // 毫秒级时间戳
}
```
**条件必需字段**：
- `error_message`: 错误信息（status="error"时必需）

**可选字段**：
- `execution_time_ms`: 执行耗时（毫秒）
- `summary`: 执行结果摘要
- `raw_data`: 原始数据
- `retry_count`: 重试次数

**execution_status可能的值**：
- `"success"`: 成功执行
- `"error"`: 执行失败
- `"timeout"`: 执行超时
- `"permission_denied"`: 权限不足

根据 execution_status 不同：
- 如果 "success": execution_result 必须有值
- 如果 "error": error_message 必须有值

### 4.4 observation（重构后）
**基本字段**：
```
observation: {
    step: number,             // 步骤序号
    tool_name: string,        // 工具名称（与对应的thought保持一致）
    content: string,      // 工具执行结果（原始数据）
    timestamp: number         // 毫秒级时间戳
}
```

**可选字段**：
- `return_direct`: 是否直接返回结果给用户（跳过后续推理）

### 4.5 final（重构后）

**生成时机**：LLM返回最终回答**时**（LLM响应）

**标准ReAct的ResponseReasoningStep**：
```python
class ResponseReasoningStep(BaseReasoningStep):
    thought: str      # 最终推理过程
    response: str     # 最终回答
    is_streaming: bool = False  # 是否流式输出
```
**基本字段**：
```
final: {
    step: number,           // 步骤序号
    response: string,       // 最终回答内容
    is_finished: boolean,   // 是否结束（业务完成标志）
    timestamp: number       // 毫秒级时间戳
}
```

**可选字段**：
- `thought`: 最终推理总结
- `is_streaming`: 是否流式输出

**step序号规则**：
-step=next_step()

**可选的统计字段**（框架层面，非Step必须）：
- `total_steps`: 总执行步骤数
- `total_tokens`: 总使用token数
- `usage`: 使用统计

**从loop到final的跳转机制**：

**识别规则**：LLM返回的内容匹配最终答案模式（见5.1.1统一解析器）
```
格式1: Thought: <推理内容>\nAnswer: <最终回答>  → _parse_answer()
格式2: 纯文本（无Thought/Action/Answer标记）   → 隐式回答兜底
格式3: 纯文本包含完成关键词                    → 需Agent额外判断
```

**跳转流程**：
```
步骤N: LLM返回 → 解析
  ↓
判断是否是最终答案
  ↓
是 → 生成type='final'步骤
  ↓
结束循环
```
**ReAct循环的完整终止条件**：

> ⚠️ **注意**：以下4种条件都会终止ReAct循环，但只有条件2生成type='final'步骤，其他条件生成type='error'或type='incident'步骤。

| 条件 | 说明 | 生成的type | 触发时机 |
|------|------|-----------|----------|
| `LLM返回final` | LLM输出最终答案 | `final` | LLM响应包含Answer或完成关键词 |
| `max_steps` | 超过最大步骤数 | `error` | step计数达到限制 |
| `工具执行错误` | 不可恢复的工具错误 | `error` | 工具执行失败且无法重试 |
| `用户中断` | 用户主动停止 | `incident` | 用户请求停止（interrupted/paused） |


### 4.6 error（重构后）
**基本字段**：
```
error: {
    step: number,           // 步骤序号（在整个ReAct流程中的顺序）
    error_type: string,     // 错误类型
    error_message: string,  // 错误信息
    timestamp: number,      // 毫秒级时间戳
    recoverable: boolean    // 是否可恢复
}
```

**可选字段**：
- `stack_trace`: 堆栈跟踪
- `context`: 错误上下文
- `suggested_fix`: 建议修复
- `retry_suggestion`: 重试建议

**error_type可能的值**：
- `"max_steps_exceeded"`: 超过最大步数
- `"llm_error"`: LLM调用错误
- `"tool_error"`: 工具执行错误
- `"parsing_error"`: 解析错误
- `"network_error"`: 网络错误
- `"permission_error"`: 权限不足
**step序号规则**：
step=next_step()

### 4.7 chunk（重构后）
**基本字段**：
```
chunk: {
    content: string,        // 累积的完整内容（delta累加）
    delta: string,          // 增量内容（相对于前一个chunk）
    is_final: boolean,      // 是否是最后一个chunk
    timestamp: number       // 毫秒级时间戳
}
```

**说明**：
- 用于LLM流式输出时的中间内容
- 前端用于实时显示AI回复

**生成时机**：LLM流式返回**时**（LLM响应）

**字段说明**：
| 字段 | 说明 | 必需性 |
|------|------|--------|
| `content` | 累积的完整文本内容 | ✅ 必须 |
| `delta` | 当前chunk相对于前一个的增量 | ✅ 必须 |
| `is_final` | 是否是最后一个chunk（流式结束标志） | ✅ 必须 |
| `timestamp` | 毫秒级时间戳 | ✅ 必须 |

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
---

## 4.8 当前代码字段定义（2026-04-11 修正版）

> ⚠️ **说明**：以下字段定义为当前代码实际实现，已根据代码核对修正

### 4.8.1 start 类型

**后端实现** (file_react.py):
```python
{
    'type': 'start',
    'step': next_step(),
    'timestamp': create_timestamp(),
    'display_name': f"{ai_service.provider} ({ai_service.model})",
    'provider': ai_service.provider,
    'model': ai_service.model,
    'task_id': task_id,
    'user_message': user_message[:40] if user_message else "",
    'security_check': {
        'is_safe': ...,
        'risk_level': ...,
        'risk': ...,
        'blocked': ...
    }
}
```

---

### 4.8.2 thought 类型

**后端实现** (llm_strategies.py:430-455):
```python
formatted = {
    "thought": f"Calling tool: {func_name}",
    "tool_name": func_name,      # ✅ 统一使用 tool_name
    "tool_params": args          # ✅ 统一使用 tool_params
}
```

**base_react.py yield**:
```python
yield {
    "type": "thought",
    "step": step_count,
    "timestamp": current_time,
    "content": thought_content,
    "tool_name": tool_name,       # ✅ 已统一
    "tool_params": tool_params    # ✅ 已统一
}
```

**字段说明**：
| 字段 | 说明 | 状态 |
|------|------|------|
| `step` | 步骤序号 | ✅ 已实现 |
| `timestamp` | 毫秒级时间戳 | ✅ 已实现 |
| `content` | LLM的推理内容 | ✅ 已实现 |
| `tool_name` | 工具名称 | ✅ 已统一（2026-04-08） |
| `tool_params` | 工具参数 | ✅ 已统一（2026-04-08） |

---

### 4.8.3 action_tool 类型

**后端实现** (base_react.py):
```python
yield {
    "type": "action_tool",
    "content": action_tool,
    "step": step_count,
    "timestamp": current_time,
    "tool_name": action_tool,
    "tool_params": params,
    "execution_status": execution_result.get("status", "success"),
    "summary": execution_result.get("summary", ""),
    "raw_data": execution_result.get("data"),
    "action_retry_count": execution_result.get("retry_count", 0)
}
```

---

### 4.8.4 observation 类型

**后端实现** (base_react.py:270-295):
```python
# 构建 observation 文本（包含原始数据）
raw_data = execution_result.get('data')
if raw_data:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}\n实际数据: {raw_data}"
else:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"

yield {
    "type": "observation",
    "step": step_count,
    "timestamp": create_timestamp(),
    "tool_name": tool_name,
    "content": f"Tool '{tool_name}' executed: {execution_result.get('summary', 'completed')}"
}
```

**⚠️ 重要修正**：observation 的 content 字段包含"实际数据: {raw_data}"，会显示工具执行的原始结果。

---

### 4.8.5 final 类型

**后端实现** (base_react.py):
```python
yield {
    "type": "final",
    "timestamp": current_time,
    "content": params.get("result", thought_content)
}
```

> ⚠️ **重要说明**：step字段由sse_wrapper层自动添加，final yield时不设置step，由框架统一处理。

**字段说明**：
| 字段 | 说明 | 状态 |
|------|------|------|
| `step` | 步骤序号（sse_wrapper自动添加） | ✅ 已实现 |
| `timestamp` | 毫秒级时间戳 | ✅ 已实现 |
| `content` | 最终回答内容 | ✅ 已实现 |

---

### 4.8.6 error 类型

**后端实现** (base_react.py):
```python
yield {
    "type": "error",
    "timestamp": create_timestamp(),
    "code": "MAX_STEPS_EXCEEDED",
    "message": f"已达到最大迭代次数 {max_steps}"
}
```

---

### 4.8.7 字段说明（2026-04-11 修正版）

| type | 字段 | 说明 |
|------|------|------|
| start | step, timestamp, display_name, provider, model, task_id, user_message, security_check | 对话开始时生成 |
| thought | step, timestamp, content, tool_name, tool_params, reasoning | LLM返回后解析生成 |
| action_tool | step, timestamp, content, tool_name, tool_params, execution_status, summary, raw_data, action_retry_count | 工具执行后生成 |
| observation | step, timestamp, tool_name, content | 工具执行结果（包含原始数据） |
| final | timestamp, content | action_tool=="finish"时生成 |
| error | timestamp, code, message | 发生错误时生成 |

**说明**: step字段由sse_wrapper层自动添加，不需要在agent代码中手动设置

**更新时间**: 2026-04-11 21:02:42
**编写人**: 小沈

---

## 五、type字段设计的值的构建说明
### 5.1  type字段值的生成与填写 总则
**type的字段值的原则**： agent在loop中填写，然后yield给前端显示步骤想详细信息，便于用户了解agent、LLM、tool的运行情况（输出）
1.start是进行loop前，由agent填写
2.thought的字段在是agent解析LLM的返回结果填写
3.action_tool的字段在是action tool执行后agent根据执行情况、返回结果填写
4.observation的字段 工具执行结果（原始数据，不是LLM总结）由agent根据tool的执行结构填写
5.final,LLM返回最终答案
6.error | Agent程序填写错误信息程序 

 **各type字段的值来源**：

| type | 生成时机 | 数据来源 | 填写者 |
|------|----------|----------|--------|
| `start` | 对话开始时 | 框架生成 | Agent程序 |
| `thought` | LLM返回后 | 解析LLM响应 | Agent程序 |
| `action_tool` | LLM返回后 | 解析LLM响应 | Agent程序 |
| `observation` | 工具执行后 | 工具返回结果 | Agent程序 |
| `final` | LLM返回最终答案 | 解析LLM响应 | Agent程序 |
| `error` | 发生错误时 | 错误信息 | Agent程序 |

**核心原则**：除start外，所有type字段都在LLM调用后或工具执行后填充

### 5.1.1 ReAct输出统一解析器设计

> ⚠️ **设计依据**：参考 LlamaIndex ReAct Output Parser 实际源码（`llama_index.core.agent.react.output_parser`）

**设计目标**：用一个统一的解析器入口处理LLM的所有ReAct输出格式，避免多个独立解析器导致的调用时机不明确问题。

**LLM输出的3种格式**（支持中英文关键词）：

| 格式 | 英文示例 | 中文示例 | 对应type | 说明 |
|------|---------|---------|---------|------|
| **Action格式** | `Thought: xxx\nAction: tool\nAction Input: {json}` | `思考: xxx\n行动: tool\n工具参数: {json}` | thought + action_tool | 需要调用工具 |
| **Answer格式** | `Thought: xxx\nAnswer: xxx` | `思考: xxx\n回答: xxx` | final | 最终回答 |
| **隐式格式** | 纯文本（无标记） | 纯文本（无标记） | final | LLM直接回答 |

**统一解析器实现**：

```python
import re
import json
from typing import Dict, Any

# 中英文关键词映射（LLM可能输出任意一种）
REACT_KEYWORDS = {
    "thought": r"(?:Thought|思考|推理):\s*",
    "action": r"(?:Action|行动|工具调用):\s*",
    "action_input": r"(?:Action Input|工具参数|输入):\s*",
    "answer": r"(?:Answer|回答|最终答案):\s*",
}


def parse_react_response(output: str) -> Dict[str, Any]:
    """
    统一解析LLM的ReAct输出，返回结构化结果。
    
    设计依据：LlamaIndex ReActOutputParser.parse() 实际源码
    关键改进：支持中英文关键词（Thought/思考、Action/行动、Answer/回答）
    
    返回格式:
    {
        "type": "action" | "answer" | "implicit",
        "thought": str | None,
        "tool_name": str | None,
        "tool_params": dict | None,
        "response": str | None
    }
    """
    # 定位关键词位置（支持中英文，LlamaIndex的核心判断逻辑）
    thought_match = re.search(REACT_KEYWORDS["thought"], output, re.MULTILINE | re.IGNORECASE)
    action_match = re.search(REACT_KEYWORDS["action"], output, re.MULTILINE | re.IGNORECASE)
    answer_match = re.search(REACT_KEYWORDS["answer"], output, re.MULTILINE | re.IGNORECASE)
    
    thought_idx = thought_match.start() if thought_match else None
    action_idx = action_match.start() if action_match else None
    answer_idx = answer_match.start() if answer_match else None
    
    # 情况1：都没有匹配 → 隐式回答（LLM直接回答，无需工具）
    if all(i is None for i in [thought_idx, action_idx, answer_idx]):
        return {
            "type": "implicit",
            "thought": "(Implicit) I can answer without any more tools!",
            "tool_name": None,
            "tool_params": None,
            "response": output.strip()
        }
    
    # 情况2：Action 优先于 Answer（LlamaIndex规则）
    if action_idx is not None and (answer_idx is None or action_idx < answer_idx):
        return _parse_action(output)
    
    # 情况3：有Answer → 最终回答
    if answer_idx is not None:
        return _parse_answer(output)
    
    # 情况4：只有Thought没有Action/Answer → 纯思考（罕见）
    return {
        "type": "thought_only",
        "thought": output.strip(),
        "tool_name": None,
        "tool_params": None,
        "response": None
    }


def _parse_action(output: str) -> Dict[str, Any]:
    """
    解析工具调用格式：Thought + Action + Action Input
    
    支持格式：
    - 英文: Thought: xxx\nAction: tool_name\nAction Input: {json}
    - 中文: 思考: xxx\n行动: tool_name\n工具参数: {json}
    - 混合: Thought: xxx\nAction: tool_name\n工具参数: {json}
    
    正则设计依据：LlamaIndex extract_tool_use() 实际源码
    关键改进：
    1. 工具名称约束 [^\n\(\) ]+：不允许空格和括号（防止LLM输出带参数的工具名）
    2. Thought可选前缀：没有Thought/思考标记时捕获整行
    3. Action Input使用 .*?(\{.*\})：非贪婪匹配，确保捕获到JSON对象
    4. 支持中英文关键词
    """
    # 支持中英文关键词的正则
    thought_kw = r"(?:Thought|思考|推理)"
    action_kw = r"(?:Action|行动|工具调用)"
    input_kw = r"(?:Action Input|工具参数|输入)"
    
    pattern = (
        rf"(?:\s*{thought_kw}:\s*(.*?)\n+|(.+?)\n+)"
        rf"{action_kw}:\s*([^\n\(\) ]+)"
        rf".*?\n+{input_kw}:\s*(\{{.*\}})"
    )
    match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"无法解析Action格式: {output}")
    # Thought内容：优先group(1)，无Thought标记时用group(2)（整行）
    thought = (match.group(1) or match.group(2) or "").strip()
    return {
        "type": "action",
        "thought": thought,
        "tool_name": match.group(3).strip(),
        "tool_params": _parse_action_input(match.group(4)),
        "response": None
    }


def _parse_answer(output: str) -> Dict[str, Any]:
    """
    解析最终回答格式：Thought + Answer
    
    支持格式：
    - 英文: Thought: xxx\nAnswer: xxx
    - 中文: 思考: xxx\n回答: xxx
    - 混合: Thought: xxx\n最终答案: xxx
    
    正则设计依据：LlamaIndex extract_final_response() 实际源码
    关键改进：
    1. \s*Thought: 允许Thought:前面有空格或换行
    2. (.*?)Answer: 非贪婪匹配，确保Thought内容不包含Answer关键词
    3. (.*?)$ 匹配到末尾的所有内容（支持多行回答）
    4. 支持中英文关键词
    """
    # 支持中英文关键词的正则
    thought_kw = r"(?:Thought|思考|推理)"
    answer_kw = r"(?:Answer|回答|最终答案)"
    
    pattern = rf"\s*{thought_kw}:\s*(.*?){answer_kw}:\s*(.*?)$"
    match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"无法解析Answer格式: {output}")
    return {
        "type": "answer",
        "thought": match.group(1).strip(),
        "tool_name": None,
        "tool_params": None,
        "response": match.group(2).strip()
    }


def _parse_action_input(json_str: str) -> dict:
    """
    降级JSON解析策略（参考LlamaIndex action_input_parser 实际实现）：
    
    LlamaIndex的解析策略：
    1. 先尝试标准json.loads
    2. 失败后替换单引号为双引号（LLM常用单引号输出JSON）
    3. 最后用正则提取 key: value（最坏情况兜底）
    
    额外改进：支持 extract_json_str 从复杂文本中提取JSON片段
    """
    # 第1级：标准JSON解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 第2级：从复杂文本中提取JSON片段（参考LlamaIndex extract_json_str）
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str)
    if json_match:
        extracted = json_match.group(0)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
    
    # 第3级：替换单引号为双引号（LLM常见输出格式）
    processed = re.sub(r"(?<!\w)\'|\'(?!\w)", '"', json_str)
    try:
        return json.loads(processed)
    except json.JSONDecodeError:
        pass
    
    # 第4级：正则提取 key: value（最坏情况兜底）
    # LlamaIndex原始正则：r'"(\w+)":\s*"([^"]*)"'
    pattern = r'"(\w+)":\s*"([^"]*)"'
    matches = re.findall(pattern, processed)
    if matches:
        return dict(matches)
    
    # 最终兜底：返回空对象
    return {}
```

**Agent主循环中的调用流程**：

```python
async def run_react_loop(self, user_task: str):
    """ReAct主循环"""
    # 1. 生成start步骤
    yield self.build_start_step(user_task)
    
    while True:
        # 2. 调用LLM
        llm_output = await self.llm.generate(messages)
        
        # 3. 统一解析（一个入口）
        parsed = parse_react_response(llm_output)
        
        if parsed["type"] == "action":
            # 3a. 工具调用流程
            # 生成thought步骤（含tool_name和tool_params）
            yield self.build_thought_step(parsed)
            
            # 执行工具
            result, status = await self.execute_tool(
                parsed["tool_name"], 
                parsed["tool_params"]
            )
            
            # 生成action_tool步骤
            yield self.build_action_tool_step(result, status)
            
            # 生成observation步骤
            yield self.build_observation_step(
                parsed["tool_name"],
                parsed["tool_params"],
                result
            )
            
            # 注入observation到messages，继续下一轮loop
            messages.append({"role": "user", "content": result})
            continue
            
        elif parsed["type"] in ("answer", "implicit"):
            # 3b. 最终回答流程
            yield self.build_final_step(parsed)
            break
```


**设计优势**：

| 优势 | 说明 |
|------|------|
| **一个入口** | `parse_react_response()` 统一处理所有格式，Agent无需判断调用哪个解析器 |
| **优先级明确** | Action 优先于 Answer（与LlamaIndex一致），避免格式混淆 |
| **兜底处理** | 隐式格式兜底，LLM不遵循标记格式时也能处理 |
| **降级解析** | JSON解析4级降级（标准→提取片段→替换引号→正则提取→空对象），提高容错性 |
| **职责清晰** | 解析器只负责解析，Agent只负责流程控制，符合单一职责原则 |

**正则表达式详解**（参考LlamaIndex实际实现）：

| 正则 | 用途 | 关键设计 |
|------|------|---------|
| `r"(?:Thought|思考\|推理):\s*"` | 定位Thought标记（中英文） | 支持3种中文变体，IGNORECASE |
| `r"(?:Action|行动\|工具调用):\s*"` | 定位Action标记（中英文） | 支持3种中文变体，IGNORECASE |
| `r"(?:Answer|回答\|最终答案):\s*"` | 定位Answer标记（中英文） | 支持3种中文变体，IGNORECASE |
| `r"(?:\s*(?:Thought\|思考):...Action:...Action Input:\{.*\})"` | 捕获Action格式4个字段 | `[^\n\(\) ]+` 工具名不允许空格括号 |
| `r"\s*(?:Thought\|思考):...(?:Answer\|回答):...$"` | 捕获Answer格式2个字段 | `\s*` 允许前导空格；`.*?$` 支持多行 |
| `r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'` | 从复杂文本中提取JSON片段 | 支持单层嵌套JSON |
| `r'"(\w+)":\s*"([^"]*)"'` | 正则提取key-value对 | 最坏情况兜底 |

**前端应用建议**
1. **前端渲染**：根据每个Type的核心字段设计前端组件
2. **数据存储**：设计数据库表结构时参考核心字段
3. **API设计**：定义SSE事件结构时使用核心字段
4. **测试用例**：基于核心字段设计测试用例
5. **文档规范**：作为系统设计的参考规范

#### 5.1.3 LlamaIndex ReasoningStep 基类参考设计

> ⚠️ **设计依据**：参考 LlamaIndex `llama_index.core.agent.react.types` 实际源码

**LlamaIndex的4个ReasoningStep核心设计思想**：

| LlamaIndex类型 | 字段 | is_done | 说明 | 对应我们的type |
|---------------|------|---------|------|---------------|
| `BaseReasoningStep` | 无（抽象基类） | 抽象 | 定义 `get_content()` 和 `is_done` 接口 | 所有type的基类 |
| `ActionReasoningStep` | `thought`, `action`, `action_input` | False | LLM决定调用工具 | thought（含tool_name/tool_params） |
| `ObservationReasoningStep` | `observation`, `return_direct` | =return_direct | 工具执行结果 | observation |
| `ResponseReasoningStep` | `thought`, `response`, `is_streaming` | True | 最终回答 | final |

**关键对照分析**：

| 问题 | 说明 |
|------|------|
| **LlamaIndex的ActionReasoningStep对应我们的thought** | LlamaIndex把thought+action+action_input放在一个类里，我们的thought也有content+tool_name+tool_params，**完全对应** |
| **我们的action_tool不是多余的** | LlamaIndex只关心"调用什么工具"，不关心"执行结果如何"。我们的action_tool记录execution_status/execution_result/error_message，是Agent执行需要的，**不是拆分，是职责扩展** |
| **LlamaIndex没有action_tool对应物** | 因为LlamaIndex的ReasoningStep只表示"推理步骤"，不表示"执行步骤"。我们的设计把推理和执行分开，更清晰 |

**基类设计参考**（Python实现）：

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ReasoningStep(ABC):
    """
    ReAct推理步骤基类（参考LlamaIndex BaseReasoningStep）
    
    核心接口：
    - get_content(): 获取用户可见的文本内容
    - is_done(): 判断是否结束ReAct循环
    - to_dict(): 转换为前端type字段格式
    """
    
    def __init__(self, step: int, timestamp: int):
        self.step = step
        self.timestamp = timestamp
    
    @abstractmethod
    def get_content(self) -> str:
        """获取用户可见的文本内容（用于前端显示）"""
    
    @abstractmethod
    def is_done(self) -> bool:
        """判断是否结束ReAct循环"""
    
    @abstractmethod
    def get_type(self) -> str:
        """获取对应的type字段值"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为前端type字段格式（SSE事件data）"""
        return {
            "type": self.get_type(),
            "step": self.step,
            "timestamp": self.timestamp,
            "content": self.get_content(),
        }


# 各type对应的实现类参考

class ThoughtStep(ReasoningStep):
    """
    思考步骤（对应LlamaIndex ActionReasoningStep）
    字段：content + tool_name + tool_params
    """
    def __init__(self, step: int, timestamp: int, 
                 content: str, tool_name: str = "", tool_params: dict = None):
        super().__init__(step, timestamp)
        self.content = content
        self.tool_name = tool_name
        self.tool_params = tool_params or {}
    
    def get_content(self) -> str:
        return self.content
    
    def is_done(self) -> bool:
        return False  # 思考后必须执行工具
    
    def get_type(self) -> str:
        return "thought"
    
    def has_action(self) -> bool:
        """是否需要调用工具"""
        return bool(self.tool_name)


class ActionToolStep(ReasoningStep):
    """
    工具执行步骤（我们的扩展，LlamaIndex没有对应类）
    字段：execution_status + execution_result + error_message
    """
    def __init__(self, step: int, timestamp: int,
                 execution_status: str, execution_result: Any = None,
                 error_message: str = ""):
        super().__init__(step, timestamp)
        self.execution_status = execution_status
        self.execution_result = execution_result
        self.error_message = error_message
    
    def get_content(self) -> str:
        if self.execution_status == "success":
            return f"工具执行成功: {self.execution_result}"
        return f"工具执行失败: {self.error_message}"
    
    def is_done(self) -> bool:
        return False  # 工具执行后必须生成observation
    
    def get_type(self) -> str:
        return "action_tool"


class ObservationStep(ReasoningStep):
    """
    观察步骤（对应LlamaIndex ObservationReasoningStep）
    字段：observation + tool_name + tool_params + return_direct
    """
    def __init__(self, step: int, timestamp: int,
                 observation: str, tool_name: str = "", 
                 tool_params: dict = None, return_direct: bool = False):
        super().__init__(step, timestamp)
        self.observation = observation
        self.tool_name = tool_name
        self.tool_params = tool_params or {}
        self.return_direct = return_direct
    
    def get_content(self) -> str:
        return self.observation
    
    def is_done(self) -> bool:
        return self.return_direct  # 工具说直接返回就结束
    
    def get_type(self) -> str:
        return "observation"


class FinalStep(ReasoningStep):
    """
    最终回答步骤（对应LlamaIndex ResponseReasoningStep）
    字段：response + is_finished + thought + is_streaming
    """
    def __init__(self, step: int, timestamp: int,
                 response: str, thought: str = "", is_streaming: bool = False):
        super().__init__(step, timestamp)
        self.response = response
        self.is_finished = True  # final表示业务完成
        self.thought = thought
        self.is_streaming = is_streaming
    
    def get_content(self) -> str:
        if self.is_streaming:
            return f"思考: {self.thought}\n回答 (开始): {self.response} ..."
        return f"思考: {self.thought}\n回答: {self.response}"
    
    def is_done(self) -> bool:
        return True  # 永远结束循环
    
    def get_type(self) -> str:
        return "final"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为前端type字段格式（包含is_finished）"""
        return {
            "type": self.get_type(),
            "step": self.step,
            "timestamp": self.timestamp,
            "response": self.response,
            "is_finished": self.is_finished,
            "thought": self.thought,
            "is_streaming": self.is_streaming,
        }


class ErrorStep(ReasoningStep):
    """
    错误步骤（我们的扩展，LlamaIndex没有对应类）
    字段：error_type + error_message + recoverable
    """
    def __init__(self, step: int, timestamp: int,
                 error_type: str, error_message: str, recoverable: bool = False):
        super().__init__(step, timestamp)
        self.error_type = error_type
        self.error_message = error_message
        self.recoverable = recoverable
    
    def get_content(self) -> str:
        return f"错误 [{self.error_type}]: {self.error_message}"
    
    def is_done(self) -> bool:
        return True  # 错误结束循环
    
    def get_type(self) -> str:
        return "error"
```

**is_done 循环控制机制**：

| type | is_done | 说明 |
|------|---------|------|
| thought | `False` | 思考后必须执行工具 |
| action_tool | `False` | 工具执行后必须生成observation |
| observation | `return_direct` | 工具说直接返回就结束，否则继续LLM |
| final | `True` | 永远结束循环 |
| error | `True` | 错误结束循环 |

**使用示例**：

```python
# Agent主循环中使用基类
async def run_react_loop(self, user_task: str):
    steps: list[ReasoningStep] = []
    
    while True:
        # 1. 调用LLM
        llm_output = await self.llm.generate(messages)
        parsed = parse_react_response(llm_output)
        
        if parsed["type"] == "action":
            # 2. 生成thought步骤
            thought = ThoughtStep(
                step=self.next_step(),
                timestamp=int(time.time() * 1000),
                content=parsed["thought"],
                tool_name=parsed["tool_name"],
                tool_params=parsed["tool_params"]
            )
            steps.append(thought)
            yield thought.to_dict()
            
            # 3. 执行工具
            result, status = await self.execute_tool(...)
            action = ActionToolStep(
                step=self.next_step(),
                timestamp=int(time.time() * 1000),
                execution_status=status,
                execution_result=result
            )
            steps.append(action)
            yield action.to_dict()
            
            # 4. 生成observation
            obs = ObservationStep(
                step=self.next_step(),
                timestamp=int(time.time() * 1000),
                observation=str(result),
                tool_name=parsed["tool_name"],
                tool_params=parsed["tool_params"]
            )
            steps.append(obs)
            yield obs.to_dict()
            
            # 5. 检查是否直接返回
            if obs.is_done():
                # 直接返回，跳过LLM
                final = FinalStep(
                    step=self.next_step(),
                    timestamp=int(time.time() * 1000),
                    response=str(result),
                    thought=parsed["thought"]
                )
                steps.append(final)
                yield final.to_dict()
                break
            
            # 6. 继续下一轮LLM
            messages.append({"role": "user", "content": str(result)})
            continue
            
        elif parsed["type"] in ("answer", "implicit"):
            final = FinalStep(
                step=self.next_step(),
                timestamp=int(time.time() * 1000),
                response=parsed["response"],
                thought=parsed.get("thought", "")
            )
            steps.append(final)
            yield final.to_dict()
            break
```

### 5.2 type字段值的生成与填写详细说明及前端的使用建议

#### 5.2.1 start 字段的生成与填写

**生成时机**：对话开始时，在LLM调用前由Agent程序生成

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 固定值 `1` | Agent程序硬编码 | `1` |
| `model` | 从LLM配置对象中读取 `model_name` 属性 | LLM配置 | `"glm-4"` |
| `provider` | 从LLM配置对象中读取 `provider` 属性 | LLM配置 | `"zhipu"` |
| `display_name` | 从LLM配置对象中读取 `display_name` 属性 | LLM配置 | `"智谱GLM-4"` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566400000` |
| `session_id` | 从会话管理器中获取当前会话ID | 会话管理模块 | `"sess_abc123"` |
| `task` | 从用户输入消息中提取任务描述 | 用户输入 | `"帮我查找/home目录下的文件"` |
| `user_message` | 用户原始消息内容 | 用户输入消息 | `"帮我查找/home目录下的所有txt文件"` |
| `security_check` | 对用户消息进行安全检查后返回的结果对象 | 安全检查模块 | `{"passed": true, "risk_level": "low"}` |

**type=start 可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `agent_id` | 从Agent配置对象中读取 | Agent配置 |
| `max_steps` | 从会话配置中读取最大步数限制 | 会话配置 |
| `available_tools` | 从工具注册表中获取当前可用工具列表 | 工具注册表 |


**生成start_step代码示例**：
```python
def build_start_step(self, user_task: str, user_message: str, security_check: dict) -> dict:
    return {
        "type": "start",
        "step": 1,
        "model": self.llm_config.model_name,
        "provider": self.llm_config.provider,
        "display_name": self.llm_config.display_name,
        "timestamp": int(time.time() * 1000),
        "session_id": self.session_id,
        "task": user_task,
        "user_message": user_message,
        "security_check": security_check
    }
```
**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：start不参与构建prompt（仅前端展示用）
→ 说明：start是对话开始第一条记录，在LLM调用前生成，不拼接进LLM的prompt
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "start", "step": 1, "model": "...", "provider": "...", "display_name": "...", ...}
→ 示例：
{
    "type": "start",
    "step": 1,
    "model": "glm-4",
    "provider": "zhipu",
    "display_name": "智谱GLM-4",
    "session_id": "sess_abc123",
    "task": "帮我查找/home目录下的文件",
    "user_message": "帮我查找/home目录下的所有txt文件",
    "security_check": {"passed": true, "risk_level": "low"},
    "timestamp": 1743566400000
}
```


**type=start 的前端使用建议**：
- 显示为"对话开始"标记，展示模型信息和用户任务
- 可作为对话历史记录的首条记录
- 用于显示当前使用的模型和提供商信息

**对比现在的前端type=start显示方式分析**：

当前前端实现（`MessageItem.tsx:421-467`）：
```tsx
// start类型显示：用户消息 + 任务ID + 安全检查
<div style={getStepStyle("start")}>
  <div style={getStepTitleStyle("start")}>
    🚀 用户消息：{step.user_message || "(无)"}
  </div>
  <div>
    <span>任务ID：{step.task_id || "无"}</span>
    {step.security_check && (
      <span>安全：{step.security_check.is_safe ? "✅ 通过" : "⚠️ 拦截"}</span>
    )}
  </div>
</div>
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示"步骤N"徽章 |
| `model` | 未使用 | ❌ 缺失 | 前端未显示model信息 |
| `provider` | 未使用 | ❌ 缺失 | 前端未显示provider信息 |
| `display_name` | 未使用 | ❌ 缺失 | 前端未显示display_name |
| `session_id` | `step.task_id` | ⚠️ 不同 | 设计用session_id，前端用task_id |
| `task` | 未使用 | ❌ 缺失 | 前端未显示task字段 |
| `user_message` | `step.user_message` | ✅ 一致 | 标题行显示 |
| `security_check` | `step.security_check` | ✅ 一致 | 详细信息行显示 |

**需要修改的地方**：
1. `session_id` → 前端应改为 `step.session_id`，与后端字段名一致
2. `task` → 前端应显示 `step.task` 字段（用户任务描述）
3. `model/provider/display_name` → 建议在前端添加显示，格式：`模型：{display_name} ({provider}/{model})`

**修改建议代码**（`MessageItem.tsx` start部分）：
```tsx
// 添加模型信息行
{(step.model || step.provider || step.display_name) && (
  <div style={getStepContentStyle("start", "secondary")}>
    🤖 模型：{step.display_name || step.model} ({step.provider})
  </div>
)}
// 添加任务行
{step.task && (
  <div style={getStepContentStyle("start", "secondary")}>
    📋 任务：{step.task}
  </div>
)}
// session_id替代task_id
<span>会话ID：{step.session_id || "无"}</span>
```
---

#### 5.2.2 thought 字段的生成与填写

**生成时机**：LLM返回响应后，Agent程序解析LLM响应时生成

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 调用`next_step()`函数获得递增的step值 | Agent程序的step计数器 | `2`, `5`, `8` |
| `content` | 从LLM响应中解析出thought文本（去除"Thought:"前缀） | LLM返回内容 | `"我需要先查看目录结构"` |
| `tool_name` | 从LLM响应中解析出工具名称（无工具调用时为空） | LLM返回内容 | `"list_directory"` 或 `""` |
| `tool_params` | 从LLM响应中解析出工具参数（无工具调用时为空对象） | LLM返回内容 | `{"path": "/home"}` 或 `{}` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566405000` |

**type=thought 条件必需字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `tool_name` | LLM决定调用工具时从响应中解析，不调用工具时为空字符串 | LLM返回内容 |
| `tool_params` | LLM决定调用工具时从响应中解析JSON参数，不调用工具时为空对象 | LLM返回内容 |


**LlamaIndex 参考源码**（`ActionReasoningStep`）：
```python
# 来源: llama_index.core.agent.react.types
class ActionReasoningStep(BaseReasoningStep):
    """Action Reasoning step."""
    thought: str
    action: str           # 对应我们的 tool_name
    action_input: Dict    # 对应我们的 tool_params

    def get_content(self) -> str:
        return f"Thought: {self.thought}\nAction: {self.action}\nAction Input: {self.action_input}"

    @property
    def is_done(self) -> bool:
        return False  # 需要继续循环执行工具
```

**对照分析**：
- LlamaIndex的 `action` → 我们的 `tool_name`
- LlamaIndex的 `action_input` → 我们的 `tool_params`
- LlamaIndex的 `thought` → 我们的 `content`
- **完全对应**，只是字段命名不同
- LlamaIndex把tool_name/tool_params放在thought里，我们的设计一致

**生成thought_step代码示例**：
```python
def build_thought_step(self, parsed: dict) -> dict:
    """
    从统一解析器结果构建thought步骤。
    调用方：parsed = parse_react_response(llm_response)
    """
    return {
        "type": "thought",
        "step": self.next_step(),  # 调用next_step()获得独立递增的step值
        "content": parsed["thought"],
        "tool_name": parsed.get("tool_name", ""),
        "tool_params": parsed.get("tool_params", {}),
        "timestamp": int(time.time() * 1000)
    }
```

**我们构建 prompt 的函数（替代 LlamaIndex 的 get_content()）**：
```python
def build_prompt_from_history(steps: list[dict]) -> str:
    """从步骤历史构建 LLM prompt 片段（替代 LlamaIndex 的 get_content()）"""
    parts = []
    for s in steps:
        if s["type"] == "thought":
            parts.append(f"Thought: {s['content']}")
            if s["tool_name"]:
                parts.append(f"Action: {s['tool_name']}")
                parts.append(f"Action Input: {s['tool_params']}")
        elif s["type"] == "observation":
            parts.append(f"Observation: {s['observation']}")
        elif s["type"] == "final":
            parts.append(f"Thought: {s['content']}")
            parts.append(f"Final Answer: {s['response']}")
    return "\n".join(parts)
```

**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：f"Thought: {self.thought}\nAction: {self.action}\nAction Input: {self.action_input}"
→ 示例：Thought: 需要查天气\nAction: get_weather\nAction Input: {"city": "北京"}
→ 拼接："\n".join([step.get_content() for step in current_reasoning])
→ LLM收到的prompt片段：
    Thought: 需要查天气
    Action: get_weather
    Action Input: {"city": "北京"}
    Observation: 北京今天晴，25度
    Observation: （提示LLM继续）
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "thought", "step": 2, "content": "...", "tool_name": "...", "tool_params": {...}}
→ 示例：
{
    "type": "thought",
    "step": 2,
    "content": "需要查天气",
    "tool_name": "get_weather",
    "tool_params": {"city": "北京"},
    "timestamp": 1743566405000
}
```

**type=thought 前端使用建议**：
- 显示为"思考中"卡片，展示AI的推理过程
- 可同时展示AI决定调用的工具名称和参数
- 可使用折叠面板，默认收起，用户点击展开查看详情
- 使用不同颜色或图标区分正常思考和错误处理

**对比现在的前端type=thought显示方式分析**：

当前前端实现（`MessageItem.tsx:469-510`）：
```tsx
// thought类型显示：推理内容 + 下一步 + 参数
<div style={getStepStyle("thought")}>
  <span style={getStepContentStyle("thought", "primary")}>
    {step.reasoning || step.content || ""}
  </span>
  <div style={{...信息区域...}}>
    {(step as any).action_tool && (
      <div>⬇️ 下一步：{(step as any).action_tool}</div>
    )}
    {(step as any).params && Object.keys((step as any).params).length > 0 && (
      <div><JsonHighlight data={(step as any).params} /></div>
    )}
  </div>
</div>
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示"步骤N"徽章 |
| `content` | `step.reasoning \|\| step.content` | ⚠️ 兼容 | 前端优先读reasoning，兼容content |
| `tool_name` | `(step as any).action_tool` | ❌ 不一致 | 设计用tool_name，前端用action_tool |
| `tool_params` | `(step as any).params` | ❌ 不一致 | 设计用tool_params，前端用params |
| `timestamp` | 外层StepRow显示 | ✅ 一致 | 统一在StepRow右侧显示 |

**需要修改的地方**：
1. **字段名不一致**：设计文档用 `tool_name`/`tool_params`，前端用 `action_tool`/`params`
2. **content字段**：设计文档用 `content`，前端优先读 `reasoning`

**修改建议**（统一字段名，二选一）：
- **方案A（推荐）**：后端改为 `tool_name`/`tool_params`，前端同步修改
  ```tsx
  // 前端改为
  {step.tool_name && <div>⬇️ 下一步：{step.tool_name}</div>}
  {step.tool_params && <JsonHighlight data={step.tool_params} />}
  ```
- **方案B**：保持前端字段名，后端适配 `action_tool`/`params`

**内容显示**：前端使用 `step.reasoning || step.content` 是合理的，兼容两种字段名。建议后端统一使用 `content` 字段。

---

#### 5.2.3 action_tool 字段的生成与填写

**生成时机**：工具执行完成后，Agent程序根据工具执行情况生成

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 调用`next_step()`函数获得递增的step值 | Agent程序的step计数器 | `3`, `6`, `9` |
| `execution_status` | 工具执行后由Agent程序设置状态值 | 工具执行结果 | `"success"`, `"error"`, `"timeout"` |
| `execution_result` | 工具执行返回的原始结果 | 工具返回数据 | `["file1.txt", "file2.txt"]` |
| `error_message` | 工具执行失败时，从异常信息中提取（status="error"时必填） | 异常对象 | `"权限不足，无法访问该目录"` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566406000` |

**条件必需字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `error_message` | status="error"时从异常对象中提取，status="success"时不填 | 异常对象 |

**可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `execution_time_ms` | 工具执行前后记录时间差值 | Agent内部计时 |
| `summary` | 对execution_result进行摘要生成 | 工具返回数据 |
| `raw_data` | 工具返回的原始未处理数据 | 工具返回数据 |
| `retry_count` | Agent内部跟踪当前工具的重试次数 | Agent内部状态 |

**生成代码示例**：
```python
def build_action_tool_step(self, result: any, status: str, error_msg: str = None) -> dict:
    return {
        "type": "action_tool",
        "step": self.next_step(),  # 调用next_step()获得独立递增的step值
        "execution_status": status,
        "execution_result": result,
        "error_message": error_msg,
        "retry_count": self.retry_count,
        "timestamp": int(time.time() * 1000)
    }
```

**前端type=action_tool 使用建议**：
- 显示为"工具执行"卡片，展示执行状态和结果
- 工具名称和参数从上一个thought步骤获取
- 根据 `execution_status` 显示不同状态图标（成功/失败/超时）
- 支持展开查看完整的执行结果和错误信息
- 失败时显示重试次数和错误提示

**对比现在的前端type=action_tool显示方式分析**：

当前前端实现（`MessageItem.tsx:218-308`）：
```tsx
// action_tool类型显示：工具名 + 参数(可展开) + 工具视图 + 状态/摘要
{step.type === "action_tool" && (
  <>
    {step.action_description || step.tool_name || "执行中..."}
    {step.tool_params && (
      <div onClick={() => toggleExpand(...) }>
        <JsonHighlight data={step.tool_params} />
        <span>{expanded ? "▲ 收起" : "▼ 展开"}</span>
      </div>
    )}
    {renderToolResult(step, isExpanded, toggleExpand, stepIndex)}
    {(step as any).execution_status && (
      <div>📊 状态：{(step as any).execution_status} | 摘要：{(step as any).summary}</div>
    )}
  </>
)}
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示 |
| `execution_status` | `(step as any).execution_status` | ⚠️ 类型断言 | 前端用any类型断言 |
| `execution_result` | 未直接使用 | ❌ 缺失 | 前端通过`renderToolResult`从`raw_data`读取 |
| `error_message` | 未显示 | ❌ 缺失 | 前端未显示error_message |
| `tool_name` | `step.tool_name` | ✅ 一致 | 显示工具名 |
| `tool_params` | `step.tool_params` | ✅ 一致 | 可展开显示参数 |
| `retry_count` | 未显示 | ❌ 缺失 | 前端未显示重试次数 |

**`renderToolResult` 分支函数**（`MessageItem.tsx:572-618`）：
```tsx
const renderToolResult = (step, isExpanded, toggleExpand, stepIndex) => {
  const data = step.raw_data?.data || step.raw_data;
  switch (step.tool_name) {
    case "list_directory": return <ListDirectoryView data={data} ... />;
    case "read_file": return <ReadFileView data={data} />;
    case "write_file": return <WriteFileView data={data} />;
    case "delete_file": return <DeleteFileView data={data} />;
    case "move_file": return <MoveFileView data={data} />;
    case "search_files": return <SearchFilesView data={transformedData} />;
    case "search_file_content": return <SearchFileContentView data={transformedData} />;
    case "generate_report": return <GenerateReportView data={data} ... />;
    default: return <pre>{JSON.stringify(data, null, 2)}</pre>;
  }
};
```

**需要修改的地方**：
1. **execution_result**：前端通过 `raw_data` 间接读取，建议直接使用 `execution_result`
2. **error_message**：前端未显示，建议添加错误信息显示
3. **retry_count**：前端未显示，建议添加重试次数显示
4. **action_description**：前端有但设计文档无此字段，建议保留作为可选字段

**修改建议**：
```tsx
// 添加错误信息显示
{(step as any).execution_status === "error" && (step as any).error_message && (
  <div style={{ color: "#ff4d4f", fontSize: 12, marginTop: 6 }}>
    ❌ 错误：{(step as any).error_message}
  </div>
)}
// 添加重试次数显示
{(step as any).retry_count > 0 && (
  <div style={{ fontSize: 12, color: "#666" }}>
    🔄 重试次数：{(step as any).retry_count}
  </div>
)}
```

---
**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：action_tool不参与构建prompt（仅前端展示用）
→ 说明：action_tool是工具执行结果，不拼接进LLM的prompt
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "action_tool", "step": 3, "execution_status": "...", "execution_result": "...", ...}
→ 示例：
{
    "type": "action_tool",
    "step": 3,
    "execution_status": "success",
    "execution_result": "北京今天晴，25度",
    "error_message": null,
    "timestamp": 1743566406000
}
```

#### 5.2.4 observation 字段的生成与填写

**生成时机**：工具执行返回结果后，Agent程序直接生成（不经过LLM）

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 调用`next_step()`函数获得递增的step值 | Agent程序的step计数器 | `4`, `7`, `10` |
| `tool_name` | 从对应的thought step中复制 | 上一步thought | `"list_directory"` |
| `tool_params` | 从对应的thought step中复制 | 上一步thought | `{"path": "/home"}` |
| `observation` | 工具执行返回的原始结果（字符串形式） | 工具返回数据 | `"找到3个文件：file1.txt, file2.txt, file3.txt"` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566407000` |

**type=observation可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `return_direct` | 根据工具配置判断是否直接返回 | 工具配置 |

**LlamaIndex 参考源码**（`ObservationReasoningStep`）：
```python
# 来源: llama_index.core.agent.react.types
class ObservationReasoningStep(BaseReasoningStep):
    """Observation reasoning step."""
    observation: str
    return_direct: bool = False  # 直接返回标志

    def get_content(self) -> str:
        return f"Observation: {self.observation}"

    @property
    def is_done(self) -> bool:
        return self.return_direct  # 如果 return_direct=True，直接结束循环
```

**对照分析**：
- LlamaIndex的 `observation` → 我们的 `observation`
- LlamaIndex的 `return_direct` → 我们的 `return_direct`
- **完全一致**
- 关键设计：`is_done = return_direct`，工具决定是否需要继续LLM推理
- 我们的observation还额外记录了 `tool_name` 和 `tool_params`（从thought复制），便于前端渲染

**生成observation_step代码示例**：
```python
def build_observation_step(self, tool_name: str, tool_params: dict, 
                           raw_result: str, return_direct: bool = False) -> dict:
    return {
        "type": "observation",
        "step": self.next_step(),  # 调用next_step()获得独立递增的step值
        "tool_name": tool_name,
        "tool_params": tool_params,
        "observation": raw_result,
        "return_direct": return_direct,
        "timestamp": int(time.time() * 1000)
    }
```
**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：f"Observation: {self.observation}"
→ 示例：Observation: 北京今天晴，25度
→ 拼接：build_prompt_from_history()中每个observation步骤会拼接进LLM的prompt
→ LLM收到的prompt片段：
    Thought: 需要查天气
    Action: get_weather
    Action Input: {"city": "北京"}
    Observation: 北京今天晴，25度
    Observation: （提示LLM继续思考下一步）
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "observation", "step": 4, "tool_name": "...", "observation": "...", ...}
→ 示例：
{
    "type": "observation",
    "step": 4,
    "tool_name": "get_weather",
    "tool_params": {"city": "北京"},
    "observation": "北京今天晴，25度",
    "return_direct": false,
    "timestamp": 1743566407000
}
```

**type=observation 前端使用建议**：
- 显示为"工具结果"卡片，展示工具执行的原始输出
- 与thought卡片配对显示，形成"决定→执行→结果"的视觉关联
- **根据 `tool_name` 和 `tool_params` 选择合适的视图组件渲染原始数据**：
  - `list_directory` / `dir`：目录列表视图
    - 纯文件列表模式：简单展示文件名和大小
    - 带递归的目录树模式：支持展开/折叠子目录
  - `search_file` / `find_files`：文件搜索视图
    - 纯文件列表模式：展示匹配的文件路径
    - 带搜索内容的文件内容视图：高亮显示匹配的文件内容片段
  - `read_file` / `cat`：文件内容视图
    - 纯文本模式：直接展示文件内容
    - 代码高亮模式：根据文件扩展名进行语法高亮
  - 默认模式：JSON/文本原始数据展示
- 支持展开查看完整的原始数据
- 如果 `return_direct=true`，可显示"直接返回"标记

**对比现在的前端type=observation显示方式分析**：

当前前端实现（`MessageItem.tsx:310-419`）：
```tsx
// observation类型显示：观察内容 + obs_raw_data文件列表 + obs_summary + 下一步/参数/结束标志
{step.type === "observation" && (
  <>
    {/* 观察内容 */}
    {(step as any).obs_reasoning || step.reasoning || step.content && (
      <div style={getStepStyle("observation")}>
        <span>{(step as any).obs_reasoning || step.reasoning || step.content}</span>
      </div>
    )}
    {/* obs_raw_data文件列表 */}
    {!step.content && step.obs_raw_data?.entries && (
      <div>
        <span onClick={() => toggleExpand(stepIndex)}>
          {isExpanded ? "▼ 收起" : "▶ 展开"} 文件列表 ({entryCount}个)
        </span>
        {isExpanded && obsRawData.entries.map(...)}
      </div>
    )}
    {/* obs_summary */}
    {step.obs_summary && <div>📊 {step.obs_summary}</div>}
    {/* 下一步/参数/结束标志 */}
    <div>
      {step.obs_action_tool && <div>⬇️ 下一步：{step.obs_action_tool}</div>}
      {step.obs_params && <JsonHighlight data={step.obs_params} />}
      {step.is_finished && <span>✅ 结束</span>}
    </div>
  </>
)}
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示 |
| `tool_name` | 未使用 | ❌ 缺失 | 前端未显示observation的tool_name |
| `tool_params` | `step.obs_params` | ⚠️ 前缀不同 | 设计用tool_params，前端用obs_params |
| `observation` | `step.content` 或 `step.reasoning` | ❌ 不一致 | 设计用observation，前端用content/reasoning |
| `return_direct` | 未使用 | ❌ 缺失 | 前端未显示return_direct |
| `timestamp` | 外层StepRow显示 | ✅ 一致 | 统一在StepRow右侧显示 |

**前端特有的obs_前缀字段**（与SSE后端一致）：
- `obs_reasoning`：观察推理
- `obs_raw_data`：原始数据（含entries数组）
- `obs_summary`：摘要
- `obs_action_tool`：下一步工具
- `obs_params`：下一步参数
- `obs_execution_status`：执行状态
- `is_finished`：结束标志

**需要修改的地方**：
1. **字段名不一致**：设计文档用 `observation`，前端用 `content`/`reasoning`/`obs_reasoning`
2. **obs_前缀**：前端使用obs_前缀区分observation的字段，与thought/action_tool区分
3. **工具视图渲染位置**：前端工具视图（ListDirectoryView等）渲染在 **action_tool** 的 `renderToolResult` 中，而不是observation中

**关键发现**：
- 前端的 **observation** 和 **action_tool** 的渲染逻辑是分离的
- action_tool 负责渲染工具结果视图（通过 `renderToolResult`）
- observation 负责显示观察摘要、下一步信息、文件列表等
- 这与设计文档中 observation 包含工具原始结果的设计不同

**修改建议**：
1. 保持前端 obs_ 前缀字段设计（与SSE后端一致）
2. 工具视图渲染保持在 action_tool 中（当前设计合理）
3. observation 显示观察摘要、下一步信息、is_finished标志


---

#### 5.2.5 final 字段的生成与填写

**生成时机**：LLM返回最终答案时，Agent程序解析LLM响应时生成

> ⚠️ **识别规则**（见4.5节）：只有以下情况生成final步骤：
> - 模式1：LLM返回 `Thought: <推理内容>\nAnswer: <最终回答>`
> - 模式2：纯文本包含完成关键词（如"任务完成"、"总结"、"已结束"）
> 
> 其他终止条件（max_steps/工具错误/用户中断）生成error或incident步骤，不调用此方法。

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 调用`next_step()`函数获得递增的step值 | Agent程序的step计数器 | `8`（假设2轮loop后） |
| `response` | 从LLM响应中解析出最终回答内容 | LLM返回内容 | `"根据搜索结果，/home目录下有以下文件..."` |
| `is_finished` | 固定值 `true`（final表示业务完成） | Agent程序硬编码 | `true` |
| `thought` | 从LLM响应中解析出最终推理总结（可选） | LLM返回内容 | `"经过多次搜索，我已找到所有相关信息"` |
| `is_streaming` | 根据当前输出模式设置 | Agent程序配置 | `true` 或 `false` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566415000` |

**type=final可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `thought` | 从LLM响应中解析出最终推理总结（如有） | LLM返回内容 |
| `is_streaming` | 根据当前输出模式设置 | Agent程序配置 |




**LlamaIndex 参考源码**（`ResponseReasoningStep`）：
```python
# 来源: llama_index.core.agent.react.types
class ResponseReasoningStep(BaseReasoningStep):
    """Response reasoning step."""
    thought: str
    response: str
    is_streaming: bool = False  # 流式输出标志

    def get_content(self) -> str:
        if self.is_streaming:
            return f"Thought: {self.thought}\nAnswer (Starts With): {self.response} ..."
        else:
            return f"Thought: {self.thought}\nAnswer: {self.response}"

    @property
    def is_done(self) -> bool:
        return True  # 永远结束循环
```

**对照分析**：
- LlamaIndex的 `thought` → 我们的 `thought`（可选）
- LlamaIndex的 `response` → 我们的 `response`
- LlamaIndex的 `is_streaming` → 我们的 `is_streaming`
- **完全一致**
- 关键设计：`is_done = True`，永远结束循环
- LlamaIndex的 `get_content()` 根据 `is_streaming` 显示不同格式，前端可参考

**生成final_step代码示例**：
```python
def build_final_step(self, parsed: dict, is_streaming: bool = False) -> dict:
    """
    从统一解析器结果构建final步骤。
    调用方：parsed = parse_react_response(llm_response)
    前提条件：parsed["type"] in ("answer", "implicit")
    """
    return {
        "type": "final",
        "step": self.next_step(),  # 调用next_step()获得独立递增的step值
        "response": parsed["response"],
        "is_finished": True,  # final表示业务完成
        "thought": parsed.get("thought", ""),
        "is_streaming": is_streaming,
        "timestamp": int(time.time() * 1000)
    }
```
**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：f"Thought: {self.thought}\nAnswer: {self.response}"（非流式）
→ 格式：f"Thought: {self.thought}\nAnswer (Starts With): {self.response} ..."（流式）
→ 示例：Thought: 经过多次搜索，我已找到所有相关信息\nAnswer: 根据搜索结果，/home目录下有以下文件...
→ LLM收到的prompt片段（最后一个步骤）：
    Thought: 经过多次搜索，我已找到所有相关信息
    Answer: 根据搜索结果，/home目录下有以下文件...
    （完成后循环结束）
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "final", "step": 8, "response": "...", "is_finished": true, ...}
→ 示例：
{
    "type": "final",
    "step": 8,
    "response": "根据搜索结果，/home目录下有以下文件...",
    "is_finished": true,
    "thought": "经过多次搜索，我已找到所有相关信息",
    "is_streaming": false,
    "timestamp": 1743566415000
}
```


**type=final前端使用建议**：
- 显示为"最终回答"卡片，使用突出样式区别于其他步骤
- 支持Markdown渲染，展示格式化的回答内容
- 如果 `is_streaming=true`，使用打字机效果逐步显示
- 总步骤数和总耗时等统计信息来自框架层（`total_steps`/`total_tokens`），非final步骤字段

**对比现在的前端type=final显示方式分析**：

当前前端实现（`MessageItem.tsx:512-518`）：
```tsx
// final类型显示：仅显示content
{step.type === "final" && (
  <div style={getStepStyle("final" as StepType)}>
    <span style={getStepContentStyle("final" as StepType, "primary")}>
      {step.content || ""}
    </span>
  </div>
)}
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示 |
| `response` | `step.content` | ❌ 不一致 | 设计用response，前端用content |
| `is_finished` | 未使用 | ❌ 缺失 | 前端未显示is_finished标志 |
| `thought` | 未使用 | ❌ 缺失 | 前端未显示final的thought推理 |
| `is_streaming` | 未使用 | ❌ 缺失 | 前端未使用打字机效果 |
| `timestamp` | 外层StepRow显示 | ✅ 一致 | 统一在StepRow右侧显示 |

**需要修改的地方**：
1. **字段名不一致**：设计用 `response`，前端用 `content`
2. **is_finished标志**：前端未显示，建议添加"✅ 结束"徽章
3. **thought字段**：前端未显示final的推理过程，建议添加
4. **is_streaming**：前端未实现打字机效果

**修改建议**：
```tsx
{step.type === "final" && (
  <div style={getStepStyle("final" as StepType)}>
    {/* 最终回答内容 */}
    <span style={getStepContentStyle("final", "primary")}>
      {step.response || step.content || ""}
    </span>
    {/* 推理过程（可选） */}
    {step.thought && (
      <div style={{ marginTop: 6, fontSize: 12, color: "#666" }}>
        💭 推理：{step.thought}
      </div>
    )}
    {/* 结束标志 */}
    {step.is_finished && (
      <div style={{ marginTop: 6 }}>
        <span style={getFinishedBadgeStyle()}>✅ 结束</span>
      </div>
    )}
  </div>
)}
```
---

#### 5.2.6 error 字段的生成与填写

**生成时机**：发生错误时，Agent程序捕获异常后生成

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `step` | 调用`next_step()`函数获得递增的step值 | Agent程序的step计数器 | `5`（假设第2轮thought后出错） |
| `error_type` | 根据错误类型设置对应的错误类型值 | 异常类型 | `"tool_error"`, `"llm_error"` |
| `error_message` | 从异常对象中提取错误信息 | 异常对象 | `"工具执行超时，请重试"` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566410000` |
| `recoverable` | 根据错误类型判断是否可恢复 | Agent程序逻辑 | `true` 或 `false` |

**type=error可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `stack_trace` | 从异常对象中获取堆栈跟踪信息 | 异常对象 |
| `context` | 记录错误发生时的上下文信息（当前step、工具名等） | Agent内部状态 |
| `suggested_fix` | 根据错误类型生成建议修复方案 | Agent程序逻辑 |
| `retry_suggestion` | 根据错误类型生成重试建议 | Agent程序逻辑 |

**生成代码示例**：
```python
def build_error_step(self, error: Exception) -> dict:
    error_type = classify_error(error)
    recoverable = is_recoverable_error(error)
    return {
        "type": "error",
        "step": self.next_step(),  # 调用next_step()获得独立递增的step值
        "error_type": error_type,
        "error_message": str(error),
        "timestamp": int(time.time() * 1000),
        "recoverable": recoverable
    }
```
**用途：注入到 LLM 的 prompt 中作为上下文**
```
→ 格式：error不参与构建prompt（仅前端展示用）
→ 说明：error是异常终止，不拼接进LLM的prompt
→ 如果错误可恢复，prompt中会包含重试提示
```

**yield 返回的 dict - 发送给前端渲染**
```
→ 用途：发送给前端渲染
→ 格式：{"type": "error", "step": 5, "error_type": "...", "error_message": "...", ...}
→ 示例：
{
    "type": "error",
    "step": 5,
    "error_type": "tool_error",
    "error_message": "工具执行超时，请重试",
    "recoverable": true,
    "timestamp": 1743566410000
}
```


**type=error前端使用建议**：
- 显示为"错误"卡片，使用红色警告样式
- 显示错误类型和错误信息
- 如果 `recoverable=true`，可显示"重试"按钮
- 支持展开查看详细错误堆栈（开发模式）

**对比现在的前端type=error显示方式分析**：

当前前端实现（`MessageItem.tsx:519-531`）：
```tsx
// error类型显示：使用ErrorDetail组件
{step.type === "error" && (
  <ErrorDetail
    errorType={(step as any).error_type}
    errorMessage={step.error_message || (step as any).message}
    errorTimestamp={typeof step.timestamp === 'number' ? new Date(step.timestamp).toISOString() : String(step.timestamp)}
    errorDetails={(step as any).details}
    errorStack={(step as any).stack}
    errorRetryable={(step as any).retryable}
    errorRetryAfter={(step as any).retry_after}
    model={(step as any).model}
    provider={(step as any).provider}
  />
)}
```

**ErrorDetail组件**（`ErrorDetail.tsx`）：
```tsx
// ErrorDetail组件显示：错误类型 + 错误消息 + 时间戳 + 详情 + 堆栈 + 可重试 + 重试等待时间 + 模型/提供商
interface ErrorDetailProps {
  errorType?: string;
  errorMessage?: string;
  errorTimestamp?: string;
  errorDetails?: string;
  errorStack?: string;
  errorRetryable?: boolean;
  errorRetryAfter?: number;
  model?: string;
  provider?: string;
}
```

**字段对照**：
| 设计文档字段 | 前端使用字段 | 是否一致 | 说明 |
|-------------|------------|---------|------|
| `step` | `step.step` | ✅ 一致 | StepRow外层显示 |
| `error_type` | `(step as any).error_type` | ⚠️ 类型断言 | 前端用any类型断言 |
| `error_message` | `step.error_message \|\| (step as any).message` | ⚠️ 兼容 | 前端兼容两种字段名 |
| `timestamp` | `(step as any).errorTimestamp` | ⚠️ 不同 | 前端用errorTimestamp，设计用timestamp |
| `recoverable` | `(step as any).errorRetryable` | ⚠️ 不同 | 前端用errorRetryable，设计用recoverable |
| `stack_trace` | `(step as any).errorStack` | ⚠️ 不同 | 前端用errorStack，设计用stack_trace |

**ErrorDetail组件特有字段**：
- `errorRetryAfter`：重试等待时间（秒）
- `model`：模型名称
- `provider`：提供商

**需要修改的地方**：
1. **字段名不一致**：设计用 `recoverable`/`stack_trace`，前端用 `errorRetryable`/`errorStack`
2. **timestamp**：设计用 `timestamp`，前端用 `errorTimestamp`
3. **类型断言**：前端大量使用 `(step as any)`，建议定义明确的TypeScript类型

**修改建议**：
- 统一字段名，建议后端适配前端字段名（errorRetryable、errorStack等），因为前端ErrorDetail组件已完善
- 或者前端适配设计文档字段名，修改ErrorDetail组件的props
- 建议保持前端现有设计，ErrorDetail组件功能完善，包含重试、模型信息等


---

#### 5.2.7 chunk 字段的生成与填写

**生成时机**：LLM流式返回时，每个chunk由Agent程序实时生成

**字段生成规则**：

| 字段 | 生成方法 | 数据来源 | 示例值 |
|------|---------|---------|--------|
| `content` | 累积的完整内容（delta累加） | LLM流式响应 | `"根据搜索结果..."` |
| `delta` | 当前chunk的增量内容 | LLM流式响应 | `"文件"` |
| `is_final` | 根据流式结束标志设置 | LLM流式响应 | `true` 或 `false` |
| `timestamp` | 使用 `int(time.time() * 1000)` 获取毫秒级时间戳 | 系统时钟 | `1743566408000` |

**生成代码示例**：
```python
def build_chunk_step(self, delta: str, is_final: bool = False) -> dict:
    self.chunk_content += delta
    return {
        "type": "chunk",
        "content": self.chunk_content,
        "delta": delta,
        "is_final": is_final,
        "timestamp": int(time.time() * 1000)
    }
```

**前端使用建议**：
- 用于流式输出时的实时显示
- 使用 `delta` 字段进行增量更新，避免全量刷新
- 当 `is_final=true` 时，标记流式输出结束
- 可配合打字机效果实现平滑的内容展示

**可选字段生成说明**：
| 字段 | 生成方法 | 数据来源 |
|------|---------|---------|
| `index` | 当前chunk的序号（从0开始递增） | Agent内部计数器 |
| `role` | 固定为 "assistant" | 固定值 |
| `model` | 从LLM配置对象中读取 | LLM配置 |
| `finish_reason` | 从LLM流式响应的结束标志中获取 | LLM流式响应 |

---

### 5.2.8 前端使用建议总结

| 场景 | 建议 |
|------|------|
| **步骤渲染** | 根据 `type` 字段渲染对应的组件（StartCard, ThoughtCard, ActionCard等） |
| **步骤排序** | 根据 `step` 字段对步骤进行排序，确保显示顺序正确 |
| **步骤关联** | 将 `action_tool` 和 `observation` 配对显示，形成调用→结果的视觉关联 |
| **状态显示** | 根据 `execution_status` 显示不同状态（成功/失败/超时） |
| **流式输出** | 使用 `chunk` 的 `delta` 字段进行增量更新，`is_final` 标记结束 |
| **错误处理** | 根据 `recoverable` 字段决定是否显示重试按钮 |
| **数据存储** | 将完整的steps数组存储到数据库，便于后续查询和分析 |
| **API设计** | SSE事件结构应包含 `type`、`step`、`data` 三个核心字段 |

**更新时间**: 2026-04-02 18:41:00    最后的时间
**版本**: v4.13
**编写人**: 小沈
**检查人**: 小健

---

## 六、流式设计对比与改进建议

### 6.1 两个流式设计文档对比

**文档A**：本文档（React步骤分析与4次重构设计与实现）- 我们的系统设计
**文档B**：`Langchain 流式代码-完整版-小沈-2026-04-02.md` - LangChain/LangGraph参考

#### 6.1.1 核心设计理念对比

| 维度 | 文档A（我们的设计） | 文档B（LangChain） |
|------|---------------------|-------------------|
| **设计目标** | 自研ReAgent系统的完整step-by-step设计 | 学习LangChain/LangGraph的流式实现 |
| **step字段** | ✅ 有（独立递增：1,2,3,4...） | ❌ 无 |
| **type类型** | 10种：start/thought/action_tool/observation/chunk/final/error/incident等 | 3种：token/tool_start/tool_end |
| **事件驱动** | Agent程序解析LLM+执行工具后填充 | 框架自动触发事件 |
| **数据分离** | messages数组（给LLM）+ type字段（给前端） | 事件监听 + SSE推送 |

#### 6.1.2 后端yield对比

**文档A我们的yield**：
```
data: {"type": "start", "step": 1, ...}
data: {"type": "thought", "step": 2, "content": "...", "tool_name": "...", "tool_params": {...}}
data: {"type": "action_tool", "step": 3, "execution_status": "success", "execution_result": "..."}
data: {"type": "observation", "step": 4, "tool_name": "...", "observation": "..."}
```

**文档B的yield**：
```
data: {"type": "token", "content": "北京"}
data: {"type": "token", "content": "天气"}
data: {"type": "tool_start", "tool_name": "get_weather", "input": {"city": "北京"}}
data: {"type": "tool_end", "output": "北京天气：晴，25°C"}
```

#### 6.1.3 结论

| 结论 | 说明 |
|------|------|
| **我们的设计更完整** | ✅ 独立Step、step序号、10种type、符合标准ReAct |
| **LangChain可借鉴** | 事件驱动机制、SSE推送格式、前端消费逻辑 |
| **建议** | 以文档A为主，吸收文档B的SSE推送和前端消费方案 |

---

### 6.6 统一System Prompt和JSON Schema字段名修改

**修改时间**: 2026-04-07 22:30:00  
**修改人**: 小沈  
**问题发现**: 小沈在分析message组装机制时发现system prompt字段名与代码不一致

#### 问题描述

| 位置 | 字段名 | 说明 |
|------|--------|------|
| **System Prompt要求LLM返回** | `action` / `action_input` | file_prompts.py 第198-209行 |
| **JSON Schema定义** | `action` / `action_input` | llm_strategies.py 第481-487行 |
| **代码解析器期望** | `action_tool` / `params` | ToolParser.parse_response() |

虽然解析器有降级兼容（`parsed.get("action_tool", parsed.get("action", "finish"))`），但走的是降级路径，不是最优解。

#### 修改效果

**修改前**：LLM按prompt返回 `{"action":"xxx", "action_input":{...}}`，解析器走降级路径读取
**修改后**：LLM按prompt返回 `{"action_tool":"xxx", "params":{...}}`，解析器直接读取，无需降级

#### Git提交

```
commit c7c1e2c6
fix: 统一system prompt和JSON Schema字段名 action_tool/params 小沈 2026-04-07
```

## 七、设计文档与当前代码的深度对比分析（整合版）

**分析时间**: 2026-04-08 15:23:58  
**分析人**: 小沈  
**整合来源**: 第5章type字段设计 + 第6章对比分析 + 第7章深度对比分析  
**修正说明**: 修正final/error的step字段说明（由sse_wrapper层自动添加）

---

### 7.0 重要说明：step字段的实现方式

> ⚠️ **关键修正**：所有type的step字段由sse_wrapper层自动添加，不需要在agent代码中手动设置。

根据4.8.7节说明：
> **说明**: step字段由sse_wrapper层自动添加，不需要在agent代码中手动设置

**这意味着**：
- ✅ final和error**有step字段**，由sse_wrapper层自动添加
- ✅ 所有type都包含step字段，保持一致性
- ✅ agent代码中不需要显式设置step，由框架统一处理

---

### 7.1 各type字段完整对比分析

#### 7.1.1 start字段对比

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | step=1 | step=next_step() | ✅ 基本一致（sse_wrapper添加） |
| **session_id** | `session_id` | `task_id` | ❌ 字段名不同，但用途不同 |
| **task** | 用户任务描述 | 未实现 | ❌ 缺失 |
| **model/provider** | 3个独立字段 | 合并在display_name | ⚠️ 格式不同 |

**已实现字段**：step, timestamp, display_name, provider, model, task_id, user_message, security_check

**session_id vs task_id 详细分析**：

| 项目 | task_id（任务ID） | session_id（会话ID） |
|------|------------------|---------------------|
| **定义** | 标识一次具体的任务执行 | 标识一次完整的对话会话 |
| **粒度** | 任务级别 | 对话级别 |
| **格式** | UUID格式 | UUID格式 |
| **用途** | 任务控制（暂停/恢复/取消） | 对话历史管理、关联多轮对话 |
| **生命周期** | 单次任务执行 | 多轮对话 |
| **核心价值** | ⭐⭐⭐⭐⭐ 任务控制 | ⭐⭐⭐⭐⭐ 对话管理 |

**关系**：
```
session_id (对话级别)
    │
    ├── task_id_1 (第1轮对话的任务)
    │   ├── thought
    │   ├── action_tool
    │   └── observation
    │
    └── task_id_2 (第2轮对话的任务)
        ├── thought
        └── final
```

**结论**：两者**用途不同**，不是字段名错误
- `task_id`：用于任务控制（暂停、恢复、取消）
- `session_id`：用于对话历史管理、关联多轮对话

**可借鉴优点**：
- ✅ `task`字段：记录用户原始任务，便于前端展示"任务是什么"

---

#### 7.1.2 thought字段对比

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | ✅ | ✅ sse_wrapper添加 | ✅ 一致 |
| **content** | `content` | `content` | ✅ 一致 |
| **tool_name** | `tool_name` | `action_tool` | ❌ 字段名不同（已统一修改） |
| **tool_params** | `tool_params` | `params` | ❌ 字段名不同（已统一修改） |

**已实现字段**：step, timestamp, content, action_tool, params

**已修改**: 2026-04-08已统一为`tool_name`/`tool_params`

---

#### 7.1.3 action_tool字段对比

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | ✅ | ✅ sse_wrapper添加 | ✅ 一致 |
| **execution_status** | ✅ | ✅ | ✅ 一致 |
| **execution_result** | ✅ | `raw_data` | ⚠️ 字段名不同 |
| **error_message** | 条件必填 | 未实现 | ❌ 缺失 |
| **summary** | 可选 | ✅ | ✅ 一致 |

**已实现字段**：step, timestamp, content, tool_name, tool_params, execution_status, summary, raw_data, action_retry_count

**可借鉴优点**：
- ✅ `error_message`字段：工具执行失败时明确记录错误信息
- ✅ `execution_result`比`raw_data`更语义化

---

#### 7.1.4 observation字段对比 ⭐重点

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | ✅ | ✅ sse_wrapper添加 | ✅ 一致 |
| **tool_name** | ✅ 从thought复制 | ✅ 已添加 | ✅ 一致（2026-04-08修改） |
| **tool_params** | ✅ 从thought复制 | 未实现 | ❌ 缺失 |
| **observation/content** | ✅ 工具原始结果 | 包含"实际数据: {raw_data}" | ⚠️ 已包含原始数据 |
| **return_direct** | ✅ 支持直接返回 | 未实现 | ❌ 缺失 |

**已实现字段**：step, timestamp, tool_name, content（包含原始数据）

**关键差异**：
```
文档设计: observation="北京今天晴，25度"  ← 纯原始数据
当前实现: content="Tool 'get_weather' executed: completed\n实际数据: {...}"  ← 包含原始数据
```

**可借鉴优点**：
- ⭐⭐⭐ `return_direct`字段：支持工具直接返回结果，跳过LLM分析（新功能）
- ⭐ `tool_name`字段：便于前端显示"调用了什么工具"（已实现）

---

#### 7.1.5 final字段对比

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | ✅ | ✅ sse_wrapper添加 | ✅ 一致 |
| **response** | ✅ 最终回答 | `content` | ⚠️ 字段名不同 |
| **is_finished** | ✅ 业务完成标志 | 未实现 | ❌ 缺失 |
| **thought** | 可选，最终推理 | 未实现 | ❌ 缺失 |
| **is_streaming** | 流式输出标志 | 未实现 | ❌ 缺失 |

**已实现字段**：step, timestamp, content

**可借鉴优点**：
- ✅ `is_finished`字段：明确标识业务完成，前端可显示"✅ 结束"徽章
- ✅ `thought`字段：显示最终推理过程，增强用户体验
- ✅ `is_streaming`字段：支持打字机效果

---

#### 7.1.6 error字段对比

| 对比项 | 文档设计 | 我们当前实现 | 差异 |
|--------|---------|-------------|------|
| **step** | ✅ | ✅ sse_wrapper添加 | ✅ 一致 |
| **error_type** | ✅ 详细分类 | `code` | ⚠️ 字段名/值不同 |
| **error_message** | ✅ | `message` | ⚠️ 字段名不同 |
| **recoverable** | ✅ 是否可恢复 | 未实现 | ❌ 缺失 |

**已实现字段**：step, timestamp, code, message

**可借鉴优点**：
- ✅ `error_type`详细分类：`"max_steps_exceeded"`, `"llm_error"`, `"tool_error"`等
- ✅ `recoverable`字段：前端可根据此字段决定是否显示"重试"按钮

---

### 7.2 ReasoningStep基类分析

#### 7.2.1 LlamaIndex的4个ReasoningStep核心设计

| LlamaIndex类型 | 字段 | is_done | 说明 | 对应我们的type |
|---------------|------|---------|------|---------------|
| `BaseReasoningStep` | 无（抽象基类） | 抽象 | 定义 `get_content()` 和 `is_done` 接口 | 所有type的基类 |
| `ActionReasoningStep` | `thought`, `action`, `action_input` | False | LLM决定调用工具 | thought（含tool_name/tool_params） |
| `ObservationReasoningStep` | `observation`, `return_direct` | =return_direct | 工具执行结果 | observation |
| `ResponseReasoningStep` | `thought`, `response`, `is_streaming` | True | 最终回答 | final |

#### 7.2.2 is_done循环控制机制

| type | is_done | 说明 |
|------|---------|------|
| thought | `False` | 思考后必须执行工具 |
| action_tool | `False` | 工具执行后必须生成observation |
| observation | `return_direct` | 工具说直接返回就结束，否则继续LLM |
| final | `True` | 永远结束循环 |
| error | `True` | 错误结束循环 |

#### 7.2.3 是否值得借鉴？

| 方面 | 评价 | 说明 |
|------|------|------|
| **is_done机制** | ⭐⭐⭐ 有价值 | 明确的循环控制，比`if action_tool == "finish"`更清晰 |
| **OOP基类** | ⭐ 一般 | 当前项目Step类型固定，引入6个类增加复杂度 |
| **get_content()方法** | ⭐⭐ 有价值 | 统一的内容获取接口，便于构建prompt |

**结论**：
- ✅ `is_done`机制有借鉴价值，可考虑引入
- ❌ OOP基类不建议引入，当前if判断够用
- ✅ `get_content()`方法可参考，统一内容获取接口

---

### 7.3 ReAct统一解析器分析

#### 7.3.1 文档设计的解析器特点

```python
REACT_KEYWORDS = {
    "thought": r"(?:Thought|思考|推理):\s*",
    "action": r"(?:Action|行动|工具调用):\s*",
    "action_input": r"(?:Action Input|工具参数|输入):\s*",
    "answer": r"(?:Answer|回答|最终答案):\s*",
}
```

**设计特点**：
1. **支持中英文关键词**：Thought/思考/推理、Action/行动/工具调用
2. **4级JSON降级解析**：标准JSON → 提取JSON片段 → 替换单引号 → 正则提取
3. **统一入口**：一个`parse_react_response()`函数处理所有格式

#### 7.3.2 与当前代码的对比

| 对比项 | 文档设计 | 当前代码 |
|--------|---------|---------|
| **格式** | ReAct文本格式 | JSON格式 |
| **中文支持** | ✅ 支持 | ❌ JSON键名英文 |
| **容错能力** | 正则+降级JSON | JSON+正则降级 |
| **LLM依赖** | LLM按论文格式 | LLM按prompt输出JSON |

#### 7.3.3 是否值得借鉴？

| 方面 | 评价 | 说明 |
|------|------|------|
| **中英文支持** | ⭐⭐⭐ 有价值 | 如果LLM输出中文关键词，可正确解析 |
| **4级JSON降级** | ⭐⭐⭐ 有价值 | 提高容错性 |
| **与当前实现的关系** | - | 当前用JSON格式，两种格式可共存 |

**结论**：
- ✅ 如果未来需要支持非JSON格式的LLM输出，这个解析器很有价值
- ✅ 当前已有降级兼容（`tool_parser.py` 第84-101行），无需大幅改动
- ✅ 可考虑将中英文支持作为降级路径

---

### 7.4 messages构建对比分析

#### 7.4.1 对比表

| 对比项 | 文档设计 | 当前代码 |
|--------|---------|---------|
| **构建方式** | 每次从steps历史**重建**messages | 每轮**增量追加**到conversation_history |
| **数据源** | steps数组（前端显示数据） | conversation_history（独立存储） |
| **性能** | O(n) 每次遍历steps | O(1) 每次append |
| **一致性** | 保证messages与steps同步 | 需要保证追加顺序正确 |

#### 7.4.2 是否值得借鉴？

| 维度 | 文档设计 | 当前代码 |
|------|---------|---------|
| **优点** | 数据一致性高 | 性能好，无需每次遍历 |
| **缺点** | 性能差，每次LLM调用都要重建 | 需要手动维护同步 |
| **风险** | 无 | 如果追加顺序错乱，messages会不一致 |

**结论**：
- ❌ 不建议吸收重建方式，当前增量追加性能更好
- ✅ 建议在每个step追加后，验证conversation_history的长度和内容是否正确

---

### 7.5 已完成的修改汇总（2026-04-08）

| 修改项 | 文件 | 状态 |
|--------|------|------|
| thought字段名统一(tool_name/tool_params) | base_react.py | ✅ 已完成 |
| observation添加tool_name | base_react.py | ✅ 已完成 |
| system prompt字段名统一 | file_prompts.py | ✅ 已完成 |
| JSON Schema字段名统一 | llm_strategies.py | ✅ 已完成 |

**测试验证**：28 passed, 4 skipped

**Git提交**：
- feat: base_react.py observation yield添加tool_name字段-小沈-2026-04-08
- feat: file_prompts.py统一字段名action/action_input-小沈-2026-04-08
- feat: llm_strategies.py统一JSON Schema字段名-小沈-2026-04-08

---

### 7.6 后续改进建议（2026-04-11 更新）

#### 7.6.1 高优先级（建议尽快完成）

| 改进项 | 价值 | 复杂度 | 状态 | 说明 |
|--------|------|--------|------|------|
| **Structured Output 支持** | ⭐⭐⭐⭐⭐ | 中 | 待实现 | 提升LLM输出稳定性 |
| **Budget 控制 + 成本追踪** | ⭐⭐⭐⭐⭐ | 高 | 待实现 | 成本管理 |
| **超长历史优化** | ⭐⭐⭐⭐ | 中 | TODO已添加 | 添加总长度检查 |
| **final添加is_finished字段** | ⭐⭐⭐⭐ | 低 | 待实现 | 前端显示"✅ 结束"徽章 |

#### 7.6.2 中优先级（建议后续考虑）

| 改进项 | 价值 | 复杂度 | 状态 | 说明 |
|--------|------|--------|------|------|
| **带Jitter指数退避** | ⭐⭐⭐⭐ | 低 | 待实现 | 429重试优化 |
| **熔断器** | ⭐⭐⭐⭐ | 中 | 待实现 | 防止级联失败 |
| **收敛检测** | ⭐⭐⭐ | 低 | 待实现 | 加速循环结束判断 |
| **error添加recoverable字段** | ⭐⭐⭐ | 低 | 待实现 | 前端显示"重试"按钮 |
| **start添加task字段** | ⭐⭐ | 低 | 待实现 | 显示用户原始任务 |

#### 7.6.3 低优先级（可选）

| 改进项 | 价值 | 复杂度 | 说明 |
|--------|------|--------|------|
| **action_tool添加error_message字段** | ⭐⭐ | 低 | 记录工具执行错误 |
| **考虑return_direct机制** | ⭐⭐⭐ | 高 | 新功能，工具直接返回 |

#### 7.6.4 已完成改进（2026-04-11）

| 改进项 | 完成时间 | 说明 |
|--------|---------|------|
| **429错误统一处理** | 2026-04-11 | 通过 error_handler.py 统一处理，不再丢失错误信息 |
| **超长历史TODO** | 2026-04-11 | 已添加总长度检查的TODO注释 |
| **observation添加tool_name** | 2026-04-08 | 从thought复制tool_name |
| **字段名统一** | 2026-04-08 | action_tool/params → tool_name/tool_params |

---

### 7.7 最终结论

#### 7.7.1 文档设计的价值

1. ✅ **概念定义清晰**：Step/Loop、messages/type的区分
2. ✅ **字段规范完整**：每个type的字段定义详细
3. ✅ **LlamaIndex参考**：ReasoningStep基类、is_done机制
4. ✅ **前端使用建议**：详细的渲染建议

#### 7.7.2 我们当前实现的优点

1. ✅ **简单直接**：不需要OOP基类，if判断够用
2. ✅ **性能更好**：增量追加messages，O(1)复杂度
3. ✅ **已有降级兼容**：解析器支持多种格式

#### 7.7.3 核心建议

- 以我们当前实现为主
- 选择性吸收文档设计的优点
- 优先完成：observation改为原始结果、final添加is_finished

---

### 7.8 设计项汇总表

| 设计项 | 文档设计 | 当前代码 | 建议 |
|--------|---------|---------|------|
| **统一解析器** | parse_react_response() 支持中英文 | ToolParser.parse_response() JSON格式 | ✅ 已有降级兼容，无需改动 |
| **is_done机制** | ReasoningStep基类 | if判断硬编码 | ⭐ 可考虑引入is_done机制 |
| **messages构建** | build_messages_from_steps() | conversation_history 直接append | ❌ 不建议吸收，性能更好 |
| **observation字段** | 含tool_name/tool_params/return_direct | content(工具简述) | ⭐ 建议改为原始结果 |
| **final字段** | 含is_finished/thought/is_streaming | content | ⭐ 建议添加is_finished |
| **error字段** | 含error_type/recoverable | code/message | ⭐ 建议添加recoverable |

---

## 八、后端tool_name/tool_params统一化修改方案

**分析时间**: 2026-04-08 15:47:25  
**分析人**: 小沈  
**目标**: 统一后端系统名称为`tool_name`和`tool_params`，消除所有`action_tool`和`params`的使用

---

### 8.1 问题概述

**当前状态**：后端代码中存在两种字段名混用
- `action_tool` / `params`：LLM prompt、JSON Schema、thought阶段
- `tool_name` / `tool_params`：action_tool阶段、observation阶段

**目标状态**：统一使用`tool_name`和`tool_params`

---

### 8.2 完整修改清单

已经完成


## 九、前端tool_name/tool_params统一化修改方案


### 9.1 问题概述

**当前状态**：前端代码中存在两套字段名

| 字段 | 用途 | 位置 |
|------|------|------|
| `action_tool` / `params` | thought类型存储工具名/参数 | sse.ts:81-82 |
| `tool_name` / `tool_params` | action_tool类型存储工具名/参数 | sse.ts:97-98 |

**目标状态**：统一使用`tool_name`和`tool_params`

**重要区分**：
- **type字段值**：如`"type": "action_tool"` - 这是步骤类型标识，**保持不变**
- **数据字段名**：如`step.action_tool` - 这是数据字段，需要改为`step.tool_name`

---

### 9.2 修改原则
已经完成


---

## 十、2026-04-11 文档修正记录

**修正时间**: 2026-04-11 21:02:42
**修正人**: 小沈
**修正依据**: 基于实际代码与文档对比分析

---

### 10.1 文档与代码核对结果

| 章节 | 文档描述 | 实际代码 | 差异说明 |
|------|---------|---------|---------|
| 4.8.2 thought | `action_tool`, `params` | `tool_name`, `tool_params` | ⚠️ 文档字段名已过时 |
| 4.8.4 observation | content="Tool executed: summary" | 包含"实际数据: {raw_data}" | ⚠️ 文档描述不准确 |
| 7.1.4 observation | content是程序生成描述 | 包含原始数据 | ⚠️ 文档描述需更新 |

---

### 10.2 当前代码实际状态（2026-04-11）

#### 10.2.1 thought 类型（实际代码）

**文件**: `llm_strategies.py:430-455`
```python
formatted = {
    "thought": f"Calling tool: {func_name}",
    "tool_name": func_name,      # ✅ 使用 tool_name
    "tool_params": args          # ✅ 使用 tool_params
}
```

**字段对照**:
| 字段 | 说明 | 状态 |
|------|------|------|
| `content` | LLM推理内容 | ✅ 已统一 |
| `tool_name` | 工具名称 | ✅ 已统一 |
| `tool_params` | 工具参数 | ✅ 已统一 |
| `reasoning` | LLM的reasoning字段 | ✅ 已支持 |

---

#### 10.2.2 observation 类型（实际代码）

**文件**: `base_react.py:270-274`
```python
raw_data = execution_result.get('data')
if raw_data:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}\n实际数据: {raw_data}"
else:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"
```

**字段对照**:
| 字段 | 说明 | 状态 |
|------|------|------|
| `tool_name` | 工具名称 | ✅ 已添加（2026-04-08） |
| `content` | 包含原始数据(raw_data) | ✅ 已包含实际数据 |
| `observation` | 实际内容 | ⚠️ 字段名待统一 |

---

#### 10.2.3 429错误统一处理（新增）

**文件**: `llm_strategies.py:403-414`
```python
# 【修复 2026-04-11 小沈】统一错误处理：不应该降级到 TextStrategy，应该调用 error_handler 统一处理
if last_error:
    error_type = resolve_http_error_type(last_error) if last_error else None
    error_code, error_message = get_stream_error_info(error_type, original_message=last_error)
    logger.error(f"[Function Calling] 错误统一处理: error_type={error_type}, error_message={error_message}")
    return self._make_result(
        content=f"[错误] {error_message}",
        tool_name="finish",
        tool_params={"result": f"[错误] {error_message}"}
    )
```

**说明**: 429错误现在统一通过 `error_handler.py` 处理，不再降级到TextStrategy，错误信息不会丢失。

---

#### 10.2.4 超长历史TODO（新增）

**文件**: `base_react.py:380-392`
```python
def _trim_history(self) -> None:
    """
    TODO [2026-04-11]: 当前只检查消息数量(<=15不触发清理)，没有检查消息总长度
    问题：工具执行结果很长(如390627字符的observation)，导致API请求体过大触发429
    思路：添加总长度检查，如 total_chars > 100000 时强制清理 observation 内容(可截断或只保留摘要)
    """
    # ... 现有代码 ...

    # TODO [2026-04-11]: 还需要检查消息总长度
    total_chars = sum(len(msg.get("content", "")) for msg in self.conversation_history)
    if total_chars > 100000:
        logger.warning(f"[History] Warning: total chars={total_chars} exceeds limit, should trim")
```

---

#### 10.2.5 search_files 参数统一（新增）

**文件**: `tool_executor.py:114`
```python
STANDARD_PARAMS = {
    # ...
    # 【修复 2026-04-11】用 page_token 替换 after（与 file_tools.py 第1164行保持一致）
    "search_files": ["file_pattern", "path", "recursive", "max_depth", "page_token"],
    # ...
}
```

**说明**: search_files 参数已统一为 `page_token`（与 file_tools.py 保持一致）。

---

### 10.3 文档修正清单

#### 10.3.1 第4章 字段定义修正

| 章节 | 修正前 | 修正后 |
|------|--------|--------|
| 4.8.2 thought | `action_tool`, `params` | `tool_name`, `tool_params` |
| 4.8.4 observation | content="Tool executed: summary" | 包含"实际数据: {raw_data}" |

#### 10.3.2 第7章 对比分析修正

| 章节 | 修正前 | 修正后 |
|------|--------|--------|
| 7.1.4 observation | content是程序生成描述 | 包含原始数据(raw_data) |
| 7.6 后续改进 | 未提及429错误处理 | 新增429错误统一处理说明 |

---

### 10.4 待改进项（优先级）

| 优先级 | 改进项 | 状态 | 说明 |
|--------|--------|------|------|
| P0 | Structured Output 支持 | 待实现 | 提升LLM输出稳定性 |
| P0 | Budget 控制 + 成本追踪 | 待实现 | 成本管理 |
| P1 | 超长历史优化 | TODO已添加 | 添加总长度检查 |
| P1 | 带Jitter指数退避 | 待实现 | 429重试优化 |
| P1 | 熔断器 | 待实现 | 防止级联失败 |
| P1 | 收敛检测 | 待实现 | 加速循环结束判断 |

---

**文档版本**: v4.25
**更新时间**: 2026-04-11 21:02:42
**编写人**: 小沈
**修正依据**: 基于实际代码与文档对比分析

---

## 十一、文档中方案和建议的未实现项汇总（逐章分析版）

**汇总时间**: 2026-04-11 21:20:00
**汇总人**: 小沈
**汇总依据**: 基于文档第1-10章逐章对比分析后端代码实现

---

### 11.1 对比分析说明

**对比范围**：
- 文档第4章：type字段设计（4.1-4.8）
- 文档第5章：字段生成说明（5.2.1-5.2.8）
- 文档第7章：深度对比分析（7.1-7.6）
- 文档第10章：2026-04-11修正记录

**后端代码文件**：
- `backend/app/services/agent/base_react.py` - ReAct核心基类
- `backend/app/services/agent/llm_strategies.py` - LLM策略
- `backend/app/services/agent/tool_executor.py` - 工具执行器
- `backend/app/services/agent/adapter.py` - 参数适配器
- `backend/app/services/agent/types/step_types.py` - Step类型定义
- `backend/app/chat_stream/error_handler.py` - 统一错误处理

---

### 11.2 已完成改进项（基于代码验证）

| 序号 | 改进项 | 代码位置 | 验证状态 |
|------|--------|----------|----------|
| 1 | **429错误统一处理** | `llm_strategies.py:403-414` | ✅ 已实现 |
| 2 | **超长历史TODO** | `base_react.py:380-392` | ✅ 已添加TODO |
| 3 | **observation添加tool_name** | `base_react.py:270-274` | ✅ 2026-04-08 |
| 4 | **字段名统一** | 多个文件 | ✅ 2026-04-08 |

**代码验证依据**：

```python
# llm_strategies.py:403-414 - 429错误统一处理
if last_error:
    error_type = resolve_http_error_type(last_error) if last_error else None
    error_code, error_message = get_stream_error_info(error_type, original_message=last_error)
    logger.error(f"[Function Calling] 错误统一处理: error_type={error_type}, error_message={error_message}")
    return self._make_result(
        content=f"[错误] {error_message}",
        tool_name="finish",
        tool_params={"result": f"[错误] {error_message}"}
    )

# base_react.py:270-274 - observation添加tool_name
raw_data = execution_result.get('data')
if raw_data:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}\n实际数据: {raw_data}"
else:
    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"
```

---

### 11.3 高优先级未实现项（P0）

| 序号 | 改进项 | 文档位置 | 代码位置 | 未实现说明 |
|------|--------|----------|----------|-----------|
| 1 | **Structured Output 支持** | 7.6.1 | `llm_strategies.py` | 提升LLM输出稳定性，当前使用JSON文本解析 |
| 2 | **Budget 控制 + 成本追踪** | 7.6.1 | 无 | 成本管理，当前没有token计费和成本统计 |
| 3 | **超长历史优化** | 7.6.1 | `base_react.py:380-392` | 已添加TODO注释，但未实现总长度检查逻辑 |

**代码验证**：
```python
# llm_strategies.py - 没有Budget控制类
class BaseStrategy:
    def __init__(self, ...):
        self.max_retries = 3  # 只有重试次数，没有token/budget控制
```

---

### 11.4 中优先级未实现项（P1）

| 序号 | 改进项 | 文档位置 | 代码位置 | 未实现说明 |
|------|--------|----------|----------|-----------|
| 4 | **带Jitter指数退避** | 7.6.2 | `llm_strategies.py:342-348` | 只有固定倍数退避(2,4,8秒)，无Jitter随机化 |
| 5 | **熔断器** | 7.6.2 | 无 | 没有熔断器机制来防止级联失败 |
| 6 | **收敛检测** | 7.6.2 | 无 | 没有加速循环结束的判断机制 |
| 7 | **error添加recoverable字段** | 7.6.2 | `error_handler.py` | error_handler有retryable字段，但error步骤未统一添加 |
| 8 | **start添加task字段** | 7.6.2 | `base_react.py` | start步骤缺少task字段来显示用户原始任务 |

**代码验证**：
```python
# llm_strategies.py:342-348 - 只有固定退避
retry_delay = self.RETRY_DELAY * (2 ** attempt)  # 固定倍数，无Jitter
await asyncio.sleep(retry_delay)
```

---

### 11.5 低优先级未实现项（P2）

| 序号 | 改进项 | 文档位置 | 代码位置 | 未实现说明 |
|------|--------|----------|----------|-----------|
| 9 | **action_tool添加error_message字段** | 7.6.3 | `base_react.py` | summary已包含错误信息，无独立error_message字段 |
| 10 | **return_direct机制** | 7.6.3 | 无 | 工具直接返回结果跳过后续LLM推理的功能 |
| 11 | **增加tool_start事件** | 6.4.1 | 无 | 工具开始执行时立即yield，让前端显示"正在调用xxx..." |

---

### 11.6 前端字段相关未实现项

| 序号 | 字段项 | 文档位置 | 未实现说明 |
|------|--------|----------|-----------|
| 12 | **final添加is_finished字段** | 7.6.1/5.2.5 | 前端无法显示"✅ 结束"徽章 |
| 13 | **observation添加tool_params字段** | 7.1.4 | observation缺少tool_params字段 |
| 14 | **final添加thought字段** | 5.2.5 | 前端无法显示最终推理过程 |
| 15 | **final添加is_streaming字段** | 5.2.5 | 前端没有实现打字机效果 |

**文档依据**（5.2.5）：
```markdown
final字段生成规则：
| thought | 从LLM响应中解析出最终推理总结（可选） |
| is_streaming | 根据当前输出模式设置 |
```

---

### 11.7 ReasoningStep基类设计相关

| 序号 | 设计项 | 文档位置 | 当前状态 |
|------|--------|----------|----------|
| 16 | **is_done机制** | 7.2.3 | 用if判断硬编码，没有引入is_done接口方法 |
| 17 | **OOP基类** | 7.2.3 | 当前不需要引入ReasoningStep基类 |

**文档结论**（7.2.3）：
```
| OOP基类 | ⭐ 一般 | 当前项目Step类型固定，引入6个类增加复杂度 |
```

---

### 11.8 未实现项汇总表

| 类别 | 总数 | 已实现 | 未实现 |
|------|------|--------|--------|
| **已完成** | 4 | 4 | 0 |
| **P0高优先级** | 3 | 0 | 3 |
| **P1中优先级** | 5 | 1 | 4 |
| **P2低优先级** | 3 | 0 | 3 |
| **前端字段相关** | 4 | 0 | 4 |
| **ReAct设计相关** | 2 | 0 | 2 |
| **总计** | 21 | 5 | 16 |

---

### 11.9 实施建议

| Phase | 时间 | 改进项 | 预计工时 |
|-------|------|--------|----------|
| **Phase 1** | 短期 | Structured Output支持、Budget控制 | 4-6小时 |
| **Phase 2** | 中期 | 带Jitter退避、熔断器、收敛检测 | 6-8小时 |
| **Phase 3** | 长期 | 超长历史优化、前端字段完善 | 4-6小时 |

---

### 11.10 未实现项详细说明

#### 11.10.1 Structured Output 支持（P0）

**文档描述**（7.6.1）：
```
Structured Output 支持 - 提升LLM输出稳定性
通过LLM的response_format或tools参数约束输出结构
```

**当前代码状态**：
- `llm_strategies.py` 只有 `ResponseFormatStrategy` 类（未使用）
- 主要使用 JSON 文本解析 + 正则降级
- 没有强制使用 Function Calling

**建议实现方式**：
```python
# 方案1：Function Calling
response = await llm_client.chat_with_tools(
    message=message,
    history=history_messages,
    tools=self.tools  # 强制使用tools参数
)

# 方案2：response_format (需模型支持)
response = await llm_client.chat_with_response_format(
    message=message,
    history=history_messages,
    response_format={"type": "json_object", "json_schema": {...}}
)
```

---

#### 11.10.2 Budget 控制 + 成本追踪（P0）

**文档描述**（5.5.1）：
```
Structured Output 支持 - 提升LLM输出稳定性
通过LLM的response_format或tools参数约束输出结构
```

**当前代码状态**：
- `llm_strategies.py` 只有 `ResponseFormatStrategy` 类（未使用）
- 主要使用 JSON 文本解析 + 正则降级
- 没有强制使用 Function Calling

**建议实现方式**：
```python
# 方案1：Function Calling
response = await llm_client.chat_with_tools(
    message=message,
    history=history_messages,
    tools=self.tools  # 强制使用tools参数
)

# 方案2：response_format (需模型支持)
response = await llm_client.chat_with_response_format(
    message=message,
    history=history_messages,
    response_format={"type": "json_object", "json_schema": {...}}
)
```

---

#### 11.8.2 Budget 控制 + 成本追踪（P0）

**文档描述**（7.6.1）：
```
Budget 控制 + 成本追踪 - 成本管理
- 设置每次任务的最大token消耗
- 追踪LLM调用token数量
- 计算任务成本
```

**当前代码状态**：
- 没有token计费逻辑
- 没有成本统计
- 没有Budget上限控制

**建议实现方式**：
```python
class BaseAgent:
    def __init__(self, max_steps: int = 100, max_tokens: int = 100000):
        self.max_tokens = max_tokens
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def track_usage(self, prompt_tokens: int, completion_tokens: int):
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_cost += self._calculate_cost(prompt_tokens, completion_tokens)
        if self.total_tokens > self.max_tokens:
            raise BudgetExceededError("Token budget exceeded")
```

---

#### 11.8.3 带Jitter指数退避（P1）

**文档描述**（7.6.2）：
```
带Jitter指数退避 - 429重试优化
当前：2, 4, 8秒递增
改进：添加随机Jitter避免多实例同时重试
```

**当前代码状态**（llm_strategies.py:342-348）：
```python
retry_delay = self.RETRY_DELAY * (2 ** attempt)  # 固定倍数
await asyncio.sleep(retry_delay)
```

**建议实现方式**：
```python
import random

def calculate_backoff_with_jitter(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """带Jitter的指数退避"""
    exponential_delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, exponential_delay * 0.1)  # 0-10%随机
    return min(exponential_delay + jitter, max_delay)
```

---

#### 11.8.4 熔断器（P1）

**文档描述**（7.6.2）：
```
熔断器 - 防止级联失败
当错误率达到阈值时，打开熔断器
熔断期间快速失败，不调用LLM
```

**建议实现方式**：
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit is open")
        # ... 调用func，失败时更新状态
```

---

#### 11.8.5 收敛检测（P1）

**文档描述**（7.6.2）：
```
收敛检测 - 加速循环结束判断
当连续多次调用相同工具+相同参数时，认为LLM陷入循环
提前终止并返回错误
```

**建议实现方式**：
```python
class ConvergenceDetector:
    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive
        self.history = []  # [(tool_name, params_hash), ...]
    
    def check(self, tool_name: str, params: dict) -> bool:
        """返回True表示检测到循环，应终止"""
        params_hash = hash(str(sorted(params.items())))
        current = (tool_name, params_hash)
        
        # 统计连续相同调用次数
        consecutive = 1
        for item in reversed(self.history[-self.max_consecutive:]):
            if item == current:
                consecutive += 1
            else:
                break
        
        self.history.append(current)
        return consecutive >= self.max_consecutive
```

---

#### 11.8.6 tool_start事件（P2）

**文档描述**（6.4.1）：
```
增加tool_start事件 - 工具开始执行时立即yield
让前端显示"正在调用xxx..."
解决长时间执行工具时用户等待无反馈的问题
```

**当前代码状态**：
- 工具执行后才yield action_tool
- 用户等待期间没有任何反馈

**建议实现方式**：
```python
# 在 _execute_tool 调用前立即yield
yield {
    "type": "tool_start",
    "step": step_count,
    "tool_name": tool_name,
    "tool_params": tool_params,
    "timestamp": create_timestamp()
}

# 然后执行工具
execution_result = await self._execute_tool(tool_name, tool_params)
```

---

### 11.9 实施建议

| Phase | 时间 | 改进项 | 预计工时 |
|-------|------|--------|----------|
| **Phase 1** | 短期 | Structured Output支持、Budget控制 | 4-6小时 |
| **Phase 2** | 中期 | 带Jitter退避、熔断器、收敛检测 | 6-8小时 |
| **Phase 3** | 长期 | 超长历史优化、前端字段完善 | 4-6小时 |

---

**文档版本**: v4.27
**汇总时间**: 2026-04-11 21:20:00
**汇总人**: 小沈
**汇总依据**: 基于文档第1-10章逐章对比分析后端代码实现

---

## 十二、未实现项详细说明（补充版）

**补充时间**: 2026-04-14 11:12:27
**补充人**: 小欧
**补充依据**: 对照文档设计与后端/前端代码实现的实际差异

---

### 12.1 未实现的字段详细说明

#### 12.1.1 start 类型缺失字段

| 缺失字段 | 文档参考位置 | 当前实现 | 说明 |
|----------|-------------|----------|------|
| **task** | 4.1节、4.8.1节 | ❌ 未实现 | 用户原始任务描述字段缺失 |

**文档设计** (4.1节 start字段):
```python
start: {
    step: number,
    model: string,
    provider: string,
    display_name: string,
    timestamp: number,
    session_id: string,
    task: string,           # ← 缺失：用户任务/问题
    user_message: string,
    security_check: object
}
```

**当前实现** (file_react.py):
```python
{
    'type': 'start',
    'step': next_step(),
    'timestamp': create_timestamp(),
    'display_name': f"{ai_service.provider} ({ai_service.model})",
    'provider': ai_service.provider,
    'model': ai_service.model,
    'task_id': task_id,
    'user_message': user_message[:40] if user_message else "",
    'security_check': {...}
    # ❌ 缺少 'task' 字段
}
```

---

#### 12.1.2 action_tool 类型缺失字段

| 缺失字段 | 文档参考位置 | 当前实现 | 说明 |
|----------|-------------|----------|------|
| **error_message** | 4.3节、5.2.3节、7.1.3节 | ⚠️ 在summary中 | 工具执行失败时的独立错误信息字段 |
| **execution_result** | 4.3节 | ⚠️ 用raw_data | 语义化的执行结果字段 |

**文档设计** (4.3节 action_tool字段):
```python
action_tool: {
    step: number,
    execution_status: string,
    execution_result: any,      # ← 当前用raw_data替代
    error_message: string,        # ← 当前在summary中
    timestamp: number
}
```

**当前实现** (base_react.py:250-274):
```python
# 工具执行失败时
action_tool_result = create_tool_error_result(
    tool_name=tool_name,
    error_message=execution_result.get("summary", "执行失败"),  # ⚠️ 用summary
    ...
)

# 工具执行成功时
yield {
    "type": "action_tool",
    "execution_status": "success",
    "raw_data": execution_result.get("data"),  # ⚠️ 用raw_data
    ...
}
```

---

#### 12.1.3 observation 类型缺失字段

| 缺失字段 | 文档参考位置 | 当前实现 | 说明 |
|----------|-------------|----------|------|
| **tool_params** | 4.4节、5.2.4节、7.1.4节 | ❌ 未实现 | 从thought复制的工具参数 |
| **return_direct** | 4.4节、5.2.4节、7.1.4节 | ❌ 未实现 | 工具直接返回标志，跳过后续LLM推理 |

**文档设计** (4.4节 observation字段):
```python
observation: {
    step: number,
    tool_name: string,
    tool_params: object,        # ← 缺失：从thought复制
    content: string,
    return_direct: boolean,     # ← 缺失：新功能
    timestamp: number
}
```

**当前实现** (base_react.py:296-303):
```python
yield {
    "type": "observation",
    "step": step_count,
    "timestamp": create_timestamp(),
    "tool_name": tool_name,
    # ❌ 缺少 "tool_params": tool_params
    "content": f"Tool '{tool_name}' executed: ..."
    # ❌ 缺少 "return_direct": ...
}
```

---

#### 12.1.4 final 类型缺失/不同字段

| 缺失字段 | 文档参考位置 | 当前实现 | 说明 |
|----------|-------------|----------|------|
| **response** | 4.5节、5.2.5节、7.1.5节 | ⚠️ 用content | 最终回答内容字段名不同 |
| **is_finished** | 4.5节、5.2.5节、7.1.5节 | ❌ 未实现 | 业务完成标志，前端无法显示"✅ 结束"徽章 |
| **thought** | 4.5节、5.2.5节、7.1.5节 | ❌ 未实现 | 最终推理总结字段 |
| **is_streaming** | 4.5节、5.2.5节、7.1.5节 | ❌ 未实现 | 流式输出标志，前端无打字机效果 |

**文档设计** (4.5节 final字段):
```python
final: {
    step: number,
    response: string,             # ← 当前用content
    is_finished: boolean,         # ← 缺失：业务完成标志
    timestamp: number,
    thought: string,             # ← 缺失：最终推理总结
    is_streaming: boolean        # ← 缺失：流式输出标志
}
```

**当前实现** (base_react.py:310-315):
```python
yield {
    "type": "final",
    "timestamp": create_timestamp(),
    "content": tool_params.get("result", thought_content)  # ⚠️ 用content而非response
    # ❌ 缺少 "is_finished": True
    # ❌ 缺少 "thought": ...
    # ❌ 缺少 "is_streaming": ...
}
```

**前端实现** (MessageItem.tsx:505-511):
```tsx
{step.type === "final" && (
  <div style={getStepStyle("final" as StepType)}>
    <span style={getStepContentStyle("final" as StepType, "primary")}>
      {step.content || ""}  {/* ⚠️ 用content而非response */}
    </span>
    {/* ❌ 没有显示 is_finished 徽章 */}
    {/* ❌ 没有显示 thought 字段 */}
  </div>
)}
```

---

#### 12.1.5 error 类型字段名不同

| 字段 | 文档参考位置 | 当前实现 | 说明 |
|------|-------------|----------|------|
| **error_type** | 4.6节、7.1.6节 | ⚠️ 用code | 详细错误分类字段名不同 |
| **recoverable** | 4.6节、7.1.6节、7.6.2节 | ❌ 未实现 | 是否可恢复字段缺失 |

**文档设计** (4.6节 error字段):
```python
error: {
    step: number,
    error_type: string,          # ← 当前用code
    error_message: string,
    timestamp: number,
    recoverable: boolean        # ← 缺失
}
```

**当前实现** (error_handler.py):
```python
# 文档设计：error_type = "max_steps_exceeded"
# 实际代码：code = "max_steps_exceeded"

# 文档设计：recoverable = True/False
# 实际代码：无此字段（前端用 errorRetryable）
```

---

### 12.2 未实现的功能改进项详细说明

#### 12.2.1 高优先级未实现项（P0）

##### (1) Structured Output 支持

**文档参考位置**: 7.6.1节

**文档描述**:
```
Structured Output 支持 - 提升LLM输出稳定性
通过LLM的response_format或tools参数约束输出结构
```

**当前代码状态**:
- `llm_strategies.py` 只有 `ResponseFormatStrategy` 类（未使用）
- 主要使用 JSON 文本解析 + 正则降级
- 没有强制使用 Function Calling

**建议实现方式**:
```python
# 方案1：Function Calling（推荐）
response = await llm_client.chat_with_tools(
    message=message,
    history=history_messages,
    tools=self.tools  # 强制使用tools参数
)

# 方案2：response_format (需模型支持)
response = await llm_client.chat_with_response_format(
    message=message,
    history=history_messages,
    response_format={"type": "json_object", "json_schema": {...}}
)
```

---

##### (2) Budget 控制 + 成本追踪

**文档参考位置**: 7.6.1节

**文档描述**:
```
Budget 控制 + 成本追踪 - 成本管理
- 设置每次任务的最大token消耗
- 追踪LLM调用token数量
- 计算任务成本
```

**当前代码状态**:
- 没有token计费逻辑
- 没有成本统计
- 没有Budget上限控制

**建议实现方式**:
```python
class BaseAgent:
    def __init__(self, max_steps: int = 100, max_tokens: int = 100000):
        self.max_tokens = max_tokens
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def track_usage(self, prompt_tokens: int, completion_tokens: int):
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_cost += self._calculate_cost(prompt_tokens, completion_tokens)
        if self.total_tokens > self.max_tokens:
            raise BudgetExceededError("Token budget exceeded")
```

---

##### (3) 超长历史优化

**文档参考位置**: 7.6.1节、10.2.4节

**文档描述**:
```
超长历史优化 - 解决429错误
当前只检查消息数量(<=15不触发清理)，没有检查消息总长度
问题：工具执行结果很长(如390627字符的observation)，导致API请求体过大触发429
思路：添加总长度检查，如 total_chars > 100000 时强制清理 observation 内容(可截断或只保留摘要)
```

**当前代码状态** (base_react.py:376-399):
```python
def _trim_history(self) -> None:
    # TODO [2026-04-11]: 当前只检查消息数量，没有检查消息总长度
    # TODO: 还需要检查消息总长度
    total_chars = sum(len(msg.get("content", "")) for msg in self.conversation_history)
    if total_chars > 100000:
        logger.warning(f"[History] Warning: total chars={total_chars} exceeds limit, should trim")
        # TODO: 这里应该截断或压缩超长的 observation 内容
```

**建议实现方式**:
```python
def _trim_history(self) -> None:
    # 检查总长度
    total_chars = sum(len(msg.get("content", "")) for msg in self.conversation_history)
    if total_chars > 100000:
        # 压缩超长observation内容
        for i, msg in enumerate(self.conversation_history):
            if msg.get("content", "").startswith("Observation:") and \
               len(msg["content"]) > 50000:
                # 截断或只保留摘要
                self.conversation_history[i]["content"] = \
                    msg["content"][:5000] + "\n[...已截断...]"
```

---

#### 12.2.2 中优先级未实现项（P1）

##### (4) 带Jitter指数退避

**文档参考位置**: 7.6.2节

**文档描述**:
```
带Jitter指数退避 - 429重试优化
当前：2, 4, 8秒递增
改进：添加随机Jitter避免多实例同时重试
```

**当前代码状态** (llm_strategies.py:342-348):
```python
retry_delay = self.RETRY_DELAY * (2 ** attempt)  # 固定倍数，无Jitter
await asyncio.sleep(retry_delay)
```

**建议实现方式**:
```python
import random

def calculate_backoff_with_jitter(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """带Jitter的指数退避"""
    exponential_delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, exponential_delay * 0.1)  # 0-10%随机
    return min(exponential_delay + jitter, max_delay)
```

---

##### (5) 熔断器

**文档参考位置**: 7.6.2节

**文档描述**:
```
熔断器 - 防止级联失败
当错误率达到阈值时，打开熔断器
熔断期间快速失败，不调用LLM
```

**建议实现方式**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit is open")
        # ... 调用func，失败时更新状态
```

---

##### (6) 收敛检测

**文档参考位置**: 7.6.2节

**文档描述**:
```
收敛检测 - 加速循环结束判断
当连续多次调用相同工具+相同参数时，认为LLM陷入循环
提前终止并返回错误
```

**建议实现方式**:
```python
class ConvergenceDetector:
    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive
        self.history = []  # [(tool_name, params_hash), ...]
    
    def check(self, tool_name: str, params: dict) -> bool:
        """返回True表示检测到循环，应终止"""
        params_hash = hash(str(sorted(params.items())))
        current = (tool_name, params_hash)
        
        # 统计连续相同调用次数
        consecutive = 1
        for item in reversed(self.history[-self.max_consecutive:]):
            if item == current:
                consecutive += 1
            else:
                break
        
        self.history.append(current)
        return consecutive >= self.max_consecutive
```

---

##### (7) start添加task字段

**文档参考位置**: 7.6.2节

**文档描述**:
```
start添加task字段 - 显示用户原始任务
前端可显示用户最初的任务描述
```

---

##### (8) error添加recoverable字段

**文档参考位置**: 7.6.2节、7.1.6节

**文档描述**:
```
error添加recoverable字段 - 前端显示"重试"按钮
根据recoverable字段决定是否显示重试按钮
```

---

#### 12.2.3 低优先级未实现项（P2）

##### (9) action_tool添加error_message字段

**文档参考位置**: 7.6.3节

**文档描述**:
```
action_tool添加error_message字段 - 记录工具执行错误
```

---

##### (10) return_direct机制

**文档参考位置**: 7.6.3节、4.4节、7.1.4节

**文档描述**:
```
return_direct机制 - 工具直接返回
当return_direct=True时，跳过LLM分析，直接返回结果给用户
```

---

##### (11) tool_start事件

**文档参考位置**: 6.4.1节

**文档描述**:
```
增加tool_start事件 - 工具开始执行时立即yield
让前端显示"正在调用xxx..."
解决长时间执行工具时用户等待无反馈的问题
```

**当前代码状态**:
- 工具执行后才yield action_tool
- 用户等待期间没有任何反馈

**建议实现方式**:
```python
# 在 _execute_tool 调用前立即yield
yield {
    "type": "tool_start",
    "step": step_count,
    "tool_name": tool_name,
    "tool_params": tool_params,
    "timestamp": create_timestamp()
}

# 然后执行工具
execution_result = await self._execute_tool(tool_name, tool_params)
```

---

### 12.3 总结

| 类别 | 总数 | 已实现 | 未实现 |
|------|------|--------|--------|
| **字段缺失** | 10 | 3 | 7 |
| **字段名不同** | 3 | 0 | 3 |
| **功能改进** | 11 | 1 | 10 |
| **总计** | 24 | 4 | 20 |

**建议优先级**:
1. **第一优先级**: final添加is_finished/thought字段、start添加task字段
2. **第二优先级**: observation添加tool_params、error添加recoverable
3. **第三优先级**: Structured Output支持、Budget控制
4. **第四优先级**: 带Jitter退避、熔断器、收敛检测

---

**补充版本**: v1.0
**补充时间**: 2026-04-14 11:12:27
**补充人**: 小欧
**补充依据**: 文档第4-7章、第10-11章与实际代码对照分析

---

## 十三、可选字段深入分析（2026-04-14）

**分析时间**: 2026-04-14 11:25:08
**分析人**: 小欧
**分析方法**: 对照文档第4章设计与后端/前端代码实现，逐字段分析必要性

---

### 13.1 start 可选字段分析

**文档设计的可选字段**：
- `agent_id`: Agent标识
- `max_steps`: 最大迭代步数
- `available_tools`: 可用工具列表

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **agent_id** | 4.1节 | ❌ 未实现 | ❌ 无必要 | 当前已有task_id和session_id足够区分任务，agent类型由子类(file_react)决定 |
| **max_steps** | 4.1节 | ⚠️ 部分实现 | ⚠️ 可加 | **有价值** - 前端可显示"已执行X步/最多Y步"，当前代码已从参数传入但未传递给前端 |
| **available_tools** | 4.1节 | ❌ 未实现 | ❌ 无必要 | System prompt中已有工具列表，前端不需要重复显示 |

**建议添加**: `max_steps`（中优先级）

---

### 13.2 action_tool 可选字段分析

**文档设计的可选字段**：
- `execution_time_ms`: 执行耗时（毫秒）
- `summary`: 执行结果摘要
- `raw_data`: 原始数据
- `retry_count`: 重试次数

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **execution_time_ms** | 4.3节 | ❌ 未实现 | ⚠️ 可加 | **高优先级** - 可监控工具性能，前端显示执行耗时，只需在action_tool yield前计算耗时 |
| **summary** | 4.3节 | ✅ 已实现 | ✅ 已有 | 当前已实现 |
| **raw_data** | 4.3节 | ✅ 已实现 | ✅ 已有 | 当前已实现 |
| **retry_count** | 4.3节 | ✅ 已实现(action_retry_count) | ✅ 已有 | 当前已实现(action_retry_count) |

**实现方式**（参考代码）:
```python
# 在 _execute_tool 调用前后计算耗时
start_time = time.time()
execution_result = await self._execute_tool(tool_name, tool_params)
execution_time_ms = int((time.time() - start_time) * 1000)

yield {
    "type": "action_tool",
    "execution_time_ms": execution_time_ms,
    ...
}
```

---

### 13.3 observation 可选字段分析

**文档设计的可选字段**：
- `return_direct`: 是否直接返回结果给用户（跳过后续推理）

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **return_direct** | 4.4节、7.6.3节 | ❌ 未实现 | ⚠️ 可加但复杂 | **低优先级** - 需要工具层面支持return_direct，当前无此功能，属于新功能设计 |

---

### 13.4 final 可选字段分析

**文档设计的可选字段**：
- `thought`: 最终推理总结
- `is_streaming`: 是否流式输出
- `total_steps`: 总执行步骤数（框架层面）
- `total_tokens`: 总使用token数（框架层面）
- `usage`: 使用统计（框架层面）

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **thought** | 4.5节、5.2.5节 | ❌ 未实现 | ✅ 非常有价值 | **高优先级** - 前端可显示最终推理过程，增强用户体验 |
| **is_streaming** | 4.5节、5.2.5节 | ❌ 未实现 | ⚠️ 部分需要 | **中优先级** - 当前final不是流式，但为未来扩展预留有意义 |
| **total_steps** | 4.5节 | ⚠️ 部分实现 | ✅ 已有 | file_react.py中已传递给final_result，但不在step中 |
| **total_tokens** | 4.5节 | ❌ 未实现 | ⚠️ 可加 | **中优先级** - 需要LLM返回token统计 |
| **usage** | 4.5节 | ❌ 未实现 | ❌ 暂无必要 | 当前没有token统计功能，暂不需要 |

**实现方式**（参考代码）:
```python
# final生成时
yield {
    "type": "final",
    "thought": thought_content,  # 最终推理
    "is_finished": True,
    "is_streaming": False,
    ...
}
```

---

### 13.5 error 可选字段分析

**文档设计的可选字段**：
- `stack_trace`: 堆栈跟踪
- `context`: 错误上下文
- `suggested_fix`: 建议修复
- `retry_suggestion`: 重试建议

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **stack_trace** | 4.6节 | ⚠️ 部分实现(errorStack) | ✅ 已有 | ErrorDetail组件已有errorStack |
| **context** | 4.6节 | ❌ 未实现 | ⚠️ 可加 | **中优先级** - 有价值，记录错误发生时的上下文(当前step、tool_name等) |
| **suggested_fix** | 4.6节 | ❌ 未实现 | ⚠️ 可加 | **低优先级** - 根据错误类型生成修复建议 |
| **retry_suggestion** | 4.6节 | ❌ 未实现 | ⚠️ 可加 | **低优先级** - 重试建议，当前errorHandler有retryable字段 |

---

### 13.6 chunk 可选字段分析

**文档设计的可选字段**：
- `index`: chunk序号
- `role`: 角色（assistant）
- `model`: 使用的模型
- `finish_reason`: 完成原因（stop/length/tool_calls等）

| 可选字段 | 文档参考 | 当前实现 | 分析结果 | 建议 |
|----------|---------|---------|---------|------|
| **index** | 4.7节 | ❌ 未实现 | ❌ 暂无必要 | chunk主要用于流式显示，不需要序号 |
| **role** | 4.7节 | ❌ 未实现 | ❌ 暂无必要 | 固定是assistant，前端已知 |
| **model** | 4.7节 | ❌ 未实现 | ⚠️ 可加 | **低优先级** - 为完整性可以加，但当前message级别已有model |
| **finish_reason** | 4.7节 | ❌ 未实现 | ⚠️ 可加 | **低优先级** - 有价值，可显示LLM为何停止(stop/length) |

---

### 13.7 建议添加的可选字段汇总

| 优先级 | 类型 | 字段 | 文档参考 | 理由 |
|--------|------|------|---------|------|
| **P0高** | final | `thought` | 4.5节、5.2.5节 | 前端显示最终推理，增强用户体验 |
| **P1中** | action_tool | `execution_time_ms` | 4.3节 | 监控工具性能，前端显示执行耗时 |
| **P1中** | final | `is_streaming` | 4.5节 | 为未来流式输出扩展预留 |
| **P1中** | error | `context` | 4.6节 | 记录错误上下文，助于调试 |
| **P2低** | start | `max_steps` | 4.1节 | 前端显示进度(X/Y步) |

---

**分析版本**: v1.0
**分析时间**: 2026-04-14 11:25:08
**分析人**: 小欧
**分析方法**: 对照文档设计与后端/前端代码实现，逐字段分析必要性
