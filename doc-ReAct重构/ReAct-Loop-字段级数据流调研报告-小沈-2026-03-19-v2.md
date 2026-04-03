# ReAct Loop 字段级数据流调研报告（v2）

**文档版本**: v2.0  
**创建时间**: 2026-03-20 00:05:00  
**编写人**: 小沈  
**参考资料**: LangChain ReAct Agent 官方实现

---

## 一、ReAct Loop 的本质

**ReAct Loop = 信息在三个 stage 之间流转**

```
start → [ thought → action_tool → observation ] → ... → final
              ↑                              ↓
              └──────── scratchpad 累积 ←────┘
```

**三个 stage**：
1. **thought**：LLM 思考，决定下一步
2. **action_tool**：执行工具
3. **observation**：工具执行结果

**loop 如何实现**：通过字段传递信息，让 LLM 记住之前发生了什么

---

## 二、第一轮 Loop（从 start 进入）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         第 1 轮 Loop                                      │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 调用（输入）                                                       ║ │
│  ║                                                                        ║ │
│  ║  prompt = "你是文件管理助手..."                                         ║ │
│  ║  tools = [list_directory, read_file, write_file, ...]                  ║ │
│  ║  user_input = "查看桌面文件"                                            ║ │
│  ║  scratchpad = ""                                                        ║ │
│  ║           ↑                                                              ║ │
│  ║           └─ 第1轮为空，第N轮是前(N-1)轮的历史累积                      ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 输出 → thought_stage                                               ║ │
│  ║                                                                        ║ │
│  ║  thought_stage = {                                                     ║ │
│  ║      "tool": "list_directory",        ← 字段1: 工具名称                ║ │
│  ║      "tool_input": {"path": "C:/Desktop"},  ← 字段2: 工具参数          ║ │
│  ║      "log": "Thought: 用户要看桌面文件，我需要先列出目录\n"            ║ │
│  ║             "Action: list_directory\n"                                 ║ │
│  ║             "Action Input: {\"path\": \"C:/Desktop\"}"                  ║ │
│  ║                ↑                                                        ║ │
│  ║                └─ 字段3: LLM的完整思考过程（包含Thought+Action+Input）  ║ │
│  ║  }                                                                     ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  action_tool_stage（工具执行）                                          ║ │
│  ║                                                                        ║ │
│  ║  输入字段:                                                              ║ │
│  ║    - thought_stage.tool          = "list_directory"                  ║ │
│  ║    - thought_stage.tool_input     = {"path": "C:/Desktop"}            ║ │
│  ║                         ↑                                              ║ │
│  ║                         └─ 从 thought_stage 的字段1、字段2 传入        ║ │
│  ║                                                                        ║ │
│  ║  执行: list_directory(path="C:/Desktop")                               ║ │
│  ║                                                                        ║ │
│  ║  输出:                                                                  ║ │
│  ║    - observation = "[file1.txt, file2.doc, folder1/]"  ← 纯字符串    ║ │
│  ║         ↑                                                              ║ │
│  ║         └─ 字段4: 工具执行结果（observation），不判断，直接传递        ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  中间步骤存储（为下一轮准备）                                            ║ │
│  ║                                                                        ║ │
│  ║  intermediate_steps = [                                                ║ │
│  ║      (                                                              ║ │
│  ║          {                                                           ║ │
│  ║              "tool": "list_directory",                               ║ │
│  ║              "tool_input": {"path": "C:/Desktop"},                  ║ │
│  ║              "log": "Thought: ...\nAction: ...\nAction Input: ..."  ║ │
│  ║                        ↑  字段3                                     ║ │
│  ║          },                                                           ║ │
│  ║          "[file1.txt, file2.doc, folder1/]"  ← 字段4（observation） ║ │
│  ║      )                                                                ║ │
│  ║  ]                                                                    ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、第二轮 Loop（从 observation 返回 thought）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         第 2 轮 Loop                                      │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 调用（输入）                                                       ║ │
│  ║                                                                        ║ │
│  ║  prompt = "你是文件管理助手..."                                         ║ │
│  ║  tools = [list_directory, read_file, ...]                              ║ │
│  ║  user_input = "查看桌面文件"                                            ║ │
│  ║                                                                        ║ │
│  ║  scratchpad = format_log_to_str(intermediate_steps)                   ║ │
│  ║               ┌─────────────────────────────────────────────────────┐ ║ │
│  ║               │ 第1轮的 log + 第1轮的 observation 格式化后的文本:     │ ║ │
│  ║               │                                                     │ ║ │
│  ║               │ Thought: 用户要看桌面文件，我需要先列出目录          │ ║ │
│  ║               │ Action: list_directory                              │ ║ │
│  ║               │ Action Input: {"path": "C:/Desktop"}               │ ║ │
│  ║               │ Observation: [file1.txt, file2.doc, folder1/]     │ ║ │
│  ║               │ Thought: （LLM在这里继续思考...）                    │ ║ │
│  ║               └─────────────────────────────────────────────────────┘ ║ │
│  ║                              ↑                                         ║ │
│  ║                              └─ 字段5: scratchpad（累积的历史）       ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 输出 → thought_stage（第2轮）                                     ║ │
│  ║                                                                        ║ │
│  ║  thought_stage = {                                                     ║ │
│  ║      "tool": "read_file",           ← 字段1: 工具名称（变了！）        ║ │
│  ║      "tool_input": {"path": "C:/Desktop/file1.txt"},  ← 字段2        ║ │
│  ║      "log": "Thought: 已看到文件列表，file1.txt可能是用户要的\n"      ║ │
│  ║             "Action: read_file\n"                                      ║ │
│  ║             "Action Input: {\"path\": \"C:/Desktop/file1.txt\"}"        ║ │
│  ║                ↑                                                        ║ │
│  ║                └─ 字段3: LLM基于scratchpad（字段5）思考后的输出       ║ │
│  ║  }                                                                     ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  action_tool_stage（工具执行）                                          ║ │
│  ║                                                                        ║ │
│  ║  输入字段:                                                              ║ │
│  ║    - thought_stage.tool          = "read_file"                        ║ │
│  ║    - thought_stage.tool_input     = {"path": "C:/Desktop/file1.txt"}  ║ │
│  ║                                                                        ║ │
│  ║  执行: read_file(path="C:/Desktop/file1.txt")                          ║ │
│  ║                                                                        ║ │
│  ║  输出:                                                                  ║ │
│  ║    - observation = "文件内容：Hello World!"  ← 字段4                  ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  中间步骤存储（第2轮后）                                                ║ │
│  ║                                                                        ║ │
│  ║  intermediate_steps = [                                                ║ │
│  ║      (                                                              ║ │
│  ║          {第1轮的tool, tool_input, log},                              ║ │
│  ║          "[file1.txt, file2.doc, folder1/]"   ← 第1轮observation      ║ │
│  ║      ),                                                               ║ │
│  ║      (                                                              ║ │
│  ║          {第2轮的tool, tool_input, log},                              ║ │
│  ║          "文件内容：Hello World!"   ← 第2轮observation               ║ │
│  ║      )                                                                ║ │
│  ║  ]                                                                    ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、第 N 轮 Loop（继续或退出）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         第 N 轮 Loop                                      │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 调用（输入）                                                       ║ │
│  ║                                                                        ║ │
│  ║  scratchpad = format_log_to_str(intermediate_steps)                   ║ │
│  ║               ┌─────────────────────────────────────────────────────┐ ║ │
│  ║               │ 累积前(N-1)轮的历史:                                 │ ║ │
│  ║               │                                                     │ ║ │
│  ║               │ 第1轮: Thought → Action → Observation                │ ║ │
│  ║               │ 第2轮: Thought → Action → Observation                │ ║ │
│  ║               │ ...                                                  │ ║ │
│  ║               │ 第(N-1)轮: Thought → Action → Observation            │ ║ │
│  ║               │                                                     │ ║ │
│  ║               │ 字段5: scratchpad（所有历史的累积文本）               │ ║ │
│  ║               └─────────────────────────────────────────────────────┘ ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  LLM 输出（两种可能）                                                   ║ │
│  ║                                                                        ║ │
│  ║  ┌────────────────────────────────────────────────────────────────┐ ║ │
│  ║  │ 情况A: 继续行动                                                   │ ║ │
│  ║  │                                                                │ ║ │
│  ║  │ thought_stage = {                                              │ ║ │
│  ║  │     "tool": "read_file",           ← 继续调用工具               │ ║ │
│  ║  │     "tool_input": {...},                                       │ ║ │
│  ║  │     "log": "Thought: ..."                                       │ ║ │
│  ║  │ }                                                              │ ║ │
│  ║  │                                                                │ ║ │
│  ║  │ → 进入 action_tool → observation → 下一轮                      │ ║ │
│  ║  └────────────────────────────────────────────────────────────────┘ ║ │
│  ║                                                                        ║ │
│  ║  ┌────────────────────────────────────────────────────────────────┐ ║ │
│  ║  │ 情况B: 完成任务（action = "finish"）                           │ ║ │
│  ║  │                                                                │ ║ │
│  ║  │ thought_stage = {                                              │ ║ │
│  ║  │     "tool": "finish",            ← 退出信号                   │ ║ │
│  ║  │     "tool_input": {},                                         │ ║ │
│  ║  │     "log": "Thought: I now know the final answer\n"          │ ║ │
│  ║  │              "Final Answer: 已找到桌面文件内容..."             │ ║ │
│  ║  │ }                                                              │ ║ │
│  ║  │                                                                │ ║ │
│  ║  │ → 进入 final_stage（结束）                                      │ ║ │
│  ║  └────────────────────────────────────────────────────────────────┘ ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五、字段汇总表

### 5.1 三个 stage 的字段

| Stage | 字段名 | 类型 | 说明 | 数据流向 |
|-------|--------|------|------|---------|
| **thought** | `tool` | string | 工具名称 | → action_tool |
| **thought** | `tool_input` | dict | 工具参数 | → action_tool |
| **thought** | `log` | string | LLM完整思考（包含Thought+Action+Input） | → intermediate_steps |
| **action_tool** | 无固定字段 | - | 工具执行器 | 输入: tool + tool_input |
| **action_tool** | `observation` | string | 工具执行结果（纯字符串） | → intermediate_steps |
| **observation** | 无固定字段 | - | observation不单独存在 | 合并到intermediate_steps |

### 5.2 中间存储的字段

| 字段名 | 类型 | 说明 | 数据流向 |
|--------|------|------|---------|
| `intermediate_steps` | List[Tuple[AgentAction, str]] | 中间步骤列表 | 包含所有历史 |
| `AgentAction.tool` | string | 工具名称 | 中间步骤第1项的字段 |
| `AgentAction.tool_input` | dict | 工具参数 | 中间步骤第1项的字段 |
| `AgentAction.log` | string | LLM完整思考 | → scratchpad |
| `str` (observation) | string | 工具执行结果 | → scratchpad |

### 5.3 scratchpad 的字段

| 字段名 | 类型 | 说明 | 数据流向 |
|--------|------|------|---------|
| `scratchpad` | string | format_log_to_str(intermediate_steps) 的输出 | → LLM 输入 |

---

## 六、字段在 Loop 中的流动关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   ┌──────────────┐     tool       ┌──────────────────┐   observation   ┌──┤
│   │   thought    │ ────────────► │   action_tool    │ ──────────────► │  │
│   │   (LLM输出)  │   tool_input │   (工具执行)     │                │  │
│   └──────────────┘               └──────────────────┘                │  │
│          │                                                          │  │
│          │ log                                                      ▼  │
│          │                                               ┌──────────────┤
│          ▼                                               │ intermediate │
│   ┌──────────────┐                                       │   _steps     │
│   │  scratchpad  │ ◄─────────────────────────────────── │ (元组列表)   │
│   │ (格式化文本) │       format_log_to_str()             └──────────────┤
│   └──────┬───────┘                                              │  │
│          │                                                        │  │
│          │ 返回给LLM作为下一轮输入                               │  │
│          │                                                        │  │
│          │                                                        │  │
│   ┌──────┴───────┐                                               │  │
│   │     LLM      │ ◄───────────────────────────────────────────┘  │
│   │   (思考)     │                                                │
│   └──────────────┘                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

图例：
  ──────►  信息传入/传出
  ───────►  累积历史
  ├─┤     组合结构
```

**字段流动说明**：

1. **thought → action_tool**：
   - `tool` + `tool_input` 从 thought 传入 action_tool

2. **action_tool → intermediate_steps**：
   - `observation`（工具执行结果）添加到 intermediate_steps

3. **intermediate_steps → scratchpad**：
   - 通过 `format_log_to_str()` 将所有历史的 `(AgentAction.log, observation)` 格式化为文本

4. **scratchpad → LLM**：
   - scratchpad 作为下一轮 LLM 的输入，让 LLM 知道之前发生了什么

---

## 七、参考资料

| 资料 | 链接 |
|------|------|
| LangChain AgentAction | https://reference.langchain.com/python/langchain-core/agents/AgentAction |
| LangChain format_log_to_str | https://reference.langchain.com/python/langchain-classic/agents/format_scratchpad/log/format_log_to_str |
| ReAct Prompt 模板 | https://github.com/langchain-ai/langchain-hub/blob/master/slots/prompts/hwchase17/react/prompt.yaml |

---

**文档结束**
